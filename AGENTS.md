# AGENTS.md — Referencia Rápida para el Bot Trading

## Role

Act as a software engineer.

## Propósito
Archivo de referencia para agentes. Consultar antes de modificar o agregar features. Mantener actualizado con cada cambio significativo.

---

## 1. Trailing Stop

**Archivo:** `execution/trailing.py` — `TrailingManager`

### Comportamiento

1. **Evaluación por ciclo** (`loop_once`): itera todas las posiciones abiertas y llama a `update_trailing`.
2. **Inicialización segura post-restart**: si `symbol` no está en `st.trail`, inicializa `best = entry` para no perder tracking del mejor precio.
3. **Activación**: cuando `pnl_pct >= TRAILING_ACTIVATION_PCT` (default 0.5%).
4. **Cálculo del nuevo SL**:
   - Si `TRAILING_USE_ATR = True`: `new_sl = best - (atr * TRAILING_ATR_MULT)` (LONG)
   - Si `TRAILING_USE_ATR = False`: `new_sl = best * (1 - trailing_pct/100)` (LONG)
5. **Protección SL >= Entry Price**: `new_sl = max(new_sl, entry)` (LONG). Garantiza que el SL nunca quede por debajo del precio de entrada.
6. **Solo mejora en dirección favorable**: solo actualiza si `new_sl > old_sl` (LONG) o `new_sl < old_sl` (SHORT).
7. **Throttle API**: máximo 1 actualización cada 5 segundos por símbolo.
8. **Persistencia**: `st.trail[symbol]` guarda `direction`, `entry`, `best`, `qty`, `sl`, `activated`.

### Estado en memoria

```python
st.trail[symbol] = {
    "direction": "LONG",       # o "SHORT"
    "entry": 100000.0,         # precio de entrada
    "qty": 0.333,              # cantidad actual
    "best": 102000.0,          # mejor precio alcanzado (para LONG = max)
    "sl": 101000.0,            # stop loss actual (None si no se colocó aún)
    "activated": True          # True una vez que pnl_pct >= TRAILING_ACTIVATION_PCT
}
```

### Config (config.py)

```python
TRAILING_ACTIVATION_PCT = 0.5    # % de profit requerido para activar
TRAILING_USE_ATR = True          # True = usa ATR, False = usa trailing_pct %
TRAILING_ATR_MULT = 2.0          # multiplicador ATR para distancia del SL
TRAILING_PCT = 0.5              # solo si TRAILING_USE_ATR = False (% por vela)
```

### Flujo de ejecución en bot.py

```
bot.py loop:
  1. market.update_all()
  2. signal_engine.process_symbol()
  3. event_loop.loop_once()     ← nuevas entradas, guards
  4. trailing.loop_once()       ← trailing stop
  5. telegram.poll_once()
  6. account snapshot
```

### Notas importantes
- El trailing solo maneja SL. El precio de entrada (`entry`) se usa solo para la protección `SL >= entry`.
- Si el bot se reinicia, `best` se reinicia a `entry` (comportamiento seguro, no pierde más de lo inicial).
- Si `atr <= 0`, retorna sin actualizar (evita SL con ATR inválido).
- Compatible con TakeProfitManager: no compiten por el mismo SL ya que TP cierra qty parcial y trailing sigue con el remanente.

---

## 2. Take Profit

**Archivo:** `execution/take_profit_manager.py` — `TakeProfitManager`

### Dos modos de operación

Determinado por `TP_BY_PCT` en config:

| Modo | Config | Lógica | Archivo método |
|------|--------|--------|----------------|
| **Por %** (recomendado) | `TP_BY_PCT = True` | Evalúa profit % vs `TP_ACTIVATION_PCT` | `_evaluate_tp_by_pct` |
| **Por R:R** (legacy) | `TP_BY_PCT = False` | Evalúa R:R vs niveles en `TP_LEVELS` | `_evaluate_tps` |

### Modo por % de ganancia (actual default)

```python
TP_BY_PCT = True
TP_ACTIVATION_PCT = 1.2    # activa cuando profit llega a 1.2%
TP_CLOSE_PCT = 70          # cierra 70% de la posición
TP_SL_MODE = "trailing"    # "trailing" = TrailingManager maneja SL restante
                           # "entry" = mover SL del resto al precio de entrada
```

**Flujo:**
1. Evalúa `profit_pct = (mp - entry) / entry * 100` (LONG)
2. Si `profit_pct >= TP_ACTIVATION_PCT` y aún no se ejecutó → continúa
3. Normaliza `close_qty = total_qty * TP_CLOSE_PCT / 100` con safety buffer 0.999
4. Valida `min_notional` de Binance (20 USDT)
5. Ejecuta market order `reduce_only=True` por `close_qty`
6. Actualiza `remaining_qty` en DB
7. Si `TP_SL_MODE = "trailing"`: NO toca el SL → `TrailingManager` sigue manejando el 30% restante
8. Si `TP_SL_MODE = "entry"`: llama `_move_sl_to_entry` para mover SL del remanente al entry
9. Limpia tracking: `_tp_by_pct_executed[symbol] = True` (solo se ejecuta 1 vez por símbolo)

**Al cerrar posición completamente:** `reset_symbol()` limpia `_tp_by_pct_executed` para permitir nuevo ciclo.

### Modo legacy: R:R múltiple (config original)

```python
TP_LEVELS = [
    {"ratio": 5.0, "close_pct": 30, "move_sl_to_be": True},   # 30% en 5R
    {"ratio": 8.0, "close_pct": 30, "move_sl_to_be": False},  # 30% en 8R
    {"ratio": 12.0, "close_pct": 40, "move_sl_to_be": False}, # 40% en 12R
]
```

- Calcula R:R actual: `current_r = (mp - entry) / risk` donde `risk = |entry - initial_sl|`
- Obtiene `initial_sl` de DB (`position_stops`) o de `st.trail`
- Ejecuta un nivel por ciclo (break after first hit)
- Si `move_sl_to_be = True`: llama `_move_sl_to_breakeven` para el remanente

### SL Breakeven (ambos modos)

`_move_sl_to_breakeven`: mueve SL del remanente a `entry * (1 + buffer_pct)` para LONG.
- **Solo mueve si el nuevo SL es mejor** que el actual (protección dual con trailing).
- `SL_BUFFER_PCT = 0.0012` (0.12% de buffer sobre entry).

### Estado en memoria

```python
# TakeProfitManager instance fields:
_tp_executed = {}              # {symbol: {tp_index: timestamp}}  — modo R:R
_tp_by_pct_executed = {}       # {symbol: True}                  — modo %
_last_tp_action = {}           # {symbol: timestamp}            — throttle API
```

### Throttle

`TP_THROTTLE_SECONDS = 10` — mínimo 10 segundos entre acciones de TP por símbolo.

### Notas importantes
- TP y Trailing **no compiten**: TP cierra qty parcial, trailing sigue con el remanente.
- El `position_id` debe existir en `st.position_ids` para que TP funcione.
- Si `_tp_by_pct_executed[symbol] = True`, no vuelve a ejecutar (protección contra doble cierre).
- `reset_symbol()` se llama desde `event_loop.reconcile_filled_orders()` cuando la posición se cierra completamente.

---

## 3. Daily Loss Guard

**Archivos:** `execution/event_loop.py` (líneas 39-50, 469-493)

### Comportamiento

1. **Reset diario UTC**: al cambiar el día (UTC), `day_start_equity = equity` y `day_key = nuevo día`.
2. **Verificación**: `dd_pct = ((start - equity) / start) * 100`. Si `dd_pct >= daily_loss_limit_pct` → bloquea nuevas entradas.
3. **Solo bloquea entradas**: NO cierra posiciones existentes, NO detiene trailing ni TP.
4. **Notificación Telegram**: al bloquear, envía mensaje con equity actual, equity inicial y drawdown %.

### Config

```python
DEFAULT_DAILY_LOSS_LIMIT_PCT = 10.0  # config.py
daily_loss_limit_pct = st.daily_loss_limit_pct  # configurable por DB
```

### Notas importantes
- **No está en OrderManager** — siempre estuvo solo en EventLoop como guard global.
- Si se superó el límite y ya hay posiciones abiertas, estas siguen corriendo con trailing/tp activos.
- Para debuggear: buscar `[DAILY LOSS]` en los logs.

---

## 4. Order Manager

**Archivo:** `execution/order_manager.py`

### Métodos clave

| Método | Propósito |
|--------|-----------|
| `execute(st, signal)` | Entry principal: valida, ejecuta market order, coloca SL inicial |
| `replace_stop_order(st, symbol, direction, qty, new_sl)` | Reemplaza/cancela SL anterior y coloca nuevo. Compatible con trailing. |

### replace_stop_order

1. Cancela stop anterior (maneja `-2011 Unknown order` gracefully).
2. Crea `STOP_MARKET` con `reduceOnly=True`, `closePosition=False`.
3. Extrae `algoId` (no `orderId`).
4. Actualiza `st.stop_orders[symbol]` con `order_id`, `is_algo=True`, `stop_price`.
5. Desactiva stops anteriores en DB, crea nuevo registro.

---

## 5. Event Loop — Guards en orden

`event_loop.py` → `loop_once()`:

```
1. reconcile_filled_orders()     — sync DB ↔ Binance, detecta posiciones manuales
2. paused? → return
3. reset diario UTC
4. daily_loss_exceeded? → block + telegram
5. TP loop_once()                — evalúa take profit
6. pop signal del bus
7. adx_min filter (solo ema_breakout)
8. adx_rising filter (solo ema_breakout)
9. cooldown_blocked?
10. max_positions_reached?
11. spread filter?
12. build_signal_dict()
13. om.execute()
14. set_cooldown()
```

---

## 6. Estado persistente (BotState)

**Archivo:** `core/models.py`

Campos clave relacionados con risk/trail/tp:

```python
@dataclass
class BotState:
    paused: bool
    risk_pct: float
    leverage: int
    symbols: List[str]
    strategy_mode: str           # "ema_breakout" | "stop_hunt"
    trailing_pct: float          # para modo % del trailing
    max_positions: int
    adx_min: float
    cooldown_bars: int
    cooldown: dict               # {symbol: {"until_ms": int, "bars": int}}
    daily_loss_limit_pct: float
    day_key: str                 # UTC "YYYY-MM-DD"
    day_start_equity: float
    trail: dict                  # {symbol: {...}} — ver Trailing Stop
    position_ids: dict           # {symbol: position_id}
    stop_orders: dict           # {symbol: {order_id, is_algo, stop_price}}
    paper_trading: bool
```

**DB como fuente de verdad**: al iniciar, `db.load_state()` sobrescribe defaults de `config.py` (excepto sanity checks en `bot.py`).

---

## 7. Reconciliation

**Archivo:** `execution/event_loop.py` → `reconcile_filled_orders()`

1. Detecta posiciones abiertas en Binance pero no en DB → `_adopt_manual_position()`
2. Detecta posiciones cerradas en Binance → calcula PnL real de Binance, cierra en DB
3. Detecta reducciones parciales → actualiza `qty` en DB

Al cerrar posición: limpia `position_ids`, `trail`, `stop_orders` de state y llama `tp_manager.reset_symbol()`.

---

## 8. Flags de feature on/off

| Feature | Flag | Ubicación |
|---------|------|-----------|
| Take Profit | `USE_TAKE_PROFIT` | `config.py` |
| TP modo % | `TP_BY_PCT` | `config.py` |
| Trailing | `st.trailing_active` | `BotState` (no tiene flag global, siempre corre) |

---

## 9. Llamado desde bot.py

```python
trailing = TrailingManager(exchange, market, om, db, telegram.send, log)
event_loop = EventLoop(bus, market, exchange, om, telegram.send, db, log)
# dentro del while:
event_loop.loop_once(st)   # 3
trailing.loop_once(st)      # 4
# TP se llama dentro de event_loop.loop_once (paso 5)
```

---

## 10. DB — Tablas relevantes

```sql
positions               -- abierta/cerrada, entry/exit, pnl
position_stops          -- historial de SL por posición
position_events         -- eventos: TAKE_PROFIT, TAKE_PROFIT_PCT, PARTIAL_CLOSE
bot_state               -- estado completo del bot (serializado JSON)
account_snapshots       -- equity/margin/available cada 15s
equity_snapshots        -- equity histórico cada 60s
```
