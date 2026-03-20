# Guía de Estrategias de Trading

## 1. EMA Breakout

### Descripción
Estrategia de trend-following que busca breakouts de pivots confirmados por EMA, ADX, volumen y momentum.

### Parámetros Clave (config.py)

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| EMA_FAST | 9 | EMA rápida para tendencia |
| EMA_SLOW | 21 | EMA lenta para tendencia |
| DEFAULT_ADX_MIN | 20.0 | ADX mínimo para entrar |
| MIN_PIVOT_DISTANCE_PCT | 0.15 | Distancia mínima precio-pivot (%) |
| MIN_BODY_RATIO | 0.50 | Ratio cuerpo/rango vela (0-1) |
| MIN_ATR_PCT | 0.15 | Volatilidad mínima (%) |
| VOLUME_MIN_RATIO | 1.20 | Volumen mínimo vs media |
| MAX_VOLUME_RATIO | 3.5 | Volumen máximo (evitar climaxes) |
| MIN_MOMENTUM_PCT | 0.12 | Momentum mínimo en 3 velas (%) |
| MAX_PIVOT_AGE | 15 | Máxima antigüedad del pivot (velas) |

### Filtros en el Código (ema_adx_breakout.py)

1. **Tendencia (EMA Slope)**
   - Slope EMA debe ser > MIN_EMA_SLOPE_PCT
   - Si slope < mínimo → trend = "NONE" (no opera)

2. **Volumen**
   - Debe estar entre VOLUME_MIN_RATIO y MAX_VOLUME_RATIO
   - vol_increasing = volumen actual > volumen anterior

3. **ATR (Volatilidad)**
   - ATR% debe ser >= MIN_ATR_PCT

4. **Momentum**
   - momentum_pct >= MIN_MOMENTUM_PCT en dirección de tendencia
   - O candle_momentum_strong (body >= 0.6 + cierre a favor)

5. **Breakout**
   - prev["high"] <= pivot_high (vela anterior no rompió)
   - last["high"] > pivot_high (vela actual rompe con mecha)
   - Vela direccional (close > open para LONG)
   - Distancia mínima al pivot
   - Body ratio suficiente
   - Pivot reciente (MAX_PIVOT_AGE)

6. **En event_loop.py**
   - ADX >= DEFAULT_ADX_MIN
   - ADX rising (opcional, REQUIRE_ADX_RISING)

### Cuándo Opera
- Mercados con tendencia definida
- Alta volatilidad (ATR% > 0.15)
- Volumen normal (no excesivo)

### Cuándo NO Opera
- Mercados laterales
- Baja volatilidad
- Tendencia weak (slope bajo)
- ADX bajo

---

## 2. Stop Hunt

### Descripción
Estrategia que busca zonas de liquidez (pivots + order blocks), detecta stop hunts y entra en el rechazo.

### Parámetros Clave (config.py)

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| STOP_HUNT_WICK_PCT | 0.20 | Mecha mínima para detectar hunt (%) |
| STOP_HUNT_REJECTION_RATIO | 0.7 | Body/wick ratio mínimo para rechazo |
| STOP_HUNT_MIN_ZONES | 2 | Número mínimo de zonas de liquidez |
| STOP_HUNT_MAX_ZONE_DISTANCE_PCT | 0.8 | Máxima distancia precio-zona (%) |
| STOP_HUNT_MIN_VOLUME_RATIO | 1.5 | Volumen mínimo vs media |
| STOP_HUNT_USE_EMA_FILTER | True | Usar EMA para tendencia |
| STOP_HUNT_ADX_MIN | 18.0 | ADX mínimo para operar |
| STOP_HUNT_MIN_ATR_PCT | 0.12 | Volatilidad mínima (%) |
| STOP_HUNT_ATR_MULT_SL | 2.0 | Multiplicador ATR para SL |
| STOP_HUNT_MOMENTUM_BARS | 3 | Velas para momentum |
| STOP_HUNT_MIN_BREAK_CANDLES | 2 | Velas consecutivas rompiendo zona |
| ORDER_BLOCK_LOOKBACK | 5 | Velas hacia atrás para buscar OBs |

### Filtros en el Código (stop_hunt.py)

1. **Zonas de Liquidez**
   - Swing highs/lows de últimos 5 pivots
   - Order blocks (velas institucionales antes de impulso)

2. **Detección Stop Hunt**
   - Precio atraviesa zona con mecha > STOP_HUNT_WICK_PCT
   - Velas consecutivas rompen zona (STOP_HUNT_MIN_BREAK_CANDLES)
   - Rechazo: close vuelve a favor de la zona
   - Body/wick ratio >= STOP_HUNT_REJECTION_RATIO

3. **Confirmaciones**
   - Volumen >= STOP_HUNT_MIN_VOLUME_RATIO
   - Momentum en dirección correcta
   - Volatilidad (ATR%) >= STOP_HUNT_MIN_ATR_PCT
   - ADX >= STOP_HUNT_ADX_MIN
   - EMA confirma tendencia (si STOP_HUNT_USE_EMA_FILTER = True)

4. **Distancia**
   - Precio debe estar a <= STOP_HUNT_MAX_ZONE_DISTANCE_PCT de la zona

### Cuándo Opera
- Mercados con zonas de liquidez claras
- Post-stop hunt (whipsaw)
- Alta volatilidad

### Cuándo NO Opera
- Sin zonas de liquidez cerca
- Movimiento continuo sin rechazo
- Baja volatilidad
- ADX bajo (< 18)

---

## 3. VWAP Refresh

### Descripción
Estrategia que busca entradas cuando el precio se extiende más allá del VWAP y sus bandas, y luego rechaza hacia el VWAP. Ideal para mercados en rango con sesiones de volumen equilibrado.

### Parámetros Clave (config.py)

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| VWAP_STD_MULT | 1.5 | Multiplicador de desviación estándar para bandas |
| VWAP_MIN_VOLUME_RATIO | 1.5 | Volumen mínimo vs media |
| VWAP_SL_ATR_MULT | 2.0 | Multiplicador ATR para Stop Loss |
| VWAP_MAX_DEVIATION_PCT | 2.0 | Máxima desviación precio-VWAP (%) |

### Lógica (vwap_refresh.py)

1. **VWAP + Bandas**
   - VWAP = (TP * Volumen).cumsum() / Volumen.cumsum()
   - Bandas = VWAP ± (StdDev * multiplicador)

2. **Detección de Refresh**
   - LONG: precio < VWAP y low < lower_band → close > VWAP
   - SHORT: precio > VWAP y high > upper_band → close < VWAP

3. **Confirmaciones**
   - Volumen spike (>= VWAP_MIN_VOLUME_RATIO)
   - Precio volviendo hacia VWAP (no extendiendo)
   - ATR% mínimo

4. **Stop Loss**
   - Más allá de las bandas VWAP
   - ATR buffer para holgura

### Cuándo Opera
- Mercados en rango (no hay tendencia clara)
- VWAP actúa como imán
- Volumen equilibrado durante la sesión

### Cuándo NO Opera
- Mercados en tendencia fuerte
- VWAP se mueve constantemente

---

## 4. RSI + Bollinger Band Mean Reversion

### Descripción
Estrategia de mean-reversion que combina RSI extremes, Bollinger Bands y divergencias para capturar reversiones de precio en sobreextensiones. Detecta cuando el precio se extiende fuera de las bandas con RSI en zona extrema y busca la reversión.

### Parámetros Clave (config.py)

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| RSI_BB_RSI_PERIOD | 14 | Período del RSI |
| RSI_BB_OVERSOLD | 25 | RSI zona de sobreventa |
| RSI_BB_OVERBOUGHT | 75 | RSI zona de sobrecompra |
| RSI_BB_BB_PERIOD | 20 | Período Bollinger Bands |
| RSI_BB_BB_STD_MULT | 2.0 | StdDev multiplier Bollinger |
| RSI_BB_STOCH_PERIOD | 14 | Período Stochastic RSI |
| RSI_BB_DIVERGENCE_LOOKBACK | 20 | Velas para detectar divergencias |
| RSI_BB_BAND_TOLERANCE_PCT | 0.3 | Tolerancia fuera de banda (%) |
| RSI_BB_MIN_VOLUME_RATIO | 1.5 | Volumen mínimo vs media |
| RSI_BB_ADX_MIN | 15.0 | ADX mínimo |
| RSI_BB_MIN_ATR_PCT | 0.15 | Volatilidad mínima (%) |
| RSI_BB_SL_ATR_MULT | 2.5 | ATR multiplier para SL |
| RSI_BB_SL_PCT | 0.60 | SL mínimo por porcentaje |

### Lógica (rsi_bb_reversion.py)

**3 tipos de trigger (se necesita AL MENOS UNO):**

1. **RSI Crossover + BB Rejection**
   - RSI cruza hacia arriba desde zona oversold (≤ 25) + precio rechazado en banda inferior
   - RSI cruza hacia abajo desde zona overbought (≥ 75) + precio rechazado en banda superior

2. **Divergencia RSI (Classic)**
   - Bullish: precio hace lower low, RSI hace higher low (swing points con ventana de 5)
   - Bearish: precio hace higher high, RSI hace lower high
   - Requiere separación mínima de 5 velas entre swing points

3. **Extreme RSI**
   - RSI < 20 + precio por debajo de BB lower + vela verde → LONG
   - RSI > 80 + precio por encima de BB upper + vela roja → SHORT

### Filtros de Confirmación
1. **Volumen**: ratio >= RSI_BB_MIN_VOLUME_RATIO (1.5)
2. **ADX**: >= RSI_BB_ADX_MIN (15.0)
3. **Volatilidad**: ATR% >= RSI_BB_MIN_ATR_PCT (0.15%)
4. **Stochastic RSI**: K > D (LONG) o K < D (SHORT), o en zona extrema (<20/>80)
5. **No contra tendencia fuerte**: si ADX > 30 + EMA en contra + spread > 0.5% → bloquea

### Stop Loss
- Basado en Bollinger Bands +/- ATR * 2.5
- Fallback: entry +/- 0.60%
- Usa el máximo de ambos (más holgado)

### Detección de Divergencia
- Swing points con ventana de 5 (robusto, no ruidoso)
- Requiere separación mínima de 5 velas entre swings
- Strength score basado en diferencia de precio y RSI

### Cuándo Opera
- Mercados en rango o transición
- RSI en zona extrema (sobrecompra/sobreventa)
- Precio tocando/rebasando bandas de Bollinger
- Divergencia RSI presente

### Cuándo NO Opera
- Tendencia fuerte sin rechazo (ADX > 30 con EMA en contra)
- Baja volatilidad (ATR% < 0.15)
- Sin señal clara de reversión

### Rendimiento por Símbolo (Backtest 30d 5m)
| Símbolo | Trades | WR | PnL |
|---------|--------|-----|------|
| XRPUSDT | 23 | 61% | +$0.43 |
| 1000PEPEUSDT | 19 | 58% | +$0.19 |
| ETHUSDT | 17 | 53% | ~$0 |
| BNBUSDT | - | bajo | negativo |
| SOLUSDT | - | bajo | negativo |

### Comandos Debug
```bash
# Ver señales RSI+BB
tail -f logs/bot.log | grep "rsi_bb_reversion"

# Ver triggers
tail -f logs/bot.log | grep "trigger_long\|trigger_short"
```

---

## 5. Modo Auto (Market Regime Detection)

### Descripción
El bot analiza automáticamente el régimen del mercado **POR SÍMBOLO** y cambia la estrategia según las condiciones predominantes. Cada mercado puede tener una estrategia diferente.

### Cuándo usar Auto
- Cuando querés que el bot decida qué estrategia usar según el mercado
- Cuando operás múltiples símbolos con condiciones diferentes
- Auto NO es necesario si ya tenés bots con estrategias fijas

### Cuándo NO usar Auto
- Si operás con estrategias fijas ("ema_breakout", "stop_hunt", "vwap_refresh", "rsi_bb_reversion")
- Si preferís control manual de qué estrategia usar

### Parámetros Clave (config.py)

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| REGIME_TRENDING_ADX_MIN | 25.0 | ADX mínimo para considerar trending |
| REGIME_RANGING_ADX_MAX | 18.0 | ADX máximo para considerar ranging |
| REGIME_HUNT_VOL_RATIO_MIN | 1.3 | Volumen mínimo para hunts |

### Lógica (market_regime.py)

1. **Cálculo de Métricas**
   - ADX actual y su tendencia
   - Rango alto-bajo de últimas 20 velas
   - EMA spread (diferencia entre EMAs)
   - Volumen vs media
   - Confidence (0.5 a 0.95)

2. **Detección de Régimen POR SÍMBOLO**

   | Condición | Régimen | Estrategia |
   |-----------|---------|------------|
   | ADX >= 25 y no range-bound | TRENDING | EMA Breakout |
   | ADX 18-25 | TRANSITIONAL | Stop Hunt |
   | ADX <= 18, range-bound, vol >= 1.3 | RANGING + VOL | Stop Hunt |
   | ADX <= 18, range-bound, RSI extremo (≤25 o ≥75) | RANGING + EXTREME | RSI+BB Reversion |
   | ADX <= 18, range-bound, vol < 1.3 | RANGING + LOW VOL | VWAP Refresh |

3. **Switch Automático**
   - Evalúa cada 3 ciclos
   - Requiere confianza >= 70% para cambiar
   - Cada símbolo mantiene su propia estrategia efectiva en cache
   - Si cambia estrategia, limpia cache de indicadores

### Ejemplo Real

```
Símbolo    ADX     Régimen        Estrategia
BTCUSDT    32.07  TRENDING       EMA Breakout
ETHUSDT    29.25  TRENDING       EMA Breakout  
NEARUSDT   15.51  RANGING        VWAP Refresh
LTCUSDT    19.28  TRANSITIONAL   Stop Hunt
```

### Cómo Activar
Seleccionar "Auto (Mercado)" en el dashboard → Estrategia

### Ver logs
```bash
tail -f logs/bot.log | grep "\[REGIME\]"
```

---

## Archivos Clave para Optimización

### Lectura Obligatoria
```
strategy/ema_adx_breakout.py    # Lógica EMA Breakout
strategy/stop_hunt.py           # Lógica Stop Hunt
strategy/vwap_refresh.py        # Lógica VWAP Refresh
strategy/rsi_bb_reversion.py    # Lógica RSI + BB Mean Reversion
strategy/market_regime.py       # Detección de régimen
strategy/signal_engine.py       # Motor de señales
strategy/indicators.py          # RSI, Bollinger, Stochastic, EMA, ATR, ADX
execution/event_loop.py         # Guards y ejecución
config.py                      # Todos los parámetros
```

### Para Debug y Análisis
```
logs/bot.log                   # Logs de actividad
execution/order_manager.py      # Ejecución de órdenes
execution/trailing.py           # Trailing stop
```

### Para Métricas
```
db.py                          # get_performance_metrics()
dashboard/services/dashboard_service.py  # Métricas para dashboard
```

---

## Cómo Optimizar

### 1. Probar Cambios de Parámetros
1. Modificar config.py o dashboard
2. Esperar mínimo 1 día para evaluar
3. Revisar logs para ver signals

### 2. Cambios en Lógica
1. Modificar archivo de estrategia
2. El bot recarga parámetros cada 30s

### 3. Monitoreo
```bash
# Ver signals en tiempo real
tail -f logs/bot.log | grep "trend="

# Ver régimen de mercado
tail -f logs/bot.log | grep "\[REGIME\]"

# Ver bloqueos
tail -f logs/bot.log | grep "BLOCKED"

# Ver operaciones
tail -f logs/bot.log | grep "ENTRY"
```

---

## Reglas de Oro

1. **No cambiar varios parámetros a la vez** - Cambiar uno y esperar resultados
2. **Documentar cambios** - Commit con descripción clara
3. **Probar en paper trading** - Validar antes de producción
4. **Métricas importan más que intuición** - Revisar win rate, avg R, drawdown
5. **Menos es más** - Parámetros de más = overfitting
6. **Auto para principiantes** - Usar modo Auto hasta entender los regímenes
