#!/usr/bin/env python3
"""
Backtest rápido 30 días. Pre-calcula señales por símbolo/estrategia usando
el DF completo (batch), luego simula ejecución secuencial con guards.
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
    symbol: str; side: str; strategy: str; entry_price: float
    qty: float; entry_bar: int; initial_sl: float; current_sl: float
    trailing_activated: bool = False; best_price: float = 0.0; tp_executed: bool = False
    def __post_init__(self):
        self.best_price = self.entry_price
        self.current_sl = self.initial_sl

@dataclass
class Trade:
    symbol: str; side: str; strategy: str; entry_price: float; exit_price: float
    qty: float; pnl_usdt: float; commission: float; exit_reason: str
    entry_time: str = ""; exit_time: str = ""

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
    client = Client()
    k = client.futures_historical_klines(symbol=symbol, interval=interval,
        start_str=f"{start_date} 00:00 UTC", end_str=f"{end_date} 00:00 UTC")
    if not k: return pd.DataFrame()
    df = pd.DataFrame(k, columns=["open_time","open","high","low","close","volume",
        "close_time","quote_volume","trades","taker_buy_base","taker_buy_quote","ignore"])
    for c in ["o","h","l","c","v"]: df[c] = df[c].astype(float)
    df["ct"] = df["ct"].astype(int)
    df.to_csv(cf, index=False)
    return df

def calc_all_signals(df, compute_fn, min_bar=50, step=1, window=200):
    """Calcula señales con ventana fija (tiempo constante por llamada)."""
    signals = []
    for bar in range(min_bar, len(df), step):
        try:
            start = max(0, bar - window + 1)
            sig = compute_fn(df.iloc[start:bar+1])
            sl = sig.get("breakout_long", False)
            ss = sig.get("breakout_short", False)
            if sl or ss:
                signals.append((bar, "LONG" if sl else "SHORT", sig))
        except: pass
    return signals

def run_backtest(strategy_symbols, enabled_map, risk_pct, max_positions, cooldown_bars,
                 trailing_activation_pct, trailing_pct, tp_activation_pct, tp_close_pct,
                 initial_sl_atr_mult, min_initial_sl_pct, adx_min, data_by_interval):
    
    equity = INITIAL_CAPITAL
    positions = {}  # symbol -> SimPos
    trades = []
    cooldown_until = {}
    start_date_ms = int(datetime.strptime(START_DATE, "%Y-%m-%d").timestamp() * 1000)
    
    # 1. Pre-calcular TODAS las señales ordenadas por tiempo
    all_signals = []
    for interval, data in data_by_interval.items():
        for symbol, df in data.items():
            for strat, syms in strategy_symbols.items():
                if symbol not in syms: continue
                if CFG.STRATEGY_INTERVALS.get(strat, "5m") != interval: continue
                if not enabled_map.get(strat, True): continue
                compute_fn = STRATEGY_COMPUTE.get(strat)
                if not compute_fn: continue
                
                sigs = calc_all_signals(df, compute_fn, step=50 if interval=="5m" else 15 if interval=="15m" else 3)
                for bar, direction, sig in sigs:
                    ct = int(df.iloc[bar]["close_time"])
                    if ct < start_date_ms: continue
                    all_signals.append((ct, symbol, direction, sig, strat, bar, interval))
    
    all_signals.sort(key=lambda x: x[0])
    total_signals = len(all_signals)
    
    # 2. Pre-calcular trailing updates: por cada símbolo/interval, lista de (close_time, bar_idx)
    trail_updates = {}
    for interval, data in data_by_interval.items():
        for symbol, df in data.items():
            key = (symbol, interval)
            trail_updates[key] = [(int(df.iloc[i]["close_time"]), i) for i in range(len(df))]
    
    # 3. Simular secuencialmente
    sig_count = 0
    blocked_adx = blocked_cooldown = blocked_maxpos = blocked_spread = 0
    blocked_slippage = blocked_funding = blocked_throttle = 0
    
    for ct, symbol, direction, sig, strat, bar, interval in all_signals:
        sig_count += 1
        df = data_by_interval[interval][symbol]
        
        # Actualizar posiciones abiertas antes de procesar esta señal
        # (simular que el trailing/TP corrió entre la última señal y esta)
        for sym in list(positions.keys()):
            pos = positions[sym]
            pos_interval = CFG.STRATEGY_INTERVALS.get(pos.strategy, "5m")
            pos_df = data_by_interval.get(pos_interval, {}).get(sym)
            if pos_df is None: continue
            
            # Encontrar la última vela cerrada antes de ct
            updates = trail_updates.get((sym, pos_interval), [])
            last_bar = pos.entry_bar
            for uct, ubar in updates:
                if uct <= ct and ubar > pos.entry_bar:
                    last_bar = ubar
            
            # Actualizar trailing desde entry_bar hasta last_bar
            for update_bar in range(pos.entry_bar + 1, last_bar + 1):
                if update_bar >= len(pos_df): break
                if sym not in positions: break
                _update_pos(positions, sym, pos_df, update_bar, 
                           trailing_activation_pct, trailing_pct, 
                           tp_activation_pct, tp_close_pct, equity, trades)
        
        # Guards
        if strat == "ema_breakout":
            if float(sig.get("adx",0)) < adx_min:
                blocked_adx += 1; continue
        
        if symbol in cooldown_until and bar < cooldown_until[symbol]:
            blocked_cooldown += 1; continue
        
        if len(positions) >= max_positions:
            blocked_maxpos += 1; continue
        
        if symbol in positions: continue
        
        # Filtros OrderManager
        price = float(sig.get("signal_price", sig.get("close", 0)))
        atr_val = float(sig.get("atr", 0))
        if price <= 0 or atr_val <= 0: continue
        
        # Spread (volumen)
        if bar >= 20:
            vol_avg = float(df["volume"].iloc[bar-20:bar].mean())
            vol_curr = float(df.iloc[bar]["volume"])
            if vol_avg > 0 and (vol_curr / vol_avg) < 0.5:
                blocked_spread += 1; continue
        
        # Slippage (rango vs ATR)
        if atr_val > 0:
            candle_range = float(df.iloc[bar]["high"]) - float(df.iloc[bar]["low"])
            if candle_range / atr_val > 2.0:
                blocked_slippage += 1; continue
        
        # Funding (movimiento reciente)
        if bar >= 20:
            lookback = float(df.iloc[bar-20]["close"])
            if lookback > 0:
                recent_move = ((price - lookback) / lookback) * 100
                if direction == "LONG" and recent_move > 5.0:
                    blocked_funding += 1; continue
                elif direction == "SHORT" and recent_move < -5.0:
                    blocked_funding += 1; continue
        
        # Execute entry
        risk_pct_per_trade = risk_pct / max_positions
        risk_usdt = equity * (risk_pct_per_trade / 100.0)
        stop_dist = max(atr_val * 0.5, price * 0.001)
        raw_sl_dist = atr_val * initial_sl_atr_mult
        min_sl_dist = price * (min_initial_sl_pct / 100.0)
        final_sl_dist = max(raw_sl_dist, min_sl_dist)
        initial_sl = price - final_sl_dist if direction == "LONG" else price + final_sl_dist
        if initial_sl <= 0: continue
        
        qty = max(risk_usdt / stop_dist, 0.001)
        if price * qty < CFG.MIN_NOTIONAL_USDT:
            qty = CFG.MIN_NOTIONAL_USDT / price
        
        commission = price * qty * (COMMISSION_PCT / 100)
        equity -= commission
        
        ts = int(df.iloc[bar]["close_time"])
        bar_time = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M")
        
        pos = SimPos(symbol=symbol, side=direction, strategy=strat,
                     entry_price=price, qty=qty, entry_bar=bar,
                     initial_sl=initial_sl, current_sl=initial_sl)
        pos.entry_time_str = bar_time
        positions[symbol] = pos
    
    # 4. Cerrar posiciones restantes (actualizar trailing hasta el final)
    for sym in list(positions.keys()):
        pos = positions[sym]
        pos_interval = CFG.STRATEGY_INTERVALS.get(pos.strategy, "5m")
        pos_df = data_by_interval.get(pos_interval, {}).get(sym)
        if pos_df is None: continue
        for update_bar in range(pos.entry_bar + 1, len(pos_df)):
            if sym not in positions: break
            _update_pos(positions, sym, pos_df, update_bar,
                       trailing_activation_pct, trailing_pct,
                       tp_activation_pct, tp_close_pct, equity, trades)
        if sym in positions:
            _close_pos(positions, trades, sym, pos_df, len(pos_df)-1, "END_OF_DATA", equity)
    
    return trades, sig_count, blocked_adx, blocked_cooldown, blocked_maxpos, blocked_spread, blocked_slippage, blocked_funding

def _update_pos(positions, symbol, df, bar, trail_act_pct, trail_pct, tp_act_pct, tp_close_pct, equity, trades=None):
    if trades is None: trades = []
    pos = positions.get(symbol)
    if pos is None: return
    h, l, c = float(df.iloc[bar]["high"]), float(df.iloc[bar]["low"]), float(df.iloc[bar]["close"])
    is_long = pos.side == "LONG"
    
    # SL check
    if is_long and l <= pos.current_sl:
        _close_pos(positions, trades, symbol, df, bar, "TRAILING" if pos.trailing_activated else "STOP_LOSS", equity); return
    elif not is_long and h >= pos.current_sl:
        _close_pos(positions, trades, symbol, df, bar, "TRAILING" if pos.trailing_activated else "STOP_LOSS", equity); return
    
    # Trailing
    if is_long:
        pnl_pct = (c - pos.entry_price) / pos.entry_price * 100
        pos.best_price = max(pos.best_price, h)
    else:
        pnl_pct = (pos.entry_price - c) / pos.entry_price * 100
        pos.best_price = min(pos.best_price, l)
    
    if pnl_pct >= trail_act_pct:
        pos.trailing_activated = True
        if is_long:
            ns = pos.best_price * (1 - trail_pct / 100)
            ns = max(ns, pos.entry_price)
            if ns > pos.current_sl: pos.current_sl = ns
        else:
            ns = pos.best_price * (1 + trail_pct / 100)
            ns = min(ns, pos.entry_price)
            if ns < pos.current_sl: pos.current_sl = ns

def _close_pos(positions, trades, symbol, df, bar, reason, equity):
    pos = positions.get(symbol)
    if pos is None: return
    exit_price = float(df.iloc[bar]["close"])
    is_long = pos.side == "LONG"
    pnl = (exit_price - pos.entry_price) * pos.qty if is_long else (pos.entry_price - exit_price) * pos.qty
    commission = exit_price * pos.qty * (COMMISSION_PCT / 100)
    equity += pnl - commission
    
    ts = int(df.iloc[bar]["close_time"])
    exit_time = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M")
    
    trades.append(Trade(symbol=symbol, side=pos.side, strategy=pos.strategy,
        entry_price=pos.entry_price, exit_price=exit_price, qty=pos.qty,
        pnl_usdt=pnl - commission, commission=commission, exit_reason=reason,
        entry_time=getattr(pos, 'entry_time_str', ''), exit_time=exit_time))
    del positions[symbol]

def main():
    print(f"\n{'='*90}")
    print(f"  BACKTEST 30 DÍAS — {START_DATE} → {END_DATE}")
    print(f"{'='*90}")
    
    db = Database()
    state = db.load_state()
    strategy_symbols = state.get("strategy_symbols", CFG.DEFAULT_STRATEGY_SYMBOLS)
    enabled_map = {k: True for k in strategy_symbols.keys()}
    
    risk_pct = float(state.get("risk_pct", CFG.DEFAULT_RISK_PCT))
    max_positions = int(state.get("max_positions", CFG.MAX_OPEN_POSITIONS))
    cooldown_bars = int(state.get("cooldown_bars", CFG.COOLDOWN_BARS))
    trailing_activation_pct = float(state.get("trailing_activation_pct", CFG.TRAILING_ACTIVATION_PCT))
    trailing_pct = float(state.get("trailing_pct", CFG.TRAILING_PCT))
    adx_min = float(state.get("adx_min", CFG.ADX_MIN))
    
    print(f"  Risk: {risk_pct}% | Max pos: {max_positions} | Cooldown: {cooldown_bars} bars")
    print(f"  Trailing: {trailing_pct}% (act: {trailing_activation_pct}%) | TP: {CFG.TP_ACTIVATION_PCT}%→{CFG.TP_CLOSE_PCT}%")
    print(f"  SL: ATR×{CFG.INITIAL_SL_ATR_MULT} min {CFG.MIN_INITIAL_SL_PCT}% | ADX: {adx_min}")
    
    # Descargar datos
    data_by_interval = {}
    for strat, syms in strategy_symbols.items():
        interval = CFG.STRATEGY_INTERVALS.get(strat, "5m")
        if interval not in data_by_interval:
            data_by_interval[interval] = {}
            print(f"\n  Descargando {interval}:")
        for sym in sorted(syms):
            if sym in data_by_interval[interval]: continue
            try:
                df = fetch_klines(sym, interval, "2026-02-20", END_DATE)
                if len(df) >= 50:
                    data_by_interval[interval][sym] = df
                    print(f"    ✅ {sym}: {len(df)} velas")
                else:
                    print(f"    ⚠️ {sym}: {len(df)} velas")
                time.sleep(0.1)
            except Exception as e:
                print(f"    ❌ {sym}: {e}")
    
    print(f"\n  Ejecutando backtest...")
    t0 = time.time()
    
    trades, total_sig, b_adx, b_cd, b_mp, b_sp, b_sl, b_fu = run_backtest(
        strategy_symbols, enabled_map, risk_pct, max_positions, cooldown_bars,
        trailing_activation_pct, trailing_pct, CFG.TP_ACTIVATION_PCT, CFG.TP_CLOSE_PCT,
        CFG.INITIAL_SL_ATR_MULT, CFG.MIN_INITIAL_SL_PCT, adx_min, data_by_interval
    )
    
    elapsed = time.time() - t0
    print(f"  Completado en {elapsed:.0f}s\n")
    
    # Resultados
    wins = [t for t in trades if t.pnl_usdt > 0]
    losses = [t for t in trades if t.pnl_usdt <= 0]
    total_pnl = sum(t.pnl_usdt for t in trades)
    win_rate = len(wins) / len(trades) * 100 if trades else 0
    gross_wins = sum(t.pnl_usdt for t in wins)
    gross_losses = abs(sum(t.pnl_usdt for t in losses))
    pf = gross_wins / gross_losses if gross_losses > 0 else 0
    
    by_strat = {}
    for t in trades:
        if t.strategy not in by_strat: by_strat[t.strategy] = {"n":0,"pnl":0,"w":0}
        by_strat[t.strategy]["n"] += 1; by_strat[t.strategy]["pnl"] += t.pnl_usdt
        if t.pnl_usdt > 0: by_strat[t.strategy]["w"] += 1
    
    exit_reasons = {}
    for t in trades: exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1
    
    print(f"{'='*90}")
    print(f"  RESULTADOS 30 DÍAS")
    print(f"{'='*90}\n")
    print(f"  Señales: {total_sig} | Bloqueadas: adx={b_adx} cooldown={b_cd} maxpos={b_mp} spread={b_sp} slippage={b_sl} funding={b_fu}")
    print(f"  Trades: {len(trades)} | Wins: {len(wins)} | Losses: {len(losses)} | WR: {win_rate:.1f}%")
    print(f"  PnL: ${total_pnl:+.4f} | PF: {pf:.2f} | Return: {total_pnl/INITIAL_CAPITAL*100:+.2f}%")
    
    print(f"\n  Por estrategia:")
    print(f"  {'Estrategia':<22} {'Trades':>7} {'Wins':>5} {'WR%':>6} {'PnL':>10}")
    print(f"  {'─'*55}")
    for s, d in sorted(by_strat.items(), key=lambda x: x[1]["pnl"], reverse=True):
        wr = d["w"]/d["n"]*100 if d["n"]>0 else 0
        print(f"  {s:<22} {d['n']:>7} {d['w']:>5} {wr:>5.0f}% {d['pnl']:>+10.4f}")
    
    print(f"\n  Salidas: {exit_reasons}")
    
    # Comparación DB
    print(f"\n{'='*90}")
    real = db.get_recent_closed_positions_filtered(limit=None, start_date=START_DATE, end_date=END_DATE)
    real_pnl = sum(float(p["realized_pnl"]) for p in real) if real else 0
    real_wins = sum(1 for p in real if float(p["realized_pnl"]) > 0) if real else 0
    print(f"  {'Métrica':<25} {'Backtest':>15} {'Producción':>15}")
    print(f"  {'─'*58}")
    print(f"  {'Trades':<25} {len(trades):>15} {len(real) if real else 0:>15}")
    print(f"  {'Wins':<25} {len(wins):>15} {real_wins:>15}")
    wr_real = real_wins/len(real)*100 if real else 0
    print(f"  {'Win Rate':<25} {win_rate:>14.1f}% {wr_real:>14.1f}%")
    print(f"  {'PnL':<25} ${total_pnl:>+14.4f} ${real_pnl:>+14.4f}")
    print(f"  {'Return':<25} {total_pnl/INITIAL_CAPITAL*100:>+13.2f}% {real_pnl/INITIAL_CAPITAL*100:>+13.2f}%")
    print(f"  {'─'*58}")

if __name__ == "__main__":
    main()
