#core/models.py

from dataclasses import dataclass, field, asdict
import copy
from typing import Dict, List, Optional, Tuple
import pandas as pd

@dataclass
class BotState:
    paused: bool = False
    risk_pct: float = 1.0
    leverage: int = 5
    symbols: List[str] = field(default_factory=list)
    strategy_symbols: dict = field(default_factory=lambda: {
        "rsi_bb_reversion": ["XRPUSDT", "1000PEPEUSDT", "AVAXUSDT", "TIAUSDT", "ORDIUSDT"],
        "stop_hunt":        ["XRPUSDT", "1000PEPEUSDT", "AVAXUSDT", "TIAUSDT", "ORDIUSDT"],
        "macd_momentum":    ["XRPUSDT", "AVAXUSDT", "SOLUSDT", "LINKUSDT", "TIAUSDT"],
        "ema_breakout":     [],
        "volatility_squeeze": ["NEARUSDT", "OPUSDT", "BTCUSDT", "LINKUSDT", "XRPUSDT"],
    })

    # EMA Breakout v2
    ema_fast: int = 9
    ema_slow: int = 21
    ema_breakout_fast: int = 25
    ema_breakout_slow: int = 50
    ema_min_slope_pct: float = 0.04
    ema_rsi_period: int = 14
    ema_rsi_oversold: float = 30.0
    ema_rsi_overbought: float = 70.0
    ema_min_volume_ratio: float = 1.2
    ema_min_atr_pct: float = 0.15
    ema_momentum_bars: int = 3
    ema_min_momentum_pct: float = 0.10
    ema_breakout_lookback: int = 8
    ema_pullback_atr_mult: float = 0.8
    ema_max_pullback_atr_mult: float = 2.5
    ema_sl_atr_mult: float = 2.0
    ema_sl_pct: float = 0.30

    trailing_pct: float = 0.5
    max_positions: int = 1
    adx_min: float = 25.0
    cooldown_bars: int = 5
    daily_loss_limit_pct: float = 10.0
    # Legacy fields (compatibilidad DB)
    vol_min_ratio: float = 1.2
    adx_rising: bool = False
    pivot_len: int = 5
    timeframe: str = "5m"

    trail: Dict[str, dict] = field(default_factory=dict)
    cooldown: Dict[str, dict] = field(default_factory=dict)
    stop_orders: Dict[str, dict] = field(default_factory=dict)
    position_ids: Dict[str, dict] = field(default_factory=dict)

    day_key: Optional[str] = None
    day_start_equity: float = 0.0

    paper_trading: bool = False
    trailing_automatico: bool = True
    strategy_mode: str = "ema_breakout"

    # Estrategias activas (modo auto filtra por estas)
    strategy_enabled_rsi_bb: bool = True
    strategy_enabled_stop_hunt: bool = True
    strategy_enabled_macd: bool = True
    strategy_enabled_ema: bool = True
    strategy_enabled_structure: bool = True
    strategy_enabled_vol_squeeze: bool = True

    # Trailing (runtime)
    trailing_activation_pct: float = 0.5
    trailing_use_atr: bool = True
    trailing_atr_mult: float = 2.0

    # Take Profit
    use_take_profit: bool = True
    tp_by_pct: bool = True
    tp_activation_pct: float = 1.2
    tp_close_pct: float = 70
    tp_sl_mode: str = "trailing"
    tp_use_mark: bool = True

    # Stop Hunt
    stop_hunt_wick_pct: float = 0.20
    stop_hunt_rejection_ratio: float = 0.7
    stop_hunt_min_zones: int = 2
    stop_hunt_max_zone_distance_pct: float = 0.8
    stop_hunt_sl_pct: float = 0.35
    stop_hunt_min_volume_ratio: float = 1.5
    stop_hunt_use_ema_filter: bool = True
    stop_hunt_min_break_candles: int = 2
    stop_hunt_atr_mult_sl: float = 2.0
    stop_hunt_momentum_bars: int = 3
    stop_hunt_min_atr_pct: float = 0.12
    stop_hunt_adx_min: float = 18.0
    order_block_lookback: int = 5

    # RSI + BB Mean Reversion
    rsi_bb_rsi_period: int = 14
    rsi_bb_oversold: float = 20.0
    rsi_bb_overbought: float = 80.0
    rsi_bb_bb_period: int = 20
    rsi_bb_bb_std_mult: float = 2.0
    rsi_bb_stoch_period: int = 14
    rsi_bb_divergence_lookback: int = 20
    rsi_bb_band_tolerance_pct: float = 0.3
    rsi_bb_min_volume_ratio: float = 1.2
    rsi_bb_adx_min: float = 12.0
    rsi_bb_min_atr_pct: float = 0.15
    rsi_bb_sl_atr_mult: float = 2.5
    rsi_bb_sl_pct: float = 0.60
    rsi_bb_require_divergence: bool = True

    # EMA Breakout v2 (additional)
    ema_min_body_ratio: float = 0.50
    ema_min_pivot_distance_pct: float = 0.08
    ema_min_break_distance_pct: float = 0.04
    ema_max_pivot_age: int = 15

    # MACD Momentum
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    macd_min_volume_ratio: float = 3.0
    macd_rsi_period: int = 14
    macd_rsi_bull_min: float = 55.0
    macd_rsi_bear_max: float = 45.0
    macd_adx_min: float = 25.0
    macd_min_atr_pct: float = 0.20
    macd_structure_lookback: int = 10
    macd_sl_atr_mult: float = 2.0

    # Structure Break
    structure_swing_window: int = 5
    structure_lookback: int = 60
    structure_break_lookback: int = 10
    structure_retest_lookback: int = 8
    structure_retest_tolerance_atr: float = 0.5
    structure_min_break_volume: float = 2.0
    structure_sl_buffer_atr: float = 1.0
    structure_adx_min: float = 15.0

    # Volatility Squeeze (1h)
    vol_squeeze_atr_period: int = 14
    vol_squeeze_atr_lookback: int = 100
    vol_squeeze_atr_percentile: int = 15
    vol_squeeze_bb_period: int = 20
    vol_squeeze_bb_width_percentile: int = 25
    vol_squeeze_rsi_period: int = 14
    vol_squeeze_rsi_oversold: float = 30.0
    vol_squeeze_rsi_overbought: float = 70.0
    vol_squeeze_min_volume_ratio: float = 1.5
    vol_squeeze_adx_min: float = 15.0
    vol_squeeze_sl_atr_mult: float = 1.5
    vol_squeeze_tp_atr_mult: float = 4.0
    vol_squeeze_ema_fast: int = 20
    vol_squeeze_ema_slow: int = 50

    def to_dict(self):
        return asdict(self)

@dataclass
class MarketData:
    df: pd.DataFrame
    last_closed_kline_ms: int = 0
    mark_price: float = 0.0

@dataclass(frozen=True)
class SignalEvent:
    symbol: str
    direction: str  # "LONG" | "SHORT"
    signal: dict     # snapshot de compute_signals()
    kline_close_time_ms: int
