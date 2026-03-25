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
        "strategy_symbols",
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
        # EMA Breakout v2
        "ema_breakout_fast",
        "ema_breakout_slow",
        "ema_min_slope_pct",
        "ema_rsi_period",
        "ema_rsi_oversold",
        "ema_rsi_overbought",
        "ema_min_volume_ratio",
        "ema_min_atr_pct",
        "ema_momentum_bars",
        "ema_min_momentum_pct",
        "ema_breakout_lookback",
        "ema_pullback_atr_mult",
        "ema_max_pullback_atr_mult",
        "ema_sl_atr_mult",
        "ema_sl_pct",
        "ema_min_body_ratio",
        "ema_min_pivot_distance_pct",
        "ema_min_break_distance_pct",
        "ema_max_pivot_age",
        # MACD Momentum
        "macd_fast",
        "macd_slow",
        "macd_signal",
        "macd_min_volume_ratio",
        "macd_rsi_period",
        "macd_rsi_bull_min",
        "macd_rsi_bear_max",
        "macd_adx_min",
        "macd_min_atr_pct",
        "macd_structure_lookback",
        "macd_sl_atr_mult",
        # Structure Break
        "structure_swing_window",
        "structure_lookback",
        "structure_break_lookback",
        "structure_retest_lookback",
        "structure_retest_tolerance_atr",
        "structure_min_break_volume",
        "structure_sl_buffer_atr",
        "structure_adx_min",
        # Volatility Squeeze (1h)
        "vol_squeeze_atr_period",
        "vol_squeeze_atr_lookback",
        "vol_squeeze_atr_percentile",
        "vol_squeeze_bb_period",
        "vol_squeeze_bb_width_percentile",
        "vol_squeeze_rsi_period",
        "vol_squeeze_rsi_oversold",
        "vol_squeeze_rsi_overbought",
        "vol_squeeze_min_volume_ratio",
        "vol_squeeze_adx_min",
        "vol_squeeze_sl_atr_mult",
        "vol_squeeze_tp_atr_mult",
        "vol_squeeze_ema_fast",
        "vol_squeeze_ema_slow",
        # Volatility Regime (1h)
        "vr_atr_period",
        "vr_atr_lookback",
        "vr_atr_low_percentile",
        "vr_atr_high_percentile",
        "vr_volume_ratio_min",
        "vr_rsi_period",
        "vr_adx_min",
        "vr_sl_atr_mult",
        "vr_ema_fast",
        "vr_ema_slow",
        "vr_momentum_bars",
        "vr_breakout_lookback",
        # Estrategias activas (toggles)
        "strategy_enabled_rsi_bb",
        "strategy_enabled_stop_hunt",
        "strategy_enabled_macd",
        "strategy_enabled_ema",
        "strategy_enabled_structure",
        "strategy_enabled_vol_squeeze",
        "strategy_enabled_vol_regime",
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
                valid_strategies = ["ema_breakout", "stop_hunt", "rsi_bb_reversion", "macd_momentum", "structure_break", "volatility_squeeze", "auto"]
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

            if key == "strategy_symbols":
                val = payload["strategy_symbols"]
                if isinstance(val, dict):
                    # Convertir strings separados por coma a listas
                    cleaned = {}
                    for strat, syms_str in val.items():
                        if isinstance(syms_str, str):
                            cleaned[strat] = [s.strip().upper() for s in syms_str.split(",") if s.strip()]
                        elif isinstance(syms_str, list):
                            cleaned[strat] = syms_str
                    payload["strategy_symbols"] = cleaned    

            if key == "risk_pct":
                if payload["risk_pct"] <= 0 or payload["risk_pct"] > 10:
                    raise HTTPException(status_code=400, detail="risk_pct inválido (0.1-10)")
            if key == "leverage":
                if payload["leverage"] < 1 or payload["leverage"] > 50:
                    raise HTTPException(status_code=400, detail="leverage inválido (1-50)")

            if key in ("paper_trading", "trailing_automatico", "adx_rising",
                        "trailing_use_atr", "use_take_profit", "tp_by_pct",
                        "stop_hunt_use_ema_filter", "rsi_bb_require_divergence",
                        "strategy_enabled_rsi_bb", "strategy_enabled_stop_hunt",
                        "strategy_enabled_macd", "strategy_enabled_ema",
                        "strategy_enabled_structure", "strategy_enabled_vol_squeeze",
                        "strategy_enabled_vol_regime"):
                payload[key] = bool(payload[key])

            if key == "tp_sl_mode":
                valid = ["trailing", "entry"]
                if payload["tp_sl_mode"] not in valid:
                    raise HTTPException(status_code=400, detail="tp_sl_mode inválido")

            state[key] = payload[key]
    
    db.save_state(state)
    return {"status": "ok"}