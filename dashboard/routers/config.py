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
        "strategy_mode",
        # Trailing runtime
        "trailing_activation_pct",
        "trailing_use_atr",
        "trailing_atr_mult",
        # Take Profit
        "use_take_profit",
        "tp_by_pct",
        "tp_activation_pct",
        "tp_close_pct",
        "tp_sl_mode",
        # Stop Hunt
        "stop_hunt_wick_pct",
        "stop_hunt_rejection_ratio",
        "stop_hunt_min_zones",
        "stop_hunt_max_zone_distance_pct",
        "stop_hunt_sl_pct",
        "stop_hunt_min_volume_ratio",
        "stop_hunt_use_ema_filter",
        "stop_hunt_min_break_candles",
        "stop_hunt_atr_mult_sl",
        "stop_hunt_momentum_bars",
        "stop_hunt_min_atr_pct",
        "stop_hunt_adx_min",
        "order_block_lookback",
        # RSI + Bollinger Band
        "rsi_bb_rsi_period",
        "rsi_bb_oversold",
        "rsi_bb_overbought",
        "rsi_bb_bb_period",
        "rsi_bb_bb_std_mult",
        "rsi_bb_stoch_period",
        "rsi_bb_divergence_lookback",
        "rsi_bb_band_tolerance_pct",
        "rsi_bb_min_volume_ratio",
        "rsi_bb_adx_min",
        "rsi_bb_min_atr_pct",
        "rsi_bb_sl_atr_mult",
        "rsi_bb_sl_pct",
        "rsi_bb_require_divergence",
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

            # Validación para strategy_mode
            if key == "strategy_mode":
                valid_strategies = ["ema_breakout", "stop_hunt", "rsi_bb_reversion", "macd_momentum", "auto"]
                if payload["strategy_mode"] not in valid_strategies:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Estrategia inválida. Opciones: {', '.join(valid_strategies)}"
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

            if key in ("paper_trading", "trailing_automatico", "adx_rising",
                        "trailing_use_atr", "use_take_profit", "tp_by_pct",
                        "stop_hunt_use_ema_filter", "rsi_bb_require_divergence"):
                payload[key] = bool(payload[key])

            if key == "tp_sl_mode":
                valid = ["trailing", "entry"]
                if payload["tp_sl_mode"] not in valid:
                    raise HTTPException(status_code=400, detail="tp_sl_mode inválido")

            state[key] = payload[key]
    
    db.save_state(state)
    return {"status": "ok"}