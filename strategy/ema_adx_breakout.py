# strategy/ema_adx_breakout.py

import pandas as pd
import config as CFG
from db import Database
from core.logging_setup import setup_logging
from strategy.indicators import ema, adx, atr
from strategy.pivots import last_pivot_levels

db = Database()
log = setup_logging(db)


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
            "pivot_fresh": False,  # ← NUEVO
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
    min_slope_pct = getattr(CFG, "MIN_EMA_SLOPE_PCT", 0.01)

    if abs(slope_pct) < min_slope_pct:
        trend = "NONE"
    else:
        if ema_diff > 0:
            trend = "BULL"
        elif ema_diff < 0:
            trend = "BEAR"

    # ============================
    # PIVOTS + FRESCURA
    # ============================

    last_ph, last_pl = last_pivot_levels(df_closed, CFG.PIVOT_LEN)

    # Verificar si el pivot es "fresco" (formado en las últimas N velas)
    pivot_fresh_long = False
    pivot_fresh_short = False
    max_pivot_age = getattr(CFG, "MAX_PIVOT_AGE", 15)  # velas

    if last_ph is not None:
        # Buscar cuándo se formó el último pivot high
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
    # VOLUME (con techo para evitar clímax)
    # ============================

    vol_ma = float(last["volume_ma"]) if float(last["volume_ma"]) > 0 else float(volume.mean())
    vol_ratio = float(last["volume"]) / vol_ma if vol_ma > 0 else 1.0
    vol_increasing = float(last["volume"]) > float(prev["volume"])

    # Volumen máximo para evitar entrar en clímax
    max_vol_ratio = getattr(CFG, "MAX_VOLUME_RATIO", 2.5)
    volume_confirmed = (
        vol_ratio >= CFG.VOLUME_MIN_RATIO and
        vol_ratio <= max_vol_ratio and
        vol_increasing
    )

    # ============================
    # ATR FILTER
    # ============================

    atr_val = float(last["atr"])
    atr_pct = (atr_val / last["close"]) * 100 if last["close"] > 0 else 0
    min_atr_pct = getattr(CFG, "MIN_ATR_PCT", 0.20)
    volatility_ok = atr_pct >= min_atr_pct

    # ============================
    # MOMENTUM (enfocado en vela actual)
    # ============================

    momentum_lookback = getattr(CFG, "MOMENTUM_LOOKBACK", 3)
    min_momentum_pct = getattr(CFG, "MIN_MOMENTUM_PCT", 0.15)

    # Momentum de las últimas N velas (base)
    if len(close) >= momentum_lookback + 1:
        momentum_pct = ((close.iloc[-1] - close.iloc[-(momentum_lookback + 1)]) / 
                        close.iloc[-(momentum_lookback + 1)]) * 100
    else:
        momentum_pct = 0.0

    # Momentum intravela (¿la vela actual está cerrando fuerte?)
    candle_body_pct = ((last["close"] - last["open"]) / (last["high"] - last["low"])) if (last["high"] > last["low"]) else 0
    candle_momentum_strong = (
        (trend == "BULL" and candle_body_pct >= 0.6 and last["close"] > last["open"]) or
        (trend == "BEAR" and candle_body_pct >= 0.6 and last["close"] < last["open"])
    )

    # Evaluar momentum según tendencia
    momentum_ok = False
    if trend == "BULL":
        momentum_ok = (momentum_pct >= min_momentum_pct) or candle_momentum_strong
    elif trend == "BEAR":
        momentum_ok = (momentum_pct <= -min_momentum_pct) or candle_momentum_strong

    # ============================
    # BREAKOUT 
    # ============================

    body_size = abs(last["close"] - last["open"])
    range_size = last["high"] - last["low"]
    body_ratio = body_size / range_size if range_size > 0 else 0
    min_body_ratio = getattr(CFG, "MIN_BODY_RATIO", 0.55)
    strong_body = body_ratio >= min_body_ratio

    prev_range = prev["high"] - prev["low"]
    range_expansion = range_size > prev_range * 1.2

    # Pre-calcular distancias
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
        min_break_pct = getattr(CFG, "MIN_BREAK_DISTANCE_PCT", 0.08)

        # ============================
        # LONG BREAKOUT
        # ============================
        if trend == "BULL" and last_ph is not None:
            # NUEVO: Entrar por ruptura de mecha, no por cierre
            # Condiciones:
            # 1. La vela anterior NO rompió el pivot (prev["high"] <= last_ph)
            # 2. La vela ACTUAL rompió con la mecha (last["high"] > last_ph)
            # 3. La vela es alcista (last["close"] > last["open"])
            # 4. Distancia mínima al pivot (evita entradas pegadas)
            
            min_pivot_distance_pct = getattr(CFG, "MIN_PIVOT_DISTANCE_PCT", 0.15)
            distance_ok = break_distance_pct_long >= min_pivot_distance_pct
            
            breakout_long = (
                prev["high"] <= last_ph and          # ← CAMBIO: prev["high"] en vez de prev["close"]
                last["high"] > last_ph and           # ← CAMBIO: last["high"] en vez de last["close"]
                last["close"] > last["open"] and     # ← NUEVO: vela alcista
                distance_ok and
                break_distance_pct_long >= min_break_pct and
                strong_body and
                momentum_ok and
                pivot_fresh_long                      # ← NUEVO: pivot fresco
            )

        # ============================
        # SHORT BREAKOUT
        # ============================
        if trend == "BEAR" and last_pl is not None:
            min_pivot_distance_pct = getattr(CFG, "MIN_PIVOT_DISTANCE_PCT", 0.15)
            distance_ok = break_distance_pct_short >= min_pivot_distance_pct
            
            breakout_short = (
                prev["low"] >= last_pl and           # ← CAMBIO: prev["low"] en vez de prev["close"]
                last["low"] < last_pl and            # ← CAMBIO: last["low"] en vez de last["close"]
                last["close"] < last["open"] and     # ← NUEVO: vela bajista
                distance_ok and
                break_distance_pct_short >= min_break_pct and
                strong_body and
                momentum_ok and
                pivot_fresh_short                     # ← NUEVO: pivot fresco
            )

    # ============================
    # ADX
    # ============================

    adx_val = float(last["adx"])
    adx_prev = float(prev["adx"])
    adx_increasing = adx_val > adx_prev

    # ===== CAPTURAR FEATURES PARA ML =====
    ml_features = {
        "adx": float(last["adx"]),
        "adx_increasing": bool(adx_increasing),
        "atr": float(atr_val),
        "atr_pct": float((atr_val / last["close"] * 100) if last["close"] > 0 else 0),
        "vol_ratio": float(vol_ratio),
        "vol_increasing": bool(vol_increasing),
        "momentum_pct": float(momentum_pct),
        "body_ratio": float(body_ratio),
        "pivot_fresh_long": bool(pivot_fresh_long),
        "pivot_fresh_short": bool(pivot_fresh_short),
        "break_distance_pct_long": float(break_distance_pct_long),
        "break_distance_pct_short": float(break_distance_pct_short),
        "trend": str(trend),
        "candle_momentum_strong": bool(candle_momentum_strong),
        "volume_confirmed": bool(volume_confirmed),
        "volatility_ok": bool(volatility_ok),
    }

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
        "signal_price": float(last_ph) if trend == "BULL" and breakout_long else(float(last_pl) if trend == "BEAR" and breakout_short else float(last["close"])),
        "ml_features": ml_features,
    }


def build_initial_sl(direction: str, df: pd.DataFrame, atr_val: float):
    last_ph, last_pl = last_pivot_levels(df, CFG.PIVOT_LEN)

    if direction == "LONG":
        if last_pl is None:
            return None
        # Buffer extra contra stop hunts
        buffer_pct = getattr(CFG, "SL_BUFFER_PCT", 0.001)
        sl_price = float(last_pl) - (atr_val * 1.2)
        return sl_price * (1 - buffer_pct)
    else:
        if last_ph is None:
            return None
        buffer_pct = getattr(CFG, "SL_BUFFER_PCT", 0.001)
        sl_price = float(last_ph) + (atr_val * 1.2)
        return sl_price * (1 + buffer_pct)