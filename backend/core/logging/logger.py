"""
Central Logger for SandSwap AI
"""

import logging
import sys


class LoggerFactory:
    """Creates application loggers."""

    @staticmethod
    def get_logger(name: str) -> logging.Logger:

        logger = logging.getLogger(name)

        if logger.hasHandlers():
            return logger

        logger.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s | %(name)s | %(message)s"
        )

        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)

        logger.addHandler(console)

        return logger
