# strategy/ema_adx_breakout.py
# EMA Breakout v2 - Breakout clásico + SL ajustado + RSI filter

import pandas as pd
import config as CFG
from db import Database
from core.logging_setup import setup_logging
from strategy.indicators import ema, adx, atr, rsi
from strategy.pivots import last_pivot_levels

db = Database()
log = setup_logging(db)


def compute_signals(df: pd.DataFrame) -> dict:

    if df is None or len(df) < 55:
        return {
            "strategy": "ema_breakout",
            "trend": "NONE",
            "breakout_long": False,
            "breakout_short": False,
            "adx": 0.0,
            "adx_increasing": False,
            "atr": 0.0,
            "vol_ratio": 0.0,
            "vol_increasing": False,
            "close": 0.0,
            "last_ph": None,
            "last_pl": None,
            "pivot_fresh": False,
            "signal_type": "none",
        }

    df_closed = df.iloc[:-1].copy()
    if len(df_closed) < 30:
        df_closed = df.copy()

    close = df_closed["close"]
    volume = df_closed["volume"]

    df_closed["ema_fast"] = ema(close, getattr(CFG, "EMA_BREAKOUT_FAST", CFG.EMA_FAST))
    df_closed["ema_slow"] = ema(close, getattr(CFG, "EMA_BREAKOUT_SLOW", CFG.EMA_SLOW))
    df_closed["adx_val"] = adx(df_closed, CFG.ADX_PERIOD)
    df_closed["atr_val"] = atr(df_closed, CFG.ATR_PERIOD)
    df_closed["rsi_val"] = rsi(close, CFG.EMA_RSI_PERIOD)
    df_closed["volume_ma"] = volume.rolling(20).mean()

    last = df_closed.iloc[-1]
    prev = df_closed.iloc[-2]

    current_price = float(last["close"])

    # ============================
    # 1. TREND DETECTION
    # ============================

    ema_fast_val = float(last["ema_fast"])
    ema_slow_val = float(last["ema_slow"])
    ema_diff = ema_fast_val - ema_slow_val

    # Slope de EMA fast (últimas 5 velas)
    ema_fast_prev = float(df_closed["ema_fast"].iloc[-6])
    slope_pct = ((ema_fast_val - ema_fast_prev) / ema_fast_val) * 100 if ema_fast_val > 0 else 0
    min_slope = getattr(CFG, "EMA_MIN_SLOPE_PCT", 0.03)

    trend = "NONE"
    if ema_diff > 0 and slope_pct > min_slope:
        trend = "BULL"
    elif ema_diff < 0 and slope_pct < -min_slope:
        trend = "BEAR"

    # ============================
    # 2. PIVOT LEVELS + FRESCURA
    # ============================

    last_ph, last_pl = last_pivot_levels(df_closed, CFG.PIVOT_LEN)

    pivot_fresh_long = False
    pivot_fresh_short = False
    max_pivot_age = getattr(CFG, "MAX_PIVOT_AGE", 15)

    if last_ph is not None:
        ph_mask = df_closed["high"] == last_ph
        if ph_mask.any():
            last_ph_idx = ph_mask[ph_mask].index[-1]
            candles_since_ph = len(df_closed) - df_closed.index.get_loc(last_ph_idx) - 1
            pivot_fresh_long = candles_since_ph <= max_pivot_age

    if last_pl is not None:
        pl_mask = df_closed["low"] == last_pl
        if pl_mask.any():
            last_pl_idx = pl_mask[pl_mask].index[-1]
            candles_since_pl = len(df_closed) - df_closed.index.get_loc(last_pl_idx) - 1
            pivot_fresh_short = candles_since_pl <= max_pivot_age

    # ============================
    # 3. RSI FILTER
    # ============================

    rsi_val = float(last["rsi_val"])
    rsi_oversold = getattr(CFG, "EMA_RSI_OVERSOLD", 35)
    rsi_overbought = getattr(CFG, "EMA_RSI_OVERBOUGHT", 65)

    rsi_ok_long = rsi_val < rsi_overbought
    rsi_ok_short = rsi_val > rsi_oversold

    # ============================
    # 4. VOLUME
    # ============================

    vol_ma = float(last["volume_ma"]) if float(last["volume_ma"]) > 0 else float(volume.mean())
    vol_ratio = float(last["volume"]) / vol_ma if vol_ma > 0 else 1.0
    vol_increasing = float(last["volume"]) > float(prev["volume"])

    min_vol = getattr(CFG, "EMA_MIN_VOLUME_RATIO", 1.2)
    volume_confirmed = vol_ratio >= min_vol and vol_increasing

    # ============================
    # 5. ATR / VOLATILITY
    # ============================

    atr_val = float(last["atr_val"])
    atr_pct = (atr_val / current_price) * 100 if current_price > 0 else 0
    min_atr = getattr(CFG, "EMA_MIN_ATR_PCT", 0.15)
    volatility_ok = atr_pct >= min_atr

    # ============================
    # 6. MOMENTUM
    # ============================

    momentum_bars = getattr(CFG, "EMA_MOMENTUM_BARS", 3)
    min_momentum = getattr(CFG, "EMA_MIN_MOMENTUM_PCT", 0.15)

    if len(close) >= momentum_bars + 1:
        momentum_pct = ((close.iloc[-1] - close.iloc[-(momentum_bars + 1)]) /
                        close.iloc[-(momentum_bars + 1)]) * 100
    else:
        momentum_pct = 0.0

    candle_body_pct = abs(last["close"] - last["open"]) / (last["high"] - last["low"]) if (last["high"] > last["low"]) else 0
    candle_momentum_strong = (
        (trend == "BULL" and candle_body_pct >= 0.5 and last["close"] > last["open"]) or
        (trend == "BEAR" and candle_body_pct >= 0.5 and last["close"] < last["open"])
    )

    momentum_ok = False
    if trend == "BULL":
        momentum_ok = (momentum_pct >= min_momentum) or candle_momentum_strong
    elif trend == "BEAR":
        momentum_ok = (momentum_pct <= -min_momentum) or candle_momentum_strong

    # ============================
    # 7. ADX
    # ============================

    adx_val = float(last["adx_val"])
    adx_prev = float(prev["adx_val"])
    adx_increasing = adx_val > adx_prev
    adx_min = getattr(CFG, "ADX_MIN", 20.0)
    adx_ok = adx_val >= adx_min

    # ============================
    # 8. BREAKOUT DETECTION
    # ============================

    body_size = abs(last["close"] - last["open"])
    range_size = last["high"] - last["low"]
    body_ratio = body_size / range_size if range_size > 0 else 0
    min_body_ratio = getattr(CFG, "MIN_BODY_RATIO", 0.45)
    strong_body = body_ratio >= min_body_ratio

    breakout_long = False
    breakout_short = False
    signal_type = "none"

    if volatility_ok and volume_confirmed and momentum_ok and adx_ok:
        min_break_pct = getattr(CFG, "MIN_BREAK_DISTANCE_PCT", 0.05)

        # LONG BREAKOUT
        if trend == "BULL" and last_ph is not None and rsi_ok_long:
            break_distance_pct = ((last["close"] - last_ph) / last_ph) * 100 if last_ph > 0 else 0
            min_pivot_distance = getattr(CFG, "MIN_PIVOT_DISTANCE_PCT", 0.10)

            breakout_long = (
                prev["high"] <= last_ph and
                last["high"] > last_ph and
                last["close"] > last["open"] and
                break_distance_pct >= min_pivot_distance and
                break_distance_pct >= min_break_pct and
                strong_body and
                pivot_fresh_long
            )
            if breakout_long:
                signal_type = "breakout"

        # SHORT BREAKOUT
        if trend == "BEAR" and last_pl is not None and rsi_ok_short:
            break_distance_pct = ((last_pl - last["close"]) / last_pl) * 100 if last_pl > 0 else 0
            min_pivot_distance = getattr(CFG, "MIN_PIVOT_DISTANCE_PCT", 0.10)

            breakout_short = (
                prev["low"] >= last_pl and
                last["low"] < last_pl and
                last["close"] < last["open"] and
                break_distance_pct >= min_pivot_distance and
                break_distance_pct >= min_break_pct and
                strong_body and
                pivot_fresh_short
            )
            if breakout_short:
                signal_type = "breakout"

    # ============================
    # ML FEATURES
    # ============================

    ml_features = {
        "adx": adx_val,
        "adx_increasing": adx_increasing,
        "atr": atr_val,
        "atr_pct": atr_pct,
        "vol_ratio": vol_ratio,
        "vol_increasing": vol_increasing,
        "momentum_pct": momentum_pct,
        "body_ratio": body_ratio,
        "rsi": rsi_val,
        "trend": trend,
        "signal_type": signal_type,
        "signal_long": breakout_long,
        "signal_short": breakout_short,
    }

    return {
        "strategy": "ema_breakout",
        "trend": trend,
        "last_ph": float(last_ph) if last_ph is not None else None,
        "last_pl": float(last_pl) if last_pl is not None else None,
        "breakout_long": bool(breakout_long),
        "breakout_short": bool(breakout_short),
        "adx": adx_val,
        "adx_increasing": bool(adx_increasing),
        "atr": atr_val,
        "vol_ratio": float(vol_ratio),
        "vol_increasing": bool(vol_increasing),
        "close": current_price,
        "signal_price": current_price,
        "signal_type": signal_type,
        "rsi_val": rsi_val,
        "ml_features": ml_features,
    }


def build_initial_sl(direction: str, df: pd.DataFrame, atr_val: float):
    """SL ajustado basado en entry price.

    LONG: entry - ATR * multiplier
    SHORT: entry + ATR * multiplier
    """
    entry_price = float(df["close"].iloc[-1])
    atr_mult = getattr(CFG, "EMA_SL_ATR_MULT", 1.5)

    if direction == "LONG":
        sl_price = entry_price - (atr_val * atr_mult)
        sl_pct = getattr(CFG, "EMA_SL_PCT", 0.30)
        sl_from_pct = entry_price * (1 - sl_pct / 100)
        return max(sl_price, sl_from_pct)
    else:
        sl_price = entry_price + (atr_val * atr_mult)
        sl_pct = getattr(CFG, "EMA_SL_PCT", 0.30)
        sl_from_pct = entry_price * (1 + sl_pct / 100)
        return min(sl_price, sl_from_pct)
