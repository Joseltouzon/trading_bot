# datafeed/ws_manager.py

import time
import threading
from typing import List, Optional

import pandas as pd
from binance import ThreadedWebsocketManager

import config as CFG
from core.models import SignalEvent
from strategy.ema_adx_breakout import compute_signals


class WSManager:

    def __init__(self, api_key: str, api_secret: str, market_cache, signal_bus, tg_send, log):
        self.api_key = api_key
        self.api_secret = api_secret
        self.market = market_cache
        self.bus = signal_bus
        self.tg_send = tg_send
        self.log = log

        self._twm_lock = threading.Lock()
        self._twm: Optional[ThreadedWebsocketManager] = None

        self._restart_flag = False
        self._restart_reason = "unknown"

    # ============================================================
    # LIFECYCLE
    # ============================================================

    def _is_alive(self):
        with self._twm_lock:
            return self._twm is not None

    def _stop(self):
        with self._twm_lock:
            if self._twm is None:
                return

            try:
                self._twm.stop()
            except Exception:
                pass

            self._twm = None

        # Esperar a que threads mueran realmente
        time.sleep(5)

    def _start(self, symbols: List[str]):

        with self._twm_lock:
            if self._twm is not None:
                return  # ya existe, no crear otro

            twm = ThreadedWebsocketManager(
                api_key=self.api_key,
                api_secret=self.api_secret
            )

            twm.start()
            twm.start_futures_mark_price_socket(callback=self._on_mark_price)

            for sym in symbols:
                twm.start_futures_kline_socket(
                    callback=self._on_kline,
                    symbol=sym,
                    interval=CFG.INTERVAL
                )

            self._twm = twm


    # ============================================================
    # CALLBACKS
    # ============================================================

    def _on_kline(self, msg):
        try:
            if msg.get("e") != "kline":
                return

            sym = msg.get("s")
            k = msg.get("k", {})

            if not k.get("x", False):
                return  # sólo vela cerrada

            open_time = int(k["t"])
            close_time = int(k["T"])

            o = float(k["o"])
            h = float(k["h"])
            l = float(k["l"])
            c = float(k["c"])
            v = float(k["v"])

            df = self.market.get_df_copy(sym)
            if df is None:
                return

            last_close = int(df["close_time"].iloc[-1])
            if close_time <= last_close:
                return

            new_row = {
                "open_time": open_time,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": v,
                "close_time": close_time,
                "quote_asset_volume": 0,
                "trades": 0,
                "taker_buy_base": 0,
                "taker_buy_quote": 0,
                "ignore": 0
            }

            df2 = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

            if len(df2) > CFG.KLINES_LIMIT:
                df2 = df2.iloc[-CFG.KLINES_LIMIT:].reset_index(drop=True)

            self.market.update_closed_kline(sym, df2, close_time)

            sig = compute_signals(df2)

            if sig["trend"] == "BULL" and sig["breakout_long"]:
                self.bus.publish(SignalEvent(sym, "LONG", sig, close_time))

            elif sig["trend"] == "BEAR" and sig["breakout_short"]:
                self.bus.publish(SignalEvent(sym, "SHORT", sig, close_time))

        except Exception as e:
            self.log.warning(f"[WS kline] error: {e}")

    def _on_mark_price(self, msg):
        try:
            if isinstance(msg, list):
                self.market.update_mark_prices(msg)
        except Exception as e:
            self.log.warning(f"[WS mark] error: {e}")

    # ============================================================
    # CONTROL
    # ============================================================

    def request_restart(self, reason: str):
        self._restart_flag = True
        self._restart_reason = reason

    def supervisor_loop(self, st):

        while True:
            try:

                alive = self._is_alive()

                if self._restart_flag:
                    self.tg_send(f"🔄 Reiniciando WS ({self._restart_reason})...")
                    self._restart_flag = False
                    self._stop()
                    alive = False

                if not alive:
                    try:
                        self.tg_send("🧩 WS supervisor: iniciando websockets...")
                        self._start(st.symbols)
                        self.tg_send("🟢 WebSockets activos")
                    except Exception as e:
                        self.tg_send(f"🔴 No se pudo iniciar WS: {e}")
                        time.sleep(CFG.WS_RECONNECT_WAIT)
                        continue

                time.sleep(5)

            except Exception as e:
                self.log.warning(f"[WS supervisor] error: {e}")
                time.sleep(5)

    def watchdog_loop(self, st):

        threshold = CFG.WATCHDOG_THRESHOLD_SECONDS

        while True:
            try:

                dead = []

                for sym in st.symbols:
                    age = self.market.get_last_kline_close_age_seconds(sym)

                    if age > threshold:
                        dead.append(sym)

                if dead:
                    self.tg_send(
                        "🟠 <b>WATCHDOG</b>\n"
                        f"No llegan velas cerradas ({len(dead)}): {', '.join(dead)}\n"
                        "Reiniciando WebSockets..."
                    )
                    self.request_restart("watchdog")

                time.sleep(15)

            except Exception as e:
                self.log.warning(f"[watchdog] error: {e}")
                time.sleep(10)
