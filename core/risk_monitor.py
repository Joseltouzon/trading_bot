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
        self.cooldown_sec = 600

    def _can_alert(self, key):
        now = time.time()
        last = self._last_alert_time.get(key, 0)
        if now - last > self.cooldown_sec:
            self._last_alert_time[key] = now
            return True
        return False

    def check(self):
        eq = self.exchange.get_equity()
        used_margin = self.exchange.get_used_margin()
        available = self.exchange.get_available_balance()
        exposure = self.exchange.get_total_exposure_notional()
        positions = self.exchange.get_open_positions()

        total_margin_used = used_margin
        total_account = total_margin_used + available

        if total_account <= 0:
            return

        margin_health_pct = (total_margin_used / total_account) * 100.0

        if margin_health_pct >= 70:
            if self._can_alert("margin_high"):
                self.telegram.send(
                    f"🔴 <b>ALERTA MARGIN</b>\n"
                    f"Margin usage: {margin_health_pct:.1f}%\n"
                    f"Used: ${total_margin_used:.2f} / ${total_account:.2f}"
                )

        if margin_health_pct >= 80:
            if self._can_alert("margin_critical"):
                self.telegram.send(
                    f"🚨 <b>MARGIN CRITICO</b>\n"
                    f"Margin usage: {margin_health_pct:.1f}%\n"
                    f"Liquidacion inminente si siguen en contra!"
                )

        if eq > 0:
            ratio = exposure / eq
            if ratio >= 5:
                if self._can_alert("exposure_high"):
                    self.telegram.send(
                        f"⚠️ <b>ALERTA EXPOSURE</b>\n"
                        f"Exposure/Equity: {ratio:.2f}x\n"
                        f"Equity: ${eq:.2f}"
                    )

        if positions:
            max_concentration = 0
            concentrated_sym = ""
            for p in positions:
                mark = self.exchange.get_mark_price(p["symbol"])
                sym_notional = abs(mark * float(p["size"]))
                concentration = sym_notional / exposure if exposure > 0 else 0
                if concentration > max_concentration:
                    max_concentration = concentration
                    concentrated_sym = p["symbol"]

            if max_concentration >= 0.7:
                if self._can_alert("concentration"):
                    self.telegram.send(
                        f"⚠️ <b>CONCENTRACION</b>\n"
                        f"{concentrated_sym}: {max_concentration*100:.1f}% de exposure"
                    )

        if self.st.day_start_equity > 0:
            dd_pct = ((eq - self.st.day_start_equity) /
                      self.st.day_start_equity) * 100.0

            if dd_pct <= -self.st.daily_loss_limit_pct:
                if self._can_alert("daily_dd"):
                    self.telegram.send(
                        f"🛑 <b>LIMITE DIARIO ALCANZADO</b>\n"
                        f"Drawdown: {dd_pct:.2f}%"
                    )
                    #panic_mode(
                    #   self.st,
                    #   self.exchange,
                    #   self.telegram.db,
                    #   self.telegram
                    #)
