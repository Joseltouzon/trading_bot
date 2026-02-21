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
    )

    state_dict = db.load_state() or {}

    # merge seguro usando dataclass real
    merged_data = {
        **defaults.to_dict(),
        **state_dict
    }

    st = BotState(**merged_data)

    if not st.day_key:
        st.day_key = utc_day_key()

    if st.day_start_equity <= 0:
        st.day_start_equity = max(exchange.get_equity(), 0.0)

    db.save_state(st.to_dict())

    # ================= LEVERAGE =================
    for s in st.symbols:
        exchange.set_margin_and_leverage(s, st.leverage, CFG.MARGIN_TYPE)

    # ================= COMPONENTES =================
    market = MarketCache(exchange, log)
    market.init_cache(st.symbols)

    bus = SignalBus()
    om = OrderManager(exchange, log, db, telegram.send)
    trailing = TrailingManager(exchange, market, om, db, telegram.send, log)
    event_loop = EventLoop(bus, market, exchange, om, log)

    # ✅ NUEVO: Motor de señales desacoplado de WS
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

    # ================= MASTER LOOP (REST) =================
    while True:
        try:
            # RELOAD STATE DINÁMICO PARA CARGAR CONFIG DEL DASHBOARD
            state_dict = db.load_state() or {}
            merged_data = {
                **st.to_dict(),
                **state_dict
            }
            st = BotState(**merged_data)
            # 1) Actualizar velas/market (REST polling)
            market.update_all(st.symbols)

            # 2) Generar señales (1 vez por vela cerrada)
            for sym in st.symbols:
                signal_engine.process_symbol(sym)

            # 3) Ejecutar señales del bus
            event_loop.loop_once(st)

            # 4) Trailing
            trailing.loop_once(st)

            # 5) Telegram polling (si existe)
            if hasattr(telegram, "poll_once"):
                telegram.poll_once(st, exchange)

            time.sleep(CFG.LOOP_SLEEP_SECONDS)

        except Exception as e:
            telegram.send(f"⚠️ Bot error: {type(e).__name__}: {str(e)[:120]}")
            time.sleep(5)


if __name__ == "__main__":
    main()
