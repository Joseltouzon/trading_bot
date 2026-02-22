# exchange/binance_futures.py

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from binance.client import Client
from binance.enums import (
    SIDE_BUY,
    SIDE_SELL,
    FUTURE_ORDER_TYPE_MARKET,
    FUTURE_ORDER_TYPE_STOP_MARKET,
)

import config as CFG
from infra.api_cache import APICache


class BinanceFutures:
    """
    Wrapper REST para Binance Futures (USDT-M).

    Incluye:
    - ExchangeInfo cacheado (TTL configurable)
    - Cache TTL corto para account/spread (APICache)
    - Normalización qty/precio por filtros
    - Helpers: equity, available balance, posiciones, órdenes, spread
    """

    def __init__(self, api_key: str, api_secret: str, logger, testnet: bool = False):
        self.logger = logger

        # python-binance
        self.client = Client(api_key, api_secret, testnet=testnet)

        # Cache para datos tolerantes a leve delay
        self.cache = APICache(ttl=int(getattr(CFG, "API_CACHE_TTL_SECONDS", 2)))

        # ExchangeInfo cambia poco
        self._exchange_info_cache = APICache(ttl=int(getattr(CFG, "EXCHANGE_INFO_TTL_SECONDS", 60)))

        # Para no spamear logs de spread
        self._last_spread_log_ts: Dict[str, float] = {}

    # ============================================================
    # EXCHANGE INFO / FILTERS
    # ============================================================

    def _get_exchange_info(self) -> Dict[str, Any]:
        return self._exchange_info_cache.get(
            "futures_exchange_info",
            self.client.futures_exchange_info,
        )

    def symbol_exists_in_futures(self, symbol: str) -> bool:
        info = self._get_exchange_info()
        for s in info.get("symbols", []):
            if s.get("symbol") == symbol:
                return True
        return False

    def get_symbol_filters(self, symbol: str) -> dict:
        info = self._get_exchange_info()

        for s in info.get("symbols", []):
            if s.get("symbol") == symbol:
                filters = {f["filterType"]: f for f in s.get("filters", [])}
                return {
                    "step_size": float(filters.get("LOT_SIZE", {}).get("stepSize", 0.0) or 0.0),
                    "min_qty": float(filters.get("LOT_SIZE", {}).get("minQty", 0.0) or 0.0),
                    "tick_size": float(filters.get("PRICE_FILTER", {}).get("tickSize", 0.0) or 0.0),
                    # MIN_NOTIONAL no siempre está, lo dejamos por compatibilidad
                    "min_notional": float(filters.get("MIN_NOTIONAL", {}).get("notional", 0.0) or 0.0),
                }

        raise ValueError(f"Symbol {symbol} not found in futures_exchange_info")

    def _floor_to_step(self, value: float, step: float) -> float:
        if step <= 0:
            return float(value)
        return float(int(value / step) * step)

    def normalize_qty(self, symbol: str, qty: float) -> float:
        f = self.get_symbol_filters(symbol)
        step = float(f["step_size"])
        min_qty = float(f["min_qty"])

        q = self._floor_to_step(float(qty), step)

        if min_qty and q < min_qty:
            return 0.0

        # Evitar floats feos tipo 0.300000000004
        return float(f"{q:.10f}")

    def normalize_price(self, symbol: str, price: float) -> float:
        f = self.get_symbol_filters(symbol)
        tick = float(f["tick_size"])

        p = self._floor_to_step(float(price), tick)
        return float(f"{p:.10f}")

    # ============================================================
    # MARGIN / LEVERAGE
    # ============================================================

    def set_margin_and_leverage(self, symbol: str, leverage: int, margin_type: str = "ISOLATED"):
        try:
            self.client.futures_change_margin_type(symbol=symbol, marginType=margin_type)
        except Exception as e:
            # Binance suele responder "No need to change margin type"
            msg = str(e)
            if "No need to change margin type" not in msg and "margin type is already" not in msg.lower():
                self.logger.warning(f"[MARGIN] warning {symbol}: {e}")

        try:
            self.client.futures_change_leverage(symbol=symbol, leverage=int(leverage))
        except Exception as e:
            self.logger.exception(f"[LEVERAGE] change failed {symbol}: {e}")
            raise

    # ============================================================
    # ACCOUNT
    # ============================================================

    def get_account(self, use_cache: bool = True) -> Dict[str, Any]:
        if use_cache:
            return self.cache.get("futures_account", self.client.futures_account)
        return self.client.futures_account()

    def get_equity(self) -> float:
        """
        Para futures, totalMarginBalance suele representar mejor el equity.
        Fallback: totalWalletBalance.
        """
        acc = self.get_account(use_cache=True)

        try:
            if "totalMarginBalance" in acc and acc["totalMarginBalance"] is not None:
                return float(acc["totalMarginBalance"])
        except Exception:
            pass

        return float(acc.get("totalWalletBalance", 0.0) or 0.0)

    def get_available_balance(self) -> float:
        acc = self.get_account(use_cache=True)
        return float(acc.get("availableBalance", 0.0) or 0.0)

    def get_used_margin(self) -> float:
        acc = self.get_account(use_cache=True)
        return float(acc.get("totalPositionInitialMargin", 0.0) or 0.0)

    def refresh_account_state(self) -> Dict[str, Any]:
        return self.get_account(use_cache=False)

    # ============================================================
    # MARKET DATA
    # ============================================================

    def get_mark_price(self, symbol: str) -> float:
        data = self.client.futures_mark_price(symbol=symbol)
        return float(data["markPrice"])

    def get_funding_rate(self, symbol: str) -> float:
        data = self.client.futures_funding_rate(symbol=symbol, limit=1)
        if not data:
            return 0.0
        return float(data[0]["fundingRate"])

    def get_spread_pct(self, symbol: str, cache_seconds: int = 3) -> float:
        """
        Spread % usando order_book top 5:
          spread = (ask - bid) / bid * 100

        Está cacheado con APICache. Como APICache tiene TTL global, el parámetro
        cache_seconds se usa para diferenciar la key, pero el TTL real depende
        de CFG.API_CACHE_TTL_SECONDS (por defecto 2s). En la práctica está OK.
        """
        key = f"spread_pct:{symbol}:{int(cache_seconds)}"

        def _fetch() -> float:
            ob = self.client.futures_order_book(symbol=symbol, limit=5)
            bid = float(ob["bids"][0][0])
            ask = float(ob["asks"][0][0])
            if bid <= 0:
                return 999.0
            return (ask - bid) / bid * 100.0

        spread = float(self.cache.get(key, _fetch))

        # log si excede umbral, con rate limit para no spamear
        max_spread = float(getattr(CFG, "MAX_SPREAD_PCT", 0.10))
        if spread > max_spread:
            now = time.time()
            last = float(self._last_spread_log_ts.get(symbol, 0.0))
            if now - last > 30:
                self._last_spread_log_ts[symbol] = now
                self.logger.info(f"[SPREAD] {symbol} spread={spread:.3f}% (max {max_spread}%)")

        return spread

    def get_klines_rest(self, symbol: str, interval: str, limit: int = 200):
        limit = int(limit)
        return self.client.futures_klines(symbol=symbol, interval=interval, limit=limit)

    # ============================================================
    # POSITIONS
    # ============================================================

    def get_open_positions(self, symbol: str = None) -> List[dict]:
        """
        Devuelve lista de posiciones abiertas (positionAmt != 0).
        """
        positions_data = self.client.futures_position_information(symbol=symbol)
        positions: List[dict] = []

        for p in positions_data:
            position_amt = float(p.get("positionAmt", 0) or 0.0)
            if position_amt == 0.0:
                continue

            side = "LONG" if position_amt > 0 else "SHORT"
            positions.append({
                "symbol": p.get("symbol"),
                "side": side,
                "size": abs(position_amt),
                "entry_price": float(p.get("entryPrice", 0) or 0.0),
                "unrealized_pnl": float(p.get("unRealizedProfit", 0) or 0.0),
                "leverage": int(float(p.get("leverage", 0) or 0)) if p.get("leverage") else None,
                "liquidation_price": float(p.get("liquidationPrice", 0) or 0.0),
            })

        return positions

    def get_position_history(self, symbol: str, open_time: int):
        """
        Devuelve información real del cierre de una posición.
        open_time debe estar en ms (timestamp Binance).
        """

        try:
            trades = self.client.futures_account_trades(
                symbol=symbol,
                startTime=open_time
            )

            if not trades:
                return None

            total_realized = 0.0
            total_qty = 0.0
            weighted_price = 0.0

            for t in trades:

                realized = float(t.get("realizedPnl", 0))
                qty = abs(float(t.get("qty", 0)))
                price = float(t.get("price", 0))

                # Solo contamos trades que realmente cierran/reducen
                if realized != 0:

                    total_realized += realized
                    total_qty += qty
                    weighted_price += price * qty

            if total_qty == 0:
                return None

            avg_exit_price = weighted_price / total_qty

            return {
                "symbol": symbol,
                "exit_price": avg_exit_price,
                "closed_qty": total_qty,
                "realizedPnl": total_realized
            }

        except Exception as e:
            self.logger.warning(f"{symbol} get_position_history failed: {e}")
            return None
            
    # ============================================================
    # ORDERS
    # ============================================================

    def place_market_order(self, symbol: str, side: str, quantity: float):
        """
        side: "LONG" | "SHORT"
        """
        order_side = SIDE_BUY if side == "LONG" else SIDE_SELL

        q = self.normalize_qty(symbol, float(quantity))
        if q <= 0:
            raise ValueError(f"Qty invalid after normalization. symbol={symbol} qty={quantity}")

        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=FUTURE_ORDER_TYPE_MARKET,
                quantity=q
            )
            self.logger.info(f"[ORDER] MARKET {symbol} {side} qty={q}")
            return order
        except Exception as e:
            self.logger.exception(f"[ORDER] Market order failed {symbol}: {e}")
            raise

    def place_reduce_only_stop(self, symbol: str, side: str, quantity: float, stop_price: float):
        """
        STOP_MARKET reduceOnly=True
        side debe ser directamente "BUY" o "SELL"
        """

        if side not in ["BUY", "SELL"]:
            raise ValueError(f"Invalid stop side: {side}")

        sp = self.normalize_price(symbol, float(stop_price))
        qty = self.normalize_qty(symbol, float(quantity))

        if sp <= 0:
            raise ValueError(f"Invalid stop_price after normalization. symbol={symbol} stop_price={stop_price}")

        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type=FUTURE_ORDER_TYPE_STOP_MARKET,
                quantity=qty,
                stopPrice=sp,
                reduceOnly=True,
                closePosition=False
            )

            self.logger.info(
                f"[ORDER] STOP_MARKET {symbol} side={side} qty={qty} stop={sp}"
            )

            return order

        except Exception as e:
            self.logger.exception(f"[ORDER] Stop order failed {symbol}: {e}")
            raise

    # ============================================================
    # ORDER STATUS / CANCEL
    # ============================================================

    def get_order(self, symbol: str, order_id: int):
        return self.client.futures_get_order(symbol=symbol, orderId=int(order_id))

    def cancel_order(self, symbol: str, order_id: int):
        try:
            res = self.client.futures_cancel_order(symbol=symbol, orderId=int(order_id))
            self.logger.info(f"[ORDER] CANCEL {symbol} orderId={order_id}")
            return res
        except Exception as e:
            self.logger.warning(f"[ORDER] cancel failed {symbol} orderId={order_id}: {e}")
            raise

    def cancel_algo_order(self, symbol: str, algo_id: int):
        try:
            self.client.futures_cancel_algo_order(
                symbol=symbol,
                algoId=int(algo_id)
            )
            self.logger.info(f"[CANCEL] ALGO STOP {symbol} algoId={algo_id}")

        except Exception as e:
            msg = str(e)

            if "-2011" in msg or "Unknown order" in msg:
                self.logger.warning(f"[CANCEL] ALGO already closed {symbol} algoId={algo_id}")
                return

            self.logger.exception(f"[CANCEL] Algo cancel failed {symbol}: {e}")
            raise  

    # ============================================================
    # POSITION MANAGEMENT
    # ============================================================

    def close_position(self, symbol: str):
        """
        Cierra posición abierta al mercado.
        """
        positions = self.get_open_positions(symbol=symbol)

        if not positions:
            return False

        p = positions[0]
        side = "SHORT" if p["side"] == "LONG" else "LONG"
        qty = float(p["size"])

        return self.place_market_order(symbol, side, qty)

    # ============================================================
    # PERFORMANCE
    # ============================================================

    def get_daily_realized_pnl(self) -> float:
        """
        PnL realizado hoy (UTC).
        """
        start_ts = int(time.time() // 86400 * 86400) * 1000  # inicio día UTC en ms

        income = self.client.futures_income_history(
            incomeType="REALIZED_PNL",
            startTime=start_ts
        )

        total = 0.0
        for row in income:
            total += float(row.get("income", 0.0))

        return total

    # ============================================================
    # EXPOSURE
    # ============================================================

    def get_total_exposure_notional(self) -> float:
        """
        Suma del notional absoluto de todas las posiciones abiertas.
        """
        positions = self.get_open_positions()

        total_notional = 0.0

        for p in positions:
            mark = self.get_mark_price(p["symbol"])
            total_notional += abs(mark * float(p["size"]))

        return total_notional

    # ============================================================
    # HEALTH CHECK
    # ============================================================

    def health_check(self) -> dict:
        """
        Testea conectividad y latencia REST.
        """
        result = {
            "api_reachable": False,
            "latency_ms": None,
            "server_time_diff_ms": None
        }

        try:
            t0 = time.time()
            server_time = self.client.futures_time()
            t1 = time.time()

            latency = (t1 - t0) * 1000.0

            server_ts = int(server_time.get("serverTime"))
            local_ts = int(time.time() * 1000)

            result["api_reachable"] = True
            result["latency_ms"] = round(latency, 2)
            result["server_time_diff_ms"] = local_ts - server_ts

        except Exception as e:
            self.logger.warning(f"[HEALTH] API error: {e}")

        return result
    
    # ============================================================
    # VOLATILITY
    # ============================================================

    def get_atr_pct(self, symbol: str, interval: str = "5m", period: int = 14) -> float:
        """
        Devuelve ATR % (ATR / precio * 100).
        """
        kl = self.get_klines_rest(symbol, interval, limit=period + 5)

        if not kl or len(kl) < period + 1:
            return 0.0

        highs = [float(k[2]) for k in kl]
        lows = [float(k[3]) for k in kl]
        closes = [float(k[4]) for k in kl]

        trs = []
        for i in range(1, len(kl)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)

        atr = sum(trs[-period:]) / period
        price = closes[-1]

        if price <= 0:
            return 0.0

        return (atr / price) * 100.0        
