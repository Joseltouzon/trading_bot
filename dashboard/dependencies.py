import os
from dotenv import load_dotenv
load_dotenv()

import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from db import Database
from dashboard.services.exchange_cache import ExchangeCache
from exchange.binance_futures import BinanceFutures
from core.logging_setup import setup_logging

# =======================
# SHARED INSTANCES
# =======================

db_instance = Database()
logger_instance = setup_logging(db_instance)

exchange_instance = BinanceFutures(
    api_key=os.getenv("BINANCE_API_KEY"),
    api_secret=os.getenv("BINANCE_API_SECRET"),
    logger=logger_instance,
    testnet=False
)

exchange_cache = ExchangeCache(exchange_instance, refresh_interval=10)
exchange_cache.start()

# =======================
# DEPENDENCIES
# =======================

def get_exchange_cache():
    return exchange_cache

def get_db():
    return db_instance

def get_exchange():
    return exchange_instance

# =======================
# AUTH
# =======================

security = HTTPBasic()

def verify(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = "tuvieja"
    correct_password = os.getenv("DASHBOARD_PASSWORD")

    if not correct_password:
        return

    is_correct_username = secrets.compare_digest(
        credentials.username,
        correct_username
    )

    is_correct_password = secrets.compare_digest(
        credentials.password,
        correct_password
    )

    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect credentials",
            headers={"WWW-Authenticate": "Basic"},
        )