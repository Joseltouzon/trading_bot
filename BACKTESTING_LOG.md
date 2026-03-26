# Backtesting Log — Variaciones Probadas

Última actualización: 2026-03-25

## Configuración del bot actual

- Capital: $170
- Leverage: 5x
- Risk: 1.0%
- Max posiciones: 2
- Trailing: activa 0.40%, distancia 0.30%
- TP: toma 80% a 0.80%

---

## EMA Breakout (15m)

### Combinaciones EMAs probadas (30 días, trailing 0.30%)

| EMA | ADX | Vol | Trades | WR | PnL | Nota |
|-----|-----|-----|--------|-----|-----|------|
| 9/21 | 20 | 1.2 | 65 | 63% | $+1.05 | Default viejo |
| **21/55** | **30** | **1.5** | **17** | **82.35%** | **$+21.64** | **GANADOR** |
| 20/50 | 30 | 1.5 | 17 | 76.47% | $+18.83 | Bueno |
| 12/26 | 30 | 1.5 | 15 | 73.33% | $+14.16 | OK |
| 21/55 | 30 | 2.0 | 8 | 62.50% | $+2.63 | Pocos trades |
| 20/50 | 25 | 1.5 | 37 | 54.05% | $+26.66 | Más trades, menor WR |
| 12/26 | 25 | 1.5 | 38 | 57.89% | $+30.92 | Más trades, menor WR |

### Con nuevos trailing/TP (0.30%/0.40%/80%)

| EMA | ADX | Vol | Trades | WR | PF | PnL | DD |
|-----|-----|-----|--------|-----|-----|-----|-----|
| **21/55** | **30** | **1.5** | **18** | **83.33%** | **7.47** | **$+19.72** | **1.28%** |

---

## MACD Momentum (15m)

### Variaciones probadas (30 días, trailing 0.30%)

| MACD | ADX | Vol | Trades | W/L | WR | PnL |
|------|-----|-----|--------|-----|-----|-----|
| 12/26/9 | 25 | 2.0 | 161 | 89/72 | 55.28% | $+19.76 |
| 12/26/9 | 25 | 3.0 | 85 | 52/33 | 61.18% | $+25.70 |
| 12/26/9 | 25 | 4.0 | 45 | 30/15 | 66.67% | $+20.96 |
| 12/26/9 | 30 | 2.0 | 118 | 68/50 | 57.63% | $+18.83 |
| **12/26/9** | **30** | **3.0** | **55** | **38/17** | **69.09%** | **$+25.34** |
| **12/26/9** | **30** | **4.0** | **31** | **23/8** | **74.19%** | **$+19.51** |
| 12/26/9 | 35 | 4.0 | 15 | 11/4 | 73.33% | $+12.57 |
| 8/17/7 | 30 | 4.0 | 30 | 21/9 | 70.00% | $+17.13 |
| 19/39/9 | 25 | 4.0 | 46 | 30/16 | 65.22% | $+22.37 |

### GANADOR: MACD 12/26/9, ADX 30, Vol 4.0 = 74% WR, $+19.51

---

## Structure Break (5m)

### Variaciones probadas (30 días, trailing 0.30%)

| Swing | Look | Break | Vol | ADX | Trades | W/L | WR | PnL |
|-------|------|-------|-----|-----|--------|-----|-----|-----|
| 5 | 60 | 10 | 2.0 | 15 | 197 | 110/85 | 56.41% | $+51.01 | Default |
| **3** | **30** | **5** | **3.0** | **25** | **17** | **14/3** | **82.35%** | **$+11.60** |
| 3 | 30 | 5 | 3.0 | 20 | 18 | 14/4 | 77.78% | $+10.51 |
| 3 | 30 | 5 | 3.0 | 15 | 23 | 16/7 | 69.57% | $+9.24 |
| 3 | 30 | 5 | 2.0 | 20 | 71 | 49/22 | 69.01% | $+25.66 |
| 3 | 30 | 5 | 2.0 | 25 | 63 | 43/20 | 68.25% | $+22.95 |
| 5 | 60 | 10 | 2.5 | 20 | 61 | - | 49% | $+0.67 |
| 5 | 60 | 10 | 2.5 | 18 | 91 | - | 49% | $+2.97 |
| 5 | 60 | 10 | 2.2 | 17 | 123 | - | 54% | $+13.48 |

### GANADOR: Swing 3, Look 30, Break 5, Vol 3.0, ADX 25 = 82% WR, $+11.60

---

## Stop Hunt (5m)

### Variaciones probadas (30 días, trailing 0.30%)

| Wick | Rej | Vol | ADX | Trades | W/L | WR | PnL |
|------|-----|-----|-----|--------|-----|-----|-----|
| 0.20 | 0.7 | 1.5 | 18 | 14 | 9/3 | 75.00% | $+8.36 | Default |
| 0.15 | 0.6 | 1.5 | 18 | 12 | 9/3 | 75.00% | $+1.27 |
| 0.15 | 0.6 | 2.0 | 18 | 4 | 3/1 | 75.00% | $-0.36 |

### No mejoró significativamente con trailing 0.30%

---

## RSI+BB Reversion (5m)

### Variaciones probadas (30 días, trailing 0.30%)

| OS | OB | BB | Vol | ADX | Trades | WR | PnL |
|----|----|-----|-----|-----|--------|-----|-----|
| 25 | 75 | 2.0 | 1.5 | 15 | 38 | 66.67% | $+12.42 | Default |
| 20 | 70 | 1.5 | 1.5 | 25 | 50 | 62.00% | $+3.47 |
| 20 | 70 | 1.5 | 1.5 | 20 | 72 | 56.94% | $-1.05 |
| 20 | 70 | 1.5 | 1.5 | 15 | 79 | 56.96% | $-1.32 |
| 20 | 70 | 1.5 | 2.0 | 15 | 46 | 52.17% | $-3.94 |

### No funciona bien con trailing 0.30% — DESACTIVADA

---

## Volatility Squeeze (1h)

### Configuración actual (60 días)

| Parámetro | Valor |
|-----------|-------|
| ATR Percentile | 15 |
| BB Width Percentile | 25 |
| Volume Ratio | 1.5 |
| ADX Min | 15 |
| SL ATR Mult | 1.5 |
| EMA | 20/50 |

| Símbolos | Trades | WR | PF | PnL |
|----------|--------|-----|-----|-----|
| NEAR, OP, BTC, LINK, XRP | 77 | 88.61% | 3.46 | $+35.64 |

---

## Volatility Regime (1h)

### Variaciones probadas (60 días)

| Variante | Low | High | Vol | ADX | Bars | Trades | WR | PF | PnL |
|----------|-----|------|-----|-----|------|--------|-----|-----|-----|
| Baseline | 20 | 70 | 1.3 | 18 | 3 | 149 | 81% | 2.58 | $+42.12 |
| **A** | **25** | **75** | **1.5** | **22** | **4** | **109** | **84%** | **3.25** | **$+37.80** |
| B | 15 | 80 | 1.8 | 25 | 4 | 51 | 76% | 1.33 | $+3.52 |
| C | 20 | 75 | 1.5 | 22 | 4 | 102 | 85% | 3.35 | $+34.58 |

### GANADOR: Variante A (Low 25, High 75, Vol 1.5, ADX 22, Bars 4)

---

## Estrategias Descartadas

| Estrategia | TF | Mejor PF | Problema |
|------------|-----|----------|----------|
| Liquidation Cascade | 1h | 1.23 | Trailing muy apretado vs SL |
| Momentum Divergence | 1h | 0.36 | 0% WR, filtros muy estrictos |
| Smart Money Flow | 1h | inf | Solo 2 trades |
| Volatility Breakout | 1h | 1.07 | PF marginal |
| Funding Rate Extreme | 1h | 1.26 | Avg Win muy bajo |
| MTF Trend Alignment | 1h | 1.32 | Demasiado sensible a filtros |

---

## Configuración Final Recomendada

| Estrategia | Parámetros clave | Trades/mes | WR | PnL/mes |
|------------|------------------|------------|-----|---------|
| EMA | 21/55, ADX 30, Vol 1.5 | ~18 | 83% | ~$20 |
| MACD | 12/26/9, ADX 30, Vol 4.0 | ~31 | 74% | ~$20 |
| Structure | Swing 3, Look 30, Break 5, Vol 3.0, ADX 25 | ~17 | 82% | ~$12 |
| Vol Squeeze | Default | ~39 | 89% | ~$18 |
| Vol Regime | Variant A | ~55 | 84% | ~$19 |
| Stop Hunt | Default | ~14 | 75% | ~$4 |
| RSI+BB | DESACTIVADA | - | - | - |

**Total estimado: ~174 trades/mes, WR promedio 81%, PnL ~$93/mes**

---

## Lecciones aprendidas

1. Trailing 0.30% mejora significativamente el WR y PF vs 0.35%
2. TP 80% a 0.80% captura ganancias antes de reversión
3. EMAs más largas (21/55, 20/50) dan mejor WR que cortas (9/21)
4. ADX más alto (25-30) filtra señales débiles
5. RSI+BB no funciona con trailing ajustado (mean-reversion necesita espacio)
6. Estrategias contrarian no funcionan en 1h
7. Volatility Squeeze es la mejor estrategia (89% WR)
8. Más posiciones simultáneas = menos riesgo % pero mismo PnL $
