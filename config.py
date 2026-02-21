# config.py

# =========================
# STATE
# =========================
STATE_FILE = "state.json"

# =========================
# SYMBOLS / TF
# =========================
SYMBOLS = ["POLUSDT","SOLUSDT","XRPUSDT","BNBUSDT","LINKUSDT","DOGEUSDT","ADAUSDT","DOTUSDT"]
INTERVAL = "5m"
KLINES_LIMIT = 500

# =========================
# STRATEGY
# =========================
EMA_FAST = 9  # 20
EMA_SLOW = 21  #50

ADX_PERIOD = 14
ATR_PERIOD = 14
PIVOT_LEN = 4 # 5

DEFAULT_ADX_MIN = 18.0  # 18.0
REQUIRE_ADX_RISING = True

VOLUME_MIN_RATIO = 1.20  # 1.2

# =========================
# EXECUTION / RISK
# =========================
DEFAULT_RISK_PCT = 1.0  # 1.0
MAX_RISK_PCT_ALLOWED = 10.0
MIN_NOTIONAL_USDT = 20

DEFAULT_LEVERAGE = 5
MAX_OPEN_POSITIONS = 2

MARGIN_TYPE = "ISOLATED"

# Stop / trailing
TRAILING_PCT = 0.7
TRAILING_ACTIVATION_PCT = 0.8
TRAILING_POLL_SECONDS = 3

TRAILING_USE_ATR = True
TRAILING_ATR_MULT = 1.5

MIN_SL_DISTANCE_PCT = 0.10
INITIAL_SL_ATR_MULT = 2.2  # usado por EventLoop para initial_sl
MIN_INITIAL_SL_PCT = 0.35  # mínimo 0.35% aunque ATR sea muy bajo

# Cooldown / daily loss
DEFAULT_COOLDOWN_BARS = 4   # 12
DEFAULT_DAILY_LOSS_LIMIT_PCT = 6.0

# Trade lock (anti-duplicado)
MIN_SECONDS_BETWEEN_ENTRIES = 45

# Spread filter
MAX_SPREAD_PCT = 0.10
SPREAD_CACHE_SECONDS = 3

# Slippage guard (RATIO: 0.003 = 0.3%)
MAX_SLIPPAGE_RATIO = 0.003

# Funding filter (0.0005 = 0.05%)
FUNDING_THRESHOLD = 0.0005

# =========================
# REST POLLING (performance)
# =========================
LOOP_SLEEP_SECONDS = 0.5
KLINE_POLL_SECONDS = 15
MARK_POLL_SECONDS = 3

# =========================
# Major lock (si lo estás usando en algún guard; si no, puedes quitarlo)
# =========================
MAJOR_LOCK_ENABLED = True
MAJOR_SYMBOLS = ["BTCUSDT", "ETHUSDT"]
MAX_OPEN_MAJORS = 2  # 1

# =========================
# BINANCE CLIENT
# =========================
TESTNET = False

# =========================
# API CACHE (para APICache en BinanceFutures)
# =========================
API_CACHE_TTL_SECONDS = 2
EXCHANGE_INFO_TTL_SECONDS = 60
