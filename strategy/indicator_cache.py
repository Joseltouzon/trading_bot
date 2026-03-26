# strategy/indicator_cache.py
# Cache global de indicadores para evitar recálculo

import pandas as pd
from strategy.indicators import ema, atr, adx, rsi, bollinger_bands


class IndicatorCache:
    """Cache de indicadores por símbolo e intervalo.
    
    Los indicadores se calculan una vez por vela cerrada y se reutilizan
    entre estrategias que usen los mismos parámetros.
    """
    
    def __init__(self):
        self._cache = {}  # (symbol, interval, indicator, params) -> Series/value
        self._last_close_time = {}  # (symbol, interval) -> close_time
    
    def _make_key(self, symbol, interval, indicator, params):
        return (symbol, interval, indicator, tuple(sorted(params.items())))
    
    def _is_valid(self, symbol, interval, close_time):
        """Verifica si el cache es válido para esta vela."""
        key = (symbol, interval)
        return self._last_close_time.get(key) == close_time
    
    def _invalidate(self, symbol, interval):
        """Invalida todo el cache para un símbolo/intervalo."""
        keys_to_remove = [k for k in self._cache.keys() 
                         if k[0] == symbol and k[1] == interval]
        for k in keys_to_remove:
            del self._cache[k]
    
    def get_ema(self, df, symbol, interval, period, close_time=None):
        """Obtiene EMA cacheada o la calcula."""
        if close_time is None:
            close_time = int(df["close_time"].iloc[-2])
        
        if not self._is_valid(symbol, interval, close_time):
            self._invalidate(symbol, interval)
            self._last_close_time[(symbol, interval)] = close_time
        
        key = self._make_key(symbol, interval, "ema", {"period": period})
        if key not in self._cache:
            self._cache[key] = ema(df["close"], period)
        return self._cache[key]
    
    def get_atr(self, df, symbol, interval, period=14, close_time=None):
        """Obtiene ATR cacheado o lo calcula."""
        if close_time is None:
            close_time = int(df["close_time"].iloc[-2])
        
        if not self._is_valid(symbol, interval, close_time):
            self._invalidate(symbol, interval)
            self._last_close_time[(symbol, interval)] = close_time
        
        key = self._make_key(symbol, interval, "atr", {"period": period})
        if key not in self._cache:
            self._cache[key] = atr(df, period)
        return self._cache[key]
    
    def get_rsi(self, df, symbol, interval, period=14, close_time=None):
        """Obtiene RSI cacheado o lo calcula."""
        if close_time is None:
            close_time = int(df["close_time"].iloc[-2])
        
        if not self._is_valid(symbol, interval, close_time):
            self._invalidate(symbol, interval)
            self._last_close_time[(symbol, interval)] = close_time
        
        key = self._make_key(symbol, interval, "rsi", {"period": period})
        if key not in self._cache:
            self._cache[key] = rsi(df["close"], period)
        return self._cache[key]
    
    def get_adx(self, df, symbol, interval, period=14, close_time=None):
        """Obtiene ADX cacheado o lo calcula."""
        if close_time is None:
            close_time = int(df["close_time"].iloc[-2])
        
        if not self._is_valid(symbol, interval, close_time):
            self._invalidate(symbol, interval)
            self._last_close_time[(symbol, interval)] = close_time
        
        key = self._make_key(symbol, interval, "adx", {"period": period})
        if key not in self._cache:
            self._cache[key] = adx(df, period)
        return self._cache[key]
    
    def get_bollinger(self, df, symbol, interval, period=20, std_mult=2.0, close_time=None):
        """Obtiene Bollinger Bands cacheadas o las calcula."""
        if close_time is None:
            close_time = int(df["close_time"].iloc[-2])
        
        if not self._is_valid(symbol, interval, close_time):
            self._invalidate(symbol, interval)
            self._last_close_time[(symbol, interval)] = close_time
        
        key = self._make_key(symbol, interval, "bollinger", {"period": period, "std": std_mult})
        if key not in self._cache:
            self._cache[key] = bollinger_bands(df["close"], period, std_mult)
        return self._cache[key]


# Instancia global
indicator_cache = IndicatorCache()
