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
