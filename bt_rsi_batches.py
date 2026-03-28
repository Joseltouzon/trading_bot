#!/usr/bin/env python3
"""Tests RSI+BB Reversion - batches."""
import sys; sys.path.insert(0,'.')
import config as CFG
exec(open('bt_test_combos.py').read().split('def main')[0])

def base():
    CFG.RSI_BB_OVERSOLD=20; CFG.RSI_BB_OVERBOUGHT=80; CFG.RSI_BB_BB_PERIOD=20
    CFG.RSI_BB_BB_STD_MULT=2.0; CFG.RSI_BB_MIN_VOLUME_RATIO=1.2; CFG.RSI_BB_ADX_MIN=12
    CFG.RSI_BB_SL_ATR_MULT=2.5; CFG.RSI_BB_STOCH_PERIOD=14
    CFG.RSI_BB_REQUIRE_DIVERGENCE=True; CFG.RSI_BB_ATR_PCT=0.15

def run(label, syms, overrides=None, adx=None):
    base()
    if adx is not None: CFG.ADX_MIN = adx
    if overrides:
        for k,v in overrides.items(): setattr(CFG,k,v)
    a = adx if adx else CFG.RSI_BB_ADX_MIN
    r = run_test('rsi_bb_reversion',syms,'5m',trail_act=0.4,trail_pct=0.22)
    print(f'  {label:<50} T={r["trades"]:>3} W={r["wins"]:>2} WR={r["wr"]:>4.0f}% PF={r["pf"]:>5.2f} PnL=${r["pnl"]:>+8.2f}')
    return r

ACTUALES = ['1000PEPEUSDT','AVAXUSDT','TIAUSDT','ORDIUSDT','TAOUSDT']
NUEVOS_A = ['XRPUSDT','ETHUSDT','DOGEUSDT','SOLUSDT','FILUSDT']
NUEVOS_B = ['WIFUSDT','LINKUSDT','NEARUSDT','PENDLEUSDT','BTCUSDT']
MIX_A = ['1000PEPEUSDT','XRPUSDT','AVAXUSDT','ETHUSDT','TIAUSDT']
MIX_B = ['ORDIUSDT','TAOUSDT','DOGEUSDT','SOLUSDT','WIFUSDT']
MIX_C = ['LINKUSDT','NEARUSDT','PENDLEUSDT','BTCUSDT','FILUSDT']

batch = sys.argv[1] if len(sys.argv)>1 else '1'

if batch=='1':
    print(f'\n{"="*80}\n  RSI+BB BATCH 1: Parámetros con símbolos actuales\n{"="*80}')
    run('BASE',ACTUALES)
    run('OS 25 OB 75',ACTUALES,{'RSI_BB_OVERSOLD':25,'RSI_BB_OVERBOUGHT':75})
    run('OS 30 OB 70',ACTUALES,{'RSI_BB_OVERSOLD':30,'RSI_BB_OVERBOUGHT':70})
    run('OS 25 OB 70',ACTUALES,{'RSI_BB_OVERSOLD':25,'RSI_BB_OVERBOUGHT':70})
    run('BB 1.5',ACTUALES,{'RSI_BB_BB_STD_MULT':1.5})
    run('BB 2.5',ACTUALES,{'RSI_BB_BB_STD_MULT':2.5})
    run('ADX 15',ACTUALES,adx=15)
    run('ADX 18',ACTUALES,adx=18)

if batch=='2':
    print(f'\n{"="*80}\n  RSI+BB BATCH 2: Más parámetros\n{"="*80}')
    run('VOL 1.0',ACTUALES,{'RSI_BB_MIN_VOLUME_RATIO':1.0})
    run('VOL 1.5',ACTUALES,{'RSI_BB_MIN_VOLUME_RATIO':1.5})
    run('SL 2.0',ACTUALES,{'RSI_BB_SL_ATR_MULT':2.0})
    run('SL 3.0',ACTUALES,{'RSI_BB_SL_ATR_MULT':3.0})
    run('DIVERG OFF',ACTUALES,{'RSI_BB_REQUIRE_DIVERGENCE':False})
    run('ATR 0.10',ACTUALES,{'RSI_BB_ATR_PCT':0.10})
    run('ATR 0.20',ACTUALES,{'RSI_BB_ATR_PCT':0.20})
    run('BB_PERIOD 14',ACTUALES,{'RSI_BB_BB_PERIOD':14})

if batch=='3':
    print(f'\n{"="*80}\n  RSI+BB BATCH 3: Combinaciones\n{"="*80}')
    run('OS25+OB75+ADX15',ACTUALES,{'RSI_BB_OVERSOLD':25,'RSI_BB_OVERBOUGHT':75},adx=15)
    run('OS25+OB75+ADX18',ACTUALES,{'RSI_BB_OVERSOLD':25,'RSI_BB_OVERBOUGHT':75},adx=18)
    run('OS30+OB70+BB1.5',ACTUALES,{'RSI_BB_OVERSOLD':30,'RSI_BB_OVERBOUGHT':70,'RSI_BB_BB_STD_MULT':1.5})
    run('DIVERG_OFF+ADX15',ACTUALES,{'RSI_BB_REQUIRE_DIVERGENCE':False},adx=15)
    run('TODO RELAJADO',ACTUALES,{'RSI_BB_OVERSOLD':25,'RSI_BB_OVERBOUGHT':75,
        'RSI_BB_MIN_VOLUME_RATIO':1.0,'RSI_BB_REQUIRE_DIVERGENCE':False},adx=15)

if batch=='4':
    print(f'\n{"="*80}\n  RSI+BB BATCH 4: Nuevos símbolos\n{"="*80}')
    run('NUEVOS_A base',NUEVOS_A)
    run('NUEVOS_A OS25/OB75',NUEVOS_A,{'RSI_BB_OVERSOLD':25,'RSI_BB_OVERBOUGHT':75})
    run('NUEVOS_A ADX15',NUEVOS_A,adx=15)
    run('NUEVOS_B base',NUEVOS_B)
    run('NUEVOS_B OS25/OB75',NUEVOS_B,{'RSI_BB_OVERSOLD':25,'RSI_BB_OVERBOUGHT':75})
    run('NUEVOS_B ADX15',NUEVOS_B,adx=15)

if batch=='5':
    print(f'\n{"="*80}\n  RSI+BB BATCH 5: Mix\n{"="*80}')
    run('MIX_A base',MIX_A)
    run('MIX_A RELAJADO',MIX_A,{'RSI_BB_OVERSOLD':25,'RSI_BB_OVERBOUGHT':75,
        'RSI_BB_MIN_VOLUME_RATIO':1.0,'RSI_BB_REQUIRE_DIVERGENCE':False},adx=15)
    run('MIX_B base',MIX_B)
    run('MIX_B RELAJADO',MIX_B,{'RSI_BB_OVERSOLD':25,'RSI_BB_OVERBOUGHT':75,
        'RSI_BB_MIN_VOLUME_RATIO':1.0,'RSI_BB_REQUIRE_DIVERGENCE':False},adx=15)
    run('MIX_C base',MIX_C)
    run('MIX_C RELAJADO',MIX_C,{'RSI_BB_OVERSOLD':25,'RSI_BB_OVERBOUGHT':75,
        'RSI_BB_MIN_VOLUME_RATIO':1.0,'RSI_BB_REQUIRE_DIVERGENCE':False},adx=15)

print(f'\n  Uso: ./venv/bin/python bt_rsi_batches.py [1-5]')
