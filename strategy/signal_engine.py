# strategy/signal_engine.py
import config as CFG
from core.models import SignalEvent
from strategy.ema_adx_breakout import compute_signals


class SignalEngine:

    def __init__(self, market_cache, signal_bus, log): 
        self.market = market_cache
        self.bus = signal_bus
        self.log = log
        self._last_processed = {}

    def process_symbol(self, symbol: str):

        df = self.market.get_df_copy(symbol)
        if df is None or len(df) < 50:
            return

        last_close_time = int(df["close_time"].iloc[-2])

        if self._last_processed.get(symbol) == last_close_time:
            return

        self._last_processed[symbol] = last_close_time

        sig = compute_signals(df)

        # ===== Evaluaciones individuales =====
        trend_ok_long = sig["trend"] == "BULL"
        trend_ok_short = sig["trend"] == "BEAR"

        adx_ok = sig["adx"] >= CFG.DEFAULT_ADX_MIN
        rising_ok = (not CFG.REQUIRE_ADX_RISING or sig["adx_increasing"])

        breakout_long = sig["breakout_long"]
        breakout_short = sig["breakout_short"]

        # ===== Log estructurado =====
        self.log.info(
            f"{symbol} | "
            f"trend={sig['trend']} | "
            f"breakL={breakout_long} | "
            f"breakS={breakout_short} | "
            f"adx={sig['adx']:.2f} | "
            f"adx_ok={adx_ok} | "
            f"rising_ok={rising_ok} | "
            f"vol_ratio={sig['vol_ratio']:.2f} | "
            f"vol_up={sig.get('vol_increasing', False)}"
        )

        # ===== LONG =====
        if (
            trend_ok_long
            and breakout_long
            and adx_ok
            and rising_ok
        ):
            self.bus.publish(
                SignalEvent(symbol, "LONG", sig, last_close_time)
            )
            self.log.info(
                f"{symbol} ENTRY_DEBUG | "
                f"ph={sig['last_ph']:.2f} pl={sig['last_pl']:.2f} | "
                f"close={sig['close']:.2f} | "
                f"atr={sig['atr']:.4f} ({(sig['atr']/sig['close']*100):.2f}%)"
            )
            self.log.info(f"{symbol} → LONG signal published")

        # ===== SHORT =====
        elif (
            trend_ok_short
            and breakout_short
            and adx_ok
            and rising_ok
        ):
            self.bus.publish(
                SignalEvent(symbol, "SHORT", sig, last_close_time)
            )
            self.log.info(
                f"{symbol} ENTRY_DEBUG | "
                f"ph={sig['last_ph']:.2f} pl={sig['last_pl']:.2f} | "
                f"close={sig['close']:.2f} | "
                f"atr={sig['atr']:.4f} ({(sig['atr']/sig['close']*100):.2f}%)"
            )
            self.log.info(f"{symbol} → SHORT signal published")
