# strategy/volatility_regime.py
# Volatility Regime + Adaptive Entry (1h)
# Adapta la entrada según el régimen de volatilidad

import pandas as pd
import numpy as np
import config as CFG
from strategy.indicators import ema, atr, adx, rsi


# ============================================================
# CONFIGURACIÓN DEFAULT
# ============================================================
VR_ATR_PERIOD = 14
VR_ATR_LOOKBACK = 100
VR_ATR_LOW_PERCENTILE = 20
VR_ATR_HIGH_PERCENTILE = 70
VR_VOLUME_RATIO_MIN = 1.3
VR_RSI_PERIOD = 14
VR_ADX_MIN = 18.0
VR_SL_ATR_MULT = 1.5
VR_EMA_FAST = 20
VR_EMA_SLOW = 50
VR_MOMENTUM_BARS = 3
VR_BREAKOUT_LOOKBACK = 20


def compute_volatility_regime_signals(df: pd.DataFrame) -> dict:
    """
    Estrategia adaptativa según régimen de volatilidad.
    
    Lógica:
    1. ATR < percentil 20 → BAJO → breakout en dirección swing
    2. ATR > percentil 70 → ALTO → momentum continuation
    3. Entre 20-70 → NO OPERAR
    
    Timeframe óptimo: 1h
    """
    
    if df is None or len(df) < 120:
        return _empty_signal()

    df_closed = df.iloc[:-1].copy()
    if len(df_closed) < 120:
        df_closed = df.copy()

    close = df_closed["close"]
    volume = df_closed["volume"]
    high = df_closed["high"]
    low = df_closed["low"]
    open_price = df_closed["open"]

    # Parámetros
    atr_period = getattr(CFG, "VR_ATR_PERIOD", VR_ATR_PERIOD)
    atr_lookback = getattr(CFG, "VR_ATR_LOOKBACK", VR_ATR_LOOKBACK)
    atr_low_pct = getattr(CFG, "VR_ATR_LOW_PERCENTILE", VR_ATR_LOW_PERCENTILE)
    atr_high_pct = getattr(CFG, "VR_ATR_HIGH_PERCENTILE", VR_ATR_HIGH_PERCENTILE)
    vol_ratio_min = getattr(CFG, "VR_VOLUME_RATIO_MIN", VR_VOLUME_RATIO_MIN)
    rsi_period = getattr(CFG, "VR_RSI_PERIOD", VR_RSI_PERIOD)
    adx_min = getattr(CFG, "VR_ADX_MIN", VR_ADX_MIN)
    sl_atr_mult = getattr(CFG, "VR_SL_ATR_MULT", VR_SL_ATR_MULT)
    ema_fast_period = getattr(CFG, "VR_EMA_FAST", VR_EMA_FAST)
    ema_slow_period = getattr(CFG, "VR_EMA_SLOW", VR_EMA_SLOW)
    momentum_bars = getattr(CFG, "VR_MOMENTUM_BARS", VR_MOMENTUM_BARS)
    breakout_lookback = getattr(CFG, "VR_BREAKOUT_LOOKBACK", VR_BREAKOUT_LOOKBACK)

    # Calcular indicadores
    df_closed["atr_val"] = atr(df_closed, atr_period)
    df_closed["rsi_val"] = rsi(close, rsi_period)
    df_closed["adx_val"] = adx(df_closed, 14)
    df_closed["ema_fast"] = ema(close, ema_fast_period)
    df_closed["ema_slow"] = ema(close, ema_slow_period)
    df_closed["volume_ma"] = volume.rolling(20).mean()

    last = df_closed.iloc[-1]
    prev = df_closed.iloc[-2]

    current_price = float(last["close"])
    current_rsi = float(last["rsi_val"])
    current_adx = float(last["adx_val"])
    current_atr = float(last["atr_val"])
    vol_ratio = float(last["volume"] / last["volume_ma"]) if last["volume_ma"] > 0 else 0

    # ============================
    # 1. RÉGIMEN DE VOLATILIDAD
    # ============================
    atr_series = df_closed["atr_val"].iloc[-atr_lookback:]
    atr_percentile = float((atr_series < current_atr).sum() / len(atr_series) * 100)
    
    regime_low = atr_percentile < atr_low_pct       # compresión
    regime_high = atr_percentile > atr_high_pct     # expansión
    regime_normal = not regime_low and not regime_high

    # ============================
    # 2. EMA TREND
    # ============================
    ema_fast_val = float(last["ema_fast"])
    ema_slow_val = float(last["ema_slow"])
    ema_trend = "BULL" if ema_fast_val > ema_slow_val else "BEAR"

    # ============================
    # 3. SEÑAL BAJO (breakout como VS)
    # ============================
    signal_low_long = False
    signal_low_short = False
    
    if regime_low:
        # Swing direction (últimas 20 velas)
        recent_closes = close.iloc[-breakout_lookback:]
        swing_up = float(recent_closes.iloc[-1]) > float(recent_closes.iloc[0])
        swing_down = float(recent_closes.iloc[-1]) < float(recent_closes.iloc[0])
        
        # LONG: compresión + swing alcista + tendencia alcista
        if swing_up and ema_trend == "BULL":
            signal_low_long = True
        # SHORT: compresión + swing bajista + tendencia bajista
        elif swing_down and ema_trend == "BEAR":
            signal_low_short = True

    # ============================
    # 4. SEÑAL ALTO (momentum continuation)
    # ============================
    signal_high_long = False
    signal_high_short = False
    
    if regime_high:
        # Contar velas consecutivas en la misma dirección
        bullish_count = 0
        bearish_count = 0
        
        for i in range(-momentum_bars, 0):
            row = df_closed.iloc[i]
            if float(row["close"]) > float(row["open"]):
                bullish_count += 1
            elif float(row["close"]) < float(row["open"]):
                bearish_count += 1
        
        # Precio hace nuevos highs/lows
        recent_high = float(high.iloc[-momentum_bars:].max())
        recent_low = float(low.iloc[-momentum_bars:].min())
        making_new_high = float(last["high"]) >= recent_high
        making_new_low = float(last["low"]) <= recent_low
        
        # LONG: expansión + N velas alcistas + nuevo high
        if bullish_count >= momentum_bars and making_new_high and ema_trend == "BULL":
            signal_high_long = True
        # SHORT: expansión + N velas bajistas + nuevo low
        elif bearish_count >= momentum_bars and making_new_low and ema_trend == "BEAR":
            signal_high_short = True

    # ============================
    # 5. COMBINAR SEÑALES
    # ============================
    vr_long = signal_low_long or signal_high_long
    vr_short = signal_low_short or signal_high_short

    # Filtros
    volume_ok = vol_ratio >= vol_ratio_min
    adx_ok = current_adx >= adx_min

    # Régimen label
    if regime_low:
        regime = "LOW"
    elif regime_high:
        regime = "HIGH"
    else:
        regime = "NORMAL"

    return {
        "strategy": "volatility_regime",
        "trend": ema_trend,
        "breakout_long": vr_long and volume_ok and adx_ok,
        "breakout_short": vr_short and volume_ok and adx_ok,
        "regime": regime,
        "atr_percentile": atr_percentile,
        "rsi": current_rsi,
        "adx": current_adx,
        "atr": current_atr,
        "close": current_price,
        "signal_price": current_price,
        "vol_ratio": vol_ratio,
        "vol_increasing": vol_ratio > float(prev["volume"] / prev["volume_ma"]) if prev["volume_ma"] > 0 else False,
        "sl_atr_mult": sl_atr_mult,
    }


def build_volatility_regime_sl(signal: dict, direction: str) -> float:
    price = signal.get("signal_price", signal.get("close", 0))
    atr_val = signal.get("atr", 0)
    atr_mult = signal.get("sl_atr_mult", VR_SL_ATR_MULT)
    
    if price <= 0 or atr_val <= 0:
        return 0.0
    
    if direction == "LONG":
        return price - (atr_val * atr_mult)
    else:
        return price + (atr_val * atr_mult)


def _empty_signal():
    return {
        "strategy": "volatility_regime",
        "trend": "NONE",
        "breakout_long": False,
        "breakout_short": False,
        "regime": "NORMAL",
        "atr_percentile": 50.0,
        "rsi": 50.0,
        "adx": 0.0,
        "atr": 0.0,
        "close": 0.0,
        "vol_ratio": 0.0,
    }
