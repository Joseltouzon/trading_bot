# execution/event_loop.py

import time
import config as CFG
from core.utils import utc_day_key


class EventLoop:
    """
    Consume SignalEvents del SignalBus (provenientes del MarketCache / Strategy),
    aplica guards globales (daily loss, max_positions, cooldown),
    construye el dict final y llama a OrderManager.execute().
    """

    def __init__(self, bus, market, exchange, order_manager, logger):
        self.bus = bus
        self.market = market
        self.exchange = exchange
        self.om = order_manager
        self.log = logger

    # ============================================================
    # GUARDS
    # ============================================================

    def _daily_loss_exceeded(self, st) -> bool:
        """
        Daily loss limit basado en day_start_equity (UTC day).
        """
        try:
            eq = float(self.exchange.get_equity())
            start = float(st.day_start_equity)

            if start <= 0:
                return False

            dd_pct = ((start - eq) / start) * 100.0
            return dd_pct >= float(st.daily_loss_limit_pct)

        except Exception as e:
            # Si no podemos calcular equity, mejor NO bloquear por esto.
            self.log.warning(f"[DAILY LOSS] could not compute dd: {e}")
            return False

    def _max_positions_reached(self, st) -> bool:
        """
        Máximo de posiciones abiertas reales en Binance.
        """
        try:
            open_positions = self.exchange.get_open_positions()
            return len(open_positions) >= int(st.max_positions)
        except Exception as e:
            # Si no podemos verificar, por seguridad NO abrimos trades.
            self.log.warning(f"[MAX POS] could not fetch open positions: {e}")
            return True

    def _cooldown_blocked(self, st, symbol: str, bar_close_ms: int) -> bool:
        """
        Cooldown por símbolo basado en cantidad de velas.
        st.cooldown: { "BTCUSDT": {"until_ms": int, "bars": int} }
        """
        try:
            cd = st.cooldown.get(symbol)
            if not cd:
                return False

            until_ms = int(cd.get("until_ms", 0))
            return bar_close_ms < until_ms

        except Exception:
            return False

    def _set_cooldown(self, st, symbol: str, bar_close_ms: int):
        """
        Setea cooldown_bars para el símbolo.
        cooldown_bars = cantidad de velas a esperar.
        """
        interval = str(CFG.INTERVAL).lower().strip()

        tf_map = {
            "1m": 60_000,
            "3m": 3 * 60_000,
            "5m": 5 * 60_000,
            "15m": 15 * 60_000,
            "30m": 30 * 60_000,
            "1h": 60 * 60_000,
            "2h": 2 * 60 * 60_000,
            "4h": 4 * 60 * 60_000,
            "1d": 24 * 60 * 60_000,
        }

        tf_ms = tf_map.get(interval, 5 * 60_000)  # fallback 5m

        bars = int(getattr(st, "cooldown_bars", 0))
        if bars <= 0:
            return

        until_ms = int(bar_close_ms + (bars * tf_ms))

        st.cooldown[symbol] = {
            "until_ms": until_ms,
            "bars": bars
        }

    # ============================================================
    # SIGNAL BUILD
    # ============================================================

    def _build_signal_dict(self, ev, st):
        """
        Convierte SignalEvent -> dict esperado por OrderManager.execute()

        OrderManager.execute espera:
        {
            "symbol": str,
            "side": "LONG" | "SHORT",
            "price": float,
            "qty": float,
            "atr": float,
            "bar_close_ms": int,
            "initial_sl": float | None
        }
        """
        sym = ev.symbol
        side = ev.direction
        sig = ev.signal

        price = float(sig.get("close", 0.0))
        atr = float(sig.get("atr", 0.0))
        if price <= 0 or atr <= 0:
            return None

        # Qty por riesgo (mantengo tu lógica actual)
        equity = float(self.exchange.get_equity())
        risk_usdt = equity * (float(st.risk_pct) / 100.0)

        stop_dist = max(atr * 0.5, price * 0.001)
        qty = risk_usdt / stop_dist
        qty = max(qty, 0.001)

        sl_mult = float(getattr(CFG, "INITIAL_SL_ATR_MULT", 2.0))
        min_sl_pct = float(getattr(CFG, "MIN_INITIAL_SL_PCT", 0.3))

        raw_sl_dist = atr * sl_mult
        min_sl_dist = price * (min_sl_pct / 100.0)

        final_sl_dist = max(raw_sl_dist, min_sl_dist)

        if side == "LONG":
            initial_sl = price - final_sl_dist
        else:
            initial_sl = price + final_sl_dist

        if initial_sl <= 0:
            initial_sl = None

        return {
            "symbol": sym,
            "side": side,
            "price": price,
            "qty": qty,
            "atr": atr,
            "bar_close_ms": int(ev.kline_close_time_ms),
            "initial_sl": initial_sl
        }

    # ============================================================
    # LOOPS
    # ============================================================

    def loop_once(self, st) -> bool:
        """
        Ejecuta un solo ciclo (modo REST/polling).
        Devuelve True si procesó algo (aunque no haya entrado).
        """
        # Pausa manual
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

        # Pop signal
        # self.log.info("EventLoop polling bus...")
        ev = self.bus.pop_any()
        if ev is None:
            # self.log.info("EventLoop: no signal in bus")
            return False

        symbol = ev.symbol
        bar_close_ms = int(ev.kline_close_time_ms)

        # ADX min
        adx_val = float(ev.signal.get("adx", 0.0))
        if adx_val < float(st.adx_min):
            self.log.info(f"{symbol} BLOCKED: adx {adx_val:.2f} < min {st.adx_min}")
            return True

        # ADX rising obligatorio (lo pediste)
        if bool(getattr(CFG, "REQUIRE_ADX_RISING", True)):
            if not bool(ev.signal.get("adx_increasing", False)):
                self.log.info(f"{symbol} BLOCKED: adx not rising")
                return True

        # Cooldown
        if self._cooldown_blocked(st, symbol, bar_close_ms):
            self.log.info(f"{symbol} BLOCKED: cooldown")
            return True

        # Max positions
        if self._max_positions_reached(st):
            self.log.info(f"{symbol} BLOCKED: max positions")
            return True

        # (Opcional) Spread filter si tu exchange lo soporta
        # No lo fuerzo aquí porque depende de tu BinanceFutures wrapper.
        # Si tienes exchange.get_spread_pct(symbol), lo habilitamos:
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
            return True  # conservador: si no puedo validar, no entro

        # Construir dict final
        signal = self._build_signal_dict(ev, st)
        if not signal:
            return True

        # Ejecutar
        result = self.om.execute(st, signal)

        # Si entró, set cooldown
        if result:
            self._set_cooldown(st, symbol, bar_close_ms)

        return True

    def loop(self, st):
        """
        Loop continuo (si quisieras modo thread).
        """
        while True:
            try:
                did = self.loop_once(st)
                if not did:
                    time.sleep(0.05)
            except Exception:
                self.log.exception("[EventLoop] critical error")
                time.sleep(0.5)
