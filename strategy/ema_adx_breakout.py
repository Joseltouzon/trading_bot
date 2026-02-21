# strategy/ema_adx_breakout.py

import pandas as pd
import config as CFG

from strategy.indicators import ema, adx, atr
from strategy.pivots import last_pivot_levels


def compute_signals(df: pd.DataFrame) -> dict:
    """
    IMPORTANTE:
    df (REST) normalmente incluye la vela en curso como última fila.
    Para señales, usamos SOLO velas cerradas => df_closed = df.iloc[:-1]
    """
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

    # quitar vela en formación
    df_closed = df.iloc[:-1].copy()
    if len(df_closed) < 30:
        df_closed = df.copy()  # fallback raro

    close = df_closed["close"]
    volume = df_closed["volume"]

    df_closed["ema_fast"] = ema(close, CFG.EMA_FAST)
    df_closed["ema_slow"] = ema(close, CFG.EMA_SLOW)
    df_closed["adx"] = adx(df_closed, CFG.ADX_PERIOD)
    df_closed["atr"] = atr(df_closed, CFG.ATR_PERIOD)
    df_closed["volume_ma"] = volume.rolling(20).mean()

    last = df_closed.iloc[-1]   # última CERRADA
    prev = df_closed.iloc[-2]

    # Trend
    if last["ema_fast"] > last["ema_slow"]:
        trend = "BULL"
    elif last["ema_fast"] < last["ema_slow"]:
        trend = "BEAR"
    else:
        trend = "NONE"

    # Pivots sobre velas cerradas
    last_ph, last_pl = last_pivot_levels(df_closed, CFG.PIVOT_LEN)

    # Volumen ratio correcto (vela cerrada / MA cerrada)
    vol_ma = float(last["volume_ma"]) if float(last["volume_ma"]) > 0 else float(volume.mean())
    vol_ratio = float(last["volume"]) / vol_ma if vol_ma > 0 else 1.0
    vol_increasing = float(last["volume"]) > float(prev["volume"])

    volume_confirmed = (vol_ratio >= CFG.VOLUME_MIN_RATIO) or vol_increasing

    # Breakout confirmado al cierre
    breakout_long = False
    breakout_short = False

    if last_ph is not None and volume_confirmed:
        breakout_long = (prev["close"] <= last_ph) and (last["close"] > last_ph)

    if last_pl is not None and volume_confirmed:
        breakout_short = (prev["close"] >= last_pl) and (last["close"] < last_pl)

    # ADX
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
        "atr": float(last["atr"]),
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
