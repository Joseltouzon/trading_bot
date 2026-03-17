# strategy/signal_engine.py
import config as CFG
from core.models import SignalEvent
from strategy.ema_adx_breakout import compute_signals
from strategy.stop_hunt import compute_stop_hunt_signals


class SignalEngine:

    def __init__(self, market_cache, signal_bus, log, strategy_mode: str = "ema_breakout"): 
        self.market = market_cache
        self.bus = signal_bus
        self.log = log
        self.strategy_mode = strategy_mode
        self._last_processed = {}

    def set_strategy_mode(self, mode: str):
        if mode in ["ema_breakout", "stop_hunt"]:
            self.strategy_mode = mode
            self.log.info(f"[SIGNAL] Strategy mode changed to: {mode}")
        else:
            self.log.warning(f"[SIGNAL] Unknown strategy mode: {mode}, keeping {self.strategy_mode}")

    def process_symbol(self, symbol: str):

        df = self.market.get_df_copy(symbol)
        if df is None or len(df) < 50:
            return

        last_close_time = int(df["close_time"].iloc[-2])

        if self._last_processed.get(symbol) == last_close_time:
            return

        self._last_processed[symbol] = last_close_time

        if self.strategy_mode == "stop_hunt":
            self._process_stop_hunt(symbol, df, last_close_time)
        else:
            self._process_ema_breakout(symbol, df, last_close_time)

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
