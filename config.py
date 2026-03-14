# config.py
# =========================
# SYMBOLS / TF
# =========================
SYMBOLS = ["BTCUSDT", "BNBUSDT", "XRPUSDT"]
INTERVAL = "5m"
KLINES_LIMIT = 500

# =========================
# STRATEGY
# =========================
EMA_FAST = 9
EMA_SLOW = 21
MIN_EMA_SLOPE_PCT = 0.01
ADX_PERIOD = 14
ATR_PERIOD = 14
PIVOT_LEN = 5
DEFAULT_ADX_MIN = 20.0
REQUIRE_ADX_RISING = False
VOLUME_MIN_RATIO = 1.20
MAX_VOLUME_RATIO = 3.5
MIN_BREAK_DISTANCE_PCT = 0.05
MIN_BODY_RATIO = 0.50
MIN_ATR_PCT = 0.15
# Momentum trigger
MOMENTUM_LOOKBACK = 3
MIN_MOMENTUM_PCT = 0.12         # 0.15% de movimiento en 3 velas (15 min en 5m)
MAX_PIVOT_AGE = 15              # Pivot debe tener <= 15 velas de antigüedad
MIN_PIVOT_DISTANCE_PCT = 0.10   # Mínimo 0.15% entre precio y pivot para entrar
SL_BUFFER_PCT = 0.0012          # Buffer 0.12% extra en SL contra stop hunts

# =========================
# EXECUTION / RISK
# =========================
DEFAULT_RISK_PCT = 1.0
MAX_RISK_PCT_ALLOWED = 10.0
MIN_NOTIONAL_USDT = 20          # CRÍTICO: No borrar, Binance exige min ~20USDT
DEFAULT_LEVERAGE = 5
MAX_OPEN_POSITIONS = 1
MARGIN_TYPE = "ISOLATED"
# =========================
# MARGIN / RISK
# =========================
MARGIN_SAFETY_BUFFER = 0.03     # 3% buffer extra para evitar -2019 en Binance, margin insufficient

# Stop / trailing
TRAILING_PCT = 0.5              # Solo usa si TRAILING_USE_ATR = False
TRAILING_ACTIVATION_PCT = 0.5
TRAILING_USE_ATR = True         # ✅ Activo: Usa volatilidad
TRAILING_ATR_MULT = 0.7
MIN_INITIAL_SL_PCT = 0.35       # Mínimo SL inicial
INITIAL_SL_ATR_MULT = 0.7

# Cooldown / daily loss
DEFAULT_COOLDOWN_BARS = 4
DEFAULT_DAILY_LOSS_LIMIT_PCT = 10.0
MIN_SECONDS_BETWEEN_ENTRIES = 45

# Filters
MAX_SPREAD_PCT = 0.12
SPREAD_CACHE_SECONDS = 3
MAX_SLIPPAGE_RATIO = 0.003
FUNDING_THRESHOLD = 0.0005

# =========================
# REST POLLING
# =========================
LOOP_SLEEP_SECONDS = 0.5
KLINE_POLL_SECONDS = 15
MARK_POLL_SECONDS = 3

# =========================
# BINANCE CLIENT
# =========================
TESTNET = False
API_CACHE_TTL_SECONDS = 2
EXCHANGE_INFO_TTL_SECONDS = 60

# ============================================================
# TAKE PROFIT ESCALONADO
# ============================================================
USE_TAKE_PROFIT = False

# Niveles de TP: [R:R, % a cerrar, ¿mover SL a Breakeven?]
TP_LEVELS = [
    {"ratio": 3.5, "close_pct": 50, "move_sl_to_be": True},   # 50% en 1.5R → SL a Entry
    {"ratio": 5.0, "close_pct": 30, "move_sl_to_be": False},  # 30% en 2.5R → dejar correr
    {"ratio": 6.0, "close_pct": 20, "move_sl_to_be": False},  # 20% en 4.0R → moonbag
]

MIN_R_FOR_FIRST_TP = 2.2      # No activar TP si R:R < 1.2 (evitar ruido)
TP_THROTTLE_SECONDS = 10      # Mínimo tiempo entre ejecuciones de TP por símbolo
TP_USE_MARK_PRICE = True      # Usar Mark Price (no last) para evaluar TP