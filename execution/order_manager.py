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
        signal_price = float(signal["price"])
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

        # ===== Spread Filter =====
        try:
            max_spread = float(getattr(CFG, "MAX_SPREAD_PCT", 0.10))
            cache_s = int(getattr(CFG, "SPREAD_CACHE_SECONDS", 3))

            if hasattr(self.exchange, "get_spread_pct"):
                sp = float(self.exchange.get_spread_pct(symbol, cache_seconds=cache_s))
                if sp > max_spread:
                    self.logger.warning(f"[SPREAD] {symbol} blocked: {sp:.3f}% > {max_spread}%")
                    return False
        except Exception as e:
            self.logger.warning(f"[SPREAD] could not validate spread {symbol}: {e}")
            return False

        # ===== Funding Filter =====
        try:
            funding_rate = float(self.exchange.get_funding_rate(symbol))
            if not funding_allowed(side, funding_rate):
                self.logger.warning(f"[FUNDING] {symbol} blocked. side={side} funding={funding_rate:.6f}")
                return False
        except Exception as e:
            self.logger.warning(f"[FUNDING] error {symbol}: {e}")
            return False

        # ===== Slippage Guard =====
        if not slippage_allowed(signal_price, mark_price):
            diff_ratio = abs(mark_price - signal_price) / signal_price if signal_price else 999
            self.logger.warning(
                f"[SLIPPAGE] {symbol} blocked. "
                f"signal={signal_price:.6f} mark={mark_price:.6f} diff={diff_ratio*100:.3f}%"
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
        # SE COMENTA PORQUE AL SER CUENTA CHICA NO DEJA ENTRAR NADA 
        # =====  control de capital simultáneo antes de auto-scale de margin =====
        #account = self.exchange.get_account_info()

        
        #total_wallet = float(account.get("totalWalletBalance", 0))
        #total_initial_margin = float(account.get("totalInitialMargin", 0))

        #if total_wallet > 0:
        #    usage_ratio = total_initial_margin / total_wallet

        #    if usage_ratio >= CFG.MAX_CAPITAL_USAGE:
        #        self.logger.warning(
        #            f"[CAPITAL] usage {usage_ratio:.2%} >= {CFG.MAX_CAPITAL_USAGE:.0%}. Skip {symbol}"
        #       )
        #       return False    

        # ============================================================
        # AUTO-SCALE MARGIN MANAGEMENT (Institutional version)
        # ============================================================

        try:
            if hasattr(self.exchange, "get_available_balance"):

                available = float(self.exchange.get_available_balance())
                lev = float(getattr(st, "leverage", 1) or 1)

                notional = mark_price * qty
                required_margin = notional / max(lev, 1.0)

                if required_margin > available:

                    scale_factor = (available * CFG.SAFETY_BUFFER) / required_margin

                    if scale_factor <= 0:
                        self.logger.warning(f"[MARGIN] {symbol} no available margin.")
                        return False

                    qty *= scale_factor
                    notional = mark_price * qty

                    required_margin = (notional / max(lev, 1.0))

                    if required_margin > available * CFG.SAFETY_BUFFER:
                        self.logger.warning(
                            f"[MARGIN] {symbol} still insufficient after scaling."
                        )
                        return False

                    self.logger.warning(
                        f"[MARGIN] {symbol} auto-scaled | "
                        f"scale={scale_factor:.3f} | new_qty={qty:.6f}"
                    )

                min_notional = float(getattr(CFG, "MIN_NOTIONAL_USDT", 5.0))
                if notional < min_notional:
                    self.logger.warning(
                        f"[MARGIN] {symbol} too small after scaling. notional={notional:.2f}"
                    )
                    return False
            # SE COMENTA PORQUE NO ME DEJA ENTRAR NINGUNA OPERACION
            # account = self.exchange.get_account_info()

            # total_wallet = float(account.get("totalWalletBalance", 0))
            # total_initial_margin = float(account.get("totalInitialMargin", 0))
            # available = float(account.get("availableBalance", 0))

            # lev = float(getattr(st, "leverage", 1) or 1)
            # notional = mark_price * qty
            # required_margin = notional / max(lev, 1.0)

            # # 1️⃣ Hard capital usage guard
            # if total_wallet > 0:
            #     usage_ratio = total_initial_margin / total_wallet
            #     if usage_ratio >= CFG.MAX_CAPITAL_USAGE:
            #         self.logger.warning(
            #             f"[CAPITAL] usage {usage_ratio:.2%} >= {CFG.MAX_CAPITAL_USAGE:.0%}. Skip {symbol}"
            #         )
            #         return False

            # # 2️⃣ Margin sufficiency check
            # if required_margin > available: # * CFG.SAFETY_BUFFER: esto esta cagando todo

            #     scale_factor = available / required_margin # antes (available * CFG.SAFETY_BUFFER) / required_margin

            #     if scale_factor <= 0:
            #         self.logger.warning(f"[MARGIN] {symbol} no available margin.")
            #         return False

            #     qty *= scale_factor
            #     notional = mark_price * qty
            #     required_margin = notional / max(lev, 1.0)

            #     if required_margin > available: # * CFG.SAFETY_BUFFER: por misma razon que arriba
            #         self.logger.warning(
            #             f"[MARGIN] {symbol} insufficient after scaling."
            #         )
            #         return False

            #     self.logger.warning(
            #         f"[MARGIN] {symbol} auto-scaled | "
            #         f"scale={scale_factor:.3f} | new_qty={qty:.6f}"
            #     )

            # # 3️⃣ Minimum notional
            # min_notional = float(getattr(CFG, "MIN_NOTIONAL_USDT", 10.0))
            # if notional < min_notional:
            #     self.logger.warning(
            #         f"[MARGIN] {symbol} too small after scaling. notional={notional:.2f}"
            #     )
            #     return False

        except Exception as e:
            self.logger.warning(f"[MARGIN] validation error {symbol}: {e}")
            return False
            
        # ============================================================
        # EXECUTE MARKET ORDER
        # ============================================================

        try:
            order = self.exchange.place_market_order(
                symbol=symbol,
                side=side,
                quantity=qty
            )

            if not order:
                self.logger.warning(f"{symbol} market order returned None")
                return False

            self.trade_lock.mark_entered(symbol, bar_close_ms)
            self.logger.info(f"[ENTRY] {symbol} {side} qty={qty:.6f}")

        except Exception:
            self.logger.exception("[ENTRY] Order execution failed.")
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

        # ============================================================
        # INITIAL STOP (NO INVALIDA ENTRY)
        # ============================================================

        if initial_sl is not None:
            try:
                self.replace_stop_order(st, symbol, side, qty, float(initial_sl))
                self.logger.info(
                    f"[SL] initial stop placed {symbol} {side} sl={float(initial_sl)}"
                )
            except Exception as e:
                self.logger.warning(f"[SL] stop creation failed {symbol}: {e}")
        else:
            self.logger.warning(
                f"[SL] {symbol} entered WITHOUT initial stop (initial_sl=None)"
            )

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