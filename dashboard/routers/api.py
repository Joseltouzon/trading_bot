from fastapi import APIRouter, Depends

from dashboard.dependencies import get_db, get_exchange

router = APIRouter(prefix="/api")

@router.get("/stats")
def api_stats(db = Depends(get_db)):
    return {
        "stats": db.get_dashboard_stats(),
        "account": db.get_latest_account_snapshot(),
        "bot_status": db.get_bot_status()
    }

@router.get("/health")
def api_health(exchange = Depends(get_exchange)):
    return exchange.health_check()