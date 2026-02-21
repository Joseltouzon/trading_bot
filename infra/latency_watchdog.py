import time


class LatencyWatchdog:
    def __init__(self, max_delay=10):
        self.max_delay = max_delay
        self.last_update = time.time()

    def ping(self):
        self.last_update = time.time()

    @property
    def stale(self):
        return (time.time() - self.last_update) > self.max_delay
