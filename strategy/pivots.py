import pandas as pd
from typing import Optional, Tuple

def pivot_high_vectorized(high: pd.Series, left_right: int) -> pd.Series:
    window = 2 * left_right + 1
    rolling_max = high.rolling(window=window, center=True).max()
    return (high == rolling_max) & (high.notna())

def pivot_low_vectorized(low: pd.Series, left_right: int) -> pd.Series:
    window = 2 * left_right + 1
    rolling_min = low.rolling(window=window, center=True).min()
    return (low == rolling_min) & (low.notna())

def last_pivot_levels(df: pd.DataFrame, L: int) -> Tuple[Optional[float], Optional[float]]:
    ph = pivot_high_vectorized(df["high"], L)
    pl = pivot_low_vectorized(df["low"], L)
    last_ph = df.loc[ph, "high"].iloc[-1] if ph.any() else None
    last_pl = df.loc[pl, "low"].iloc[-1] if pl.any() else None
    return last_ph, last_pl
