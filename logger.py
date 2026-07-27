# ──────────────────────────────────────────────
# Project Ella v1.0 — Logger
# Structured logging with loguru
# Every action is timestamped and categorized
# ──────────────────────────────────────────────

import sys
from loguru import logger

from config import LOGS_DIR, LOG_LEVEL, LOG_ROTATION, LOG_RETENTION


def setup_logger():
    """
    Configure loguru logger with:
    - Console output (colored, concise)
    - File output (detailed, rotated)
    
    Log format:
    [2026-07-27 11:40:23] [INFO] [brain.gemma] Response — 45 tokens, 320ms
    """
    
    # Remove default logger
    logger.remove()
    
    # ── Console Handler ────────────────────────
    # Colored, concise format for terminal
    logger.add(
        sys.stdout,
        format=(
            "<green>{time:HH:mm:ss}</green> │ "
            "<level>{level: <8}</level> │ "
            "<cyan>{extra[module]: <20}</cyan> │ "
            "<level>{message}</level>"
        ),
        level=LOG_LEVEL,
        colorize=True,
        filter=lambda record: record["extra"].get("module", "") != "",
    )
    
    # Fallback for logs without module context
    logger.add(
        sys.stdout,
        format=(
            "<green>{time:HH:mm:ss}</green> │ "
            "<level>{level: <8}</level> │ "
            "<level>{message}</level>"
        ),
        level=LOG_LEVEL,
        colorize=True,
        filter=lambda record: record["extra"].get("module", "") == "",
    )
    
    # ── File Handler ───────────────────────────
    # Detailed format, rotated, with full timestamps
    log_file = LOGS_DIR / "ella_{time:YYYY-MM-DD}.log"
    logger.add(
        str(log_file),
        format=(
            "[{time:YYYY-MM-DD HH:mm:ss.SSS}] "
            "[{level: <8}] "
            "[{extra[module]}] "
            "{message}"
        ),
        level="DEBUG",
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        encoding="utf-8",
        filter=lambda record: record["extra"].setdefault("module", "system") or True,
    )
    
    return logger


def get_logger(module_name: str):
    """
    Get a module-specific logger.
    
    Usage:
        from logger import get_logger
        log = get_logger("brain.gemma")
        log.info("Model loaded — gemma4:e4b")
    """
    return logger.bind(module=module_name)


# Initialize logger on import
setup_logger()
