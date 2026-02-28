# dashboard/dependencies.py
import os
from typing import Optional
from dotenv import load_dotenv
load_dotenv()
import secrets
from fastapi import Depends, HTTPException, status, Request, Response, Form
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
# SESSION SECURITY (NUEVO)
# =======================
# Este token se genera AL INICIAR el servidor. Si reinicias el bot, cambia.
SERVER_SESSION_TOKEN = secrets.token_urlsafe(32) 
CORRECT_PASSWORD = os.getenv("DASHBOARD_PASSWORD")

class SessionUser:
    """Objeto ligero para representar la sesión"""
    def __init__(self, token: str):
        self.token = token
        self.is_authenticated = True

def verify_session(request: Request) -> Optional[SessionUser]:
    token_cookie = request.cookies.get("auth_token")
    if not token_cookie or not secrets.compare_digest(token_cookie, SERVER_SESSION_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"}
        )
    return SessionUser(token_cookie) 

# =======================
# DEPENDENCIES
# =======================
def get_exchange_cache():
    return exchange_cache

def get_db():
    return db_instance

def get_exchange():
    return exchange_instance