# strategy/rsi_bb_reversion.py
# RSI Divergence + Bollinger Band Mean Reversion

import pandas as pd
import numpy as np
import config as CFG
from strategy.indicators import ema, atr, adx, rsi, bollinger_bands, stochastic_rsi


def detect_rsi_divergence(df: pd.DataFrame, rsi_series: pd.Series, lookback: int = 20) -> dict:
    """Detecta divergencias RSI usando swing points más robustos.

    Busca los 2 swing lows/highs más significativos en la ventana y compara
    precio vs RSI. Requiere separación mínima de 5 velas entre swings.
    """
    if len(df) < lookback + 5:
        return {"bullish": False, "bearish": False, "strength_bull": 0.0, "strength_bear": 0.0}

    recent = df.iloc[-lookback:]
    rsi_recent = rsi_series.iloc[-lookback:]

    lows = recent["low"].values
    highs = recent["high"].values
    rsi_vals = rsi_recent.values

    # Swing lows con ventana de 5 (más robusto que 2)
    swing_lows = []
    for i in range(3, len(lows) - 3):
        is_swing_low = True
        for j in range(1, 4):
            if lows[i] > lows[i-j] or lows[i] > lows[i+j]:
                is_swing_low = False
                break
        if is_swing_low:
            swing_lows.append((i, lows[i], rsi_vals[i]))

    swing_highs = []
    for i in range(3, len(highs) - 3):
        is_swing_high = True
        for j in range(1, 4):
            if highs[i] < highs[i-j] or highs[i] < highs[i+j]:
                is_swing_high = False
                break
        if is_swing_high:
            swing_highs.append((i, highs[i], rsi_vals[i]))

    result = {"bullish": False, "bearish": False, "strength_bull": 0.0, "strength_bear": 0.0}

    if len(swing_lows) >= 2:
        s1 = swing_lows[-2]
        s2 = swing_lows[-1]
        # Separación mínima de 5 velas
        if s2[0] - s1[0] >= 5:
            # Classic bullish: lower low in price, higher low in RSI
            if s2[1] < s1[1] and s2[2] > s1[2]:
                price_diff_pct = abs(s2[1] - s1[1]) / s1[1] * 100
                rsi_diff = abs(s2[2] - s1[2])
                result["bullish"] = True
                result["strength_bull"] = min((price_diff_pct * rsi_diff) / 5.0, 1.0)

    if len(swing_highs) >= 2:
        s1 = swing_highs[-2]
        s2 = swing_highs[-1]
        if s2[0] - s1[0] >= 5:
            # Classic bearish: higher high in price, lower high in RSI
            if s2[1] > s1[1] and s2[2] < s1[2]:
                price_diff_pct = abs(s2[1] - s1[1]) / s1[1] * 100
                rsi_diff = abs(s2[2] - s1[2])
                result["bearish"] = True
                result["strength_bear"] = min((price_diff_pct * rsi_diff) / 5.0, 1.0)

    return result


def detect_rsi_crossover(rsi_series: pd.Series, level: float, direction: str) -> bool:
    """Detecta si RSI cruzó una línea de nivel en la dirección indicada.

    LONG: RSI cruzó hacia arriba desde por debajo de 'level' (ej: 30)
    SHORT: RSI cruzó hacia abajo desde por encima de 'level' (ej: 70)
    """
    if len(rsi_series) < 3:
        return False

    curr = float(rsi_series.iloc[-1])
    prev = float(rsi_series.iloc[-2])
    prev2 = float(rsi_series.iloc[-3])

    if direction == "LONG":
        # RSI estaba por debajo y ahora cruzó hacia arriba
        return prev2 < level and prev < level and curr >= level
    else:
        # RSI estaba por encima y ahora cruzó hacia abajo
        return prev2 > level and prev > level and curr <= level


def detect_bb_rejection(df: pd.DataFrame, bb_upper: float, bb_lower: float, atr_val: float) -> dict:
    """Detecta rechazo en las bandas de Bollinger.

    LONG: precio tocó/pasó banda inferior y cerró por encima (rechazo alcista)
    SHORT: precio tocó/pasó banda superior y cerró por debajo (rechazo bajista)
    """
    if len(df) < 2:
        return {"long": False, "short": False}

    last = df.iloc[-1]
    prev = df.iloc[-2]

    close_p = float(last["close"])
    low_p = float(last["low"])
    high_p = float(last["high"])
    open_p = float(last["open"])
    prev_low = float(prev["low"])
    prev_close = float(prev["close"])

    body = abs(close_p - open_p)

    # LONG: mecha inferior toca banda inferior, cierra por encima
    long_rejection = (
        low_p <= bb_lower and
        close_p > bb_lower and
        close_p > open_p and  # vela verde
        body > atr_val * 0.15  # cuerpo mínimo
    )

    # SHORT: mecha superior toca banda superior, cierra por debajo
    short_rejection = (
        high_p >= bb_upper and
        close_p < bb_upper and
        close_p < open_p and  # vela roja
        body > atr_val * 0.15
    )

    return {"long": long_rejection, "short": short_rejection}


def compute_rsi_bb_signals(df: pd.DataFrame) -> dict:
    if df is None or len(df) < 55:
        return {
            "strategy": "rsi_bb_reversion",
            "trend": "NONE",
            "breakout_long": False,
            "breakout_short": False,
            "adx": 0.0,
            "adx_increasing": False,
            "atr": 0.0,
            "vol_ratio": 0.0,
            "close": 0.0,
            "signal_price": 0.0,
            "rsi_val": 50.0,
            "bb_position": 0.0,
            "divergence_type": "none",
        }

    close = df["close"]
    current_price = float(close.iloc[-1])

    # Indicadores base
    df_calc = df.copy()
    df_calc["atr"] = atr(df_calc, CFG.ATR_PERIOD)
    df_calc["adx_val"] = adx(df_calc, CFG.ADX_PERIOD)
    df_calc["rsi_val"] = rsi(close, CFG.RSI_BB_RSI_PERIOD)

    last = df_calc.iloc[-1]
    prev = df_calc.iloc[-2]

    atr_val = float(last["atr"])
    atr_pct = (atr_val / current_price) * 100 if current_price > 0 else 0
    adx_val = float(last["adx_val"])
    adx_prev = float(prev["adx_val"])
    adx_increasing = adx_val > adx_prev
    rsi_val = float(last["rsi_val"])
    rsi_prev = float(prev["rsi_val"])

    # Bollinger Bands
    bb = bollinger_bands(close, CFG.RSI_BB_BB_PERIOD, CFG.RSI_BB_BB_STD_MULT)
    bb_upper = float(bb["upper"].iloc[-1])
    bb_lower = float(bb["lower"].iloc[-1])
    bb_mid = float(bb["mid"].iloc[-1])
    bb_width = float(bb["width_pct"].iloc[-1])

    # Posición del precio dentro de las bandas (0 = lower, 1 = upper)
    bb_range = bb_upper - bb_lower
    bb_position = ((current_price - bb_lower) / bb_range) if bb_range > 0 else 0.5

    # Stochastic RSI
    stoch = stochastic_rsi(close, CFG.RSI_BB_RSI_PERIOD, CFG.RSI_BB_STOCH_PERIOD)
    stoch_k = float(stoch["k"].iloc[-1])
    stoch_d = float(stoch["d"].iloc[-1])

    # EMA trend
    ema_fast = ema(close, CFG.EMA_FAST)
    ema_slow = ema(close, CFG.EMA_SLOW)
    ema_fast_val = float(ema_fast.iloc[-1])
    ema_slow_val = float(ema_slow.iloc[-1])
    ema_trend = "BULL" if ema_fast_val > ema_slow_val else "BEAR"
    ema_spread_pct = abs(ema_fast_val - ema_slow_val) / ema_slow_val * 100 if ema_slow_val > 0 else 0

    # Volume
    vol_ma = df["volume"].iloc[-20:].mean()
    vol_ratio = float(last["volume"]) / vol_ma if vol_ma > 0 else 1.0
    vol_increasing = float(last["volume"]) > float(prev["volume"])

    # Detecciones
    divergences = detect_rsi_divergence(df_calc, df_calc["rsi_val"], 20)
    rsi_cross_up = detect_rsi_crossover(df_calc["rsi_val"], CFG.RSI_BB_OVERSOLD, "LONG")
    rsi_cross_down = detect_rsi_crossover(df_calc["rsi_val"], CFG.RSI_BB_OVERBOUGHT, "SHORT")
    bb_rejection = detect_bb_rejection(df_calc, bb_upper, bb_lower, atr_val)

    # ===== SEÑAL LONG =====
    # Se necesita AL MENOS UNO de estos triggers:
    trigger_long = False
    trigger_type_long = "none"

    # Trigger 1: RSI cruza hacia arriba desde sobreventa + precio rechazado en BB lower
    if rsi_cross_up and bb_rejection["long"]:
        trigger_long = True
        trigger_type_long = "rsi_cross_bb_reject"

    # Trigger 2: Divergencia bullish + RSI en zona extrema
    elif divergences["bullish"] and rsi_val < CFG.RSI_BB_OVERSOLD + 10:
        trigger_long = True
        trigger_type_long = "divergence"

    # Trigger 3: RSI muy bajo (< 20) + precio por debajo de BB lower + vela verde
    elif rsi_val < 20 and current_price < bb_lower and float(last["close"]) > float(last["open"]):
        trigger_long = True
        trigger_type_long = "extreme_oversold"

    # Filtros de confirmación
    volume_ok = vol_ratio >= CFG.RSI_BB_MIN_VOLUME_RATIO
    adx_ok = adx_val >= CFG.RSI_BB_ADX_MIN
    volatility_ok = atr_pct >= CFG.RSI_BB_MIN_ATR_PCT
    stoch_ok_long = stoch_k > stoch_d or stoch_k < 20
    no_strong_bear_trend = not (adx_val > 30 and ema_trend == "BEAR" and ema_spread_pct > 0.5)

    signal_long = trigger_long and volume_ok and adx_ok and volatility_ok and stoch_ok_long and no_strong_bear_trend

    # ===== SEÑAL SHORT =====
    trigger_short = False
    trigger_type_short = "none"

    # Trigger 1: RSI cruza hacia abajo desde sobrecompra + precio rechazado en BB upper
    if rsi_cross_down and bb_rejection["short"]:
        trigger_short = True
        trigger_type_short = "rsi_cross_bb_reject"

    # Trigger 2: Divergencia bearish + RSI en zona extrema
    elif divergences["bearish"] and rsi_val > CFG.RSI_BB_OVERBOUGHT - 10:
        trigger_short = True
        trigger_type_short = "divergence"

    # Trigger 3: RSI muy alto (> 80) + precio por encima de BB upper + vela roja
    elif rsi_val > 80 and current_price > bb_upper and float(last["close"]) < float(last["open"]):
        trigger_short = True
        trigger_type_short = "extreme_overbought"

    stoch_ok_short = stoch_k < stoch_d or stoch_k > 80
    no_strong_bull_trend = not (adx_val > 30 and ema_trend == "BULL" and ema_spread_pct > 0.5)

    signal_short = trigger_short and volume_ok and adx_ok and volatility_ok and stoch_ok_short and no_strong_bull_trend

    # Tipo de divergencia para logging
    div_type = "none"
    if trigger_long:
        div_type = trigger_type_long
    elif trigger_short:
        div_type = trigger_type_short

    trend = "NONE"
    if signal_long:
        trend = "BULL"
    elif signal_short:
        trend = "BEAR"
    else:
        trend = ema_trend

    return {
        "strategy": "rsi_bb_reversion",
        "trend": trend,
        "ema_trend": ema_trend,
        "breakout_long": signal_long,
        "breakout_short": signal_short,
        "adx": adx_val,
        "adx_increasing": adx_increasing,
        "atr": atr_val,
        "atr_pct": atr_pct,
        "vol_ratio": vol_ratio,
        "vol_increasing": vol_increasing,
        "close": current_price,
        "signal_price": current_price,
        "rsi_val": rsi_val,
        "rsi_prev": rsi_prev,
        "stoch_k": stoch_k,
        "stoch_d": stoch_d,
        "bb_upper": bb_upper,
        "bb_mid": bb_mid,
        "bb_lower": bb_lower,
        "bb_position": bb_position,
        "bb_width_pct": bb_width,
        "divergence_type": div_type,
        "divergences": divergences,
        "trigger_long": trigger_type_long,
        "trigger_short": trigger_type_short,
        "bb_rejection": bb_rejection,
        "ml_features": {
            "rsi": rsi_val,
            "rsi_prev": rsi_prev,
            "stoch_k": stoch_k,
            "stoch_d": stoch_d,
            "bb_position": bb_position,
            "bb_width_pct": bb_width,
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
            "div_bullish": divergences["bullish"],
            "div_bearish": divergences["bearish"],
            "div_strength_bull": divergences.get("strength_bull", 0),
            "div_strength_bear": divergences.get("strength_bear", 0),
            "rsi_cross_up": rsi_cross_up,
            "rsi_cross_down": rsi_cross_down,
            "bb_reject_long": bb_rejection["long"],
            "bb_reject_short": bb_rejection["short"],
            "vol_ratio": vol_ratio,
            "vol_ok": volume_ok,
            "ema_trend": ema_trend,
            "ema_spread_pct": ema_spread_pct,
            "atr_pct": atr_pct,
            "adx": adx_val,
            "adx_increasing": adx_increasing,
            "signal_long": signal_long,
            "signal_short": signal_short,
        },
    }


def build_rsi_bb_sl(df: pd.DataFrame, direction: str, entry_price: float) -> float:
    close = df["close"]
    atr_series = atr(df, CFG.ATR_PERIOD)
    atr_val = float(atr_series.iloc[-1]) if len(atr_series) > 0 else 0

    bb = bollinger_bands(close, CFG.RSI_BB_BB_PERIOD, CFG.RSI_BB_BB_STD_MULT)
    bb_lower = float(bb["lower"].iloc[-1])
    bb_upper = float(bb["upper"].iloc[-1])

    if direction == "LONG":
        sl_from_bb = bb_lower - (atr_val * CFG.RSI_BB_SL_ATR_MULT)
        sl_from_pct = entry_price * (1 - CFG.RSI_BB_SL_PCT / 100)
        return max(sl_from_bb, sl_from_pct)
    else:
        sl_from_bb = bb_upper + (atr_val * CFG.RSI_BB_SL_ATR_MULT)
        sl_from_pct = entry_price * (1 + CFG.RSI_BB_SL_PCT / 100)
        return min(sl_from_bb, sl_from_pct)
