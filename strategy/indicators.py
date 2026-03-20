import numpy as np
import pandas as pd

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()

def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr1 = (high - low)
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr_val = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr_val)
    minus_di = 100 * (pd.Series(minus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr_val)

    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).replace([np.inf, -np.inf], np.nan)
    adx_val = dx.ewm(alpha=1/period, adjust=False).mean()
    return adx_val.fillna(0.0)

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rs = rs.replace([np.inf, -np.inf], np.nan)
    return (100 - (100 / (1 + rs))).fillna(50.0)

def bollinger_bands(series: pd.Series, period: int = 20, std_mult: float = 2.0) -> dict:
    mid = series.rolling(window=period, min_periods=1).mean()
    std = series.rolling(window=period, min_periods=1).std()
    return {
        "upper": mid + (std * std_mult),
        "mid": mid,
        "lower": mid - (std * std_mult),
        "width_pct": ((std * 2 * std_mult) / mid * 100).fillna(0),
    }

def stochastic_rsi(series: pd.Series, rsi_period: int = 14, stoch_period: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> dict:
    rsi_val = rsi(series, rsi_period)
    rsi_low = rsi_val.rolling(window=stoch_period, min_periods=1).min()
    rsi_high = rsi_val.rolling(window=stoch_period, min_periods=1).max()
    denom = rsi_high - rsi_low
    denom = denom.replace(0, np.nan)
    stoch_k_raw = ((rsi_val - rsi_low) / denom) * 100
    stoch_k = stoch_k_raw.rolling(window=smooth_k, min_periods=1).mean().fillna(50.0)
    stoch_d = stoch_k.rolling(window=smooth_d, min_periods=1).mean().fillna(50.0)
    return {"k": stoch_k, "d": stoch_d}
