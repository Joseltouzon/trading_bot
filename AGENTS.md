# Agents Instructions

## Product Overview
Bot de trading algorítmico para Binance Futures (USDT-M) con **dos estrategias seleccionables**: EMA Breakout y Stop Hunt. Sistema completo de gestión de riesgo, notificaciones Telegram y dashboard en tiempo real.

## Estrategias Disponibles

### 1. EMA Breakout (default)
- **Lógica**: Breakout de pivot high/low confirmado por EMA, ADX y volumen
- **Filtros**: ADX > 20, volumen 120-350%, ATR > 0.15%, momentum de 3 velas
- **Más información**: strategy/ema_adx_breakout.py

### 2. Stop Hunt
- **Lógica**: Busca zonas de liquidez (pivots + order blocks), detecta stop hunts y entra en el rechazo
- **Zonas de liquidez**: Últimos 3-5 swing highs/lows + order blocks institucionales
- **Confirmación**: Mecha que atraviesa zona + rechazo con body/wick ratio > 0.5
- **Más información**: strategy/stop_hunt.py

### Cambiar estrategia
```sql
-- Via SQL
UPDATE bot_state SET strategy_mode = 'stop_hunt' WHERE id = 1;

-- Via Dashboard
POST /update-config con { "strategy_mode": "stop_hunt" }
```

Valores válidos: `"ema_breakout"` | `"stop_hunt"`

## Technical Implementation

### Tech Stack
- Language: **Python 3**
- Framework: **FastAPI** (dashboard), **python-binance** (exchange)
- Database: **PostgreSQL** (historial trades, logs, estado bot)
- Security: **API Keys via .env, IP restriction, Isolated margin**
- Testing: **Manual test scripts** (test-db.py, test-binance-connect.py)
- Logging: **Python logging + RotatingFileHandler + PostgreSQL**

### Development workflow
```bash
# Set up the project
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
# Create .env with: BINANCE_API_KEY, BINANCE_API_SECRET, 
# TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

# Run the bot
python bot.py

# Run dashboard
uvicorn dashboard.main:app --reload

# Test database connection
python test-db.py
```

### Archivos clave por estrategia
```
strategy/
├── ema_adx_breakout.py    # Estrategia EMA Breakout
├── stop_hunt.py            # Estrategia Stop Hunt (NUEVO)
├── signal_engine.py        # Motor de señales (soporta ambas)
├── pivots.py               # Detección de pivots
└── indicators.py           # EMA, ADX, ATR

execution/
├── event_loop.py           # Guards (ADX solo aplica a EMA Breakout)
├── order_manager.py        # Ejecución de órdenes
├── trailing.py              # Trailing stop
└── take_profit_manager.py  # TP escalonado
```

### Parámetros Stop Hunt (config.py)
```python
STOP_HUNT_WICK_PCT = 0.15           # Mecha mínima para detectar hunt
STOP_HUNT_REJECTION_RATIO = 0.5     # Body/wick ratio mínimo
STOP_HUNT_MIN_ZONES = 3             # Zonas de liquidez a monitorear
STOP_HUNT_MAX_ZONE_DISTANCE_PCT = 1.5  # Distancia máxima precio-zona
STOP_HUNT_SL_PCT = 0.30             # SL como % del precio
STOP_HUNT_MIN_VOLUME_RATIO = 1.2    # Volumen mínimo
ORDER_BLOCK_LOOKBACK = 5             # Velas para buscar order blocks
STOP_HUNT_ATR_MULT_SL = 1.5         # Multiplicador ATR para SL
STOP_HUNT_MOMENTUM_BARS = 2        # Velas de momentum
```

## Flujo de señales

```
SignalEngine (signal_engine.py)
    │
    ├── strategy_mode == "ema_breakout"
    │   └── _process_ema_breakout() → compute_signals()
    │       └── Filtros: ADX, EMA slope, breakout pivot, volumen, ATR
    │
    └── strategy_mode == "stop_hunt"
        └── _process_stop_hunt() → compute_stop_hunt_signals()
            └── Detecta: zonas liquidez + stop hunt + rechazo

EventLoop (event_loop.py)
    │
    ├── strategy_type = signal.get("strategy")
    │
    ├── Si "ema_breakout": aplica filtros ADX
    │
    ├── Si "stop_hunt": salta filtros ADX
    │
    └── _build_signal_dict() → OrderManager.execute()
```

## Modelos importantes

### BotState (core/models.py)
```python
@dataclass
class BotState:
    paused: bool = False
    risk_pct: float = 1.0
    leverage: int = 5
    symbols: List[str]
    strategy_mode: str = "ema_breakout"  # ← NUEVO
    # ... otros campos
```

### SignalEvent (core/models.py)
```python
@dataclass(frozen=True)
class SignalEvent:
    symbol: str
    direction: str  # "LONG" | "SHORT"
    signal: dict   #包含 strategy, atr, signal_price, ml_features
    kline_close_time_ms: int
```

## Environment
- Code and documentation are in Spanish.
- Chat responses must match user prompt language.
- Sacrifice grammar for conciseness in responses.
- macOS/Linux environment using zsh/bash terminal.
- Default branch is `master`.
- Trading bot requires: PostgreSQL running, Binance API keys, Telegram bot token.
- Paper trading mode available via PAPER_TRADING env var.
