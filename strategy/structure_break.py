# strategy/structure_break.py
# Market Structure Break + Volume + Retest

import pandas as pd
import numpy as np
import config as CFG
from strategy.indicators import ema, adx, atr


def find_swing_highs_lows(df: pd.DataFrame, window: int = 5) -> tuple:
    """Encuentra swing highs y lows usando ventana."""
    high = df["high"].values
    low = df["low"].values
    n = len(high)

    swing_highs = []
    swing_lows = []

    for i in range(window, n - window):
        # Swing high: high[i] es el máximo de la ventana
        is_sh = True
        for j in range(1, window + 1):
            if high[i] <= high[i - j] or high[i] <= high[i + j]:
                is_sh = False
                break
        if is_sh:
            swing_highs.append((i, high[i]))

        # Swing low: low[i] es el mínimo de la ventana
        is_sl = True
        for j in range(1, window + 1):
            if low[i] >= low[i - j] or low[i] >= low[i + j]:
                is_sl = False
                break
        if is_sl:
            swing_lows.append((i, low[i]))

    return swing_highs, swing_lows


def compute_structure_break_signals(df: pd.DataFrame) -> dict:
    if df is None or len(df) < 60:
        return _empty_result()

    close = df["close"]
    high = df["high"]
    low = df["low"]
    current_price = float(close.iloc[-1])

    # ============================
    # 1. INDICADORES
    # ============================
    df_calc = df.copy()
    df_calc["atr_val"] = atr(df_calc, CFG.ATR_PERIOD)
    df_calc["adx_val"] = adx(df_calc, CFG.ADX_PERIOD)
    df_calc["ema_fast"] = ema(close, CFG.EMA_FAST)
    df_calc["ema_slow"] = ema(close, CFG.EMA_SLOW)
    df_calc["volume_ma"] = df["volume"].rolling(20).mean()

    last = df_calc.iloc[-1]
    prev = df_calc.iloc[-2]

    atr_val = float(last["atr_val"])
    atr_pct = (atr_val / current_price) * 100 if current_price > 0 else 0
    adx_val = float(last["adx_val"])
    ema_fast_val = float(last["ema_fast"])
    ema_slow_val = float(last["ema_slow"])
    ema_trend = "BULL" if ema_fast_val > ema_slow_val else "BEAR"

    # Volume
    vol_ma = float(last["volume_ma"]) if float(last["volume_ma"]) > 0 else 1.0
    vol_ratio = float(last["volume"]) / vol_ma if vol_ma > 0 else 1.0

    # ============================
    # 2. SWING HIGHS/LOWS
    # ============================
    swing_window = getattr(CFG, "STRUCTURE_SWING_WINDOW", 5)
    lookback = getattr(CFG, "STRUCTURE_LOOKBACK", 60)

    df_lookback = df_calc.iloc[-lookback:]
    swing_highs, swing_lows = find_swing_highs_lows(df_lookback, swing_window)

    if not swing_highs or not swing_lows:
        return _empty_result(adx_val, atr_val, atr_pct, vol_ratio, current_price, ema_trend)

    # Últimos swing high/low
    last_sh_idx, last_sh_price = swing_highs[-1]
    last_sl_idx, last_sl_price = swing_lows[-1]

    # Ajustar índices al DF completo
    last_sh_idx += len(df_calc) - lookback
    last_sl_idx += len(df_calc) - lookback

    # ============================
    # 3. DETECTAR RUPTURA
    # ============================
    break_lookback = getattr(CFG, "STRUCTURE_BREAK_LOOKBACK", 10)
    min_break_vol = getattr(CFG, "STRUCTURE_MIN_BREAK_VOLUME", 2.0)
    retest_lookback = getattr(CFG, "STRUCTURE_RETEST_LOOKBACK", 8)
    retest_tolerance_atr = getattr(CFG, "STRUCTURE_RETEST_TOLERANCE_ATR", 0.5)
    retest_buffer_atr = getattr(CFG, "STRUCTURE_SL_BUFFER_ATR", 1.0)

    # Buscar ruptura del swing high en las últimas N velas
    # (excluyendo las últimas retest_lookback velas que son donde buscamos retest)
    break_zone_end = len(df_calc) - retest_lookback
    break_zone_start = max(last_sh_idx + 1, break_zone_end - break_lookback)

    long_broke = False
    long_break_level = last_sh_price
    long_break_bar = -1

    if break_zone_start < break_zone_end:
        for bar in range(break_zone_start, break_zone_end):
            if bar >= len(df_calc):
                break
            row = df_calc.iloc[bar]
            # La vela cierra por encima del swing high
            if float(row["close"]) > last_sh_price:
                # Verificar volumen de la vela de ruptura
                bar_vol = float(row["volume"])
                bar_vol_ma = float(df_calc["volume_ma"].iloc[bar]) if float(df_calc["volume_ma"].iloc[bar]) > 0 else 1.0
                if bar_vol / bar_vol_ma >= min_break_vol:
                    long_broke = True
                    long_break_bar = bar
                    break

    # Buscar ruptura del swing low
    short_broke = False
    short_break_level = last_sl_price
    short_break_bar = -1

    if break_zone_start < break_zone_end:
        for bar in range(break_zone_start, break_zone_end):
            if bar >= len(df_calc):
                break
            row = df_calc.iloc[bar]
            if float(row["close"]) < last_sl_price:
                bar_vol = float(row["volume"])
                bar_vol_ma = float(df_calc["volume_ma"].iloc[bar]) if float(df_calc["volume_ma"].iloc[bar]) > 0 else 1.0
                if bar_vol / bar_vol_ma >= min_break_vol:
                    short_broke = True
                    short_break_bar = bar
                    break

    # ============================
    # 4. DETECTAR RETEST + RECHAZO
    # ============================
    signal_long = False
    signal_short = False
    signal_type = "none"

    retest_tolerance = atr_val * retest_tolerance_atr

    if long_broke:
        # Buscar retest: el low toca el nivel roto +/- tolerancia
        retest_zone_start = long_break_bar + 1
        retest_zone_end = min(retest_zone_start + retest_lookback, len(df_calc))

        for bar in range(retest_zone_start, retest_zone_end):
            if bar >= len(df_calc):
                break
            row = df_calc.iloc[bar]
            candle_low = float(row["low"])
            candle_close = float(row["close"])
            candle_open = float(row["open"])

            # El low toca o se acerca al nivel roto
            if candle_low <= long_break_level + retest_tolerance:
                # Vela de rechazo: cierra por encima del open (verde) y por encima del nivel
                if candle_close > candle_open and candle_close > long_break_level:
                    signal_long = True
                    signal_type = "structure_retest"
                    break

    if short_broke and not signal_long:
        retest_zone_start = short_break_bar + 1
        retest_zone_end = min(retest_zone_start + retest_lookback, len(df_calc))

        for bar in range(retest_zone_start, retest_zone_end):
            if bar >= len(df_calc):
                break
            row = df_calc.iloc[bar]
            candle_high = float(row["high"])
            candle_close = float(row["close"])
            candle_open = float(row["open"])

            if candle_high >= short_break_level - retest_tolerance:
                if candle_close < candle_open and candle_close < short_break_level:
                    signal_short = True
                    signal_type = "structure_retest"
                    break

    # Filtros adicionales
    adx_min = getattr(CFG, "STRUCTURE_ADX_MIN", 15.0)
    min_vol = getattr(CFG, "STRUCTURE_MIN_VOLUME_RATIO", 1.0)
    min_atr = getattr(CFG, "STRUCTURE_MIN_ATR_PCT", 0.10)

    if signal_long and (adx_val < adx_min or vol_ratio < min_vol or atr_pct < min_atr):
        signal_long = False
        signal_type = "none"
    if signal_short and (adx_val < adx_min or vol_ratio < min_vol or atr_pct < min_atr):
        signal_short = False
        signal_type = "none"

    return {
        "strategy": "structure_break",
        "trend": ema_trend,
        "ema_trend": ema_trend,
        "breakout_long": signal_long,
        "breakout_short": signal_short,
        "adx": adx_val,
        "adx_increasing": adx_val > float(prev.get("adx_val", 0)),
        "atr": atr_val,
        "atr_pct": atr_pct,
        "vol_ratio": vol_ratio,
        "vol_increasing": float(last["volume"]) > float(prev["volume"]),
        "close": current_price,
        "signal_price": current_price,
        "signal_type": signal_type,
        "last_sh": last_sh_price,
        "last_sl": last_sl_price,
        "rsi_val": 0,
        "ml_features": {
            "last_sh": last_sh_price,
            "last_sl": last_sl_price,
            "long_broke": long_broke,
            "short_broke": short_broke,
            "adx": adx_val,
            "atr_pct": atr_pct,
            "vol_ratio": vol_ratio,
            "ema_trend": ema_trend,
            "signal_long": signal_long,
            "signal_short": signal_short,
            "signal_type": signal_type,
        },
    }


def build_structure_sl(df: pd.DataFrame, direction: str, entry_price: float) -> float:
    """SL por debajo/encima del nivel roto + ATR buffer."""
    atr_series = atr(df, CFG.ATR_PERIOD)
    atr_val = float(atr_series.iloc[-1]) if len(atr_series) > 0 else 0
    sl_buffer = getattr(CFG, "STRUCTURE_SL_BUFFER_ATR", 1.0)

    swing_window = getattr(CFG, "STRUCTURE_SWING_WINDOW", 5)
    swing_highs, swing_lows = find_swing_highs_lows(df.iloc[-60:], swing_window)

    if direction == "LONG" and swing_highs:
        # SL por debajo del swing high roto
        break_level = swing_highs[-1][1]
        sl_from_level = break_level - (atr_val * sl_buffer)
        sl_from_pct = entry_price * (1 - 0.5 / 100)
        return max(sl_from_level, sl_from_pct)
    elif direction == "SHORT" and swing_lows:
        break_level = swing_lows[-1][1]
        sl_from_level = break_level + (atr_val * sl_buffer)
        sl_from_pct = entry_price * (1 + 0.5 / 100)
        return min(sl_from_level, sl_from_pct)
    else:
        if direction == "LONG":
            return entry_price * (1 - 0.5 / 100)
        else:
            return entry_price * (1 + 0.5 / 100)


def _empty_result(adx=0, atr=0, atr_pct=0, vol_ratio=0, close=0, trend="NONE"):
    return {
        "strategy": "structure_break",
        "trend": trend,
        "ema_trend": trend,
        "breakout_long": False,
        "breakout_short": False,
        "adx": adx,
        "adx_increasing": False,
        "atr": atr,
        "atr_pct": atr_pct,
        "vol_ratio": vol_ratio,
        "vol_increasing": False,
        "close": close,
        "signal_price": close,
        "signal_type": "none",
        "rsi_val": 0,
        "ml_features": {},
    }
