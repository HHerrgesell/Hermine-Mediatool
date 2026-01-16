"""Logging setup for Hermine downloader."""
import logging
from pathlib import Path
from typing import Optional
from src.config import Config


def setup_logger(config: Config) -> logging.Logger:
    """Setup logging configuration."""
    logger = logging.getLogger('hermine')
    logger.setLevel(getattr(logging, config.logging.level))

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File Handler
    log_file = Path(config.storage.base_dir) / config.logging.file
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(getattr(logging, config.logging.level))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console Handler
    if config.logging.console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, config.logging.level))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
