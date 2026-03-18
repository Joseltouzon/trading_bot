# strategy/market_regime.py

import pandas as pd
import numpy as np
import config as CFG
from strategy.indicators import ema, atr, adx


def calculate_regime_metrics(df: pd.DataFrame) -> dict:
    if df is None or len(df) < 50:
        return {
            "regime": "UNKNOWN",
            "confidence": 0.0,
            "adx": 0.0,
            "atr_pct": 0.0,
            "vol_ratio": 1.0,
            "ema_spread_pct": 0.0,
            "range_bound": False,
            "high_low_range_pct": 0.0,
        }

    close = df["close"]
    last = df.iloc[-1]
    current_price = float(last["close"])

    df["atr_val"] = atr(df, CFG.ATR_PERIOD)
    df["adx_val"] = adx(df, CFG.ADX_PERIOD)
    df["ema_fast"] = ema(close, CFG.EMA_FAST)
    df["ema_slow"] = ema(close, CFG.EMA_SLOW)

    atr_val = float(last["atr_val"])
    atr_pct = (atr_val / current_price) * 100 if current_price > 0 else 0

    adx_val = float(last["adx_val"])
    adx_prev = float(df["adx_val"].iloc[-5]) if len(df) >= 5 else adx_val
    adx_trend = adx_val > adx_prev

    ema_fast = float(last["ema_fast"])
    ema_slow = float(last["ema_slow"])
    ema_spread_pct = ((ema_fast - ema_slow) / ema_slow) * 100

    vol_ma = df["volume"].iloc[-20:].mean()
    vol_ratio = float(last["volume"]) / vol_ma if vol_ma > 0 else 1.0

    lookback = 20
    if len(df) >= lookback:
        recent = df.iloc[-lookback:]
        high_low_range = ((recent["high"].max() - recent["low"].min()) / recent["low"].min()) * 100
    else:
        high_low_range = 0.0

    ema_slope_fast = ((ema_fast - float(df["ema_fast"].iloc[-10])) / float(df["ema_fast"].iloc[-10])) * 100 if len(df) >= 10 else 0

    range_bound = high_low_range < 5.0 and abs(ema_slope_fast) < 0.3

    return {
        "adx": adx_val,
        "adx_trend": adx_trend,
        "atr_pct": atr_pct,
        "vol_ratio": vol_ratio,
        "ema_spread_pct": ema_spread_pct,
        "range_bound": range_bound,
        "high_low_range_pct": high_low_range,
        "ema_trend": "BULL" if ema_spread_pct > 0 else "BEAR",
    }


def detect_market_regime(df: pd.DataFrame) -> str:
    metrics = calculate_regime_metrics(df)

    if metrics["regime"] == "UNKNOWN":
        return "auto"

    adx = metrics["adx"]
    range_bound = metrics["range_bound"]
    vol_ratio = metrics["vol_ratio"]
    high_low_range = metrics["high_low_range_pct"]

    trending_threshold = CFG.REGIME_TRENDING_ADX_MIN
    ranging_threshold = CFG.REGIME_RANGING_ADX_MAX

    if adx >= trending_threshold and not range_bound:
        return "ema_breakout"

    if adx <= ranging_threshold and range_bound and vol_ratio >= CFG.REGIME_HUNT_VOL_RATIO_MIN:
        return "stop_hunt"

    if adx <= ranging_threshold and range_bound and vol_ratio < CFG.REGIME_HUNT_VOL_RATIO_MIN:
        return "vwap_refresh"

    if adx > ranging_threshold and adx < trending_threshold:
        return "stop_hunt"

    return "auto"


def get_regime_confidence(df: pd.DataFrame) -> dict:
    metrics = calculate_regime_metrics(df)

    adx = metrics["adx"]
    range_bound = metrics["range_bound"]
    vol_ratio = metrics["vol_ratio"]
    high_low_range = metrics["high_low_range_pct"]

    trending_threshold = CFG.REGIME_TRENDING_ADX_MIN
    ranging_threshold = CFG.REGIME_RANGING_ADX_MAX

    if adx >= trending_threshold:
        confidence = min((adx - trending_threshold) / 10 + 0.5, 0.95)
        regime = "TRENDING"
    elif adx <= ranging_threshold and range_bound:
        confidence = 0.7 + (0.3 * min(vol_ratio / 2.0, 1.0))
        regime = "RANGING"
    elif high_low_range < 3.0:
        confidence = 0.6
        regime = "LOW_VOLATILITY"
    else:
        confidence = 0.5
        regime = "TRANSITIONAL"

    return {
        "regime": regime,
        "confidence": confidence,
        "recommended_strategy": detect_market_regime(df),
        **metrics,
    }


def should_switch_strategy(df: pd.DataFrame, current_strategy: str, threshold_confidence: float = 0.75) -> tuple:
    regime_info = get_regime_confidence(df)

    recommended = regime_info["recommended_strategy"]
    confidence = regime_info["confidence"]

    if confidence < threshold_confidence:
        return current_strategy, False, regime_info

    if recommended != current_strategy and recommended != "auto":
        return recommended, True, regime_info

    return current_strategy, False, regime_info
