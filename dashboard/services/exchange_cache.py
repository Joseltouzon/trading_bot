import threading
import time

class ExchangeCache:

    def __init__(self, exchange, refresh_interval=10):
        self.exchange = exchange
        self.refresh_interval = refresh_interval
        self._open_positions = []
        self._running = False

    def start(self):
        if self._running:
            return

        self._running = True
        thread = threading.Thread(target=self._loop, daemon=True)
        thread.start()

    def _loop(self):
        while self._running:
            try:
                self._open_positions = self.exchange.get_open_positions() or []
            except Exception:
                pass

            time.sleep(self.refresh_interval)

    def get_open_positions(self):
        return self._open_positions