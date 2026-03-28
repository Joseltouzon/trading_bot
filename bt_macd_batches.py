#!/usr/bin/env python3
"""Tests MACD Momentum - batches."""
import sys; sys.path.insert(0,'.')
import config as CFG
exec(open('bt_test_combos.py').read().split('def main')[0])

def base():
    CFG.MACD_FAST=12; CFG.MACD_SLOW=26; CFG.MACD_SIGNAL=9
    CFG.MACD_MIN_VOLUME_RATIO=3.0; CFG.MACD_RSI_PERIOD=14
    CFG.MACD_RSI_BULL_MIN=55; CFG.MACD_RSI_BEAR_MAX=45
    CFG.MACD_ADX_MIN=25; CFG.MACD_MIN_ATR_PCT=0.20
    CFG.MACD_STRUCTURE_LOOKBACK=10; CFG.MACD_SL_ATR_MULT=2.0

def run(label, syms, overrides=None, adx=None):
    base()
    if adx is not None: CFG.ADX_MIN = adx
    if overrides:
        for k,v in overrides.items(): setattr(CFG,k,v)
    a = adx if adx else CFG.MACD_ADX_MIN
    r = run_test('macd_momentum',syms,'15m',trail_act=0.4,trail_pct=0.22)
    print(f'  {label:<50} T={r["trades"]:>3} W={r["wins"]:>2} WR={r["wr"]:>4.0f}% PF={r["pf"]:>5.2f} PnL=${r["pnl"]:>+8.2f}')
    return r

ACTUALES = ['SANDUSDT','PENDLEUSDT','XRPUSDT','AVAXUSDT','SOLUSDT']
NUEVOS_A = ['LINKUSDT','TIAUSDT','ARBUSDT','ORDIUSDT','DOGEUSDT']
NUEVOS_B = ['ETHUSDT','NEARUSDT','FETUSDT','OPUSDT','WIFUSDT']
NUEVOS_C = ['SUIUSDT','FILUSDT','APTUSDT','ATOMUSDT','TAOUSDT']
MIX_A = ['SANDUSDT','LINKUSDT','PENDLEUSDT','TIAUSDT','XRPUSDT']
MIX_B = ['AVAXUSDT','SOLUSDT','ARBUSDT','ORDIUSDT','DOGEUSDT']
MIX_C = ['ETHUSDT','NEARUSDT','SUIUSDT','OPUSDT','WIFUSDT']

batch = sys.argv[1] if len(sys.argv)>1 else '1'

if batch=='1':
    print(f'\n{"="*80}\n  MACD BATCH 1: Variaciones del BACKTESTING_LOG (con símbolos actuales)\n{"="*80}')
    run('BASE 12/26/9 ADX25 Vol3',ACTUALES)
    run('12/26/9 ADX25 Vol2',ACTUALES,{'MACD_MIN_VOLUME_RATIO':2.0})
    run('12/26/9 ADX25 Vol4',ACTUALES,{'MACD_MIN_VOLUME_RATIO':4.0})
    run('12/26/9 ADX30 Vol3',ACTUALES,adx=30)
    run('12/26/9 ADX30 Vol4',ACTUALES,{'MACD_MIN_VOLUME_RATIO':4.0},adx=30)
    run('12/26/9 ADX35 Vol4',ACTUALES,{'MACD_MIN_VOLUME_RATIO':4.0},adx=35)
    run('8/17/7 ADX30 Vol4',ACTUALES,{'MACD_FAST':8,'MACD_SLOW':17,'MACD_SIGNAL':7,'MACD_MIN_VOLUME_RATIO':4.0},adx=30)
    run('19/39/9 ADX25 Vol4',ACTUALES,{'MACD_FAST':19,'MACD_SLOW':39,'MACD_MIN_VOLUME_RATIO':4.0})

if batch=='2':
    print(f'\n{"="*80}\n  MACD BATCH 2: Más MACD settings\n{"="*80}')
    run('8/17/7 ADX25 Vol3',ACTUALES,{'MACD_FAST':8,'MACD_SLOW':17,'MACD_SIGNAL':7})
    run('8/17/7 ADX25 Vol2',ACTUALES,{'MACD_FAST':8,'MACD_SLOW':17,'MACD_SIGNAL':7,'MACD_MIN_VOLUME_RATIO':2.0})
    run('19/39/9 ADX25 Vol3',ACTUALES,{'MACD_FAST':19,'MACD_SLOW':39})
    run('19/39/9 ADX30 Vol3',ACTUALES,{'MACD_FAST':19,'MACD_SLOW':39},adx=30)
    run('12/26/9 ADX20 Vol3',ACTUALES,adx=20)
    run('12/26/9 ADX20 Vol2',ACTUALES,{'MACD_MIN_VOLUME_RATIO':2.0},adx=20)
    run('12/26/9 ADX22 Vol2.5',ACTUALES,{'MACD_MIN_VOLUME_RATIO':2.5},adx=22)
    run('12/26/9 ADX18 Vol2',ACTUALES,{'MACD_MIN_VOLUME_RATIO':2.0},adx=18)

if batch=='3':
    print(f'\n{"="*80}\n  MACD BATCH 3: RSI, ATR, SL\n{"="*80}')
    run('RSI BULL 50',ACTUALES,{'MACD_RSI_BULL_MIN':50})
    run('RSI BULL 60',ACTUALES,{'MACD_RSI_BULL_MIN':60})
    run('RSI BEAR 40',ACTUALES,{'MACD_RSI_BEAR_MAX':40})
    run('RSI BEAR 50',ACTUALES,{'MACD_RSI_BEAR_MAX':50})
    run('ATR 0.15',ACTUALES,{'MACD_MIN_ATR_PCT':0.15})
    run('ATR 0.25',ACTUALES,{'MACD_MIN_ATR_PCT':0.25})
    run('SL 1.5',ACTUALES,{'MACD_SL_ATR_MULT':1.5})
    run('SL 2.5',ACTUALES,{'MACD_SL_ATR_MULT':2.5})

if batch=='4':
    print(f'\n{"="*80}\n  MACD BATCH 4: Combinaciones\n{"="*80}')
    run('ADX20+Vol2+RSI50/50',ACTUALES,{'MACD_MIN_VOLUME_RATIO':2.0,'MACD_RSI_BULL_MIN':50,'MACD_RSI_BEAR_MAX':50},adx=20)
    run('ADX20+Vol2+RSI50/40',ACTUALES,{'MACD_MIN_VOLUME_RATIO':2.0,'MACD_RSI_BULL_MIN':50,'MACD_RSI_BEAR_MAX':40},adx=20)
    run('ADX18+Vol2',ACTUALES,{'MACD_MIN_VOLUME_RATIO':2.0},adx=18)
    run('ADX18+Vol1.5',ACTUALES,{'MACD_MIN_VOLUME_RATIO':1.5},adx=18)
    run('12/26/9 ADX18+Vol2+ATR0.15',ACTUALES,{'MACD_MIN_VOLUME_RATIO':2.0,'MACD_MIN_ATR_PCT':0.15},adx=18)
    run('8/17/7 ADX20+Vol2',ACTUALES,{'MACD_FAST':8,'MACD_SLOW':17,'MACD_SIGNAL':7,'MACD_MIN_VOLUME_RATIO':2.0},adx=20)

if batch=='5':
    print(f'\n{"="*80}\n  MACD BATCH 5: Más combinaciones relajadas\n{"="*80}')
    run('TODO RELAJADO A',ACTUALES,{'MACD_MIN_VOLUME_RATIO':2.0,'MACD_RSI_BULL_MIN':50,
        'MACD_RSI_BEAR_MAX':50,'MACD_MIN_ATR_PCT':0.15},adx=18)
    run('TODO RELAJADO B',ACTUALES,{'MACD_MIN_VOLUME_RATIO':1.5,'MACD_RSI_BULL_MIN':50,
        'MACD_RSI_BEAR_MAX':50,'MACD_MIN_ATR_PCT':0.15},adx=18)
    run('8/17/7 RELAJADO',ACTUALES,{'MACD_FAST':8,'MACD_SLOW':17,'MACD_SIGNAL':7,
        'MACD_MIN_VOLUME_RATIO':2.0,'MACD_RSI_BULL_MIN':50,'MACD_RSI_BEAR_MAX':50},adx=18)
    run('19/39/9 RELAJADO',ACTUALES,{'MACD_FAST':19,'MACD_SLOW':39,
        'MACD_MIN_VOLUME_RATIO':2.0,'MACD_RSI_BULL_MIN':50,'MACD_RSI_BEAR_MAX':50},adx=18)
    run('ADX15+Vol1.5+RSI50/50',ACTUALES,{'MACD_MIN_VOLUME_RATIO':1.5,'MACD_RSI_BULL_MIN':50,
        'MACD_RSI_BEAR_MAX':50,'MACD_MIN_ATR_PCT':0.15},adx=15)

if batch=='6':
    print(f'\n{"="*80}\n  MACD BATCH 6: Nuevos símbolos A\n{"="*80}')
    run('NUEVOS_A base',NUEVOS_A)
    run('NUEVOS_A ADX20+Vol2',NUEVOS_A,{'MACD_MIN_VOLUME_RATIO':2.0},adx=20)
    run('NUEVOS_A ADX18+Vol2+RSI50/50',NUEVOS_A,{'MACD_MIN_VOLUME_RATIO':2.0,
        'MACD_RSI_BULL_MIN':50,'MACD_RSI_BEAR_MAX':50},adx=18)
    run('NUEVOS_A RELAJADO',NUEVOS_A,{'MACD_MIN_VOLUME_RATIO':1.5,'MACD_RSI_BULL_MIN':50,
        'MACD_RSI_BEAR_MAX':50,'MACD_MIN_ATR_PCT':0.15},adx=18)
    run('NUEVOS_B base',NUEVOS_B)
    run('NUEVOS_B ADX20+Vol2',NUEVOS_B,{'MACD_MIN_VOLUME_RATIO':2.0},adx=20)

if batch=='7':
    print(f'\n{"="*80}\n  MACD BATCH 7: Nuevos símbolos B + C\n{"="*80}')
    run('NUEVOS_B RELAJADO',NUEVOS_B,{'MACD_MIN_VOLUME_RATIO':1.5,'MACD_RSI_BULL_MIN':50,
        'MACD_RSI_BEAR_MAX':50,'MACD_MIN_ATR_PCT':0.15},adx=18)
    run('NUEVOS_C base',NUEVOS_C)
    run('NUEVOS_C ADX20+Vol2',NUEVOS_C,{'MACD_MIN_VOLUME_RATIO':2.0},adx=20)
    run('NUEVOS_C RELAJADO',NUEVOS_C,{'MACD_MIN_VOLUME_RATIO':1.5,'MACD_RSI_BULL_MIN':50,
        'MACD_RSI_BEAR_MAX':50,'MACD_MIN_ATR_PCT':0.15},adx=18)

if batch=='8':
    print(f'\n{"="*80}\n  MACD BATCH 8: Mix\n{"="*80}')
    run('MIX_A base',MIX_A)
    run('MIX_A RELAJADO',MIX_A,{'MACD_MIN_VOLUME_RATIO':2.0,'MACD_RSI_BULL_MIN':50,
        'MACD_RSI_BEAR_MAX':50,'MACD_MIN_ATR_PCT':0.15},adx=18)
    run('MIX_B base',MIX_B)
    run('MIX_B RELAJADO',MIX_B,{'MACD_MIN_VOLUME_RATIO':2.0,'MACD_RSI_BULL_MIN':50,
        'MACD_RSI_BEAR_MAX':50,'MACD_MIN_ATR_PCT':0.15},adx=18)
    run('MIX_C base',MIX_C)
    run('MIX_C RELAJADO',MIX_C,{'MACD_MIN_VOLUME_RATIO':2.0,'MACD_RSI_BULL_MIN':50,
        'MACD_RSI_BEAR_MAX':50,'MACD_MIN_ATR_PCT':0.15},adx=18)

print(f'\n  Uso: ./venv/bin/python bt_macd_batches.py [1-8]')
