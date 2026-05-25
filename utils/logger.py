"""
utils/logger.py
───────────────
Structured logging with timestamps, session IDs, and file output.

WHY structured logging matters:
After a run completes, you need to understand exactly what happened.
Print statements disappear. Logs persist with timestamps so you can
trace every decision the system made.

Every important event is logged with:
- Timestamp (when)
- Module name (where)
- Message (what happened)
- Saved to file (permanent record)
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

# ─── Log File Setup ───────────────────────────────────────────────
_LOG_DIR = Path("logs")
_LOG_DIR.mkdir(exist_ok=True)

# One log file per run (timestamped so you can compare runs)
_LOG_FILE = _LOG_DIR / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# ─── Formatter ────────────────────────────────────────────────────
_FORMATTER = logging.Formatter(
    fmt="[%(asctime)s] %(levelname)-8s  %(name)-30s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Track loggers already configured (prevent duplicate handlers)
_configured: set[str] = set()


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger for any module.

    Usage (at top of any file):
        from utils.logger import get_logger
        logger = get_logger(__name__)

    Then use:
        logger.info("Something happened")
        logger.warning("Something looks wrong")
        logger.error("Something broke")
        logger.critical("Everything is on fire")
    """
    logger = logging.getLogger(name)

    # Only configure once per logger name
    if name not in _configured:
        logger.setLevel(logging.INFO)

        # Console handler → shows in terminal during run
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(_FORMATTER)
        console.setLevel(logging.INFO)

        # File handler → permanent record in logs/
        file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(_FORMATTER)
        file_handler.setLevel(logging.DEBUG)  # File gets more detail

        logger.addHandler(console)
        logger.addHandler(file_handler)
        logger.propagate = False  # Don't double-log to root logger

        _configured.add(name)

    return logger