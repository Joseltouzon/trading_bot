#!/usr/bin/env python3
"""
Backtest por estrategia individual (rápido).
Cada estrategia con sus símbolos, sin interferencia entre estrategias.
"""
import sys, os, time
from datetime import datetime
from dataclasses import dataclass
import numpy as np
import pandas as pd
from binance.client import Client
import config as CFG
from db import Database
from strategy.ema_adx_breakout import compute_signals
from strategy.stop_hunt import compute_stop_hunt_signals
from strategy.rsi_bb_reversion import compute_rsi_bb_signals
from strategy.macd_momentum import compute_macd_momentum_signals
from strategy.structure_break import compute_structure_break_signals
from strategy.volatility_squeeze import compute_volatility_squeeze_signals
from strategy.volatility_regime import compute_volatility_regime_signals

START_DATE = "2026-02-25"
END_DATE = "2026-03-27"
INITIAL_CAPITAL = 170.0
COMMISSION_PCT = 0.04

STRATEGY_COMPUTE = {
    "ema_breakout": compute_signals,
    "stop_hunt": compute_stop_hunt_signals,
    "rsi_bb_reversion": compute_rsi_bb_signals,
    "macd_momentum": compute_macd_momentum_signals,
    "structure_break": compute_structure_break_signals,
    "volatility_squeeze": compute_volatility_squeeze_signals,
    "volatility_regime": compute_volatility_regime_signals,
}

@dataclass
class SimPos:
    symbol: str; side: str; entry_price: float; qty: float
    entry_bar: int; initial_sl: float; current_sl: float
    trailing_activated: bool = False; best_price: float = 0.0
    def __post_init__(self):
        self.best_price = self.entry_price
        self.current_sl = self.initial_sl

def fetch_klines(symbol, interval, start_date, end_date):
    cache_dir = "/tmp/bt_cache"
    os.makedirs(cache_dir, exist_ok=True)
    cf = f"{cache_dir}/{symbol}_{interval}_{start_date}_{end_date}.csv"
    cols = ["open_time","open","high","low","close","volume",
            "close_time","quote_volume","trades","taker_buy_base","taker_buy_quote","ignore"]
    if os.path.exists(cf):
        try:
            df = pd.read_csv(cf)
            if "open" in df.columns:
                for c in ["open","high","low","close","volume"]: df[c] = df[c].astype(float)
                df["close_time"] = df["close_time"].astype(int)
                return df
        except: pass
    client = Client()
    k = client.futures_historical_klines(symbol=symbol, interval=interval,
        start_str=f"{start_date} 00:00 UTC", end_str=f"{end_date} 00:00 UTC")
    if not k: return pd.DataFrame()
    df = pd.DataFrame(k, columns=cols)
    for c in ["open","high","low","close","volume"]: df[c] = df[c].astype(float)
    df["close_time"] = df["close_time"].astype(int)
    df.to_csv(cf, index=False)
    return df

def run_strategy(strategy, symbols, interval, compute_fn, adx_min, max_positions,
                 cooldown_bars, risk_pct, trailing_activation_pct, trailing_pct):
    """Backtest una sola estrategia con sus símbolos."""

    # Descargar datos
    data = {}
    for sym in symbols:
        try:
            df = fetch_klines(sym, interval, "2026-02-20", END_DATE)
            if len(df) >= 50:
                data[sym] = df
            time.sleep(0.1)
        except Exception as e:
            print(f"    ❌ {sym}: {e}")

    if not data:
        return [], 0, 0, 0, 0, 0

    # Pre-calcular señales con ventana fija (tiempo constante)
    all_signals = []
    for symbol, df in data.items():
        for bar in range(50, len(df)):
            try:
                sig = compute_fn(df.iloc[max(0,bar-199):bar+1])
                sl = sig.get("breakout_long", False)
                ss = sig.get("breakout_short", False)
                if sl or ss:
                    ct = int(df.iloc[bar]["close_time"])
                    direction = "LONG" if sl else "SHORT"
                    all_signals.append((ct, symbol, direction, sig, bar))
            except: pass

    all_signals.sort(key=lambda x: x[0])

    start_ms = int(datetime.strptime(START_DATE, "%Y-%m-%d").timestamp() * 1000)

    # Simular
    equity = INITIAL_CAPITAL
    positions = {}  # symbol -> SimPos
    trades = []
    cooldown_until = {}
    blocked_adx = blocked_cd = blocked_mp = blocked_sl = 0
    total_sig = 0

    for ct, symbol, direction, sig, bar in all_signals:
        if ct < start_ms: continue
        total_sig += 1
        df = data[symbol]

        # Actualizar posiciones abiertas antes de nueva señal
        for sym in list(positions.keys()):
            pos = positions[sym]
            pos_df = data[sym]
            # Actualizar trailing desde entry hasta esta vela
            for ub in range(pos.entry_bar + 1, bar + 1):
                if ub >= len(pos_df) or sym not in positions: break
                _update(pos_df, ub, positions, sym, equity, trades,
                       trailing_activation_pct, trailing_pct)

        # Guards
        if strategy == "ema_breakout":
            if float(sig.get("adx",0)) < adx_min:
                blocked_adx += 1; continue

        if symbol in cooldown_until and bar < cooldown_until[symbol]:
            blocked_cd += 1; continue

        if len(positions) >= max_positions:
            blocked_mp += 1; continue

        if symbol in positions: continue

        # Entry
        price = float(sig.get("signal_price", sig.get("close", 0)))
        atr_val = float(sig.get("atr", 0))
        if price <= 0 or atr_val <= 0: continue

        # Slippage filter (más común en logs reales)
        if atr_val > 0:
            candle_range = float(df.iloc[bar]["high"]) - float(df.iloc[bar]["low"])
            if candle_range / atr_val > 2.0:
                blocked_sl += 1; continue

        risk_usdt = equity * (risk_pct / max_positions / 100.0)
        stop_dist = max(atr_val * 0.5, price * 0.001)
        sl_dist = max(atr_val * CFG.INITIAL_SL_ATR_MULT, price * CFG.MIN_INITIAL_SL_PCT / 100.0)
        initial_sl = price - sl_dist if direction == "LONG" else price + sl_dist
        if initial_sl <= 0: continue

        qty = max(risk_usdt / stop_dist, 0.001)
        if price * qty < CFG.MIN_NOTIONAL_USDT:
            qty = CFG.MIN_NOTIONAL_USDT / price

        commission = price * qty * (COMMISSION_PCT / 100)
        equity -= commission

        positions[symbol] = SimPos(symbol=symbol, side=direction, entry_price=price,
                                   qty=qty, entry_bar=bar, initial_sl=initial_sl, current_sl=initial_sl)
        cooldown_until[symbol] = bar + cooldown_bars

    # Cerrar posiciones restantes
    for sym in list(positions.keys()):
        pos = positions[sym]
        pos_df = data[sym]
        for ub in range(pos.entry_bar + 1, len(pos_df)):
            if sym not in positions: break
            _update(pos_df, ub, positions, sym, equity, trades,
                   trailing_activation_pct, trailing_pct)
        if sym in positions:
            pos_df = data[sym]
            exit_price = float(pos_df.iloc[-1]["close"])
            is_long = pos.side == "LONG"
            pnl = (exit_price - pos.entry_price) * pos.qty if is_long else (pos.entry_price - exit_price) * pos.qty
            comm = exit_price * pos.qty * (COMMISSION_PCT / 100)
            equity += pnl - comm
            trades.append({"symbol": sym, "side": pos.side, "entry": pos.entry_price,
                          "exit": exit_price, "pnl": pnl - comm, "reason": "END"})
            del positions[sym]

    return trades, total_sig, blocked_adx, blocked_cd, blocked_mp, blocked_sl

def _update(df, bar, positions, symbol, equity, trades, trail_act, trail_pct):
    pos = positions.get(symbol)
    if pos is None: return
    h, l, c = float(df.iloc[bar]["high"]), float(df.iloc[bar]["low"]), float(df.iloc[bar]["close"])
    is_long = pos.side == "LONG"

    if is_long and l <= pos.current_sl:
        _close(df, bar, positions, symbol, equity, trades, "TRAILING" if pos.trailing_activated else "SL"); return
    elif not is_long and h >= pos.current_sl:
        _close(df, bar, positions, symbol, equity, trades, "TRAILING" if pos.trailing_activated else "SL"); return

    if is_long:
        pos.best_price = max(pos.best_price, h)
        pnl_pct = (c - pos.entry_price) / pos.entry_price * 100
    else:
        pos.best_price = min(pos.best_price, l)
        pnl_pct = (pos.entry_price - c) / pos.entry_price * 100

    if pnl_pct >= trail_act:
        pos.trailing_activated = True
        if is_long:
            ns = max(pos.best_price * (1 - trail_pct / 100), pos.entry_price)
            if ns > pos.current_sl: pos.current_sl = ns
        else:
            ns = min(pos.best_price * (1 + trail_pct / 100), pos.entry_price)
            if ns < pos.current_sl: pos.current_sl = ns

def _close(df, bar, positions, symbol, equity, trades, reason):
    pos = positions.get(symbol)
    if pos is None: return
    exit_price = float(df.iloc[bar]["close"])
    is_long = pos.side == "LONG"
    pnl = (exit_price - pos.entry_price) * pos.qty if is_long else (pos.entry_price - exit_price) * pos.qty
    comm = exit_price * pos.qty * (COMMISSION_PCT / 100)
    equity += pnl - comm
    trades.append({"symbol": symbol, "side": pos.side, "entry": pos.entry_price,
                   "exit": exit_price, "pnl": pnl - comm, "reason": reason})
    del positions[symbol]

def main():
    print(f"\n{'='*90}")
    print(f"  BACKTEST POR ESTRATEGIA — {START_DATE} → {END_DATE}")
    print(f"{'='*90}")

    db = Database()
    state = db.load_state()
    strategy_symbols = state.get("strategy_symbols", CFG.DEFAULT_STRATEGY_SYMBOLS)
    adx_min = float(state.get("adx_min", CFG.ADX_MIN))
    max_positions = int(state.get("max_positions", CFG.MAX_OPEN_POSITIONS))
    cooldown_bars = int(state.get("cooldown_bars", CFG.COOLDOWN_BARS))
    risk_pct = float(state.get("risk_pct", CFG.DEFAULT_RISK_PCT))
    trail_act = float(state.get("trailing_activation_pct", CFG.TRAILING_ACTIVATION_PCT))
    trail_pct = float(state.get("trailing_pct", CFG.TRAILING_PCT))

    all_results = {}
    grand_total_trades = 0
    grand_total_pnl = 0
    grand_total_wins = 0

    for strategy, symbols in strategy_symbols.items():
        interval = CFG.STRATEGY_INTERVALS.get(strategy, "5m")
        compute_fn = STRATEGY_COMPUTE.get(strategy)
        if not compute_fn: continue

        print(f"\n{'─'*70}")
        print(f"  {strategy} ({interval}) — {symbols}")
        print(f"{'─'*70}")

        t0 = time.time()
        trades, total_sig, b_adx, b_cd, b_mp, b_sl = run_strategy(
            strategy, symbols, interval, compute_fn, adx_min, max_positions,
            cooldown_bars, risk_pct, trail_act, trail_pct
        )
        elapsed = time.time() - t0

        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]
        total_pnl = sum(t["pnl"] for t in trades)
        wr = len(wins) / len(trades) * 100 if trades else 0
        gw = sum(t["pnl"] for t in wins)
        gl = abs(sum(t["pnl"] for t in losses))
        pf = gw / gl if gl > 0 else 0

        print(f"  Señales: {total_sig} | Bloqueadas: adx={b_adx} cd={b_cd} mp={b_mp} sl={b_sl}")
        print(f"  Trades: {len(trades)} | Wins: {len(wins)} | Losses: {len(losses)} | WR: {wr:.0f}%")
        print(f"  PnL: ${total_pnl:+.4f} | PF: {pf:.2f} | Tiempo: {elapsed:.0f}s")

        if trades:
            print(f"  Detalle:")
            for i, t in enumerate(trades, 1):
                e = "+" if t["pnl"] > 0 else "-"
                print(f"    {i:>2}. {t['symbol']:<14} {t['side']:<6} {t['entry']:>10.4f} → {t['exit']:>10.4f} {t['pnl']:>+8.4f} [{t['reason']}]")

        all_results[strategy] = {"trades": len(trades), "wins": len(wins), "pnl": total_pnl, "wr": wr, "pf": pf}
        grand_total_trades += len(trades)
        grand_total_pnl += total_pnl
        grand_total_wins += len(wins)

    # Resumen
    print(f"\n{'='*90}")
    print(f"  RESUMEN POR ESTRATEGIA (30 días)")
    print(f"{'='*90}\n")
    print(f"  {'Estrategia':<22} {'Trades':>7} {'Wins':>5} {'WR%':>6} {'PF':>6} {'PnL':>10}")
    print(f"  {'─'*60}")
    for s, d in sorted(all_results.items(), key=lambda x: x[1]["pnl"], reverse=True):
        print(f"  {s:<22} {d['trades']:>7} {d['wins']:>5} {d['wr']:>5.0f}% {d['pf']:>6.2f} {d['pnl']:>+10.4f}")
    print(f"  {'─'*60}")
    grand_wr = grand_total_wins / grand_total_trades * 100 if grand_total_trades else 0
    print(f"  {'TOTAL':<22} {grand_total_trades:>7} {grand_total_wins:>5} {grand_wr:>5.0f}% {'':>6} {grand_total_pnl:>+10.4f}")

    # Producción
    print(f"\n  Producción DB (30 días):")
    real = db.get_recent_closed_positions_filtered(limit=None, start_date=START_DATE, end_date=END_DATE)
    if real:
        real_pnl = sum(float(p["realized_pnl"]) for p in real)
        real_wins = sum(1 for p in real if float(p["realized_pnl"]) > 0)
        print(f"  {len(real)} trades | {real_wins} wins | PnL: ${real_pnl:+.4f}")

if __name__ == "__main__":
    main()
