# Binance Futures Bot (USDT-M) — EMA20/EMA50 + WS + Trailing (Mark Price)

## Qué hace

Bot para Binance Futures USDT-M (One-way mode) que opera:

* LONG y SHORT
* 5m
* EMA20/EMA50 trend
* Breakout de pivots (pivot len 5)
* Filtro ADX + volumen
* SL por pivots con buffer ATR
* Trailing manual 0.5% sobre MARK PRICE (activación +0.5%)

Incluye:

* WebSocket klines + mark price
* Reconexión robusta + supervisor
* Watchdog (si no llegan velas cerradas reinicia WS)
* State.json atómico
* Logs rotativos
* Daily loss limit
* Cooldown
* Telegram control

## Requisitos

* Python 3.10+ recomendado
* API Key Binance con Futures habilitado
* Telegram bot token + chat id

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Crear `.env`:

```bash
cp .env.example .env
nano .env
```

## Modo

Por defecto corre en PAPER:

```
PAPER_TRADING=true
```

Cuando estés seguro:

```
PAPER_TRADING=false
```

## Correr

```bash
python bot.py
```

Logs:

* `logs/bot.log`

## Telegram

Comandos principales:

* `/help`
* `/status`
* `/pause` / `/resume`
* `/set_risk 1`  (máximo 10)
* `/set_leverage 5`
* `/positions`
* `/paper_mode`

## Notas críticas

* Debe estar en One-way mode (NO hedge)
* Margin: ISOLATED
* Leverage: 5x

## Advertencia

Este bot puede perder dinero. Futures es alto riesgo. Usar primero en PAPER.
