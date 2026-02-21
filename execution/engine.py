# execution/engine.py

import time

from risk.kill_switch import KillSwitch
from risk.exposure_controller import ExposureController
from risk.losing_streak_guard import LosingStreakGuard
from risk.volatility_filter import volatility_allowed
from risk.guards import daily_drawdown_exceeded


class Engine:

    def __init__(self, strategy, execution, datafeed, exchange, logger, config):

        self.strategy = strategy
        self.execution = execution
        self.datafeed = datafeed
        self.exchange = exchange
        self.logger = logger
        self.config = config

        self.kill_switch = KillSwitch()
        self.exposure = ExposureController(
            max_directional=config.MAX_DIRECTIONAL,
            max_margin_usage=config.MAX_MARGIN_USAGE
        )
        self.losing_guard = LosingStreakGuard(
            max_losses=config.MAX_CONSECUTIVE_LOSSES
        )

        self.initial_equity = None

    def loop(self):

        while True:
            try:

                # ===== Kill switch =====
                if self.kill_switch.triggered:
                    self.logger.warning("Kill switch active.")
                    time.sleep(5)
                    continue

                # ===== Snapshot equity =====
                equity = self.exchange.get_equity()
                used_margin = self.exchange.get_used_margin()

                if self.initial_equity is None:
                    self.initial_equity = equity

                # ===== Daily DD Guard =====
                if daily_drawdown_exceeded(
                    self.initial_equity,
                    equity,
                    self.config.MAX_DAILY_DD
                ):
                    self.logger.warning("Daily drawdown exceeded.")
                    time.sleep(10)
                    continue

                # ===== Losing streak guard =====
                if self.losing_guard.blocked:
                    self.logger.warning("Blocked by losing streak.")
                    time.sleep(10)
                    continue

                # ===== Market Data =====
                market_data = self.datafeed.get_snapshot()

                signals = self.strategy.generate(market_data)

                open_positions = self.exchange.get_open_positions()

                for signal in signals:

                    # ===== Garantizar campo bar_close_ms =====
                    # Esto es clave para el TradeLock.
                    if "bar_close_ms" not in signal:
                        signal["bar_close_ms"] = 0

                    # Volatility regime filter
                    if not volatility_allowed(
                        signal["atr"],
                        signal["price"],
                        self.config.MAX_ATR_PCT
                    ):
                        continue

                    # Exposure control
                    if not self.exposure.directional_allowed(
                        open_positions,
                        signal
                    ):
                        continue

                    if not self.exposure.margin_allowed(
                        equity,
                        used_margin
                    ):
                        continue

                    result = self.execution.execute(signal)

                    if result:
                        self.logger.info("Trade executed.")

                time.sleep(self.config.LOOP_SLEEP)

            except Exception:
                self.logger.exception("Critical engine error.")
                self.kill_switch.register_error()
                time.sleep(2)
