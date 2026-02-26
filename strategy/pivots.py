import pandas as pd
from typing import Optional, Tuple

def pivot_high_vectorized(high: pd.Series, left_right: int) -> pd.Series:
    window = 2 * left_right + 1
    # center=False asegura que solo usamos datos pasados
    rolling_max = high.rolling(window=window, center=False).max()
    # Identificamos el pico
    is_pivot = (high == rolling_max) & (high.notna())
    # Desplazamos para confirmar que pasaron las velas de la derecha
    return is_pivot.shift(left_right).fillna(False)

def pivot_low_vectorized(low: pd.Series, left_right: int) -> pd.Series:
    window = 2 * left_right + 1
    rolling_min = low.rolling(window=window, center=False).min()
    is_pivot = (low == rolling_min) & (low.notna())
    return is_pivot.shift(left_right).fillna(False)

def last_pivot_levels(df: pd.DataFrame, L: int) -> Tuple[Optional[float], Optional[float]]:
    ph = pivot_high_vectorized(df["high"], L)
    pl = pivot_low_vectorized(df["low"], L)
    last_ph = df.loc[ph, "high"].iloc[-1] if ph.any() else None
    last_pl = df.loc[pl, "low"].iloc[-1] if pl.any() else None
    return last_ph, last_pl
