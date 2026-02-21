import os
import logging
from logging.handlers import RotatingFileHandler


class DatabaseHandler(logging.Handler):
    def __init__(self, db):
        super().__init__()
        self.db = db

    def emit(self, record):
        try:
            msg = self.format(record)
            level = record.levelname
            symbol = getattr(record, "symbol", None)

            self.db.log(
                level=level,
                symbol=symbol,
                message=msg,
                context=None
            )
        except Exception:
            pass  # Nunca romper el bot por logging


def setup_logging(db=None) -> logging.Logger:
    os.makedirs("logs", exist_ok=True)

    logger = logging.getLogger("bot")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(threadName)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)

    fh = RotatingFileHandler(
        filename="logs/bot.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)

    if not logger.handlers:
        logger.addHandler(sh)
        logger.addHandler(fh)

        # 👇 agregar DB handler si hay db
        if db:
            db_handler = DatabaseHandler(db)
            db_handler.setFormatter(fmt)
            logger.addHandler(db_handler)

    return logger