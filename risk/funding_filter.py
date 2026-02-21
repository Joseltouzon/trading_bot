# risk/funding_filter.py
import config as CFG

def funding_allowed(side, funding_rate, threshold=None):
    thr = float(threshold if threshold is not None else getattr(CFG, "FUNDING_THRESHOLD", 0.0005))
    if side == "LONG" and funding_rate > thr:
        return False
    if side == "SHORT" and funding_rate < -thr:
        return False
    return True