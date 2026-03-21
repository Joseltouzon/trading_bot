# strategy/signal_engine.py
# Multi-strategy engine: ejecuta las 4 estrategias en paralelo
# 5m: RSI+BB, Stop Hunt | 15m: EMA, MACD

import config as CFG
from core.models import SignalEvent
from strategy.ema_adx_breakout import compute_signals
from strategy.stop_hunt import compute_stop_hunt_signals
from strategy.rsi_bb_reversion import compute_rsi_bb_signals
from strategy.macd_momentum import compute_macd_momentum_signals


# Estrategias activas y sus timeframes
ACTIVE_STRATEGIES = {
    "rsi_bb_reversion": {"compute": compute_rsi_bb_signals, "short": "RSI"},
    "stop_hunt": {"compute": compute_stop_hunt_signals, "short": "HNT"},
    "ema_breakout": {"compute": compute_signals, "short": "EMA"},
    "macd_momentum": {"compute": compute_macd_momentum_signals, "short": "MAC"},
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
        if self.strategy_mode == "all" or self.strategy_mode == "auto":
            return list(ACTIVE_STRATEGIES.keys())
        elif self.strategy_mode in ACTIVE_STRATEGIES:
            return [self.strategy_mode]
        return []

    def process_symbol(self, symbol: str, max_positions_reached: bool = False):
        """Ejecuta las estrategias activas para un símbolo.

        Cada estrategia usa su propio DF (5m o 15m) y su propia detección de nueva vela.
        """
        if max_positions_reached:
            return

        strategies = self._get_strategies_to_run()

        for strategy_name in strategies:
            info = ACTIVE_STRATEGIES[strategy_name]
            interval = CFG.STRATEGY_INTERVALS.get(strategy_name, "5m")

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

            # Ejecutar estrategia
            try:
                sig = info["compute"](df)
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
