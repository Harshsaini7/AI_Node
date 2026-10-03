"""
Logger
======
Centralized logging configuration for the AI Loan Customer Agent.

Uses Python's built-in logging module to provide consistent,
formatted log output to the console.

Log Levels:
    DEBUG    - Detailed diagnostic info (hidden by default)
    INFO     - General operational messages
    WARNING  - Something unexpected but not critical
    ERROR    - Something failed, but the app can continue
    CRITICAL - Something failed badly, app may need to stop

Phase 2.3 - Error Handling & Safe Failures
"""

import logging
import sys


def setup_logger(name="ai_loan_agent", level=logging.INFO):
    """
    Create and configure a logger.

    Args:
        name (str): Logger name (usually the module name)
        level: Logging level (default: INFO)

    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if setup_logger is called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Format: [TIME] [LEVEL] [MODULE] message
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)-8s] %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    return logger


# Create a default logger for the whole application
log = setup_logger()
