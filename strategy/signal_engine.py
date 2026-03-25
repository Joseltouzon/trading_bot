# strategy/signal_engine.py
# Multi-strategy engine: ejecuta las 6 estrategias en paralelo
# 5m: RSI+BB, Stop Hunt | 15m: EMA, MACD | 1h: Volatility Squeeze

import config as CFG
from core.models import SignalEvent
from strategy.ema_adx_breakout import compute_signals
from strategy.stop_hunt import compute_stop_hunt_signals
from strategy.rsi_bb_reversion import compute_rsi_bb_signals
from strategy.macd_momentum import compute_macd_momentum_signals
from strategy.structure_break import compute_structure_break_signals
from strategy.volatility_squeeze import compute_volatility_squeeze_signals


# Estrategias activas y sus timeframes
ACTIVE_STRATEGIES = {
    "rsi_bb_reversion": {"compute": compute_rsi_bb_signals, "short": "RSI"},
    "stop_hunt": {"compute": compute_stop_hunt_signals, "short": "HNT"},
    "ema_breakout": {"compute": compute_signals, "short": "EMA"},
    "macd_momentum": {"compute": compute_macd_momentum_signals, "short": "MAC"},
    "structure_break": {"compute": compute_structure_break_signals, "short": "STR"},
    "volatility_squeeze": {"compute": compute_volatility_squeeze_signals, "short": "VSQ"},
}


class SignalEngine:

    def __init__(self, market_cache, signal_bus, log, strategy_mode: str = "ema_breakout"):
        self.market = market_cache
        self.bus = signal_bus
        self.log = log
        self.strategy_mode = strategy_mode
        self._last_processed = {}  # (symbol, strategy) -> close_time_ms

    def set_strategy_mode(self, mode: str):
        valid = list(ACTIVE_STRATEGIES.keys()) + ["auto", "all"]
        if mode in valid:
            old_mode = self.strategy_mode
            self.strategy_mode = mode
            if old_mode != mode:
                self.log.info(f"[SIGNAL] Strategy mode changed to: {mode}")
        else:
            self.log.warning(f"[SIGNAL] Unknown strategy mode: {mode}")

    def _get_strategies_to_run(self):
        """Retorna las estrategias que deben ejecutarse según el modo."""
        if self.strategy_mode == "all":
            return list(ACTIVE_STRATEGIES.keys())
        elif self.strategy_mode == "auto":
            # auto: 6 estrategias
            return ["rsi_bb_reversion", "stop_hunt", "macd_momentum", "ema_breakout", "structure_break", "volatility_squeeze"]
        elif self.strategy_mode in ACTIVE_STRATEGIES:
            return [self.strategy_mode]
        return []

    def process_all(self, strategy_symbols: dict, max_positions_reached: bool = False):
        """Ejecuta las estrategias activas, cada una con sus propios símbolos.

        Itera por estrategia → por símbolo de esa estrategia.
        Filtra por STRATEGY_ENABLED (dashboard toggle).
        """
        if max_positions_reached:
            return

        strategies = self._get_strategies_to_run()
        enabled_map = getattr(CFG, "STRATEGY_ENABLED", {})

        for strategy_name in strategies:
            # Filtrar por enabled (si existe el mapa)
            if enabled_map and not enabled_map.get(strategy_name, True):
                continue

            symbols = strategy_symbols.get(strategy_name, [])
            if not symbols:
                continue

            info = ACTIVE_STRATEGIES[strategy_name]
            interval = CFG.STRATEGY_INTERVALS.get(strategy_name, "5m")

            for symbol in symbols:
                # Obtener DF del timeframe correcto
                df = self.market.get_df_copy(symbol, interval)
                if df is None or len(df) < 50:
                    continue

                # Detección de nueva vela (independiente por timeframe)
                last_close_time = int(df["close_time"].iloc[-2])
                processed_key = (symbol, strategy_name)

                if self._last_processed.get(processed_key) == last_close_time:
                    continue

                self._last_processed[processed_key] = last_close_time

                # Ejecutar estrategia (excluir última vela parcial)
                try:
                    sig = info["compute"](df.iloc[:-1])
                    self._publish_signal(symbol, strategy_name, sig, last_close_time)
                except Exception as e:
                    self.log.error(f"[SIGNAL] {symbol} {strategy_name} error: {e}")

    def _publish_signal(self, symbol: str, strategy_name: str, sig: dict, last_close_time: int):
        """Procesa el resultado de una estrategia y publica señal si corresponde."""
        short = ACTIVE_STRATEGIES[strategy_name]["short"]

        signal_long = sig.get("breakout_long", False)
        signal_short = sig.get("breakout_short", False)

        # Log de estado
        self.log.info(
            f"{symbol} | {strategy_name} | "
            f"trend={sig.get('trend', 'NONE')} | "
            f"L={signal_long} | S={signal_short} | "
            f"adx={sig.get('adx', 0):.1f} | "
            f"vol={sig.get('vol_ratio', 0):.2f}"
        )

        if signal_long:
            self.bus.publish(SignalEvent(symbol, "LONG", sig, last_close_time))
            self.log.info(f"{symbol} → LONG published ({strategy_name})")

        elif signal_short:
            self.bus.publish(SignalEvent(symbol, "SHORT", sig, last_close_time))
            self.log.info(f"{symbol} → SHORT published ({strategy_name})")
