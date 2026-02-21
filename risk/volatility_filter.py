def volatility_allowed(atr, price, max_atr_pct=0.04):
    if price == 0:
        return False
    atr_pct = atr / price
    return atr_pct < max_atr_pct
