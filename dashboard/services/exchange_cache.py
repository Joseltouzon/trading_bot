# dashboard/services/exchange_cache.py
import threading
import time
import logging
from datetime import datetime, timedelta


class ExchangeCache:

    def __init__(self, exchange, refresh_interval=10, logger=None):
        self.exchange = exchange
        self.refresh_interval = refresh_interval
        self.logger = logger or logging.getLogger(__name__)

        # Datos cacheados
        self._open_positions = []
        self._account_info = {}

        # Estado del caché
        self._running = False
        self._last_success = None
        self._last_error = None
        self._error_count = 0
        self._consecutive_failures = 0
        self._total_requests = 0
        self._failed_requests = 0

    def start(self):
        if self._running:
            return
        self._running = True
        thread = threading.Thread(target=self._loop, daemon=True)
        thread.start()
        self.logger.info("[CACHE] Exchange cache thread started")

    def stop(self):
        self._running = False
        self.logger.info("[CACHE] Exchange cache thread stopped")

    def _loop(self):
        while self._running:
            try:
                # Actualizar posiciones
                self._open_positions = self.exchange.get_open_positions() or []

                # Actualizar info de cuenta
                self._account_info = self.exchange.get_account_info()

                # Resetear contadores de error en éxito
                self._last_success = datetime.now()
                self._consecutive_failures = 0
                self._total_requests += 1

            except Exception as e:
                self._last_error = datetime.now()
                self._error_count += 1
                self._consecutive_failures += 1
                self._failed_requests += 1
                self._total_requests += 1

                # Log solo si es el primer error o cada 5 errores consecutivos
                if self._consecutive_failures == 1 or self._consecutive_failures % 5 == 0:
                    self.logger.warning(
                        f"[CACHE] Error fetching data (consecutive: {self._consecutive_failures}): {str(e)}"
                    )

                # Backoff exponencial: esperar más si hay errores consecutivos
                # Máximo 60 segundos entre retries
                backoff = min(self._consecutive_failures * 5, 60)
                time.sleep(backoff)
                continue

            # Sleep normal si todo salió bien
            time.sleep(self.refresh_interval)

    def get_open_positions(self):
        return self._open_positions

    def get_account_info(self):
        return self._account_info

    def get_cache_health(self):
        """Devuelve estado de salud del caché para el dashboard"""
        now = datetime.now()
        last_success_age = None
        is_stale = False

        if self._last_success:
            last_success_age = (now - self._last_success).total_seconds()
            # Consideramos stale si pasó más de 3x el refresh_interval
            is_stale = last_success_age > (self.refresh_interval * 3)

        error_rate = (round((self._failed_requests / self._total_requests) *
                            100, 2) if self._total_requests > 0 else 0)

        return {
            "is_running":
            self._running,
            "last_success":
            self._last_success.strftime("%H:%M:%S")
            if self._last_success else None,
            "last_error":
            self._last_error.strftime("%H:%M:%S")
            if self._last_error else None,
            "last_success_age_seconds":
            last_success_age,
            "is_stale":
            is_stale,
            "consecutive_failures":
            self._consecutive_failures,
            "total_requests":
            self._total_requests,
            "failed_requests":
            self._failed_requests,
            "error_rate_pct":
            error_rate,
        }