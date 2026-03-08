# execution/slippage_guard.py

import config as CFG

def slippage_allowed(signal_price: float, mark_price: float, max_ratio: float = None) -> bool:
    if max_ratio is None:
        max_ratio = getattr(CFG, "MAX_SLIPPAGE_RATIO", 0.003)
    
    if signal_price <= 0:
        return False
    diff_ratio = abs(mark_price - signal_price) / signal_price
    return diff_ratio <= max_ratio

