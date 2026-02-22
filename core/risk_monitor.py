# core/risk_monitor.py

import time
from core.control import panic_mode

class RiskMonitor:

    def __init__(self, st, exchange, telegram, log):
        self.st = st
        self.exchange = exchange
        self.telegram = telegram
        self.log = log

        self._last_alert_time = {}
        self.cooldown_sec = 300  # 5 min entre alertas iguales

    def _can_alert(self, key):
        now = time.time()
        last = self._last_alert_time.get(key, 0)
        if now - last > self.cooldown_sec:
            self._last_alert_time[key] = now
            return True
        return False

    def check(self):

        eq = self.exchange.get_equity()
        exposure = self.exchange.get_total_exposure_notional()

        # ===============================
        # 1️⃣ Exposure alto
        # ===============================

        if eq > 0:
            ratio = exposure / eq

            if ratio > 3:
                if self._can_alert("exposure_high"):
                    self.telegram.send(
                        f"⚠️ <b>ALERTA EXPOSURE</b>\n"
                        f"Exposure/Equity: {ratio:.2f}x"
                    )

        # ===============================
        # 2️⃣ Drawdown diario
        # ===============================

        if self.st.day_start_equity > 0:
            dd_pct = ((eq - self.st.day_start_equity) /
                      self.st.day_start_equity) * 100.0

            if dd_pct <= -self.st.daily_loss_limit_pct:
                if self._can_alert("daily_dd"):
                    self.telegram.send(
                        f"🛑 <b>LIMITE DIARIO ALCANZADO</b>\n"
                        f"Drawdown: {dd_pct:.2f}%"
                    )
                    #panic_mode(           ## por ahora me parece demasiado y si se activa cierra todo
                    #   self.st,
                    #   self.exchange,
                    #   self.telegram.db,
                    #   self.telegram
                    #) 