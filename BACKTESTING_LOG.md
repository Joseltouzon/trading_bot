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

### Re-test Backtest Fiel (30 días, TP 0.8%/80%, Trail 0.4%/0.22%)

**Símbolos base: DOGE+LINK+TIA+ORDI+PENDLE**

**Variaciones de EMA + ADX:**
| EMA | ADX | T | WR | PF | PnL |
|-----|-----|---|-----|-----|-----|
| 9/21 | 17 | 84 | 49% | 2.19 | **+$94.98** ✅✅ |
| 9/21 | 20 | 68 | 50% | 2.31 | +$81.20 |
| 12/26 | 17 | 75 | 51% | 2.21 | +$93.17 |
| 20/50 | 17 | 69 | 48% | 1.86 | +$61.07 |
| 15/40 | 17 | 71 | 48% | 1.88 | +$64.30 |
| 25/50 | 17 | 39 | 46% | 2.02 | +$44.58 |

**Combinaciones con RSI:**
| Config | T | WR | PF | PnL |
|--------|---|-----|-----|-----|
| 12/26 ADX17 RSI OB75 | 83 | 49% | 2.10 | **+$93.51** |
| 9/21 ADX20 | 68 | 50% | 2.31 | +$81.20 |
| 20/50 ADX17 RSI OB80 | 81 | 47% | 1.75 | +$63.12 |

**Nuevos símbolos:** Todos pierden dinero. MIX_A (DOGE+LINK+ORD+PENDLE+AVAX) = +$88.70

**GANADORES:**
1. **EMA 9/21 + ADX 17** = +$94.98, PF 2.19, WR 49%, 84 trades
2. **EMA 12/26 + ADX 17 + RSI OB75** = +$93.51, PF 2.10, WR 49%, 83 trades

Cambiar desde dashboard:
- `EMA_BREAKOUT_FAST`: 25 → **9** (o 12)
- `EMA_BREAKOUT_SLOW`: 50 → **21** (o 26)
- `ADX_MIN`: 25 → **17**

### Pruebas anteriores (backtest viejo, NO válidas)

<details>
<summary>Click para ver pruebas anteriores</summary>

| EMA | ADX | Vol | Trades | WR | PnL | Nota |
|-----|-----|-----|--------|-----|-----|------|
| 9/21 | 20 | 1.2 | 65 | 63% | $+1.05 | Default viejo |
| **21/55** | **30** | **1.5** | **17** | **82.35%** | **$+21.64** | **GANADOR (viejo)** |
| 20/50 | 30 | 1.5 | 17 | 76.47% | $+18.83 | Bueno |
| 12/26 | 30 | 1.5 | 15 | 73.33% | $+14.16 | OK |

</details>

---

## MACD Momentum (15m)

### Re-test Backtest Fiel (30 días, TP 0.8%/80%, Trail 0.4%/0.22%)

**Símbolos actuales: SAND+PENDLE+XRP+AVAX+SOL**

**Parámetros MACD (con ADX variando):**
| Config | T | WR | PF | PnL |
|--------|---|-----|-----|-----|
| BASE 12/26/9 ADX25 Vol3 | 26 | 46% | 1.24 | +$4.94 |
| 12/26/9 ADX25 Vol2 | 110 | 45% | 1.08 | +$7.71 |
| **ADX18+Vol1.5** | **189** | **41%** | **1.20** | **+$34.77** |
| ADX15+Vol1.5+RSI50/50 | 190 | 41% | 1.26 | **+$47.96** ✅ |
| ADX20+Vol2+RSI50/50 | 111 | 45% | 1.20 | +$20.06 |

**Nuevos símbolos:**
| Config | Símbolos | T | WR | PF | PnL |
|--------|----------|---|-----|-----|-----|
| NUEVOS_B ADX20+Vol2 | ETH+NEAR+SUI+OP+WIF | 119 | 46% | 1.49 | +$46.67 |
| MIX_B RELAJADO | AVAX+SOL+ARB+ORDI+DOGE | 136 | 46% | 1.33 | +$40.87 |

**GANADOR: ADX 15 + Vol 1.5 + RSI 50/50 + símbolos actuales = +$47.96, PF 1.26, WR 41%**
Cambiar desde dashboard:
- `MACD_ADX_MIN`: 25 → **15**
- `MACD_MIN_VOLUME_RATIO`: 3.0 → **1.5**
- `MACD_RSI_BULL_MIN`: 55 → **50**
- `MACD_RSI_BEAR_MAX`: 45 → **50**

### Pruebas anteriores (backtest viejo, NO válidas)
<details><summary>Click</summary>

| MACD | ADX | Vol | Trades | W/L | WR | PnL |
|------|-----|-----|--------|-----|-----|-----|
| 12/26/9 | 25 | 2.0 | 161 | 89/72 | 55.28% | $+19.76 |
| 12/26/9 | 30 | 3.0 | 55 | 38/17 | 69.09% | $+25.34 |
| 12/26/9 | 30 | 4.0 | 31 | 23/8 | 74.19% | $+19.51 |

</details>

---

## Structure Break (5m)

### Re-test Backtest Fiel (30 días, TP 0.8%/80%, Trail 0.4%/0.22%)

**Símbolos actuales: FIL+DOGE+APT+WIF+ATOM**

**Parámetros individuales:**
| Config | T | WR | PF | PnL |
|--------|---|-----|-----|-----|
| BASE (Sw5/Look60/Bk10/Vol2/ADX15) | 218 | 47% | 1.24 | +$64.28 |
| **BREAK 5** | **164** | **51%** | **1.46** | **+$96.96** ✅✅ |
| LOOKBACK 30 | 86 | 52% | 1.73 | +$73.28 |
| TOL 0.8 | 257 | 47% | 1.23 | +$71.93 |
| BREAK 15 | 250 | 46% | 1.21 | +$66.59 |
| SWING 7 | 288 | 43% | 1.06 | +$21.62 |
| BREAK_VOL 1.5 | 357 | 45% | 1.09 | +$33.81 |
| RETEST 5 | 331 | 41% | 0.96 | -$12.01 ❌ |

**Nuevos símbolos:**
| Config | Símbolos | T | WR | PF | PnL |
|--------|----------|---|-----|-----|-----|
| NUEVOS_B restrictivo | AVAX+PENDLE+NEAR+PEPE+TIA | 14 | 50% | 5.67 | +$69.69 |
| NUEVOS_B base | AVAX+PENDLE+NEAR+PEPE+TIA | 207 | 44% | 1.26 | +$62.44 |

**GANADOR: BREAK 5 (STRUCTURE_BREAK_LOOKBACK 10→5) + símbolos actuales = +$96.96, PF 1.46, WR 51%**
Cambiar desde dashboard:
- `STRUCTURE_BREAK_LOOKBACK`: 10 → **5**

### Pruebas anteriores (backtest viejo, NO válidas)
<details><summary>Click</summary>

| Swing | Look | Break | Vol | ADX | Trades | W/L | WR | PnL |
|-------|------|-------|-----|-----|--------|-----|-----|-----|
| 5 | 60 | 10 | 2.0 | 15 | 197 | 110/85 | 56.41% | $+51.01 |
| 3 | 30 | 5 | 3.0 | 25 | 17 | 14/3 | 82.35% | $+11.60 |

</details>

---

## Stop Hunt (5m)

### Re-test Backtest Fiel (30 días, TP 0.8%/80%, Trail 0.4%/0.22%)

**Parámetros individuales (5 símbolos actuales: PEPE+AVAX+ORDI+SUI+WIF):**
| Parámetro | Base | Alt | T | WR | PF | PnL |
|-----------|------|-----|---|-----|-----|-----|
| WICK_PCT | 0.20 | 0.15 | 9 | 67% | 1.28 | +$4.04 |
| WICK_PCT | 0.20 | 0.25 | 9 | 67% | 1.28 | +$4.04 |
| REJECTION_RATIO | 0.7 | 0.5 | 9 | 67% | 1.28 | +$4.04 |
| MIN_ZONES | 2 | 1 | 5 | 60% | 0.14 | -$56.38 ❌ |
| MIN_ZONES | 2 | 3 | 10 | 60% | 1.14 | +$2.28 |
| MIN_VOLUME_RATIO | 1.5 | 1.2 | 14 | 64% | 1.42 | +$7.84 ✅ |
| **USE_EMA_FILTER** | **True** | **False** | **26** | **77%** | **4.70** | **+$48.64** ✅✅ |
| MOMENTUM_BARS | 3 | 2 | 10 | 70% | 1.56 | +$8.26 ✅ |
| **ADX_MIN** | **18** | **14** | **14** | **79%** | **1.95** | **+$14.32** ✅ |

**Combinaciones con símbolos actuales:**
| Config | T | WR | PF | PnL |
|--------|---|-----|-----|-----|
| EMA_OFF+ADX14 | 39 | 79% | 5.04 | +$76.18 |
| EMA_OFF+ADX14+Vol1.2 | 33 | 73% | 3.64 | +$62.02 |
| TODO RELAJADO | 34 | 74% | 3.76 | +$65.50 |

**Nuevos símbolos (XRP+TIA+ETH+PENDLE+BTC):**
| Config | T | WR | PF | PnL |
|--------|---|-----|-----|-----|
| Base | 6 | 100% | - | +$35.27 |
| EMA_OFF | 23 | 74% | 5.42 | +$64.01 |
| **TODO RELAJADO** | **38** | **74%** | **3.69** | **+$78.34** ✅ |

**GANADOR: EMA OFF + ADX 14 + Vol 1.2 + XRP+TIA+ETH+PENDLE+BTC = +$78.34, PF 3.69, WR 74%**
Cambiar desde dashboard:
- `STOP_HUNT_USE_EMA_FILTER`: True → False
- `STOP_HUNT_ADX_MIN`: 18 → 14
- `STOP_HUNT_MIN_VOLUME_RATIO`: 1.5 → 1.2
- Símbolos: PEPE+AVAX+ORDI+SUI+WIF → XRP+TIA+ETH+PENDLE+BTC

### Pruebas anteriores (backtest viejo, NO válidas)
<details><summary>Click</summary>

| Wick | Rej | Vol | ADX | Trades | W/L | WR | PnL |
|------|-----|-----|-----|--------|-----|-----|-----|
| 0.20 | 0.7 | 1.5 | 18 | 14 | 9/3 | 75.00% | $+8.36 | Default |
| 0.15 | 0.6 | 1.5 | 18 | 12 | 9/3 | 75.00% | $+1.27 |
| 0.15 | 0.6 | 2.0 | 18 | 4 | 3/1 | 75.00% | $-0.36 |

</details>

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

### Re-test Backtest Fiel (30 días, TP 0.8%/80%, Trail 0.4%/0.22%)

**Símbolos actuales: NEAR+OP+BTC+LINK+XRP**
| Config | T | WR | PF | PnL |
|--------|---|-----|-----|-----|
| **BASE** | **28** | **61%** | **2.35** | **+$21.71** |
| ATR_PCT 20 | 35 | 57% | 2.06 | +$22.79 |
| ATR20+BB30 | 35 | 57% | 2.06 | +$22.79 |
| EMA 25/60 | 31 | 58% | 1.83 | +$15.42 |
| VOL 1.2 | 42 | 43% | 1.27 | +$8.83 |

**Nuevos símbolos no superan a los actuales.** Config actual es la mejor.
No cambiar nada desde dashboard.

---

## Volatility Regime (1h)

### Re-test Backtest Fiel (30 días, TP 0.8%/80%, Trail 0.4%/0.22%)

**Símbolos actuales: XRP+BTC+DOGE+OP+FIL**
| Config | T | WR | PF | PnL |
|--------|---|-----|-----|-----|
| BASE (Low25/H75/Vol1.5/ADX22) | 49 | 53% | 1.65 | +$20.95 |
| **VOL 1.2** | **62** | **58%** | **2.03** | **+$38.75** ✅ |
| Low30/H80 | 54 | 54% | 1.66 | +$23.28 |
| EMA 15/40 | 51 | 53% | 1.78 | +$27.16 |
| MOM 5 | 45 | 53% | 1.80 | +$23.35 |
| Low20/H75+VOL1.2 | 53 | 57% | 1.82 | +$27.53 |

**Nuevos símbolos:** NUEVOS_A (ETH+SOL+NEAR+LINK+AVAX) = +$24.10
MIX_A (XRP+ETH+BTC+SOL+DOGE) = +$24.24
No superan significativamente a los actuales.

**GANADOR: VOL 1.2 + símbolos actuales = +$38.75, PF 2.03, WR 58%**
Cambiar desde dashboard:
- `VR_VOLUME_RATIO_MIN`: 1.5 → **1.2**

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
