from fastapi import APIRouter, Depends, Response, Query
from dashboard.dependencies import get_db, get_exchange, get_exchange_cache
import csv
import io
from datetime import datetime

router = APIRouter(prefix="/api")

@router.get("/stats")
def api_stats(db = Depends(get_db), exchange = Depends(get_exchange)):
    stats = db.get_dashboard_stats() or {}
    account = db.get_latest_account_snapshot() or {}
    bot_status = db.get_bot_status() or "UNKNOWN"
    
    # 🆕 Obtener PnL real de Binance
    try:
        binance_pnl = exchange.get_daily_realized_pnl()
    except Exception:
        binance_pnl = stats.get("daily_pnl", 0)  # Fallback a DB
    
    return {
        "stats": {
            "daily_pnl": stats.get("daily_pnl", 0),      # DB value (backup)
            "daily_pnl_binance": round(binance_pnl, 2),  # ✅ Binance real
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
    """
    Devuelve unrealized PnL + Mark Price + PnL % para cada posición abierta.
    """
    open_positions = db.get_open_positions_with_stops() or []
    exchange_positions = exchange.get_open_positions()
    exchange_map = {p["symbol"]: p for p in exchange_positions}
    
    result = {}
    for pos in open_positions:
        symbol = pos["symbol"]
        ex_pos = exchange_map.get(symbol, {})
        
        # ✅ Obtener entry_price de la DB (fuente de verdad)
        entry_price = float(pos.get("entry_price") or 0)
        if entry_price <= 0:
            # Si no hay entry válido, omitir este símbolo
            continue
        
        # ✅ Obtener Mark Price actual (con fallback seguro)
        try:
            mark_price = float(exchange.get_mark_price(symbol))
        except Exception:
            mark_price = 0.0
        
        # ✅ Usar side de la DB, no del exchange (más confiable)
        side = pos.get("side", "LONG")
        
        # Calcular PnL % con validación
        if entry_price > 0 and mark_price > 0:
            if side == "LONG":
                pnl_pct = (mark_price - entry_price) / entry_price * 100
            else:  # SHORT
                pnl_pct = (entry_price - mark_price) / entry_price * 100
        else:
            pnl_pct = 0.0   
        
        result[symbol] = {
            "unrealized_pnl": float(ex_pos.get("unrealized_pnl", 0) or 0),
            "mark_price": mark_price,
            "pnl_pct": round(pnl_pct, 2),
            "entry_price": entry_price  # ← Útil para debug/frontend
        }
    
    return result  

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

@router.get("/export/trades")
def api_export_trades(
    db = Depends(get_db),
    format: str = "csv",  # Por ahora solo CSV, pero deja puerta abierta a JSON
    start_date: str = Query(None, description="YYYY-MM-DD"),
    end_date: str = Query(None, description="YYYY-MM-DD"),
    symbol: str = Query(None, description="Filtrar por símbolo")
):
    """
    Exporta historial de trades cerrados en formato CSV.
    Incluye: symbol, side, entry/exit, PnL, fechas, hold time, etc.
    """
    if format != "csv":
        return {"error": "Formato no soportado. Usá ?format=csv"}
    
    # Obtener trades cerrados con todos los campos útiles
    trades = db.get_recent_closed_positions(limit=None)  # None = todos

    # Filtrar por fechas si se proporcionan
    if start_date or end_date or symbol:
        trades = db.get_closed_positions_filtered(
            start_date=start_date,
            end_date=end_date,
            symbol=symbol
        )
    else:
        trades = db.get_recent_closed_positions(limit=None)
    
    # Crear buffer en memoria para el CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header del CSV
    writer.writerow([
        "id",
        "symbol",
        "side",
        "entry_price",
        "exit_price",
        "qty",
        "realized_pnl",
        "pnl_pct",
        "opened_at",
        "closed_at",
        "hold_hours",
        "close_reason"
    ])
    
    # Filas de datos
    for t in trades:
        # Calcular hold time en horas
        hold_hours = None
        if t.get("opened_at") and t.get("closed_at"):
            delta = t["closed_at"] - t["opened_at"]
            hold_hours = round(delta.total_seconds() / 3600, 2)
        
        # Calcular PnL % respecto al entry
        pnl_pct = None
        if t.get("entry_price") and t.get("entry_price") != 0:
            pnl_pct = round(
                ((t["exit_price"] - t["entry_price"]) / t["entry_price"]) * 100 
                if t["side"] == "LONG" 
                else ((t["entry_price"] - t["exit_price"]) / t["entry_price"]) * 100,
                2
            )
        
        writer.writerow([
            t.get("id", ""),
            t.get("symbol", ""),
            t.get("side", ""),
            t.get("entry_price", ""),
            t.get("exit_price", ""),
            t.get("qty", ""),
            round(float(t.get("realized_pnl", 0) or 0), 2),
            pnl_pct,
            t.get("opened_at", "").strftime("%Y-%m-%d %H:%M:%S") if t.get("opened_at") else "",
            t.get("closed_at", "").strftime("%Y-%m-%d %H:%M:%S") if t.get("closed_at") else "",
            hold_hours,
            t.get("close_reason", "")
        ])
    
    # Preparar respuesta HTTP con headers de descarga
    filename = f"beast_trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )  

@router.get("/analytics")
def api_analytics(
    db = Depends(get_db),
    start_date: str = None,
    end_date: str = None,
    symbol: str = None
):
    """
    Devuelve analytics de trades con filtros opcionales.
    Útil para actualizar la tabla sin recargar toda la página.
    """
    analytics = db.get_trade_analytics(
        start_date=start_date,
        end_date=end_date,
        symbol=symbol
    )
    
    # Formatear para JSON (Decimal → float, datetime → string)
    result = []
    for row in analytics:
        result.append({
            "symbol": row["symbol"],
            "total_trades": int(row["total_trades"] or 0),
            "total_pnl": float(row["total_pnl"] or 0),
            "best_trade": float(row["best_trade"] or 0),
            "worst_trade": float(row["worst_trade"] or 0),
            "avg_hold_hours": round(float(row["avg_hold_hours"] or 0), 2)
        })
    
    return {"analytics": result}

@router.get("/closed-positions")
def api_closed_positions(
    db = Depends(get_db),
    limit: int = 50,
    start_date: str = None,
    end_date: str = None,
    symbol: str = None
):
    """
    Devuelve posiciones cerradas con filtros opcionales.
    Útil para actualizar la tabla sin recargar toda la página.
    """
    positions = db.get_recent_closed_positions_filtered(
        limit=limit if limit > 0 else None,
        start_date=start_date,
        end_date=end_date,
        symbol=symbol
    )
    
    # Formatear para JSON
    result = []
    for pos in positions:
        result.append({
            "symbol": pos["symbol"],
            "side": pos["side"],
            "entry_price": float(pos["entry_price"] or 0),
            "exit_price": float(pos["exit_price"] or 0),
            "realized_pnl": float(pos["realized_pnl"] or 0),
            "commission": float(pos["commission"] or 0),
            "closed_at": pos["closed_at"].strftime("%Y-%m-%d %H:%M:%S") if pos["closed_at"] else None
        })
    
    return {"positions": result}

@router.post("/positions/{symbol}/close")
def api_close_position(
    symbol: str,
    exchange = Depends(get_exchange),
    db = Depends(get_db)
):
    """
    Cierra una posición abierta al mercado.
    Retorna el resultado de la operación.
    """
    try:
        # Verificar que la posición existe y está abierta
        open_positions = db.get_open_positions_with_stops()
        position = next((p for p in open_positions if p["symbol"] == symbol), None)
        
        if not position:
            raise HTTPException(status_code=404, detail=f"Posición {symbol} no encontrada o ya cerrada")
        
        # Ejecutar cierre en Binance
        result = exchange.close_position(symbol)
        
        # Registrar evento en DB (opcional, para auditoría)
        db.create_position_event(
            position_id=position["id"],
            event_type="MANUAL_CLOSE",
            payload={"triggered_by": "dashboard", "timestamp": time.time()}
        )
        
        return {
            "status": "ok",
            "message": f"Posición {symbol} cerrada correctamente",
            "symbol": symbol
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al cerrar posición: {str(e)}")

@router.get("/daily-pnl")
def api_daily_pnl(
    db = Depends(get_db),
    days: int = 30  # Default: último mes
):
    """
    Devuelve PnL diario para el calendario de performance.
    
    Query params:
        days: int (opcional) - Cantidad de días hacia atrás (max 90)
    """
    # Limitar a 90 días para no sobrecargar
    days = min(max(days, 1), 90)
    
    daily_pnl = db.get_daily_pnl_calendar(days=days)
    
    # Calcular resumen para el frontend
    total_pnl = sum(d["pnl_usdt"] for d in daily_pnl)
    total_trades = sum(d["trades"] for d in daily_pnl)
    total_wins = sum(d["wins"] for d in daily_pnl)
    
    return {
        "daily_pnl": daily_pnl,
        "summary": {
            "total_pnl": round(total_pnl, 2),
            "total_trades": total_trades,
            "win_rate": round((total_wins / total_trades * 100), 2) if total_trades > 0 else 0,
            "avg_pnl_per_day": round(total_pnl / len(daily_pnl), 2) if daily_pnl else 0,
            "best_day": max(daily_pnl, key=lambda x: x["pnl_usdt"]) if daily_pnl else None,
            "worst_day": min(daily_pnl, key=lambda x: x["pnl_usdt"]) if daily_pnl else None
        }
    }