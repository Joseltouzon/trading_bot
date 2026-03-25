# strategy/volatility_squeeze.py
# Volatility Compression + Momentum Exhaustion (1h)
# Detecta compresiones de volatilidad y entra anticipando la expansión

import pandas as pd
import numpy as np
import config as CFG
from strategy.indicators import ema, atr, adx, rsi, bollinger_bands


# ============================================================
# CONFIGURACIÓN DEFAULT
# ============================================================
VOL_SQUEEZE_ATR_PERIOD = 14
VOL_SQUEEZE_ATR_LOOKBACK = 100
VOL_SQUEEZE_ATR_PERCENTILE = 20
VOL_SQUEEZE_BB_PERIOD = 20
VOL_SQUEEZE_BB_WIDTH_PERCENTILE = 15
VOL_SQUEEZE_RSI_PERIOD = 14
VOL_SQUEEZE_RSI_OVERSOLD = 30
VOL_SQUEEZE_RSI_OVERBOUGHT = 70
VOL_SQUEEZE_MIN_VOLUME_RATIO = 1.2
VOL_SQUEEZE_ADX_MIN = 15.0
VOL_SQUEEZE_SL_ATR_MULT = 1.5
VOL_SQUEEZE_TP_ATR_MULT = 4.0
VOL_SQUEEZE_EMA_FAST = 20
VOL_SQUEEZE_EMA_SLOW = 50


def compute_volatility_squeeze_signals(df: pd.DataFrame) -> dict:
    """
    Estrategia de compresión de volatilidad + agotamiento de momentum.
    
    Lógica:
    1. Detectar compresión: ATR en percentil bajo históricamente
    2. Confirmar squeeze: Bollinger Band Width muy comprimido
    3. Agotamiento: RSI sale de zona extrema + divergencia
    4. Entry: En dirección del último swing antes de la compresión
    
    Timeframe óptimo: 1h
    """
    
    if df is None or len(df) < 120:
        return {
            "strategy": "volatility_squeeze",
            "trend": "NONE",
            "breakout_long": False,
            "breakout_short": False,
            "squeeze_active": False,
            "compression_level": 0.0,
            "atr_percentile": 0.0,
            "bb_width_percentile": 0.0,
            "rsi": 50.0,
            "adx": 0.0,
            "atr": 0.0,
            "close": 0.0,
            "vol_ratio": 0.0,
        }

    df_closed = df.iloc[:-1].copy()
    if len(df_closed) < 120:
        df_closed = df.copy()

    close = df_closed["close"]
    volume = df_closed["volume"]
    high = df_closed["high"]
    low = df_closed["low"]

    # Parámetros
    atr_period = getattr(CFG, "VOL_SQUEEZE_ATR_PERIOD", VOL_SQUEEZE_ATR_PERIOD)
    atr_lookback = getattr(CFG, "VOL_SQUEEZE_ATR_LOOKBACK", VOL_SQUEEZE_ATR_LOOKBACK)
    atr_percentile_threshold = getattr(CFG, "VOL_SQUEEZE_ATR_PERCENTILE", VOL_SQUEEZE_ATR_PERCENTILE)
    bb_period = getattr(CFG, "VOL_SQUEEZE_BB_PERIOD", VOL_SQUEEZE_BB_PERIOD)
    bb_width_percentile = getattr(CFG, "VOL_SQUEEZE_BB_WIDTH_PERCENTILE", VOL_SQUEEZE_BB_WIDTH_PERCENTILE)
    rsi_period = getattr(CFG, "VOL_SQUEEZE_RSI_PERIOD", VOL_SQUEEZE_RSI_PERIOD)
    rsi_oversold = getattr(CFG, "VOL_SQUEEZE_RSI_OVERSOLD", VOL_SQUEEZE_RSI_OVERSOLD)
    rsi_overbought = getattr(CFG, "VOL_SQUEEZE_RSI_OVERBOUGHT", VOL_SQUEEZE_RSI_OVERBOUGHT)
    min_vol_ratio = getattr(CFG, "VOL_SQUEEZE_MIN_VOLUME_RATIO", VOL_SQUEEZE_MIN_VOLUME_RATIO)
    adx_min = getattr(CFG, "VOL_SQUEEZE_ADX_MIN", VOL_SQUEEZE_ADX_MIN)
    sl_atr_mult = getattr(CFG, "VOL_SQUEEZE_SL_ATR_MULT", VOL_SQUEEZE_SL_ATR_MULT)
    ema_fast_period = getattr(CFG, "VOL_SQUEEZE_EMA_FAST", VOL_SQUEEZE_EMA_FAST)
    ema_slow_period = getattr(CFG, "VOL_SQUEEZE_EMA_SLOW", VOL_SQUEEZE_EMA_SLOW)

    # Calcular indicadores
    df_closed["atr_val"] = atr(df_closed, atr_period)
    df_closed["rsi_val"] = rsi(close, rsi_period)
    df_closed["adx_val"] = adx(df_closed, 14)
    df_closed["ema_fast"] = ema(close, ema_fast_period)
    df_closed["ema_slow"] = ema(close, ema_slow_period)
    df_closed["volume_ma"] = volume.rolling(20).mean()

    # Bollinger Bands
    bb = bollinger_bands(close, bb_period, 2.0)
    df_closed["bb_width"] = bb["width_pct"]

    last = df_closed.iloc[-1]
    prev = df_closed.iloc[-2]

    current_atr = float(last["atr_val"])
    current_price = float(last["close"])
    current_rsi = float(last["rsi_val"])
    current_adx = float(last["adx_val"])
    current_bb_width = float(last["bb_width"])
    vol_ratio = float(last["volume"] / last["volume_ma"]) if last["volume_ma"] > 0 else 0

    # ============================
    # 1. DETECTAR COMPRESIÓN
    # ============================
    
    # Percentil de ATR en los últimos N períodos
    atr_series = df_closed["atr_val"].iloc[-atr_lookback:]
    atr_percentile = float((atr_series < current_atr).sum() / len(atr_series) * 100)
    
    # Percentil de BB Width
    bb_width_series = df_closed["bb_width"].iloc[-atr_lookback:]
    bb_width_percentile = float((bb_width_series < current_bb_width).sum() / len(bb_width_series) * 100)
    
    # Compresión activa: ATR o BB Width en percentiles bajos
    is_compressed = (
        atr_percentile < atr_percentile_threshold or
        bb_width_percentile < bb_width_percentile
    )

    # ============================
    # 2. DIRECCIÓN DEL SWING PREVIO
    # ============================
    
    # Último swing antes de la compresión (últimas 20 velas)
    swing_window = 20
    recent_closes = close.iloc[-swing_window:]
    swing_direction = "NONE"
    
    if float(recent_closes.iloc[-1]) > float(recent_closes.iloc[0]):
        swing_direction = "BULL"
    elif float(recent_closes.iloc[-1]) < float(recent_closes.iloc[0]):
        swing_direction = "BEAR"
    
    # EMA trend
    ema_fast_val = float(last["ema_fast"])
    ema_slow_val = float(last["ema_slow"])
    ema_trend = "BULL" if ema_fast_val > ema_slow_val else "BEAR"

    # ============================
    # 3. SEÑALES SIMPLIFICADAS
    # ============================
    
    squeeze_long = False
    squeeze_short = False
    
    if is_compressed:
        # LONG: compresión + swing previo alcista
        if swing_direction == "BULL" and ema_trend == "BULL":
            squeeze_long = True
        
        # SHORT: compresión + swing previo bajista
        elif swing_direction == "BEAR" and ema_trend == "BEAR":
            squeeze_short = True
    
    # Filtros adicionales
    volume_ok = vol_ratio >= min_vol_ratio
    adx_ok = current_adx >= adx_min

    return {
        "strategy": "volatility_squeeze",
        "trend": ema_trend,
        "breakout_long": squeeze_long and volume_ok and adx_ok,
        "breakout_short": squeeze_short and volume_ok and adx_ok,
        "squeeze_active": is_compressed,
        "compression_level": float(100 - atr_percentile),
        "atr_percentile": atr_percentile,
        "bb_width_percentile": bb_width_percentile,
        "rsi": current_rsi,
        "adx": current_adx,
        "atr": current_atr,
        "close": current_price,
        "signal_price": current_price,
        "vol_ratio": vol_ratio,
        "vol_increasing": vol_ratio > float(prev["volume"] / prev["volume_ma"]) if prev["volume_ma"] > 0 else False,
        "swing_direction": swing_direction,
        "sl_atr_mult": sl_atr_mult,
    }


def build_volatility_squeeze_sl(signal: dict, direction: str) -> float:
    """
    Calcula SL basado en ATR ajustado por la compresión.
    SL más apretado porque la volatilidad está comprimida.
    """
    price = signal.get("signal_price", signal.get("close", 0))
    atr_val = signal.get("atr", 0)
    atr_mult = signal.get("sl_atr_mult", VOL_SQUEEZE_SL_ATR_MULT)
    
    if price <= 0 or atr_val <= 0:
        return 0.0
    
    if direction == "LONG":
        return price - (atr_val * atr_mult)
    else:
        return price + (atr_val * atr_mult)
