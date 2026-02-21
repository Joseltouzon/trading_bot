import time


class APICache:
    def __init__(self, ttl=2):
        self.ttl = ttl
        self.store = {}

    def get(self, key, fetch_fn):
        now = time.time()
        if key in self.store:
            value, ts = self.store[key]
            if now - ts < self.ttl:
                return value

        value = fetch_fn()
        self.store[key] = (value, now)
        return value
