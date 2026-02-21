import time
from binance.exceptions import BinanceAPIException
import config as CFG

def call_with_retries(func, *args, **kwargs):
    for attempt in range(CFG.MAX_API_RETRIES):
        try:
            return func(*args, **kwargs)
        except BinanceAPIException as e:
            # rate limit / too many requests
            if getattr(e, "code", None) in (-1003, -1015):
                time.sleep(2 ** attempt)
                continue
            raise
        except Exception:
            if attempt == CFG.MAX_API_RETRIES - 1:
                raise
            time.sleep(1.5 ** attempt)
    raise RuntimeError("API call failed after retries")
