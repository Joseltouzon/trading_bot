# strategy/signal_engine.py
import config as CFG
from core.models import SignalEvent
from strategy.ema_adx_breakout import compute_signals
from strategy.stop_hunt import compute_stop_hunt_signals
from strategy.vwap_refresh import compute_vwap_refresh_signals
from strategy.market_regime import should_switch_strategy, get_regime_confidence


class SignalEngine:

    def __init__(self, market_cache, signal_bus, log, strategy_mode: str = "ema_breakout"): 
        self.market = market_cache
        self.bus = signal_bus
        self.log = log
        self.strategy_mode = strategy_mode
        self._last_processed = {}
        self._regime_check_counter = 0
        self._regime_check_interval = 5

    def set_strategy_mode(self, mode: str):
        if mode in ["ema_breakout", "stop_hunt", "vwap_refresh", "auto"]:
            old_mode = self.strategy_mode
            self.strategy_mode = mode
            if old_mode != mode:
                self.log.info(f"[SIGNAL] Strategy mode changed to: {mode}")
        else:
            self.log.warning(f"[SIGNAL] Unknown strategy mode: {mode}, keeping {self.strategy_mode}")

    def _evaluate_regime_and_switch(self, symbol: str, df):
        self._regime_check_counter += 1

        if self._regime_check_counter < self._regime_check_interval:
            return

        self._regime_check_counter = 0

        if self.strategy_mode != "auto":
            return

        new_strategy, should_switch, regime_info = should_switch_strategy(
            df, self.strategy_mode, threshold_confidence=0.75
        )

        self.log.info(
            f"[REGIME] {symbol} | detected={regime_info.get('recommended_strategy', 'unknown')} | "
            f"confidence={regime_info.get('confidence', 0):.2f} | "
            f"adx={regime_info.get('adx', 0):.1f} | "
            f"range_bound={regime_info.get('range_bound', False)}"
        )

        if should_switch and new_strategy != self.strategy_mode:
            self.set_strategy_mode(new_strategy)
            self.log.info(f"[REGIME] Switched to strategy: {new_strategy}")

    def process_symbol(self, symbol: str):

        df = self.market.get_df_copy(symbol)
        if df is None or len(df) < 50:
            return

        last_close_time = int(df["close_time"].iloc[-2])

        if self._last_processed.get(symbol) == last_close_time:
            return

        self._last_processed[symbol] = last_close_time

        if self.strategy_mode == "auto":
            self._evaluate_regime_and_switch(symbol, df)

        if self.strategy_mode in ["stop_hunt", "auto"]:
            effective_mode = "stop_hunt" if self.strategy_mode != "auto" else self._get_effective_mode()
            if effective_mode == "stop_hunt":
                self._process_stop_hunt(symbol, df, last_close_time)
                return

        if self.strategy_mode in ["vwap_refresh", "auto"]:
            effective_mode = "vwap_refresh" if self.strategy_mode == "vwap_refresh" else self._get_effective_mode()
            if effective_mode == "vwap_refresh":
                self._process_vwap_refresh(symbol, df, last_close_time)
                return

        if self.strategy_mode in ["ema_breakout", "auto"]:
            self._process_ema_breakout(symbol, df, last_close_time)

    def _get_effective_mode(self) -> str:
        df = None
        for symbol in self.market._data.keys():
            df = self.market.get_df_copy(symbol)
            if df is not None and len(df) >= 50:
                break

        if df is None:
            return self.strategy_mode if self.strategy_mode != "auto" else "ema_breakout"

        _, should_switch, regime_info = should_switch_strategy(df, "ema_breakout", threshold_confidence=0.0)
        return regime_info.get("recommended_strategy", "ema_breakout")

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
