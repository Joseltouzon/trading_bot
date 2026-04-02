#!/usr/bin/env python3
"""
Backtest simultáneo: EMA + Stop Hunt + Structure Break
Simula el circuito real del bot con max_positions=1.
"""
import sys, os, time
from datetime import datetime
from dataclasses import dataclass
import pandas as pd
from binance.client import Client
import config as CFG

sys.path.insert(0, '.')
from strategy.ema_adx_breakout import compute_signals as compute_ema
from strategy.stop_hunt import compute_stop_hunt_signals as compute_sh
from strategy.structure_break import compute_structure_break_signals as compute_sb
from strategy.indicators import atr

# ============================================================
# CONFIG GANADORA
# ============================================================
INITIAL_CAPITAL = 150.0
MAX_POSITIONS = 1
COMMISSION_PCT = 0.04
START_DATE = "2026-03-27"
END_DATE = "2026-04-02"
WINDOW = 200  # ventana fija para compute_f

# EMA Breakout (15m)
EMA_SYMBOLS = ['DOGEUSDT','LINKUSDT','TIAUSDT','ORDIUSDT','PENDLEUSDT']

# Stop Hunt (5m)
SH_SYMBOLS = ['XRPUSDT','TIAUSDT','ETHUSDT','PENDLEUSDT','BTCUSDT']

# Structure Break (5m)
SB_SYMBOLS = ['FILUSDT','DOGEUSDT','APTUSDT','WIFUSDT','ATOMUSDT']

# Estrategias por intervalo
STRATEGIES = {
    "5m": [
        ("stop_hunt", compute_sh, SH_SYMBOLS),
        ("structure_break", compute_sb, SB_SYMBOLS),
    ],
    "15m": [
        ("ema_breakout", compute_ema, EMA_SYMBOLS),
    ],
}

# ============================================================
# DATA
# ============================================================
def fetch_klines(symbol, interval, start, end):
    cf = f"/tmp/bt_cache/{symbol}_{interval}_{start}_{end}.csv"
    cols = ["open_time","open","high","low","close","volume","close_time","quote_volume","trades","taker_buy_base","taker_buy_quote","ignore"]
    os.makedirs("/tmp/bt_cache", exist_ok=True)
    if os.path.exists(cf):
        try:
            df = pd.read_csv(cf)
            if "open" in df.columns:
                for c in ["open","high","low","close","volume"]: df[c] = df[c].astype(float)
                df["close_time"] = df["close_time"].astype(int)
                return df
        except: pass
    client = Client()
    k = client.futures_historical_klines(symbol=symbol, interval=interval, start_str=f"{start} 00:00 UTC", end_str=f"{end} 00:00 UTC")
    if not k: return pd.DataFrame()
    df = pd.DataFrame(k, columns=cols)
    for c in ["open","high","low","close","volume"]: df[c] = df[c].astype(float)
    df["close_time"] = df["close_time"].astype(int)
    df.to_csv(cf, index=False)
    return df

# ============================================================
# ENGINE
# ============================================================
@dataclass
class Pos:
    symbol: str; side: str; strategy: str; entry_price: float
    qty: float; entry_bar: int; initial_sl: float; current_sl: float
    trailing_activated: bool = False; best_price: float = 0.0; tp_executed: bool = False
    def __post_init__(self):
        self.best_price = self.entry_price
        self.current_sl = self.initial_sl

def apply_config():
    """Aplica configuración ganadora."""
    CFG.EMA_BREAKOUT_FAST = 9
    CFG.EMA_BREAKOUT_SLOW = 21
    CFG.ADX_MIN = 17

    CFG.STOP_HUNT_USE_EMA_FILTER = False
    CFG.STOP_HUNT_ADX_MIN = 14
    CFG.STOP_HUNT_MIN_VOLUME_RATIO = 1.2

    CFG.STRUCTURE_BREAK_LOOKBACK = 5

def run():
    apply_config()
    start_ms = int(datetime.strptime(START_DATE, "%Y-%m-%d").timestamp() * 1000)

    # Descargar datos
    print("Descargando datos...")
    data = {}  # {interval: {symbol: df}}
    all_symbols = set()
    for interval, strats in STRATEGIES.items():
        data[interval] = {}
        for strat_name, _, symbols in strats:
            for sym in symbols:
                all_symbols.add(sym)
                if sym not in data[interval]:
                    try:
                        df = fetch_klines(sym, interval, "2026-02-20", END_DATE)
                        if len(df) >= 50:
                            data[interval][sym] = df
                            print(f"  ✅ {sym} {interval}: {len(df)} velas")
                        time.sleep(0.08)
                    except Exception as e:
                        print(f"  ❌ {sym} {interval}: {e}")

    # Pre-calcular señales
    print("\nPre-calculando señales...")
    all_signals = []
    for interval, strats in STRATEGIES.items():
        for strat_name, compute_fn, symbols in strats:
            for sym in symbols:
                df = data.get(interval, {}).get(sym)
                if df is None: continue
                # Step agresivo para que no tarde tanto
                step = 1 if interval == "5m" else 3
                count = 0
                for bar in range(50, len(df), step):
                    try:
                        sig = compute_fn(df.iloc[max(0,bar-WINDOW+1):bar+1])
                        sl = sig.get("breakout_long", False)
                        ss = sig.get("breakout_short", False)
                        if sl or ss:
                            ct = int(df.iloc[bar]["close_time"])
                            direction = "LONG" if sl else "SHORT"
                            all_signals.append((ct, sym, direction, sig, strat_name, bar, interval))
                            count += 1
                    except: pass
                print(f"  {strat_name} {sym} {interval}: {count} señales")

    all_signals.sort(key=lambda x: x[0])
    print(f"\nTotal señales: {len(all_signals)}")

    # Simular
    print("\nSimulando...\n")
    equity = INITIAL_CAPITAL
    positions = {}  # symbol -> Pos
    trades = []
    cooldown_until = {}
    COOLDOWN_BARS = 3
    blocked = {"adx":0, "cd":0, "mp":0, "sl":0}
    total_sig = 0

    for ct, sym, direction, sig, strat_name, bar, interval in all_signals:
        if ct < start_ms: continue
        total_sig += 1
        df = data[interval][sym]

        # Actualizar posiciones abiertas
        for psym in list(positions.keys()):
            pos = positions[psym]
            pos_interval = pos.strategy == "ema_breakout" and "15m" or "5m"
            pdf = data.get(pos_interval, {}).get(psym)
            if pdf is None: continue
            for ub in range(pos.entry_bar + 1, bar + 1):
                if ub >= len(pdf) or psym not in positions: break
                h,l,c = float(pdf.iloc[ub]["high"]), float(pdf.iloc[ub]["low"]), float(pdf.iloc[ub]["close"])
                is_long = pos.side == "LONG"

                if is_long and l <= pos.current_sl:
                    pnl = (pos.current_sl - pos.entry_price) * pos.qty
                    comm = pos.current_sl * pos.qty * (COMMISSION_PCT/100)
                    trades.append({"symbol":psym,"side":pos.side,"strategy":pos.strategy,
                        "entry":pos.entry_price,"exit":pos.current_sl,"pnl":pnl-comm,"reason":"TRAILING" if pos.trailing_activated else "SL"})
                    equity += pnl - comm
                    cooldown_until[psym] = bar + COOLDOWN_BARS
                    del positions[psym]; break
                elif not is_long and h >= pos.current_sl:
                    pnl = (pos.entry_price - pos.current_sl) * pos.qty
                    comm = pos.current_sl * pos.qty * (COMMISSION_PCT/100)
                    trades.append({"symbol":psym,"side":pos.side,"strategy":pos.strategy,
                        "entry":pos.entry_price,"exit":pos.current_sl,"pnl":pnl-comm,"reason":"TRAILING" if pos.trailing_activated else "SL"})
                    equity += pnl - comm
                    cooldown_until[psym] = bar + COOLDOWN_BARS
                    del positions[psym]; break

                if psym not in positions: break
                if is_long:
                    pos.best_price = max(pos.best_price, h)
                    ppct = (c - pos.entry_price) / pos.entry_price * 100
                else:
                    pos.best_price = min(pos.best_price, l)
                    ppct = (pos.entry_price - c) / pos.entry_price * 100
                if ppct >= 0.4:
                    pos.trailing_activated = True
                    if is_long:
                        ns = max(pos.best_price*(1-0.22/100), pos.entry_price)
                        if ns > pos.current_sl: pos.current_sl = ns
                    else:
                        ns = min(pos.best_price*(1+0.22/100), pos.entry_price)
                        if ns < pos.current_sl: pos.current_sl = ns

        # Guards
        if strat_name == "ema_breakout":
            if float(sig.get("adx",0)) < CFG.ADX_MIN:
                blocked["adx"]+=1; continue
        if strat_name == "stop_hunt":
            if float(sig.get("adx",0)) < CFG.STOP_HUNT_ADX_MIN:
                blocked["adx"]+=1; continue

        if sym in cooldown_until and bar < cooldown_until[sym]:
            blocked["cd"]+=1; continue
        if len(positions) >= MAX_POSITIONS:
            blocked["mp"]+=1; continue
        if sym in positions: continue

        price = float(sig.get("signal_price", sig.get("close",0)))
        atr_val = float(sig.get("atr",0))
        if price<=0 or atr_val<=0: continue

        # Slippage
        if atr_val > 0 and (float(df.iloc[bar]["high"])-float(df.iloc[bar]["low"]))/atr_val > 2.0:
            blocked["sl"]+=1; continue

        # Entry - qty basado en SL real (como el bot real)
        risk_usdt = equity * (1.0 / MAX_POSITIONS / 100.0)
        sl_dist = max(atr_val * CFG.INITIAL_SL_ATR_MULT, price * CFG.MIN_INITIAL_SL_PCT / 100.0)
        initial_sl = price - sl_dist if direction == "LONG" else price + sl_dist
        if initial_sl<=0: continue
        qty = max(risk_usdt / sl_dist, 0.001)
        if price*qty < CFG.MIN_NOTIONAL_USDT: qty = CFG.MIN_NOTIONAL_USDT/price
        equity -= price*qty*(COMMISSION_PCT/100)

        positions[sym] = Pos(symbol=sym,side=direction,strategy=strat_name,
            entry_price=price,qty=qty,entry_bar=bar,initial_sl=initial_sl,current_sl=initial_sl)

    # Cerrar restantes
    for psym in list(positions.keys()):
        pos = positions[psym]
        pos_interval = "15m" if pos.strategy == "ema_breakout" else "5m"
        pdf = data.get(pos_interval, {}).get(psym)
        if pdf is None: continue
        exit_price = float(pdf.iloc[-1]["close"])
        is_long = pos.side == "LONG"
        pnl = (exit_price-pos.entry_price)*pos.qty if is_long else (pos.entry_price-exit_price)*pos.qty
        comm = exit_price*pos.qty*(COMMISSION_PCT/100)
        trades.append({"symbol":psym,"side":pos.side,"strategy":pos.strategy,
            "entry":pos.entry_price,"exit":exit_price,"pnl":pnl-comm,"reason":"END"})
        equity += pnl - comm

    # Resultados
    wins = [t for t in trades if t["pnl"]>0]
    losses = [t for t in trades if t["pnl"]<=0]
    tpnl = sum(t["pnl"] for t in trades)
    gw = sum(t["pnl"] for t in wins)
    gl = abs(sum(t["pnl"] for t in losses))
    wr = len(wins)/len(trades)*100 if trades else 0
    pf = gw/gl if gl>0 else 0

    by_strat = {}
    for t in trades:
        s = t["strategy"]
        if s not in by_strat: by_strat[s] = {"n":0,"w":0,"pnl":0}
        by_strat[s]["n"]+=1; by_strat[s]["pnl"]+=t["pnl"]
        if t["pnl"]>0: by_strat[s]["w"]+=1

    print(f"{'='*80}")
    print(f"  BACKTEST SIMULTÁNEO: EMA + STOP HUNT + STRUCTURE")
    print(f"  Capital: ${INITIAL_CAPITAL} | Max pos: {MAX_POSITIONS} | Período: {START_DATE} → {END_DATE}")
    print(f"  TP: 0.8%/80% | Trailing: 0.4%/0.22% | SL: ATR×0.7 min 0.35%")
    print(f"{'='*80}\n")
    print(f"  Señales: {total_sig} | Bloqueadas: adx={blocked['adx']} cd={blocked['cd']} mp={blocked['mp']} sl={blocked['sl']}")
    print(f"  Trades: {len(trades)} | Wins: {len(wins)} | Losses: {len(losses)} | WR: {wr:.0f}%")
    print(f"  PnL: ${tpnl:+.2f} | PF: {pf:.2f} | Return: {tpnl/INITIAL_CAPITAL*100:+.1f}%")
    print(f"  Equity final: ${equity:.2f}")

    print(f"\n  Por estrategia:")
    print(f"  {'Estrategia':<22} {'Trades':>7} {'Wins':>5} {'WR%':>6} {'PnL':>10}")
    print(f"  {'─'*55}")
    for s,d in sorted(by_strat.items(), key=lambda x: x[1]["pnl"], reverse=True):
        w = d["w"]/d["n"]*100 if d["n"]>0 else 0
        print(f"  {s:<22} {d['n']:>7} {d['w']:>5} {w:>5.0f}% {d['pnl']:>+10.2f}")

    print(f"\n  Detalle:")
    print(f"  {'#':>3} {'Symbol':<14} {'Side':<6} {'Strategy':<20} {'Entry':>10} {'Exit':>10} {'PnL':>8} {'Razón':<10}")
    print(f"  {'─'*85}")
    for i,t in enumerate(trades,1):
        print(f"  {i:>3} {t['symbol']:<14} {t['side']:<6} {t['strategy']:<20} {t['entry']:>10.4f} {t['exit']:>10.4f} {t['pnl']:>+8.2f} {t['reason']:<10}")

if __name__ == "__main__":
    run()
