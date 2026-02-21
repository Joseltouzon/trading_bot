import json
import os
import threading
from dataclasses import asdict

import config as CFG
from core.models import BotState
from core.utils import utc_day_key, clamp

_state_lock = threading.Lock()

def load_state(defaults: BotState, get_equity_usdt) -> BotState:
    if not os.path.exists(CFG.STATE_FILE):
        st = defaults
        st.day_key = utc_day_key()
        st.day_start_equity = max(get_equity_usdt(), 0.0)
        return st

    try:
        with open(CFG.STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        st = BotState(
            paused=bool(data.get("paused", False)),
            risk_pct=float(data.get("risk_pct", defaults.risk_pct)),
            leverage=int(data.get("leverage", defaults.leverage)),
            symbols=list(data.get("symbols", defaults.symbols)),

            trailing_pct=float(data.get("trailing_pct", defaults.trailing_pct)),
            max_positions=int(data.get("max_positions", defaults.max_positions)),
            adx_min=float(data.get("adx_min", defaults.adx_min)),
            cooldown_bars=int(data.get("cooldown_bars", defaults.cooldown_bars)),
            daily_loss_limit_pct=float(data.get("daily_loss_limit_pct", defaults.daily_loss_limit_pct)),

            trail=dict(data.get("trail", {})),
            cooldown=dict(data.get("cooldown", {})),
            stop_orders=dict(data.get("stop_orders", {})),

            day_key=data.get("day_key", utc_day_key()),
            day_start_equity=float(data.get("day_start_equity", 0.0)),

            paper_trading=bool(data.get("paper_trading", defaults.paper_trading)),
        )

        st.risk_pct = clamp(st.risk_pct, 0.1, CFG.MAX_RISK_PCT_ALLOWED)
        st.leverage = int(clamp(st.leverage, 1, 20))
        st.max_positions = int(clamp(st.max_positions, 1, 5))
        return st

    except Exception:
        st = defaults
        st.day_key = utc_day_key()
        st.day_start_equity = max(get_equity_usdt(), 0.0)
        return st

def save_state(st: BotState):
    data = asdict(st)
    tmp_path = f"{CFG.STATE_FILE}.tmp"
    with _state_lock:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, CFG.STATE_FILE)
