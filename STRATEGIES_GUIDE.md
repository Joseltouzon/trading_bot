# Guía de Estrategias — Beast Money Maker

## Comparación Final (30 días, leverage 5x)

```
                    Símbolos T/mes  T/día   WR      PF      Ret     DD
================================================================
RSI+BB (5m):         6       65     2.17    64.6%   2.35    +0.74%  0.26%
Stop Hunt (5m):      5       11     0.37    81.8%   4.25    +0.19%  0.07%
MACD (15m):          5       99     3.30    56.6%   2.82    +1.47%  0.14%
EMA (15m):           6       65     2.17    63.1%   3.97    +1.05%  0.20%
Structure (5m):      5      215     7.17    59.1%   2.22    +2.13%  0.27%
================================================================
SUBTOTAL 5m/15m:    27      455    15.17      -       -     +5.58%  0.94%
================================================================
Vol Squeeze (1h):    5       78     2.60    88.0%   3.46   +19.93%  4.37%
================================================================
```

Mode auto ejecuta 5 estrategias (5m/15m). Volatility Squeeze opera por separado en 1h.

---

## 1. RSI + Bollinger Band Mean Reversion (5m)

### Símbolos
XRPUSDT, 1000PEPEUSDT, AVAXUSDT, TIAUSDT, ORDIUSDT, TAOUSDT

### Parámetros clave
| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| RSI_BB_OVERSOLD | 20 | RSI zona sobreventa |
| RSI_BB_OVERBOUGHT | 80 | RSI zona sobrecompra |
| RSI_BB_MIN_VOLUME_RATIO | 1.2 | Volumen mínimo |
| RSI_BB_ADX_MIN | 12.0 | ADX mínimo |
| RSI_BB_SL_ATR_MULT | 2.5 | ATR multiplier SL |
| RSI_BB_REQUIRE_DIVERGENCE | True | Requiere divergencia real |

### 3 Triggers
1. RSI crossover + BB rejection
2. Classic divergence (swing points)
3. Extreme RSI (< 20 / > 80) + vela direccional

---

## 2. Stop Hunt (5m)

### Símbolos
XRPUSDT, 1000PEPEUSDT, AVAXUSDT, TIAUSDT, ORDIUSDT

### Parámetros clave
| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| STOP_HUNT_WICK_PCT | 0.20 | Mecha mínima hunt |
| STOP_HUNT_REJECTION_RATIO | 0.7 | Body/wick rechazo |
| STOP_HUNT_MIN_ZONES | 2 | Mínimo zonas de liquidez |
| STOP_HUNT_MIN_VOLUME_RATIO | 1.5 | Volumen mínimo |
| STOP_HUNT_ATR_MULT_SL | 2.0 | ATR multiplier SL |

**Nota:** Baja frecuencia pero la más precisa (WR 81.8%, PF 4.25).

---

## 3. MACD Momentum + Volume Spike (15m)

### Símbolos
PENDLEUSDT, XRPUSDT, AVAXUSDT, SOLUSDT, RUNEUSDT

### Parámetros clave
| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| MACD_FAST/SLOW/SIGNAL | 12/26/9 | MACD settings |
| MACD_MIN_VOLUME_RATIO | 3.0 | Volume spike (3x media) |
| MACD_RSI_BULL_MIN | 55 | RSI mínimo LONG |
| MACD_RSI_BEAR_MAX | 45 | RSI máximo SHORT |
| MACD_ADX_MIN | 25.0 | ADX mínimo |
| MACD_SL_ATR_MULT | 2.0 | ATR multiplier SL |

---

## 4. EMA Breakout (15m, 25/50 + ADX 25)

### Símbolos
DOGEUSDT, LINKUSDT, TIAUSDT, ORDIUSDT, PENDLEUSDT, AVAXUSDT

### Parámetros clave
| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| EMA_BREAKOUT_FAST | 25 | EMA rápida |
| EMA_BREAKOUT_SLOW | 50 | EMA lenta |
| ADX_MIN | 25 | ADX mínimo (optimizado) |
| EMA_MIN_SLOPE_PCT | 0.04 | Pendiente mínima EMA |
| EMA_RSI_OVERBOUGHT | 70 | No LONG si RSI > 70 |
| EMA_RSI_OVERSOLD | 30 | No SHORT si RSI < 30 |
| MIN_BODY_RATIO | 0.50 | Ratio mínimo cuerpo/rango |
| EMA_SL_ATR_MULT | 2.0 | ATR multiplier SL |

### Rendimiento por símbolo (30d 15m, ADX 25)
| Símbolo | Trades | WR | PF | Ret |
|---------|--------|-----|------|-----|
| ORDIUSDT | 18 | 44% | 2.86 | +0.21% |
| LINKUSDT | 15 | 53% | 2.60 | +0.14% |
| PENDLEUSDT | 10 | 50% | 2.51 | +0.10% |
| TIAUSDT | 20 | 50% | 2.41 | +0.20% |
| AVAXUSDT | 7 | 57% | 2.28 | +0.06% |
| DOGEUSDT | 19 | 53% | 2.12 | +0.15% |

---

## 5. Structure Break + Retest (5m)

### Símbolos
FILUSDT, DOGEUSDT, APTUSDT, WIFUSDT, ATOMUSDT

### Parámetros clave
| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| STRUCTURE_SWING_WINDOW | 5 | Ventana para swing highs/lows |
| STRUCTURE_LOOKBACK | 60 | Velas para buscar swings |
| STRUCTURE_BREAK_LOOKBACK | 10 | Velas para buscar ruptura |
| STRUCTURE_MIN_BREAK_VOLUME | 2.0 | Volumen mínimo en ruptura (2x) |
| STRUCTURE_RETEST_LOOKBACK | 8 | Velas después de ruptura para retest |
| STRUCTURE_RETEST_TOLERANCE_ATR | 0.5 | Tolerancia de retest (ATR) |
| STRUCTURE_SL_BUFFER_ATR | 1.0 | Buffer ATR para SL |
| STRUCTURE_ADX_MIN | 15.0 | ADX mínimo |

### Lógica
1. **Estructura rota**: precio cierra por encima del swing high (LONG) o por debajo del swing low (SHORT)
2. **Volumen spike**: la vela de ruptura tiene volumen 2x+ (institucionales entrando)
3. **Retest**: precio vuelve a tocar el nivel roto y se rechaza
4. **Entry**: en el retest, no en el breakout

---

## 6. Volatility Squeeze + Momentum Exhaustion (1h) 🆕

### Símbolos (Top 5 backtested 60 días)
NEARUSDT, OPUSDT, BTCUSDT, LINKUSDT, XRPUSDT

### Parámetros clave
| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| VOL_SQUEEZE_ATR_PERIOD | 14 | Período del ATR |
| VOL_SQUEEZE_ATR_LOOKBACK | 100 | Velas para percentil histórico |
| VOL_SQUEEZE_ATR_PERCENTILE | 15 | ATR en bottom 15% = compresión |
| VOL_SQUEEZE_BB_PERIOD | 20 | Período Bollinger Bands |
| VOL_SQUEEZE_BB_WIDTH_PERCENTILE | 25 | BB Width comprimido |
| VOL_SQUEEZE_RSI_PERIOD | 14 | Período RSI |
| VOL_SQUEEZE_RSI_OVERSOLD | 30 | Zona oversold |
| VOL_SQUEEZE_RSI_OVERBOUGHT | 70 | Zona overbought |
| VOL_SQUEEZE_MIN_VOLUME_RATIO | 1.5 | Volumen mínimo |
| VOL_SQUEEZE_ADX_MIN | 15.0 | ADX mínimo |
| VOL_SQUEEZE_SL_ATR_MULT | 1.5 | ATR multiplier para SL |
| VOL_SQUEEZE_EMA_FAST/SLOW | 20 / 50 | EMAs para tendencia |

### Lógica
1. **Compresión detectada**: ATR en percentil bajo (< 15%) O BB Width comprimido (< 25%)
2. **Dirección del swing**: precio de las últimas 20 velas indica BULL o BEAR
3. **Tendencia EMA**: EMA 20 > EMA 50 = BULL, EMA 20 < EMA 50 = BEAR
4. **Entry**: compresión + swing direction + EMA trend confirmados

### Resultados Backtesting (60 días, 1h, $170, 5x)

| Símbolo | Trades | WR | PnL | Return |
|---------|--------|-----|-----|--------|
| NEARUSDT | 13 | 92% | $+9.72 | +5.72% |
| OPUSDT | 22 | 95% | $+8.08 | +4.75% |
| BTCUSDT | 14 | 79% | $+7.26 | +4.27% |
| LINKUSDT | 12 | 92% | $+5.60 | +3.29% |
| XRPUSDT | 17 | 82% | $+3.22 | +1.89% |
| **TOTAL** | **78** | **88%** | **$+33.88** | **+19.93%** |

| Salida | Cantidad | % |
|--------|----------|---|
| TRAILING | 50 | 64% |
| TAKE_PROFIT | 16 | 21% |
| STOP_LOSS | 12 | 15% |

---

## Archivos Clave

```
strategy/rsi_bb_reversion.py    # RSI+BB (5m)
strategy/stop_hunt.py           # Stop Hunt (5m)
strategy/ema_adx_breakout.py    # EMA Breakout (15m, 25/50)
strategy/macd_momentum.py       # MACD Momentum (15m)
strategy/structure_break.py     # Structure Break (5m)
strategy/volatility_squeeze.py  # Volatility Squeeze (1h) 🆕
strategy/signal_engine.py       # Motor multi-estrategia (6 en paralelo)
strategy/indicators.py          # EMA, ATR, ADX, RSI, Bollinger, MACD
execution/event_loop.py         # Guards y ejecución
datafeed/market_cache.py        # Cache multi-timeframe (5m, 15m, 1h)
config.py                      # Todos los parámetros
```
