#!/usr/bin/env python3
"""
Backtest engine para Beast Money Maker.

Reutiliza las estrategias existentes (EMA Breakout, Stop Hunt, VWAP Refresh)
y simula trading bar-a-bar con trailing stop, take profit y gestión de riesgo.

Uso:
    python backtest.py                          # Todos los símbolos, estrategia por defecto
    python backtest.py --symbol BTCUSDT         # Solo BTC
    python backtest.py --strategy stop_hunt     # Solo stop hunt
    python backtest.py --days 60                # Últimos 60 días
    python backtest.py --capital 170            # Capital inicial
    python backtest.py --all                    # Probar las 3 estrategias y comparar
"""

import argparse
import sys
import os
import time
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from binance.client import Client

# Importar estrategias del bot
import config as CFG
from strategy.ema_adx_breakout import compute_signals, build_initial_sl
from strategy.stop_hunt import compute_stop_hunt_signals, build_stop_hunt_sl
from strategy.vwap_refresh import compute_vwap_refresh_signals, build_vwap_refresh_sl
from strategy.rsi_bb_reversion import compute_rsi_bb_signals, build_rsi_bb_sl
from strategy.indicators import atr


# ============================================================
# CONFIGURACIÓN DEL BACKTEST
# ============================================================

@dataclass
class BacktestConfig:
    symbols: list = field(default_factory=lambda: ["ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "LTCUSDT", "1000PEPEUSDT", "GRASSUSDT"])
    strategy: str = "ema_breakout"  # ema_breakout | stop_hunt | vwap_refresh | rsi_bb_reversion
    interval: str = CFG.INTERVAL
    days: int = 30
    initial_capital: float = 170.0
    risk_pct: float = 1.0          # % del capital por trade
    leverage: int = 5
    max_positions: int = 2
    commission_pct: float = 0.04   # 0.04% maker/taker Binance

    # Trailing
    trailing_activation_pct: float = CFG.TRAILING_ACTIVATION_PCT
    trailing_use_atr: bool = CFG.TRAILING_USE_ATR
    trailing_atr_mult: float = CFG.TRAILING_ATR_MULT
    trailing_pct: float = CFG.TRAILING_PCT

    # Take Profit
    use_take_profit: bool = CFG.USE_TAKE_PROFIT
    tp_by_pct: bool = CFG.TP_BY_PCT
    tp_activation_pct: float = CFG.TP_ACTIVATION_PCT
    tp_close_pct: float = CFG.TP_CLOSE_PCT

    # SL
    initial_sl_atr_mult: float = CFG.INITIAL_SL_ATR_MULT
    min_initial_sl_pct: float = CFG.MIN_INITIAL_SL_PCT

    # Cooldown
    cooldown_bars: int = CFG.DEFAULT_COOLDOWN_BARS

    # Filters
    adx_min: float = CFG.DEFAULT_ADX_MIN


# ============================================================
# FETCH DE DATOS HISTÓRICOS
# ============================================================

def fetch_klines(symbol: str, interval: str, days: int) -> pd.DataFrame:
    """Descarga klines históricos de Binance Futures."""
    client = Client()

    start_str = f"{days} day ago UTC"
    end_str = "now UTC"

    print(f"  Descargando {symbol} {interval} {days}d...", end=" ", flush=True)

    klines = client.futures_historical_klines(
        symbol=symbol,
        interval=interval,
        start_str=start_str,
        end_str=end_str,
    )

    if not klines:
        print("SIN DATOS")
        return pd.DataFrame()

    df = pd.DataFrame(klines, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore"
    ])

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    df["close_time"] = df["close_time"].astype(int)
    print(f"{len(df)} velas")
    
    # Rate limit: esperar entre descargas
    time.sleep(0.5)
    return df


# ============================================================
# SIMULADOR DE POSICIÓN
# ============================================================

@dataclass
class SimPosition:
    symbol: str
    side: str          # LONG | SHORT
    entry_price: float
    qty: float
    entry_bar: int
    initial_sl: float
    trailing_activated: bool = False
    best_price: float = 0.0
    current_sl: float = 0.0
    tp_executed: bool = False

    def __post_init__(self):
        self.best_price = self.entry_price
        self.current_sl = self.initial_sl


@dataclass
class Trade:
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    qty: float
    entry_bar: int
    exit_bar: int
    pnl_usdt: float
    pnl_pct: float
    commission: float
    exit_reason: str  # STOP_LOSS | TRAILING | TAKE_PROFIT | END_OF_DATA


class BacktestEngine:
    def __init__(self, config: BacktestConfig):
        self.cfg = config
        self.capital = config.initial_capital
        self.equity = config.initial_capital
        self.peak_equity = config.initial_capital
        self.positions: dict[str, SimPosition] = {}
        self.trades: list[Trade] = []
        self.equity_curve: list[float] = [config.initial_capital]
        self.cooldown: dict[str, int] = {}  # symbol -> bar index until cooldown

    def run(self, data: dict[str, pd.DataFrame]) -> dict:
        """Ejecuta el backtest sobre todos los símbolos."""
        if not data:
            return {}

        # Encontrar el rango común de velas
        min_len = min(len(df) for df in data.values())
        total_bars = min_len

        print(f"\n{'='*60}")
        print(f"BACKTEST: {self.cfg.strategy.upper()}")
        print(f"Símbolos: {', '.join(data.keys())}")
        print(f"Período: {total_bars} velas ({self.cfg.interval})")
        print(f"Capital: ${self.cfg.initial_capital:.2f} | Leverage: {self.cfg.leverage}x")
        print(f"Risk: {self.cfg.risk_pct}% | Max pos: {self.cfg.max_positions}")
        print(f"{'='*60}\n")

        # Iterar bar a bar
        for bar in range(50, total_bars):  # Empezar en 50 para tener suficientes indicadores
            # 1. Actualizar posiciones abiertas (trailing, TP, SL)
            for symbol in list(self.positions.keys()):
                df = data.get(symbol)
                if df is None or bar >= len(df):
                    continue
                self._update_position(symbol, df, bar)

            # 2. Generar señales (solo si no estamos al máximo de posiciones)
            if len(self.positions) < self.cfg.max_positions:
                for symbol, df in data.items():
                    if bar >= len(df):
                        continue
                    if symbol in self.positions:
                        continue
                    if symbol in self.cooldown and bar < self.cooldown[symbol]:
                        continue
                    self._check_signal(symbol, df, bar)

            # 3. Registrar equity
            self.equity_curve.append(self.equity)

            # 4. Progress
            if bar % 100 == 0:
                dd = ((self.peak_equity - self.equity) / self.peak_equity) * 100
                print(f"  Bar {bar}/{total_bars} | Equity: ${self.equity:.2f} | DD: {dd:.1f}% | Pos: {len(self.positions)}")

        # Cerrar posiciones restantes al final
        for symbol in list(self.positions.keys()):
            df = data.get(symbol)
            if df is not None:
                last_bar = len(df) - 1
                self._close_position(symbol, df, last_bar, "END_OF_DATA")

        return self._generate_report()

    def _check_signal(self, symbol: str, df: pd.DataFrame, bar: int):
        """Genera señal y abre posición si corresponde."""
        window = df.iloc[:bar + 1].copy()
        if len(window) < 50:
            return

        signal = None
        direction = None
        sl_price = None
        signal_price = None
        atr_val = 0.0

        if self.cfg.strategy == "ema_breakout":
            sig = compute_signals(window)
            atr_val = sig.get("atr", 0)
            if sig["trend"] == "BULL" and sig["breakout_long"] and sig["adx"] >= self.cfg.adx_min:
                signal = sig
                direction = "LONG"
                entry_price = float(df.iloc[bar]["close"])
                signal_price = sig.get("signal_price", entry_price)
                sl_price = build_initial_sl("LONG", window, atr_val)
            elif sig["trend"] == "BEAR" and sig["breakout_short"] and sig["adx"] >= self.cfg.adx_min:
                signal = sig
                direction = "SHORT"
                entry_price = float(df.iloc[bar]["close"])
                signal_price = sig.get("signal_price", entry_price)
                sl_price = build_initial_sl("SHORT", window, atr_val)
            else:
                entry_price = 0.0

        elif self.cfg.strategy == "stop_hunt":
            sig = compute_stop_hunt_signals(window)
            atr_val = sig.get("atr", 0)
            if sig.get("breakout_long"):
                signal = sig
                direction = "LONG"
                entry_price = float(df.iloc[bar]["close"])
                signal_price = sig.get("signal_price", entry_price)
                sl_price = build_stop_hunt_sl(window, "LONG", signal_price)
            elif sig.get("breakout_short"):
                signal = sig
                direction = "SHORT"
                entry_price = float(df.iloc[bar]["close"])
                signal_price = sig.get("signal_price", entry_price)
                sl_price = build_stop_hunt_sl(window, "SHORT", signal_price)
            else:
                entry_price = 0.0

        elif self.cfg.strategy == "vwap_refresh":
            try:
                sig = compute_vwap_refresh_signals(window)
                atr_val = sig.get("atr", 0)
                if sig.get("refresh_long"):
                    signal = sig
                    direction = "LONG"
                    entry_price = float(df.iloc[bar]["close"])
                    signal_price = sig.get("signal_price", entry_price)
                    sl_price = build_vwap_refresh_sl(window, "LONG", signal_price)
                elif sig.get("refresh_short"):
                    signal = sig
                    direction = "SHORT"
                    entry_price = float(df.iloc[bar]["close"])
                    signal_price = sig.get("signal_price", entry_price)
                    sl_price = build_vwap_refresh_sl(window, "SHORT", signal_price)
                else:
                    entry_price = 0.0
            except Exception:
                entry_price = 0.0

        elif self.cfg.strategy == "rsi_bb_reversion":
            sig = compute_rsi_bb_signals(window)
            atr_val = sig.get("atr", 0)
            if sig.get("breakout_long"):
                signal = sig
                direction = "LONG"
                entry_price = float(df.iloc[bar]["close"])
                signal_price = sig.get("signal_price", entry_price)
                sl_price = build_rsi_bb_sl(window, "LONG", signal_price)
            elif sig.get("breakout_short"):
                signal = sig
                direction = "SHORT"
                entry_price = float(df.iloc[bar]["close"])
                signal_price = sig.get("signal_price", entry_price)
                sl_price = build_rsi_bb_sl(window, "SHORT", signal_price)
            else:
                entry_price = 0.0
        else:
            entry_price = 0.0

        if signal is None or direction is None or sl_price is None:
            return

        if entry_price <= 0 or atr_val <= 0 or sl_price <= 0:
            return

        # Calcular qty basado en riesgo (entry_price = close real)
        stop_distance = abs(entry_price - sl_price)
        if stop_distance <= 0:
            return

        risk_usdt = self.equity * (self.cfg.risk_pct / 100.0)
        notional = risk_usdt * self.cfg.leverage
        qty = notional / entry_price

        # Verificar SL mínimo
        sl_pct = stop_distance / entry_price * 100
        if sl_pct < self.cfg.min_initial_sl_pct:
            sl_price = entry_price * (1 - self.cfg.min_initial_sl_pct / 100) if direction == "LONG" else entry_price * (1 + self.cfg.min_initial_sl_pct / 100)
            stop_distance = abs(entry_price - sl_price)
            qty = (self.equity * (self.cfg.risk_pct / 100.0)) * self.cfg.leverage / entry_price

        # Comisión de entrada
        commission = entry_price * qty * (self.cfg.commission_pct / 100)
        self.equity -= commission

        # Abrir posición
        pos = SimPosition(
            symbol=symbol,
            side=direction,
            entry_price=entry_price,
            qty=qty,
            entry_bar=bar,
            initial_sl=sl_price,
            current_sl=sl_price,
        )
        self.positions[symbol] = pos

    def _update_position(self, symbol: str, df: pd.DataFrame, bar: int):
        """Actualiza trailing, TP y SL de una posición."""
        pos = self.positions.get(symbol)
        if pos is None:
            return

        row = df.iloc[bar]
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])

        is_long = pos.side == "LONG"

        # 1. Verificar SL (usar high/low de la vela, no solo close)
        if is_long and low <= pos.current_sl:
            self._close_position(symbol, df, bar, "STOP_LOSS" if not pos.trailing_activated else "TRAILING", exit_price=pos.current_sl)
            return
        elif not is_long and high >= pos.current_sl:
            self._close_position(symbol, df, bar, "STOP_LOSS" if not pos.trailing_activated else "TRAILING", exit_price=pos.current_sl)
            return

        # 2. Verificar TP por porcentaje
        if self.cfg.use_take_profit and self.cfg.tp_by_pct and not pos.tp_executed:
            if is_long:
                profit_pct = (close - pos.entry_price) / pos.entry_price * 100
            else:
                profit_pct = (pos.entry_price - close) / pos.entry_price * 100

            if profit_pct >= self.cfg.tp_activation_pct:
                # Cerrar porcentaje parcial
                close_qty = pos.qty * (self.cfg.tp_close_pct / 100)
                remaining_qty = pos.qty - close_qty
                if remaining_qty > 0:
                    # Cerrar parcial
                    pnl = (close - pos.entry_price) * close_qty if is_long else (pos.entry_price - close) * close_qty
                    commission = close * close_qty * (self.cfg.commission_pct / 100)
                    self.equity += pnl - commission
                    self.trades.append(Trade(
                        symbol=symbol, side=pos.side,
                        entry_price=pos.entry_price, exit_price=close,
                        qty=close_qty, entry_bar=pos.entry_bar, exit_bar=bar,
                        pnl_usdt=pnl - commission,
                        pnl_pct=(pnl / (pos.entry_price * close_qty)) * 100,
                        commission=commission,
                        exit_reason="TAKE_PROFIT"
                    ))
                    pos.qty = remaining_qty
                    pos.tp_executed = True
                else:
                    self._close_position(symbol, df, bar, "TAKE_PROFIT", exit_price=close)
                    return

        # 3. Actualizar trailing
        if is_long:
            pnl_pct = (close - pos.entry_price) / pos.entry_price * 100
            pos.best_price = max(pos.best_price, high)
        else:
            pnl_pct = (pos.entry_price - close) / pos.entry_price * 100
            pos.best_price = min(pos.best_price, low)

        if pnl_pct >= self.cfg.trailing_activation_pct:
            if not pos.trailing_activated:
                pos.trailing_activated = True

            # Calcular nuevo SL
            df_window = df.iloc[:bar + 1]
            atr_series = atr(df_window, CFG.ATR_PERIOD)
            atr_val = float(atr_series.iloc[-1]) if len(atr_series) > 0 else 0

            if is_long:
                if self.cfg.trailing_use_atr and atr_val > 0:
                    new_sl = pos.best_price - (atr_val * self.cfg.trailing_atr_mult)
                else:
                    new_sl = pos.best_price * (1 - self.cfg.trailing_pct / 100)
                new_sl = max(new_sl, pos.entry_price)  # Nunca debajo del entry
                # Solo mejorar
                if new_sl > pos.current_sl:
                    pos.current_sl = new_sl
            else:
                if self.cfg.trailing_use_atr and atr_val > 0:
                    new_sl = pos.best_price + (atr_val * self.cfg.trailing_atr_mult)
                else:
                    new_sl = pos.best_price * (1 + self.cfg.trailing_pct / 100)
                new_sl = min(new_sl, pos.entry_price)  # Nunca arriba del entry
                # Solo mejorar
                if new_sl < pos.current_sl:
                    pos.current_sl = new_sl

    def _close_position(self, symbol: str, df: pd.DataFrame, bar: int, reason: str, exit_price: float = None):
        """Cierra una posición completamente."""
        pos = self.positions.get(symbol)
        if pos is None:
            return

        if exit_price is None:
            exit_price = float(df.iloc[bar]["close"])

        is_long = pos.side == "LONG"
        pnl = (exit_price - pos.entry_price) * pos.qty if is_long else (pos.entry_price - exit_price) * pos.qty
        commission = exit_price * pos.qty * (self.cfg.commission_pct / 100)
        net_pnl = pnl - commission

        self.equity += net_pnl
        self.peak_equity = max(self.peak_equity, self.equity)

        pnl_pct = (pnl / (pos.entry_price * pos.qty)) * 100

        self.trades.append(Trade(
            symbol=symbol,
            side=pos.side,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            qty=pos.qty,
            entry_bar=pos.entry_bar,
            exit_bar=bar,
            pnl_usdt=net_pnl,
            pnl_pct=pnl_pct,
            commission=commission,
            exit_reason=reason,
        ))

        # Cooldown
        self.cooldown[symbol] = bar + self.cfg.cooldown_bars

        del self.positions[symbol]

    def _generate_report(self) -> dict:
        """Genera reporte de performance."""
        if not self.trades:
            print("\n⚠️ No se realizaron trades.")
            return {"trades": 0}

        wins = [t for t in self.trades if t.pnl_usdt > 0]
        losses = [t for t in self.trades if t.pnl_usdt <= 0]

        total_pnl = sum(t.pnl_usdt for t in self.trades)
        total_commission = sum(t.commission for t in self.trades)
        win_rate = len(wins) / len(self.trades) * 100 if self.trades else 0

        avg_win = np.mean([t.pnl_usdt for t in wins]) if wins else 0
        avg_loss = np.mean([abs(t.pnl_usdt) for t in losses]) if losses else 0
        profit_factor = sum(t.pnl_usdt for t in wins) / abs(sum(t.pnl_usdt for t in losses)) if losses and sum(t.pnl_usdt for t in losses) != 0 else float("inf")

        # Max drawdown
        peak = self.equity_curve[0]
        max_dd = 0
        max_dd_pct = 0
        for eq in self.equity_curve:
            if eq > peak:
                peak = eq
            dd = peak - eq
            dd_pct = (dd / peak) * 100
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct

        # Rachas
        max_win_streak = 0
        max_loss_streak = 0
        curr_ws = 0
        curr_ls = 0
        for t in self.trades:
            if t.pnl_usdt > 0:
                curr_ws += 1
                curr_ls = 0
                max_win_streak = max(max_win_streak, curr_ws)
            else:
                curr_ls += 1
                curr_ws = 0
                max_loss_streak = max(max_loss_streak, curr_ls)

        # Sharpe (simplificado, por trade)
        returns = [t.pnl_pct for t in self.trades]
        sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(len(returns)) if np.std(returns) > 0 and len(returns) > 1 else 0

        # Recovery factor
        recovery_factor = total_pnl / max_dd if max_dd > 0 else float("inf")

        # Duración promedio
        bars_per_trade = np.mean([t.exit_bar - t.entry_bar for t in self.trades])

        # Por razón de salida
        exit_reasons = {}
        for t in self.trades:
            exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1

        # Por símbolo
        by_symbol = {}
        for t in self.trades:
            if t.symbol not in by_symbol:
                by_symbol[t.symbol] = {"trades": 0, "pnl": 0, "wins": 0}
            by_symbol[t.symbol]["trades"] += 1
            by_symbol[t.symbol]["pnl"] += t.pnl_usdt
            if t.pnl_usdt > 0:
                by_symbol[t.symbol]["wins"] += 1

        result = {
            "strategy": self.cfg.strategy,
            "total_trades": len(self.trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 4),
            "total_commission": round(total_commission, 4),
            "net_pnl": round(total_pnl, 4),
            "pnl_pct": round(total_pnl / self.cfg.initial_capital * 100, 2),
            "avg_win": round(avg_win, 4),
            "avg_loss": round(avg_loss, 4),
            "profit_factor": round(profit_factor, 2),
            "expectancy": round(np.mean(returns), 4),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown_usdt": round(max_dd, 4),
            "max_drawdown_pct": round(max_dd_pct, 2),
            "recovery_factor": round(recovery_factor, 2),
            "max_win_streak": max_win_streak,
            "max_loss_streak": max_loss_streak,
            "avg_bars_per_trade": round(bars_per_trade, 1),
            "final_equity": round(self.equity, 2),
            "return_pct": round((self.equity - self.cfg.initial_capital) / self.cfg.initial_capital * 100, 2),
            "exit_reasons": exit_reasons,
            "by_symbol": {k: {kk: round(vv, 4) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in by_symbol.items()},
        }

        self._print_report(result)
        return result

    def _print_report(self, r: dict):
        """Imprime reporte formateado."""
        print(f"\n{'='*60}")
        print(f"RESULTADOS: {r['strategy'].upper()}")
        print(f"{'='*60}")
        print(f"  Trades:        {r['total_trades']}")
        print(f"  Wins/Losses:   {r['wins']}/{r['losses']}")
        print(f"  Win Rate:      {r['win_rate']}%")
        print(f"  Profit Factor: {r['profit_factor']}")
        print(f"  Expectancy:    {r['expectancy']:.4f}% por trade")
        print(f"  Sharpe:        {r['sharpe_ratio']}")
        print(f"{'─'*60}")
        print(f"  PnL Total:     ${r['total_pnl']:.2f} ({r['pnl_pct']:+.2f}%)")
        print(f"  Comisiones:    ${r['total_commission']:.2f}")
        print(f"  Capital Final: ${r['final_equity']:.2f} (de ${self.cfg.initial_capital:.2f})")
        print(f"  Return:        {r['return_pct']:+.2f}%")
        print(f"{'─'*60}")
        print(f"  Avg Win:       ${r['avg_win']:.4f}")
        print(f"  Avg Loss:      ${r['avg_loss']:.4f}")
        print(f"  Max DD:        ${r['max_drawdown_usdt']:.2f} ({r['max_drawdown_pct']:.2f}%)")
        print(f"  Recovery:      {r['recovery_factor']:.2f}")
        print(f"  Max Win Streak:  {r['max_win_streak']}")
        print(f"  Max Loss Streak: {r['max_loss_streak']}")
        print(f"  Avg Bars/Trade:  {r['avg_bars_per_trade']}")
        print(f"{'─'*60}")

        print(f"\n  Por razón de salida:")
        for reason, count in r["exit_reasons"].items():
            print(f"    {reason}: {count}")

        print(f"\n  Por símbolo:")
        for sym, data in r["by_symbol"].items():
            wr = (data["wins"] / data["trades"] * 100) if data["trades"] > 0 else 0
            print(f"    {sym}: {data['trades']} trades | ${data['pnl']:.2f} | WR {wr:.0f}%")

        print(f"\n{'='*60}\n")


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Backtest Beast Money Maker")
    parser.add_argument("--symbol", type=str, help="Símbolo único (ej: BTCUSDT)")
    parser.add_argument("--symbols", type=str, help="Símbolos separados por coma (ej: ETHUSDT,BNBUSDT)")
    parser.add_argument("--strategy", type=str, default="ema_breakout",
                        choices=["ema_breakout", "stop_hunt", "vwap_refresh", "rsi_bb_reversion"],
                        help="Estrategia a testear")
    parser.add_argument("--days", type=int, default=90, help="Días de historia")
    parser.add_argument("--capital", type=float, default=170.0, help="Capital inicial")
    parser.add_argument("--interval", type=str, default=CFG.INTERVAL, help="Timeframe")
    parser.add_argument("--leverage", type=int, default=CFG.DEFAULT_LEVERAGE, help="Apalancamiento")
    parser.add_argument("--risk", type=float, default=CFG.DEFAULT_RISK_PCT, help="Riesgo porcentual por trade")
    parser.add_argument("--all", action="store_true", help="Probar las 3 estrategias y comparar")
    parser.add_argument("--output", type=str, help="Guardar resultados en JSON")

    args = parser.parse_args()

    # Configurar símbolos
    if args.symbol:
        symbols = [args.symbol.upper()]
    elif args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",")]
    else:
        symbols = CFG.SYMBOLS.copy()

    # Descargar datos
    print(f"\n📥 Descargando datos ({args.days}d, {args.interval})...\n")
    data = {}
    for sym in symbols:
        try:
            df = fetch_klines(sym, args.interval, args.days)
            if len(df) >= 100:
                data[sym] = df
            else:
                print(f"  ⚠️ {sym}: solo {len(df)} velas, saltando")
        except Exception as e:
            print(f"  ❌ {sym}: {e}")

    if not data:
        print("❌ No hay datos suficientes.")
        sys.exit(1)

    # Configuración base
    base_config = BacktestConfig(
        symbols=list(data.keys()),
        interval=args.interval,
        days=args.days,
        initial_capital=args.capital,
        leverage=args.leverage,
        risk_pct=args.risk,
    )

    results = []

    if args.all:
        # Probar las 4 estrategias
        for strategy in ["ema_breakout", "stop_hunt", "vwap_refresh", "rsi_bb_reversion"]:
            cfg = BacktestConfig(**{**base_config.__dict__, "strategy": strategy})
            engine = BacktestEngine(cfg)
            result = engine.run(data)
            results.append(result)
    else:
        # Probar solo la estrategia especificada
        base_config.strategy = args.strategy
        engine = BacktestEngine(base_config)
        result = engine.run(data)
        results.append(result)

    # Comparación si hay múltiples estrategias
    if len(results) > 1:
        print(f"\n{'='*60}")
        print("COMPARACIÓN DE ESTRATEGIAS")
        print(f"{'='*60}")
        print(f"{'Estrategia':<18} {'Trades':>7} {'WR%':>6} {'PnL$':>10} {'PF':>6} {'MaxDD%':>7} {'Return%':>8}")
        print(f"{'─'*60}")
        for r in results:
            if r.get("trades", 0) == 0:
                continue
            print(f"{r['strategy']:<18} {r['total_trades']:>7} {r['win_rate']:>5.1f}% {r['total_pnl']:>10.2f} {r['profit_factor']:>6.2f} {r['max_drawdown_pct']:>6.2f}% {r['return_pct']:>+7.2f}%")
        print(f"{'='*60}\n")

    # Guardar resultados
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"💾 Resultados guardados en {args.output}")

    # Guardar trades detallados
    for r in results:
        if r.get("trades", 0) == 0:
            continue
        csv_name = f"backtest_trades_{r['strategy']}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        engine_trades = [t for t in engine.trades] if not args.all else []
        # Nota: para --all, necesitaríamos guardar los engines por separado


if __name__ == "__main__":
    main()
