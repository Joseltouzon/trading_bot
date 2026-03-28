#!/usr/bin/env python3
"""Test EMA Breakout: variar cada parámetro de a uno."""
import config as CFG
exec(open('bt_test_combos.py').read().split('def main')[0])

syms = ['DOGEUSDT','LINKUSDT','TIAUSDT','ORDIUSDT','PENDLEUSDT']

# Valores base (actuales del config)
base = {
    'EMA_BREAKOUT_FAST': 25,
    'EMA_BREAKOUT_SLOW': 50,
    'EMA_MIN_SLOPE_PCT': 0.04,
    'EMA_RSI_OVERSOLD': 30,
    'EMA_RSI_OVERBOUGHT': 70,
    'EMA_MIN_VOLUME_RATIO': 1.2,
    'EMA_MIN_ATR_PCT': 0.15,
    'EMA_MOMENTUM_BARS': 3,
    'EMA_MIN_MOMENTUM_PCT': 0.10,
}
adx_base = 25

# Variaciones a probar
tests = [
    ('EMA_BREAKOUT_FAST', [15, 20, 25, 30]),
    ('EMA_BREAKOUT_SLOW', [40, 50, 60]),
    ('EMA_MIN_SLOPE_PCT', [0.02, 0.04, 0.06]),
    ('EMA_RSI_OVERSOLD', [25, 30, 35]),
    ('EMA_RSI_OVERBOUGHT', [65, 70, 75]),
    ('EMA_MIN_VOLUME_RATIO', [1.0, 1.2, 1.5]),
    ('EMA_MIN_ATR_PCT', [0.10, 0.15, 0.20]),
    ('EMA_MOMENTUM_BARS', [2, 3, 5]),
    ('EMA_MIN_MOMENTUM_PCT', [0.05, 0.10, 0.15]),
    ('ADX_MIN', [20, 25, 30]),
]

def apply_base():
    for k, v in base.items():
        setattr(CFG, k, v)
    CFG.ADX_MIN = adx_base

print(f'EMA BREAKOUT — Test por parámetro | 5 símbolos: {syms}')
print(f'Base: EMA 25/50, ADX 25, slope 0.04, RSI 30/70, vol 1.2, ATR 0.15%, mom 3 bars 0.10%')
print(f'TP: 0.8%/80% | Trail: 0.4%/0.22%')
print(f'{"="*90}')

results = []

for param_name, values in tests:
    print(f'\n  {param_name}:')
    for val in values:
        apply_base()
        setattr(CFG, param_name, val)
        r = run_test('ema_breakout', syms, '15m', adx_min=getattr(CFG,'ADX_MIN',25), trail_act=0.4, trail_pct=0.22)
        wr = r['wr']
        tag = ' ← BASE' if val == base.get(param_name, adx_base) else ''
        print(f'    = {val:<8} T={r["trades"]:>3} W={r["wins"]:>2} WR={wr:>4.0f}% PF={r["pf"]:>5.2f} PnL=${r["pnl"]:>+8.2f}{tag}')
        results.append((param_name, val, r['trades'], r['wins'], r['wr'], r['pf'], r['pnl']))

apply_base()
print(f'\n{"="*90}')
print(f'Config restaurada a valores base')
print(f'\nRESUMEN - Mejor valor por parámetro:')
print(f'{"Parámetro":<25} {"Base":>8} {"Mejor":>8} {"Δ PnL":>10}')
print(f'{"-"*55}')

for param_name, values in tests:
    param_results = [(v, t, w, wr, pf, pnl) for p, v, t, w, wr, pf, pnl in results if p == param_name]
    best = max(param_results, key=lambda x: x[5])
    base_val = base.get(param_name, adx_base)
    base_result = next((x for x in param_results if x[0] == base_val), None)
    delta = best[5] - base_result[5] if base_result else 0
    marker = ' ✅' if best[0] == base_val else ' ⚠️ CAMBIAR'
    print(f'{param_name:<25} {str(base_val):>8} {str(best[0]):>8} {delta:>+10.2f}{marker}')
