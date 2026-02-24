import time
import threading
import config as CFG
from infra.retry import call_with_retries

class RateLimiter:
    def __init__(self, max_calls_per_window: int, window_seconds: int):
        self.max_calls = max_calls_per_window
        self.window = window_seconds
        self._lock = threading.Lock()
        self._count = 0
        self._last_reset = time.time()

    def _maybe_reset(self):
        now = time.time()
        if now - self._last_reset > self.window:
            self._count = 0
            self._last_reset = now

    def call(self, func, *args, **kwargs):
        with self._lock:
            self._maybe_reset()
            if self._count >= self.max_calls:
                sleep_time = self.window - (time.time() - self._last_reset)
                if sleep_time > 0:
                    time.sleep(sleep_time + 1)
                self._count = 0
                self._last_reset = time.time()
            self._count += 1

        return call_with_retries(func, *args, **kwargs)

_default_limiter = RateLimiter(CFG.MAX_API_CALLS_PER_MIN, CFG.RATE_LIMIT_WINDOW)

def api_call(func, *args, **kwargs):
    return _default_limiter.call(func, *args, **kwargs)
