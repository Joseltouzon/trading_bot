# execution/take_profit_manager.py
import time
import config as CFG
from db import Database

class TakeProfitManager:
    """
    Gestiona Take Profit escalonado con cierres parciales.
    
    Funcionamiento:
    - Evalúa R:R actual vs niveles configurados
    - Ejecuta cierres parciales cuando se alcanza un nivel
    - Opcionalmente mueve SL a Breakeven tras primer TP
    - Compatible con TrailingManager (no compiten)
    """
    
    def __init__(self, exchange, market, order_manager, db, tg_send, logger):
        self.exchange = exchange
        self.market = market
        self.om = order_manager
        self.db = db
        self.tg_send = tg_send
        self.log = logger
        
        # Trackear niveles ya ejecutados por símbolo: {symbol: {tp_index: timestamp}}
        self._tp_executed = {}
        # Throttle por símbolo para evitar spam de API
        self._last_tp_action = {}
        
    def loop_once(self, st):
        """Iterar sobre posiciones abiertas y evaluar niveles de TP"""
        try:
            positions = self.exchange.get_open_positions()
            for p in positions:
                symbol = p.get("symbol")
                if not symbol or symbol not in st.symbols:
                    continue
                    
                # Saltar si está en cooldown de TP
                if self._is_throttled(symbol):
                    continue
                    
                self._evaluate_tps(st, symbol, p)
                
        except Exception as e:
            self.log.error(f"[TP MANAGER] loop error: {e}")
            if self.tg_send:
                self.tg_send(f"⚠️ TP Manager error: {str(e)[:100]}")
    
    def _is_throttled(self, symbol: str) -> bool:
        """Verificar throttle de API por símbolo"""
        now = time.time()
        last = self._last_tp_action.get(symbol, 0)
        throttle = float(getattr(CFG, "TP_THROTTLE_SECONDS", 10))
        return (now - last) < throttle
    
    def _update_throttle(self, symbol: str):
        """Actualizar timestamp de última acción de TP"""
        self._last_tp_action[symbol] = time.time()
    
    def _evaluate_tps(self, st, symbol: str, position: dict):
        """Calcular R:R actual y ejecutar cierres parciales si corresponde"""
        
        # === Datos de la posición ===
        side = position.get("side")  # "LONG" | "SHORT"
        entry = float(position.get("entry_price", 0))
        current_qty = float(position.get("size", 0))
        position_id = st.position_ids.get(symbol)
        
        if entry <= 0 or current_qty <= 0 or not position_id:
            return
        
        # === Precio actual ===
        use_mark = bool(getattr(CFG, "TP_USE_MARK_PRICE", True))
        if use_mark:
            mp = float(self.market.get_mark_price_cached(symbol) or 0)
            if mp <= 0:
                mp = float(self.exchange.get_mark_price(symbol) or 0)
        else:
            mp = float(self.exchange.get_ticker_price(symbol) or 0)
        
        if mp <= 0:
            return
        
        # === Calcular Riesgo Inicial (Entry - SL_original) ===
        # Buscamos el SL inicial en el historial de trail o en DB
        initial_sl = self._get_initial_sl(st, symbol, position_id)
        if initial_sl is None:
            # Fallback: usar ATR * mult como estimación
            atr = float(self.market.get_last_atr(symbol) or 0)
            if atr <= 0:
                return
            sl_mult = float(getattr(CFG, "INITIAL_SL_ATR_MULT", 2.0))
            initial_sl = entry - (atr * sl_mult) if side == "LONG" else entry + (atr * sl_mult)
        
        risk = abs(entry - initial_sl)
        if risk <= 0:
            return
        
        # === Calcular R:R actual ===
        if side == "LONG":
            current_r = (mp - entry) / risk
        else:  # SHORT
            current_r = (entry - mp) / risk
        
        # === Evaluar cada nivel de TP ===
        tp_levels = getattr(CFG, "TP_LEVELS", [])
        if not tp_levels:
            return
        
        for i, tp in enumerate(tp_levels):
            tp_ratio = float(tp.get("ratio", 1.5))
            close_pct = float(tp.get("close_pct", 50))
            move_to_be = bool(tp.get("move_sl_to_be", False))
            
            # Verificar si ya se ejecutó este nivel
            if self._was_tp_executed(symbol, i):
                continue
            
            # Verificar si alcanzamos el R:R necesario
            if current_r >= tp_ratio:
                self._execute_partial_close(
                    st, symbol, position, 
                    tp_ratio, close_pct, move_to_be, current_r
                )
                self._mark_tp_executed(symbol, i)
                self._update_throttle(symbol)
                break  # Ejecutar solo un nivel por ciclo (evitar múltiples órdenes)
    
    def _get_initial_sl(self, st, symbol: str, position_id: int) -> float:
        """
        Obtener el SL inicial de la posición (antes de cualquier trailing).
        Prioridad: 1) DB position_stops histórico, 2) st.trail snapshot, 3) None
        """
        try:
            # Intentar obtener desde DB: primer stop registrado para esta posición
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT stop_price 
                    FROM position_stops 
                    WHERE position_id = %s 
                    ORDER BY created_at ASC 
                    LIMIT 1
                """, (position_id,))
                row = cur.fetchone()
                if row and row["stop_price"]:
                    return float(row["stop_price"])
        except Exception as e:
            self.log.warning(f"[TP] DB query for initial SL failed: {e}")
        
        # Fallback: usar el SL actual en memoria (no ideal pero funcional)
        if hasattr(st, "trail") and symbol in st.trail:
            sl = st.trail[symbol].get("sl")
            if sl:
                return float(sl)
        
        return None
    
    def _execute_partial_close(self, st, symbol: str, position: dict, 
                             tp_ratio: float, close_pct: float, 
                             move_to_be: bool, current_r: float):
        """Ejecutar cierre parcial y ajustar SL si corresponde"""
        
        side = position.get("side")
        entry = float(position["entry_price"])
        total_qty = float(position["size"])
        position_id = st.position_ids.get(symbol)
        
        # Calcular cantidad a cerrar
        close_qty = total_qty * (close_pct / 100.0)
        remaining_qty = total_qty - close_qty
        
        # Validaciones de Binance
        min_notional = float(getattr(CFG, "MIN_NOTIONAL_USDT", 20))
        mp = float(self.exchange.get_mark_price(symbol) or 0)
        
        if mp * close_qty < min_notional:
            self.log.warning(f"[TP] {symbol} partial qty too small for Binance min_notional")
            return
        
        try:
            # === 1. Ejecutar orden de cierre parcial ===
            order_side = "SELL" if side == "LONG" else "BUY"
            
            close_order = self.exchange.place_market_order(
                symbol=symbol,
                side=order_side,
                quantity=close_qty,
                reduce_only=True  # ← CRÍTICO: solo cierra, no abre posición opuesta
            )
            
            if not close_order:
                self.log.error(f"[TP] {symbol} partial close order failed")
                return
            
            self.log.info(
                f"[TP EXEC] {symbol} {side} | "
                f"TP@{tp_ratio}R | "
                f"closed={close_qty:.6f} | "
                f"remaining={remaining_qty:.6f}"
            )
            
            # === 2. Actualizar DB: posición y evento ===
            if position_id:
                # Actualizar cantidad restante
                self.db.update_position_qty(position_id, remaining_qty)
                
                # Registrar evento de TP
                self.db.create_position_event(
                    position_id=position_id,
                    event_type="TAKE_PROFIT",
                    payload={
                        "tp_ratio": tp_ratio,
                        "close_pct": close_pct,
                        "closed_qty": close_qty,
                        "remaining_qty": remaining_qty,
                        "price": mp,
                        "current_r": round(current_r, 2)
                    }
                )
                
                # === 3. Mover SL a Breakeven si está configurado ===
                if move_to_be and remaining_qty > 0:
                    self._move_sl_to_breakeven(st, symbol, position_id, side, remaining_qty, entry)
                
                # Persistir estado
                self.db.save_state(st.__dict__)
            
            # === 4. Notificación Telegram ===
            if self.tg_send:
                emoji = "🎯" if close_pct >= 50 else "✨"
                be_txt = " + SL a BE ✅" if move_to_be else ""
                self.tg_send(
                    f"{emoji} <b>TP Hit</b> {symbol} {side}\n"
                    f"Nivel: {tp_ratio}R\n"
                    f"Cerrado: {close_pct}% ({close_qty:.6f})\n"
                    f"Restante: {remaining_qty:.6f}{be_txt}\n"
                    f"PnL parcial: {self._calc_pnl(side, entry, mp, close_qty):+.2f} USDT"
                )
            
        except Exception as e:
            self.log.exception(f"[TP EXEC] Error in partial close {symbol}: {e}")
            if self.tg_send:
                self.tg_send(f"⚠️ TP error {symbol}: {str(e)[:80]}")
    
    def _move_sl_to_breakeven(self, st, symbol: str, position_id: int, 
                            side: str, qty: float, entry: float):
        """
        Mover SL a Breakeven SOLO si es mejor que el SL actual.
        NUNCA bajar un SL que ya está en ganancia.
        """
        
        try:
            # === 1. Obtener SL actual (el que ya tiene la posición) ===
            current_sl = None
            
            # Prioridad 1: st.trail (memoria, tiene el último SL del trailing)
            if hasattr(st, "trail") and symbol in st.trail:
                current_sl = st.trail[symbol].get("sl")
            
            # Prioridad 2: st.stop_orders (orden activa en Binance)
            if current_sl is None and hasattr(st, "stop_orders"):
                current_sl = st.stop_orders.get(symbol, {}).get("stop_price")
            
            # === 2. Calcular Breakeven con buffer ===
            buffer_pct = float(getattr(CFG, "SL_BUFFER_PCT", 0.0012))
            
            if side == "LONG":
                be_sl = entry * (1 + buffer_pct)  # SL ligeramente ABOVE entry para LONG
                # ✅ VALIDACIÓN CRÍTICA: Solo mover si el nuevo SL es MAYOR que el actual
                if current_sl and be_sl <= current_sl:
                    self.log.info(
                        f"[TP BE] {symbol} SL actual ({current_sl:.4f}) ya es mejor "
                        f"que BE ({be_sl:.4f}). No se mueve."
                    )
                    return  # ← SALIR SIN MOVER
                new_sl = be_sl
                
            else:  # SHORT
                be_sl = entry * (1 - buffer_pct)  # SL ligeramente BELOW entry para SHORT
                # ✅ VALIDACIÓN CRÍTICA: Solo mover si el nuevo SL es MENOR que el actual
                if current_sl and be_sl >= current_sl:
                    self.log.info(
                        f"[TP BE] {symbol} SL actual ({current_sl:.4f}) ya es mejor "
                        f"que BE ({be_sl:.4f}). No se mueve."
                    )
                    return  # ← SALIR SIN MOVER
                new_sl = be_sl
            
            # === 3. Ejecutar movimiento (solo si llegamos acá) ===
            result = self.om.replace_stop_order(st, symbol, side, qty, new_sl)
            
            if result:
                self.log.info(
                    f"[TP BE] {symbol} SL movido a BE: {current_sl:.4f} → {new_sl:.4f}"
                )
                
                # Actualizar st.trail para consistencia
                if hasattr(st, "trail") and symbol in st.trail:
                    st.trail[symbol]["sl"] = new_sl
                    st.trail[symbol]["activated"] = True
                    # Persistir el cambio en trail
                    self.db.save_state(st.__dict__)
                
                # Notificación Telegram
                if self.tg_send:
                    self.tg_send(
                        f"🛡️ <b>SL Protegido</b> {symbol} {side}\n"
                        f"SL anterior: {current_sl:.4f}\n"
                        f"SL nuevo: {new_sl:.4f}\n"
                        f"<i>Trailing ya había protegido, pero TP mejora SL actual</i>"
                    )
                    
        except Exception as e:
            self.log.warning(f"[TP BE] Error moving SL to BE {symbol}: {e}")
    
    def _was_tp_executed(self, symbol: str, tp_index: int) -> bool:
        """Verificar si un nivel de TP ya fue ejecutado para este símbolo"""
        if symbol not in self._tp_executed:
            self._tp_executed[symbol] = {}
        return tp_index in self._tp_executed[symbol]
    
    def _mark_tp_executed(self, symbol: str, tp_index: int):
        """Marcar un nivel de TP como ejecutado"""
        if symbol not in self._tp_executed:
            self._tp_executed[symbol] = {}
        self._tp_executed[symbol][tp_index] = time.time()
    
    def _calc_pnl(self, side: str, entry: float, exit_price: float, qty: float) -> float:
        """Calcular PnL simple para notificaciones"""
        if side == "LONG":
            return (exit_price - entry) * qty
        else:
            return (entry - exit_price) * qty
    
    def reset_symbol(self, symbol: str):
        """Limpiar estado de TP para un símbolo (útil al cerrar posición)"""
        if symbol in self._tp_executed:
            del self._tp_executed[symbol]
        if symbol in self._last_tp_action:
            del self._last_tp_action[symbol]