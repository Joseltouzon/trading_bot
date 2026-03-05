# Script rápido para chequear correlación 30 días
import pandas as pd
import ccxt

exchange = ccxt.binance()
symbols = ["BTCUSDT", "LINKUSDT", "ATOMUSDT", "SOLUSDT"]  # agregá los que quieras testear
timeframe = "1h"
limit = 720  # ~30 días

data = {}
for symbol in symbols:
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["time", "open", "high", "low", "close", "volume"])
    data[symbol] = df["close"].pct_change().dropna()

corr_matrix = pd.DataFrame(data).corr()
print(corr_matrix["BTCUSDT"].sort_values())