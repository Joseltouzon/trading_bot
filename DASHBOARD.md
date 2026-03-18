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
| Config Generales | `#config-generales` | Control, Riesgo, Ejecución, Trailing, Take Profit |
| Config Breakout | `#config-breakout` | EMA, Volume, ADX, Pivot, Trailing (Breakout) |
| Config Stop Hunt | `#config-stophunt` | 12 parámetros Stop Hunt |

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
- `strategy_mode`: `ema_breakout` | `stop_hunt`
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
| Exchange health | `/api/health` | 20s |
| Timeframe display | `/api/timeframe` | 30s |
| **Reload completo** | — | **150s (2.5 min)** |

---

## db.py — Métodos usados por el dashboard

| Método | Usado por | Retorna |
|--------|-----------|---------|
| `get_dashboard_stats()` | `DashboardService` | stats globales |
| `get_equity_curve()` | `DashboardService` | historial equity con timestamps |
| `get_drawdown_curve()` | `DashboardService` | drawdown % por timestamp |
| `calculate_drawdown()` | `DashboardService` | max drawdown % |
| `get_open_positions_with_stops()` | `api.py`, `DashboardService` | posiciones abiertas con SL/TP |
| `get_recent_closed_positions()` | `DashboardService`, `api.py` | trades cerrados recientes |
| `get_closed_positions_filtered()` | `api.py` | trades con filtros fecha/símbolo |
| `get_performance_metrics()` | `DashboardService` | win rate, profit factor, etc. |
| `get_trade_analytics()` | `DashboardService` | stats por símbolo |
| `get_advanced_metrics()` | `DashboardService` | sharpe, recovery, expectancy |
| `get_risk_reward_stats()` | `DashboardService` | R:R stats |
| `get_time_in_market()` | `DashboardService` | % tiempo en posición |
| `get_total_commissions()` | `DashboardService` | comisiones totales |
| `get_latest_account_snapshot()` | `DashboardService` | equity/margin/available |
| `get_daily_pnl_calendar()` | `api.py` | PnL diario + summary |
| `load_state()` | `DashboardService`, `config.py` | BotState completo |
| `save_state()` | `config.py` | persiste BotState |
| `get_bot_status()` | `DashboardService`, `api.py` | RUNNING/PAUSED/UNKNOWN |

---

## Cómo agregar un nuevo endpoint API

1. **Agregar endpoint en `dashboard/routers/api.py`**
2. **Agregar polling en `base.html`** si necesita refresh automático
3. **Agregar función JS en `base.html`** para actualizar el DOM
4. **Si es un nuevo dato**, puede requerir agregar método en `db.py` o usar `exchange_cache`

### Ejemplo: nuevo endpoint `/api/tp-status`

```python
# dashboard/routers/api.py
@router.get("/tp-status")
async def tp_status(db=Depends(get_db)):
    state = db.load_state()
    return {
        "use_take_profit": state.get("use_take_profit", False),
        "tp_by_pct": state.get("tp_by_pct", False),
        "tp_activation_pct": state.get("tp_activation_pct", 1.2),
        "tp_close_pct": state.get("tp_close_pct", 70),
    }
```

```javascript
// dashboard/templates/base.html (en el script de polling)
async function updateTpStatus() {
    const res = await fetch("/api/tp-status");
    // actualizar DOM
}
setInterval(updateTpStatus, 30000);
```

---

## Cómo agregar un nuevo campo de config

1. **Agregar a `core/models.py`** → `BotState` dataclass
2. **Agregar default en `bot.py`** → `defaults = BotState(...)` y en `sync_cfg_from_state()`
3. **Agregar a `dashboard/routers/config.py`** → `allowed_keys` + validaciones si corresponde
4. **Agregar input en `index.html`** → el tab que corresponda (generales/breakout/stophunt)
5. **Agregar checkbox handling en `base.html`** → si es bool, en el JS de serialización
6. **Sincronizar en `bot.py` reload** → ya lo hace `sync_cfg_from_state()` automáticamente

---

## Cómo agregar un nuevo tab de config

1. **Agregar `<li>` en `index.html`** → dentro del `<ul class="nav nav-pills mb-4 mt-4">`
2. **Agregar `<div class="tab-pane fade" id="nuevo-tab">`**
3. **Crear el contenido del tab** → con sus inputs
4. **Verificar que el form `<form id="configForm">`** cubra el tab (el save es único para todo el form)
5. **El tab persistirá automáticamente** en `localStorage` gracias al script de tab persistence en `base.html`

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
