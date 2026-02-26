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
        # Throttle para no spamear la API de Binance (5 segundos por símbolo)
        self._last_update = {} 

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
        Gestiona el Trailing Stop con protección contra restarts y rate limits.
        """
        qty = float(position.get("size", 0.0))
        entry = float(position.get("entry_price", 0.0))
        side = str(position.get("side", "NONE"))
        direction = side  # "LONG" | "SHORT"
        
        # Obtener Mark Price
        mp = float(self.market.get_mark_price_cached(symbol) or 0.0)
        if mp <= 0:
            mp = float(self.exchange.get_mark_price(symbol) or 0.0)
        if mp <= 0:
            return

        is_long = direction == "LONG"
        pnl_pct = (mp - entry) / entry * 100.0 if is_long else (entry - mp) / entry * 100.0

        # --- FIX 1: Inicialización segura tras restart ---
        # Si no existe registro en memoria/DB pero hay posición, inicializar desde entry_price
        # para no perder el "mejor precio" histórico si el bot se cayó.
        if symbol not in st.trail:
            st.trail[symbol] = {
                "direction": direction,
                "entry": entry,
                "qty": qty,
                "best": entry,  # <--- CAMBIO CRÍTICO: Usar entry como base segura
                "sl": None,
                "activated": False
            }
            self.db.save_state(st.__dict__)
            # No retornamos, dejamos que continúe para evaluar activación
        
        tr = st.trail[symbol]
        tr["direction"] = direction
        tr["qty"] = qty

        # --- Verificar Activación ---
        if pnl_pct < CFG.TRAILING_ACTIVATION_PCT:
            tr["activated"] = False
            # Actualizamos best aunque no esté activado, para tener el dato listo
            if direction == "LONG":
                tr["best"] = max(float(tr.get("best", entry)), mp)
            else:
                tr["best"] = min(float(tr.get("best", entry)), mp)
            return

        # --- Activar Trailing ---
        if not tr.get("activated", False):
            tr["activated"] = True
            self.log.info(f"[TRAILING] Activado {symbol} {direction} PnL:{pnl_pct:.2f}%")

        # --- Throttle de API ---
        now = time.time()
        last_update = self._last_update.get(symbol, 0)
        if now - last_update < 5.0:  # Solo actualizar cada 5 segundos
            return

        use_atr = bool(getattr(CFG, "TRAILING_USE_ATR", False))
        atr_mult = float(getattr(CFG, "TRAILING_ATR_MULT", 1.5))
        old_sl = tr.get("sl")

        # Calcular Nuevo SL
        if direction == "LONG":
            tr["best"] = max(float(tr.get("best", mp)), mp)
            if use_atr:
                atr = float(self.market.get_last_atr(symbol) or 0.0)
                if atr <= 0: return
                new_sl = tr["best"] - (atr * atr_mult)
            else:
                new_sl = tr["best"] * (1 - st.trailing_pct / 100.0)
        else: # SHORT
            tr["best"] = min(float(tr.get("best", mp)), mp)
            if use_atr:
                atr = float(self.market.get_last_atr(symbol) or 0.0)
                if atr <= 0: return
                new_sl = tr["best"] + (atr * atr_mult)
            else:
                new_sl = tr["best"] * (1 + st.trailing_pct / 100.0)

        # Ejecutar Movimiento
        should_update = False
        if old_sl is None:
            should_update = True
        else:
            # Solo mover si es favorable (subir SL en Long, bajar en Short)
            should_update = (direction == "LONG" and new_sl > old_sl) or \
                            (direction == "SHORT" and new_sl < old_sl)

        if should_update:
            result = self.order_manager.replace_stop_order(st, symbol, direction, qty, float(new_sl))
            if result:
                tr["sl"] = float(new_sl)
                self._last_update[symbol] = now # Actualizar timestamp solo si hubo éxito
                self.db.save_state(st.__dict__)
                
                if old_sl is None:
                    self.tg_send(
                        f"🔒 <b>Trailing activado</b> {symbol} {direction}\n"
                        f"Mark: {mp:.4f}\nSL inicial: {new_sl:.4f}\nPnL: {pnl_pct:.2f}%"
                    )