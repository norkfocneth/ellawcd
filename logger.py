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
    # Disabled for clean ChatGPT-like user terminal experience.
    # All diagnostics, warnings, and errors are saved silently to rotating file logs.

    
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
