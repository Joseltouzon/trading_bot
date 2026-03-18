# strategy/vwap_refresh.py

import pandas as pd
import numpy as np
import config as CFG
from strategy.indicators import ema, atr, adx


def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cumulative_tp_vol = (typical_price * df["volume"]).cumsum()
    cumulative_vol = df["volume"].cumsum()
    vwap = cumulative_tp_vol / cumulative_vol
    return vwap


def calculate_vwap_bands(df: pd.DataFrame, multiplier: float = 1.5) -> dict:
    vwap = calculate_vwap(df)
    atr_val = atr(df, CFG.ATR_PERIOD)
    std_dev = df["close"].rolling(20).std()

    return {
        "vwap": vwap,
        "upper_band": vwap + (std_dev * multiplier),
        "lower_band": vwap - (std_dev * multiplier),
        "atr": atr_val,
    }


def is_range_bound(df: pd.DataFrame, lookback: int = 20) -> tuple:
    if len(df) < lookback:
        return False, 0.0

    recent = df.iloc[-lookback:]
    high_low_range = (recent["high"].max() - recent["low"].min()) / recent["low"].min() * 100

    ema_fast = ema(df["close"], CFG.EMA_FAST)
    ema_slow = ema(df["close"], CFG.EMA_SLOW)

    ema_slope_fast = (ema_fast.iloc[-1] - ema_fast.iloc[-10]) / ema_fast.iloc[-10] * 100 if len(ema_fast) >= 10 else 0
    ema_slope_slow = (ema_slow.iloc[-1] - ema_slow.iloc[-10]) / ema_slow.iloc[-10] * 100 if len(ema_slow) >= 10 else 0

    range_bound = high_low_range < 5.0 and abs(ema_slope_fast) < 0.3 and abs(ema_slope_slow) < 0.3

    return range_bound, high_low_range


def detect_vwap_refresh(df: pd.DataFrame, direction: str) -> tuple:
    bands = calculate_vwap_bands(df)

    vwap = bands["vwap"].iloc[-1]
    upper_band = bands["upper_band"].iloc[-1]
    lower_band = bands["lower_band"].iloc[-1]
    atr_val = bands["atr"].iloc[-1]

    last = df.iloc[-1]
    current_price = float(last["close"])
    current_low = float(last["low"])
    current_high = float(last["high"])
    current_close = float(last["close"])

    vol_ma = df["volume"].iloc[-20:].mean()
    vol_ratio = float(last["volume"]) / vol_ma if vol_ma > 0 else 1.0
    volume_ok = vol_ratio >= CFG.VWAP_MIN_VOLUME_RATIO

    price_deviation = ((current_price - vwap) / vwap) * 100

    ema_fast = ema(df["close"], CFG.EMA_FAST)
    ema_slow = ema(df["close"], CFG.EMA_SLOW)
    ema_above = float(ema_fast.iloc[-1]) > float(ema_slow.iloc[-1])
    ema_trend = "BULL" if ema_above else "BEAR"

    refresh_long = False
    refresh_short = False

    if direction == "LONG":
        below_vwap = current_price < vwap
        extended_below = current_low < lower_band

        if below_vwap and extended_below:
            rejection = current_close > vwap
            price_returning = current_close > current_low + (atr_val * 0.3)

            if rejection and price_returning and volume_ok:
                refresh_long = True

    elif direction == "SHORT":
        above_vwap = current_price > vwap
        extended_above = current_high > upper_band

        if above_vwap and extended_above:
            rejection = current_close < vwap
            price_returning = current_close < current_high - (atr_val * 0.3)

            if rejection and price_returning and volume_ok:
                refresh_short = True

    return (refresh_long or refresh_short), {
        "vwap": vwap,
        "upper_band": upper_band,
        "lower_band": lower_band,
        "atr": float(atr_val),
        "price_deviation": price_deviation,
        "vol_ratio": vol_ratio,
        "ema_trend": ema_trend,
    }


def compute_vwap_refresh_signals(df: pd.DataFrame) -> dict:
    if df is None or len(df) < 30:
        return {
            "strategy": "vwap_refresh",
            "trend": "NONE",
            "refresh_long": False,
            "refresh_short": False,
            "adx": 0.0,
            "adx_increasing": False,
            "atr": 0.0,
            "vol_ratio": 0.0,
            "close": 0.0,
            "signal_price": 0.0,
            "vwap": 0.0,
            "range_bound": False,
        }

    close = df["close"]
    last = df.iloc[-1]
    prev = df.iloc[-2]
    current_price = float(last["close"])

    df["atr"] = atr(df, CFG.ATR_PERIOD)
    df["adx_val"] = adx(df, CFG.ADX_PERIOD)

    atr_val = float(last["atr"])
    atr_pct = (atr_val / current_price) * 100 if current_price > 0 else 0

    adx_val = float(last["adx_val"])
    adx_prev = float(prev["adx_val"]) if "adx_val" in prev else adx_val
    adx_increasing = adx_val > adx_prev

    ema_fast = ema(close, CFG.EMA_FAST)
    ema_slow = ema(close, CFG.EMA_SLOW)
    ema_above = float(ema_fast.iloc[-1]) > float(ema_slow.iloc[-1])
    ema_trend = "BULL" if ema_above else "BEAR"

    bands = calculate_vwap_bands(df)
    vwap = float(bands["vwap"].iloc[-1])
    upper_band = float(bands["upper_band"].iloc[-1])
    lower_band = float(bands["lower_band"].iloc[-1])

    range_bound, range_pct = is_range_bound(df)

    vol_ma = df["volume"].iloc[-20:].mean()
    vol_ratio = float(last["volume"]) / vol_ma if vol_ma > 0 else 1.0

    refresh_long, refresh_info_long = detect_vwap_refresh(df, "LONG")
    refresh_short, refresh_info_short = detect_vwap_refresh(df, "SHORT")

    trend = "NONE"
    if refresh_long:
        trend = "BULL"
    elif refresh_short:
        trend = "BEAR"
    else:
        trend = ema_trend

    signal_price = 0.0
    if refresh_long:
        signal_price = vwap
    elif refresh_short:
        signal_price = vwap

    return {
        "strategy": "vwap_refresh",
        "trend": trend,
        "ema_trend": ema_trend,
        "refresh_long": refresh_long,
        "refresh_short": refresh_short,
        "adx": adx_val,
        "adx_increasing": adx_increasing,
        "atr": atr_val,
        "atr_pct": atr_pct,
        "vol_ratio": vol_ratio,
        "vol_increasing": float(last["volume"]) > float(prev["volume"]),
        "close": current_price,
        "signal_price": signal_price,
        "vwap": vwap,
        "vwap_upper": upper_band,
        "vwap_lower": lower_band,
        "range_bound": range_bound,
        "range_pct": range_pct,
        "vwap_info": {
            "vwap": float(vwap),
            "upper_band": upper_band,
            "lower_band": lower_band,
            "vol_ratio": vol_ratio,
            "ema_trend": ema_trend,
            "adx": adx_val,
            "adx_increasing": adx_increasing,
        },
    }


def build_vwap_refresh_sl(df: pd.DataFrame, direction: str, entry_price: float) -> float:
    atr_val = float(atr(df, CFG.ATR_PERIOD).iloc[-1])
    bands = calculate_vwap_bands(df)

    if direction == "LONG":
        sl_price = entry_price - (atr_val * CFG.VWAP_SL_ATR_MULT)
        band_stop = float(bands["lower_band"].iloc[-1])
        if band_stop < sl_price:
            sl_price = band_stop - (atr_val * 0.5)
        return sl_price
    else:
        sl_price = entry_price + (atr_val * CFG.VWAP_SL_ATR_MULT)
        band_stop = float(bands["upper_band"].iloc[-1])
        if band_stop > sl_price:
            sl_price = band_stop + (atr_val * 0.5)
        return sl_price
