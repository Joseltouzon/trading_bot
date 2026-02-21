import threading
from typing import Dict, Optional
from core.models import SignalEvent

class SignalBus:
    def __init__(self):
        self._lock = threading.Lock()
        self._latest: Dict[str, SignalEvent] = {}

    def publish(self, ev: SignalEvent):
        with self._lock:
            self._latest[ev.symbol] = ev

    def pop_any(self) -> Optional[SignalEvent]:
        with self._lock:
            if not self._latest:
                return None
            # pop un símbolo arbitrario; podrías hacerlo round-robin si quieres
            sym = next(iter(self._latest.keys()))
            return self._latest.pop(sym)
