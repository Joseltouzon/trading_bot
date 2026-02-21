# notification/telegrma.py

import requests
import datetime
from typing import Optional

import config as CFG
from core.utils import clamp


class Telegram:

    def __init__(self, token: str, chat_id: str, log, db):
        self.token = token
        self.chat_id = str(chat_id)
        self.log = log
        self.db = db
        self._last_update_id = 0

    # ============================================================
    # SEND
    # ============================================================

    def send(self, msg: str):
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": msg,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            requests.post(url, data=payload, timeout=15)
        except Exception as e:
            self.log.warning(f"[TG] error: {e}")

    # ============================================================
    # POLL
    # ============================================================

    def poll_once(self, st, exchange):
        try:
            url = f"https://api.telegram.org/bot{self.token}/getUpdates"
            params = {"timeout": 0, "offset": self._last_update_id + 1}

            r = requests.get(url, params=params, timeout=10)
            data = r.json()

            if not data.get("ok"):
                return

            for upd in data.get("result", []):
                self._last_update_id = upd["update_id"]
                msg = upd.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))

                if chat_id != self.chat_id:
                    continue

                text = (msg.get("text") or "").strip()
                if text:
                    self._handle_command(st, text, exchange)

        except Exception as e:
            self.log.warning(f"[TG poll] error: {e}")

    # ============================================================
    # COMMAND HANDLER
    # ============================================================

    def _handle_command(self, st, text: str, exchange):

        parts = text.split()
        cmd = parts[0].lower()

        # ========================================================
        # HELP
        # ========================================================

        if cmd == "/help":
            self.send(
                "<b>📘 Comandos disponibles</b>\n\n"
                "/dashboard\n"
                "/status\n/status_full\n"
                "/balance\n/positions\n"
                "/performance\n/exposure\n/volatility\n/drawdown\n/health\n"
                "/risk\n/trail\n/symbols\n"
                "/pause /resume\n"
                "/close SYMBOL\n/close_all\n"
                "/set_leverage N\n/set_risk N\n"
                "/set_trailing N\n/set_activation N\n/set_maxpos N\n"
                "/paper_mode\n"
            )
            return

        # ========================================================
        # BASIC CONTROL
        # ========================================================

        if cmd == "/pause":
            st.paused = True
            self.db.save_state(st.__dict__)
            self.send("⏸ <b>Bot pausado</b>")
            return

        if cmd == "/resume":
            st.paused = False
            self.db.save_state(st.__dict__)
            self.send("▶️ <b>Bot reanudado</b>")
            return

        if cmd == "/paper_mode":
            st.paper_trading = not st.paper_trading
            self.db.save_state(st.__dict__)
            self.send(f"🧪 Paper mode: <b>{st.paper_trading}</b>")
            return

        # ========================================================
        # DASHBOARD
        # ========================================================

        if cmd == "/dashboard":

            eq = exchange.get_equity()
            avail = exchange.get_available_balance()
            used = exchange.get_used_margin()
            positions = exchange.get_open_positions()
            exposure = exchange.get_total_exposure_notional()
            pnl = exchange.get_daily_realized_pnl()

            drawdown = 0.0
            if st.day_start_equity > 0:
                drawdown = ((eq - st.day_start_equity) / st.day_start_equity) * 100.0

            msg = (
                "<b>📊 DASHBOARD</b>\n\n"
                f"Equity: ${eq:.2f}\n"
                f"Available: ${avail:.2f}\n"
                f"Used Margin: ${used:.2f}\n\n"
                f"Exposure: ${exposure:.2f}\n"
                f"Open Positions: {len(positions)}/{st.max_positions}\n\n"
                f"Daily Realized PnL: ${pnl:.2f}\n"
                f"Drawdown: {drawdown:.2f}%\n\n"
                f"Risk: {st.risk_pct}% | Lev: {st.leverage}x\n"
                f"Trailing: {st.trailing_pct}%"
            )

            self.send(msg)
            return

        # ========================================================
        # STATUS
        # ========================================================

        if cmd == "/status":

            pos = exchange.get_open_positions()
            eq = exchange.get_equity()

            self.send(
                f"<b>📊 Bot Status</b>\n"
                f"Paused: {st.paused}\n"
                f"Paper: {st.paper_trading}\n"
                f"Equity: ${eq:.2f}\n"
                f"Positions: {len(pos)}/{st.max_positions}"
            )
            return

        if cmd == "/status_full":

            pos = exchange.get_open_positions()
            eq = exchange.get_equity()
            avail = exchange.get_available_balance()

            msg = (
                f"<b>📊 FULL STATUS</b>\n\n"
                f"Equity: ${eq:.2f}\n"
                f"Available: ${avail:.2f}\n"
                f"Risk: {st.risk_pct}%\n"
                f"Leverage: {st.leverage}x\n"
                f"Trailing: {st.trailing_pct}%\n"
                f"Activation: {CFG.TRAILING_ACTIVATION_PCT}%\n"
                f"ADX min: {st.adx_min}\n"
                f"Max positions: {st.max_positions}\n\n"
                f"Open positions: {len(pos)}"
            )

            self.send(msg)
            return

        # ========================================================
        # PERFORMANCE
        # ========================================================

        if cmd == "/performance":
            pnl = exchange.get_daily_realized_pnl()
            self.send(
                f"<b>📈 Performance Diario</b>\n"
                f"Realized PnL (UTC): ${pnl:.2f}"
            )
            return

        if cmd == "/exposure":
            exposure = exchange.get_total_exposure_notional()
            equity = exchange.get_equity()
            ratio = exposure / equity if equity > 0 else 0

            self.send(
                f"<b>📊 Exposure</b>\n"
                f"Total Notional: ${exposure:.2f}\n"
                f"Equity: ${equity:.2f}\n"
                f"Exposure/Equity: {ratio:.2f}x"
            )
            return

        if cmd == "/volatility":

            symbols = st.symbols
            total = 0.0
            count = 0

            lines = ["<b>🧠 Volatility (ATR % 5m)</b>\n"]

            for s in symbols:
                try:
                    atr_pct = exchange.get_atr_pct(s)
                    total += atr_pct
                    count += 1
                    lines.append(f"{s}: {atr_pct:.2f}%")
                except:
                    continue

            avg = total / count if count > 0 else 0.0
            lines.append(f"\nATR Promedio: <b>{avg:.2f}%</b>")

            self.send("\n".join(lines))
            return

        if cmd == "/drawdown":

            eq = exchange.get_equity()

            if st.day_start_equity <= 0:
                self.send("No hay equity inicial del día registrado.")
                return

            dd_pct = ((eq - st.day_start_equity) / st.day_start_equity) * 100.0
            dd_usdt = eq - st.day_start_equity

            self.send(
                f"<b>📉 Drawdown Diario</b>\n"
                f"Inicio día: ${st.day_start_equity:.2f}\n"
                f"Actual: ${eq:.2f}\n\n"
                f"Resultado: ${dd_usdt:.2f}\n"
                f"Drawdown: {dd_pct:.2f}%"
            )
            return

        if cmd == "/health":

            h = exchange.health_check()

            if not h["api_reachable"]:
                self.send("❌ API no responde.")
                return

            self.send(
                f"<b>🩺 Health Check</b>\n"
                f"API reachable: ✅\n"
                f"Latency: {h['latency_ms']} ms\n"
                f"Server time diff: {h['server_time_diff_ms']} ms"
            )
            return

        # ========================================================
        # POSITIONS
        # ========================================================

        if cmd == "/positions":

            pos = exchange.get_open_positions()

            if not pos:
                self.send("No hay posiciones abiertas.")
                return

            lines = ["<b>📌 Open Positions</b>\n"]

            for p in pos:
                lines.append(
                    f"{p['symbol']} {p['side']} "
                    f"size={float(p['size']):.4f} "
                    f"entry={float(p['entry_price']):.4f}"
                )

            self.send("\n".join(lines))
            return

        if cmd == "/close_all":
            pos = exchange.get_open_positions()
            for p in pos:
                exchange.close_position(p["symbol"])
            self.send("🚨 Todas las posiciones cerradas.")
            return

        if cmd == "/close" and len(parts) >= 2:
            symbol = parts[1].upper()
            exchange.close_position(symbol)
            self.send(f"🚨 Cerrando {symbol}")
            return

        # ========================================================
        # RISK / CONFIG
        # ========================================================

        if cmd == "/risk":
            self.send(
                f"<b>🧮 Risk Config</b>\n"
                f"Risk %: {st.risk_pct}\n"
                f"Leverage: {st.leverage}x\n"
                f"Max positions: {st.max_positions}\n"
                f"Daily loss limit: {st.daily_loss_limit_pct}%"
            )
            return

        if cmd == "/trail":
            self.send(
                f"<b>🔒 Trailing Config</b>\n"
                f"Trailing %: {st.trailing_pct}\n"
                f"Activation %: {CFG.TRAILING_ACTIVATION_PCT}"
            )
            return

        if cmd == "/symbols":
            self.send("<b>Symbols activos:</b>\n" + ", ".join(st.symbols))
            return

        # ========================================================
        # SETTERS
        # ========================================================

        if cmd == "/set_leverage" and len(parts) >= 2:
            lev = int(clamp(int(parts[1]), 1, 20))
            st.leverage = lev
            self.db.save_state(st.__dict__)
            for s in st.symbols:
                exchange.set_margin_and_leverage(s, lev, CFG.MARGIN_TYPE)
            self.send(f"Leverage actualizado: {lev}x")
            return

        if cmd == "/set_risk" and len(parts) >= 2:
            r = float(clamp(float(parts[1]), 0.1, CFG.MAX_RISK_PCT_ALLOWED))
            st.risk_pct = r
            self.db.save_state(st.__dict__)
            self.send(f"Risk actualizado: {r}%")
            return

        if cmd == "/set_trailing" and len(parts) >= 2:
            tr = float(clamp(float(parts[1]), 0.1, 10))
            st.trailing_pct = tr
            self.db.save_state(st.__dict__)
            self.send(f"Trailing actualizado: {tr}%")
            return

        if cmd == "/set_maxpos" and len(parts) >= 2:
            m = int(clamp(int(parts[1]), 1, 10))
            st.max_positions = m
            self.db.save_state(st.__dict__)
            self.send(f"Max positions: {m}")
            return

        if cmd == "/set_activation" and len(parts) >= 2:
            val = float(clamp(float(parts[1]), 0.1, 10))
            CFG.TRAILING_ACTIVATION_PCT = val
            self.send(f"Trailing activation: {val}%")
            return
 