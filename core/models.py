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
    ema_slow: int = 9
    ema_fast: int = 21
    trailing_pct: float = 0.5
    trailing_active : float = 0.5
    max_positions: int = 1
    adx_min: float = 20.0
    vol_min_ratio: float = 1.2
    cooldown_bars: int = 8
    daily_loss_limit_pct: float = 10.0
    pivot_len: int = 8
    timeframe: str = "5m"

    trail: Dict[str, dict] = field(default_factory=dict)
    cooldown: Dict[str, dict] = field(default_factory=dict)
    stop_orders: Dict[str, dict] = field(default_factory=dict)
    position_ids: Dict[str, dict] = field(default_factory=dict)

    day_key: Optional[str] = None
    day_start_equity: float = 0.0

    paper_trading: bool = False
    trailing_automatico: bool = True
    adx_rising: bool = False
    strategy_mode: str = "ema_breakout"

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

    vwap_std_mult: float = 1.5
    vwap_min_volume_ratio: float = 1.5
    vwap_sl_atr_mult: float = 2.0
    vwap_max_deviation_pct: float = 2.0

    regime_trending_adx_min: float = 25.0
    regime_ranging_adx_max: float = 18.0
    regime_hunt_vol_ratio_min: float = 1.3

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

    def copy(self):
        return copy.deepcopy(self)

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
