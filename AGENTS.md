# Agents Instructions

## Product Overview
Bot de trading algorítmico para Binance Futures (USDT-M) que opera con breakouts de pivots confirmados por EMA, ADX y volumen. Sistema completo de gestión de riesgo, notificaciones Telegram y dashboard en tiempo real.

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

### Folder structure
```text
.
├── AGENTS.md                 # This file
├── README.md                 # User documentation
├── bot.py                    # Main entry point
├── config.py                 # Strategy & execution params
├── db.py                     # PostgreSQL connection
├── strategy/                 # Signal logic (EMA, ADX, Pivots)
├── execution/                # Order mgmt, trailing, events
├── exchange/                 # Binance Futures wrapper
├── core/                     # Models, logging, utilities
├── dashboard/                # FastAPI dashboard + Telegram cmd
├── datafeed/                 # Market cache & indicators
├── notifications/            # Telegram alerts
├── analysis/                 # Bot analyzer, anomaly detect
└── logs/                     # Bot activity logs
```

## Environment
- Code and documentation are in Spanish.
- Chat responses must match user prompt language.
- Sacrifice grammar for conciseness in responses.
- macOS/Linux environment using zsh/bash terminal.
- Default branch is `master`.
- Trading bot requires: PostgreSQL running, Binance API keys, Telegram bot token.
- Paper trading mode available via PAPER_TRADING env var.
