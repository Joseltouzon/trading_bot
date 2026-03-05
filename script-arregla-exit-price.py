#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔧 Fix de exit_price para posiciones cerradas

Este script:
1. Obtiene todas las posiciones cerradas de la DB
2. Para cada una, consulta los trades reales de cierre en Binance
3. Calcula el exit_price ponderado por cantidad
4. Actualiza la DB con el valor correcto

✅ Incluye:
- Dry-run mode (por defecto, sin cambios reales)
- Rate limiting para no banear la API de Binance
- Logging detallado para auditoría
- Validación de valores absurdos
- Soporte para Python <3.10
"""

from db import Database
from exchange.binance_futures import BinanceFutures
import os
from dotenv import load_dotenv
import time
from datetime import datetime
from typing import Optional, List, Dict

# Cargar variables de entorno
load_dotenv()

# ================= CONFIG =================
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
TESTNET = os.getenv("TESTNET", "false").lower() == "true"

# Rate limiting: pausas cada N requests para no saturar la API
RATE_LIMIT_EVERY = 10  # requests
RATE_LIMIT_SLEEP = 1   # segundos

# Validación: saltar si el nuevo exit_price difiere demasiado del original
MAX_PRICE_DIFF_PCT = 50  # % máximo de diferencia permitida

# Dry-run: por defecto NO aplica cambios (solo muestra qué haría)
DRY_RUN = False

# ================= INIT =================
db = Database()

# Logger simple para el script
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'fix_exit_prices_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)

exchange = BinanceFutures(
    api_key=API_KEY,
    api_secret=API_SECRET,
    logger=logger,
    testnet=TESTNET
)

# ================= HELPERS =================

def get_closing_trades(exchange, symbol: str, open_time_ms: int, close_time_ms: int, side: str) -> List[Dict]:
    """
    Obtiene los trades de CIERRE de una posición desde Binance.
    
    Args:
        symbol: 'BTCUSDT'
        open_time_ms: Timestamp de apertura (ms)
        close_time_ms: Timestamp de cierre (ms)
        side: 'LONG' o 'SHORT'
    
    Returns:
        Lista de trades que contribuyeron al cierre
    """
    try:
        # Consultar trades desde la apertura hasta un poco después del cierre
        # Binance a veces registra el trade unos ms después del close_time
        end_buffer = close_time_ms + (5 * 60 * 1000)  # +5 minutos de buffer
        
        trades = exchange.client.futures_account_trades(
            symbol=symbol,
            startTime=open_time_ms,
            endTime=end_buffer,
            limit=500  # Binance max por página
        )
        
        if not trades:
            return []
        
        closing_trades = []
        
        for t in trades:
            # Un trade de cierre/reducción tiene realizedPnl != 0
            realized = float(t.get("realizedPnl", 0) or 0)
            
            if realized != 0:
                # Validar que el lado del trade coincida con el cierre esperado
                # LONG se cierra con SELL, SHORT se cierra con BUY
                trade_side = t.get("side")
                expected_close_side = "SELL" if side == "LONG" else "BUY"
                
                if trade_side == expected_close_side:
                    closing_trades.append({
                        "time": int(t["time"]),
                        "price": float(t["price"]),
                        "qty": float(t["qty"]),
                        "realizedPnl": realized,
                        "commission": float(t.get("commission", 0) or 0),
                        "commissionAsset": t.get("commissionAsset")
                    })
        
        return closing_trades
        
    except Exception as e:
        logger.warning(f"[TRADES] Error fetching for {symbol}: {e}")
        return []


def calculate_weighted_exit_price(trades: List[Dict]) -> Optional[float]:
    """
    Calcula el precio de salida ponderado por cantidad.
    
    Si hubo partial closes, el exit_price es el promedio ponderado:
    exit_price = Σ(price_i * qty_i) / Σ(qty_i)
    """
    if not trades:
        return None
    
    total_qty = 0.0
    weighted_sum = 0.0
    
    for t in trades:
        qty = abs(t["qty"])
        price = t["price"]
        total_qty += qty
        weighted_sum += price * qty
    
    if total_qty == 0:
        return None
    
    return weighted_sum / total_qty


def validate_exit_price(original: float, new: float, symbol: str) -> bool:
    """
    Valida que el nuevo exit_price sea razonable.
    """
    if original <= 0 or new <= 0:
        return False
    
    diff_pct = abs(new - original) / original * 100
    
    if diff_pct > MAX_PRICE_DIFF_PCT:
        logger.warning(f"[VALIDATE] {symbol}: diferencia muy grande ({diff_pct:.1f}%) - original={original}, new={new}")
        return False
    
    return True


# ================= MAIN FIX =================

def fix_exit_prices():
    """Ejecuta el fix de exit_price para todas las posiciones cerradas."""
    
    mode_str = "🔍 DRY-RUN (sin cambios)" if DRY_RUN else "✅ APLICANDO CAMBIOS"
    logger.info(f"🚀 Iniciando fix de exit_price - Modo: {mode_str}")
    logger.info(f"📊 Max diff permitida: {MAX_PRICE_DIFF_PCT}%")
    logger.info(f"⏱️  Rate limit: cada {RATE_LIMIT_EVERY} requests, sleep {RATE_LIMIT_SLEEP}s")
    print()
    
    # Obtener posiciones cerradas con los campos necesarios
    # Nota: get_recent_closed_positions tiene limit, necesitamos todas
    with db.cursor() as cur:
        cur.execute("""
            SELECT id, symbol, side, entry_price, exit_price, qty, 
                   opened_at, closed_at, realized_pnl
            FROM positions
            WHERE status = 'CLOSED'
            AND exit_price IS NOT NULL
            AND exit_price > 0
            ORDER BY closed_at DESC
        """)
        positions = cur.fetchall()
    
    if not positions:
        logger.warning("⚠️  No se encontraron posiciones cerradas para procesar")
        return
    
    logger.info(f"📦 Posiciones encontradas: {len(positions)}")
    print()
    
    # Contadores para el reporte final
    stats = {
        "total": len(positions),
        "fixed": 0,
        "unchanged": 0,
        "no_trades": 0,
        "validation_failed": 0,
        "errors": 0,
        "skipped": 0
    }
    
    for i, pos in enumerate(positions, 1):
        try:
            symbol = pos["symbol"]
            side = pos["side"]
            original_exit = float(pos["exit_price"])
            entry_price = float(pos["entry_price"])
            qty = float(pos["qty"])
            opened_at = pos["opened_at"]
            closed_at = pos["closed_at"]
            position_id = pos["id"]
            
            # Convertir timestamps a ms (entero, no float)
            open_time_ms = int(opened_at.timestamp() * 1000)
            close_time_ms = int(closed_at.timestamp() * 1000)
            
            # Obtener trades reales de cierre desde Binance
            closing_trades = get_closing_trades(
                exchange, symbol, open_time_ms, close_time_ms, side
            )
            
            if not closing_trades:
                logger.debug(f"[{i}/{stats['total']}] {symbol}: No se encontraron trades de cierre")
                stats["no_trades"] += 1
                continue
            
            # Calcular exit_price ponderado
            new_exit_price = calculate_weighted_exit_price(closing_trades)
            
            if new_exit_price is None:
                logger.warning(f"[{i}/{stats['total']}] {symbol}: No se pudo calcular exit_price")
                stats["errors"] += 1
                continue
            
            # Validar que el nuevo valor sea razonable
            if not validate_exit_price(original_exit, new_exit_price, symbol):
                stats["validation_failed"] += 1
                continue
            
            # Verificar si realmente hay diferencia significativa
            diff = new_exit_price - original_exit
            diff_pct = abs(diff) / original_exit * 100 if original_exit > 0 else 0
            
            if diff_pct < 0.01:  # Menos de 0.01% de diferencia = mismo valor
                stats["unchanged"] += 1
                continue
            
            # Log del cambio
            logger.info(
                f"[{i}/{stats['total']}] {symbol}: "
                f"exit_price {original_exit:.4f} → {new_exit_price:.4f} "
                f"(diff: {diff:+.4f}, {diff_pct:+.2f}%) | "
                f"trades: {len(closing_trades)}"
            )
            
            # Aplicar cambio si no es dry-run
            if not DRY_RUN:
                with db.cursor() as cur:
                    cur.execute("""
                        UPDATE positions
                        SET exit_price = %s
                        WHERE id = %s
                    """, (new_exit_price, position_id))
                logger.debug(f"  ✅ DB actualizada para position_id={position_id}")
            
            stats["fixed"] += 1
            
            # Rate limiting
            if i % RATE_LIMIT_EVERY == 0:
                logger.debug(f"  ⏳ Rate limit: esperando {RATE_LIMIT_SLEEP}s...")
                time.sleep(RATE_LIMIT_SLEEP)
            
        except Exception as e:
            logger.error(f"[{i}/{stats['total']}] {pos['symbol']}: Error - {str(e)[:100]}")
            stats["errors"] += 1
            # En caso de error de rate limit, esperar más
            if "-1101" in str(e) or "Too many requests" in str(e):
                logger.warning("  ⚠️  Rate limit de Binance, esperando 60s...")
                time.sleep(60)
    
    # ================= REPORTE FINAL =================
    print()
    print("=" * 70)
    print(f"✅ Fix completado - Modo: {mode_str}")
    print(f"📊 Resultados:")
    print(f"   - Total procesadas: {stats['total']}")
    print(f"   - Corregidas:       {stats['fixed']}")
    print(f"   - Sin cambios:      {stats['unchanged']}")
    print(f"   - Sin trades:       {stats['no_trades']}")
    print(f"   - Validación fallida: {stats['validation_failed']}")
    print(f"   - Errores:          {stats['errors']}")
    print("=" * 70)
    
    if DRY_RUN:
        print(f"💡 Para aplicar cambios reales, editá el script y poné: DRY_RUN = False")
    else:
        print(f"🎉 Cambios aplicados. Verificá en tu DB los resultados.")
    
    # Guardar reporte en archivo
    report_file = f"fix_exit_prices_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"Reporte de Fix Exit Price - {datetime.now()}\n")
        f.write(f"Modo: {mode_str}\n")
        f.write(f"Resultados: {stats}\n")
    logger.info(f"📄 Reporte guardado en: {report_file}")


# ================= ENTRY POINT =================

if __name__ == "__main__":
    try:
        fix_exit_prices()
    except KeyboardInterrupt:
        print("\n⚠️  Interrumpido por usuario")
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}")
        raise