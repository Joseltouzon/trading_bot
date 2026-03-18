# -*- coding: utf-8 -*-
# bot.py
import os
import time
from dotenv import load_dotenv
load_dotenv()
import config as CFG
from db import Database
from core.logging_setup import setup_logging
from core.models import BotState
from core.utils import utc_day_key
from notifications.telegram import Telegram
from exchange.binance_futures import BinanceFutures
from datafeed.market_cache import MarketCache
from execution.signal_bus import SignalBus
from execution.order_manager import OrderManager
from execution.trailing import TrailingManager
from execution.event_loop import EventLoop
from strategy.signal_engine import SignalEngine
from core.risk_monitor import RiskMonitor


def validate_config():
    if CFG.EMA_FAST >= CFG.EMA_SLOW:
        raise RuntimeError("EMA_FAST debe ser menor que EMA_SLOW")
    if CFG.DEFAULT_RISK_PCT > CFG.MAX_RISK_PCT_ALLOWED:
        raise RuntimeError("DEFAULT_RISK_PCT inválido")
    if CFG.MAX_OPEN_POSITIONS < 1:
        raise RuntimeError("MAX_OPEN_POSITIONS inválido")


def sync_cfg_from_state(st):
    """Sincronizar config.py (runtime) con valores de BotState (DB/dashboard)."""
    CFG.TRAILING_ACTIVATION_PCT = float(getattr(st, "trailing_activation_pct", CFG.TRAILING_ACTIVATION_PCT))
    CFG.TRAILING_USE_ATR = bool(getattr(st, "trailing_use_atr", CFG.TRAILING_USE_ATR))
    CFG.TRAILING_ATR_MULT = float(getattr(st, "trailing_atr_mult", CFG.TRAILING_ATR_MULT))
    CFG.USE_TAKE_PROFIT = bool(getattr(st, "use_take_profit", CFG.USE_TAKE_PROFIT))
    CFG.TP_BY_PCT = bool(getattr(st, "tp_by_pct", CFG.TP_BY_PCT))
    CFG.TP_ACTIVATION_PCT = float(getattr(st, "tp_activation_pct", CFG.TP_ACTIVATION_PCT))
    CFG.TP_CLOSE_PCT = float(getattr(st, "tp_close_pct", CFG.TP_CLOSE_PCT))
    CFG.TP_SL_MODE = str(getattr(st, "tp_sl_mode", CFG.TP_SL_MODE))
    CFG.TP_USE_MARK_PRICE = bool(getattr(st, "tp_use_mark", CFG.TP_USE_MARK_PRICE))
    CFG.STOP_HUNT_WICK_PCT = float(getattr(st, "stop_hunt_wick_pct", CFG.STOP_HUNT_WICK_PCT))
    CFG.STOP_HUNT_REJECTION_RATIO = float(getattr(st, "stop_hunt_rejection_ratio", CFG.STOP_HUNT_REJECTION_RATIO))
    CFG.STOP_HUNT_MIN_ZONES = int(getattr(st, "stop_hunt_min_zones", CFG.STOP_HUNT_MIN_ZONES))
    CFG.STOP_HUNT_MAX_ZONE_DISTANCE_PCT = float(getattr(st, "stop_hunt_max_zone_distance_pct", CFG.STOP_HUNT_MAX_ZONE_DISTANCE_PCT))
    CFG.STOP_HUNT_SL_PCT = float(getattr(st, "stop_hunt_sl_pct", CFG.STOP_HUNT_SL_PCT))
    CFG.STOP_HUNT_MIN_VOLUME_RATIO = float(getattr(st, "stop_hunt_min_volume_ratio", CFG.STOP_HUNT_MIN_VOLUME_RATIO))
    CFG.STOP_HUNT_USE_EMA_FILTER = bool(getattr(st, "stop_hunt_use_ema_filter", CFG.STOP_HUNT_USE_EMA_FILTER))
    CFG.STOP_HUNT_MIN_BREAK_CANDLES = int(getattr(st, "stop_hunt_min_break_candles", CFG.STOP_HUNT_MIN_BREAK_CANDLES))
    CFG.STOP_HUNT_ATR_MULT_SL = float(getattr(st, "stop_hunt_atr_mult_sl", CFG.STOP_HUNT_ATR_MULT_SL))
    CFG.STOP_HUNT_MOMENTUM_BARS = int(getattr(st, "stop_hunt_momentum_bars", CFG.STOP_HUNT_MOMENTUM_BARS))
    CFG.STOP_HUNT_MIN_ATR_PCT = float(getattr(st, "stop_hunt_min_atr_pct", CFG.STOP_HUNT_MIN_ATR_PCT))
    CFG.STOP_HUNT_ADX_MIN = float(getattr(st, "stop_hunt_adx_min", CFG.STOP_HUNT_ADX_MIN))
    CFG.ORDER_BLOCK_LOOKBACK = int(getattr(st, "order_block_lookback", CFG.ORDER_BLOCK_LOOKBACK))

    CFG.VWAP_STD_MULT = float(getattr(st, "vwap_std_mult", CFG.VWAP_STD_MULT))
    CFG.VWAP_MIN_VOLUME_RATIO = float(getattr(st, "vwap_min_volume_ratio", CFG.VWAP_MIN_VOLUME_RATIO))
    CFG.VWAP_SL_ATR_MULT = float(getattr(st, "vwap_sl_atr_mult", CFG.VWAP_SL_ATR_MULT))
    CFG.VWAP_MAX_DEVIATION_PCT = float(getattr(st, "vwap_max_deviation_pct", CFG.VWAP_MAX_DEVIATION_PCT))

    CFG.REGIME_TRENDING_ADX_MIN = float(getattr(st, "regime_trending_adx_min", CFG.REGIME_TRENDING_ADX_MIN))
    CFG.REGIME_RANGING_ADX_MAX = float(getattr(st, "regime_ranging_adx_max", CFG.REGIME_RANGING_ADX_MAX))
    CFG.REGIME_HUNT_VOL_RATIO_MIN = float(getattr(st, "regime_hunt_vol_ratio_min", CFG.REGIME_HUNT_VOL_RATIO_MIN))


def main():
    validate_config()
    API_KEY = os.getenv("BINANCE_API_KEY")
    API_SECRET = os.getenv("BINANCE_API_SECRET")
    TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    PAPER_TRADING = os.getenv("PAPER_TRADING", "false").lower() == "true"

    # ================= DATABASE =================
    db = Database()

    # ================= LOGGING =================
    log = setup_logging(db)

    # ================= TELEGRAM =================
    telegram = Telegram(TG_TOKEN, TG_CHAT_ID, log, db)

    # ================= BINANCE =================
    exchange = BinanceFutures(
        api_key=API_KEY,
        api_secret=API_SECRET,
        logger=log,
        testnet=getattr(CFG, "TESTNET", False)
    )

    # ================= STATE =================
    defaults = BotState(
        paused=False,
        risk_pct=CFG.DEFAULT_RISK_PCT,
        leverage=CFG.DEFAULT_LEVERAGE,
        symbols=CFG.SYMBOLS.copy(),
        trailing_pct=CFG.TRAILING_PCT,
        trailing_automatico=CFG.TRAILING_USE_ATR,
        max_positions=CFG.MAX_OPEN_POSITIONS,
        adx_min=CFG.DEFAULT_ADX_MIN,
        adx_rising=CFG.REQUIRE_ADX_RISING,
        cooldown_bars=CFG.DEFAULT_COOLDOWN_BARS,
        daily_loss_limit_pct=CFG.DEFAULT_DAILY_LOSS_LIMIT_PCT,
        paper_trading=PAPER_TRADING,
        timeframe=CFG.INTERVAL,
        pivot_len=CFG.PIVOT_LEN,
        ema_slow=CFG.EMA_SLOW,
        ema_fast=CFG.EMA_FAST,
        vol_min_ratio=CFG.VOLUME_MIN_RATIO,
        trailing_active=CFG.TRAILING_ACTIVATION_PCT,
        strategy_mode="ema_breakout",
        # Trailing runtime
        trailing_activation_pct=CFG.TRAILING_ACTIVATION_PCT,
        trailing_use_atr=CFG.TRAILING_USE_ATR,
        trailing_atr_mult=CFG.TRAILING_ATR_MULT,
        # Take Profit
        use_take_profit=CFG.USE_TAKE_PROFIT,
        tp_by_pct=CFG.TP_BY_PCT,
        tp_activation_pct=CFG.TP_ACTIVATION_PCT,
        tp_close_pct=CFG.TP_CLOSE_PCT,
        tp_sl_mode=CFG.TP_SL_MODE,
        tp_use_mark=CFG.TP_USE_MARK_PRICE,
        # Stop Hunt
        stop_hunt_wick_pct=CFG.STOP_HUNT_WICK_PCT,
        stop_hunt_rejection_ratio=CFG.STOP_HUNT_REJECTION_RATIO,
        stop_hunt_min_zones=CFG.STOP_HUNT_MIN_ZONES,
        stop_hunt_max_zone_distance_pct=CFG.STOP_HUNT_MAX_ZONE_DISTANCE_PCT,
        stop_hunt_sl_pct=CFG.STOP_HUNT_SL_PCT,
        stop_hunt_min_volume_ratio=CFG.STOP_HUNT_MIN_VOLUME_RATIO,
        stop_hunt_use_ema_filter=CFG.STOP_HUNT_USE_EMA_FILTER,
        stop_hunt_min_break_candles=CFG.STOP_HUNT_MIN_BREAK_CANDLES,
        stop_hunt_atr_mult_sl=CFG.STOP_HUNT_ATR_MULT_SL,
        stop_hunt_momentum_bars=CFG.STOP_HUNT_MOMENTUM_BARS,
        stop_hunt_min_atr_pct=CFG.STOP_HUNT_MIN_ATR_PCT,
        order_block_lookback=CFG.ORDER_BLOCK_LOOKBACK,
    )
    state_dict = db.load_state() or {}
    defaults_dict = defaults.to_dict()
    for k, v in defaults_dict.items():
        if k not in state_dict:
            state_dict[k] = v
    merged_data = {**defaults_dict, **state_dict}
    st = BotState(**merged_data)
    db.save_state(st.to_dict())

    # ================= CONFIG SYNC =================
    updated = False
    if st.risk_pct <= 0 or st.risk_pct > CFG.MAX_RISK_PCT_ALLOWED:
        log.warning(f"[CONFIG] risk_pct inválido ({st.risk_pct}), usando default {CFG.DEFAULT_RISK_PCT}")
        st.risk_pct = CFG.DEFAULT_RISK_PCT
        updated = True
    if st.leverage < 1 or st.leverage > 50:
        log.warning(f"[CONFIG] leverage inválido ({st.leverage}), usando default {CFG.DEFAULT_LEVERAGE}")
        st.leverage = CFG.DEFAULT_LEVERAGE
        updated = True
    if updated:
        db.save_state(st.to_dict())
        log.info("[CONFIG] Valores corregidos y guardados en DB")

    sync_cfg_from_state(st)

    # ================= DAY INIT =================
    if not st.day_key:
        st.day_key = utc_day_key()
    if st.day_start_equity <= 0:
        st.day_start_equity = max(exchange.get_equity(), 0.0)

    # ================= LEVERAGE =================
    for s in st.symbols:
        exchange.set_margin_and_leverage(s, st.leverage, CFG.MARGIN_TYPE)

    # ================= COMPONENTES =================
    market = MarketCache(exchange, log, db)
    market.init_cache(st.symbols)
    bus = SignalBus()
    om = OrderManager(exchange, log, db, telegram.send)
    trailing = TrailingManager(exchange, market, om, db, telegram.send, log)
    event_loop = EventLoop(bus, market, exchange, om, telegram.send, db, log)
    risk_monitor = RiskMonitor(st, exchange, telegram, log)
    signal_engine = SignalEngine(market, bus, log, st.strategy_mode)

    mode = "PAPER" if st.paper_trading else "PRODUCCIÓN"
    strategy_labels = {
        "ema_breakout": "EMA Breakout",
        "stop_hunt": "Stop Hunt",
        "vwap_refresh": "VWAP Refresh",
        "auto": f"Auto (analizando...)",
    }
    strategy_label = strategy_labels.get(st.strategy_mode, "EMA Breakout")
    telegram.send(
        f"🚀 Bot activo ({mode})\n"
        f"Strategy: {strategy_label}\n"
        f"Symbols: {', '.join(st.symbols)}\n"
        f"TF: {CFG.INTERVAL}\n"
        f"Risk: {st.risk_pct}%\n"
        f"Lev: {st.leverage}x\n"
        f"Trailing: {st.trailing_pct}%"
    )

    # ================= LOOP VARS =================
    last_account_snapshot = 0
    ACCOUNT_SNAPSHOT_INTERVAL = 15
    last_equity_snapshot = 0
    EQUITY_SNAPSHOT_INTERVAL = 60
    last_state_reload = 0
    STATE_RELOAD_INTERVAL = 30
    last_server_time_check = 0
    SERVER_TIME_CHECK_INTERVAL = 60

    # ================= MASTER LOOP =================
    while True:
        try:
            now = time.time()

            # === State reload cada 30s ===
            if now - last_state_reload > STATE_RELOAD_INTERVAL:
                state_dict = db.load_state() or {}
                for k, v in defaults_dict.items():
                    if k not in state_dict:
                        state_dict[k] = v
                new_st = BotState(**{**defaults_dict, **state_dict})

                if new_st.paper_trading != st.paper_trading:
                    mode = "PAPER" if new_st.paper_trading else "PRODUCCIÓN"
                    log.info(f"[MODE] Cambio detectado: {mode}")
                    telegram.send(f"🔄 Modo cambiado a: <b>{mode}</b>")
                if new_st.pivot_len != st.pivot_len:
                    log.info(f"[PIVOT] Cambio detectado: {st.pivot_len} → {new_st.pivot_len}")
                if set(new_st.symbols) != set(st.symbols):
                    log.info(f"[SYMBOLS] Cambio detectado: {st.symbols} -> {new_st.symbols}")
                    market.init_cache(new_st.symbols)
                    for s in new_st.symbols:
                        exchange.set_margin_and_leverage(s, new_st.leverage, CFG.MARGIN_TYPE)
                if new_st.strategy_mode != st.strategy_mode:
                    log.info(f"[STRATEGY] Cambio detectado: {st.strategy_mode} -> {new_st.strategy_mode}")
                    signal_engine.set_strategy_mode(new_st.strategy_mode)
                    strategy_label = strategy_labels.get(new_st.strategy_mode, "EMA Breakout")
                    telegram.send(f"🔄 Estrategia cambiada a: <b>{strategy_label}</b>")

                st = new_st
                last_state_reload = now
                sync_cfg_from_state(st)

            # === Sync hora Binance para daily loss ===
            if now - last_server_time_check > SERVER_TIME_CHECK_INTERVAL:
                try:
                    server_time_ms = exchange.client.futures_time()["serverTime"]
                    server_day_key = time.strftime("%Y-%m-%d", time.gmtime(server_time_ms / 1000))
                    if st.day_key != server_day_key:
                        log.info(f"[DAY ROLL] Cambio de día detectado (Binance): {server_day_key}")
                        st.day_key = server_day_key
                        st.day_start_equity = max(exchange.get_equity(), 0.0)
                        db.save_state(st.__dict__)
                    last_server_time_check = now
                except Exception as e:
                    log.warning(f"[TIME SYNC] Error obteniendo hora Binance: {e}")
                    local_day = utc_day_key()
                    if st.day_key != local_day:
                        st.day_key = local_day
                        st.day_start_equity = max(exchange.get_equity(), 0.0)

            # 1) Market update
            market.update_all(st.symbols)

            # 2) Check max positions (avoid unnecessary signal processing)
            max_pos_reached = event_loop._max_positions_reached(st)

            # 3) Regime check (once per cycle, not per symbol)
            if st.symbols and not max_pos_reached:
                signal_engine.check_and_switch_regime(st.symbols[0])

            # 4) Generate signals
            for sym in st.symbols:
                signal_engine.process_symbol(sym, max_pos_reached)

            # 3) Execute signals
            event_loop.loop_once(st)

            # 4) Trailing
            trailing.loop_once(st)

            # 5) Telegram polling
            telegram.poll_once(st, exchange, db)

            # 6) Control de Riesgo
            # risk_monitor.check()     va pero es media jedienta

            # 7) Account snapshot
            try:
                acc = exchange.get_account_info()
                now = time.time()
                if now - last_account_snapshot > ACCOUNT_SNAPSHOT_INTERVAL:
                    db.save_account_snapshot(
                        equity=acc["equity"],
                        used_margin=acc["used_margin"],
                        available=acc["available"]
                    )
                    last_account_snapshot = now
                if now - last_equity_snapshot > EQUITY_SNAPSHOT_INTERVAL:
                    unrealized_pnl = acc["equity"] - acc["available"] - acc["used_margin"]
                    db.save_equity_snapshot(
                        total_balance=acc["equity"],
                        available_balance=acc["available"],
                        unrealized_pnl=unrealized_pnl
                    )
                    last_equity_snapshot = now
            except Exception as e:
                log.warning(f"Account snapshot error: {e}")

            time.sleep(CFG.LOOP_SLEEP_SECONDS)

        except Exception as e:
            telegram.send(f"⚠️ Bot error: {type(e).__name__}: {str(e)[:120]}")
            time.sleep(5)


if __name__ == "__main__":
    main()
