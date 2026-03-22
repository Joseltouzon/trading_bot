# config.py
# =========================
# SYMBOLS / TF
# =========================
SYMBOLS = ["BTCUSDT", "BNBUSDT", "XRPUSDT"]
INTERVAL = "5m"
KLINES_LIMIT = 500

# Multi-timeframe: cada estrategia opera en su timeframe óptimo
STRATEGY_INTERVALS = {
    "rsi_bb_reversion": "5m",
    "stop_hunt": "5m",
    "ema_breakout": "15m",
    "macd_momentum": "15m",
    "structure_break": "5m",
}
DEFAULT_STRATEGY_SYMBOLS = {
    "rsi_bb_reversion": ["1000PEPEUSDT", "AVAXUSDT", "TIAUSDT", "ORDIUSDT", "TAOUSDT"],
    "stop_hunt":        ["1000PEPEUSDT", "AVAXUSDT", "ORDIUSDT", "SUIUSDT", "WIFUSDT"],
    "macd_momentum":    ["SANDUSDT", "PENDLEUSDT", "XRPUSDT", "AVAXUSDT", "SOLUSDT"],
    "ema_breakout":     ["DOGEUSDT", "LINKUSDT", "TIAUSDT", "ORDIUSDT", "PENDLEUSDT"],
    "structure_break":  ["FILUSDT", "DOGEUSDT", "APTUSDT", "WIFUSDT", "ATOMUSDT"],
}
REQUIRED_INTERVALS = sorted(set(STRATEGY_INTERVALS.values()))  # ["15m", "5m"]

# =========================
# EXECUTION / RISK
# =========================
DEFAULT_RISK_PCT = 1.0
MAX_RISK_PCT_ALLOWED = 10.0
MIN_NOTIONAL_USDT = 20          # CRÍTICO: No borrar, Binance exige min ~20USDT
DEFAULT_LEVERAGE = 5
MAX_OPEN_POSITIONS = 2
MARGIN_TYPE = "ISOLATED"

# =========================
# Stop / trailing
# =========================
TRAILING_PCT = 0.5              # Solo usa si TRAILING_USE_ATR = False
TRAILING_ACTIVATION_PCT = 0.5
TRAILING_USE_ATR = True         # Activo: Usa volatilidad
TRAILING_ATR_MULT = 2.0
MIN_INITIAL_SL_PCT = 0.35       # Mínimo SL inicial
INITIAL_SL_ATR_MULT = 0.7

# =========================
# Cooldown / daily loss
# =========================
DEFAULT_DAILY_LOSS_LIMIT_PCT = 10.0
MIN_SECONDS_BETWEEN_ENTRIES = 45

# =========================
# STRATEGY - EMA BREAKOUT v2
# =========================
EMA_FAST = 9                        # EMA rápida (tendencia)
EMA_SLOW = 21                       # EMA lenta (tendencia)
EMA_BREAKOUT_FAST = 25              # EMA rápida para EMA Breakout
EMA_BREAKOUT_SLOW = 50              # EMA lenta para EMA Breakout
EMA_MIN_SLOPE_PCT = 0.04            # Pendiente mínima EMA para tendencia
EMA_RSI_PERIOD = 14                 # Período RSI para filtro
EMA_RSI_OVERSOLD = 30               # RSI sobreventa (no SHORT por debajo)
EMA_RSI_OVERBOUGHT = 70             # RSI sobrecompra (no LONG por encima)
EMA_MIN_VOLUME_RATIO = 1.2          # Volumen mínimo vs media
EMA_MIN_ATR_PCT = 0.15              # Volatilidad mínima
EMA_MOMENTUM_BARS = 3               # Velas para momentum
EMA_MIN_MOMENTUM_PCT = 0.10         # Momentum mínimo
EMA_BREAKOUT_LOOKBACK = 8           # Velas para buscar breakout previo
EMA_PULLBACK_ATR_MULT = 0.8         # Max distancia pullback al pivot (ATR)
EMA_MAX_PULLBACK_ATR_MULT = 2.5     # Min distancia pullback al pivot (ATR)
EMA_SL_ATR_MULT = 2.0               # ATR multiplier para SL
EMA_SL_PCT = 0.30                   # SL mínimo por porcentaje
ADX_PERIOD = 14                     # Período del ADX
ATR_PERIOD = 14                     # Período del ATR
PIVOT_LEN = 5                       # Velas a cada lado para pivots
MIN_BODY_RATIO = 0.50               # Ratio mínimo cuerpo/rango vela
MIN_PIVOT_DISTANCE_PCT = 0.08       # Distancia mínima precio-pivot (%)
MIN_BREAK_DISTANCE_PCT = 0.04       # Distancia mínima de breakout (%)
MAX_PIVOT_AGE = 15                  # Máxima antigüedad del pivot (velas)
ADX_MIN = 25.0                      # ADX mínimo (optimizado para EMA 25/50)
COOLDOWN_BARS = 5
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
USE_TAKE_PROFIT = True

# --- Modo: porcentaje de ganancia (recomendado) ---
TP_BY_PCT = True                    # Usar TP por % de ganancia en vez de R:R
TP_ACTIVATION_PCT = 1.2            # Activar cuando la ganancia llegue a este %
TP_CLOSE_PCT = 70                   # Cerrar este % de la posición al activar
TP_SL_MODE = "trailing"            # SL del resto: "entry" (precio entrada) o "trailing" (TrailingManager lo maneja)

# --- Modo legacy: R:R multiples ---
# Niveles de TP: [R:R, % a cerrar, ¿mover SL a Breakeven?]
TP_LEVELS = [
    {"ratio": 5.0, "close_pct": 30, "move_sl_to_be": True},   # 50% en 1.5R → SL a Entry
    {"ratio": 8.0, "close_pct": 30, "move_sl_to_be": False},  # 30% en 2.5R → dejar correr
    {"ratio": 12.0, "close_pct": 40, "move_sl_to_be": False},  # 20% en 4.0R → moonbag
]

MIN_R_FOR_FIRST_TP = 4.8      # No activar TP si R:R < 1.2 (evitar ruido)
TP_THROTTLE_SECONDS = 10      # Mínimo tiempo entre ejecuciones de TP por símbolo
TP_USE_MARK_PRICE = True      # Usar Mark Price (no last) para evaluar TP

STOP_HUNT_WICK_PCT = 0.20           # Aumentado de 0.15 a 0.20 - mecha más grande
STOP_HUNT_REJECTION_RATIO = 0.7    # Aumentado de 0.5 a 0.7 - rechazo más fuerte
STOP_HUNT_MIN_ZONES = 2             # Reducido de 3 a 2 - menos zonas pero más relevantes
STOP_HUNT_MAX_ZONE_DISTANCE_PCT = 0.8  # Reducido de 1.5 a 0.8 - precio más cerca de zona
STOP_HUNT_SL_PCT = 0.35             # Aumentado de 0.30 a 0.35 - SL más holgado
STOP_HUNT_MIN_VOLUME_RATIO = 1.5    # Aumentado de 1.2 a 1.5 - volumen más alto
STOP_HUNT_USE_EMA_FILTER = True    # NUEVO: usar EMA para tendencia
STOP_HUNT_MIN_BREAK_CANDLES = 2     # NUEVO: velas que rompen zona
ORDER_BLOCK_LOOKBACK = 5            # Velas hacia atrás para buscar order blocks
STOP_HUNT_ATR_MULT_SL = 2.0         # Aumentado de 1.5 a 2.0 - SL más seguro
STOP_HUNT_MOMENTUM_BARS = 3        # Aumentado de 2 a 3 - momentum más fuerte
STOP_HUNT_MIN_ATR_PCT = 0.12        # NUEVO: volatilidad mínima
STOP_HUNT_ADX_MIN = 18.0            # ADX mínimo para operar (filtro de momentum)

# ============================================================
# RSI + BOLLINGER BAND MEAN REVERSION
# ============================================================
RSI_BB_RSI_PERIOD = 14              # Período del RSI
RSI_BB_OVERSOLD = 20                # RSI zona de sobreventa (más extremo)
RSI_BB_OVERBOUGHT = 80              # RSI zona de sobrecompra (más extremo)
RSI_BB_BB_PERIOD = 20               # Período Bollinger Bands
RSI_BB_BB_STD_MULT = 2.0            # StdDev multiplier Bollinger
RSI_BB_STOCH_PERIOD = 14            # Período Stochastic RSI
RSI_BB_DIVERGENCE_LOOKBACK = 20     # Velas hacia atrás para detectar divergencias
RSI_BB_BAND_TOLERANCE_PCT = 0.3     # % de tolerancia fuera de banda para considerar "en la banda"
RSI_BB_MIN_VOLUME_RATIO = 1.2       # Volumen mínimo vs media 20 (más permisivo)
RSI_BB_ADX_MIN = 12.0               # ADX mínimo (más bajo para más señales)
RSI_BB_MIN_ATR_PCT = 0.15           # Volatilidad mínima
RSI_BB_SL_ATR_MULT = 2.5            # ATR multiplier para SL (balanceado)
RSI_BB_SL_PCT = 0.60                # SL mínimo por porcentaje
RSI_BB_REQUIRE_DIVERGENCE = True    # True = requiere divergencia real, no solo rejection

# ============================================================
# MACD MOMENTUM + VOLUME SPIKE
# ============================================================
MACD_FAST = 12                      # MACD fast EMA
MACD_SLOW = 26                      # MACD slow EMA
MACD_SIGNAL = 9                     # MACD signal line
MACD_MIN_VOLUME_RATIO = 3.0         # Volume spike mínimo (3x media)
MACD_RSI_PERIOD = 14                # RSI para confirmación direccional
MACD_RSI_BULL_MIN = 55              # RSI mínimo para LONG
MACD_RSI_BEAR_MAX = 45              # RSI máximo para SHORT
MACD_ADX_MIN = 25.0                 # ADX mínimo (momentum real)
MACD_MIN_ATR_PCT = 0.20             # Volatilidad mínima
MACD_STRUCTURE_LOOKBACK = 10        # Velas para higher high / lower low
MACD_SL_ATR_MULT = 2.0              # ATR multiplier para SL

# ============================================================
# STRUCTURE BREAK + RETEST
# ============================================================
STRUCTURE_SWING_WINDOW = 5          # Ventana para swing highs/lows
STRUCTURE_LOOKBACK = 60             # Velas hacia atrás para buscar swings
STRUCTURE_BREAK_LOOKBACK = 10       # Velas para buscar ruptura
STRUCTURE_MIN_BREAK_VOLUME = 2.0    # Volumen mínimo en vela de ruptura (2x)
STRUCTURE_RETEST_LOOKBACK = 8       # Velas después de ruptura para buscar retest
STRUCTURE_RETEST_TOLERANCE_ATR = 0.5 # Tolerancia de retest (en ATR)
STRUCTURE_SL_BUFFER_ATR = 1.0       # Buffer ATR para SL
STRUCTURE_ADX_MIN = 15.0            # ADX mínimo
STRUCTURE_MIN_VOLUME_RATIO = 1.0    # Volumen mínimo
STRUCTURE_MIN_ATR_PCT = 0.10        # Volatilidad mínima