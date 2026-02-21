import math
from datetime import datetime, timezone

def round_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    return math.floor(value / step) * step

def utc_day_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def clamp(x, lo, hi):
    return max(lo, min(hi, x))
