# strategy/signal_engine.py
import config as CFG
from core.models import SignalEvent
from strategy.ema_adx_breakout import compute_signals
from strategy.stop_hunt import compute_stop_hunt_signals
from strategy.vwap_refresh import compute_vwap_refresh_signals
from strategy.rsi_bb_reversion import compute_rsi_bb_signals
from strategy.market_regime import should_switch_strategy, get_regime_confidence
from strategy.indicators import ema, atr, adx


class SignalEngine:

    def __init__(self, market_cache, signal_bus, log, strategy_mode: str = "ema_breakout"): 
        self.market = market_cache
        self.bus = signal_bus
        self.log = log
        self.strategy_mode = strategy_mode
        self._last_processed = {}
        self._effective_mode = strategy_mode if strategy_mode != "auto" else None
        self._regime_per_symbol = {}
        self._last_regime_check = {}
        self._indicator_cache = {}
        self._cache_symbol = None
        self._regime_check_counter = {}
        self._regime_check_interval = 3

    def _get_effective_mode_for_symbol(self, symbol: str, df) -> str:
        if self.strategy_mode != "auto":
            return self.strategy_mode

        if not isinstance(self._effective_mode, dict):
            self._effective_mode = {}

        if symbol in self._effective_mode and self._effective_mode[symbol] is not None:
            return self._effective_mode[symbol]

        _, should_switch, regime_info = should_switch_strategy(
            df, "ema_breakout", threshold_confidence=0.70
        )
        
        self._effective_mode[symbol] = regime_info.get("recommended_strategy", "ema_breakout")
        return self._effective_mode[symbol]

    def set_strategy_mode(self, mode: str):
        if mode in ["ema_breakout", "stop_hunt", "vwap_refresh", "rsi_bb_reversion", "auto"]:
            old_mode = self.strategy_mode
            self.strategy_mode = mode
            self._effective_mode = {} if mode == "auto" else None
            self._regime_per_symbol = {}
            self._indicator_cache = {}
            self._cache_symbol = None
            if old_mode != mode:
                self.log.info(f"[SIGNAL] Strategy mode changed to: {mode}")
        else:
            self.log.warning(f"[SIGNAL] Unknown strategy mode: {mode}, keeping {self.strategy_mode}")

    def process_symbol(self, symbol: str, max_positions_reached: bool = False):
        df = self.market.get_df_copy(symbol)
        if df is None or len(df) < 50:
            return

        last_close_time = int(df["close_time"].iloc[-2])

        if self._last_processed.get(symbol) == last_close_time:
            return

        self._last_processed[symbol] = last_close_time

        if max_positions_reached:
            return

        effective_mode = self._get_effective_mode_for_symbol(symbol, df)

        if effective_mode == "stop_hunt":
            self._process_stop_hunt(symbol, df, last_close_time)
        elif effective_mode == "vwap_refresh":
            self._process_vwap_refresh(symbol, df, last_close_time)
        elif effective_mode == "rsi_bb_reversion":
            self._process_rsi_bb_reversion(symbol, df, last_close_time)
        else:
            self._process_ema_breakout(symbol, df, last_close_time)

    def check_and_switch_regime(self, symbol: str):
        if self.strategy_mode != "auto":
            return

        self._regime_check_counter[symbol] = self._regime_check_counter.get(symbol, 0) + 1
        
        if self._regime_check_counter.get(symbol, 0) < self._regime_check_interval:
            return

        self._regime_check_counter[symbol] = 0

        df = self.market.get_df_copy(symbol)
        if df is None or len(df) < 50:
            return

        current_mode = self._effective_mode.get(symbol) if isinstance(self._effective_mode, dict) else "ema_breakout"
        new_strategy, should_switch, regime_info = should_switch_strategy(
            df, current_mode, threshold_confidence=0.70
        )

        last_check = self._last_regime_check.get(symbol)
        if last_check != regime_info.get("recommended_strategy"):
            self.log.info(
                f"[REGIME] {symbol} | regime={regime_info.get('recommended_strategy', 'unknown')} | "
                f"conf={regime_info.get('confidence', 0):.2f} | "
                f"adx={regime_info.get('adx', 0):.1f} | "
                f"range={regime_info.get('range_bound', False)} | "
                f"vol={regime_info.get('vol_ratio', 0):.1f}"
            )
            self._last_regime_check[symbol] = regime_info.get("recommended_strategy")

        if should_switch and isinstance(self._effective_mode, dict):
            self._effective_mode[symbol] = new_strategy
            self.log.info(f"[REGIME] {symbol} switched to: {new_strategy}")

    def _process_ema_breakout(self, symbol: str, df, last_close_time):
        sig = compute_signals(df)

        trend_ok_long = sig["trend"] == "BULL"
        trend_ok_short = sig["trend"] == "BEAR"

        adx_ok = sig["adx"] >= CFG.DEFAULT_ADX_MIN
        rising_ok = (not CFG.REQUIRE_ADX_RISING or sig["adx_increasing"])

        breakout_long = sig["breakout_long"]
        breakout_short = sig["breakout_short"]

        self.log.info(
            f"{symbol} | strategy=ema_breakout | "
            f"trend={sig['trend']} | "
            f"breakL={breakout_long} | "
            f"breakS={breakout_short} | "
            f"adx={sig['adx']:.2f} | "
            f"adx_ok={adx_ok} | "
            f"rising_ok={rising_ok} | "
            f"vol_ratio={sig['vol_ratio']:.2f} | "
            f"vol_up={sig.get('vol_increasing', False)}"
        )

        if trend_ok_long and breakout_long and adx_ok and rising_ok:
            self.bus.publish(
                SignalEvent(symbol, "LONG", sig, last_close_time)
            )
            self.log.info(
                f"{symbol} ENTRY_DEBUG | "
                f"ph={sig['last_ph']:.2f} pl={sig['last_pl']:.2f} | "
                f"close={sig['close']:.2f} | "
                f"atr={sig['atr']:.4f} ({(sig['atr']/sig['close']*100):.2f}%)"
            )
            self.log.info(f"{symbol} → LONG signal published (ema_breakout)")

        elif trend_ok_short and breakout_short and adx_ok and rising_ok:
            self.bus.publish(
                SignalEvent(symbol, "SHORT", sig, last_close_time)
            )
            self.log.info(
                f"{symbol} ENTRY_DEBUG | "
                f"ph={sig['last_ph']:.2f} pl={sig['last_pl']:.2f} | "
                f"close={sig['close']:.2f} | "
                f"atr={sig['atr']:.4f} ({(sig['atr']/sig['close']*100):.2f}%)"
            )
            self.log.info(f"{symbol} → SHORT signal published (ema_breakout)")

    def _process_stop_hunt(self, symbol: str, df, last_close_time):
        sig = compute_stop_hunt_signals(df)

        breakout_long = sig["breakout_long"]
        breakout_short = sig["breakout_short"]

        zones_long = sig.get("stop_hunt_zones", {}).get("long", [])
        zones_short = sig.get("stop_hunt_zones", {}).get("short", [])

        self.log.info(
            f"{symbol} | strategy=stop_hunt | "
            f"trend={sig['trend']} | "
            f"breakL={breakout_long} | "
            f"breakS={breakout_short} | "
            f"vol_ratio={sig['vol_ratio']:.2f} | "
            f"zones_long={len(zones_long)} | "
            f"zones_short={len(zones_short)} | "
            f"hunt_detected={sig.get('hunt_detected', False)}"
        )

        if breakout_long:
            self.bus.publish(
                SignalEvent(symbol, "LONG", sig, last_close_time)
            )
            self.log.info(
                f"{symbol} ENTRY_DEBUG | "
                f"zone={sig['signal_price']:.2f} | "
                f"close={sig['close']:.2f} | "
                f"atr={sig['atr']:.4f} ({(sig['atr']/sig['close']*100):.2f}%) | "
                f"hunt_info={sig.get('hunt_info', {})}"
            )
            self.log.info(f"{symbol} → LONG signal published (stop_hunt)")

        elif breakout_short:
            self.bus.publish(
                SignalEvent(symbol, "SHORT", sig, last_close_time)
            )
            self.log.info(
                f"{symbol} ENTRY_DEBUG | "
                f"zone={sig['signal_price']:.2f} | "
                f"close={sig['close']:.2f} | "
                f"atr={sig['atr']:.4f} ({(sig['atr']/sig['close']*100):.2f}%) | "
                f"hunt_info={sig.get('hunt_info', {})}"
            )
            self.log.info(f"{symbol} → SHORT signal published (stop_hunt)")

    def _process_vwap_refresh(self, symbol: str, df, last_close_time):
        sig = compute_vwap_refresh_signals(df)

        refresh_long = sig["refresh_long"]
        refresh_short = sig["refresh_short"]

        self.log.info(
            f"{symbol} | strategy=vwap_refresh | "
            f"trend={sig['trend']} | "
            f"refreshL={refresh_long} | "
            f"refreshS={refresh_short} | "
            f"vwap={sig['vwap']:.2f} | "
            f"vol_ratio={sig['vol_ratio']:.2f} | "
            f"range_bound={sig.get('range_bound', False)}"
        )

        if refresh_long:
            self.bus.publish(
                SignalEvent(symbol, "LONG", sig, last_close_time)
            )
            self.log.info(
                f"{symbol} ENTRY_DEBUG | "
                f"vwap={sig['vwap']:.2f} | "
                f"close={sig['close']:.2f} | "
                f"vwap_lower={sig.get('vwap_lower', 0):.2f}"
            )
            self.log.info(f"{symbol} → LONG signal published (vwap_refresh)")

        elif refresh_short:
            self.bus.publish(
                SignalEvent(symbol, "SHORT", sig, last_close_time)
            )
            self.log.info(
                f"{symbol} ENTRY_DEBUG | "
                f"vwap={sig['vwap']:.2f} | "
                f"close={sig['close']:.2f} | "
                f"vwap_upper={sig.get('vwap_upper', 0):.2f}"
            )
            self.log.info(f"{symbol} → SHORT signal published (vwap_refresh)")

    def _process_rsi_bb_reversion(self, symbol: str, df, last_close_time):
        sig = compute_rsi_bb_signals(df)

        signal_long = sig["breakout_long"]
        signal_short = sig["breakout_short"]

        self.log.info(
            f"{symbol} | strategy=rsi_bb_reversion | "
            f"trend={sig['trend']} | "
            f"sigL={signal_long} | "
            f"sigS={signal_short} | "
            f"rsi={sig['rsi_val']:.1f} | "
            f"bb_pos={sig['bb_position']:.2f} | "
            f"div={sig.get('divergence_type', 'none')} | "
            f"stoch_k={sig.get('stoch_k', 0):.1f} | "
            f"vol_ratio={sig['vol_ratio']:.2f}"
        )

        if signal_long:
            self.bus.publish(
                SignalEvent(symbol, "LONG", sig, last_close_time)
            )
            self.log.info(
                f"{symbol} ENTRY_DEBUG | "
                f"rsi={sig['rsi_val']:.1f} | "
                f"bb_lower={sig['bb_lower']:.2f} | "
                f"close={sig['close']:.2f} | "
                f"div={sig.get('divergence_type', 'none')} | "
                f"atr={sig['atr']:.4f} ({sig['atr_pct']:.2f}%)"
            )
            self.log.info(f"{symbol} → LONG signal published (rsi_bb_reversion)")

        elif signal_short:
            self.bus.publish(
                SignalEvent(symbol, "SHORT", sig, last_close_time)
            )
            self.log.info(
                f"{symbol} ENTRY_DEBUG | "
                f"rsi={sig['rsi_val']:.1f} | "
                f"bb_upper={sig['bb_upper']:.2f} | "
                f"close={sig['close']:.2f} | "
                f"div={sig.get('divergence_type', 'none')} | "
                f"atr={sig['atr']:.4f} ({sig['atr_pct']:.2f}%)"
            )
            self.log.info(f"{symbol} → SHORT signal published (rsi_bb_reversion)")
