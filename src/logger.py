"""Logging setup for Hermine downloader."""
import logging
from pathlib import Path
from typing import Optional
from src.config import Config


def setup_logger(config: Config) -> logging.Logger:
    """Setup logging configuration."""
    # Configure the root logger so all child loggers inherit the handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.logging.level))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Ensure log directory exists
    log_dir = Path(config.storage.base_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # File Handler
    log_file = log_dir / config.logging.file
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(getattr(logging, config.logging.level))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Console Handler
    if config.logging.console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, config.logging.level))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    return root_logger
