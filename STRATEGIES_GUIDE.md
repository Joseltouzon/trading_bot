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
| MIN_BODY_RATIO | 0.50 | Ratio cuerpo/ rango vela (0-1) |
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
| STOP_HUNT_MIN_ATR_PCT | 0.12 | Volatilidad mínima (%) |
| STOP_HUNT_ATR_MULT_SL | 2.0 | Multiplicador ATR para SL |
| STOP_HUNT_MOMENTUM_BARS | 3 | Velas para momentum |

### Filtros en el Código (stop_hunt.py)

1. **Zonas de Liquidez**
   - Swing highs/lows de últimos 5 pivots
   - Order blocks (velas institucionales antes de impulso)

2. **Detección Stop Hunt**
   - Precio atraviesa zona con mecha > STOP_HUNT_WICK_PCT
   - Rechazo: close vuelve a favor de la zona
   - Body/wick ratio >= STOP_HUNT_REJECTION_RATIO

3. **Confirmaciones**
   - Volumen >= STOP_HUNT_MIN_VOLUME_RATIO
   - Momentum en dirección correcta
   - Volatilidad (ATR%) >= STOP_HUNT_MIN_ATR_PCT
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

---

## Archivos Clave para Optimización

### Lectura Obligatoria
```
strategy/ema_adx_breakout.py    # Lógica EMA Breakout
strategy/stop_hunt.py           # Lógica Stop Hunt
strategy/signal_engine.py       # Motor de señales (selección estrategia)
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
1. Modificar config.py
2. Reiniciar bot
3. Esperar mínimo 1 día para evaluar
4. Revisar logs para ver signals

### 2. Cambios en Lógica
1. Modificar archivo de estrategia (ema_adx_breakout.py o stop_hunt.py)
2. El bot usa la lógica directamente (no necesita restart para cambios de código, pero sí para imports nuevos)

### 3. Monitoreo
```bash
# Ver signals en tiempo real
tail -f logs/bot.log | grep "trend="

# Ver bloqueos
tail -f logs/bot.log | grep "BLOCKED"

# Ver operaciones
tail -f logs/bot.log | grep "ENTRY"
```

---

## Reglas de Oro

1. **No cambiar varios parámetros a la vez** - Cambiar uno y esperar resultados
2. **Documentar cambios** - Commit con descripción clara
3. **Backtest antes de producción** - Probar en paper trading primero
4. **Métricas importan más que intuición** - Revisar win rate, avg R, drawdown
5. **Menos es más** - Parámetros de más = overfitting
