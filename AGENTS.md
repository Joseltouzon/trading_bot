# AGENTS.md — Referencia Completa Beast Money Maker

## Role

Act as a software engineer.

## Reglas de Comunicación

1. **Antes de implementar:** Explicar el problema, la solución propuesta y pedir autorización
2. **No hacer commits** sin autorización expresa del usuario. Si se autoriza, usar mensajes cortos (ej: "add RSI filter to EMA breakout", "fix spread calculation", etc.)
3. **Al commitear:** Revisar AGENTS.md, STRATEGIES_GUIDE.md y los archivos clave del mapa de archivos (sección 22) para ver si hay que actualizarlos
4. **Explicar con claridad** cada decisión técnica para que el usuario pueda aprender
4. **Ser preciso** con términos y números
5. **Si hay bugs:** Mostrar el código problemático, explicar por qué falla, y proponer el fix
6. **No agregar imports que no existan** — verificar que el método/clase esté en el archivo antes de usarlo
7. **Verificar contra código real** — leer el archivo antes de asumir que un método existe
8. **No ejecutar tests ni backtest** con `python` plano — usar `./venv/bin/python` (el entorno virtual tiene todas las dependencias). Si el usuario pide correr un test, aclarar que se hace manualmente con el venv.

## Propósito

Archivo de referencia único para agentes. Contiene la arquitectura, flujo de ejecución, archivos clave y sus relaciones. Consultar ANTES de modificar cualquier archivo. Mantener actualizado con cada cambio significativo.

---

## Índice

1. [Arquitectura General](#1-arquitectura-general)
2. [Flujo de Ejecución (bot.py)](#2-flujo-de-ejecución)
3. [Estrategias](#3-estrategias)
4. [Modo Auto](#4-modo-auto)
5. [Signal Engine](#5-signal-engine)
6. [Event Loop y Guards](#6-event-loop-y-guards)
7. [Order Manager](#7-order-manager)
8. [Trailing Stop](#8-trailing-stop)
9. [Take Profit](#9-take-profit)
10. [Daily Loss Guard](#10-daily-loss-guard)
11. [Reconciliation](#11-reconciliation)
12. [Datafeed y Market Cache](#12-datafeed-y-market-cache)
13. [Exchange (Binance)](#13-exchange-binance)
14. [Infra (API Cache)](#14-infra)
15. [Notifications (Telegram)](#15-notifications-telegram)
16. [Base de Datos](#16-base-de-datos)
17. [Estado Persistente (BotState)](#17-estado-persistente)
18. [Config ↔ Dashboard ↔ DB Pipeline](#18-config-dashboard-db)
19. [Dashboard](#19-dashboard)
20. [Backtesting](#20-backtesting)
21. [Risk Monitor](#21-risk-monitor)
22. [Mapa de Archivos](#22-mapa-de-archivos)
23. [Logs y Debug](#23-logs-y-debug)

---

## 1. Arquitectura General

```
┌─────────────────────────────────────────────────────────┐
│                      bot.py (Main)                       │
│  Init → State → Components → While True: loop           │
└──────────┬──────────────────────────────────────────────┘
           │
    ┌──────┴──────┐
    │  Components  │
    └──────┬──────┘
           │
    ┌──────┴──────────────────────────────────────────┐
    │                                                  │
    ▼                    ▼                             ▼
┌──────────┐     ┌──────────────┐            ┌──────────────┐
│ DataFeed  │     │   Strategy   │            │  Execution   │
│──────────│     │──────────────│            │──────────────│
│MarketCache│    │SignalEngine  │            │EventLoop     │
│          │     │EMA Breakout  │            │OrderManager  │
│          │     │Stop Hunt     │            │TrailingMgr   │
│          │     │RSI+BB        │            │TakeProfitMgr │
│          │     │Stop Hunt     │            │              │
│          │     │EMA Breakout  │            │              │
│          │     │MACD Momentum │            │              │
│          │     │              │            │              │
└────┬─────┘     └──────┬───────┘            └──────┬───────┘
     │                  │                           │
     └──────────────────┴───────────────────────────┘
                        │
              ┌─────────┴─────────┐
              │                    │
              ▼                    ▼
       ┌─────────────┐     ┌─────────────┐
       │  Exchange    │     │     DB       │
       │ (Binance)    │     │ (PostgreSQL) │
       └─────────────┘     └─────────────┘
              │
              ▼
       ┌─────────────┐     ┌─────────────┐
       │  Infra       │     │ Telegram     │
       │ (APICache)   │     │ (Notify)     │
       └─────────────┘     └─────────────┘
```

### Dependencias entre módulos

| Módulo | Lee de | Escribe a |
|--------|--------|-----------|
| `strategy/*` | `config.CFG`, DataFrames | `SignalBus` (via SignalEvent) |
| `execution/event_loop.py` | `SignalBus`, `exchange`, `db`, `config.CFG` | `OrderManager`, `TakeProfitManager` |
| `execution/order_manager.py` | `exchange`, `db`, `config.CFG` | Binance (órdenes), DB (positions) |
| `execution/trailing.py` | `exchange`, `market`, `db` | Binance (SL orders), DB (position_stops) |
| `execution/take_profit_manager.py` | `exchange`, `market`, `db` | Binance (market orders), DB (position_events) |
| `datafeed/market_cache.py` | `exchange` | cache interno, DataFrames |
| `exchange/binance_futures.py` | Binance REST API | cache interno (`APICache`) |

---

## 2. Flujo de Ejecución

**Archivo:** `bot.py`

### Startup (fuera del loop)

```
1. validate_config()
2. Setup: logging, telegram, exchange, db
3. BotState defaults + merge con DB
4. sync_cfg_from_state(st)        ← copia st → CFG runtime
5. Day init (day_start_equity)
6. Leverage setup (por símbolo)
7. market.init_cache(symbols)      ← descarga 500 velas por símbolo
8. Componentes: bus, om, trailing, event_loop, signal_engine
9. telegram.send("Bot activo")
```

### Main Loop (while True)

```
1. State reload (cada 30s)
   └─ db.load_state() → BotState → sync_cfg_from_state()
   └─ Si cambian symbols: market.init_cache() + leverage
   └─ Si cambia strategy_mode: signal_engine.set_strategy_mode()

2. Server time sync (cada 60s)
   └─ Detecta cambio de día UTC → reset daily_loss

3. market.update_all(st.symbols)
   └─ Poll klines cada 15s, mark price cada 3s
   └─ Si nueva vela cerrada: re-descarga DF completo

4. max_pos_reached = event_loop._max_positions_reached(st)
   └─ Si True: SKIPPED signal processing

5. Signal generation (si no max_positions)
   └─ Por cada símbolo:
      └─ process_symbol()             ← ejecuta las 5 estrategias

6. event_loop.loop_once(st)
   └─ Guards → ejecuta señal del bus

7. trailing.loop_once(st)
   └─ Actualiza SL de posiciones abiertas

8. telegram.poll_once()
   └─ Procesa comandos del usuario

9. Account snapshot (cada 15s / 60s)
```

### Manejo de errores

```python
# En el main loop:
try:
    # ... todo el loop ...
except Exception as e:
    log.error(f"Bot error: {type(e).__name__}: {e}", exc_info=True)  # traceback completo
    telegram.send(f"⚠️ Bot error: ...")  # notificación
    time.sleep(5)
```

**Nota:** El bot NUNCA debe crashear permanentemente. Si algo falla, log + telegram + sleep 5s + reintento.

---

## 3. Estrategias

**Archivos:**
- `strategy/ema_adx_breakout.py` — Trend-following (15m)
- `strategy/stop_hunt.py` — Mean-reversion / Liquidity (5m)
- `strategy/rsi_bb_reversion.py` — Mean-reversion RSI + Bollinger (5m)
- `strategy/macd_momentum.py` — Momentum + Volume Spike (15m)
- `strategy/structure_break.py` — Market Structure Break + Retest (5m)
- `strategy/volatility_squeeze.py` — Volatility Compression + Momentum Exhaustion (1h) 🆕
- `strategy/signal_engine.py` — Motor multi-estrategia
- `strategy/indicators.py` — EMA, ATR, ADX, RSI, Bollinger, Stochastic, MACD
- `strategy/pivots.py` — Pivot highs/lows vectorizados

### Señales de salida (todas las estrategias)

Cada estrategia devuelve un dict con:
```python
{
    "strategy": "ema_breakout",  # nombre de la estrategia
    "trend": "BULL",             # BULL | BEAR | NONE
    "breakout_long": True,       # señal LONG
    "breakout_short": False,     # señal SHORT
    "adx": 25.3,                 # ADX actual
    "adx_increasing": True,      # ADX subiendo
    "atr": 150.0,                # ATR actual
    "close": 60000.0,            # precio de cierre
    "signal_price": 60100.0,     # precio para la señal
    "vol_ratio": 1.5,            # volumen / media
    "vol_increasing": True,      # volumen subiendo
    "last_ph": 60200.0,          # último pivot high
    "last_pl": 59800.0,          # último pivot low
    # ... campos específicos de cada estrategia
}
```

### EMA Breakout

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| EMA_FAST / EMA_SLOW | 9 / 21 | EMAs para tendencia |
| DEFAULT_ADX_MIN | 20.0 | ADX mínimo |
| MIN_PIVOT_DISTANCE_PCT | 0.15 | Distancia mínima al pivot (%) |
| MIN_ATR_PCT | 0.15 | Volatilidad mínima |
| VOLUME_MIN_RATIO / MAX_VOLUME_RATIO | 1.20 / 3.5 | Rango de volumen |
| MIN_MOMENTUM_PCT | 0.12 | Momentum mínimo |
| MAX_PIVOT_AGE | 15 | Antigüedad máxima del pivot (velas) |

**Filtros:** tendencia EMA slope → volumen → ATR → momentum → breakout de pivot → ADX en event_loop

### Stop Hunt

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| STOP_HUNT_WICK_PCT | 0.20 | Mecha mínima hunt (%) |
| STOP_HUNT_REJECTION_RATIO | 0.7 | Body/wick rechazo |
| STOP_HUNT_MIN_ZONES | 2 | Mínimo zonas de liquidez |
| STOP_HUNT_MAX_ZONE_DISTANCE_PCT | 0.8 | Distancia máxima a zona |
| STOP_HUNT_MIN_VOLUME_RATIO | 1.5 | Volumen mínimo |
| STOP_HUNT_USE_EMA_FILTER | True | Filtrar por EMA trend |
| STOP_HUNT_ADX_MIN | 18.0 | ADX mínimo |
| STOP_HUNT_ATR_MULT_SL | 2.0 | ATR multiplier para SL |
| ORDER_BLOCK_LOOKBACK | 5 | Velas para buscar OBs |

**Zonas:** Swing levels (pivots) son targets de hunt. Order blocks son confirmación de proximidad (boost de confianza).

### MACD Momentum + Volume Spike (15m)

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| MACD_FAST | 12 | MACD fast EMA |
| MACD_SLOW | 26 | MACD slow EMA |
| MACD_SIGNAL | 9 | MACD signal line |
| MACD_MIN_VOLUME_RATIO | 3.0 | Volume spike mínimo (3x media) |
| MACD_RSI_BULL_MIN | 55 | RSI mínimo para LONG |
| MACD_RSI_BEAR_MAX | 45 | RSI máximo para SHORT |
| MACD_ADX_MIN | 25.0 | ADX mínimo |
| MACD_MIN_ATR_PCT | 0.20 | Volatilidad mínima |
| MACD_SL_ATR_MULT | 2.0 | ATR multiplier para SL |

**Trigger:** MACD histogram creciente × 3 velas + volume spike + RSI direction + EMA alignment + higher high/lower low.

**Funciona en 15m.** PF 2.10, Return +0.92%, DD 0.31%.

### RSI + Bollinger Band Mean Reversion

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| RSI_BB_RSI_PERIOD | 14 | Período del RSI |
| RSI_BB_OVERSOLD | 25 | RSI zona de sobreventa |
| RSI_BB_OVERBOUGHT | 75 | RSI zona de sobrecompra |
| RSI_BB_BB_PERIOD | 20 | Período Bollinger Bands |
| RSI_BB_BB_STD_MULT | 2.0 | StdDev multiplier Bollinger |
| RSI_BB_STOCH_PERIOD | 14 | Período Stochastic RSI |
| RSI_BB_DIVERGENCE_LOOKBACK | 20 | Velas para detectar divergencias |
| RSI_BB_MIN_VOLUME_RATIO | 1.5 | Volumen mínimo |
| RSI_BB_ADX_MIN | 15.0 | ADX mínimo |
| RSI_BB_MIN_ATR_PCT | 0.15 | Volatilidad mínima |
| RSI_BB_SL_ATR_MULT | 2.5 | ATR multiplier para SL |
| RSI_BB_SL_PCT | 0.60 | SL mínimo por porcentaje |

**3 tipos de trigger:**
1. **RSI crossover + BB rejection**: RSI cruza desde zona extrema + precio rechazado en banda
2. **Divergencia RSI**: classic divergence (swing lows/highs con confirmación)
3. **Extreme RSI**: RSI < 20 / > 80 + precio fuera de banda + vela direccional

**Filtros:** volumen, ADX, ATR, Stochastic RSI, no contra tendencia fuerte (ADX>30).

**Funciona mejor en:** ETH, XRP, PEPE. No funciona bien en: BNB, SOL, GRASS, LTC.

### Volatility Squeeze + Momentum Exhaustion (1h) 🆕

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| VOL_SQUEEZE_ATR_PERCENTILE | 15 | ATR en bottom 15% = compresión |
| VOL_SQUEEZE_BB_WIDTH_PERCENTILE | 25 | BB Width comprimido |
| VOL_SQUEEZE_RSI_OVERSOLD/OVERBOUGHT | 30 / 70 | Zonas RSI |
| VOL_SQUEEZE_MIN_VOLUME_RATIO | 1.5 | Volumen mínimo |
| VOL_SQUEEZE_ADX_MIN | 15.0 | ADX mínimo |
| VOL_SQUEEZE_SL_ATR_MULT | 1.5 | ATR multiplier SL |
| VOL_SQUEEZE_EMA_FAST/SLOW | 20 / 50 | EMAs para tendencia |

**Lógica:** Detecta compresión de volatilidad (ATR bajo + BB estrecho) y entra en dirección del swing previo cuando la tendencia EMA confirma.

**Mejores símbolos (60 días, 1h):** NEARUSDT (+9.72), OPUSDT (+8.08), BTCUSDT (+7.26), LINKUSDT (+5.60), XRPUSDT (+3.22)

**Stats combinados:** 78 trades, WR 88%, PF 3.46, Return +19.93%, Sharpe 4.92

---

## 4. Modo Auto

`auto` ejecuta 5 estrategias en paralelo por cada símbolo:
- RSI+BB (5m) + Stop Hunt (5m) + MACD Momentum (15m) + EMA Breakout (15m) + Structure Break (5m)

EMA optimizada con EMA 25/50 + ADX 25 (PF 3.97, WR 63%).

**Volatility Squeeze (1h)** se ejecuta por separado con sus propios símbolos.

---

## 5. Signal Engine (Multi-Timeframe)

**Archivo:** `strategy/signal_engine.py`

El engine ejecuta **las 5 estrategias + VS en paralelo** por cada símbolo:

| Estrategia | Timeframe | Intervalo |
|-----------|-----------|-----------|
| RSI+BB Reversion | 5m | Cada 5 minutos |
| Stop Hunt | 5m | Cada 5 minutos |
| MACD Momentum | 15m | Cada 15 minutos |
| EMA Breakout | 15m | Cada 15 minutos |
| Structure Break | 5m | Cada 5 minutos |
| Volatility Squeeze | 1h | Cada 1 hora |

### Flujo `process_symbol()`

```
Para cada estrategia en ACTIVE_STRATEGIES:
  1. interval = STRATEGY_INTERVALS[strategy]  ("5m" o "15m")
  2. df = market.get_df_copy(symbol, interval)
  3. close_time = df["close_time"].iloc[-2]
  4. Si _last_processed[(symbol, strategy)] == close_time → skip
  5. Ejecutar compute_function(df)
  6. Si señal → publish al bus
```

### Métodos clave

| Método | Propósito |
|--------|-----------|
| `process_symbol(symbol, max_positions)` | Ejecuta las 5 estrategias con sus DFs |
| `set_strategy_mode(mode)` | `all`=5 estrategias, `auto`=5, o una individual |

### Config

```python
STRATEGY_INTERVALS = {
    "rsi_bb_reversion": "5m",
    "stop_hunt": "5m",
    "ema_breakout": "15m",
    "macd_momentum": "15m",
    "structure_break": "5m",
    "volatility_squeeze": "1h",
}
```

### Cache

- `_last_processed`: {(symbol, strategy): close_time_ms} — evita reprocesar misma vela por estrategia

---

## 6. Event Loop y Guards

**Archivo:** `execution/event_loop.py`

### Orden de guards en `loop_once()`

```
1. reconcile_filled_orders()     ← sync DB ↔ Binance
2. paused? → return
3. reset diario UTC
4. daily_loss_exceeded? → block + telegram
5. tp_manager.loop_once()        ← evalúa take profit
6. pop signal del bus
7. strategy_type detectado desde señal
8. adx_min filter (solo ema_breakout)
9. adx_rising filter (solo ema_breakout)
10. cooldown_blocked?
11. max_positions_reached?       ← (re-check por seguridad)
12. build_signal_dict()
13. om.execute()
14. set_cooldown()
```

### Métodos clave

| Método | Propósito |
|--------|-----------|
| `loop_once(st)` | Un ciclo completo del event loop |
| `reconcile_filled_orders(st)` | Sync posiciones DB ↔ Binance |
| `_max_positions_reached(st)` | ¿Hay max_positions abiertas? |
| `_daily_loss_exceeded(st)` | ¿Se superó el daily loss? |
| `_cooldown_blocked(st, symbol, bar_ms)` | ¿Símbolo en cooldown? |

### Spread filter

El spread filter dinámico está en `OrderManager.execute()`, NO en event_loop. Usa:
```python
dynamic_max_spread = base_spread + (atr_pct * 0.5)
```

---

## 7. Order Manager

**Archivo:** `execution/order_manager.py`

### Métodos

| Método | Propósito |
|--------|-----------|
| `execute(st, signal)` | Entry: valida → market order → coloca SL inicial |
| `replace_stop_order(st, symbol, direction, qty, new_sl)` | Reemplaza SL (trailing, TP) |

### Flujo de `execute()`

```
1. Verificar qty > 0 y notional >= mínimo
2. Set leverage (si no está seteado)
3. Market price check
4. ATR % (calcular una vez, reusar)
5. Spread filter dinámico (atr_pct * 0.5)
6. Slippage guard dinámico
7. Ejecutar market order (BUY/SELL)
8. Calcular qty real de fills
9. Verificar reduce-only si ya hay posición
10. Calcular SL inicial
11. Colocar STOP_MARKET order
12. Guardar en DB (positions + position_stops)
13. Set position_id, trail, stop_orders en state
14. Notificar Telegram
```

---

## 8. Trailing Stop

**Archivo:** `execution/trailing.py` — `TrailingManager`

### Comportamiento

1. Evalúa cada ciclo (`loop_once`) para todas las posiciones abiertas
2. **Activación**: cuando `pnl_pct >= TRAILING_ACTIVATION_PCT` (default 0.5%)
3. **Cálculo SL**:
   - `TRAILING_USE_ATR = True`: `new_sl = best - (atr * TRAILING_ATR_MULT)` (LONG)
   - `TRAILING_USE_ATR = False`: `new_sl = best * (1 - trailing_pct/100)` (LONG)
4. **Protección**: `new_sl = max(new_sl, entry)` — nunca por debajo del entry
5. **Solo mejora**: solo actualiza si `new_sl > old_sl` (LONG)
6. **Throttle API**: máximo 1 actualización cada 5s por símbolo
7. **Post-restart**: `best = entry` (comportamiento seguro)

### Estado

```python
st.trail[symbol] = {
    "direction": "LONG"|"SHORT",
    "entry": 60000.0,
    "qty": 0.001,
    "best": 61000.0,      # mejor precio alcanzado
    "sl": 60500.0,        # SL actual
    "activated": True      # pnl >= activation
}
```

### Config

```python
TRAILING_ACTIVATION_PCT = 0.5   # % profit para activar
TRAILING_USE_ATR = True         # ATR vs % fijo
TRAILING_ATR_MULT = 2.0         # multiplicador ATR
TRAILING_PCT = 0.5              # solo si USE_ATR=False
```

---

## 9. Take Profit

**Archivo:** `execution/take_profit_manager.py` — `TakeProfitManager`

### Modo por % (default)

```python
TP_BY_PCT = True
TP_ACTIVATION_PCT = 1.2    # activa a 1.2% profit
TP_CLOSE_PCT = 70          # cierra 70% de la posición
TP_SL_MODE = "trailing"    # trailing maneja el 30% restante
```

**Flujo:**
1. `profit_pct >= TP_ACTIVATION_PCT` → cierra `TP_CLOSE_PCT` %
2. Market order `reduce_only=True`
3. Si `TP_SL_MODE = "trailing"`: NO toca SL, TrailingManager sigue
4. `_tp_by_pct_executed[symbol] = True` (1 ejecución por símbolo)

### Métodos clave

| Método | Propósito |
|--------|-----------|
| `loop_once(st)` | Evalúa TP para todas las posiciones |
| `reset_symbol(symbol)` | Limpia tracking al cerrar posición |
| `_evaluate_tp_by_pct(...)` | Evalúa TP por porcentaje |
| `_move_sl_to_entry(...)` | Mueve SL al entry (si SL_MODE = "entry") |

### Importante

- **Obtiene qty real de Binance** via `exchange.get_open_positions(symbol=symbol)` (NO `get_position_info` — no existe)
- TP y Trailing **no compiten**: TP cierra parcial, trailing sigue con restante
- Throttle: 10s mínimo entre acciones por símbolo

---

## 10. Daily Loss Guard

**Archivo:** `execution/event_loop.py` → `_daily_loss_exceeded()`

- Reset diario UTC: `day_start_equity = equity`
- `dd_pct = ((start - equity) / start) * 100`
- Si `dd_pct >= daily_loss_limit_pct` → **bloquea nuevas entradas**
- **NO cierra posiciones existentes**, trailing/TP siguen activos
- Notifica por Telegram
- Log: `[DAILY LOSS]`

---

## 11. Reconciliation

**Archivo:** `execution/event_loop.py` → `reconcile_filled_orders()`

1. Posiciones abiertas en Binance pero no en DB → `_adopt_manual_position()`
2. Posiciones cerradas en Binance → calcula PnL real, cierra en DB
3. Reducciones parciales → actualiza `qty` en DB

Al cerrar: limpia `position_ids`, `trail`, `stop_orders` de state + `tp_manager.reset_symbol()`

---

## 12. Datafeed y Market Cache (Multi-Timeframe)

**Archivo:** `datafeed/market_cache.py` — `MarketCache`

Cachea **múltiples DataFrames por símbolo** (5m y 15m).

### Estructura

```python
self.cache = {
    "ETHUSDT": {
        "5m": MarketData(df_5m, ...),
        "15m": MarketData(df_15m, ...),
        "mark_price": 1234.56
    }
}
```

### Funcionamiento

- `init_cache(symbols)`: descarga velas de TODOS los timeframes requeridos por símbolo
- `update_all(symbols)`: poll cada `KLINE_POLL_SECONDS` (15s) para CADA timeframe independientemente
- `get_df_copy(symbol, interval)`: devuelve DF del timeframe específico
- `get_mark_price_cached(symbol)`: precio mark cacheado

### Throttles

```python
KLINE_POLL_SECONDS = 15    # cada cuánto revisa velas nuevas
MARK_POLL_SECONDS = 3      # cada cuánto actualiza mark price
```

---

## 13. Exchange (Binance)

**Archivo:** `exchange/binance_futures.py` — `BinanceFutures`

### Métodos disponibles

| Método | Propósito |
|--------|-----------|
| `get_klines_rest(symbol, interval, limit)` | Descarga velas |
| `get_mark_price(symbol)` | Precio mark |
| `get_open_positions(symbol=None)` | Posiciones abiertas (lista de dicts) |
| `get_position_history(symbol, open_time)` | Info de cierre de posición |
| `get_position_close_info(symbol, open_time_ms)` | Info de cierre |
| `get_equity()` | Equity total |
| `get_account_info()` | Account snapshot |
| `get_atr_pct(symbol)` | ATR como % del precio |
| `get_spread_pct(symbol, cache_seconds)` | Spread bid/ask |
| `market_buy / market_sell(symbol, qty)` | Órdenes market |
| `place_stop_market(...)` | Stop market order |
| `cancel_order(symbol, order_id)` | Cancelar orden |
| `set_margin_and_leverage(symbol, leverage, margin_type)` | Set leverage |
| `symbol_exists_in_futures(symbol)` | Verificar símbolo |
| `get_symbol_filters(symbol)` | Filtros (step, min qty, tick) |

### NO existe

- ~~`get_position_info(symbol)`~~ — usar `get_open_positions(symbol=symbol)` y tomar `[0]`

### Cache

- ExchangeInfo: `APICache(ttl=60s)`
- Account/spread: `APICache(ttl=2s)` — configurable via `API_CACHE_TTL_SECONDS`

---

## 14. Infra

**Archivo:** `infra/api_cache.py` — `APICache`

Cache genérico con TTL para llamadas REST. Usado por `BinanceFutures` para exchange info y account data.

```python
cache = APICache(ttl=5)
result = cache.get("key", fetch_function)  # devuelve cacheado si < 5s
```

---

## 15. Notifications (Telegram)

**Archivo:** `notifications/telegram.py` — `Telegram`

### Métodos

| Método | Propósito |
|--------|-----------|
| `send(message)` | Envía mensaje al chat |
| `poll_once(st, exchange, db)` | Procesa comandos entrantes |

### Comandos disponibles

| Comando | Acción |
|---------|--------|
| `/dashboard` | Resumen de cuenta y posiciones |
| `/pause` / `/resume` | Control del bot |
| `/set_risk N` | Cambiar riesgo % |
| `/set_leverage N` | Cambiar apalancamiento |
| `/close SYMBOL` | Cerrar posición manual |
| `/help` | Lista completa |

### Errores comunes

- Token/chat_id `None` → `send()` falla silenciosamente o crashea
- Fix: try/except alrededor de `send()` en startup

---

## 16. Base de Datos

**Archivo:** `db.py` — `Database`

### Tablas

```sql
positions               -- trades abiertos/cerrados, entry/exit, pnl, strategy_tag
position_stops          -- historial de SL por posición
position_events         -- eventos: TAKE_PROFIT, TAKE_PROFIT_PCT, PARTIAL_CLOSE
bot_state               -- estado del bot (JSON serializado)
account_snapshots       -- equity/margin/available cada 15s
equity_snapshots        -- equity histórico cada 60s
signals                 -- señales generadas (para análisis)
```

### Notas importantes

- `positions.strategy_tag` se guarda con cada posición (ej: "rsi_bb_reversion", "macd_momentum")
- `positions.realized_pnl` guarda el PnL **neto** (después de restar comisiones)
- `positions.signal_features` guarda ML features de la señal que generó la posición (JSON)

### Métodos clave

| Método | Propósito |
|--------|-----------|
| `load_state()` | Carga estado del bot desde DB |
| `save_state(state_dict)` | Guarda estado |
| `save_position(...)` | Crea/actualiza posición |
| `close_position(...)` | Cierra posición con PnL |
| `save_account_snapshot(...)` | Snapshot de cuenta |
| `save_equity_snapshot(...)` | Snapshot de equity |

### Fuente de verdad

- **DB es la fuente de verdad** para el estado del bot
- `config.py` tiene defaults, DB los sobrescribe
- Al startup: `db.load_state()` → merge con defaults → `BotState(**merged)`
- Dashboard modifica DB → bot reloadea cada 30s

---

## 17. Estado Persistente

**Archivo:** `core/models.py` — `BotState`

### Todos los campos

```python
@dataclass
class BotState:
    # Control
    paused: bool
    paper_trading: bool

    # Riesgo
    risk_pct: float                    # % del equity por trade
    leverage: int                      # apalancamiento
    max_positions: int                 # máximo de posiciones simultáneas
    daily_loss_limit_pct: float        # límite de pérdida diaria (%)

    # Símbolos y estrategia
    symbols: List[str]
    strategy_mode: str                 # "ema_breakout"|"stop_hunt"|"rsi_bb_reversion"|"macd_momentum"|"auto"|"all"
    timeframe: str                     # "5m", "15m", etc.

    # Trailing
    trailing_pct: float
    trailing_automatico: bool          # alias de trailing_use_atr
    trailing_activation_pct: float
    trailing_use_atr: bool
    trailing_atr_mult: float

    # Take Profit
    use_take_profit: bool
    tp_by_pct: bool
    tp_activation_pct: float
    tp_close_pct: float
    tp_sl_mode: str                    # "trailing"|"entry"
    tp_use_mark: bool

    # EMA Breakout
    ema_fast: int
    ema_slow: int
    pivot_len: int
    adx_min: float
    adx_rising: bool
    cooldown_bars: int
    vol_min_ratio: float

    # Stop Hunt
    stop_hunt_wick_pct: float
    stop_hunt_rejection_ratio: float
    stop_hunt_min_zones: int
    stop_hunt_max_zone_distance_pct: float
    stop_hunt_sl_pct: float
    stop_hunt_min_volume_ratio: float
    stop_hunt_use_ema_filter: bool
    stop_hunt_min_break_candles: int
    stop_hunt_atr_mult_sl: float
    stop_hunt_momentum_bars: int
    stop_hunt_min_atr_pct: float
    stop_hunt_adx_min: float
    order_block_lookback: int

    # Runtime state (NO se exponen en dashboard)
    trail: dict                        # trailing stops activos
    position_ids: dict                 # symbol → position_id
    stop_orders: dict                  # symbol → {order_id, is_algo, stop_price}
    cooldown: dict                     # symbol → {until_ms, bars}
    day_key: str                       # "YYYY-MM-DD" UTC
    day_start_equity: float
```

### sync_cfg_from_state(st)

Corre cada 30s. Copia valores de `st` a `config.CFG` runtime para que los strategy files lean sin pasar `st` por parámetro. Ver `bot.py:32-64`.

---

## 18. Config ↔ Dashboard ↔ DB

### Pipeline de guardado

```
Dashboard Form → JS serializa → POST /update-config
                                        ↓
                             dashboard/routers/config.py
                             allowed_keys valida
                             db.save_state(state)
                                        ↓
                             bot.py reload (30s)
                             sync_cfg_from_state(st)
                                        ↓
                          strategy files leen CFG runtime
```

### Checkbox handling (base.html)

Los checkboxes NO aparecen en FormData si están unchecked. Fix: inicializar TODOS los checkboxes con `.checked` ANTES del forEach loop.

```javascript
const checkboxIds = ['paused', 'paper_trading', 'trailing_automatico', ...];
checkboxIds.forEach(id => {
    const el = document.getElementById(id);
    if (el) data[id] = el.checked;  // siempre envía true o false
});
```

### allowed_keys (dashboard/routers/config.py)

Lista blanca de campos que el dashboard puede modificar. Si un campo no está aquí, el dashboard NO puede cambiarlo.

---

## 19. Dashboard

**Archivos:**
- `dashboard/app.py` — FastAPI app
- `dashboard/templates/index.html` — UI principal
- `dashboard/templates/base.html` — JS serialización
- `dashboard/routers/config.py` — endpoint `/update-config`
- `dashboard/routers/positions.py` — endpoints de posiciones
- `dashboard/routers/trades.py` — endpoints de trades
- `dashboard/services/dashboard_service.py` — lógica de negocio

### Tabs

| Tab | Contenido |
|-----|-----------|
| Overview | Equity, drawdown, PnL, posiciones abiertas |
| Performance | Stats diarias, trades, exportar CSV |
| Advanced Stats | Sharpe, recovery, expectancy, profit factor |
| Analytics | Análisis detallado por símbolo |
| Calendar | PnL por día (heatmap) |
| Trailing | Tabla de trailing activos por símbolo |
| Rendimiento | Estadísticas por estrategia: trades, WR, PF, PnL neto |
| Config Generales | Control, Riesgo, Ejecución, Trailing, Take Profit |
| Config Breakout | EMA 25/50, Volume, ADX, Pivot, EMA v2 filtros |
| Config Stop Hunt | Parámetros de Stop Hunt |
| Config RSI+BB | RSI, Bollinger Bands, Filtros, SL |
| Config MACD | MACD, Filtros, SL |
| Config Structure | Parámetros de Structure Break |

### Autenticación

`DASHBOARD_PASSWORD` en `.env`. Session cookie después de login.

---

## 20. Backtesting

**Archivo:** `backtest.py`

### Uso

```bash
python backtest.py --strategy ema_breakout --days 30 --capital 170
python backtest.py --symbol BTCUSDT --strategy stop_hunt
python backtest.py --symbols "ETHUSDT,BNBUSDT,SOLUSDT" --strategy ema_breakout
python backtest.py --strategy rsi_bb_reversion --symbols "ETHUSDT,XRPUSDT,1000PEPEUSDT"
python backtest.py --all  # prueba las 5 estrategias
```

### Qué incluye

- Fetch de datos históricos de Binance Futures (con rate limiting 0.5s entre descargas)
- Simulación bar-a-bar reutilizando estrategias del bot
- Trailing stop, take profit escalonado
- Comisiones reales (0.04%)
- Reporte: win rate, profit factor, Sharpe, max DD, por símbolo, por razón de salida

### Arquitectura

```
backtest.py
├── BacktestConfig      ← parámetros del backtest
├── BacktestEngine      ← simulador
│   ├── run(data)       ← loop principal
│   ├── _check_signal() ← genera señal
│   ├── _update_position() ← trailing, TP, SL
│   └── _close_position()  ← cierra trade
├── fetch_klines()      ← descarga de Binance
└── main()              ← CLI
```

---

## 21. Risk Monitor

**Archivo:** `core/risk_monitor.py` — `RiskMonitor`

Módulo de monitoreo de riesgo activo. Se ejecuta cada ciclo del main loop. Checks:
- Margin usage >= 70% → alerta, >= 80% → crítico
- Exposure/Equity >= 5x → alerta
- Concentración por símbolo >= 60% → alerta
- Daily loss limit → alerta (no cierra posiciones)

Cooldown entre alertas: 10 min. Usa `get_used_margin()`, `get_available_balance()` y `get_total_exposure_notional()` del exchange.

---

## 22. Mapa de Archivos

### Raíz

| Archivo | Propósito |
|---------|-----------|
| `bot.py` | Entry point, main loop, component wiring |
| `config.py` | Todos los parámetros (defaults + runtime) |
| `db.py` | PostgreSQL connection y queries |
| `backtest.py` | Backtesting engine |
| `beast-db.sql` | Schema de la DB |

### `strategy/`

| Archivo | Propósito |
|---------|-----------|
| `ema_adx_breakout.py` | Estrategia EMA Breakout (15m) |
| `stop_hunt.py` | Estrategia Stop Hunt (5m) |
| `rsi_bb_reversion.py` | Estrategia RSI + Bollinger Band (5m) |
| `macd_momentum.py` | Estrategia MACD Momentum (15m) |
| `structure_break.py` | Estrategia Market Structure Break + Retest (5m) 🆕 |
| `signal_engine.py` | Motor multi-estrategia (5 en paralelo) |
| `indicators.py` | EMA, ATR, ADX, RSI, Bollinger, Stochastic, MACD |
| `pivots.py` | Pivot highs/lows vectorizados |

### `execution/`

| Archivo | Propósito |
|---------|-----------|
| `event_loop.py` | Guards, reconciliation, loop principal |
| `order_manager.py` | Ejecución de órdenes, SL management |
| `trailing.py` | Trailing stop manager |
| `take_profit_manager.py` | Take profit manager |
| `signal_bus.py` | Cola de señales entre strategy y execution |

### `exchange/`

| Archivo | Propósito |
|---------|-----------|
| `binance_futures.py` | Wrapper REST Binance Futures |

### `datafeed/`

| Archivo | Propósito |
|---------|-----------|
| `market_cache.py` | Cache de velas y mark prices |

### `core/`

| Archivo | Propósito |
|---------|-----------|
| `models.py` | BotState, SignalEvent, MarketData dataclasses |
| `logging_setup.py` | Configuración de logging |
| `utils.py` | Utilidades (utc_day_key, etc.) |
| `risk_monitor.py` | Monitor de riesgo (desactivado) |

### `infra/`

| Archivo | Propósito |
|---------|-----------|
| `api_cache.py` | Cache genérico con TTL |

### `notifications/`

| Archivo | Propósito |
|---------|-----------|
| `telegram.py` | Bot de Telegram (envío + comandos) |

### `dashboard/`

| Archivo | Propósito |
|---------|-----------|
| `app.py` | FastAPI application |
| `templates/index.html` | UI principal |
| `templates/base.html` | JS serialización forms |
| `routers/config.py` | Endpoint update-config |
| `routers/positions.py` | Endpoints de posiciones |
| `routers/trades.py` | Endpoints de trades |
| `services/dashboard_service.py` | Lógica de negocio dashboard |

---

## 23. Estrategias Fallidas (Registro)

Estrategias probadas y descartadas. No re-probar sin cambios fundamentales.

| Estrategia | Timeframe | Mejor PF | Problema |
|-----------|-----------|----------|----------|
| EMA Breakout (vieja 9/21) | 5m | 0.96 | WR 75% pero Avg Loss 3x Avg Win. Pérdidas grandes. |
| EMA Breakout (vieja 9/21) | 15m | 1.40 | Marginal con 9/21. OPTIMIZADA a 25/50 + ADX 25 = PF 3.97. |
| EMA original 15m | 15m | 1.36 | PF 1.36, WR 55%. OPTIMIZADA con filtros de features. |
| Donchian Channel | 5m | 0.88 | Perdedor en 5m. |
| Donchian Channel | 15m | 1.25 | Marginal. No justifica usarla. |
| Supertrend | 5m | 0.91 | Perdedor. Cálculo iterativo lento. |
| Supertrend | 15m | 0.66 | Terrible. |
| Keltner Channel | - | - | No testeada (usuario descartó antes de probar). |
| BB Squeeze | 5m/15m | 1.78 | Top 3 15m: PF 1.56. No suficiente. |
| Funding Rate Filter | - | - | Rates demasiado bajos (max 0.01%). No filtra nada. |
| Extreme Price Zone | 15m | 1.75 | Solo 2 símbolos con PF > 1.3. Insuficiente. |
| VWAP Refresh | 5m | - | 0 trades. Eliminada completamente. |
| Market Regime | - | - | Sistema de auto-detección. Reemplazado por auto=fixed. |
| Liquidation Cascade | 1h | 1.23 | WR 58% pero PF bajo. Trailing 0.35% cierra ganancias muy pronto. 18 símbolos probados. |
| Momentum Divergence | 1h | 0.36 | Solo 8 trades, 0% WR. Filtros demasiado estrictos, no genera señales suficientes. |
| Smart Money Flow | 1h | inf | Solo 2 trades (100% WR pero muestra insuficiente). Concepto bueno, implementación muy restrictiva. |
| Volatility Breakout | 1h | 1.07 | 126 trades pero PF marginal. Demasiados trades perdedores (AVAXUSDT -$0.68). Comisiones comen ganancias. |

**Lecciones aprendidas (1h):**
- Volatility Squeeze funciona: detectar compresión + dirección del swing + tendencia EMA
- Liquidation Cascade no funciona: trailing muy apretado vs SL amplio (ratio 1:3)
- Momentum Divergence: demasiados filtros, no genera señales
- Smart Money Flow: concepto bueno pero demasiado restrictivo
- Volatility Breakout puro: demasiados falsos positivos, comisiones altas

**Lecciones aprendidas (5m/15m):**
- Breakouts directos en 5m no funcionan (ruido alto, tendencias débiles)
- SL desde entry es mejor que SL desde pivot
- RSI filter (30/70) reduce falsos positivos
- Volume spike mínimo 2x es necesario para cualquier breakout
- Timeframes más altos (15m) favorecen estrategias de tendencia

---

## 24. Telegram Comandos

### Comandos disponibles

| Comando | Descripción |
|---------|-------------|
| `/dashboard` | Resumen: equity, exposure, daily PnL, drawdown, strategy |
| `/positions` | Posiciones abiertas con mark, pnl%, trailing, SL |
| `/strategies` | Lista estrategias activas con símbolos y timeframe |
| `/symbols` | Símbolos agrupados por estrategia |
| `/volatility` | ATR% de todos los símbolos |
| `/performance` | Daily realized PnL |
| `/risk` | Config de riesgo |
| `/trail` | Config de trailing |
| `/pause /resume` | Control del bot |
| `/close SYMBOL` | Cerrar posición |
| `/close_all confirm` | Cerrar todas |
| `/set_leverage N` | Cambiar leverage |
| `/set_risk N` | Cambiar risk% |
| `/set_trailing N` | Cambiar trailing% |
| `/set_activation N` | Cambiar activation% |
| `/set_maxpos N` | Cambiar max positions |
| `/paper_mode` | Toggle paper trading |

### Notificaciones automáticas

| Evento | Emoji | Info mostrada |
|--------|-------|---------------|
| Nueva posición | 📈/📉 | entry, qty, notional, SL, leverage, riesgo, estrategia |
| SL actualizado | 📈/📉 | SL nuevo, distancia, mark, PnL% y USDT |
| Trailing activado | 🔒 | mark, SL, PnL% y USDT, qty |
| TP hit | 🎯 | profit%, cerrado%, restante, PnL USDT, estrategia |
| Posición cerrada | 🟢/🔴 | entry→exit, PnL%, PnL USDT, comisión, neto, duración |
| Error | ⚠️ | Descripción del error |

---

## 25. Logs y Debug

### Tags de log

| Tag | Significado |
|-----|-------------|
| `[CACHE INIT]` | Carga inicial de velas |
| `[CACHE]` | Actualización de cache (nueva vela) |
| `[STARTUP]` | Bot listo para operar |
| `[LOOP]` | Main loop iniciado |
| `[DAILY LOSS]` | Límite de pérdida diaria |
| `[SPREAD]` | Filtro de spread |
| `[SLIPPAGE]` | Guard de slippage |
| `[TRAIL]` | Trailing stop update |
| `[TP%]` | Take profit por porcentaje |
| `[RECONCILE]` | Reconciliation DB ↔ Binance |
| `[MANUAL POS]` | Posición manual adoptada |
| `[COOLDOWN]` | Símbolo en cooldown |
| `[STRATEGY]` | Cambio de estrategia |
| `[SYMBOLS]` | Cambio de símbolos |

### Comandos útiles

```bash
# Ver señales en tiempo real
tail -f logs/bot.log | grep "trend="

# Ver entradas/salidas
tail -f logs/bot.log | grep "ENTRY\|EXIT\|CLOSE"

# Ver trailing
tail -f logs/bot.log | grep "\[TRAIL\]"

# Ver take profit
tail -f logs/bot.log | grep "\[TP"

# Ver errores
tail -f logs/bot.log | grep "ERROR\|WARNING\|Bot error"

# Ver reconciliation
tail -f logs/bot.log | grep "\[RECONCILE\]"

# Ver señales RSI+BB
tail -f logs/bot.log | grep "rsi_bb_reversion"
```

---

## Reglas de Oro

1. **No cambiar varios parámetros a la vez** — uno a la vez, evaluar resultados
2. **Probar en backtest antes de producción** — `./venv/bin/python backtest.py --all` (usar venv)
3. **No agregar imports que no existan** — verificar contra código real
4. **Métricas > intuición** — win rate, profit factor, max DD
5. **El bot debe ser resiliente** — nunca crashear permanentemente
6. **DB es fuente de verdad** — no confiar solo en config.py
7. **sync_cfg_from_state** — cada cambio de BotState debe reflejarse en CFG
