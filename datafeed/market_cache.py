# datafeed/market_cache.py

import pandas as pd
import config as CFG
import time

from core.models import MarketData


class MarketCache:
    def __init__(self, exchange, log, db=None):
        self.exchange = exchange
        self.log = log
        self.db = db
        self.cache = {}
        self._cached_timeframe = None

        # Throttles (para REST en 5m y Macbook viejo)
        self._last_kline_poll_ts = {}   # symbol -> ts
        self._last_mark_poll_ts = {}    # symbol -> ts

        # Ajustables (podés mover a config si querés)
        self.KLINE_POLL_SECONDS = getattr(CFG, "KLINE_POLL_SECONDS", 15)
        self.MARK_POLL_SECONDS = getattr(CFG, "MARK_POLL_SECONDS", 3)

    # ============================================================
    # INIT
    # ============================================================
    def _get_current_timeframe(self, fallback: str = "5m") -> str:
        """
        Obtiene el timeframe desde la DB si está disponible, sino usa fallback.
        Valida que sea un timeframe soportado por Binance.
        """
        valid_tfs = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"]
        
        if self.db:
            try:
                state = self.db.load_state()
                tf = state.get("timeframe", fallback)
                if tf in valid_tfs:
                    return tf
                else:
                    self.log.warning(f"[TIMEFRAME] '{tf}' no válido, usando fallback '{fallback}'")
            except Exception as e:
                self.log.error(f"[TIMEFRAME] Error leyendo estado: {e}")
        
        return fallback

    def init_cache(self, symbols):
        timeframe = self._get_current_timeframe()
        for sym in symbols:
            kl = self.exchange.get_klines_rest(sym, timeframe, CFG.KLINES_LIMIT)
            df = self._klines_to_df(kl)

            mp = 0.0
            try:
                mp = float(self.exchange.get_mark_price(sym))
            except Exception as e:
                self.log.warning(f"[CACHE INIT] mark price error {sym}: {e}")

            self.cache[sym] = MarketData(
                df=df,
                last_closed_kline_ms=int(df["close_time"].iloc[-1]),
                mark_price=mp,
            )

            self._last_kline_poll_ts[sym] = 0.0
            self._last_mark_poll_ts[sym] = 0.0

            self.log.info(f"[CACHE INIT] {sym} loaded {len(df)} candles")

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

        current_tf = self._get_current_timeframe()
        if self._cached_timeframe and current_tf != self._cached_timeframe:
            self.log.critical(f"[TIMEFRAME] Cambio detectado: {self._cached_timeframe} -> {current_tf}. Reiniciá el bot para aplicar.")
            return
        self._cached_timeframe = current_tf
        timeframe = current_tf

        # ----------- 1) KLINES (poll cada X segundos) -----------
        last_poll = float(self._last_kline_poll_ts.get(symbol, 0.0))
        if (now_ts - last_poll) >= self.KLINE_POLL_SECONDS:
            self._last_kline_poll_ts[symbol] = now_ts

            data = self.exchange.get_klines_rest(symbol, timeframe, 2)
            df_new = self._klines_to_df(data)

            # Ojo: [-2] es la última cerrada (la [-1] puede ser la que está en curso)
            last_closed_time = int(df_new["close_time"].iloc[-2])
            cached_last = int(self.cache[symbol].last_closed_kline_ms)

            if last_closed_time > cached_last:
                full = self.exchange.get_klines_rest(symbol, timeframe, CFG.KLINES_LIMIT)
                df_full = self._klines_to_df(full)

                self.cache[symbol].df = df_full
                self.cache[symbol].last_closed_kline_ms = last_closed_time

                self.log.info(f"[CACHE] New closed candle {symbol} close_time={last_closed_time}")

        # ----------- 2) MARK PRICE (poll cada Y segundos) -----------
        last_mark = float(self._last_mark_poll_ts.get(symbol, 0.0))
        if (now_ts - last_mark) >= self.MARK_POLL_SECONDS:
            self._last_mark_poll_ts[symbol] = now_ts
            try:
                self.cache[symbol].mark_price = float(self.exchange.get_mark_price(symbol))
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

    def get_df_copy(self, symbol):
        if symbol not in self.cache:
            return None
        return self.cache[symbol].df.copy()

    def get_mark_price_cached(self, symbol):
        if symbol not in self.cache:
            return 0.0
        return float(self.cache[symbol].mark_price)

    def get_last_kline_close_age_seconds(self, symbol: str) -> float:
        if symbol not in self.cache:
            return float("inf")

        last_ms = int(self.cache[symbol].last_closed_kline_ms or 0)
        if not last_ms:
            return float("inf")

        return time.time() - (last_ms / 1000.0)
    
    def get_last_atr(self, symbol: str, period: int = None) -> float:
        """
        Calcula el último ATR basado en el dataframe cacheado.
        No modifica el estado interno.
        """

        if symbol not in self.cache:
            return 0.0

        df = self.cache[symbol].df

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
