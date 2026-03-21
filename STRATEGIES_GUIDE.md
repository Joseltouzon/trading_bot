# Guía de Estrategias — Beast Money Maker

## Arquitectura Multi-Timeframe

El bot ejecuta **3 estrategias en paralelo** (mode auto):

| Estrategia | Timeframe | Símbolos |
|-----------|-----------|----------|
| RSI+BB Reversion | **5m** | XRP, PEPE, AVAX, TIA, ORDI, TAO |
| Stop Hunt | **5m** | XRP, PEPE, AVAX, TIA, ORDI |
| MACD Momentum | **15m** | PENDLE, XRP, AVAX, SOL, RUNE |

`MarketCache` mantiene DFs separados por timeframe. `SignalEngine` ejecuta las 3 estrategias, cada una con su DF correcto.

---

## Backtest Final (símbolos actuales, 30 días)

```
                    Trades  T/día   T/sem   WR      PF      Return  PnL
================================================================
RSI+BB (5m):         65     2.17    15.1   64.6%   2.35    +0.74%  +$1.41
Stop Hunt (5m):      11     0.37     2.6   81.8%   4.25    +0.19%  +$0.36
MACD (15m):          99     3.30    23.0   56.6%   2.82    +1.47%  +$2.76
================================================================
TOTAL:              175     5.84    40.7    -       -      +2.40%  +$4.53
================================================================
PnL incluye leverage 5x. Sharpe promedio ~4.5.
```

---

## 1. RSI + Bollinger Band Mean Reversion (5m) ⭐

Captura sobreextensiones de precio combinando RSI extremes, Bollinger Bands y divergencias.

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

### Rendimiento por símbolo
| Símbolo | Trades | WR | PnL |
|---------|--------|-----|------|
| PEPEUSDT | 8 | 100% | +$0.36 |
| AVAXUSDT | 14 | 57% | +$0.27 |
| XRPUSDT | 16 | 56% | +$0.22 |
| TIAUSDT | 10 | 70% | +$0.21 |
| ORDIUSDT | 10 | 60% | +$0.18 |
| TAOUSDT | 7 | 57% | +$0.17 |

---

## 2. Stop Hunt (5m) 🏆

Estrategia institucional que detecta hunts de liquidez en swing levels.

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

### Nota
Baja frecuencia (11 trades/mes) pero la más precisa (WR 81.8%, PF 4.25). No ajustar parámetros — la calidad es la prioridad.

---

## 3. MACD Momentum + Volume Spike (15m) 💰

Captura tendencias fuertes que RSI+BB ignora.

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

### Rendimiento por símbolo
| Símbolo | Trades | WR | PnL |
|---------|--------|-----|------|
| SOLUSDT | 27 | 56% | +$0.87 |
| PENDLEUSDT | 16 | 69% | +$0.71 |
| XRPUSDT | 22 | 59% | +$0.46 |
| AVAXUSDT | 19 | 53% | +$0.36 |
| RUNEUSDT | 15 | 47% | +$0.36 |

---

## 4. Configuración desde el Dashboard

```
strategy_mode: "auto" (ejecuta RSI+BB + Stop Hunt + MACD)
Cada estrategia tiene sus propios símbolos configurados en su tab.
```

---

## Archivos Clave

```
strategy/rsi_bb_reversion.py    # RSI+BB (5m)
strategy/stop_hunt.py           # Stop Hunt (5m)
strategy/macd_momentum.py       # MACD Momentum (15m)
strategy/signal_engine.py       # Motor multi-estrategia
strategy/indicators.py          # EMA, ATR, ADX, RSI, Bollinger, MACD
execution/event_loop.py         # Guards y ejecución
datafeed/market_cache.py        # Cache multi-timeframe
config.py                      # Todos los parámetros
```
