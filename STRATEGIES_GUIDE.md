# Guía de Estrategias — Beast Money Maker

## Arquitectura Multi-Timeframe

El bot ejecuta **4 estrategias en paralelo** por cada símbolo:

| Estrategia | Timeframe | Tipo |
|-----------|-----------|------|
| RSI+BB Reversion | **5m** | Mean-reversion |
| Stop Hunt | **5m** | Mean-reversion institucional |
| EMA Breakout | **15m** | Trend-following |
| MACD Momentum | **15m** | Momentum/Trend |

El `MarketCache` mantiene DFs separados por timeframe. `SignalEngine` ejecuta las 4 estrategias, cada una con su DF correcto.

---

## 1. RSI + Bollinger Band Mean Reversion (5m) ⭐

La estrategia más rentable. Captura sobreextensiones de precio combinando RSI extremes, Bollinger Bands y divergencias.

### Parámetros (config.py)

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| RSI_BB_RSI_PERIOD | 14 | Período del RSI |
| RSI_BB_OVERSOLD | 20 | RSI zona de sobreventa |
| RSI_BB_OVERBOUGHT | 80 | RSI zona de sobrecompra |
| RSI_BB_BB_PERIOD | 20 | Período Bollinger Bands |
| RSI_BB_BB_STD_MULT | 2.0 | StdDev multiplier Bollinger |
| RSI_BB_STOCH_PERIOD | 14 | Período Stochastic RSI |
| RSI_BB_DIVERGENCE_LOOKBACK | 20 | Velas para detectar divergencias |
| RSI_BB_MIN_VOLUME_RATIO | 1.2 | Volumen mínimo vs media |
| RSI_BB_ADX_MIN | 12.0 | ADX mínimo |
| RSI_BB_MIN_ATR_PCT | 0.15 | Volatilidad mínima (%) |
| RSI_BB_SL_ATR_MULT | 2.5 | ATR multiplier para SL |
| RSI_BB_SL_PCT | 0.60 | SL mínimo por porcentaje |
| RSI_BB_REQUIRE_DIVERGENCE | True | Requiere divergencia real |

### 3 Triggers

1. **RSI crossover + BB rejection**: RSI cruza desde zona extrema + precio rechazado en banda
2. **Classic divergence**: swing lows/highs con confirmación RSI
3. **Extreme RSI**: RSI < 20 / > 80 + precio fuera de banda + vela direccional

### Backtest (6 símbolos, 30d)
- WR: 65.7% | PF: 2.29 | Return: +0.69% | DD: 0.23% | Sharpe: 5.44
- Mejores símbolos: XRP, PEPE, AVAX, TIA, ORDI

---

## 2. Stop Hunt (5m)

Estrategia institucional que detecta hunts de liquidez en swing levels con order blocks como confirmación.

### Parámetros

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| STOP_HUNT_WICK_PCT | 0.20 | Mecha mínima hunt (%) |
| STOP_HUNT_REJECTION_RATIO | 0.7 | Body/wick rechazo |
| STOP_HUNT_MIN_ZONES | 2 | Mínimo zonas de liquidez |
| STOP_HUNT_MAX_ZONE_DISTANCE_PCT | 0.8 | Distancia máxima a zona |
| STOP_HUNT_MIN_VOLUME_RATIO | 1.5 | Volumen mínimo |
| STOP_HUNT_ATR_MULT_SL | 2.0 | ATR multiplier SL |
| STOP_HUNT_ADX_MIN | 18.0 | ADX mínimo |

### Backtest (6 símbolos, 30d)
- WR: 75.0% | PF: 2.60 | Return: +0.22% | DD: 0.07%
- Solo 16 trades (baja frecuencia pero alta calidad)

---

## 3. EMA Breakout (15m)

Trend-following con breakout de pivots. SL ajustado desde entry, filtro RSI para evitar sobreextensiones.

### Parámetros

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| EMA_FAST / EMA_SLOW | 9 / 21 | EMAs para tendencia |
| EMA_MIN_SLOPE_PCT | 0.04 | Pendiente mínima EMA |
| EMA_RSI_OVERSOLD / OVERBOUGHT | 30 / 70 | Filtro RSI |
| EMA_MIN_VOLUME_RATIO | 1.2 | Volumen mínimo |
| EMA_MIN_ATR_PCT | 0.15 | Volatilidad mínima |
| EMA_SL_ATR_MULT | 2.0 | ATR multiplier SL |
| MIN_BODY_RATIO | 0.50 | Ratio cuerpo/rango vela |
| ADX_MIN | 20.0 | ADX mínimo |

### Backtest (4 símbolos, 15m, 30d)
- WR: 40.6% | PF: 1.40 | Return: +0.26% | DD: 0.66%

---

## 4. MACD Momentum + Volume Spike (15m)

Captura tendencias fuertes que RSI+BB ignora. MACD histogram creciente + volume spike + RSI direction.

### Parámetros

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| MACD_FAST / SLOW / SIGNAL | 12 / 26 / 9 | MACD settings |
| MACD_MIN_VOLUME_RATIO | 3.0 | Volume spike mínimo (3x media) |
| MACD_RSI_BULL_MIN | 55 | RSI mínimo para LONG |
| MACD_RSI_BEAR_MAX | 45 | RSI máximo para SHORT |
| MACD_ADX_MIN | 25.0 | ADX mínimo |
| MACD_MIN_ATR_PCT | 0.20 | Volatilidad mínima |
| MACD_SL_ATR_MULT | 2.0 | ATR multiplier SL |

### Trigger
MACD histogram creciente × 3 velas + volume spike + RSI direction + EMA alignment + higher high/lower low.

### Backtest (4 símbolos, 15m, 30d)
- WR: 54.8% | PF: 2.10 | Return: +0.92% | DD: 0.31%

---

## 5. Configuración Recomendada

### Desde el Dashboard
```
strategy_mode: "auto" (ejecuta las 4 en paralelo)
Símbolos: XRPUSDT, 1000PEPEUSDT, AVAXUSDT, TIAUSDT, ORDIUSDT, ETHUSDT
```

### Backtesting
```bash
# Una estrategia
./venv/bin/python backtest.py --strategy rsi_bb_reversion --symbols "XRPUSDT,AVAXUSDT" --days 30

# Todas con timeframes correctos
./venv/bin/python backtest.py --all --symbols "XRPUSDT,AVAXUSDT" --days 30

# Estrategia individual con intervalo
./venv/bin/python backtest.py --strategy macd_momentum --interval 15m --days 30
```

---

## Archivos Clave

```
strategy/ema_adx_breakout.py    # EMA Breakout (15m)
strategy/stop_hunt.py           # Stop Hunt (5m)
strategy/rsi_bb_reversion.py    # RSI+BB (5m)
strategy/macd_momentum.py       # MACD Momentum (15m)
strategy/signal_engine.py       # Motor multi-estrategia
strategy/indicators.py          # EMA, ATR, ADX, RSI, Bollinger, MACD
execution/event_loop.py         # Guards y ejecución
datafeed/market_cache.py        # Cache multi-timeframe
config.py                      # Todos los parámetros
```
