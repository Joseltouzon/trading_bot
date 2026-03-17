# strategy/stop_hunt.py

import pandas as pd
import numpy as np
import config as CFG
from strategy.pivots import pivot_high_vectorized, pivot_low_vectorized
from strategy.indicators import ema, atr


def find_swing_levels(df: pd.DataFrame, lookback: int = 5):
    if len(df) < lookback * 2:
        return [], []

    df_calc = df.copy()

    df_calc["ph"] = pivot_high_vectorized(df_calc["high"], CFG.PIVOT_LEN)
    df_calc["pl"] = pivot_low_vectorized(df_calc["low"], CFG.PIVOT_LEN)

    recent = df_calc.iloc[-lookback:]

    swing_highs = []
    swing_lows = []

    for i, row in recent.iterrows():
        if row["ph"]:
            swing_highs.append(float(row["high"]))
        if row["pl"]:
            swing_lows.append(float(row["low"]))

    return swing_highs[-CFG.STOP_HUNT_MIN_ZONES:], swing_lows[-CFG.STOP_HUNT_MIN_ZONES:]


def find_order_blocks(df: pd.DataFrame, direction: str, lookback: int = None):
    if lookback is None:
        lookback = CFG.ORDER_BLOCK_LOOKBACK

    lookback = min(lookback, len(df) - 2)
    if lookback < 2:
        return []

    blocks = []
    recent = df.iloc[-lookback-1:-1].copy()

    for i in range(len(recent) - 1):
        curr = recent.iloc[i]
        next_row = recent.iloc[i + 1]

        if direction == "LONG":
            if curr["close"] < curr["open"]:
                impulse_up = next_row["close"] > curr["high"] and next_row["close"] > curr["open"]
                if impulse_up:
                    blocks.append({
                        "type": "bear_OB",
                        "high": float(curr["high"]),
                        "low": float(curr["low"]),
                        "close": float(curr["close"]),
                        "index": i
                    })

        elif direction == "SHORT":
            if curr["close"] > curr["open"]:
                impulse_down = next_row["close"] < curr["low"] and next_row["close"] < curr["open"]
                if impulse_down:
                    blocks.append({
                        "type": "bull_OB",
                        "high": float(curr["high"]),
                        "low": float(curr["low"]),
                        "close": float(curr["close"]),
                        "index": i
                    })

    return blocks[-3:]


def detect_stop_hunt(df: pd.DataFrame, zone_price: float, direction: str):
    if len(df) < 3:
        return False, {}

    last = df.iloc[-1]
    prev = df.iloc[-2]

    wick_pct = CFG.STOP_HUNT_WICK_PCT / 100
    wick_threshold = zone_price * wick_pct

    if direction == "LONG":
        wick_bottom = last["low"]
        body_top = last["close"]
        body_bottom = min(last["open"], last["close"])

        zone_breached = wick_bottom < zone_price
        rejection = body_top > zone_price

        if zone_breached and rejection:
            wick_size = zone_price - wick_bottom
            body_size = body_top - body_bottom
            body_to_wick = body_size / wick_size if wick_size > 0 else 0

            rejection_ok = body_to_wick >= CFG.STOP_HUNT_REJECTION_RATIO

            if rejection_ok:
                return True, {
                    "zone_price": zone_price,
                    "wick_size_pct": (wick_size / zone_price) * 100,
                    "body_ratio": body_to_wick,
                    "rejection_strength": body_to_wick
                }

    elif direction == "SHORT":
        wick_top = last["high"]
        body_top = max(last["open"], last["close"])
        body_bottom = last["close"]

        zone_breached = wick_top > zone_price
        rejection = body_bottom < zone_price

        if zone_breached and rejection:
            wick_size = wick_top - zone_price
            body_size = body_top - body_bottom
            body_to_wick = body_size / wick_size if wick_size > 0 else 0

            rejection_ok = body_to_wick >= CFG.STOP_HUNT_REJECTION_RATIO

            if rejection_ok:
                return True, {
                    "zone_price": zone_price,
                    "wick_size_pct": (wick_size / zone_price) * 100,
                    "body_ratio": body_to_wick,
                    "rejection_strength": body_to_wick
                }

    return False, {}


def check_momentum(df: pd.DataFrame, direction: str) -> bool:
    lookback = CFG.STOP_HUNT_MOMENTUM_BARS + 1
    if len(df) < lookback:
        return False

    close = df["close"].iloc[-lookback:]
    momentum_bars = CFG.STOP_HUNT_MOMENTUM_BARS

    if direction == "LONG":
        momentum = ((close.iloc[-1] - close.iloc[-momentum_bars]) / close.iloc[-momentum_bars]) * 100
        return momentum > 0.1
    else:
        momentum = ((close.iloc[-1] - close.iloc[-momentum_bars]) / close.iloc[-momentum_bars]) * 100
        return momentum < -0.1


def check_volume(df: pd.DataFrame) -> bool:
    if len(df) < 20:
        return True

    vol_ma = df["volume"].iloc[-20:].mean()
    last_vol = df["volume"].iloc[-1]

    return last_vol / vol_ma >= CFG.STOP_HUNT_MIN_VOLUME_RATIO


def compute_stop_hunt_signals(df: pd.DataFrame) -> dict:
    if df is None or len(df) < 30:
        return {
            "strategy": "stop_hunt",
            "trend": "NONE",
            "breakout_long": False,
            "breakout_short": False,
            "adx": 0.0,
            "atr": 0.0,
            "vol_ratio": 0.0,
            "close": 0.0,
            "last_ph": None,
            "last_pl": None,
            "signal_price": 0.0,
            "stop_hunt_zones": {"long": [], "short": []},
            "hunt_detected": False,
        }

    df_calc = df.iloc[:-1].copy()
    if len(df_calc) < 30:
        df_calc = df.copy()

    close = df_calc["close"]

    df_calc["atr"] = atr(df_calc, CFG.ATR_PERIOD)
    last = df_calc.iloc[-1]
    current_price = float(last["close"])
    atr_val = float(last["atr"])
    atr_pct = (atr_val / current_price) * 100 if current_price > 0 else 0

    swing_highs, swing_lows = find_swing_levels(df_calc)
    ob_bull = find_order_blocks(df_calc, "LONG")
    ob_bear = find_order_blocks(df_calc, "SHORT")

    all_long_zones = swing_lows + [ob["low"] for ob in ob_bull]
    all_short_zones = swing_highs + [ob["high"] for ob in ob_bear]

    max_dist_pct = CFG.STOP_HUNT_MAX_ZONE_DISTANCE_PCT / 100
    min_atr_pct = getattr(CFG, "STOP_HUNT_MIN_ATR_PCT", 0.10)
    volatility_ok = atr_pct >= min_atr_pct

    ema_fast = ema(close, CFG.EMA_FAST)
    ema_slow = ema(close, CFG.EMA_SLOW)
    last_ema_fast = float(ema_fast.iloc[-1])
    last_ema_slow = float(ema_slow.iloc[-1])
    ema_trend = "BULL" if last_ema_fast > last_ema_slow else "BEAR"

    breakout_long = False
    breakout_short = False
    hunt_info = {}
    signal_price = 0.0

    use_ema_filter = getattr(CFG, "STOP_HUNT_USE_EMA_FILTER", True)
    vol_ok = check_volume(df_calc)
    momentum_long = check_momentum(df_calc, "LONG")
    momentum_short = check_momentum(df_calc, "SHORT")

    for zone in all_long_zones:
        dist_pct = abs(current_price - zone) / zone
        if dist_pct <= max_dist_pct:
            hunt_detected, info = detect_stop_hunt(df_calc, zone, "LONG")
            ema_ok = not use_ema_filter or ema_trend == "BULL"
            if hunt_detected and vol_ok and momentum_long and volatility_ok and ema_ok:
                breakout_long = True
                hunt_info = info
                signal_price = zone
                break

    for zone in all_short_zones:
        dist_pct = abs(current_price - zone) / zone
        if dist_pct <= max_dist_pct:
            hunt_detected, info = detect_stop_hunt(df_calc, zone, "SHORT")
            ema_ok = not use_ema_filter or ema_trend == "BEAR"
            if hunt_detected and vol_ok and momentum_short and volatility_ok and ema_ok:
                breakout_short = True
                hunt_info = info
                signal_price = zone
                break

    trend = "NONE"
    if breakout_long:
        trend = "BULL"
    elif breakout_short:
        trend = "BEAR"
    else:
        trend = ema_trend

    vol_ma = df_calc["volume"].iloc[-20:].mean()
    vol_ratio = float(last["volume"]) / vol_ma if vol_ma > 0 else 1.0

    return {
        "strategy": "stop_hunt",
        "trend": trend,
        "ema_trend": ema_trend,
        "last_ph": swing_highs[-1] if swing_highs else None,
        "last_pl": swing_lows[-1] if swing_lows else None,
        "breakout_long": breakout_long,
        "breakout_short": breakout_short,
        "adx": 0.0,
        "adx_increasing": False,
        "atr": atr_val,
        "atr_pct": atr_pct,
        "vol_ratio": vol_ratio,
        "vol_increasing": last["volume"] > df_calc["volume"].iloc[-2],
        "close": current_price,
        "signal_price": signal_price,
        "stop_hunt_zones": {
            "long": all_long_zones,
            "short": all_short_zones
        },
        "hunt_detected": breakout_long or breakout_short,
        "hunt_info": hunt_info,
        "ml_features": {
            "atr": float(atr_val),
            "atr_pct": float(atr_pct),
            "vol_ratio": float(vol_ratio),
            "vol_ok": bool(vol_ok),
            "ema_trend": ema_trend,
            "volatility_ok": volatility_ok,
            "swing_highs": swing_highs,
            "swing_lows": swing_lows,
            "order_blocks_bull": len(ob_bull),
            "order_blocks_bear": len(ob_bear),
        },
    }


def build_stop_hunt_sl(df: pd.DataFrame, direction: str, entry_price: float) -> float:
    atr_val = atr(df, CFG.ATR_PERIOD)
    last = df.iloc[-1]

    if direction == "LONG":
        swing_lows, _ = find_swing_levels(df)
        if swing_lows:
            sl_price = min(swing_lows) - (atr_val * CFG.STOP_HUNT_ATR_MULT_SL)
        else:
            sl_price = entry_price * (1 - CFG.STOP_HUNT_SL_PCT / 100)
        return sl_price
    else:
        _, swing_highs = find_swing_levels(df)
        if swing_highs:
            sl_price = max(swing_highs) + (atr_val * CFG.STOP_HUNT_ATR_MULT_SL)
        else:
            sl_price = entry_price * (1 + CFG.STOP_HUNT_SL_PCT / 100)
        return sl_price
