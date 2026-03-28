#!/usr/bin/env python3
"""Tests Volatility Squeeze - batches."""
import sys; sys.path.insert(0,'.')
import config as CFG
exec(open('bt_test_combos.py').read().split('def main')[0])

def base():
    CFG.VOL_SQUEEZE_ATR_PERCENTILE=15; CFG.VOL_SQUEEZE_BB_WIDTH_PERCENTILE=25
    CFG.VOL_SQUEEZE_MIN_VOLUME_RATIO=1.5; CFG.VOL_SQUEEZE_ADX_MIN=15
    CFG.VOL_SQUEEZE_SL_ATR_MULT=1.5; CFG.VOL_SQUEEZE_EMA_FAST=20; CFG.VOL_SQUEEZE_EMA_SLOW=50

def run(label, syms, overrides=None, adx=None):
    base()
    if adx is not None: CFG.ADX_MIN = adx
    if overrides:
        for k,v in overrides.items(): setattr(CFG,k,v)
    a = adx if adx else CFG.VOL_SQUEEZE_ADX_MIN
    r = run_test('volatility_squeeze',syms,'1h',trail_act=0.4,trail_pct=0.22)
    print(f'  {label:<50} T={r["trades"]:>3} W={r["wins"]:>2} WR={r["wr"]:>4.0f}% PF={r["pf"]:>5.2f} PnL=${r["pnl"]:>+8.2f}')
    return r

ACTUALES = ['NEARUSDT','OPUSDT','BTCUSDT','LINKUSDT','XRPUSDT']
NUEVOS_A = ['SOLUSDT','ETHUSDT','DOGEUSDT','AVAXUSDT','FILUSDT']
NUEVOS_B = ['PENDLEUSDT','ORDIUSDT','TIAUSDT','SUIUSDT','APTUSDT']
MIX_A = ['NEARUSDT','SOLUSDT','ETHUSDT','OPUSDT','BTCUSDT']
MIX_B = ['LINKUSDT','XRPUSDT','DOGEUSDT','AVAXUSDT','PENDLEUSDT']
MIX_C = ['ORDIUSDT','TIAUSDT','SUIUSDT','FILUSDT','APTUSDT']

batch = sys.argv[1] if len(sys.argv)>1 else '1'

if batch=='1':
    print(f'\n{"="*80}\n  VOL SQUEEZE BATCH 1: Parámetros actuales\n{"="*80}')
    run('BASE',ACTUALES)
    run('ATR_PCT 10',ACTUALES,{'VOL_SQUEEZE_ATR_PERCENTILE':10})
    run('ATR_PCT 20',ACTUALES,{'VOL_SQUEEZE_ATR_PERCENTILE':20})
    run('BB_WIDTH 20',ACTUALES,{'VOL_SQUEEZE_BB_WIDTH_PERCENTILE':20})
    run('BB_WIDTH 30',ACTUALES,{'VOL_SQUEEZE_BB_WIDTH_PERCENTILE':30})
    run('VOL 1.2',ACTUALES,{'VOL_SQUEEZE_MIN_VOLUME_RATIO':1.2})
    run('VOL 2.0',ACTUALES,{'VOL_SQUEEZE_MIN_VOLUME_RATIO':2.0})
    run('ADX 12',ACTUALES,adx=12)

if batch=='2':
    print(f'\n{"="*80}\n  VOL SQUEEZE BATCH 2: Más parámetros\n{"="*80}')
    run('ADX 18',ACTUALES,adx=18)
    run('ADX 20',ACTUALES,adx=20)
    run('SL 1.0',ACTUALES,{'VOL_SQUEEZE_SL_ATR_MULT':1.0})
    run('SL 2.0',ACTUALES,{'VOL_SQUEEZE_SL_ATR_MULT':2.0})
    run('EMA 15/40',ACTUALES,{'VOL_SQUEEZE_EMA_FAST':15,'VOL_SQUEEZE_EMA_SLOW':40})
    run('EMA 25/60',ACTUALES,{'VOL_SQUEEZE_EMA_FAST':25,'VOL_SQUEEZE_EMA_SLOW':60})
    run('ATR10+BB20',ACTUALES,{'VOL_SQUEEZE_ATR_PERCENTILE':10,'VOL_SQUEEZE_BB_WIDTH_PERCENTILE':20})
    run('ATR20+BB30',ACTUALES,{'VOL_SQUEEZE_ATR_PERCENTILE':20,'VOL_SQUEEZE_BB_WIDTH_PERCENTILE':30})

if batch=='3':
    print(f'\n{"="*80}\n  VOL SQUEEZE BATCH 3: Nuevos símbolos\n{"="*80}')
    run('NUEVOS_A base',NUEVOS_A)
    run('NUEVOS_A ATR10',NUEVOS_A,{'VOL_SQUEEZE_ATR_PERCENTILE':10})
    run('NUEVOS_A ADX12',NUEVOS_A,adx=12)
    run('NUEVOS_B base',NUEVOS_B)
    run('NUEVOS_B ATR10',NUEVOS_B,{'VOL_SQUEEZE_ATR_PERCENTILE':10})
    run('NUEVOS_B ADX12',NUEVOS_B,adx=12)

if batch=='4':
    print(f'\n{"="*80}\n  VOL SQUEEZE BATCH 4: Mix\n{"="*80}')
    run('MIX_A base',MIX_A)
    run('MIX_A RELAJADO',MIX_A,{'VOL_SQUEEZE_ATR_PERCENTILE':10,'VOL_SQUEEZE_MIN_VOLUME_RATIO':1.2},adx=12)
    run('MIX_B base',MIX_B)
    run('MIX_B RELAJADO',MIX_B,{'VOL_SQUEEZE_ATR_PERCENTILE':10,'VOL_SQUEEZE_MIN_VOLUME_RATIO':1.2},adx=12)
    run('MIX_C base',MIX_C)
    run('MIX_C RELAJADO',MIX_C,{'VOL_SQUEEZE_ATR_PERCENTILE':10,'VOL_SQUEEZE_MIN_VOLUME_RATIO':1.2},adx=12)

print(f'\n  Uso: ./venv/bin/python bt_vs_batches.py [1-4]')
