import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

from app.config import settings

LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def _file_handler(file_name: str, level: int) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        f"{LOGS_DIR}/{file_name}", maxBytes=10 * 1024 * 1024, backupCount=5
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    return handler


def setup_logging(level: Optional[str] = None) -> None:
    numeric_level = getattr(
        logging, (level or settings.LOG_LEVEL).upper(), logging.INFO
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger.addHandler(console_handler)
    root_logger.addHandler(_file_handler("app.log", logging.INFO))
    root_logger.addHandler(_file_handler("error.log", logging.ERROR))
    logging.getLogger("uvicorn.access").addHandler(
        _file_handler("access.log", logging.INFO)
    )

    for noisy in ("uvicorn", "asyncpg", "httpx", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
