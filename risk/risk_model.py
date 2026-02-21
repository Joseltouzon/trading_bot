def dynamic_risk(base_risk: float, adx: float) -> float:
    """
    Escalado dinámico de riesgo según fuerza de tendencia.
    """

    if adx > 30:
        return base_risk * 1.3

    if adx < 20:
        return base_risk * 0.7

    return base_risk


def position_size(equity: float, risk_pct: float, stop_distance: float) -> float:
    """
    Calcula tamaño de posición basado en riesgo real.
    """

    if stop_distance <= 0:
        return 0

    risk_amount = equity * risk_pct
    qty = risk_amount / stop_distance

    return qty
