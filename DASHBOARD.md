# DASHBOARD.md — Referencia Rápida del Dashboard

## Propósito
Archivo de referencia para el dashboard. Consultar antes de modificar o agregar features. Mantener actualizado con cada cambio significativo.

---

## Arquitectura

```
Browser
  ├── index.html          ← 8 tabs, extiende base.html
  ├── login.html         ← página de login
  └── base.html          ← navbar, CSS, JS global

FastAPI (main.py)
  ├── dashboard.py       ← GET /, GET /login, POST /login, GET /logout
  ├── api.py             ← 14 endpoints /api/*
  └── config.py          ← POST /update-config

Services
  ├── dashboard_service.py  ← build_dashboard_context()
  └── exchange_cache.py     ← ExchangeCache (hilo en background, refresh cada 10s)

Dependencies
  └── dependencies.py       ← db, exchange, exchange_cache singletons
```

---

## Seguridad

```
1. Server start → genera SERVER_SESSION_TOKEN (secrets.token_urlsafe(32))
2. GET / → verify_session() valida cookie auth_token
3. Sin cookie / token wrong → HTTP 307 redirect /login
4. POST /login + password correcta → set HttpOnly cookie (1hr)
5. Logout → limpia cookie
```

- Password: variable de entorno `DASHBOARD_PASSWORD`
- Comparación timing-safe con `secrets.compare_digest`

---

## Tabs (Bootstrap 5 pills, una fila con mt-4 y mb-4)

| Tab | ID | Contenido principal |
|-----|----|---------------------|
| Overview | `#overview` | Stats cards, equity chart, drawdown chart, open positions |
| Performance | `#performance` | Closed trades, export, symbols status |
| Stats Avanzadas | `#advanced-stats` | Sharpe, recovery, expectancy, streaks |
| Analytics | `#analytics` | Per-symbol analytics, commissions |
| Calendario PnL | `#calendar` | Daily PnL calendar, summary stats |
| Trailing | `#trailing-tab` | Estado trailing en tiempo real, tabla ordenable |
| Rendimiento | `#strategy-performance` | Estadísticas por estrategia: trades, WR, PF, PnL neto |
| Config Generales | `#config-generales` | Control, Riesgo, Ejecución, Trailing, Take Profit |
| Config Breakout | `#config-breakout` | EMA 25/50, Volume, ADX, Pivot, EMA v2 filtros |
| Config Stop Hunt | `#config-stophunt` | 12 parámetros Stop Hunt |
| Config RSI+BB | `#config-rsi-bb` | RSI, Bollinger Bands, Filtros, SL |
| Config MACD | `#config-macd` | MACD settings, Filtros, SL |
| Config Structure | `#config-structure` | Parámetros Structure Break |

---

## Formularios de Configuración

### Formato de campos en JS (`base.html`)

| Tipo | Cómo se serializa |
|------|-----------------|
| Checkbox | `document.getElementById("id").checked` |
| Números float | `Number(value)` |
| Integers | `parseInt(value, 10)` |
| Strings (timeframe, strategy_mode, tp_sl_mode) | valor directo |
| symbols | `value.split(",").map(s => s.trim())` |

**Checkboxes manejados explicitamente:**
`paused`, `paper_trading`, `adx_rising`, `trailing_automatico`, `trailing_use_atr`, `use_take_profit`, `tp_by_pct`, `stop_hunt_use_ema_filter`

### Pipeline de guardado

```
Formulario → JS serializa → POST /update-config
                                      ↓
                           dashboard/routers/config.py
                           allowed_keys valida
                           db.save_state(state)
                                      ↓
                           bot.py reload (30s)
                           sync_cfg_from_state(st)
                                      ↓
                    execution files leen CFG runtime
```

---

## Endpoints REST (`/api/*`)

| Método | Path | Descripción | Frecuencia polling |
|--------|------|-------------|--------------------|
| GET | `/api/stats` | Stats, account, daily PnL (DB + Binance) | 5s |
| GET | `/api/open-positions/pnl` | Unrealized PnL, mark price, % por símbolo | 5s |
| GET | `/api/trailing-status` | Estado del trailing por símbolo | 5s |
| GET | `/api/symbols-status` | Estado global de símbolos | 5s |
| GET | `/api/health` | Binance API reachability + latency | 20s |
| GET | `/api/timeframe` | Timeframe actual + display | 30s |
| GET | `/api/analytics` | Analytics por símbolo con filtros | manual |
| GET | `/api/closed-positions` | Trades cerrados con filtros | manual |
| GET | `/api/daily-pnl` | Calendario diario con summary | manual |
| GET | `/api/export/trades` | CSV de trades con filtros | manual |
| POST | `/api/positions/{symbol}/close` | Cerrar posición al mercado | manual |
| GET | `/api/trailing-status` | **Enriquecido**: incluye mark_price, pnl_pct, dist_sl_pct | 5s |
| GET | `/api/sparkline/{symbol}` | Últimos 50 closes de 5m para sparkline | manual |
| GET | `/api/benchmark-btc` | BTCUSDT normalizado al equity inicial | manual |

### `/api/stats` — fuente de verdad

```python
# Prioriza Binance real sobre DB local
daily_pnl_binance = exchange.get_daily_realized_pnl()  # si existe
daily_pnl_db = stats["daily_pnl"]
# UI usa Binance si está disponible, sino fallback a DB
```

---

## Allowed Keys — `/update-config`

**Control:** `paused`, `paper_trading`

**Riesgo:** `risk_pct`, `leverage`, `max_positions`, `daily_loss_limit_pct`

**Ejecución:** `symbols`, `timeframe`, `strategy_mode`, `cooldown_bars`, `pivot_len`

**Trailing:** `trailing_pct`, `trailing_active`, `trailing_automatico`, `trailing_activation_pct`, `trailing_use_atr`, `trailing_atr_mult`

**Take Profit:** `use_take_profit`, `tp_by_pct`, `tp_activation_pct`, `tp_close_pct`, `tp_sl_mode`

**Stop Hunt (12):** `stop_hunt_wick_pct`, `stop_hunt_rejection_ratio`, `stop_hunt_min_zones`, `stop_hunt_max_zone_distance_pct`, `stop_hunt_sl_pct`, `stop_hunt_min_volume_ratio`, `stop_hunt_use_ema_filter`, `stop_hunt_min_break_candles`, `stop_hunt_atr_mult_sl`, `stop_hunt_momentum_bars`, `stop_hunt_min_atr_pct`, `order_block_lookback`

### Validaciones

- `timeframe`: enum válido
- `strategy_mode`: `ema_breakout` | `stop_hunt` | `rsi_bb_reversion` | `macd_momentum` | `structure_break` | `auto` | `all`
- `risk_pct`: 0.1 - 10
- `leverage`: 1 - 50
- `pivot_len`: 5 - 50 (int)
- `tp_sl_mode`: `trailing` | `entry`
- Bools: casteados explícitamente a `bool`

---

## BotState ↔ Dashboard ↔ DB

- **DB** (`bot_state.state_json`): JSON plano con todos los campos de BotState
- **Startup**: `db.load_state()` → merge con defaults de BotState → fill missing keys → `BotState(**merged)` → `db.save_state()` al inicio
- **Sync runtime**: `sync_cfg_from_state(st)` corre cada 30s al reloadear estado desde DB y actualiza `config.py` runtime para que los strategy files lo lean. No recibe `db` — solo lee de `st` y escribe en `CFG`.

---

## ExchangeCache — Hilo en background

**Archivo:** `dashboard/services/exchange_cache.py`

```python
# Refresco cada 10s, exponential backoff en errores
# Datos cacheados: open_positions, account_info
```

**Health fields:** `is_running`, `last_success_age_seconds`, `is_stale` (>30s sin refresh), `error_rate_pct`, `consecutive_failures`

---

## Auto-refresh del navegador

| Qué | Endpoint | Intervalo |
|-----|----------|-----------|
| Stats, PnL, bot status | `/api/stats` | 5s |
| Unrealized PnL, Mark Price | `/api/open-positions/pnl` | 5s |
| Trailing y symbols status | `/api/trailing-status`, `/api/symbols-status` | 5s |
| Trailing tab | `/api/trailing-status` | 5s (carga completa) |
| Exchange health | `/api/health` | 20s |
| Timeframe display | `/api/timeframe` | 30s |
| Sparklines | `/api/sparkline/{symbol}` | 15s (cacheado) |
| **Reload completo** | — | **150s (2.5 min)** |

---

## Features implementadas

### Tab Trailing Activo

Nuevo tab con tabla de estado trailing en tiempo real. Columnas: Symbol, Side, Entry, Best, Mark, PnL %, Dist SL %, SL, Activo.

- Polling cada 5s via `/api/trailing-status` (enriquecido con mark_price y pnl_pct)
- También actualiza los badges de trailing en la tabla de posiciones abiertas
- Tabla ordenable por cualquier columna (click en header)

### Sparklines en posiciones abiertas

Canvas de 100x40px por símbolo en la columna "Sparkline" de la tabla de posiciones abiertas.

- Fetch via `/api/sparkline/{symbol}` (50 velas de 5m)
- Cacheado en `sparklineCache` para no repetir requests
- Color: lime si el último close >= primer close, rojo si baja
- Polling cada 15s

### Equity vs Benchmark BTC

Overlay de BTCUSDT (Buy & Hold) en el equity chart.

- Fetch via `/api/benchmark-btc`: obtiene BTCUSDT hourly desde la hora de inicio del equity
- Normalizado: `equity_inicial * (btc_precio / btc_inicial)`
- Se agrega como segunda dataset al equity Chart.js con línea dorada punteada
- Leyenda visible en el chart

### Tablas ordenables

Click en header de columna para ordenar (asc/desc). Indicador visual: ⇅ (neutral), ↑ (asc), ↓ (desc).

- **Performance → Closed Trades**: 6 columnas ordenables
- **Analytics**: 6 columnas ordenables
- **Trailing** (nuevo tab): 9 columnas ordenables

Ordenamiento 100% client-side (JavaScript). Los datos se guardan en `window._perfData` y `window._analytData` al init desde el HTML renderizado por Jinja.

---

## Variables de entorno del dashboard

| Variable | Descripción |
|---------|-------------|
| `BINANCE_API_KEY` | API key de Binance Futures |
| `BINANCE_API_SECRET` | API secret |
| `DASHBOARD_PASSWORD` | Password para login del dashboard |
| `POSTGRES_HOST` | Host de PostgreSQL |
| `POSTGRES_PORT` | Puerto de PostgreSQL |
| `POSTGRES_DB` | Nombre de la base |
| `POSTGRES_USER` | Usuario |
| `POSTGRES_PASSWORD` | Password |

---

## Lanzar el dashboard

```bash
cd beast-money-maker
source venv/bin/activate
uvicorn dashboard.main:app --host 0.0.0.0 --port 8000 --reload
```

O desde `run_dashboard.py` si existe.
