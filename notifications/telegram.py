# notification/telegrma.py

import requests
import datetime
from typing import Optional

import config as CFG
from core.utils import clamp
from core.control import pause_bot, resume_bot, close_all_positions, panic_mode


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

    def poll_once(self, st, exchange, db):
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
                    self._handle_command(st, text, exchange, db)

        except Exception as e:
            self.log.warning(f"[TG poll] error: {e}")

    # ============================================================
    # COMMAND HANDLER
    # ============================================================

    def _handle_command(self, st, text: str, exchange, db):

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
                "/risk\n/trail\n/symbols\n/strategies\n"
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
            pause_bot(st, self.db)
            self.send("⏸ <b>Bot pausado</b>")
            return

        if cmd == "/resume":
            resume_bot(st, self.db)
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
                f"Strategy: {st.strategy_mode}\n"
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

            strategy_symbols = st.strategy_symbols if hasattr(st, "strategy_symbols") else {}
            all_symbols = set()
            for syms in strategy_symbols.values():
                all_symbols.update(syms)

            total = 0.0
            count = 0

            lines = ["<b>🧠 Volatility (ATR %)</b>\n"]

            for s in all_symbols:
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

            trail = st.trail if hasattr(st, "trail") else {}
            lines = ["<b>📌 Open Positions</b>\n"]

            for p in pos:
                symbol = p["symbol"]
                side = p["side"]
                size = float(p["size"])
                entry = float(p["entry_price"])
                pnl_unreal = float(p["unrealized_pnl"])

                # Mark price
                try:
                    mark = float(exchange.get_mark_price(symbol))
                except:
                    mark = 0

                pnl_pct = ((mark - entry) / entry * 100) if entry > 0 and side == "LONG" else ((entry - mark) / entry * 100) if entry > 0 else 0

                # Trailing status
                tr = trail.get(symbol, {})
                trailing_txt = "🔒ON" if tr.get("activated") else "⏳wait" if tr else "❌"
                sl_txt = f"SL:{tr.get('sl', 0):.4f}" if tr.get("sl") else "SL:-"

                lines.append(
                    f"{symbol} {side}\n"
                    f"  Entry:{entry:.4f} Mark:{mark:.4f}\n"
                    f"  PnL: {pnl_pct:+.2f}% (${pnl_unreal:+.2f})\n"
                    f"  {trailing_txt} {sl_txt}"
                )

            self.send("\n".join(lines))
            return

        if cmd == "/close_all":

            pos = exchange.get_open_positions()

            if not pos:
                self.send("No hay posiciones abiertas.")
                return

            if len(parts) < 2 or parts[1].lower() != "confirm":
                self.send("⚠️ Para confirmar usa:\n/close_all confirm")
                return

            n = close_all_positions(exchange)
            self.send(f"🚨 Cerradas: {n}")

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
            strategy_symbols = st.strategy_symbols if hasattr(st, "strategy_symbols") else {}
            lines = ["<b>📊 Símbolos por estrategia</b>\n"]
            all_symbols = set()
            for strat, syms in strategy_symbols.items():
                if syms:
                    lines.append(f"<b>{strat}:</b> {', '.join(syms)}")
                    all_symbols.update(syms)
            lines.append(f"\nTotal únicos: {len(all_symbols)}")
            self.send("\n".join(lines))
            return

        if cmd == "/strategies":
            from strategy.signal_engine import ACTIVE_STRATEGIES
            from config import STRATEGY_INTERVALS
            strategy_symbols = st.strategy_symbols if hasattr(st, "strategy_symbols") else {}
            mode = st.strategy_mode if hasattr(st, "strategy_mode") else "unknown"

            lines = [f"<b>🔧 Estrategias (mode: {mode})</b>\n"]
            for name, info in ACTIVE_STRATEGIES.items():
                interval = STRATEGY_INTERVALS.get(name, "?")
                syms = strategy_symbols.get(name, [])
                status = "✅" if syms else "❌ sin símbolos"
                lines.append(f"<b>{info['short']} {name}</b> ({interval}) {status}")
                if syms:
                    lines.append(f"  → {', '.join(syms)}")

            self.send("\n".join(lines))
            return

        # ========================================================
        # SETTERS
        # ========================================================

        if cmd == "/set_leverage" and len(parts) >= 2:
            lev = int(clamp(int(parts[1]), 1, 20))
            st.leverage = lev
            self.db.save_state(st.__dict__)
            strategy_symbols = st.strategy_symbols if hasattr(st, "strategy_symbols") else {}
            all_symbols = set()
            for syms in strategy_symbols.values():
                all_symbols.update(syms)
            for s in all_symbols:
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

        # ========================================================
        # PANIC ATTACK
        # ======================================================== 

        if cmd == "/panic":
            panic_mode(st, exchange, self.db, self)
            return