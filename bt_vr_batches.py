#!/usr/bin/env python3
"""Tests Volatility Regime - batches."""
import sys; sys.path.insert(0,'.')
import config as CFG
exec(open('bt_test_combos.py').read().split('def main')[0])

def base():
    CFG.VR_ATR_LOW_PERCENTILE=25; CFG.VR_ATR_HIGH_PERCENTILE=75
    CFG.VR_VOLUME_RATIO_MIN=1.5; CFG.VR_ADX_MIN=22
    CFG.VR_SL_ATR_MULT=1.5; CFG.VR_EMA_FAST=20; CFG.VR_EMA_SLOW=50
    CFG.VR_MOMENTUM_BARS=4; CFG.VR_BREAKOUT_LOOKBACK=20

def run(label, syms, overrides=None, adx=None):
    base()
    if adx is not None: CFG.ADX_MIN = adx
    if overrides:
        for k,v in overrides.items(): setattr(CFG,k,v)
    a = adx if adx else CFG.VR_ADX_MIN
    r = run_test('volatility_regime',syms,'1h',trail_act=0.4,trail_pct=0.22)
    print(f'  {label:<50} T={r["trades"]:>3} W={r["wins"]:>2} WR={r["wr"]:>4.0f}% PF={r["pf"]:>5.2f} PnL=${r["pnl"]:>+8.2f}')
    return r

ACTUALES = ['XRPUSDT','BTCUSDT','DOGEUSDT','OPUSDT','FILUSDT']
NUEVOS_A = ['ETHUSDT','SOLUSDT','NEARUSDT','LINKUSDT','AVAXUSDT']
NUEVOS_B = ['PENDLEUSDT','ORDIUSDT','TIAUSDT','SUIUSDT','APTUSDT']
MIX_A = ['XRPUSDT','ETHUSDT','BTCUSDT','SOLUSDT','DOGEUSDT']
MIX_B = ['OPUSDT','FILUSDT','NEARUSDT','LINKUSDT','AVAXUSDT']
MIX_C = ['PENDLEUSDT','ORDIUSDT','TIAUSDT','SUIUSDT','APTUSDT']

batch = sys.argv[1] if len(sys.argv)>1 else '1'

if batch=='1':
    print(f'\n{"="*80}\n  VOL REGIME BATCH 1: Parámetros actuales\n{"="*80}')
    run('BASE (A 25/75)',ACTUALES)
    run('Low 20 High 70',ACTUALES,{'VR_ATR_LOW_PERCENTILE':20,'VR_ATR_HIGH_PERCENTILE':70})
    run('Low 30 High 80',ACTUALES,{'VR_ATR_LOW_PERCENTILE':30,'VR_ATR_HIGH_PERCENTILE':80})
    run('Low 20 High 75',ACTUALES,{'VR_ATR_LOW_PERCENTILE':20})
    run('Low 25 High 80',ACTUALES,{'VR_ATR_HIGH_PERCENTILE':80})
    run('VOL 1.2',ACTUALES,{'VR_VOLUME_RATIO_MIN':1.2})
    run('VOL 2.0',ACTUALES,{'VR_VOLUME_RATIO_MIN':2.0})
    run('ADX 18',ACTUALES,adx=18)

if batch=='2':
    print(f'\n{"="*80}\n  VOL REGIME BATCH 2: Más parámetros\n{"="*80}')
    run('ADX 25',ACTUALES,adx=25)
    run('ADX 28',ACTUALES,adx=28)
    run('SL 1.0',ACTUALES,{'VR_SL_ATR_MULT':1.0})
    run('SL 2.0',ACTUALES,{'VR_SL_ATR_MULT':2.0})
    run('EMA 15/40',ACTUALES,{'VR_EMA_FAST':15,'VR_EMA_SLOW':40})
    run('EMA 25/60',ACTUALES,{'VR_EMA_FAST':25,'VR_EMA_SLOW':60})
    run('MOM 3',ACTUALES,{'VR_MOMENTUM_BARS':3})
    run('MOM 5',ACTUALES,{'VR_MOMENTUM_BARS':5})

if batch=='3':
    print(f'\n{"="*80}\n  VOL REGIME BATCH 3: Combinaciones\n{"="*80}')
    run('Low20/H70+ADX18',ACTUALES,{'VR_ATR_LOW_PERCENTILE':20,'VR_ATR_HIGH_PERCENTILE':70},adx=18)
    run('Low20/H70+ADX20',ACTUALES,{'VR_ATR_LOW_PERCENTILE':20,'VR_ATR_HIGH_PERCENTILE':70},adx=20)
    run('Low20/H75+VOL1.2',ACTUALES,{'VR_ATR_LOW_PERCENTILE':20,'VR_VOLUME_RATIO_MIN':1.2})
    run('MOM3+ADX18',ACTUALES,{'VR_MOMENTUM_BARS':3},adx=18)
    run('TODO RELAJADO',ACTUALES,{'VR_ATR_LOW_PERCENTILE':20,'VR_ATR_HIGH_PERCENTILE':70,
        'VR_VOLUME_RATIO_MIN':1.2,'VR_MOMENTUM_BARS':3},adx=18)

if batch=='4':
    print(f'\n{"="*80}\n  VOL REGIME BATCH 4: Nuevos símbolos\n{"="*80}')
    run('NUEVOS_A base',NUEVOS_A)
    run('NUEVOS_A RELAJADO',NUEVOS_A,{'VR_ATR_LOW_PERCENTILE':20,'VR_ATR_HIGH_PERCENTILE':70,
        'VR_VOLUME_RATIO_MIN':1.2,'VR_MOMENTUM_BARS':3},adx=18)
    run('NUEVOS_B base',NUEVOS_B)
    run('NUEVOS_B RELAJADO',NUEVOS_B,{'VR_ATR_LOW_PERCENTILE':20,'VR_ATR_HIGH_PERCENTILE':70,
        'VR_VOLUME_RATIO_MIN':1.2,'VR_MOMENTUM_BARS':3},adx=18)

if batch=='5':
    print(f'\n{"="*80}\n  VOL REGIME BATCH 5: Mix\n{"="*80}')
    run('MIX_A base',MIX_A)
    run('MIX_A RELAJADO',MIX_A,{'VR_ATR_LOW_PERCENTILE':20,'VR_ATR_HIGH_PERCENTILE':70,
        'VR_VOLUME_RATIO_MIN':1.2,'VR_MOMENTUM_BARS':3},adx=18)
    run('MIX_B base',MIX_B)
    run('MIX_B RELAJADO',MIX_B,{'VR_ATR_LOW_PERCENTILE':20,'VR_ATR_HIGH_PERCENTILE':70,
        'VR_VOLUME_RATIO_MIN':1.2,'VR_MOMENTUM_BARS':3},adx=18)
    run('MIX_C base',MIX_C)
    run('MIX_C RELAJADO',MIX_C,{'VR_ATR_LOW_PERCENTILE':20,'VR_ATR_HIGH_PERCENTILE':70,
        'VR_VOLUME_RATIO_MIN':1.2,'VR_MOMENTUM_BARS':3},adx=18)

print(f'\n  Uso: ./venv/bin/python bt_vr_batches.py [1-5]')
