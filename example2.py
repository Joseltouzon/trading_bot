from binance.client import Client
from binance.exceptions import BinanceAPIException

API_KEY='xxxxxxxxxxxxx'
API_SECRET='xxxxxxxxxxxx'

c = Client(API_KEY, API_SECRET)


print(c.futures_account())
