# datafeed/market_cache.py
# Multi-timeframe: cachea DFs por símbolo e intervalo

import pandas as pd
import config as CFG
import time

from core.models import MarketData


class MarketCache:
    def __init__(self, exchange, log, db=None):
        self.exchange = exchange
        self.log = log
        self.db = db
        self.cache = {}  # {symbol: {"5m": MarketData, "15m": MarketData, "mark_price": float}}

        # Throttles por símbolo+intervalo
        self._last_kline_poll_ts = {}   # (symbol, interval) -> ts
        self._last_mark_poll_ts = {}    # symbol -> ts

        self.KLINE_POLL_SECONDS = getattr(CFG, "KLINE_POLL_SECONDS", 15)
        self.MARK_POLL_SECONDS = getattr(CFG, "MARK_POLL_SECONDS", 3)

        # Timeframes requeridos
        self._intervals = getattr(CFG, "REQUIRED_INTERVALS", ["5m"])

    # ============================================================
    # INIT
    # ============================================================

    def init_cache(self, symbols):
        for sym in symbols:
            self.cache[sym] = {}

            for interval in self._intervals:
                try:
                    kl = self.exchange.get_klines_rest(sym, interval, CFG.KLINES_LIMIT)
                    df = self._klines_to_df(kl)
                    self.cache[sym][interval] = MarketData(
                        df=df,
                        last_closed_kline_ms=int(df["close_time"].iloc[-1]),
                        mark_price=0.0,
                    )
                    self.log.info(f"[CACHE INIT] {sym} {interval} loaded {len(df)} candles")
                except Exception as e:
                    self.log.error(f"[CACHE INIT] {sym} {interval} error: {e}")

            # Mark price (solo uno por símbolo)
            try:
                self.cache[sym]["mark_price"] = float(self.exchange.get_mark_price(sym))
            except Exception as e:
                self.log.warning(f"[CACHE INIT] mark price error {sym}: {e}")
                self.cache[sym]["mark_price"] = 0.0

            self._last_mark_poll_ts[sym] = 0.0
            for interval in self._intervals:
                self._last_kline_poll_ts[(sym, interval)] = 0.0

    # ============================================================
    # UPDATE LOOP (REST POLLING)
    # ============================================================

    def update_all(self, symbols):
        now = time.time()
        for sym in symbols:
            try:
                self._update_symbol(sym, now)
            except Exception as e:
                self.log.warning(f"[CACHE] update error {sym}: {e}")

    def _update_symbol(self, symbol, now_ts: float):
        if symbol not in self.cache:
            return

        # Actualizar cada timeframe independientemente
        for interval in self._intervals:
            if interval not in self.cache[symbol]:
                continue

            last_poll_key = (symbol, interval)
            last_poll = float(self._last_kline_poll_ts.get(last_poll_key, 0.0))

            if (now_ts - last_poll) >= self.KLINE_POLL_SECONDS:
                self._last_kline_poll_ts[last_poll_key] = now_ts

                try:
                    data = self.exchange.get_klines_rest(symbol, interval, 2)
                    df_new = self._klines_to_df(data)

                    last_closed_time = int(df_new["close_time"].iloc[-2])
                    cached_last = int(self.cache[symbol][interval].last_closed_kline_ms)

                    if last_closed_time > cached_last:
                        full = self.exchange.get_klines_rest(symbol, interval, CFG.KLINES_LIMIT)
                        df_full = self._klines_to_df(full)

                        self.cache[symbol][interval].df = df_full
                        self.cache[symbol][interval].last_closed_kline_ms = last_closed_time
                        self.cache[symbol][interval]._closed_df = None  # Invalidar cache

                        self.log.info(f"[CACHE] New closed candle {symbol} {interval} close_time={last_closed_time}")
                except Exception as e:
                    self.log.warning(f"[CACHE] kline poll error {symbol} {interval}: {e}")

        # Mark price (solo uno por símbolo)
        last_mark = float(self._last_mark_poll_ts.get(symbol, 0.0))
        if (now_ts - last_mark) >= self.MARK_POLL_SECONDS:
            self._last_mark_poll_ts[symbol] = now_ts
            try:
                self.cache[symbol]["mark_price"] = float(self.exchange.get_mark_price(symbol))
            except Exception as e:
                self.log.warning(f"[CACHE] mark price error {symbol}: {e}")

    # ============================================================
    # INTERNAL
    # ============================================================

    def _klines_to_df(self, klines):
        df = pd.DataFrame(
            klines,
            columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "trades",
                "taker_buy_base", "taker_buy_quote", "ignore"
            ]
        )

        for c in ["open", "high", "low", "close", "volume"]:
            df[c] = df[c].astype(float)

        df["open_time"] = df["open_time"].astype(int)
        df["close_time"] = df["close_time"].astype(int)
        return df

    # ============================================================
    # PUBLIC API
    # ============================================================

    def get_df_copy(self, symbol, interval=None):
        """Obtiene copia del DF cacheado para un símbolo e intervalo.

        Si interval es None, devuelve el DF del primer intervalo disponible.
        """
        if symbol not in self.cache:
            return None

        if interval is not None:
            md = self.cache[symbol].get(interval)
            if md is None:
                return None
            return md.df.copy()

        # Fallback: primer intervalo disponible
        for iv in self._intervals:
            if iv in self.cache[symbol]:
                return self.cache[symbol][iv].df.copy()
        return None

    def get_df(self, symbol, interval=None):
        """Obtiene DF cacheado SIN copia (solo lectura).
        Más rápido que get_df_copy(). Usar cuando no se modifica el DF.
        """
        if symbol not in self.cache:
            return None

        if interval is not None:
            md = self.cache[symbol].get(interval)
            if md is None:
                return None
            return md.df

        # Fallback: primer intervalo disponible
        for iv in self._intervals:
            if iv in self.cache[symbol]:
                return self.cache[symbol][iv].df
        return None

    def get_closed_df(self, symbol, interval=None):
        """Obtiene DF sin la última vela parcial (cached).
        Evita hacer df.iloc[:-1] en cada ciclo.
        """
        if symbol not in self.cache:
            return None

        if interval is not None:
            md = self.cache[symbol].get(interval)
            if md is None:
                return None
            # Cache del DF cerrado
            if not hasattr(md, '_closed_df') or md._closed_df is None:
                md._closed_df = md.df.iloc[:-1].copy()
            return md._closed_df

        # Fallback
        for iv in self._intervals:
            if iv in self.cache[symbol]:
                md = self.cache[symbol][iv]
                if not hasattr(md, '_closed_df') or md._closed_df is None:
                    md._closed_df = md.df.iloc[:-1].copy()
                return md._closed_df
        return None

    def invalidate_closed_df(self, symbol, interval=None):
        """Invalida el cache del DF cerrado cuando hay nueva vela."""
        if symbol not in self.cache:
            return

        if interval is not None:
            md = self.cache[symbol].get(interval)
            if md is not None:
                md._closed_df = None
        else:
            for iv in self._intervals:
                if iv in self.cache[symbol]:
                    self.cache[symbol][iv]._closed_df = None

    def get_mark_price_cached(self, symbol):
        if symbol not in self.cache:
            return 0.0
        return float(self.cache[symbol].get("mark_price", 0.0))

    def get_last_kline_close_age_seconds(self, symbol: str, interval: str = None) -> float:
        if symbol not in self.cache:
            return float("inf")

        if interval is None:
            interval = self._intervals[0] if self._intervals else "5m"

        md = self.cache[symbol].get(interval)
        if md is None:
            return float("inf")

        last_ms = int(md.last_closed_kline_ms or 0)
        if not last_ms:
            return float("inf")

        return time.time() - (last_ms / 1000.0)

    def get_last_atr(self, symbol: str, period: int = None) -> float:
        """Calcula ATR del primer intervalo disponible."""
        if symbol not in self.cache:
            return 0.0

        # Usar el primer intervalo
        for iv in self._intervals:
            if iv in self.cache[symbol]:
                df = self.cache[symbol][iv].df
                break
        else:
            return 0.0

        if df is None or len(df) < 2:
            return 0.0

        period = period or getattr(CFG, "ATR_PERIOD", 14)

        high = df["high"]
        low = df["low"]
        close = df["close"]
        prev_close = close.shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()

        last_atr = atr.iloc[-1]
        if pd.isna(last_atr):
            return 0.0

        return float(last_atr)
