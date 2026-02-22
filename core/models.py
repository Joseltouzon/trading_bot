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

    trailing_pct: float = 0.5
    max_positions: int = 2
    adx_min: float = 18.0
    cooldown_bars: int = 12
    daily_loss_limit_pct: float = 3.0

    trail: Dict[str, dict] = field(default_factory=dict)
    cooldown: Dict[str, dict] = field(default_factory=dict)
    stop_orders: Dict[str, dict] = field(default_factory=dict)
    position_ids: Dict[str, dict] = field(default_factory=dict)

    day_key: Optional[str] = None
    day_start_equity: float = 0.0

    paper_trading: bool = False

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
