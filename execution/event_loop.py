# execution/event_loop.py

import time
import config as CFG
from core.utils import utc_day_key
from execution.take_profit_manager import TakeProfitManager


class EventLoop:
    """
    Consume SignalEvents del SignalBus, aplica guards globales,
    construye señales y llama a OrderManager.execute().
    
    🆕 NUEVO: Detecta y adopta posiciones abiertas manualmente en Binance.
    """

    def __init__(self, bus, market, exchange, order_manager, tg_send, db, logger):
        self.bus = bus
        self.market = market
        self.exchange = exchange
        self.om = order_manager
        self.tg_send = tg_send
        self.db = db
        self.log = logger
        # 🆕 Take Profit Manager
        self.tp_manager = TakeProfitManager(
            exchange=exchange,
            market=market,
            order_manager=order_manager,
            db=db,
            tg_send=tg_send,
            logger=logger
        )

    # ============================================================
    # GUARDS
    # ============================================================

    def _daily_loss_exceeded(self, st) -> bool:
        """Daily loss limit basado en day_start_equity (UTC day)."""
        try:
            eq = float(self.exchange.get_equity())
            start = float(st.day_start_equity)
            if start <= 0:
                return False
            dd_pct = ((start - eq) / start) * 100.0
            return dd_pct >= float(st.daily_loss_limit_pct)
        except Exception as e:
            self.log.warning(f"[DAILY LOSS] could not compute dd: {e}")
            return False

    def _max_positions_reached(self, st) -> bool:
        """Máximo de posiciones abiertas reales en Binance."""
        try:
            open_positions = self.exchange.get_open_positions()
            return len(open_positions) >= int(st.max_positions)
        except Exception as e:
            self.log.warning(f"[MAX POS] could not fetch open positions: {e}")
            return True

    def _cooldown_blocked(self, st, symbol: str, bar_close_ms: int) -> bool:
        """Cooldown por símbolo basado en cantidad de velas."""
        try:
            cd = st.cooldown.get(symbol)
            if not cd:
                return False
            until_ms = int(cd.get("until_ms", 0))
            return bar_close_ms < until_ms
        except Exception:
            return False

    def _set_cooldown(self, st, symbol: str, bar_close_ms: int):
        """Setea cooldown_bars para el símbolo."""
        interval = str(CFG.INTERVAL).lower().strip()
        tf_map = {
            "1m": 60_000, "3m": 3 * 60_000, "5m": 5 * 60_000,
            "15m": 15 * 60_000, "30m": 30 * 60_000, "1h": 60 * 60_000,
            "2h": 2 * 60 * 60_000, "4h": 4 * 60 * 60_000, "1d": 24 * 60 * 60_000,
        }
        tf_ms = tf_map.get(interval, 5 * 60_000)
        bars = int(getattr(st, "cooldown_bars", 0))
        if bars <= 0:
            return
        until_ms = int(bar_close_ms + (bars * tf_ms))
        st.cooldown[symbol] = {"until_ms": until_ms, "bars": bars}

    # ============================================================
    # 🆕 ADOPCIÓN DE POSICIONES MANUALES
    # ============================================================

    def _adopt_manual_position(self, st, symbol: str, ex_pos: dict):
        """
        Adopta una posición abierta manualmente en Binance.
        Crea registro en DB e inicializa estado para trailing/stops.
        """
        try:
            side = ex_pos.get("side")
            qty = float(ex_pos.get("size", 0))
            entry_price = float(ex_pos.get("entry_price", 0))
            
            if qty <= 0 or entry_price <= 0:
                return

            self.log.info(f"[ADOPT] {symbol} {side} qty={qty} entry={entry_price}")

            # 1️⃣ Crear registro en DB
            position_id = self.db.create_position(
                symbol=symbol,
                side=side,
                qty=qty,
                entry_price=entry_price,
                strategy_tag="MANUAL_ADOPTED"
            )

            # 2️⃣ Inicializar estado en memoria
            if not hasattr(st, "position_ids"):
                st.position_ids = {}
            st.position_ids[symbol] = position_id

            if not hasattr(st, "trail"):
                st.trail = {}
            st.trail[symbol] = {
                "direction": side,
                "entry": entry_price,
                "qty": qty,
                "best": entry_price,
                "sl": None,
                "activated": False
            }

            if not hasattr(st, "stop_orders"):
                st.stop_orders = {}

            # 3️⃣ Verificar si ya hay un SL en Binance y sincronizarlo
            existing_sl = self._get_existing_stop_price(symbol, side)
            if existing_sl:
                st.stop_orders[symbol] = {
                    "order_id": None,
                    "is_algo": False,
                    "stop_price": float(existing_sl)
                }
                st.trail[symbol]["sl"] = float(existing_sl)
                self.log.info(f"[ADOPT] {symbol} SL existente sincronizado: {existing_sl}")
            else:
                # Si no hay SL, colocar uno inicial conservador (ATR * 3)
                atr = float(self.market.get_last_atr(symbol) or 0)
                if atr > 0:
                    sl_dist = atr * 3.0
                    initial_sl = entry_price - sl_dist if side == "LONG" else entry_price + sl_dist
                    order_side = "SELL" if side == "LONG" else "BUY"
                    try:
                        stop_order = self.exchange.place_reduce_only_stop(
                            symbol=symbol,
                            side=order_side,
                            quantity=qty,
                            stop_price=initial_sl
                        )
                        algo_id = stop_order.get("algoId")
                        if algo_id:
                            st.stop_orders[symbol] = {
                                "order_id": int(algo_id),
                                "is_algo": True,
                                "stop_price": float(initial_sl)
                            }
                            st.trail[symbol]["sl"] = float(initial_sl)
                            self.log.info(f"[ADOPT] {symbol} SL inicial colocado: {initial_sl}")
                    except Exception as e:
                        self.log.warning(f"[ADOPT] {symbol} no se pudo colocar SL inicial: {e}")

            # 🆕 4️⃣ GUARDAR SL EN BASE DE DATOS
            sl_price = st.trail[symbol].get("sl")
            if sl_price:
                try:
                    algo_id = st.stop_orders[symbol].get("order_id")
                    self.db.create_stop(
                        position_id=position_id,
                        stop_price=float(sl_price),
                        exchange_algo_id=algo_id
                    )
                    self.log.info(f"[ADOPT DB] {symbol} SL guardado en position_stops: {sl_price}")
                except Exception as e:
                    self.log.warning(f"[ADOPT DB] Error guardando SL en DB {symbol}: {e}")

            # 5️⃣ Persistir estado
            self.db.save_state(st.__dict__)

            # 6️⃣ Notificar por Telegram
            if self.tg_send:
                sl_txt = f"{st.trail[symbol].get('sl', 'N/A'):.4f}" if st.trail[symbol].get('sl') else "NINGUNO ⚠️"
                self.tg_send(
                    f"🤝 <b>Posición adoptada</b>\n"
                    f"{symbol} {side}\n"
                    f"Qty: {qty:.6f}\n"
                    f"Entry: {entry_price:.4f}\n"
                    f"SL: {sl_txt}\n"
                    f"<i>Abierta manualmente, ahora gestionada por el bot</i>"
                )

            self.log.info(f"[ADOPT] {symbol} registrado correctamente. position_id={position_id}")

        except Exception as e:
            self.log.error(f"[ADOPT] Error adopting {symbol}: {e}")
            if self.tg_send:
                self.tg_send(f"⚠️ Error adoptando {symbol}: {str(e)[:100]}")

    def _get_existing_stop_price(self, symbol: str, position_side: str) -> float:
        """
        Consulta órdenes STOP abiertas en Binance para un símbolo.
        Devuelve el stop_price si existe, None si no.
        """
        try:
            # Obtener todas las órdenes abiertas (incluye STOP_MARKET)
            open_orders = self.exchange.client.futures_get_open_orders(symbol=symbol)
            order_side = "SELL" if position_side == "LONG" else "BUY"
            
            for order in open_orders:
                if order.get("type") == "STOP_MARKET" and order.get("side") == order_side:
                    if order.get("reduceOnly") is True:
                        return float(order.get("stopPrice", 0))
            return None
        except Exception as e:
            self.log.warning(f"[ADOPT] Error buscando SL existente {symbol}: {e}")
            return None

    # ============================================================
    # RECONCILIACIÓN DE POSICIONES
    # ============================================================

    def reconcile_filled_orders(self, st):
        """
        Sincroniza posiciones de Binance con la DB.
        🆕 Detecta y adopta posiciones manuales no registradas.
        🆕 Usa PnL REAL de Binance para cierres (no cálculo manual).
        🆕 Guarda comisión real (USDT + %) de Binance.
        """
        try:
            exchange_positions = self.exchange.get_open_positions()
            exchange_map = {}
            for p in exchange_positions:
                symbol = p.get("symbol")
                if not symbol:
                    continue
                exchange_map[symbol] = float(p.get("size") or 0)

            # 🆕 Paso 1: Detectar y adoptar posiciones manuales
            db_open = self.db.get_open_positions()
            db_symbols = {p["symbol"] for p in db_open}
            
            for ex_pos in exchange_positions:
                symbol = ex_pos.get("symbol")
                if not symbol or symbol not in st.symbols:
                    continue
                # Si existe en Binance pero NO en DB → ADOPTAR
                if symbol not in db_symbols:
                    self._adopt_manual_position(st, symbol, ex_pos)
                    db_symbols.add(symbol)

            # Refrescar lista de DB con las nuevas adopciones
            db_open = self.db.get_open_positions()

            # Paso 2: Procesar posiciones ya conocidas
            for pos in db_open:
                symbol = pos["symbol"]
                db_qty = float(pos["qty"])
                ex_qty = abs(exchange_map.get(symbol, 0.0))

                # ==================================================
                # 🔴 POSICIÓN TOTALMENTE CERRADA
                # ==================================================
                if ex_qty == 0.0:
                    open_time_ms = int(pos["opened_at"].timestamp() * 1000)
                    
                    # 🆕 1️⃣ Obtener trades desde la apertura para calcular comisiones
                    trades = self.exchange.client.futures_account_trades(
                        symbol=symbol,
                        startTime=open_time_ms
                    )
                    
                    if not trades:
                        self.log.warning(f"[RECONCILE] No trades found for {symbol}")
                        continue
                    
                    # 🆕 2️⃣ Filtrar trades de cierre y sumar comisiones
                    closing_trades = []
                    total_commission = 0.0
                    
                    for t in trades:
                        realized = float(t.get("realizedPnl", 0) or 0)
                        commission = float(t.get("commission", 0) or 0)
                        
                        # Identificar trades de cierre (tienen realizedPnl != 0)
                        if realized != 0:
                            closing_trades.append(t)
                            total_commission += commission  # ← Sumar comisión de cada trade
                    
                    if not closing_trades:
                        continue
                    
                    # 🆕 3️⃣ Calcular exit_price ponderado
                    total_qty = 0.0
                    weighted_price = 0.0
                    for t in closing_trades:
                        qty = float(t["qty"])
                        price = float(t["price"])
                        total_qty += qty
                        weighted_price += qty * price
                    exit_price = (weighted_price / total_qty) if total_qty > 0 else float(pos["entry_price"])
                    
                    # 🆕 4️⃣ Obtener PnL REAL de Binance (ya incluye comisiones internamente)
                    position_history = self.exchange.get_position_history(
                        symbol=symbol,
                        open_time=open_time_ms
                    )
                    
                    if position_history:
                        realized_pnl = float(position_history["realizedPnl"])  # ← PnL neto (ya incluye fees)
                        self.log.info(f"[RECONCILE] {symbol} PnL={realized_pnl} Commission={total_commission}")
                    else:
                        # Fallback: cálculo manual si falla la API
                        entry_price = float(pos["entry_price"])
                        qty_closed = float(pos["qty"])
                        if pos["side"] == "LONG":
                            realized_pnl = (exit_price - entry_price) * qty_closed
                        else:
                            realized_pnl = (entry_price - exit_price) * qty_closed
                        # Restar comisiones calculadas
                        realized_pnl -= total_commission
                    
                    # 🆕 5️⃣ Calcular comisión como porcentaje del notional
                    entry_price = float(pos["entry_price"])
                    qty_closed = float(pos["qty"])
                    notional = entry_price * qty_closed
                    commission_pct = (total_commission / notional * 100) if notional > 0 else 0
                    
                    # 🆕 6️⃣ Obtener close_time real
                    if closing_trades:
                        last_trade = max(closing_trades, key=lambda x: x["time"])
                        close_time_ms = last_trade["time"]
                    else:
                        close_time_ms = int(time.time() * 1000)  # Fallback a ahora
                    
                    # 🆕 7️⃣ Cerrar en DB con PnL real + comisión
                    self.db.close_position(
                        position_id=pos["id"],
                        exit_price=exit_price,
                        realized_pnl=realized_pnl,
                        commission=total_commission,        
                        commission_pct=commission_pct,       
                        close_reason="STOP_OR_MANUAL"
                    )
                    
                    # 8️⃣ Desactivar stops en DB
                    self.db.deactivate_stops(pos["id"])
                    # 🆕 Limpiar estado de TP para este símbolo
                    if hasattr(self, "tp_manager"):
                        self.tp_manager.reset_symbol(symbol)
                    # 9️⃣ Limpiar estado en memoria
                    if hasattr(st, "position_ids"):
                        st.position_ids.pop(symbol, None)
                    if hasattr(st, "trail"):
                        st.trail.pop(symbol, None)
                    if hasattr(st, "stop_orders"):
                        st.stop_orders.pop(symbol, None)
                    
                    # 🔟 Persistir estado
                    self.db.save_state(st.__dict__)

                    # 📊 LOG MÉTRICAS POST-OPERACIÓN
                    entry_time_ms = int(pos["opened_at"].timestamp() * 1000)
                    hold_min = (close_time_ms - entry_time_ms) / 60000
                    move_pct = ((exit_price - float(pos["entry_price"])) / float(pos["entry_price"])) * 100 if pos["side"] == "LONG" else ((float(pos["entry_price"]) - exit_price) / float(pos["entry_price"])) * 100
                    self.log.info(f"[METRICS] {symbol} {pos['side']} | hold={hold_min:.1f}min | move={move_pct:+.3f}% | pnl={realized_pnl:+.4f} | comm={total_commission:.4f} | net={realized_pnl - total_commission:+.4f}")
                                        
                    # 1️⃣1️⃣ Telegram notification
                    try:
                        r = float(realized_pnl or 0)
                        ep = float(exit_price or 0)
                        emoji = "🟢" if r >= 0 else "🔴"
                        if self.tg_send:
                            self.tg_send(
                                f"{emoji} <b>Posición cerrada</b>\n"
                                f"Symbol: {symbol}\n"
                                f"Side: {pos['side']}\n"
                                f"Exit: {ep:.4f}\n"
                                f"Realized: {r:.4f} USDT\n"
                                f"Commission: {total_commission:.4f} USDT ({commission_pct:.3f}%)"
                            )
                    except Exception as e:
                        self.log.warning(f"[TG CLOSE NOTIFY] {e}")
                    
                    continue
                    
                # ==================================================
                # 🟡 REDUCCIÓN PARCIAL
                # ==================================================
                if ex_qty < db_qty:
                    reduced = db_qty - ex_qty
                    self.db.update_position_qty(position_id=pos["id"], new_qty=ex_qty)
                    self.db.create_position_event(
                        position_id=pos["id"],
                        event_type="PARTIAL_CLOSE",
                        payload={"reduced_qty": reduced, "remaining_qty": ex_qty}
                    )
                    self.log.info(
                        f"[RECONCILE] {symbol} partial close "
                        f"reduced={reduced:.6f} remaining={ex_qty:.6f}"
                    )

        except Exception as e:
            self.log.warning(f"[RECONCILE] {e}")

    # ============================================================
    # SIGNAL BUILD
    # ============================================================

    def _build_signal_dict(self, ev, st):
        """Convierte SignalEvent -> dict para OrderManager.execute()"""
        sym = ev.symbol
        side = ev.direction
        sig = ev.signal

        price = float(sig.get("signal_price", sig.get("close", 0.0)))
        atr = float(sig.get("atr", 0.0))

        if price <= 0 or atr <= 0:
            return None

        # Risk Management
        equity = float(self.exchange.get_equity())
        max_positions = int(getattr(CFG, "MAX_OPEN_POSITIONS", 1))
        base_risk_pct = float(getattr(CFG, "DEFAULT_RISK_PCT", 1.0))
        risk_pct_per_trade = base_risk_pct / max_positions
        risk_usdt = equity * (risk_pct_per_trade / 100.0)

        # Stop Distance
        stop_dist = max(atr * 0.5, price * 0.001)
        qty = risk_usdt / stop_dist
        qty = max(qty, 0.001)

        # Initial SL
        sl_mult = float(getattr(CFG, "INITIAL_SL_ATR_MULT", 1.5))
        min_sl_pct = float(getattr(CFG, "MIN_INITIAL_SL_PCT", 0.3))
        raw_sl_dist = atr * sl_mult
        min_sl_dist = price * (min_sl_pct / 100.0)
        final_sl_dist = max(raw_sl_dist, min_sl_dist)

        initial_sl = (price - final_sl_dist) if side == "LONG" else (price + final_sl_dist)
        if initial_sl <= 0:
            initial_sl = None

        return {
            "symbol": sym, "side": side, "price": price, "qty": qty,
            "atr": atr, "bar_close_ms": int(ev.kline_close_time_ms),
            "initial_sl": initial_sl,
            "ml_features": ev.signal.get("ml_features"),
        }

    # ============================================================
    # LOOP PRINCIPAL
    # ============================================================

    def loop_once(self, st) -> bool:
        """Ejecuta un ciclo completo del bot."""
        self.reconcile_filled_orders(st)
        
        if st.paused:
            return False

        # Reset diario (UTC)
        day = utc_day_key()
        if st.day_key != day:
            st.day_key = day
            st.day_start_equity = max(float(self.exchange.get_equity()), 0.0)

        # Daily loss guard
        if self._daily_loss_exceeded(st):
            self.log.warning("[DAILY LOSS] limit exceeded. Blocking entries.")
            return False

        # Evaluar Take Profit (antes de nuevas entradas)
        if getattr(CFG, "USE_TAKE_PROFIT", False):
            self.tp_manager.loop_once(st)    

        # Pop signal
        ev = self.bus.pop_any()
        if ev is None:
            return False

        symbol = ev.symbol
        bar_close_ms = int(ev.kline_close_time_ms)

        # ── GUARDS SECUENCIALES ──
        
        # 1) ADX min
        adx_val = float(ev.signal.get("adx", 0.0))
        if adx_val < float(st.adx_min):
            self.log.info(f"{symbol} BLOCKED: adx {adx_val:.2f} < min {st.adx_min}")
            return True

        # 2) ADX rising
        if bool(getattr(CFG, "REQUIRE_ADX_RISING", True)):
            if not bool(ev.signal.get("adx_increasing", False)):
                self.log.info(f"{symbol} BLOCKED: adx not rising")
                return True

        # 3) Cooldown
        if self._cooldown_blocked(st, symbol, bar_close_ms):
            self.log.info(f"{symbol} BLOCKED: cooldown")
            return True

        # 4) Max positions
        if self._max_positions_reached(st):
            self.log.info(f"{symbol} BLOCKED: max positions")
            return True

        # 5) Spread filter
        try:
            max_spread = float(getattr(CFG, "MAX_SPREAD_PCT", 0.10))
            cache_s = int(getattr(CFG, "SPREAD_CACHE_SECONDS", 3))
            if hasattr(self.exchange, "get_spread_pct"):
                sp = float(self.exchange.get_spread_pct(symbol, cache_seconds=cache_s))
                if sp > max_spread:
                    self.log.info(f"[SPREAD] blocked {symbol}: {sp:.3f}% > {max_spread}%")
                    return True
        except Exception as e:
            self.log.warning(f"[SPREAD] check failed {symbol}: {e}")
            return True

        # Construir y ejecutar señal
        signal = self._build_signal_dict(ev, st)
        if not signal:
            return True

        result = self.om.execute(st, signal)
        if result:
            self._set_cooldown(st, symbol, bar_close_ms)

        return True