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
ADX_PERIOD = 14
ATR_PERIOD = 14
PIVOT_LEN = 8
DEFAULT_ADX_MIN = 20.0
REQUIRE_ADX_RISING = False
VOLUME_MIN_RATIO = 1.20
MIN_BREAK_DISTANCE_PCT = 0.15
MIN_BODY_RATIO = 0.55

# =========================
# EXECUTION / RISK
# =========================
DEFAULT_RISK_PCT = 1.0
MAX_RISK_PCT_ALLOWED = 10.0
MIN_NOTIONAL_USDT = 20          # CRÍTICO: No borrar, Binance exige min ~20USDT
DEFAULT_LEVERAGE = 5
MAX_OPEN_POSITIONS = 1
MARGIN_TYPE = "ISOLATED"

# Stop / trailing
TRAILING_PCT = 0.5              # Solo usa si TRAILING_USE_ATR = False
TRAILING_ACTIVATION_PCT = 0.5
TRAILING_USE_ATR = True         # ✅ Activo: Usa volatilidad
TRAILING_ATR_MULT = 1.5
MIN_INITIAL_SL_PCT = 0.35       # Mínimo SL inicial
INITIAL_SL_ATR_MULT = 2.2

# Cooldown / daily loss
DEFAULT_COOLDOWN_BARS = 4
DEFAULT_DAILY_LOSS_LIMIT_PCT = 10.0
MIN_SECONDS_BETWEEN_ENTRIES = 45

# Filters
MAX_SPREAD_PCT = 0.10
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