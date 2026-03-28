#!/usr/bin/env python3
"""Tests Stop Hunt - batches para ejecutar manualmente."""
import sys, os, time
sys.path.insert(0, '.')
import config as CFG
exec(open('bt_test_combos.py').read().split('def main')[0])

def base():
    CFG.STOP_HUNT_WICK_PCT=0.20; CFG.STOP_HUNT_REJECTION_RATIO=0.7
    CFG.STOP_HUNT_MIN_ZONES=2; CFG.STOP_HUNT_MAX_ZONE_DISTANCE_PCT=0.8
    CFG.STOP_HUNT_MIN_VOLUME_RATIO=1.5; CFG.STOP_HUNT_USE_EMA_FILTER=True
    CFG.STOP_HUNT_MIN_BREAK_CANDLES=2; CFG.STOP_HUNT_ATR_MULT_SL=2.0
    CFG.STOP_HUNT_MOMENTUM_BARS=3; CFG.STOP_HUNT_MIN_ATR_PCT=0.12
    CFG.STOP_HUNT_ADX_MIN=18

def run(label, syms, overrides=None):
    base()
    if adx is not None: CFG.ADX_MIN = adx
    if overrides:
        for k,v in overrides.items(): setattr(CFG,k,v)
    adx = CFG.STOP_HUNT_ADX_MIN
    r = run_test('stop_hunt', syms, '5m', adx_min=adx, trail_act=0.4, trail_pct=0.22)
    print(f'  {label:<45} T={r["trades"]:>3} W={r["wins"]:>2} WR={r["wr"]:>4.0f}% PF={r["pf"]:>5.2f} PnL=${r["pnl"]:>+8.2f}')
    return r

# === SÍMBOLOS ===
ACTUALES = ['1000PEPEUSDT','AVAXUSDT','ORDIUSDT','SUIUSDT','WIFUSDT']
NUEVOS_A = ['XRPUSDT','TIAUSDT','ETHUSDT','PENDLEUSDT','BTCUSDT']
NUEVOS_B = ['NEARUSDT','SOLUSDT','LINKUSDT','DOGEUSDT','FILUSDT']
MIX_A = ['1000PEPEUSDT','SUIUSDT','NEARUSDT','PENDLEUSDT','XRPUSDT']
MIX_B = ['AVAXUSDT','WIFUSDT','TIAUSDT','BTCUSDT','SOLUSDT']
MIX_C = ['ORDIUSDT','ETHUSDT','LINKUSDT','DOGEUSDT','FILUSDT']

batch = sys.argv[1] if len(sys.argv) > 1 else 'all'

if batch in ('1','all'):
    print(f'\n{"="*80}')
    print(f'  BATCH 1: Parámetros actuales + parámetros relajados')
    print(f'  Símbolos: {ACTUALES}')
    print(f'{"="*80}')
    run('BASE (actual)', ACTUALES)
    run('WICK 0.15', ACTUALES, {'STOP_HUNT_WICK_PCT':0.15})
    run('WICK 0.25', ACTUALES, {'STOP_HUNT_WICK_PCT':0.25})
    run('REJ 0.5', ACTUALES, {'STOP_HUNT_REJECTION_RATIO':0.5})
    run('REJ 0.6', ACTUALES, {'STOP_HUNT_REJECTION_RATIO':0.6})
    run('ZONES 1', ACTUALES, {'STOP_HUNT_MIN_ZONES':1})
    run('ZONES 3', ACTUALES, {'STOP_HUNT_MIN_ZONES':3})

if batch in ('2','all'):
    print(f'\n{"="*80}')
    print(f'  BATCH 2: Más parámetros')
    print(f'{"="*80}')
    run('ZONE_DIST 1.2', ACTUALES, {'STOP_HUNT_MAX_ZONE_DISTANCE_PCT':1.2})
    run('VOL 1.2', ACTUALES, {'STOP_HUNT_MIN_VOLUME_RATIO':1.2})
    run('VOL 2.0', ACTUALES, {'STOP_HUNT_MIN_VOLUME_RATIO':2.0})
    run('EMA OFF', ACTUALES, {'STOP_HUNT_USE_EMA_FILTER':False})
    run('BREAK 1', ACTUALES, {'STOP_HUNT_MIN_BREAK_CANDLES':1})
    run('BREAK 3', ACTUALES, {'STOP_HUNT_MIN_BREAK_CANDLES':3})

if batch in ('3','all'):
    print(f'\n{"="*80}')
    print(f'  BATCH 3: SL, momentum, ATR, ADX')
    print(f'{"="*80}')
    run('ATR_SL 1.5', ACTUALES, {'STOP_HUNT_ATR_MULT_SL':1.5})
    run('ATR_SL 2.5', ACTUALES, {'STOP_HUNT_ATR_MULT_SL':2.5})
    run('MOM 2', ACTUALES, {'STOP_HUNT_MOMENTUM_BARS':2})
    run('MOM 4', ACTUALES, {'STOP_HUNT_MOMENTUM_BARS':4})
    run('ATR_PCT 0.08', ACTUALES, {'STOP_HUNT_MIN_ATR_PCT':0.08})
    run('ADX 14', ACTUALES, {'STOP_HUNT_ADX_MIN':14})

if batch in ('4','all'):
    print(f'\n{"="*80}')
    print(f'  BATCH 4: Combinaciones relajadas')
    print(f'{"="*80}')
    run('ZONES1+VOL1.2', ACTUALES, {'STOP_HUNT_MIN_ZONES':1,'STOP_HUNT_MIN_VOLUME_RATIO':1.2})
    run('ZONES1+ADX14', ACTUALES, {'STOP_HUNT_MIN_ZONES':1,'STOP_HUNT_ADX_MIN':14})
    run('WICK15+REJ5', ACTUALES, {'STOP_HUNT_WICK_PCT':0.15,'STOP_HUNT_REJECTION_RATIO':0.5})
    run('EMA_OFF+ADX14', ACTUALES, {'STOP_HUNT_USE_EMA_FILTER':False,'STOP_HUNT_ADX_MIN':14})
    run('TODO RELAJADO', ACTUALES, {'STOP_HUNT_WICK_PCT':0.15,'STOP_HUNT_REJECTION_RATIO':0.5,
        'STOP_HUNT_MIN_ZONES':1,'STOP_HUNT_MIN_VOLUME_RATIO':1.2,'STOP_HUNT_ADX_MIN':14,
        'STOP_HUNT_USE_EMA_FILTER':False})

if batch in ('5','all'):
    print(f'\n{"="*80}')
    print(f'  BATCH 5: Nuevos símbolos A')
    print(f'{"="*80}')
    run('NUEVOS_A base', NUEVOS_A)
    run('NUEVOS_A ZONES1', NUEVOS_A, {'STOP_HUNT_MIN_ZONES':1})
    run('NUEVOS_A ADX14', NUEVOS_A, {'STOP_HUNT_ADX_MIN':14})
    run('NUEVOS_A EMA_OFF', NUEVOS_A, {'STOP_HUNT_USE_EMA_FILTER':False})
    run('NUEVOS_A RELAJADO', NUEVOS_A, {'STOP_HUNT_WICK_PCT':0.15,'STOP_HUNT_REJECTION_RATIO':0.5,
        'STOP_HUNT_MIN_ZONES':1,'STOP_HUNT_MIN_VOLUME_RATIO':1.2,'STOP_HUNT_ADX_MIN':14,
        'STOP_HUNT_USE_EMA_FILTER':False})

if batch in ('6','all'):
    print(f'\n{"="*80}')
    print(f'  BATCH 6: Nuevos símbolos B')
    print(f'{"="*80}')
    run('NUEVOS_B base', NUEVOS_B)
    run('NUEVOS_B ZONES1', NUEVOS_B, {'STOP_HUNT_MIN_ZONES':1})
    run('NUEVOS_B ADX14', NUEVOS_B, {'STOP_HUNT_ADX_MIN':14})
    run('NUEVOS_B EMA_OFF', NUEVOS_B, {'STOP_HUNT_USE_EMA_FILTER':False})
    run('NUEVOS_B RELAJADO', NUEVOS_B, {'STOP_HUNT_WICK_PCT':0.15,'STOP_HUNT_REJECTION_RATIO':0.5,
        'STOP_HUNT_MIN_ZONES':1,'STOP_HUNT_MIN_VOLUME_RATIO':1.2,'STOP_HUNT_ADX_MIN':14,
        'STOP_HUNT_USE_EMA_FILTER':False})

if batch in ('7','all'):
    print(f'\n{"="*80}')
    print(f'  BATCH 7: Mix de símbolos')
    print(f'{"="*80}')
    run('MIX_A base', MIX_A)
    run('MIX_A RELAJADO', MIX_A, {'STOP_HUNT_MIN_ZONES':1,'STOP_HUNT_MIN_VOLUME_RATIO':1.2,
        'STOP_HUNT_ADX_MIN':14,'STOP_HUNT_USE_EMA_FILTER':False})
    run('MIX_B base', MIX_B)
    run('MIX_B RELAJADO', MIX_B, {'STOP_HUNT_MIN_ZONES':1,'STOP_HUNT_MIN_VOLUME_RATIO':1.2,
        'STOP_HUNT_ADX_MIN':14,'STOP_HUNT_USE_EMA_FILTER':False})
    run('MIX_C base', MIX_C)
    run('MIX_C RELAJADO', MIX_C, {'STOP_HUNT_MIN_ZONES':1,'STOP_HUNT_MIN_VOLUME_RATIO':1.2,
        'STOP_HUNT_ADX_MIN':14,'STOP_HUNT_USE_EMA_FILTER':False})

if batch in ('8','all'):
    print(f'\n{"="*80}')
    print(f'  BATCH 8: Top combos con mejor config encontrada')
    print(f'{"="*80}')
    # Probar las mejores configs con diferentes grupos de 5
    best_overrides = {'STOP_HUNT_MIN_ZONES':1,'STOP_HUNT_MIN_VOLUME_RATIO':1.2,
        'STOP_HUNT_ADX_MIN':14,'STOP_HUNT_USE_EMA_FILTER':False}
    run('BEST + ACTUALES', ACTUALES, best_overrides)
    run('BEST + NUEVOS_A', NUEVOS_A, best_overrides)
    run('BEST + NUEVOS_B', NUEVOS_B, best_overrides)
    run('BEST + MIX_A', MIX_A, best_overrides)
    run('BEST + MIX_B', MIX_B, best_overrides)

print(f'\n{"="*80}')
print(f'  FIN STOP HUNT')
print(f'  Uso: ./venv/bin/python bt_sh_batches.py [1-8]')
print(f'{"="*80}')
