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
        max_positions=CFG.MAX_OPEN_POSITIONS,
        adx_min=CFG.DEFAULT_ADX_MIN,
        cooldown_bars=CFG.DEFAULT_COOLDOWN_BARS,
        daily_loss_limit_pct=CFG.DEFAULT_DAILY_LOSS_LIMIT_PCT,
        paper_trading=PAPER_TRADING,
        timeframe=CFG.INTERVAL,
        pivot_len=CFG.PIVOT_LEN,
    )
    state_dict = db.load_state() or {}
    # merge base
    merged_data = {
        **defaults.to_dict(),
        **state_dict
    }
    st = BotState(**merged_data)

    # ================= CONFIG SYNC =================
    # La DB es la fuente de verdad. config.py solo sirve para defaults iniciales.
    # Si querés cambiar algo, usá el dashboard. No sobrescribas la DB al iniciar.
    updated = False
    # Solo validar que los valores cargados sean razonables (sanity check)
    if st.risk_pct <= 0 or st.risk_pct > CFG.MAX_RISK_PCT_ALLOWED:
        log.warning(f"[CONFIG] risk_pct inválido ({st.risk_pct}), usando default {CFG.DEFAULT_RISK_PCT}")
        st.risk_pct = CFG.DEFAULT_RISK_PCT
        updated = True

    if st.leverage < 1 or st.leverage > 50:
        log.warning(f"[CONFIG] leverage inválido ({st.leverage}), usando default {CFG.DEFAULT_LEVERAGE}")
        st.leverage = CFG.DEFAULT_LEVERAGE
        updated = True

    # Guardar si hubo correcciones
    if updated:
        db.save_state(st.to_dict())
        log.info("[CONFIG] Valores corregidos y guardados en DB")

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
    # Motor de señales
    signal_engine = SignalEngine(market, bus, log)

    mode = "PAPER" if st.paper_trading else "PRODUCCIÓN"
    telegram.send(
        f"🚀 Bot activo ({mode})\n"
        f"Symbols: {', '.join(st.symbols)}\n"
        f"TF: {CFG.INTERVAL}\n"
        f"Risk: {st.risk_pct}%\n"
        f"Lev: {st.leverage}x\n"
        f"Trailing: {st.trailing_pct}%"
    )

    # para no guardar a cada rato en la base el snapshot
    last_account_snapshot = 0
    ACCOUNT_SNAPSHOT_INTERVAL = 15  # segundos
    last_equity_snapshot = 0
    EQUITY_SNAPSHOT_INTERVAL = 60  # segundos

    # ================= MEJORA 1: CACHE DE ESTADO DB =================
    last_state_reload = 0
    STATE_RELOAD_INTERVAL = 30  # Segundos - Solo recargar config cada 30s

    # ================= MEJORA 2: SYNC HORA BINANCE =================
    last_server_time_check = 0
    SERVER_TIME_CHECK_INTERVAL = 60  # Segundos

    # ================= MASTER LOOP (REST) =================
    while True:
        try:
            # ========== MEJORA 1: Carga de estado optimizada ==========
            now = time.time()
            # Solo recargar configuración desde DB cada 30 segundos
            if now - last_state_reload > STATE_RELOAD_INTERVAL:
                state_dict = db.load_state() or {}
                merged_data = { **st.to_dict(), **state_dict }
                new_st = BotState(**merged_data)

                # Detectar cambio de paper_trading
                if new_st.paper_trading != st.paper_trading:
                    mode = "PAPER" if new_st.paper_trading else "PRODUCCIÓN"
                    log.info(f"[MODE] Cambio detectado: {mode}")
                    telegram.send(f"🔄 Modo cambiado a: <b>{mode}</b>")
                
                # Detectar cambio de pivot_len (si tu estrategia lo usa dinámicamente)
                if new_st.pivot_len != st.pivot_len:
                    log.info(f"[PIVOT] Cambio detectado: {st.pivot_len} → {new_st.pivot_len}")
                
                # Detectar cambio de símbolos
                if set(new_st.symbols) != set(st.symbols):
                    log.info(f"[SYMBOLS] Cambio detectado: {st.symbols} -> {new_st.symbols}")
                    # Reinicializar cache con nuevos símbolos
                    market.init_cache(new_st.symbols)
                    # Actualizar leverage en nuevos símbolos
                    for s in new_st.symbols:
                        exchange.set_margin_and_leverage(s, new_st.leverage, CFG.MARGIN_TYPE)
                
                st = new_st
                last_state_reload = now    

            # ========== MEJORA 2: Sync hora Binance para daily loss ==========
            if now - last_server_time_check > SERVER_TIME_CHECK_INTERVAL:
                try:
                    server_time_ms = exchange.client.futures_time()['serverTime']
                    server_day_key = time.strftime("%Y-%m-%d", time.gmtime(server_time_ms / 1000))
                    
                    # Verificar cambio de día en Binance
                    if st.day_key != server_day_key:
                        log.info(f"[DAY ROLL] Cambio de día detectado (Binance): {server_day_key}")
                        st.day_key = server_day_key
                        st.day_start_equity = max(exchange.get_equity(), 0.0)
                        db.save_state(st.__dict__)
                    
                    last_server_time_check = now
                except Exception as e:
                    log.warning(f"[TIME SYNC] Error obteniendo hora Binance: {e}")
                    # Fallback a hora local si falla API
                    local_day = utc_day_key()
                    if st.day_key != local_day:
                        st.day_key = local_day
                        st.day_start_equity = max(exchange.get_equity(), 0.0)

            # 1) Actualizar velas/market (REST polling)
            market.update_all(st.symbols)

            # 2) Generar señales (1 vez por vela cerrada)
            for sym in st.symbols:
                signal_engine.process_symbol(sym)

            # 3) Ejecutar señales del bus
            event_loop.loop_once(st)

            # 4) Trailing
            trailing.loop_once(st)

            # 5) Telegram polling
            telegram.poll_once(st, exchange, db)

            # 6) Control de Riesgo
            # risk_monitor.check()     va pero es media jedienta

            # 7) SNAPSHOT DE CUENTA
            try:
                acc = exchange.get_account_info()
                now = time.time()
                # ================= ACCOUNT SNAPSHOT (optimizado) =================
                if now - last_account_snapshot > ACCOUNT_SNAPSHOT_INTERVAL:
                    db.save_account_snapshot(
                        equity=acc["equity"],
                        used_margin=acc["used_margin"],
                        available=acc["available"]
                    )
                    last_account_snapshot = now

                # ================= EQUITY SNAPSHOT (histórico) =================
                if now - last_equity_snapshot > EQUITY_SNAPSHOT_INTERVAL:
                    unrealized_pnl = (
                        acc["equity"]
                        - acc["available"]
                        - acc["used_margin"]
                    )
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