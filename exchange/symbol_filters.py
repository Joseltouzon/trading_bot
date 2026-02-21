import time
from dataclasses import dataclass
from typing import Dict, Optional

from infra.rate_limiter import api_call

@dataclass
class SymbolFilters:
    tick_size: float
    step_size: float
    min_qty: float

class SymbolFiltersCache:
    def __init__(self, client):
        self.client = client
        self._filters: Dict[str, SymbolFilters] = {}
        self._exchange_info_cache: Optional[Dict] = None
        self._exchange_info_ts: float = 0.0

    def get_exchange_info(self) -> Dict:
        if self._exchange_info_cache is None or time.time() - self._exchange_info_ts > 3600:
            self._exchange_info_cache = api_call(self.client.futures_exchange_info)
            self._exchange_info_ts = time.time()
        return self._exchange_info_cache

    def symbol_exists(self, symbol: str) -> bool:
        info = self.get_exchange_info()
        return any(s["symbol"] == symbol for s in info["symbols"])

    def get_filters(self, symbol: str) -> SymbolFilters:
        if symbol in self._filters:
            return self._filters[symbol]

        info = self.get_exchange_info()
        for s in info["symbols"]:
            if s["symbol"] != symbol:
                continue

            tick_size = step_size = min_qty = 0.0
            for f in s["filters"]:
                if f["filterType"] == "PRICE_FILTER":
                    tick_size = float(f["tickSize"])
                elif f["filterType"] == "LOT_SIZE":
                    step_size = float(f["stepSize"])
                    min_qty = float(f["minQty"])

            sf = SymbolFilters(tick_size=tick_size, step_size=step_size, min_qty=min_qty)
            self._filters[symbol] = sf
            return sf

        raise RuntimeError(f"Símbolo no encontrado en Futures: {symbol}")
