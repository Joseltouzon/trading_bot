# execution/slippage_guard.py

import config as CFG

def slippage_allowed(signal_price: float, mark_price: float) -> bool:
    """
    Compara desviación entre precio de señal (close) y mark price actual.
    max_slippage es un RATIO, ej:
      0.002 = 0.2%
      0.005 = 0.5%
    """
    if not signal_price or signal_price <= 0:
        return False
    if not mark_price or mark_price <= 0:
        return False

    max_slippage = float(getattr(CFG, "MAX_SLIPPAGE_RATIO", 0.003))  # default 0.3%
    diff_ratio = abs(mark_price - signal_price) / signal_price
    return diff_ratio <= max_slippage

