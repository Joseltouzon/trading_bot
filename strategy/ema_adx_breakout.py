# strategy/ema_adx_breakout.py

import pandas as pd
import config as CFG
import logging
logger = logging.getLogger(__name__)

from strategy.indicators import ema, adx, atr
from strategy.pivots import last_pivot_levels


def compute_signals(df: pd.DataFrame) -> dict:

    if df is None or len(df) < 50:
        return {
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
        }

    df_closed = df.iloc[:-1].copy()
    if len(df_closed) < 30:
        df_closed = df.copy()

    close = df_closed["close"]
    volume = df_closed["volume"]

    df_closed["ema_fast"] = ema(close, CFG.EMA_FAST)
    df_closed["ema_slow"] = ema(close, CFG.EMA_SLOW)
    df_closed["adx"] = adx(df_closed, CFG.ADX_PERIOD)
    df_closed["atr"] = atr(df_closed, CFG.ATR_PERIOD)
    df_closed["volume_ma"] = volume.rolling(20).mean()

    last = df_closed.iloc[-1]
    prev = df_closed.iloc[-2]

    # ============================
    # TREND + SLOPE FILTER
    # ============================

    trend = "NONE"

    ema_diff = last["ema_fast"] - last["ema_slow"]
    slope = last["ema_fast"] - df_closed["ema_fast"].iloc[-3]

    slope_pct = (slope / last["close"]) * 100 if last["close"] > 0 else 0
    min_slope_pct = getattr(CFG, "MIN_EMA_SLOPE_PCT", 0.02)

    if abs(slope_pct) < min_slope_pct:
        trend = "NONE"
    else:
        if ema_diff > 0:
            trend = "BULL"
        elif ema_diff < 0:
            trend = "BEAR"

    # ============================
    # PIVOTS
    # ============================

    last_ph, last_pl = last_pivot_levels(df_closed, CFG.PIVOT_LEN)

    # ============================
    # VOLUME
    # ============================

    vol_ma = float(last["volume_ma"]) if float(last["volume_ma"]) > 0 else float(volume.mean())
    vol_ratio = float(last["volume"]) / vol_ma if vol_ma > 0 else 1.0
    vol_increasing = float(last["volume"]) > float(prev["volume"])

    volume_confirmed = (vol_ratio >= CFG.VOLUME_MIN_RATIO) and vol_increasing

    # ============================
    # ATR FILTER (evita mercado muerto)
    # ============================

    atr_val = float(last["atr"])
    atr_pct = (atr_val / last["close"]) * 100 if last["close"] > 0 else 0
    min_atr_pct = getattr(CFG, "MIN_ATR_PCT", 0.20)

    volatility_ok = atr_pct >= min_atr_pct

    # ============================
    # BREAKOUT
    # ============================
    # Filtro Momentum: % de cambio en las últimas N velas
    momentum_lookback = getattr(CFG, "MOMENTUM_LOOKBACK", 3)
    min_momentum_pct = getattr(CFG, "MIN_MOMENTUM_PCT", 0.25)  # 0.25% en 3 velas de 5m

    # Calcular momentum (rate of change)
    if len(close) >= momentum_lookback + 1:
        momentum_pct = ((close.iloc[-1] - close.iloc[-(momentum_lookback + 1)]) / 
                        close.iloc[-(momentum_lookback + 1)]) * 100
    else:
        momentum_pct = 0.0

    # Evaluar según dirección de tendencia
    momentum_ok = False
    if trend == "BULL":
        momentum_ok = momentum_pct >= min_momentum_pct
    elif trend == "BEAR":
        momentum_ok = momentum_pct <= -min_momentum_pct

    # filtro de cuerpo
    body_size = abs(last["close"] - last["open"])
    range_size = last["high"] - last["low"]

    body_ratio = body_size / range_size if range_size > 0 else 0
    min_body_ratio = getattr(CFG, "MIN_BODY_RATIO", 0.55)

    strong_body = body_ratio >= min_body_ratio

    # filtro de rango de expansion descomentar este antes que el que sigue
    prev_range = prev["high"] - prev["low"]
    range_expansion = range_size > prev_range * 1.2

    # filtro de compresion previa - todavia no
    lookback = 8
    recent_range = df["high"].iloc[-lookback:-1].max() - df["low"].iloc[-lookback:-1].min()
    compression = prev_range < recent_range * 0.5

    if last_ph is not None and last["close"] > 0:
        break_distance_pct_long = ((last["close"] - last_ph) / last_ph) * 100
    else:
        break_distance_pct_long = 0.0

    if last_pl is not None and last_pl > 0:
        break_distance_pct_short = ((last_pl - last["close"]) / last_pl) * 100
    else:
        break_distance_pct_short = 0.0

    breakout_long = False
    breakout_short = False

    if volatility_ok and volume_confirmed:

        min_break_pct = getattr(CFG, "MIN_BREAK_DISTANCE_PCT", 0.15)

        if trend == "BULL" and last_ph is not None:
            breakout_long = (
                prev["close"] <= last_ph and
                last["close"] > last_ph and
                break_distance_pct_long >= min_break_pct
                and strong_body
                and momentum_ok
                # and range_expansion
                # and compression
            ) 

        if trend == "BEAR" and last_pl is not None:
            breakout_short = (
                prev["close"] >= last_pl and
                last["close"] < last_pl and
                break_distance_pct_short >= min_break_pct
                and strong_body
                and momentum_ok
                # and range_expansion
                # and compression
            ) 

    # ============================
    # ADX
    # ============================

    adx_val = float(last["adx"])
    adx_prev = float(prev["adx"])
    adx_increasing = adx_val > adx_prev

    return {
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
        "close": float(last["close"]),
    }


def build_initial_sl(direction: str, df: pd.DataFrame, atr_val: float):

    last_ph, last_pl = last_pivot_levels(df, CFG.PIVOT_LEN)

    if direction == "LONG":
        if last_pl is None:
            return None
        return float(last_pl) - (atr_val * 0.8)

    else:
        if last_ph is None:
            return None
        return float(last_ph) + (atr_val * 0.8)