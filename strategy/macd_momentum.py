# strategy/macd_momentum.py
# MACD Momentum + Volume Spike — Captura tendencias fuertes que RSI+BB ignora

import pandas as pd
import config as CFG
from strategy.indicators import ema, adx, atr, rsi, macd


def compute_macd_momentum_signals(df: pd.DataFrame) -> dict:
    if df is None or len(df) < 60:
        return {
            "strategy": "macd_momentum",
            "trend": "NONE",
            "breakout_long": False,
            "breakout_short": False,
            "adx": 0.0,
            "atr": 0.0,
            "vol_ratio": 0.0,
            "close": 0.0,
            "signal_type": "none",
        }

    close = df["close"]
    current_price = float(close.iloc[-1])

    df_calc = df.copy()
    df_calc["atr_val"] = atr(df_calc, CFG.ATR_PERIOD)
    df_calc["adx_val"] = adx(df_calc, CFG.ADX_PERIOD)
    df_calc["ema_fast"] = ema(close, CFG.EMA_FAST)
    df_calc["ema_slow"] = ema(close, CFG.EMA_SLOW)
    df_calc["volume_ma"] = df["volume"].rolling(20).mean()

    last = df_calc.iloc[-1]
    prev = df_calc.iloc[-2]

    # ============================
    # 1. MACD
    # ============================
    macd_fast = getattr(CFG, "MACD_FAST", 12)
    macd_slow = getattr(CFG, "MACD_SLOW", 26)
    macd_signal = getattr(CFG, "MACD_SIGNAL", 9)
    macd_data = macd(close, macd_fast, macd_slow, macd_signal)

    hist_now = float(macd_data["histogram"].iloc[-1])
    hist_prev = float(macd_data["histogram"].iloc[-2])
    hist_prev2 = float(macd_data["histogram"].iloc[-3])
    macd_now = float(macd_data["macd"].iloc[-1])
    signal_now = float(macd_data["signal"].iloc[-1])

    # Histogram creciente (momentum acelerando)
    hist_increasing = hist_now > hist_prev > hist_prev2
    hist_decreasing = hist_now < hist_prev < hist_prev2

    # Cruce MACD
    macd_cross_up = macd_now > signal_now and float(macd_data["macd"].iloc[-2]) <= float(macd_data["signal"].iloc[-2])
    macd_cross_down = macd_now < signal_now and float(macd_data["macd"].iloc[-2]) >= float(macd_data["signal"].iloc[-2])

    # ============================
    # 2. VOLUME SPIKE
    # ============================
    vol_ma = float(last["volume_ma"]) if float(last["volume_ma"]) > 0 else float(df["volume"].mean())
    vol_ratio = float(last["volume"]) / vol_ma if vol_ma > 0 else 1.0
    min_vol = getattr(CFG, "MACD_MIN_VOLUME_RATIO", 2.0)
    volume_spike = vol_ratio >= min_vol

    # ============================
    # 3. RSI DIRECTION CONFIRMATION
    # ============================
    rsi_period = getattr(CFG, "MACD_RSI_PERIOD", 14)
    rsi_val = float(rsi(close, rsi_period).iloc[-1])
    rsi_bull_min = getattr(CFG, "MACD_RSI_BULL_MIN", 55)
    rsi_bear_max = getattr(CFG, "MACD_RSI_BEAR_MAX", 45)
    rsi_ok_long = rsi_val >= rsi_bull_min
    rsi_ok_short = rsi_val <= rsi_bear_max

    # ============================
    # 4. EMA TREND ALIGNMENT
    # ============================
    ema_fast_val = float(last["ema_fast"])
    ema_slow_val = float(last["ema_slow"])
    ema_trend = "BULL" if ema_fast_val > ema_slow_val else "BEAR"

    # ============================
    # 5. ADX STRENGTH
    # ============================
    adx_val = float(last["adx_val"])
    adx_min = getattr(CFG, "MACD_ADX_MIN", 20.0)
    adx_ok = adx_val >= adx_min

    # ============================
    # 6. ATR VOLATILITY
    # ============================
    atr_val = float(last["atr_val"])
    atr_pct = (atr_val / current_price) * 100 if current_price > 0 else 0
    min_atr = getattr(CFG, "MACD_MIN_ATR_PCT", 0.15)
    volatility_ok = atr_pct >= min_atr

    # ============================
    # 7. PRICE STRUCTURE (higher high / lower low)
    # ============================
    lookback = getattr(CFG, "MACD_STRUCTURE_LOOKBACK", 10)
    recent_highs = df_calc["high"].iloc[-lookback:]
    recent_lows = df_calc["low"].iloc[-lookback:]

    # Higher high: último high es mayor al anterior
    prev_high = float(recent_highs.iloc[-2])
    making_higher_high = float(last["high"]) > prev_high

    # Lower low: último low es menor al anterior
    prev_low = float(recent_lows.iloc[-2])
    making_lower_low = float(last["low"]) < prev_low

    # ============================
    # SIGNALS
    # ============================
    signal_long = False
    signal_short = False
    signal_type = "none"

    # LONG: MACD histogram creciente + volume spike + RSI bullish + EMA bull + estructura HH
    long_ok = (
        hist_increasing and
        volume_spike and
        rsi_ok_long and
        ema_trend == "BULL" and
        adx_ok and
        volatility_ok and
        making_higher_high
    )

    # SHORT: MACD histogram decreciente + volume spike + RSI bearish + EMA bear + estructura LL
    short_ok = (
        hist_decreasing and
        volume_spike and
        rsi_ok_short and
        ema_trend == "BEAR" and
        adx_ok and
        volatility_ok and
        making_lower_low
    )

    # Bonus: MACD cruce reciente aumenta confianza
    if long_ok:
        signal_long = True
        signal_type = "macd_cross" if macd_cross_up else "macd_hist"
    elif short_ok:
        signal_short = True
        signal_type = "macd_cross" if macd_cross_down else "macd_hist"

    return {
        "strategy": "macd_momentum",
        "trend": ema_trend,
        "breakout_long": signal_long,
        "breakout_short": signal_short,
        "adx": adx_val,
        "adx_increasing": adx_val > float(prev.get("adx_val", 0)),
        "atr": atr_val,
        "atr_pct": atr_pct,
        "vol_ratio": vol_ratio,
        "vol_increasing": float(last["volume"]) > float(prev["volume"]),
        "close": current_price,
        "signal_price": current_price,
        "signal_type": signal_type,
        "rsi_val": rsi_val,
        "macd_val": macd_now,
        "macd_signal_val": signal_now,
        "macd_histogram": hist_now,
        "hist_increasing": hist_increasing,
        "volume_spike": volume_spike,
        "ml_features": {
            "macd": macd_now,
            "macd_signal": signal_now,
            "histogram": hist_now,
            "hist_prev": hist_prev,
            "hist_prev2": hist_prev2,
            "hist_increasing": hist_increasing,
            "hist_decreasing": hist_decreasing,
            "macd_cross_up": macd_cross_up,
            "macd_cross_down": macd_cross_down,
            "vol_ratio": vol_ratio,
            "volume_spike": volume_spike,
            "rsi": rsi_val,
            "rsi_ok_long": rsi_ok_long,
            "rsi_ok_short": rsi_ok_short,
            "adx": adx_val,
            "adx_ok": adx_ok,
            "atr_pct": atr_pct,
            "ema_trend": ema_trend,
            "making_higher_high": making_higher_high,
            "making_lower_low": making_lower_low,
            "signal_long": signal_long,
            "signal_short": signal_short,
            "signal_type": signal_type,
        },
    }


def build_macd_momentum_sl(df: pd.DataFrame, direction: str, entry_price: float) -> float:
    atr_series = atr(df, CFG.ATR_PERIOD)
    atr_val = float(atr_series.iloc[-1]) if len(atr_series) > 0 else 0
    atr_mult = getattr(CFG, "MACD_SL_ATR_MULT", 2.0)

    if direction == "LONG":
        sl_from_atr = entry_price - (atr_val * atr_mult)
        sl_from_pct = entry_price * (1 - 0.5 / 100)
        return max(sl_from_atr, sl_from_pct)
    else:
        sl_from_atr = entry_price + (atr_val * atr_mult)
        sl_from_pct = entry_price * (1 + 0.5 / 100)
        return min(sl_from_atr, sl_from_pct)
