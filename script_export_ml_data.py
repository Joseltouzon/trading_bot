#!/usr/bin/env python3
# export_ml_data.py
"""
Exporta datos de posiciones cerradas con features para entrenar modelo ML.
"""
import pandas as pd
import json
from db import Database

def export_training_data(output_file: str = "ml_training_data.csv"):
    db = Database()
    
    with db.cursor() as cur:
        cur.execute("""
            SELECT 
                p.id,
                p.symbol,
                p.side,
                p.entry_price,
                p.exit_price,
                p.realized_pnl,
                p.signal_features,
                p.opened_at,
                p.closed_at,
                EXTRACT(EPOCH FROM (p.closed_at - p.opened_at))/60 as hold_minutes
            FROM positions p
            WHERE p.status = 'CLOSED'
            AND p.signal_features IS NOT NULL
            ORDER BY p.opened_at DESC
        """)
        rows = cur.fetchall()
    
    # Convertir a DataFrame
    data = []
    for row in rows:
        features = json.loads(row["signal_features"]) if row["signal_features"] else {}
        
        # Target binario: ¿fue ganadora la operación?
        pnl = float(row["realized_pnl"] or 0)
        is_winner = 1 if pnl > 0 else 0
        
        # Crear fila combinando features + metadata + target
        record = {
            "position_id": row["id"],
            "symbol": row["symbol"],
            "side": row["side"],
            "pnl_usdt": pnl,
            "is_winner": is_winner,
            "hold_minutes": float(row["hold_minutes"] or 0),
            **{f"feat_{k}": v for k, v in features.items() if k != "symbol"}  # Prefijo para claridad
        }
        data.append(record)
    
    df = pd.DataFrame(data)
    
    if len(df) > 0:
        df.to_csv(output_file, index=False)
        print(f"✅ Exportados {len(df)} registros a {output_file}")
        print(f"📊 Win rate: {(df['is_winner'].mean()*100):.1f}%")
        print(f"📈 PnL promedio: ${df['pnl_usdt'].mean():.2f}")
    else:
        print("⚠️ No hay datos suficientes aún. Seguí operando para recolectar más señales.")
    
    return df

if __name__ == "__main__":
    export_training_data()