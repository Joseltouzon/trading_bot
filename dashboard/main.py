import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request, Form, Body, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

from core.logging_setup import setup_logging
from db import Database
from exchange.binance_futures import BinanceFutures

app = FastAPI()
templates = Jinja2Templates(directory="dashboard/templates")
db = Database()
log = setup_logging(db)

API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

exchange = BinanceFutures(
    api_key=API_KEY,
    api_secret=API_SECRET,
    logger=log,
    testnet=False
)

# ========================= AUTH SOLO PARA "/" =========================

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

# ========================= DASHBOARD =========================

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, auth: str = Depends(verify)):

    stats = db.get_dashboard_stats()
    equity_curve = db.get_equity_curve() or []
    closed_positions = db.get_recent_closed_positions()
    logs = db.get_recent_logs()
    bot_status = db.get_bot_status()
    performance = db.get_performance_metrics()
    max_drawdown = db.calculate_drawdown(equity_curve)
    drawdown_curve = db.get_drawdown_curve(equity_curve)
    state = db.load_state() or {}
    analytics = db.get_trade_analytics()
    open_positions = db.get_open_positions_with_stops() or []

    # ===== Unrealized desde exchange =====
    exchange_positions = exchange.get_open_positions() or []
    exchange_map = {p["symbol"]: p for p in exchange_positions}

    for pos in open_positions:
        symbol = pos["symbol"]
        if symbol in exchange_map:
            pos["unrealized_pnl"] = float(exchange_map[symbol]["unrealized_pnl"])
        else:
            pos["unrealized_pnl"] = 0.0

    # ===== Account snapshot =====
    account = db.get_latest_account_snapshot()

    if not account:
        account = {
            "equity": 0,
            "used_margin": 0,
            "available": 0
        }

    usage_pct = 0
    if account["equity"] > 0:
        usage_pct = round(
            (account["used_margin"] / account["equity"]) * 100,
            2
        )

    # Formateo equity
    for e in equity_curve:
        e["created_at"] = e["created_at"].strftime("%H:%M")
        e["total_balance"] = float(e["total_balance"])

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "stats": stats,
            "equity_curve": equity_curve,
            "open_positions": open_positions,
            "closed_positions": closed_positions,
            "logs": logs,
            "bot_status": bot_status,
            "performance": performance,
            "max_drawdown": max_drawdown,
            "drawdown_curve": drawdown_curve,
            "state": state,
            "account": account,
            "usage_pct": usage_pct,
            "analytics": analytics
        }
    )

# ========================= BOT CONTROL =========================

@app.post("/bot/pause")
def pause_bot():
    state = db.load_state()
    state["paused"] = True
    db.save_state(state)
    return RedirectResponse("/", status_code=303)


@app.post("/bot/resume")
def resume_bot():
    state = db.load_state()
    state["paused"] = False
    db.save_state(state)
    return RedirectResponse("/", status_code=303)


@app.post("/update-config")
async def update_config(payload: dict = Body(...)):

    state = db.load_state()

    allowed_keys = [
        "paused",
        "risk_pct",
        "leverage",
        "max_positions",
        "daily_loss_limit_pct",
        "trailing_pct",
        "adx_min",
        "cooldown_bars",
        "symbols"
    ]

    for key in allowed_keys:
        if key in payload:
            state[key] = payload[key]

    # Validaciones
    if "risk_pct" in payload:
        if payload["risk_pct"] <= 0 or payload["risk_pct"] > 5:
            raise HTTPException(status_code=400, detail="risk_pct inválido")

    if "leverage" in payload:
        if payload["leverage"] < 1 or payload["leverage"] > 50:
            raise HTTPException(status_code=400, detail="leverage inválido")

    db.save_state(state)

    return {"status": "ok"}


@app.get("/api/stats")
def api_stats():
    return {
        "stats": db.get_dashboard_stats(),
        "account": db.get_latest_account_snapshot(),
        "bot_status": db.get_bot_status()
    }


@app.get("/api/health")
def api_health():
    return exchange.health_check()