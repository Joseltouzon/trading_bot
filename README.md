# 🤖 Binance Futures Trading Bot (EMA/ADX Breakout)

Bot de trading algorítmico para Binance Futures (USDT-M) enfocado en rupturas de tendencia con confirmación de volumen y momentum.

## ⚠️ Disclaimer
Este software es solo para fines educativos. El trading de futuros conlleva un alto riesgo de pérdida de capital. Úsalo bajo tu propia responsabilidad.

## 🚀 Características
- **Estrategia:** Breakout de Pivots con confirmación EMA + ADX + Volumen.
- **Gestión de Riesgo:** Stop Loss dinámico (ATR), Trailing Stop, Límite de pérdida diaria.
- **Ejecución:** Órdenes Reduce-Only, protección contra slippage y spread.
- **Base de Datos:** PostgreSQL para historial de trades, estado del bot y logs.
- **Notificaciones:** Telegram para entradas, salidas, stops y comandos de control.
- **Dashboard:** Comandos vía Telegram para monitoreo en tiempo real.

## 📋 Requisitos
- Python 3+
- PostgreSQL Database
- Cuenta Binance Futures (API Keys)
- Bot de Telegram (Token & Chat ID)

## 🛠️ Instalación

1. **Clonar repositorio:**
   ```bash
   git clone <tu-repo>
   cd bot
   ```

2. **Entorno virtual:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate
    ```

3. **Instalar dependencias:**
    ```bash
    pip install -r requirements.txt     
    ```

4. **Configurar Variables de Entorno:**
    Crea un archivo .env en la raíz:

    .env:
    BINANCE_API_KEY=tu_api_key
    BINANCE_API_SECRET=tu_api_secret
    TELEGRAM_BOT_TOKEN=tu_token
    TELEGRAM_CHAT_ID=tu_chat_id
    DB_HOST=localhost
    DB_NAME=bot_db
    DB_USER=postgres
    DB_PASSWORD=tu_password
    DB_PORT=5432    
    # dashboard:
    DASHBOARD_PASSWORD=loquevosquieras –> aca pone lo que quieras, por si no quedo claro jajaj

5. **Configurar Estrategia:**
    Edita config.py para ajustar símbolos, riesgo y parámetros técnicos.

6. **Ejecutar:**   
    ```bash
    python bot.py
    ```

## 📱 Comandos Telegram

/dashboard: Resumen de cuenta y posiciones.
/pause / /resume: Control del bot.
/set_risk N: Cambiar riesgo % por trade.
/set_leverage N: Cambiar apalancamiento.
/close SYMBOL: Cerrar posición manual.
/help: Lista completa.

## 📂 Estructura

bot.py: Punto de entrada principal.
strategy/: Lógica de señales (EMA, ADX, Pivots).
execution/: Gestión de órdenes, trailing y eventos.
exchange/: Wrapper de Binance API.
db.py: Conexión y queries PostgreSQL.
core/: Modelos, logging y utilidades.

## 🛡️ Seguridad

Nunca compartas tus API Keys.
Habilita "Restrict to trusted IPs" en Binance si es posible.
No des permisos de Retiro (Withdrawal) a la API Key.    