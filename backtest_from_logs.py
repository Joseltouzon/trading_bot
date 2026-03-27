#!/usr/bin/env python3
"""
Backtest reconstruido desde LOGS REALES del bot.
Cada señal, entrada y bloqueo extraído de bot.log.
"""
import sys, os, time
from datetime import datetime
import pandas as pd
from binance.client import Client
import config as CFG
from db import Database

# Señales EJECUTADAS (entry real del bot, 26-27 marzo)
EXECUTED = [
    {"time":"2026-03-26 09:10","symbol":"1000PEPEUSDT","side":"LONG","strategy":"stop_hunt","entry":0.003391,"sl":0.003391,"qty":220533.91},
    {"time":"2026-03-26 12:01","symbol":"NEARUSDT","side":"SHORT","strategy":"volatility_squeeze","entry":1.2335,"sl":1.2370,"qty":135.07},
    {"time":"2026-03-26 12:02","symbol":"BTCUSDT","side":"SHORT","strategy":"volatility_regime","entry":69376.30,"sl":69948.12,"qty":0.003534},
    {"time":"2026-03-26 12:15","symbol":"XRPUSDT","side":"SHORT","strategy":"macd_momentum","entry":1.3579,"sl":1.3630,"qty":310.92},
    {"time":"2026-03-26 15:01","symbol":"NEARUSDT","side":"SHORT","strategy":"volatility_regime","entry":1.2100,"sl":1.2160,"qty":132.89},
    {"time":"2026-03-26 15:05","symbol":"SUIUSDT","side":"SHORT","strategy":"stop_hunt","entry":0.9120,"sl":0.9190,"qty":708.61},
    {"time":"2026-03-26 17:15","symbol":"ATOMUSDT","side":"SHORT","strategy":"structure_break","entry":1.6920,"sl":1.7020,"qty":318.24},
    {"time":"2026-03-26 21:05","symbol":"ORDIUSDT","side":"LONG","strategy":"stop_hunt","entry":2.3050,"sl":2.2870,"qty":336.84},
    {"time":"2026-03-27 05:45","symbol":"PENDLEUSDT","side":"SHORT","strategy":"macd_momentum","entry":1.1804,"sl":1.1860,"qty":311.90},
    {"time":"2026-03-27 07:01","symbol":"XRPUSDT","side":"SHORT","strategy":"volatility_regime","entry":1.3440,"sl":1.3540,"qty":160.66},
    {"time":"2026-03-27 09:55","symbol":"1000PEPEUSDT","side":"LONG","strategy":"stop_hunt","entry":0.003271,"sl":0.003271,"qty":152003.48},
]

# Señales BLOQUEADAS por filtros
BLOCKED = [
    {"time":"2026-03-26 12:01","symbol":"XRPUSDT","side":"SHORT","reason":"SLIPPAGE","detail":"signal=1.38 mark=1.37 diff=0.839%"},
    {"time":"2026-03-26 12:03","symbol":"LINKUSDT","side":"SHORT","reason":"MAX_POS","detail":"2/2"},
    {"time":"2026-03-26 13:01","symbol":"BTCUSDT","side":"SHORT","reason":"SLIPPAGE","detail":"diff=0.656%"},
    {"time":"2026-03-26 14:01","symbol":"NEARUSDT","side":"SHORT","reason":"SLIPPAGE","detail":"diff=0.557%"},
    {"time":"2026-03-26 14:01","symbol":"OPUSDT","side":"SHORT","reason":"SLIPPAGE","detail":"diff=1.271%"},
    {"time":"2026-03-26 15:01","symbol":"OPUSDT","side":"SHORT","reason":"SLIPPAGE","detail":"diff=2.007%"},
    {"time":"2026-03-26 17:20","symbol":"ATOMUSDT","side":"SHORT","reason":"COOLDOWN","detail":"3 bars"},
    {"time":"2026-03-26 17:30","symbol":"ATOMUSDT","side":"SHORT","reason":"COOLDOWN","detail":"1 bar"},
    {"time":"2026-03-27 07:00","symbol":"LINKUSDT","side":"SHORT","reason":"SLIPPAGE","detail":"diff=0.540%"},
    {"time":"2026-03-27 07:46","symbol":"SANDUSDT","side":"SHORT","reason":"FUNDING","detail":"funding=-0.000504"},
    {"time":"2026-03-27 14:10","symbol":"WIFUSDT","side":"LONG","reason":"SLIPPAGE","detail":"diff=0.801%"},
]

def fetch_klines(symbol, interval, start, end):
    c = Client()
    k = c.futures_historical_klines(symbol=symbol, interval=interval, start_str=f"{start} 00:00 UTC", end_str=f"{end} 00:00 UTC")
    if not k: return pd.DataFrame()
    df = pd.DataFrame(k, columns=["ot","o","h","l","c","v","ct","qv","t","tb","tq","ig"])
    for col in ["o","h","l","c","v"]: df[col] = df[col].astype(float)
    df["ct"] = df["ct"].astype(int)
    return df

def find_bar(df, time_str):
    target_ms = int(datetime.strptime(time_str, "%Y-%m-%d %H:%M").timestamp() * 1000)
    for i, row in df.iterrows():
        if int(row["ct"]) >= target_ms:
            return i
    return len(df) - 1

def simulate(sig, df):
    entry_bar = find_bar(df, sig["time"])
    if entry_bar < 50 or entry_bar >= len(df) - 1:
        return None
    entry, sl, side, qty = sig["entry"], sig["sl"], sig["side"], sig["qty"]
    is_long = side == "LONG"
    best, cur_sl, trail_on = entry, sl, False

    for bar in range(entry_bar + 1, len(df)):
        h, l, c = float(df.iloc[bar]["high"]), float(df.iloc[bar]["low"]), float(df.iloc[bar]["close"])
        ts = int(df.iloc[bar]["ct"])
        bt = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M")

        # SL check
        if is_long and l <= cur_sl:
            pnl = (cur_sl - entry) * qty; comm = cur_sl * qty * 0.0004
            return {"exit": cur_sl, "time": bt, "reason": "TRAILING" if trail_on else "STOP_LOSS", "pnl": pnl-comm, "comm": comm}
        elif not is_long and h >= cur_sl:
            pnl = (entry - cur_sl) * qty; comm = cur_sl * qty * 0.0004
            return {"exit": cur_sl, "time": bt, "reason": "TRAILING" if trail_on else "STOP_LOSS", "pnl": pnl-comm, "comm": comm}

        # Trailing
        if is_long:
            best = max(best, h)
            if (c - entry) / entry * 100 >= CFG.TRAILING_ACTIVATION_PCT:
                trail_on = True
                ns = best * (1 - CFG.TRAILING_PCT / 100)
                ns = max(ns, entry)
                if ns > cur_sl: cur_sl = ns
        else:
            best = min(best, l)
            if (entry - c) / entry * 100 >= CFG.TRAILING_ACTIVATION_PCT:
                trail_on = True
                ns = best * (1 + CFG.TRAILING_PCT / 100)
                ns = min(ns, entry)
                if ns < cur_sl: cur_sl = ns

    lc = float(df.iloc[-1]["c"])
    pnl = (lc - entry) * qty if is_long else (entry - lc) * qty
    comm = lc * qty * 0.0004
    return {"exit": lc, "time": "END", "reason": "END", "pnl": pnl-comm, "comm": comm}

def main():
    print(f"\n{'='*90}")
    print(f"  BACKTEST DESDE LOGS REALES (26-27 marzo)")
    print(f"{'='*90}")
    print(f"\n  Señales: {len(EXECUTED)} ejecutadas, {len(BLOCKED)} bloqueadas, 3 duplicadas")
    print(f"\n  Ejecutadas:")
    for i, s in enumerate(EXECUTED, 1):
        print(f"    {i:>2}. {s['time']} {s['symbol']:<14} {s['side']:<6} {s['strategy']:<20} entry={s['entry']}")
    print(f"\n  Bloqueadas:")
    for i, s in enumerate(BLOCKED, 1):
        print(f"    {i:>2}. {s['time']} {s['symbol']:<14} {s['side']:<6} {s['reason']:<12} {s['detail']}")

    print(f"\n{'='*90}")
    print(f"  SIMULANDO...")
    print(f"{'='*90}\n")

    results, total_pnl = [], 0
    for sig in EXECUTED:
        interval = CFG.STRATEGY_INTERVALS.get(sig["strategy"], "5m")
        print(f"  {sig['symbol']:<14} {sig['side']:<6} {sig['strategy']:<20} ({interval})...", end=" ", flush=True)
        try:
            df = fetch_klines(sig["symbol"], interval, "2026-03-20", "2026-03-27")
            if len(df) < 50:
                print("⚠️ pocos datos"); continue
            r = simulate(sig, df)
            if r:
                results.append({**sig, **r})
                total_pnl += r["pnl"]
                e = "✅" if r["pnl"] > 0 else "❌"
                print(f"{e} exit={r['exit']:.6f} ({r['time']}) pnl={r['pnl']:+.4f} [{r['reason']}]")
            else:
                print("⚠️ no simulable")
            time.sleep(0.3)
        except Exception as e:
            print(f"❌ {e}")

    print(f"\n{'='*90}")
    print(f"  RESULTADOS")
    print(f"{'='*90}\n")
    wins = [t for t in results if t["pnl"] > 0]
    wr = len(wins) / len(results) * 100 if results else 0
    print(f"  {'#':>3} {'Symbol':<14} {'Side':<6} {'Entry':>10} {'Exit':>10} {'PnL':>8} {'Razón':<12}")
    print(f"  {'─'*70}")
    for i, t in enumerate(results, 1):
        print(f"  {i:>3} {t['symbol']:<14} {t['side']:<6} {t['entry']:>10.6f} {t['exit']:>10.6f} {t['pnl']:>+8.4f} {t['reason']:<12}")
    print(f"  {'─'*70}")
    print(f"  {len(results)} trades | {len(wins)} wins | WR {wr:.0f}% | PnL ${total_pnl:+.4f}")

    print(f"\n  Filtros: slippage=7 max_pos=1 cooldown=2 funding=1 (44% filtrado)")

    db = Database()
    real = db.get_recent_closed_positions_filtered(limit=None, start_date="2026-03-25", end_date="2026-03-27")
    real_pnl = sum(float(p["realized_pnl"]) for p in real) if real else 0
    real_wins = sum(1 for p in real if float(p["realized_pnl"]) > 0) if real else 0
    print(f"\n  {'Métrica':<20} {'Backtest(logs)':>15} {'Producción(DB)':>15}")
    print(f"  {'─'*52}")
    print(f"  {'Trades':<20} {len(results):>15} {len(real) if real else 0:>15}")
    print(f"  {'Wins':<20} {len(wins):>15} {real_wins:>15}")
    print(f"  {'PnL':<20} ${total_pnl:>+14.4f} ${real_pnl:>+14.4f}")

if __name__ == "__main__":
    main()
