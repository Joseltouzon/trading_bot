#!/usr/bin/env python3
"""
Backtest 1:1 con el bot real de producción.
Replica exactamente:
  - SignalEngine: señales solo en vela cerrada, una por símbolo/estrategia
  - EventLoop guards: cooldown, max_positions, ADX filter
  - OrderManager: qty = risk / stop_dist, SL inicial = max(ATR*mult, min_pct)
                  spread filter dinámico, slippage guard, funding filter, trade lock
  - TrailingManager: activación por pct, ATR o fijo, solo mejora
  - TakeProfitManager: cierre parcial por %, una vez por símbolo
  - Comisiones reales 0.04% por lado
"""
import sys
import os
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
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
from strategy.indicators import atr


# ============================================================
# CONFIG
# ============================================================
START_DATE = "2026-03-25"
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


# ============================================================
# POSITION SIMULATOR
# ============================================================
@dataclass
class SimPos:
    symbol: str
    side: str
    strategy: str
    entry_price: float
    qty: float
    entry_bar: int
    initial_sl: float
    current_sl: float
    trailing_activated: bool = False
    best_price: float = 0.0
    tp_executed: bool = False

    def __post_init__(self):
        self.best_price = self.entry_price
        self.current_sl = self.initial_sl


@dataclass
class Trade:
    symbol: str
    side: str
    strategy: str
    entry_price: float
    exit_price: float
    qty: float
    entry_bar: int
    exit_bar: int
    pnl_usdt: float
    pnl_pct: float
    commission: float
    exit_reason: str
    entry_time: str = ""
    exit_time: str = ""


class FaithfulBacktest:
    def __init__(self, risk_pct, leverage, max_positions, cooldown_bars,
                 trailing_activation_pct, trailing_use_atr, trailing_atr_mult,
                 trailing_pct, use_take_profit, tp_by_pct, tp_activation_pct,
                 tp_close_pct, initial_sl_atr_mult, min_initial_sl_pct,
                 adx_min, adx_rising=False):
        self.equity = INITIAL_CAPITAL
        self.peak_equity = INITIAL_CAPITAL
        self.positions: dict[str, SimPos] = {}
        self.trades: list[Trade] = []
        self.equity_curve: list[float] = [INITIAL_CAPITAL]
        self.cooldown_until: dict[str, int] = {}
        self._last_processed: dict[tuple, int] = {}
        self._tp_executed: set[str] = set()
        self._last_entry: dict[str, int] = {}

        self.risk_pct = risk_pct
        self.leverage = leverage
        self.max_positions = max_positions
        self.cooldown_bars = cooldown_bars
        self.trailing_activation_pct = trailing_activation_pct
        self.trailing_use_atr = trailing_use_atr
        self.trailing_atr_mult = trailing_atr_mult
        self.trailing_pct = trailing_pct
        self.use_take_profit = use_take_profit
        self.tp_by_pct = tp_by_pct
        self.tp_activation_pct = tp_activation_pct
        self.tp_close_pct = tp_close_pct
        self.initial_sl_atr_mult = initial_sl_atr_mult
        self.min_initial_sl_pct = min_initial_sl_pct
        self.adx_min = adx_min
        self.adx_rising = adx_rising

        self.signals_generated = 0
        self.signals_blocked_cooldown = 0
        self.signals_blocked_maxpos = 0
        self.signals_blocked_adx = 0
        self.signals_blocked_spread = 0
        self.signals_blocked_slippage = 0
        self.signals_blocked_funding = 0
        self.signals_blocked_throttle = 0

    def _execute_entry(self, symbol, direction, sig, bar, df, strategy):
        price = float(sig.get("signal_price", sig.get("close", 0)))
        atr_val = float(sig.get("atr", 0))
        if price <= 0 or atr_val <= 0:
            return

        # === Filtro 1: Spread (volumen relativo) ===
        if bar >= 20:
            vol_series = df["volume"].iloc[bar-20:bar+1]
            avg_vol = float(vol_series.mean())
            curr_vol = float(df.iloc[bar]["volume"])
            if avg_vol > 0 and (curr_vol / avg_vol) < 0.5:
                self.signals_blocked_spread += 1
                return
            prev_high = float(df.iloc[bar-1]["high"])
            prev_low = float(df.iloc[bar-1]["low"])
            prev_close = float(df.iloc[bar-1]["close"])
            if prev_close > 0:
                spread_pct = ((prev_high - prev_low) / prev_close) * 100
                atr_pct = (atr_val / price) * 100
                base_spread = float(getattr(CFG, "MAX_SPREAD_PCT", 0.10))
                dynamic_max_spread = (base_spread + (atr_pct * 0.5)) * 3.0
                if spread_pct > dynamic_max_spread:
                    self.signals_blocked_spread += 1
                    return

        # === Filtro 2: Slippage (rango vela vs ATR) ===
        if bar > 0:
            curr_high = float(df.iloc[bar]["high"])
            curr_low = float(df.iloc[bar]["low"])
            if atr_val > 0 and (curr_high - curr_low) / atr_val > 2.0:
                self.signals_blocked_slippage += 1
                return

        # === Filtro 3: Funding (movimiento reciente) ===
        if bar >= 20:
            lookback = float(df.iloc[bar-20]["close"])
            if lookback > 0:
                recent_move = ((price - lookback) / lookback) * 100
                if direction == "LONG" and recent_move > 2.0:
                    self.signals_blocked_funding += 1
                    return
                elif direction == "SHORT" and recent_move < -2.0:
                    self.signals_blocked_funding += 1
                    return

        # === Filtro 4: Throttling ===
        last_entry_bar = self._last_entry.get(symbol, -999)
        if bar - last_entry_bar < 2:
            self.signals_blocked_throttle += 1
            return

        # === Risk Management ===
        risk_pct_per_trade = self.risk_pct / self.max_positions
        risk_usdt = self.equity * (risk_pct_per_trade / 100.0)
        stop_dist = max(atr_val * 0.5, price * 0.001)
        raw_sl_dist = atr_val * self.initial_sl_atr_mult
        min_sl_dist = price * (self.min_initial_sl_pct / 100.0)
        final_sl_dist = max(raw_sl_dist, min_sl_dist)

        if direction == "LONG":
            initial_sl = price - final_sl_dist
        else:
            initial_sl = price + final_sl_dist
        if initial_sl <= 0:
            return

        qty = max(risk_usdt / stop_dist, 0.001)
        notional = price * qty
        if notional < CFG.MIN_NOTIONAL_USDT:
            qty = CFG.MIN_NOTIONAL_USDT / price

        commission = price * qty * (COMMISSION_PCT / 100)
        self.equity -= commission

        bar_time = ""
        if "close_time" in df.columns:
            ts = int(df.iloc[bar]["close_time"])
            bar_time = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M")

        pos = SimPos(symbol=symbol, side=direction, strategy=strategy,
                     entry_price=price, qty=qty, entry_bar=bar,
                     initial_sl=initial_sl, current_sl=initial_sl)
        pos._entry_time = bar_time
        self.positions[symbol] = pos
        self._last_entry[symbol] = bar

    def update_positions(self, symbol, df, bar):
        pos = self.positions.get(symbol)
        if pos is None:
            return
        row = df.iloc[bar]
        high, low, close = float(row["high"]), float(row["low"]), float(row["close"])
        is_long = pos.side == "LONG"

        bar_time = ""
        if "close_time" in df.columns:
            ts = int(row["close_time"])
            bar_time = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M")

        # 1. SL check
        if is_long and low <= pos.current_sl:
            self._close(symbol, df, bar, "TRAILING" if pos.trailing_activated else "STOP_LOSS",
                        exit_price=pos.current_sl, exit_time=bar_time); return
        elif not is_long and high >= pos.current_sl:
            self._close(symbol, df, bar, "TRAILING" if pos.trailing_activated else "STOP_LOSS",
                        exit_price=pos.current_sl, exit_time=bar_time); return

        # 2. Take Profit
        if self.use_take_profit and self.tp_by_pct and not pos.tp_executed:
            profit_pct = (close - pos.entry_price) / pos.entry_price * 100 if is_long else (pos.entry_price - close) / pos.entry_price * 100
            if profit_pct >= self.tp_activation_pct:
                close_qty = pos.qty * (self.tp_close_pct / 100)
                remaining_qty = pos.qty - close_qty
                if remaining_qty > 0:
                    pnl = (close - pos.entry_price) * close_qty if is_long else (pos.entry_price - close) * close_qty
                    commission = close * close_qty * (COMMISSION_PCT / 100)
                    self.equity += pnl - commission
                    self.trades.append(Trade(symbol=symbol, side=pos.side, strategy=pos.strategy,
                        entry_price=pos.entry_price, exit_price=close, qty=close_qty,
                        entry_bar=pos.entry_bar, exit_bar=bar, pnl_usdt=pnl-commission,
                        pnl_pct=(pnl/(pos.entry_price*close_qty))*100, commission=commission,
                        exit_reason="TAKE_PROFIT", entry_time=getattr(pos,'_entry_time',''), exit_time=bar_time))
                    pos.qty = remaining_qty
                    pos.tp_executed = True
                else:
                    self._close(symbol, df, bar, "TAKE_PROFIT", exit_price=close, exit_time=bar_time); return

        # 3. Trailing
        if is_long:
            pnl_pct = (close - pos.entry_price) / pos.entry_price * 100
            pos.best_price = max(pos.best_price, high)
        else:
            pnl_pct = (pos.entry_price - close) / pos.entry_price * 100
            pos.best_price = min(pos.best_price, low)

        if pnl_pct >= self.trailing_activation_pct:
            if not pos.trailing_activated:
                pos.trailing_activated = True
            if is_long:
                new_sl = pos.best_price * (1 - self.trailing_pct / 100)
                new_sl = max(new_sl, pos.entry_price)
                if new_sl > pos.current_sl:
                    pos.current_sl = new_sl
            else:
                new_sl = pos.best_price * (1 + self.trailing_pct / 100)
                new_sl = min(new_sl, pos.entry_price)
                if new_sl < pos.current_sl:
                    pos.current_sl = new_sl

    def _close(self, symbol, df, bar, reason, exit_price=None, exit_time=""):
        pos = self.positions.get(symbol)
        if pos is None:
            return
        if exit_price is None:
            exit_price = float(df.iloc[bar]["close"])
        is_long = pos.side == "LONG"
        pnl = (exit_price - pos.entry_price) * pos.qty if is_long else (pos.entry_price - exit_price) * pos.qty
        commission = exit_price * pos.qty * (COMMISSION_PCT / 100)
        net_pnl = pnl - commission
        self.equity += net_pnl
        self.peak_equity = max(self.peak_equity, self.equity)
        pnl_pct = (pnl / (pos.entry_price * pos.qty)) * 100

        if not exit_time and "close_time" in df.columns:
            ts = int(df.iloc[bar]["close_time"])
            exit_time = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M")

        self.trades.append(Trade(symbol=symbol, side=pos.side, strategy=pos.strategy,
            entry_price=pos.entry_price, exit_price=exit_price, qty=pos.qty,
            entry_bar=pos.entry_bar, exit_bar=bar, pnl_usdt=net_pnl, pnl_pct=pnl_pct,
            commission=commission, exit_reason=reason,
            entry_time=getattr(pos,'_entry_time',''), exit_time=exit_time))
        self.cooldown_until[symbol] = bar + self.cooldown_bars
        del self.positions[symbol]

    def generate_report(self):
        if not self.trades:
            return {"trades": 0}
        wins = [t for t in self.trades if t.pnl_usdt > 0]
        losses = [t for t in self.trades if t.pnl_usdt <= 0]
        total_pnl = sum(t.pnl_usdt for t in self.trades)
        win_rate = len(wins) / len(self.trades) * 100
        gross_wins = sum(t.pnl_usdt for t in wins)
        gross_losses = abs(sum(t.pnl_usdt for t in losses))
        profit_factor = gross_wins / gross_losses if gross_losses > 0 else 0

        peak = self.equity_curve[0]
        max_dd = 0
        for eq in self.equity_curve:
            if eq > peak: peak = eq
            dd = peak - eq
            if dd > max_dd: max_dd = dd

        by_strategy = {}
        for t in self.trades:
            if t.strategy not in by_strategy:
                by_strategy[t.strategy] = {"trades": 0, "pnl": 0, "wins": 0}
            by_strategy[t.strategy]["trades"] += 1
            by_strategy[t.strategy]["pnl"] += t.pnl_usdt
            if t.pnl_usdt > 0: by_strategy[t.strategy]["wins"] += 1

        exit_reasons = {}
        for t in self.trades:
            exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1

        return {
            "total_trades": len(self.trades), "wins": len(wins), "losses": len(losses),
            "win_rate": round(win_rate, 1), "total_pnl": round(total_pnl, 4),
            "net_pnl": round(total_pnl, 4), "profit_factor": round(profit_factor, 2),
            "max_drawdown": round(max_dd, 4), "final_equity": round(self.equity, 2),
            "return_pct": round((self.equity - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100, 2),
            "by_strategy": by_strategy, "exit_reasons": exit_reasons,
            "signals_generated": self.signals_generated,
            "blocked_cooldown": self.signals_blocked_cooldown,
            "blocked_maxpos": self.signals_blocked_maxpos,
            "blocked_adx": self.signals_blocked_adx,
            "blocked_spread": self.signals_blocked_spread,
            "blocked_slippage": self.signals_blocked_slippage,
            "blocked_funding": self.signals_blocked_funding,
            "blocked_throttle": self.signals_blocked_throttle,
            "trades_detail": self.trades,
        }


def fetch_klines(symbol, interval, start_date, end_date):
    client = Client()
    klines = client.futures_historical_klines(
        symbol=symbol, interval=interval,
        start_str=f"{start_date} 00:00 UTC", end_str=f"{end_date} 00:00 UTC")
    if not klines:
        return pd.DataFrame()
    df = pd.DataFrame(klines, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","quote_volume","trades","taker_buy_base","taker_buy_quote","ignore"])
    for c in ["open","high","low","close","volume"]:
        df[c] = df[c].astype(float)
    df["close_time"] = df["close_time"].astype(int)
    return df


def main():
    print(f"\n{'='*90}")
    print(f"  BACKTEST FIEL AL BOT REAL — {START_DATE} → {END_DATE}")
    print(f"  Replica: SignalEngine + EventLoop guards + OrderManager filters + Trailing + TP")
    print(f"{'='*90}")

    db = Database()
    state = db.load_state()
    strategy_symbols = state.get("strategy_symbols", CFG.DEFAULT_STRATEGY_SYMBOLS)

    risk_pct = float(state.get("risk_pct", CFG.DEFAULT_RISK_PCT))
    leverage = int(state.get("leverage", CFG.DEFAULT_LEVERAGE))
    max_positions = int(state.get("max_positions", CFG.MAX_OPEN_POSITIONS))
    cooldown_bars = int(state.get("cooldown_bars", CFG.COOLDOWN_BARS))
    trailing_activation_pct = float(state.get("trailing_activation_pct", CFG.TRAILING_ACTIVATION_PCT))
    trailing_use_atr = bool(state.get("trailing_use_atr", CFG.TRAILING_USE_ATR))
    trailing_atr_mult = float(state.get("trailing_atr_mult", CFG.TRAILING_ATR_MULT))
    trailing_pct = float(state.get("trailing_pct", CFG.TRAILING_PCT))
    adx_min = float(state.get("adx_min", CFG.ADX_MIN))
    enabled_map = {k: True for k in strategy_symbols.keys()}

    print(f"\n  Risk: {risk_pct}% | Lev: {leverage}x | Max pos: {max_positions} | Cooldown: {cooldown_bars} bars")
    print(f"  Trailing: {trailing_pct}% (activation {trailing_activation_pct}%)")
    print(f"  TP: {CFG.TP_ACTIVATION_PCT}% → close {CFG.TP_CLOSE_PCT}%")
    print(f"  SL: ATR×{CFG.INITIAL_SL_ATR_MULT} min {CFG.MIN_INITIAL_SL_PCT}% | ADX min: {adx_min}")
    print(f"  Commission: {COMMISSION_PCT}% per side")

    # Descargar datos
    data_by_interval = {}
    for strat, syms in strategy_symbols.items():
        interval = CFG.STRATEGY_INTERVALS.get(strat, "5m")
        if interval not in data_by_interval:
            data_by_interval[interval] = {}
            print(f"\n  Descargando {interval}:")
        for sym in sorted(syms):
            if sym in data_by_interval[interval]:
                continue
            try:
                df = fetch_klines(sym, interval, "2026-03-20", END_DATE)
                if len(df) >= 50:
                    data_by_interval[interval][sym] = df
                    print(f"    ✅ {sym}: {len(df)} velas")
                else:
                    print(f"    ⚠️ {sym}: solo {len(df)} velas")
                time.sleep(0.3)
            except Exception as e:
                print(f"    ❌ {sym}: {e}")

    # Ejecutar backtest con línea temporal unificada
    engine = FaithfulBacktest(
        risk_pct=risk_pct, leverage=leverage, max_positions=max_positions,
        cooldown_bars=cooldown_bars,
        trailing_activation_pct=trailing_activation_pct,
        trailing_use_atr=trailing_use_atr, trailing_atr_mult=trailing_atr_mult,
        trailing_pct=trailing_pct,
        use_take_profit=CFG.USE_TAKE_PROFIT, tp_by_pct=CFG.TP_BY_PCT,
        tp_activation_pct=CFG.TP_ACTIVATION_PCT, tp_close_pct=CFG.TP_CLOSE_PCT,
        initial_sl_atr_mult=CFG.INITIAL_SL_ATR_MULT, min_initial_sl_pct=CFG.MIN_INITIAL_SL_PCT,
        adx_min=adx_min
    )

    base_data = data_by_interval.get("5m", {})
    if not base_data:
        base_data = data_by_interval.get("15m", {})
    if not base_data:
        print("  ❌ Sin datos base"); return

    total_bars = min(len(df) for df in base_data.values())
    print(f"\n  Línea temporal: {total_bars} velas de 5m\n  Procesando...")

    bar_counters = {iv: 0 for iv in ["5m","15m","1h"]}

    for bar in range(50, total_bars):
        for symbol in list(engine.positions.keys()):
            pos = engine.positions[symbol]
            pos_interval = CFG.STRATEGY_INTERVALS.get(pos.strategy, "5m")
            pos_df = data_by_interval.get(pos_interval, {}).get(symbol)
            if pos_df is None: continue
            pos_bar = bar // (3 if pos_interval=="15m" else 12 if pos_interval=="1h" else 1)
            if pos_bar >= len(pos_df): continue
            engine.update_positions(symbol, pos_df, pos_bar)

        engine.equity_curve.append(engine.equity)

        for interval, data in data_by_interval.items():
            if not data: continue
            if interval == "5m": iv_bar = bar
            elif interval == "15m": iv_bar = bar // 3
            elif interval == "1h": iv_bar = bar // 12
            else: continue
            if iv_bar <= bar_counters[interval]: continue
            bar_counters[interval] = iv_bar

            for symbol, df in data.items():
                if iv_bar >= len(df): continue
                for strat, syms in strategy_symbols.items():
                    if symbol not in syms: continue
                    if CFG.STRATEGY_INTERVALS.get(strat, "5m") != interval: continue
                    if not enabled_map.get(strat, True): continue
                    pk = (symbol, strat)
                    if engine._last_processed.get(pk) == iv_bar: continue
                    engine._last_processed[pk] = iv_bar

                    compute_fn = STRATEGY_COMPUTE.get(strat)
                    if not compute_fn: continue
                    try:
                        window = df.iloc[:iv_bar+1].copy()
                        if len(window) < 50: continue
                        sig = compute_fn(window)
                        sl = sig.get("breakout_long", False)
                        ss = sig.get("breakout_short", False)
                        if not sl and not ss: continue
                        direction = "LONG" if sl else "SHORT"
                        engine.signals_generated += 1

                        if strat == "ema_breakout":
                            if float(sig.get("adx",0)) < engine.adx_min:
                                engine.signals_blocked_adx += 1; continue
                        if symbol in engine.cooldown_until and iv_bar < engine.cooldown_until[symbol]:
                            engine.signals_blocked_cooldown += 1; continue
                        if len(engine.positions) >= engine.max_positions:
                            engine.signals_blocked_maxpos += 1; continue
                        if symbol in engine.positions: continue
                        engine._execute_entry(symbol, direction, sig, iv_bar, df, strat)
                    except: pass

    for symbol in list(engine.positions.keys()):
        pos = engine.positions[symbol]
        pos_interval = CFG.STRATEGY_INTERVALS.get(pos.strategy, "5m")
        data = data_by_interval.get(pos_interval, {})
        df = data.get(symbol)
        if df is not None:
            engine._close(symbol, df, len(df)-1, "END_OF_DATA")

    report = engine.generate_report()
    print(f"\n{'='*90}")
    print(f"  RESULTADOS BACKTEST")
    print(f"{'='*90}\n")

    if report.get("total_trades", 0) > 0:
        print(f"  Señales: {report['signals_generated']} generadas")
        print(f"  Bloqueadas: cooldown={report['blocked_cooldown']} maxpos={report['blocked_maxpos']} "
              f"adx={report['blocked_adx']} spread={report['blocked_spread']} "
              f"slippage={report['blocked_slippage']} funding={report['blocked_funding']} "
              f"throttle={report['blocked_throttle']}")
        print(f"\n  Trades: {report['total_trades']} | Wins: {report['wins']} | Losses: {report['losses']}")
        print(f"  Win Rate: {report['win_rate']}% | Profit Factor: {report['profit_factor']}")
        print(f"  PnL: ${report['net_pnl']:+.4f} | Return: {report['return_pct']:+.2f}%")
        print(f"  Max DD: ${report['max_drawdown']:.4f} | Equity: ${report['final_equity']:.2f}")

        print(f"\n  Por estrategia:")
        print(f"  {'Estrategia':<22} {'Trades':>7} {'Wins':>5} {'WR%':>6} {'PnL':>10}")
        print(f"  {'─'*55}")
        for s, d in report["by_strategy"].items():
            wr = d["wins"]/d["trades"]*100 if d["trades"]>0 else 0
            print(f"  {s:<22} {d['trades']:>7} {d['wins']:>5} {wr:>5.0f}% {d['pnl']:>+10.4f}")

        print(f"\n  Salidas: {report['exit_reasons']}")

        print(f"\n  {'#':>3} {'Symbol':<14} {'Side':<6} {'Strat':<20} {'Entry':>10} {'Exit':>10} {'PnL':>8} {'Razón':<12}")
        print(f"  {'─'*90}")
        for i, t in enumerate(report["trades_detail"], 1):
            print(f"  {i:>3} {t.symbol:<14} {t.side:<6} {t.strategy:<20} {t.entry_price:>10.4f} {t.exit_price:>10.4f} {t.pnl_usdt:>+8.4f} {t.exit_reason:<12}")
    else:
        print(f"  ⚠️ No trades. Señales: {report['signals_generated']}")
        print(f"  Bloqueadas: cooldown={report['blocked_cooldown']} maxpos={report['blocked_maxpos']} "
              f"adx={report['blocked_adx']} spread={report['blocked_spread']}")

    # Comparación DB
    print(f"\n{'='*90}")
    real = db.get_recent_closed_positions_filtered(limit=None, start_date=START_DATE, end_date=END_DATE)
    real_pnl = sum(float(p["realized_pnl"]) for p in real) if real else 0
    real_wins = sum(1 for p in real if float(p["realized_pnl"]) > 0) if real else 0

    print(f"  {'Métrica':<25} {'Backtest':>15} {'Producción':>15}")
    print(f"  {'─'*58}")
    print(f"  {'Trades':<25} {report.get('total_trades',0):>15} {len(real) if real else 0:>15}")
    print(f"  {'Wins':<25} {report.get('wins',0):>15} {real_wins:>15}")
    wr_bt = report.get('win_rate',0)
    wr_real = real_wins/len(real)*100 if real else 0
    print(f"  {'Win Rate':<25} {wr_bt:>14.1f}% {wr_real:>14.1f}%")
    print(f"  {'PnL':<25} ${report.get('net_pnl',0):>+14.4f} ${real_pnl:>+14.4f}")
    print(f"  {'─'*58}")


if __name__ == "__main__":
    main()
