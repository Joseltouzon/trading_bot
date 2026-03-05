# scripts/fix_historical_pnl_v3.2.py
from db import Database
from exchange.binance_futures import BinanceFutures
import os
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict

load_dotenv()

# ================= CONFIG =================
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
DAY_START_HOUR_ARG = int(os.getenv("DAY_START_HOUR_ARG", 21))

# ================= INIT =================
db = Database()

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

exchange = BinanceFutures(
    api_key=API_KEY,
    api_secret=API_SECRET,
    logger=logger,
    testnet=False
)

# ================= HELPERS =================

def calculate_expected_pnl(side: str, entry: float, exit: float, qty: float) -> float:
    """Calcula PnL teórico para comparar con Binance"""
    if side == "LONG":
        return (exit - entry) * qty
    else:
        return (entry - exit) * qty

def get_trades_for_commission(exchange, symbol: str, open_time_ms: int, close_time_ms: int) -> float:
    """
    Obtiene la comisión total de los trades de cierre desde Binance.
    """
    try:
        # Ventana estrecha: ±5 minutos del cierre
        start_ms = close_time_ms - (5 * 60 * 1000)
        end_ms = close_time_ms + (5 * 60 * 1000)
        
        trades = exchange.client.futures_account_trades(
            symbol=symbol,
            startTime=start_ms,
            endTime=end_ms,
            limit=100
        )
        
        total_commission = 0.0
        for t in trades:
            # Solo sumar comisiones de trades de cierre (realizedPnl != 0)
            if float(t.get("realizedPnl", 0) or 0) != 0:
                commission = float(t.get("commission", 0) or 0)
                total_commission += commission
        
        return total_commission
        
    except Exception as e:
        logger.warning(f"[COMMISSION] Error fetching for {symbol}: {e}")
        return 0.0

def match_income_record(incomes: List[Dict], target: Dict) -> Optional[Dict]:
    """
    Matchea un income record de Binance con una posición de la DB.
    """
    symbol = target["symbol"]
    side = target["side"]
    entry_price = float(target["entry_price"])
    exit_price = float(target["exit_price"])
    qty = float(target["qty"])
    closed_at = target["closed_at"]
    
    close_time_ms = int(closed_at.timestamp() * 1000)
    expected_pnl = calculate_expected_pnl(side, entry_price, exit_price, qty)
    
    best_match = None
    best_score = 0
    
    for inc in incomes:
        score = 0
        
        if inc.get("symbol") != symbol:
            continue
        
        inc_time = int(inc["time"])
        time_diff = abs(inc_time - close_time_ms)
        if time_diff > 5 * 60 * 1000:
            continue
        score += 30 - min(time_diff / 10000, 30)
        
        inc_pnl = float(inc.get("income", 0) or 0)
        if expected_pnl != 0:
            pnl_diff_pct = abs(inc_pnl - expected_pnl) / abs(expected_pnl) * 100
            if pnl_diff_pct <= 15:
                score += 40 - pnl_diff_pct * 1.5
        else:
            if abs(inc_pnl) < 0.01:
                score += 40
        
        if (inc_pnl > 0) == (expected_pnl > 0):
            score += 20
        
        if inc.get("incomeType") == "REALIZED_PNL":
            score += 10
        
        if score > best_score:
            best_score = score
            best_match = inc
    
    return best_match if best_score >= 70 else None

# ================= FIX =================
print("🔧 Iniciando fix de PnL histórico (V3.2 - + Comisiones)...")
print(f"⚠️  Día de trading: {DAY_START_HOUR_ARG}:00 Argentina (UTC-3)")
print("⚠️  Esto puede tardar si tenés muchos trades")
print()

trades = db.get_recent_closed_positions(limit=None)
print(f"📊 Trades encontrados: {len(trades)}")
print()

fixed_count = 0
error_count = 0
no_match_count = 0
dry_run = False  # ← CAMBIAR A False para aplicar cambios reales

for i, trade in enumerate(trades, 1):
    try:
        symbol = trade["symbol"]
        side = trade["side"]
        entry_price = float(trade["entry_price"])
        exit_price = float(trade["exit_price"])
        qty = float(trade["qty"])
        closed_at = trade["closed_at"]
        old_pnl = float(trade["realized_pnl"] or 0)
        
        close_time_ms = int(closed_at.timestamp() * 1000)
        
        # ✅ Ventana estrecha: ±5 minutos del cierre
        start_ms = close_time_ms - (5 * 60 * 1000)
        end_ms = close_time_ms + (5 * 60 * 1000)
        
        income = exchange.client.futures_income_history(
            symbol=symbol,
            incomeType="REALIZED_PNL",
            startTime=start_ms,
            endTime=end_ms,
            limit=100
        )
        
        if not income:
            print(f"⚠️  [{i}/{len(trades)}] {symbol}: No income records en ventana ±5min")
            no_match_count += 1
            continue
        
        # ✅ Matching con múltiples criterios
        matched = match_income_record(income, {
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "qty": qty,
            "closed_at": closed_at
        })
        
        if not matched:
            print(f"⚠️  [{i}/{len(trades)}] {symbol}: No match (score < 70)")
            print(f"     Expected: {calculate_expected_pnl(side, entry_price, exit_price, qty):+.2f}")
            print(f"     Records: {len(income)}")
            no_match_count += 1
            continue
        
        # ✅ Obtener PnL y comisión
        realized_pnl = float(matched.get("income", 0) or 0)
        
        # Intentar obtener comisión del income record (algunos endpoints la incluyen)
        commission = float(matched.get("commission", 0) or 0)
        
        # Si no vino comisión, buscarla en los trades de cierre
        if commission == 0:
            commission = get_trades_for_commission(exchange, symbol, close_time_ms - (5*60*1000), close_time_ms)
        
        # Calcular comisión como porcentaje del notional
        notional = entry_price * qty
        commission_pct = (commission / notional * 100) if notional > 0 else 0
        
        # Validación final: no permitir cambios absurdos
        expected = calculate_expected_pnl(side, entry_price, exit_price, qty)
        if abs(realized_pnl - expected) > abs(expected) * 0.5 and abs(expected) > 1:
            print(f"⚠️  [{i}/{len(trades)}] {symbol}: Diferencia grande, saltando")
            error_count += 1
            continue
        
        # Actualizar DB (solo si no es dry-run)
        if not dry_run:
            with db.cursor() as cur:
                cur.execute("""
                    UPDATE positions
                    SET realized_pnl = %s,
                        commission = %s,
                        commission_pct = %s
                    WHERE id = %s
                """, (realized_pnl, commission, commission_pct, trade["id"]))
        
        diff = realized_pnl - old_pnl
        mode = "🔍 DRY-RUN" if dry_run else "✅ FIXED"
        print(f"{mode} [{i}/{len(trades)}] {symbol}: "
              f"PnL {old_pnl:+.2f} → {realized_pnl:+.2f} | "
              f"Commission: {commission:.4f} USDT ({commission_pct:.3f}%)")
        
        if not dry_run:
            fixed_count += 1
        
        # Rate limiting
        if i % 10 == 0:
            time.sleep(1)
        
    except Exception as e:
        print(f"❌ [{i}/{len(trades)}] {trade['symbol']}: Error - {str(e)[:80]}")
        error_count += 1
        
        if "-1101" in str(e) or "Too many requests" in str(e):
            print("   ⏳ Rate limit, esperando 60s...")
            time.sleep(60)

print()
print("=" * 70)
mode = "DRY-RUN (sin cambios)" if dry_run else "APLICADO"
print(f"✅ Fix completado - Modo: {mode}")
print(f"   - Trades corregidos: {fixed_count}")
print(f"   - Sin match: {no_match_count}")
print(f"   - Errores: {error_count}")
print("=" * 70)
if dry_run:
    print(f"💡 Para aplicar cambios reales: editá el script y poné: dry_run = False")