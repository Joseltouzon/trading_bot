from fastapi import APIRouter, Depends

from dashboard.dependencies import get_db, get_exchange

router = APIRouter(prefix="/api")

@router.get("/stats")
def api_stats(db = Depends(get_db)):

    stats = db.get_dashboard_stats() or {}
    account = db.get_latest_account_snapshot() or {}
    bot_status = db.get_bot_status() or "UNKNOWN"

    return {
        "stats": {
            "daily_pnl": stats.get("daily_pnl", 0),
            **stats
        },
        "account": {
            "equity": account.get("equity", 0),
            **account
        },
        "bot_status": bot_status
    }

@router.get("/health")
def api_health(exchange = Depends(get_exchange)):
    return exchange.health_check()

@router.get("/open-positions/pnl")
def api_open_positions_pnl(
    db = Depends(get_db),
    exchange = Depends(get_exchange)
):
    open_positions = db.get_open_positions_with_stops() or []

    exchange_positions = exchange.get_open_positions()
    exchange_map = {p["symbol"]: p for p in exchange_positions}

    return {
        pos["symbol"]: float(
            exchange_map.get(pos["symbol"], {}).get("unrealized_pnl", 0)
        )
        for pos in open_positions
    }