# execution/order_manager.py

import config as CFG

from core.trade_lock import TradeLock
from execution.slippage_guard import slippage_allowed
from risk.funding_filter import funding_allowed


class OrderManager:

    def __init__(self, exchange, logger, db, tg_send=None):
        self.exchange = exchange
        self.logger = logger
        self.db = db
        self.tg_send = tg_send

        self.trade_lock = TradeLock(
            min_seconds_between_entries=getattr(CFG, "MIN_SECONDS_BETWEEN_ENTRIES", 45)
        )

    # ============================================================
    # REPLACE STOP (Trailing Compatible + DB)
    # ============================================================

    def replace_stop_order(self, st, symbol: str, position_side: str, qty: float, new_sl: float):
        # Convertir dirección de posición a lado de orden
        if position_side == "LONG":
            order_side = "SELL"   # stop para cerrar long
        elif position_side == "SHORT":
            order_side = "BUY"    # stop para cerrar short
        else:
            self.logger.error(f"{symbol} invalid position_side={position_side}")
            return False

        try:
            existing = st.stop_orders.get(symbol)
            # 1️⃣ Cancelar stop anterior si existe
            if existing:
                old_id = existing.get("order_id")
                is_algo = existing.get("is_algo", False)
                if old_id:
                    try:
                        if is_algo:
                            self.exchange.cancel_algo_order(symbol, old_id)
                        else:
                            self.exchange.cancel_order(symbol, old_id)
                    except Exception as e:
                        msg = str(e)
                        # FIX: Si la orden ya no existe (se ejecutó o canceló), no fallar
                        if "-2011" in msg or "Unknown order" in msg:
                            self.logger.warning(f"{symbol} Stop anterior ya no existe (ok), continuando...")
                        else:
                            self.logger.warning(f"{symbol} stop cancel warning: {e}")

            # 2️⃣ Crear nuevo STOP_MARKET (closePosition=False)
            stop_order = self.exchange.place_reduce_only_stop(
                symbol=symbol,
                side=order_side,
                quantity=qty,
                stop_price=new_sl
            )
            if not stop_order:
                self.logger.warning(f"{symbol} new stop not created")
                return False

            # Extraer algoId (NO orderId)
            algo_id = stop_order.get("algoId")
            if not algo_id:
                self.logger.error(f"{symbol} stop algoId missing. response={stop_order}")
                return False

            # 3️⃣ Guardar estado correctamente
            st.stop_orders[symbol] = {
                "order_id": int(algo_id),
                "is_algo": True,
                "stop_price": float(new_sl)
            }
            self.db.save_state(st.__dict__)

            # 4️⃣ DB integración
            position_id = st.position_ids.get(symbol)
            if position_id:
                self.db.deactivate_stops(position_id)
                self.db.create_stop(
                    position_id=position_id,
                    stop_price=new_sl,
                    exchange_algo_id=algo_id
                )
                self.db.create_order(
                    position_id=position_id,
                    symbol=symbol,
                    side=order_side,
                    order_type="STOP_MARKET",
                    is_reduce_only=True,
                    is_close_position=True,
                    exchange_order_id=None,
                    exchange_algo_id=algo_id,
                    is_algo=True,
                    price=None,
                    stop_price=new_sl,
                    status="NEW",
                    raw_response=stop_order
                )

            self.logger.info(f"{symbol} SL updated -> {new_sl:.4f} (algoId={algo_id})")

            # 🆕 ========== NOTIFICACIÓN TELEGRAM (NUEVO) ==========
            if self.tg_send:
                try:
                    # Obtener precio actual para mostrar distancia al SL
                    mark_price = float(self.exchange.get_mark_price(symbol))
                    distance_pct = abs(mark_price - new_sl) / mark_price * 100
                    
                    emoji = "📈" if position_side == "LONG" else "📉"
                    self.tg_send(
                        f"{emoji} <b>Stop Loss Actualizado</b>\n"
                        f"{symbol} {position_side}\n"
                        f"Nuevo SL: {new_sl:.4f}\n"
                        f"Mark: {mark_price:.4f}\n"
                        f"Distancia: {distance_pct:.2f}%"
                    )
                except Exception as e:
                    self.logger.warning(f"[TG SL NOTIFY] {e}")
            # 🆕 ========== FIN NOTIFICACIÓN ==========

            return stop_order

        except Exception as e:
            self.logger.exception(f"{symbol} replace_stop_order failed: {e}")
            return False
    
    # ============================================================
    # MAIN EXECUTE
    # ============================================================

    def execute(self, st, signal: dict):
        symbol = signal["symbol"]
        side = signal["side"]
        signal_price = float(signal.get("price", 0))
        qty = float(signal["qty"])
        bar_close_ms = int(signal.get("bar_close_ms", 0))
        initial_sl = signal.get("initial_sl", None)

        # ===== Trade Lock =====
        if not self.trade_lock.can_enter(symbol, bar_close_ms):
            self.logger.warning(f"[LOCK] {symbol} blocked duplicate entry.")
            return False

        # ===== Verificar posición real =====
        try:
            open_pos = self.exchange.get_open_positions(symbol=symbol)
            if open_pos and len(open_pos) > 0:
                self.logger.warning(f"[LOCK] {symbol} already has open position.")
                return False
        except Exception as e:
            self.logger.warning(f"[SAFETY] {symbol} could not verify open positions. Abort. err={e}")
            return False

        # ===== Mark Price =====
        try:
            mark_price = float(self.exchange.get_mark_price(symbol))
        except Exception as e:
            self.logger.warning(f"[MARK] {symbol} mark price error: {e}")
            return False

        # ===== Spread Filter Dinámico =====
        try:
            base_spread = float(getattr(CFG, "MAX_SPREAD_PCT", 0.10))
            # Obtener volatilidad actual (ATR %)
            atr_pct = self.exchange.get_atr_pct(symbol) # Usa la función que ya tienes en binance_futures.py
            
            # Si la volatilidad es alta, permitimos más spread (ej. 0.10% + 50% del ATR)
            dynamic_max_spread = base_spread + (atr_pct * 0.5) 
            
            cache_s = int(getattr(CFG, "SPREAD_CACHE_SECONDS", 3))
            if hasattr(self.exchange, "get_spread_pct"):
                sp = float(self.exchange.get_spread_pct(symbol, cache_seconds=cache_s))
                if sp > dynamic_max_spread:
                    self.logger.warning(f"[SPREAD] {symbol} blocked: {sp:.3f}% > dynamic_limit {dynamic_max_spread:.3f}%")
                    return False
        except Exception as e:
            self.logger.warning(f"[SPREAD] could not validate spread {symbol}: {e}")
            # No bloquear si falla el cálculo, ser permisivo
            # return False 

        # ===== Funding Filter =====
        try:
            funding_rate = float(self.exchange.get_funding_rate(symbol))
            if not funding_allowed(side, funding_rate):
                self.logger.warning(f"[FUNDING] {symbol} blocked. side={side} funding={funding_rate:.6f}")
                return False
        except Exception as e:
            self.logger.warning(f"[FUNDING] error {symbol}: {e}")
            return False

        # ===== Slippage Guard Dinámico =====
        base_slippage = float(getattr(CFG, "MAX_SLIPPAGE_RATIO", 0.003))
        # Si hay alta volatilidad (ATR > 0.3%), permitimos más slippage
        atr_pct = self.exchange.get_atr_pct(symbol) if hasattr(self.exchange, "get_atr_pct") else 0.2
        dynamic_slippage = base_slippage + min(atr_pct * 0.5, 0.002)  # Máximo +0.2%
        
        # LOG PARA DEBUG
        self.logger.info(f"[SLIPPAGE] {symbol} price={signal_price:.6f} mark={mark_price:.6f} atr_pct={atr_pct:.4f}%")

        if not slippage_allowed(signal_price, mark_price, max_ratio=dynamic_slippage):
            diff_ratio = abs(mark_price - signal_price) / signal_price if signal_price else 999
            self.logger.warning(
                f"[SLIPPAGE] {symbol} blocked. "
                f"signal={signal_price:.2f} mark={mark_price:.2f} diff={diff_ratio*100:.3f}% > limit {dynamic_slippage*100:.3f}%"
            )
            return False

        # ===== Equity Check =====
        try:
            equity = float(self.exchange.get_equity())
            if equity <= 0:
                self.logger.warning("[SAFETY] Equity zero.")
                return False
        except Exception as e:
            self.logger.warning(f"[SAFETY] Equity fetch error: {e}")
            return False
        
        # ============================================================
        # LOGICA ACTIVA (MIN NOTIONAL + MARGIN SCALE)
        # ============================================================
        try:
            if hasattr(self.exchange, "get_available_balance"):
                available = float(self.exchange.get_available_balance())
                lev = float(getattr(st, "leverage", 1) or 1)

                # 0. Buffer de seguridad para margen (evita APIError -2019)
                margin_buffer = float(getattr(CFG, "MARGIN_SAFETY_BUFFER", 0.03))
                available_with_buffer = available * (1 - margin_buffer)
                
                # 1. Asegurar Mínimo Notional de Binance (CRÍTICO PARA CUENTAS < $200)
                min_notional = float(getattr(CFG, "MIN_NOTIONAL_USDT", 20.0))
                current_notional = mark_price * qty
                
                if current_notional < min_notional:
                    # Ajustar qty para cumplir el mínimo obligatorio de Binance
                    qty = min_notional / mark_price
                    self.logger.warning(f"[MIN NOTIONAL] {symbol} ajustado a {qty:.4f} para cumplir min {min_notional}")
                
                # 2. Recalcular margen requerido con qty ajustada con Buffer
                notional = mark_price * qty
                required_margin = notional / max(lev, 1.0)
                
                # 3. Verificar Margen (Sin bloqueo estricto de SAFETY_BUFFER para cuentas pequeñas)
                if required_margin > available_with_buffer:
                    # Intentar escalar hacia abajo si no hay margen suficiente
                    scale_factor = available_with_buffer / required_margin
                    if scale_factor <= 0.1: # Si hay menos del 10% del margen necesario, abortar
                        self.logger.warning(f"[MARGIN] {symbol} insuficiente incluso escalando.")
                        return False
                    
                    qty *= scale_factor
                    notional = mark_price * qty
                    required_margin = notional / max(lev, 1.0)
                    self.logger.warning(
                        f"[MARGIN] {symbol} auto-scaled | "
                        f"scale={scale_factor:.3f} | "
                        f"new_qty={qty:.6f} | "
                        f"available_orig={available:.2f} | "
                        f"available_buffered={available_with_buffer:.2f}"
                    )
                    
                    # Verificar nuevamente que tras escalar no violamos el mínimo notional
                    if notional < min_notional:
                        self.logger.warning(f"[MARGIN] {symbol} demasiado pequeño tras escalar. Abort.")
                        return False

        except Exception as e:
            self.logger.warning(f"[MARGIN] validation error {symbol}: {e}")
            return False

        # ============================================================
        # EXECUTE MARKET ORDER + SL INMEDIATO
        # ============================================================
        # 1. Ejecutar entrada market
        order = self.exchange.place_market_order(
            symbol=symbol,
            side=side,
            quantity=qty
        )
        if not order:
            self.logger.warning(f"{symbol} market order returned None")
            return False

        # ================= DB: CREAR POSICIÓN =================
        position_id = self.db.create_position(
            symbol=symbol,
            side=side,
            qty=qty,
            entry_price=mark_price
        )

        if not hasattr(st, "position_ids"):
            st.position_ids = {}
        st.position_ids[symbol] = position_id

        # ===== PERSISTIR FEATURES PARA ML =====
        ml_features = signal.get("ml_features")
        if ml_features and isinstance(ml_features, dict):
            try:
                self.db.update_position_features(
                    position_id=position_id,
                    features=ml_features
                )
                self.logger.debug(f"[ML] Features guardados {symbol} pos_id={position_id}")
            except Exception as e:
                self.logger.warning(f"[ML] Error guardando features {symbol}: {e}")

        # 2. COLOCAR SL (YA tiene position_id)
        if initial_sl is not None:
            try:
                sl_result = self.replace_stop_order(st, symbol, side, qty, float(initial_sl))
                if sl_result:
                    self.logger.info(f"[SL] initial stop placed {symbol} {side} sl={float(initial_sl):.4f}")
                else:
                    self.logger.error(f"[SL WARNING] {symbol} stop creation returned False")
            except Exception as e:
                self.logger.error(f"[SL CRITICAL] {symbol} stop creation exception: {e}")

        # 3. Recién ahora marcar como entered y loguear
        self.trade_lock.mark_entered(symbol, bar_close_ms)
        sl_display = f"{float(initial_sl):.2f}" if initial_sl is not None else "N/A"
        self.logger.info(f"[ENTRY] {symbol} {side} qty={qty:.6f} @ {mark_price:.2f} SL={sl_display}")

        self.db.create_order(
            position_id=position_id,
            symbol=symbol,
            side=side,
            order_type="MARKET",
            is_reduce_only=False,
            is_close_position=False,
            exchange_order_id=order.get("orderId"),
            exchange_algo_id=None,
            is_algo=False,
            price=mark_price,
            stop_price=None,
            status=order.get("status"),
            raw_response=order
        )
        self.db.save_state(st.__dict__)

        # ===== Telegram =====
        if self.tg_send:
            try:
                sl_txt = f"{initial_sl:.4f}" if initial_sl else "N/A"
                self.tg_send(
                    f"📈 <b>Nueva posición</b>\n"
                    f"{symbol} {side}\n"
                    f"Entry: {mark_price:.4f}\n"
                    f"Qty: {qty:.6f}\n"
                    f"SL: {sl_txt}"
                )
            except Exception as e:
                self.logger.warning(f"[TELEGRAM] send failed: {e}")
        return order 