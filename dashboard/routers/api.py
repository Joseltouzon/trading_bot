from fastapi import APIRouter, Depends

from dashboard.dependencies import get_db, get_exchange, get_exchange_cache

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

@router.get("/cache-health")
def api_cache_health(exchange_cache = Depends(get_exchange_cache)):
    return exchange_cache.get_cache_health() 

@router.get("/timeframe")
def api_timeframe(db = Depends(get_db)):
    """
    Devuelve el timeframe actual configurado en el bot.
    Útil para mostrar en el frontend sin recargar la página.
    """
    state = db.load_state()
    timeframe = state.get("timeframe", "5m")  # Default a 5m si no está configurado
    
    # Validar que sea un timeframe soportado
    valid_tfs = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"]
    if timeframe not in valid_tfs:
        timeframe = "5m"  # Fallback seguro
    
    return {
        "timeframe": timeframe,
        "timeframe_display": _format_timeframe_display(timeframe)
    }

def _format_timeframe_display(tf: str) -> str:
    """
    Convierte '5m' -> '5 minutos', '1h' -> '1 hora', etc.
    Para mostrar en el frontend de forma amigable.
    """
    mapping = {
        "1m": "1 minuto",
        "3m": "3 minutos",
        "5m": "5 minutos",
        "15m": "15 minutos",
        "30m": "30 minutos",
        "1h": "1 hora",
        "2h": "2 horas",
        "4h": "4 horas",
        "6h": "6 horas",
        "12h": "12 horas",
        "1d": "1 día"
    }
    return mapping.get(tf, tf)       