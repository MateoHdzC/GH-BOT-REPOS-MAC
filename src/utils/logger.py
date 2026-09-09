"""Centralized logging configuration for GH-BOT-REPOS-MAC."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from src.utils.constants import DEFAULT_LOG_PATH

_LOGGER_INITIALIZED = False


def setup_logger(
    log_file: Optional[Path] = None,
    level: int = logging.INFO,
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB
    backup_count: int = 3,
) -> logging.Logger:
    """Configures and returns the root application logger.

    Args:
        log_file: Path to the log file (defaults to logs/app.log).
        level: Minimum logging level.
        max_bytes: Maximum size of each log file before rotation.
        backup_count: Number of rotated log files to retain.

    Returns:
        Configured logging.Logger instance.
    """
    global _LOGGER_INITIALIZED
    logger = logging.getLogger("gh_bot")
    logger.setLevel(level)

    if _LOGGER_INITIALIZED and logger.handlers:
        return logger

    target_log_file = log_file or DEFAULT_LOG_PATH
    target_log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler with rotation
    try:
        file_handler = RotatingFileHandler(
            filename=str(target_log_file),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as err:
        logger.warning(f"Could not initialize file logger at {target_log_file}: {err}")

    logger.propagate = False
    _LOGGER_INITIALIZED = True
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Returns a namespaced child logger of the main application logger."""
    base_logger = logging.getLogger("gh_bot")
    if not base_logger.handlers:
        setup_logger()
    if name:
        return base_logger.getChild(name)
    return base_logger
