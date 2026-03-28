#!/usr/bin/env python3
"""
Backtest rápido por combinación individual.
Prueba una estrategia + símbolos + parámetros y muestra resultado inmediato.
"""
import sys, os, time
from datetime import datetime
import pandas as pd
from binance.client import Client
import config as CFG
from strategy.ema_adx_breakout import compute_signals
from strategy.stop_hunt import compute_stop_hunt_signals
from strategy.rsi_bb_reversion import compute_rsi_bb_signals
from strategy.structure_break import compute_structure_break_signals
from strategy.macd_momentum import compute_macd_momentum_signals
from strategy.volatility_squeeze import compute_volatility_squeeze_signals
from strategy.volatility_regime import compute_volatility_regime_signals
from strategy.indicators import ema, atr, adx, rsi, bollinger_bands

START_DATE = "2026-02-25"
END_DATE = "2026-03-27"
INITIAL_CAPITAL = 170.0
COMMISSION_PCT = 0.04
WINDOW = 200

COMPUTE_FN = {
    "ema_breakout": compute_signals,
    "stop_hunt": compute_stop_hunt_signals,
    "rsi_bb_reversion": compute_rsi_bb_signals,
    "structure_break": compute_structure_break_signals,
    "macd_momentum": compute_macd_momentum_signals,
    "volatility_squeeze": compute_volatility_squeeze_signals,
    "volatility_regime": compute_volatility_regime_signals,
}

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

def run_test(strategy, symbols, interval, max_pos=2, cooldown=4,
             risk_pct=1.0, trail_act=0.4, trail_pct=0.22, label=""):
    compute_fn = COMPUTE_FN[strategy]
    adx_threshold = getattr(CFG, 'ADX_MIN', 25)
    compute_fn = COMPUTE_FN[strategy]
    data = {}
    for sym in symbols:
        try:
            df = fetch_klines(sym, interval, "2026-02-20", END_DATE)
            if len(df) >= 50: data[sym] = df
            time.sleep(0.08)
        except: pass

    if not data: return None

    start_ms = int(datetime.strptime(START_DATE, "%Y-%m-%d").timestamp() * 1000)
    all_sig = []
    for sym, df in data.items():
        for bar in range(50, len(df)):
            try:
                sig = compute_fn(df.iloc[max(0,bar-WINDOW+1):bar+1])
                sl = sig.get("breakout_long", False)
                ss = sig.get("breakout_short", False)
                if sl or ss:
                    ct = int(df.iloc[bar]["close_time"])
                    all_sig.append((ct, sym, "LONG" if sl else "SHORT", sig, bar))
            except: pass
    all_sig.sort(key=lambda x: x[0])

    equity = INITIAL_CAPITAL
    positions = {}
    trades = []
    cooldown_until = {}
    blocked = {"adx":0, "cd":0, "mp":0, "sl":0}
    total_sig = 0

    for ct, sym, direction, sig, bar in all_sig:
        if ct < start_ms: continue
        total_sig += 1
        df = data[sym]

        # Update open positions
        for psym in list(positions.keys()):
            pos = positions[psym]
            pdf = data[psym]
            for ub in range(pos.entry_bar + 1, bar + 1):
                if ub >= len(pdf) or psym not in positions: break
                h,l,c = float(pdf.iloc[ub]["high"]), float(pdf.iloc[ub]["low"]), float(pdf.iloc[ub]["close"])
                is_long = pos.side == "LONG"
                if is_long and l <= pos.current_sl:
                    pnl = (pos.current_sl - pos.entry_price) * pos.qty
                    comm = pos.current_sl * pos.qty * (COMMISSION_PCT/100)
                    trades.append({"symbol":psym,"side":pos.side,"entry":pos.entry_price,"exit":pos.current_sl,"pnl":pnl-comm,"reason":"TRAILING" if pos.trailing_activated else "SL"})
                    equity += pnl - comm
                    del positions[psym]; break
                elif not is_long and h >= pos.current_sl:
                    pnl = (pos.entry_price - pos.current_sl) * pos.qty
                    comm = pos.current_sl * pos.qty * (COMMISSION_PCT/100)
                    trades.append({"symbol":psym,"side":pos.side,"entry":pos.entry_price,"exit":pos.current_sl,"pnl":pnl-comm,"reason":"TRAILING" if pos.trailing_activated else "SL"})
                    equity += pnl - comm
                    del positions[psym]; break
                if psym not in positions: break
                if is_long:
                    pos.best_price = max(pos.best_price, h)
                    ppct = (c - pos.entry_price) / pos.entry_price * 100
                else:
                    pos.best_price = min(pos.best_price, l)
                    ppct = (pos.entry_price - c) / pos.entry_price * 100
                if ppct >= trail_act:
                    pos.trailing_activated = True
                    if is_long:
                        ns = max(pos.best_price*(1-trail_pct/100), pos.entry_price)
                        if ns > pos.current_sl: pos.current_sl = ns
                    else:
                        ns = min(pos.best_price*(1+trail_pct/100), pos.entry_price)
                        if ns < pos.current_sl: pos.current_sl = ns

        # Guards
        if strategy == "ema_breakout":
            if float(sig.get("adx",0)) < adx_threshold: blocked["adx"]+=1; continue
        if sym in cooldown_until and bar < cooldown_until[sym]: blocked["cd"]+=1; continue
        if len(positions) >= max_pos: blocked["mp"]+=1; continue
        if sym in positions: continue

        price = float(sig.get("signal_price", sig.get("close",0)))
        atr_val = float(sig.get("atr",0))
        if price<=0 or atr_val<=0: continue

        # Slippage filter
        if atr_val > 0 and (float(df.iloc[bar]["high"])-float(df.iloc[bar]["low"]))/atr_val > 2.0:
            blocked["sl"]+=1; continue

        risk_usdt = equity * (risk_pct/max_pos/100.0)
        stop_dist = max(atr_val*0.5, price*0.001)
        sl_dist = max(atr_val*CFG.INITIAL_SL_ATR_MULT, price*CFG.MIN_INITIAL_SL_PCT/100.0)
        initial_sl = price-sl_dist if direction=="LONG" else price+sl_dist
        if initial_sl<=0: continue
        qty = max(risk_usdt/stop_dist, 0.001)
        if price*qty < CFG.MIN_NOTIONAL_USDT: qty = CFG.MIN_NOTIONAL_USDT/price
        equity -= price*qty*(COMMISSION_PCT/100)

        from dataclasses import dataclass as dc
        @dc
        class P:
            symbol:str; side:str; entry_price:float; qty:float; entry_bar:int
            initial_sl:float; current_sl:float; trailing_activated:bool=False; best_price:float=0
            def __post_init__(self): self.best_price=self.entry_price; self.current_sl=self.initial_sl
        positions[sym] = P(symbol=sym,side=direction,entry_price=price,qty=qty,entry_bar=bar,initial_sl=initial_sl,current_sl=initial_sl)
        cooldown_until[sym] = bar + cooldown

    # Close remaining
    for psym in list(positions.keys()):
        pos = positions[psym]
        pdf = data[psym]
        exit_price = float(pdf.iloc[-1]["close"])
        is_long = pos.side == "LONG"
        pnl = (exit_price-pos.entry_price)*pos.qty if is_long else (pos.entry_price-exit_price)*pos.qty
        comm = exit_price*pos.qty*(COMMISSION_PCT/100)
        trades.append({"symbol":psym,"side":pos.side,"entry":pos.entry_price,"exit":exit_price,"pnl":pnl-comm,"reason":"END"})
        equity += pnl - comm

    if not trades: return {"trades":0,"wins":0,"wr":0,"pf":0,"pnl":0,"sig":total_sig,"blocked":blocked,"label":label}
    wins = [t for t in trades if t["pnl"]>0]
    tpnl = sum(t["pnl"] for t in trades)
    gw = sum(t["pnl"] for t in wins)
    gl = abs(sum(t["pnl"] for t in trades if t["pnl"]<=0))
    return {"trades":len(trades),"wins":len(wins),"wr":len(wins)/len(trades)*100,
            "pf":gw/gl if gl>0 else 0,"pnl":tpnl,"sig":total_sig,"blocked":blocked,"label":label}

def print_result(r):
    if r is None:
        print("  ❌ Sin datos"); return
    b = r["blocked"]
    print(f"  Trades: {r['trades']} | Wins: {r['wins']} | WR: {r['wr']:.0f}% | PF: {r['pf']:.2f} | PnL: ${r['pnl']:+.4f}")
    print(f"  Señales: {r['sig']} | Bloqueadas: adx={b['adx']} cd={b['cd']} mp={b['mp']} sl={b['sl']}")

def main():
    tests = [
        # === EMA BREAKOUT (15m) - variaciones del BACKTESTING_LOG ===
        {"strat":"ema_breakout","interval":"15m","label":"EMA 9/21 ADX20 Vol1.2 (default viejo)",
         "symbols":["DOGEUSDT","LINKUSDT","TIAUSDT","ORDIUSDT","PENDLEUSDT","AVAXUSDT"],"adx_min":20},
        {"strat":"ema_breakout","interval":"15m","label":"EMA 21/55 ADX30 Vol1.5 (GANADOR doc)",
         "symbols":["DOGEUSDT","LINKUSDT","TIAUSDT","ORDIUSDT","PENDLEUSDT","AVAXUSDT"],"adx_min":30},
        {"strat":"ema_breakout","interval":"15m","label":"EMA 20/50 ADX30 Vol1.5",
         "symbols":["DOGEUSDT","LINKUSDT","TIAUSDT","ORDIUSDT","PENDLEUSDT","AVAXUSDT"],"adx_min":30},
        {"strat":"ema_breakout","interval":"15m","label":"EMA 12/26 ADX30 Vol1.5",
         "symbols":["DOGEUSDT","LINKUSDT","TIAUSDT","ORDIUSDT","PENDLEUSDT","AVAXUSDT"],"adx_min":30},
        {"strat":"ema_breakout","interval":"15m","label":"EMA 20/50 ADX25 Vol1.5",
         "symbols":["DOGEUSDT","LINKUSDT","TIAUSDT","ORDIUSDT","PENDLEUSDT","AVAXUSDT"],"adx_min":25},
        {"strat":"ema_breakout","interval":"15m","label":"EMA 12/26 ADX25 Vol1.5",
         "symbols":["DOGEUSDT","LINKUSDT","TIAUSDT","ORDIUSDT","PENDLEUSDT","AVAXUSDT"],"adx_min":25},
        {"strat":"ema_breakout","interval":"15m","label":"EMA ADX30 top3: DOGE+LINK+TIA",
         "symbols":["DOGEUSDT","LINKUSDT","TIAUSDT"],"adx_min":30},
        {"strat":"ema_breakout","interval":"15m","label":"EMA ADX30 top3: ORDI+PENDLE+AVAX",
         "symbols":["ORDIUSDT","PENDLEUSDT","AVAXUSDT"],"adx_min":30},

        # === STOP HUNT (5m) - variaciones ===
        {"strat":"stop_hunt","interval":"5m","label":"SH default (Wick0.20 Rej0.7 Vol1.5 ADX18)",
         "symbols":["1000PEPEUSDT","AVAXUSDT","ORDIUSDT","SUIUSDT","WIFUSDT"],"adx_min":18},
        {"strat":"stop_hunt","interval":"5m","label":"SH Wick0.15 Rej0.6 Vol1.5 ADX18",
         "symbols":["1000PEPEUSDT","AVAXUSDT","ORDIUSDT","SUIUSDT","WIFUSDT"],"adx_min":18},
        {"strat":"stop_hunt","interval":"5m","label":"SH default top3: PEPE+SUI+WIF",
         "symbols":["1000PEPEUSDT","SUIUSDT","WIFUSDT"],"adx_min":18},
        {"strat":"stop_hunt","interval":"5m","label":"SH default top3: AVAX+ORDI+WIF",
         "symbols":["AVAXUSDT","ORDIUSDT","WIFUSDT"],"adx_min":18},
        {"strat":"stop_hunt","interval":"5m","label":"SH 5 symbols + NEAR",
         "symbols":["1000PEPEUSDT","SUIUSDT","WIFUSDT","NEARUSDT","ORDIUSDT"],"adx_min":18},
        {"strat":"stop_hunt","interval":"5m","label":"SH 5 symbols + PENDLE",
         "symbols":["1000PEPEUSDT","SUIUSDT","WIFUSDT","PENDLEUSDT","AVAXUSDT"],"adx_min":18},

        # === RSI+BB REVERSION (5m) - variaciones ===
        {"strat":"rsi_bb_reversion","interval":"5m","label":"RSI OS25 OB75 BB2.0 Vol1.5 ADX15 (default)",
         "symbols":["1000PEPEUSDT","AVAXUSDT","TIAUSDT","ORDIUSDT","TAOUSDT"],"adx_min":15},
        {"strat":"rsi_bb_reversion","interval":"5m","label":"RSI OS20 OB70 BB1.5 Vol1.5 ADX25",
         "symbols":["1000PEPEUSDT","AVAXUSDT","TIAUSDT","ORDIUSDT","TAOUSDT"],"adx_min":25},
        {"strat":"rsi_bb_reversion","interval":"5m","label":"RSI OS20 OB70 BB1.5 Vol1.5 ADX20",
         "symbols":["1000PEPEUSDT","AVAXUSDT","TIAUSDT","ORDIUSDT","TAOUSDT"],"adx_min":20},
        {"strat":"rsi_bb_reversion","interval":"5m","label":"RSI default top3: PEPE+TIA+TAO",
         "symbols":["1000PEPEUSDT","TIAUSDT","TAOUSDT"],"adx_min":15},
        {"strat":"rsi_bb_reversion","interval":"5m","label":"RSI default top3: AVAX+ORDI+TIA",
         "symbols":["AVAXUSDT","ORDIUSDT","TIAUSDT"],"adx_min":15},
        {"strat":"rsi_bb_reversion","interval":"5m","label":"RSI default 5 + XRP",
         "symbols":["1000PEPEUSDT","AVAXUSDT","TIAUSDT","ORDIUSDT","XRPUSDT"],"adx_min":15},

        # === VOLATILITY SQUEEZE (1h) - variaciones ===
        {"strat":"volatility_squeeze","interval":"1h","label":"VS default (ATR15 BB25 Vol1.5 ADX15)",
         "symbols":["NEARUSDT","OPUSDT","BTCUSDT","LINKUSDT","XRPUSDT"],"adx_min":15},
        {"strat":"volatility_squeeze","interval":"1h","label":"VS top3: NEAR+OP+BTC",
         "symbols":["NEARUSDT","OPUSDT","BTCUSDT"],"adx_min":15},
        {"strat":"volatility_squeeze","interval":"1h","label":"VS top3: LINK+XRP+BTC",
         "symbols":["LINKUSDT","XRPUSDT","BTCUSDT"],"adx_min":15},
        {"strat":"volatility_squeeze","interval":"1h","label":"VS 5 + SOL",
         "symbols":["NEARUSDT","OPUSDT","BTCUSDT","SOLUSDT","XRPUSDT"],"adx_min":15},
        {"strat":"volatility_squeeze","interval":"1h","label":"VS ADX20",
         "symbols":["NEARUSDT","OPUSDT","BTCUSDT","LINKUSDT","XRPUSDT"],"adx_min":20},

        # === VOLATILITY REGIME (1h) - variaciones ===
        {"strat":"volatility_regime","interval":"1h","label":"VR baseline (Low20 High70 Vol1.3 ADX18 Bars3)",
         "symbols":["XRPUSDT","BTCUSDT","DOGEUSDT","OPUSDT","FILUSDT"],"adx_min":18},
        {"strat":"volatility_regime","interval":"1h","label":"VR A (Low25 High75 Vol1.5 ADX22 Bars4) GANADOR",
         "symbols":["XRPUSDT","BTCUSDT","DOGEUSDT","OPUSDT","FILUSDT"],"adx_min":22},
        {"strat":"volatility_regime","interval":"1h","label":"VR B (Low15 High80 Vol1.8 ADX25 Bars4)",
         "symbols":["XRPUSDT","BTCUSDT","DOGEUSDT","OPUSDT","FILUSDT"],"adx_min":25},
        {"strat":"volatility_regime","interval":"1h","label":"VR A top3: XRP+BTC+DOGE",
         "symbols":["XRPUSDT","BTCUSDT","DOGEUSDT"],"adx_min":22},
        {"strat":"volatility_regime","interval":"1h","label":"VR A top3: OP+FIL+BTC",
         "symbols":["OPUSDT","FILUSDT","BTCUSDT"],"adx_min":22},
        {"strat":"volatility_regime","interval":"1h","label":"VR A 5 + NEAR",
         "symbols":["XRPUSDT","BTCUSDT","DOGEUSDT","OPUSDT","NEARUSDT"],"adx_min":22},
    ]

    results = {}
    for i, t in enumerate(tests):
        print(f"\n{'─'*70}")
        print(f"  [{i+1}/{len(tests)}] {t['label']}")
        print(f"  {t['strat']} ({t['interval']}) — {t['symbols']}")
        print(f"{'─'*70}")

        r = run_test(t["strat"], t["symbols"], t["interval"], adx_min=t.get("adx_min",30), label=t["label"])
        print_result(r)
        if r: results[t["label"]] = r

    # Resumen
    print(f"\n{'='*90}")
    print(f"  RESUMEN FINAL POR ESTRATEGIA")
    print(f"{'='*90}\n")

    for strat_name in ["ema_breakout","stop_hunt","rsi_bb_reversion","volatility_squeeze","volatility_regime"]:
        strat_results = {k:v for k,v in results.items() if strat_name.replace("_"," ") in k.lower() or
                        (strat_name=="ema_breakout" and "EMA" in k) or
                        (strat_name=="stop_hunt" and "SH " in k) or
                        (strat_name=="rsi_bb_reversion" and "RSI" in k) or
                        (strat_name=="volatility_squeeze" and "VS " in k) or
                        (strat_name=="volatility_regime" and "VR " in k)}
        if not strat_results: continue
        print(f"  {strat_name.upper().replace('_',' ')}:")
        print(f"  {'Variación':<55} {'T':>4} {'W':>4} {'WR':>5} {'PF':>6} {'PnL':>9}")
        print(f"  {'─'*85}")
        for label, r in sorted(strat_results.items(), key=lambda x: x[1]["pnl"], reverse=True):
            print(f"  {label:<55} {r['trades']:>4} {r['wins']:>4} {r['wr']:>4.0f}% {r['pf']:>6.2f} {r['pnl']:>+9.4f}")
        print()

if __name__ == "__main__":
    main()
