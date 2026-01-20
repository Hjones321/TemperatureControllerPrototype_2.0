
import logging
from logging.handlers import RotatingFileHandler
import os

def get_logger(name: str = __name__):
    """Return a configured logger shared across the project."""
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if logger.hasHandlers():
        return logger  # Avoid duplicate handlers

    # --- Log format ---
    log_format = "%(asctime)s: %(levelname)s - %(filename)s - %(message)s"
    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

    # --- Rotating file handler (prevents SD card filling up!) ---
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "app.log")

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1_000_000,   # 1MB per file
        backupCount=5         # Keep last 5 logs → max ~5MB
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # --- Console handler for debugging ---
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG)

    # --- Add handlers ---
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
