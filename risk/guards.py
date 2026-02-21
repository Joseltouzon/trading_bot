import time


def interval_to_seconds(interval: str) -> int:
    """
    Convierte intervalos tipo 5m, 15m, 1h a segundos.
    """
    if interval.endswith("m"):
        return int(interval[:-1]) * 60
    if interval.endswith("h"):
        return int(interval[:-1]) * 3600
    raise ValueError(f"Unsupported interval format: {interval}")


def cooldown_active(state, interval: str) -> bool:
    """
    Cooldown dinámico según timeframe real.
    """
    if state.last_trade_ts is None:
        return False

    seconds = state.cooldown_bars * interval_to_seconds(interval)
    return (time.time() - state.last_trade_ts) < seconds


def daily_drawdown_exceeded(initial_equity: float, current_equity: float, max_dd_pct: float) -> bool:
    """
    Guard institucional por pérdida diaria.
    """
    if initial_equity == 0:
        return False

    dd = (initial_equity - current_equity) / initial_equity
    return dd >= max_dd_pct
