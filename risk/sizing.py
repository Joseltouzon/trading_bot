from typing import Tuple
import config as CFG
from core.utils import round_step
from exchange.binance_futures import BinanceFutures

def calc_position_qty(exchange: BinanceFutures, symbol: str, entry: float, sl: float, equity: float, risk_pct: float) -> Tuple[float, str]:
    dist = abs(entry - sl)
    if dist <= 0:
        return 0.0, "Distancia SL inválida"

    risk_usdt = equity * (risk_pct / 100.0)
    qty = risk_usdt / dist

    f = exchange.filters.get_filters(symbol)
    qty = round_step(qty, f.step_size)

    if qty < f.min_qty:
        return 0.0, f"qty {qty} < minQty {f.min_qty}"

    return qty, "OK"

def validate_margin(entry: float, qty: float, leverage: int, available_balance: float) -> Tuple[bool, str]:
    notional = entry * qty
    margin_req = notional / leverage
    if margin_req > available_balance * 0.95:
        return False, f"Margen insuficiente: req={margin_req:.2f} > disp={available_balance:.2f}"
    return True, "OK"

def validate_sl_distance(entry: float, sl: float) -> Tuple[bool, str]:
    dist_pct = abs(entry - sl) / entry * 100.0
    if dist_pct < CFG.MIN_SL_DISTANCE_PCT:
        return False, f"SL muy cercano ({dist_pct:.2f}% < {CFG.MIN_SL_DISTANCE_PCT}%)"
    return True, "OK"
