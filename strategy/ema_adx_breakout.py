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
            "pivot_fresh": False,
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
    # TREND (EMA Slope)
    # ============================
    trend = "NONE"

    ema_diff = last["ema_fast"] - last["ema_slow"]
    slope = last["ema_fast"] - df_closed["ema_fast"].iloc[-3]
    slope_pct = (slope / last["close"]) * 100 if last["close"] > 0 else 0

    if abs(slope_pct) >= CFG.MIN_EMA_SLOPE_PCT:
        trend = "BULL" if ema_diff > 0 else "BEAR"

    # ============================
    # PIVOTS + FRESCURA
    # ============================
    last_ph, last_pl = last_pivot_levels(df_closed, CFG.PIVOT_LEN)

    max_pivot_age = getattr(CFG, "MAX_PIVOT_AGE", 15)

    pivot_fresh_long = False
    pivot_fresh_short = False

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
    # VOLUME (unificado)
    # ============================
    vol_ma = float(last["volume_ma"]) if float(last["volume_ma"]) > 0 else float(volume.mean())
    vol_ratio = float(last["volume"]) / vol_ma if vol_ma > 0 else 1.0

    # Volumen ok: entre min y max ratio
    vol_ok = (
        vol_ratio >= CFG.VOLUME_MIN_RATIO and
        vol_ratio <= CFG.MAX_VOLUME_RATIO
    )

    # ============================
    # ATR (volatilidad minima)
    # ============================
    atr_val = float(last["atr"])
    atr_pct = (atr_val / last["close"]) * 100 if last["close"] > 0 else 0
    volatility_ok = atr_pct >= CFG.MIN_ATR_PCT

    # ============================
    # BODY + MOMENTUM (unificado)
    # ============================
    body_size = abs(last["close"] - last["open"])
    range_size = last["high"] - last["low"]
    body_ratio = body_size / range_size if range_size > 0 else 0
    body_ok = body_ratio >= CFG.MIN_BODY_RATIO

    # Directional: vela en direccion de la tendencia
    directional_ok = False
    momentum_pct = 0.0
    momentum_ok = False
    if trend != "NONE":
        lookback = getattr(CFG, "MOMENTUM_LOOKBACK", 3) + 1
        if len(close) >= lookback:
            momentum_pct = ((close.iloc[-1] - close.iloc[-lookback]) / close.iloc[-lookback]) * 100
            if trend == "BULL":
                momentum_ok = momentum_pct >= CFG.MIN_MOMENTUM_PCT
            elif trend == "BEAR":
                momentum_ok = momentum_pct <= -CFG.MIN_MOMENTUM_PCT

    # ============================
    # BREAKOUT DISTANCE
    # ============================
    break_distance_pct_long = 0.0
    break_distance_pct_short = 0.0

    if last_ph is not None and last["close"] > 0:
        break_distance_pct_long = ((last["close"] - last_ph) / last_ph) * 100

    if last_pl is not None and last_pl > 0:
        break_distance_pct_short = ((last_pl - last["close"]) / last_pl) * 100

    # ============================
    # BREAKOUT SIGNALS
    # ============================
    breakout_long = False
    breakout_short = False

    # Solo evaluar breakout si hay volatilidad, volumen y tendencia
    if volatility_ok and vol_ok and trend != "NONE":
        min_distance_pct = getattr(CFG, "MIN_PIVOT_DISTANCE_PCT", 0.10)

        # LONG: ruptura de pivot high por mecha
        if trend == "BULL" and last_ph is not None:
            distance_ok = break_distance_pct_long >= min_distance_pct
            
            breakout_long = (
                prev["high"] <= last_ph and          # vela anterior NO rompió
                last["high"] > last_ph and           # vela actual rompe con mecha
                directional_ok and                   # vela alcista
                distance_ok and                      # distancia minima al pivot
                body_ok and                         # cuerpo fuerte
                momentum_ok and                     # momentum a favor
                pivot_fresh_long                    # pivot reciente
            )

        # SHORT: ruptura de pivot low por mecha
        if trend == "BEAR" and last_pl is not None:
            distance_ok = break_distance_pct_short >= min_distance_pct
            
            breakout_short = (
                prev["low"] >= last_pl and           # vela anterior NO rompió
                last["low"] < last_pl and            # vela actual rompe con mecha
                directional_ok and                   # vela bajista
                distance_ok and                      # distancia minima al pivot
                body_ok and                         # cuerpo fuerte
                momentum_ok and                     # momentum a favor
                pivot_fresh_short                    # pivot reciente
            )

    # ============================
    # ADX
    # ============================
    adx_val = float(last["adx"])
    adx_prev = float(prev["adx"])
    adx_increasing = adx_val > adx_prev

    # ============================
    # FEATURES PARA ML
    # ============================
    ml_features = {
        "adx": float(adx_val),
        "adx_increasing": bool(adx_increasing),
        "atr": float(atr_val),
        "atr_pct": float(atr_pct),
        "vol_ratio": float(vol_ratio),
        "vol_ok": bool(vol_ok),
        "momentum_pct": float(momentum_pct) if momentum_ok else 0.0,
        "body_ratio": float(body_ratio),
        "body_ok": bool(body_ok),
        "pivot_fresh_long": bool(pivot_fresh_long),
        "pivot_fresh_short": bool(pivot_fresh_short),
        "break_distance_pct_long": float(break_distance_pct_long),
        "break_distance_pct_short": float(break_distance_pct_short),
        "trend": str(trend),
        "directional_ok": bool(directional_ok),
        "volatility_ok": bool(volatility_ok),
    }

    # ============================
    # RETURN
    # ============================
    signal_price = 0.0
    if breakout_long:
        signal_price = float(last_ph)
    elif breakout_short:
        signal_price = float(last_pl)

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
        "vol_increasing": bool(last["volume"] > prev["volume"]),
        "close": float(last["close"]),
        "signal_price": signal_price,
        "ml_features": ml_features,
    }


def build_initial_sl(direction: str, df: pd.DataFrame, atr_val: float):
    last_ph, last_pl = last_pivot_levels(df, CFG.PIVOT_LEN)

    buffer_pct = getattr(CFG, "SL_BUFFER_PCT", 0.001)

    if direction == "LONG":
        if last_pl is None:
            return None
        sl_price = float(last_pl) - (atr_val * 1.2)
        return sl_price * (1 - buffer_pct)
    else:
        if last_ph is None:
            return None
        sl_price = float(last_ph) + (atr_val * 1.2)
        return sl_price * (1 + buffer_pct)
