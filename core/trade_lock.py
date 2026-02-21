# core/trade_lock.py

import time
import threading
from dataclasses import dataclass


@dataclass
class TradeLockState:
    last_entry_ts: float = 0.0
    last_bar_close_ms: int = 0


class TradeLock:
    """
    Lock por símbolo para evitar dobles entradas por:
    - reconexión WS
    - duplicación de evento
    - race conditions
    """

    def __init__(self, min_seconds_between_entries: int = 45):
        self.min_seconds = int(min_seconds_between_entries)
        self._lock = threading.Lock()
        self._states: dict[str, TradeLockState] = {}

    def can_enter(self, symbol: str, bar_close_ms: int) -> bool:
        now = time.time()
        with self._lock:
            st = self._states.get(symbol)
            if st is None:
                return True

            # Ya operaste esta vela cerrada
            if bar_close_ms and st.last_bar_close_ms == int(bar_close_ms):
                return False

            # Operaste hace poco
            if (now - st.last_entry_ts) < self.min_seconds:
                return False

            return True

    def mark_entered(self, symbol: str, bar_close_ms: int):
        now = time.time()
        with self._lock:
            st = self._states.get(symbol)
            if st is None:
                st = TradeLockState()
                self._states[symbol] = st

            st.last_entry_ts = now
            if bar_close_ms:
                st.last_bar_close_ms = int(bar_close_ms)
