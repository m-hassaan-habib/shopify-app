import logging
import os
from datetime import datetime

LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

def get_logger(module_name: str, log_file_name: str = None) -> logging.Logger:
    logger = logging.getLogger(module_name)
    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.DEBUG)
    log_file_name = log_file_name or f"{module_name}.log"
    log_path = os.path.join(LOGS_DIR, log_file_name)

    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
