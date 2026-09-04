"""Configuration de logging commune à tous les modules ETL."""
import logging
import os
import sys

from etl.utils.paths import LOGS_DIR


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(os.path.join(LOGS_DIR, "etl.log"))
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger
