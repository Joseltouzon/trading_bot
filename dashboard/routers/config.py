from fastapi import APIRouter, Body, Depends, HTTPException

from dashboard.dependencies import get_db

router = APIRouter()

@router.post("/update-config")
async def update_config(payload: dict = Body(...), db = Depends(get_db)):
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
        "symbols",
        "timeframe",
        "pivot_len",      
        "paper_trading",
        "ema_slow",
        "ema_fast",
        "trailing_automatico",
        "adx_rising",
        "vol_min_ratio",
        "trailing_active",
    ]
    for key in allowed_keys:
        if key in payload:
            # Validación para timeframe
            if key == "timeframe":
                valid_timeframes = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"]
                if payload["timeframe"] not in valid_timeframes:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Timeframe inválido. Opciones: {', '.join(valid_timeframes)}"
                    )

            if key == "pivot_len":
                val = payload["pivot_len"]
                if not isinstance(val, int) or val < 5 or val > 50:
                    raise HTTPException(
                        status_code=400,
                        detail="pivot_len inválido (debe ser entero entre 5 y 50)"
                    )
            
            if key == "paper_trading":
                payload["paper_trading"] = bool(payload["paper_trading"])

            if key == "trailing_automatico":
                payload["trailing_automatico"] = bool(payload["trailing_automatico"])

            if key == "adx_rising":
                payload["adx_rising"] = bool(payload["adx_rising"])    

            if key == "risk_pct":
                if payload["risk_pct"] <= 0 or payload["risk_pct"] > 10:
                    raise HTTPException(status_code=400, detail="risk_pct inválido (0.1-10)")
            if key == "leverage":
                if payload["leverage"] < 1 or payload["leverage"] > 50:
                    raise HTTPException(status_code=400, detail="leverage inválido (1-50)")
            
            state[key] = payload[key]
    
    db.save_state(state)
    return {"status": "ok"}