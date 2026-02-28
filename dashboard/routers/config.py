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
        "timeframe"
    ]

    for key in allowed_keys:
        if key in payload:
            # Validación específica para timeframe
            if key == "timeframe":
                valid_timeframes = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"]
                if payload["timeframe"] not in valid_timeframes:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"timeframe inválido. Opciones: {', '.join(valid_timeframes)}"
                    )
            state[key] = payload[key]

        if "risk_pct" in payload:
            if payload["risk_pct"] <= 0 or payload["risk_pct"] > 5:
                raise HTTPException(status_code=400, detail="risk_pct inválido")

        if "leverage" in payload:
            if payload["leverage"] < 1 or payload["leverage"] > 50:
                raise HTTPException(status_code=400, detail="leverage inválido")

    db.save_state(state)

    return {"status": "ok"}