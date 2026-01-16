"""Logging configuration and setup."""
import logging
import sys
from pathlib import Path
from typing import Optional
from colorama import Fore, Style, init

init(autoreset=True)


class ColoredFormatter(logging.Formatter):
    """Custom formatter mit Farben für Console-Output"""

    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
    }

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{log_color}{record.levelname}{Style.RESET_ALL}"
        return super().format(record)


def setup_logger(config: 'Config') -> logging.Logger:
    """Setup Logging basierend auf Config"""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.logging.level))

    # Console Handler
    if config.logging.console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, config.logging.level))
        colored_formatter = ColoredFormatter(config.logging.format)
        console_handler.setFormatter(colored_formatter)
        root_logger.addHandler(console_handler)

    # File Handler (optional)
    if config.logging.log_file:
        config.logging.log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(config.logging.log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(config.logging.format)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    return root_logger
