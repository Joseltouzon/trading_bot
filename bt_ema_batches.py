#!/usr/bin/env python3
"""Tests EMA Breakout - batches."""
import sys; sys.path.insert(0,'.')
import config as CFG
exec(open('bt_test_combos.py').read().split('def main')[0])

def base():
    CFG.EMA_BREAKOUT_FAST=25; CFG.EMA_BREAKOUT_SLOW=50; CFG.ADX_MIN=25
    CFG.EMA_MIN_SLOPE_PCT=0.04; CFG.EMA_RSI_OVERSOLD=30; CFG.EMA_RSI_OVERBOUGHT=70
    CFG.EMA_MIN_VOLUME_RATIO=1.2; CFG.EMA_MIN_ATR_PCT=0.15
    CFG.EMA_MOMENTUM_BARS=3; CFG.EMA_MIN_MOMENTUM_PCT=0.10

def run(label, syms, overrides=None, adx=None):
    base()
    if adx is not None: CFG.ADX_MIN = adx
    if overrides:
        for k,v in overrides.items(): setattr(CFG,k,v)
    a = adx if adx else CFG.ADX_MIN
    r = run_test('ema_breakout',syms,'15m',trail_act=0.4,trail_pct=0.22)
    print(f'  {label:<50} T={r["trades"]:>3} W={r["wins"]:>2} WR={r["wr"]:>4.0f}% PF={r["pf"]:>5.2f} PnL=${r["pnl"]:>+8.2f}')
    return r

ACTUALES = ['DOGEUSDT','LINKUSDT','TIAUSDT','ORDIUSDT','PENDLEUSDT']
NUEVOS_A = ['AVAXUSDT','SOLUSDT','ETHUSDT','XRPUSDT','FILUSDT']
NUEVOS_B = ['1000PEPEUSDT','NEARUSDT','SUIUSDT','BTCUSDT','APTUSDT']
NUEVOS_C = ['WIFUSDT','ATOMUSDT','TAOUSDT','SANDUSDT','DOGEUSDT']
MIX_A = ['DOGEUSDT','LINKUSDT','ORDIUSDT','PENDLEUSDT','AVAXUSDT']
MIX_B = ['SOLUSDT','ETHUSDT','XRPUSDT','TIAUSDT','FILUSDT']
MIX_C = ['NEARUSDT','SUIUSDT','BTCUSDT','APTUSDT','1000PEPEUSDT']

batch = sys.argv[1] if len(sys.argv)>1 else '1'

if batch=='1':
    print(f'\n{"="*80}\n  EMA BATCH 1: ADX sweep (EMA 25/50, símbolos actuales)\n{"="*80}')
    for adx_v in [14,16,17,18,19,20,22,25,28,30]:
        run(f'ADX {adx_v}',ACTUALES,adx=adx_v)

if batch=='2':
    print(f'\n{"="*80}\n  EMA BATCH 2: EMA variations + ADX\n{"="*80}')
    run('EMA 9/21 ADX17',ACTUALES,{'EMA_BREAKOUT_FAST':9,'EMA_BREAKOUT_SLOW':21},adx=17)
    run('EMA 9/21 ADX20',ACTUALES,{'EMA_BREAKOUT_FAST':9,'EMA_BREAKOUT_SLOW':21},adx=20)
    run('EMA 9/21 ADX25',ACTUALES,{'EMA_BREAKOUT_FAST':9,'EMA_BREAKOUT_SLOW':21})
    run('EMA 20/50 ADX17',ACTUALES,{'EMA_BREAKOUT_FAST':20},adx=17)
    run('EMA 20/50 ADX18',ACTUALES,{'EMA_BREAKOUT_FAST':20},adx=18)
    run('EMA 12/26 ADX17',ACTUALES,{'EMA_BREAKOUT_FAST':12,'EMA_BREAKOUT_SLOW':26},adx=17)
    run('EMA 12/26 ADX20',ACTUALES,{'EMA_BREAKOUT_FAST':12,'EMA_BREAKOUT_SLOW':26},adx=20)
    run('EMA 15/40 ADX17',ACTUALES,{'EMA_BREAKOUT_FAST':15,'EMA_BREAKOUT_SLOW':40},adx=17)

if batch=='3':
    print(f'\n{"="*80}\n  EMA BATCH 3: RSI variations\n{"="*80}')
    run('RSI OS 25',ACTUALES,{'EMA_RSI_OVERSOLD':25})
    run('RSI OS 35',ACTUALES,{'EMA_RSI_OVERSOLD':35})
    run('RSI OB 65',ACTUALES,{'EMA_RSI_OVERBOUGHT':65})
    run('RSI OB 75',ACTUALES,{'EMA_RSI_OVERBOUGHT':75})
    run('RSI OB 80',ACTUALES,{'EMA_RSI_OVERBOUGHT':80})
    run('RSI 25/75',ACTUALES,{'EMA_RSI_OVERSOLD':25,'EMA_RSI_OVERBOUGHT':75})
    run('RSI 30/80',ACTUALES,{'EMA_RSI_OVERBOUGHT':80})
    run('RSI 25/80',ACTUALES,{'EMA_RSI_OVERSOLD':25,'EMA_RSI_OVERBOUGHT':80})

if batch=='4':
    print(f'\n{"="*80}\n  EMA BATCH 4: Slope, volume, ATR, momentum\n{"="*80}')
    run('SLOPE 0.02',ACTUALES,{'EMA_MIN_SLOPE_PCT':0.02})
    run('SLOPE 0.06',ACTUALES,{'EMA_MIN_SLOPE_PCT':0.06})
    run('VOL 1.0',ACTUALES,{'EMA_MIN_VOLUME_RATIO':1.0})
    run('VOL 1.5',ACTUALES,{'EMA_MIN_VOLUME_RATIO':1.5})
    run('ATR 0.10',ACTUALES,{'EMA_MIN_ATR_PCT':0.10})
    run('ATR 0.20',ACTUALES,{'EMA_MIN_ATR_PCT':0.20})
    run('MOM 2',ACTUALES,{'EMA_MOMENTUM_BARS':2})
    run('MOM 5',ACTUALES,{'EMA_MOMENTUM_BARS':5})

if batch=='5':
    print(f'\n{"="*80}\n  EMA BATCH 5: Combinaciones ganadoras con ADX 17\n{"="*80}')
    run('20/50 ADX17 + RSI OB75',ACTUALES,{'EMA_BREAKOUT_FAST':20,'EMA_RSI_OVERBOUGHT':75},adx=17)
    run('20/50 ADX17 + RSI OB80',ACTUALES,{'EMA_BREAKOUT_FAST':20,'EMA_RSI_OVERBOUGHT':80},adx=17)
    run('20/50 ADX17 + VOL1.0',ACTUALES,{'EMA_BREAKOUT_FAST':20,'EMA_MIN_VOLUME_RATIO':1.0},adx=17)
    run('20/50 ADX17 + SLOPE0.02',ACTUALES,{'EMA_BREAKOUT_FAST':20,'EMA_MIN_SLOPE_PCT':0.02},adx=17)
    run('12/26 ADX17 + RSI OB75',ACTUALES,{'EMA_BREAKOUT_FAST':12,'EMA_BREAKOUT_SLOW':26,'EMA_RSI_OVERBOUGHT':75},adx=17)
    run('20/50 ADX17 + RSI 25/75',ACTUALES,{'EMA_BREAKOUT_FAST':20,'EMA_RSI_OVERSOLD':25,'EMA_RSI_OVERBOUGHT':75},adx=17)
    run('20/50 ADX17 + MOM2',ACTUALES,{'EMA_BREAKOUT_FAST':20,'EMA_MOMENTUM_BARS':2},adx=17)
    run('20/50 ADX18 + RSI OB75',ACTUALES,{'EMA_BREAKOUT_FAST':20,'EMA_RSI_OVERBOUGHT':75},adx=18)

if batch=='6':
    print(f'\n{"="*80}\n  EMA BATCH 6: Nuevos símbolos A\n{"="*80}')
    run('NUEVOS_A base',NUEVOS_A)
    run('NUEVOS_A ADX17',NUEVOS_A,adx=17)
    run('NUEVOS_A 20/50 ADX17',NUEVOS_A,{'EMA_BREAKOUT_FAST':20},adx=17)
    run('NUEVOS_A 20/50 ADX17 RSI OB75',NUEVOS_A,{'EMA_BREAKOUT_FAST':20,'EMA_RSI_OVERBOUGHT':75},adx=17)
    run('NUEVOS_B base',NUEVOS_B)
    run('NUEVOS_B ADX17',NUEVOS_B,adx=17)
    run('NUEVOS_B 20/50 ADX17',NUEVOS_B,{'EMA_BREAKOUT_FAST':20},adx=17)
    run('NUEVOS_B 20/50 ADX17 RSI OB75',NUEVOS_B,{'EMA_BREAKOUT_FAST':20,'EMA_RSI_OVERBOUGHT':75},adx=17)

if batch=='7':
    print(f'\n{"="*80}\n  EMA BATCH 7: Nuevos C + Mix\n{"="*80}')
    run('NUEVOS_C base',NUEVOS_C)
    run('NUEVOS_C ADX17',NUEVOS_C,adx=17)
    run('NUEVOS_C 20/50 ADX17 RSI OB75',NUEVOS_C,{'EMA_BREAKOUT_FAST':20,'EMA_RSI_OVERBOUGHT':75},adx=17)
    run('MIX_A 20/50 ADX17 RSI OB75',MIX_A,{'EMA_BREAKOUT_FAST':20,'EMA_RSI_OVERBOUGHT':75},adx=17)
    run('MIX_B 20/50 ADX17 RSI OB75',MIX_B,{'EMA_BREAKOUT_FAST':20,'EMA_RSI_OVERBOUGHT':75},adx=17)
    run('MIX_C 20/50 ADX17 RSI OB75',MIX_C,{'EMA_BREAKOUT_FAST':20,'EMA_RSI_OVERBOUGHT':75},adx=17)

if batch=='8':
    print(f'\n{"="*80}\n  EMA BATCH 8: Top combos finales\n{"="*80}')
    # Mejor config encontrada con diferentes grupos
    best = {'EMA_BREAKOUT_FAST':20,'EMA_RSI_OVERBOUGHT':75}
    run('BEST + ACTUALES',ACTUALES,best,adx=17)
    run('BEST + NUEVOS_A',NUEVOS_A,best,adx=17)
    run('BEST + NUEVOS_B',NUEVOS_B,best,adx=17)
    run('BEST + NUEVOS_C',NUEVOS_C,best,adx=17)
    run('BEST + MIX_A',MIX_A,best,adx=17)
    run('BEST + MIX_B',MIX_B,best,adx=17)
    run('BEST + MIX_C',MIX_C,best,adx=17)

print(f'\n  Uso: ./venv/bin/python bt_ema_batches.py [1-8]')
