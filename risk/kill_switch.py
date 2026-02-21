import time


class KillSwitch:
    def __init__(self, max_errors=5, cooldown_seconds=300):
        self.errors = 0
        self.max_errors = max_errors
        self.cooldown_seconds = cooldown_seconds
        self.triggered_until = None

    @property
    def triggered(self):
        if self.triggered_until is None:
            return False
        return time.time() < self.triggered_until

    def register_error(self):
        self.errors += 1
        if self.errors >= self.max_errors:
            self.triggered_until = time.time() + self.cooldown_seconds
            self.errors = 0

    def reset(self):
        self.errors = 0
