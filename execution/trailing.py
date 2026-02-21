# execution/trailing.py

import time
import config as CFG
from db import Database


class TrailingManager:
    def __init__(self, exchange, market, order_manager, db, tg_send, logger):
        self.exchange = exchange
        self.market = market
        self.order_manager = order_manager
        self.db = db
        self.tg_send = tg_send
        self.log = logger

    def loop_once(self, st):
        try:
            positions = self.exchange.get_open_positions()

            for p in positions:
                symbol = p.get("symbol")
                if not symbol:
                    continue
                if symbol not in st.symbols:
                    continue

                self.update_trailing(st, symbol, p)

        except Exception as e:
            self.tg_send(f"⚠️ Trailing error: {type(e).__name__}: {str(e)[:120]}")

    def update_trailing(self, st, symbol: str, position: dict):
        """
        position esperado:
        {
            "symbol": "BTCUSDT",
            "side": "LONG"|"SHORT",
            "size": float,
            "entry_price": float
        }
        """

        qty = float(position.get("size", 0.0))
        entry = float(position.get("entry_price", 0.0))
        side = str(position.get("side", "NONE"))

        if qty <= 0 or entry <= 0:
            # ================= DB CLOSE POSITION =================

            position_id = getattr(st, "position_ids", {}).get(symbol)

            if position_id:
                try:
                    # Obtener precio actual como aproximación de salida
                    exit_price = float(self.exchange.get_mark_price(symbol) or 0.0)

                    self.db.close_position(
                        position_id=position_id,
                        exit_price=exit_price,
                        realized_pnl=None  # lo podemos calcular después con precisión
                    )

                    self.db.deactivate_stops(position_id)

                    st.position_ids.pop(symbol, None)

                except Exception as e:
                    self.log.warning(f"{symbol} DB close failed: {e}")

            # limpiar estado memoria
            st.trail.pop(symbol, None)
            st.stop_orders.pop(symbol, None)

            self.db.save_state(st.__dict__)

            return

        direction = side  # "LONG" | "SHORT"

        mp = float(self.market.get_mark_price_cached(symbol) or 0.0)
        if mp <= 0:
            mp = float(self.exchange.get_mark_price(symbol) or 0.0)
        if mp <= 0:
            return

        is_long = direction == "LONG"

        pnl_pct = (mp - entry) / entry * 100.0 if is_long else (entry - mp) / entry * 100.0

        # todavía no activar trailing
        if pnl_pct < CFG.TRAILING_ACTIVATION_PCT:
            if symbol not in st.trail:
                st.trail[symbol] = {
                    "direction": direction,
                    "entry": entry,
                    "qty": qty,
                    "best": mp,
                    "sl": None,
                    "activated": False
                }
                self.db.save_state(st.__dict__)
            return

        # activar trailing
        if symbol not in st.trail:
            st.trail[symbol] = {
                "direction": direction,
                "entry": entry,
                "qty": qty,
                "best": mp,
                "sl": None,
                "activated": True
            }

        tr = st.trail[symbol]
        tr["direction"] = direction
        tr["qty"] = qty
        tr["activated"] = True

        use_atr = bool(getattr(CFG, "TRAILING_USE_ATR", False))
        atr_mult = float(getattr(CFG, "TRAILING_ATR_MULT", 1.5))

        old_sl = tr.get("sl")

        if direction == "LONG":
            tr["best"] = max(float(tr.get("best", mp)), mp)

            if use_atr:
                atr = float(self.market.get_last_atr(symbol) or 0.0)
                if atr <= 0:
                    return
                new_sl = tr["best"] - (atr * atr_mult)
            else:
                new_sl = tr["best"] * (1 - st.trailing_pct / 100.0)

        else:
            tr["best"] = min(float(tr.get("best", mp)), mp)

            if use_atr:
                atr = float(self.market.get_last_atr(symbol) or 0.0)
                if atr <= 0:
                    return
                new_sl = tr["best"] + (atr * atr_mult)
            else:
                new_sl = tr["best"] * (1 + st.trailing_pct / 100.0)

        # primer SL de trailing
        if old_sl is None:

            result = self.order_manager.replace_stop_order(st, symbol, direction, qty, float(new_sl))
            if not result:
                return

            tr["sl"] = float(new_sl)
            self.db.save_state(st.__dict__)

            self.tg_send(
                f"🔒 <b>Trailing activado</b> {symbol} {direction}\n"
                f"Mark: {mp:.4f}\n"
                f"SL inicial: {new_sl:.4f}\n"
                f"PnL: {pnl_pct:.2f}%"
            )
            return

        should_update = (direction == "LONG" and new_sl > old_sl) or (direction == "SHORT" and new_sl < old_sl)

        if should_update:

            result = self.order_manager.replace_stop_order(st, symbol, direction, qty, float(new_sl))
            if not result:
                return

            tr["sl"] = float(new_sl)
            self.db.save_state(st.__dict__)
 