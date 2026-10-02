import logging
import random
from typing import Tuple

logger = logging.getLogger("lead_intelligence.workers.retry")

# Explicit non-retryable error substrings or exception class names
PERMANENT_ERROR_SIGNALS = [
    "invalid url",
    "ssrf protection",
    "unsupported scheme",
    "validationerror",
    "malformed json",
    "blocked_by_robots",
    "not found",
    "bad request",
    "unauthorized",
    "forbidden",
]


def is_retryable_error(exc: Exception) -> bool:
    """
    Distinguishes transient/retryable failures from permanent unrecoverable errors.
    Returns True if error should trigger exponential backoff retry.
    """
    exc_type = type(exc).__name__.lower()
    exc_msg = str(exc).lower()

    # Check for permanent signals
    for signal in PERMANENT_ERROR_SIGNALS:
        if signal in exc_msg or signal in exc_type:
            logger.info("Encountered permanent non-retryable error: %s (%s)", type(exc).__name__, exc)
            return False

    # Check for transient network/server/timeout signals
    transient_signals = [
        "timeout",
        "timed out",
        "connection",
        "connecterror",
        "network",
        "readerror",
        "500",
        "502",
        "503",
        "504",
        "429",
        "rate limit",
        "server error",
        "temporarily unavailable",
    ]

    for signal in transient_signals:
        if signal in exc_msg or signal in exc_type:
            return True

    # Default to non-retryable for generic unexpected errors to avoid endless looping
    return False


def calculate_backoff_delay(
    retry_count: int,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: float = 0.5,
) -> float:
    """
    Calculates exponential backoff delay with randomized jitter:
    delay = min(max_delay, base_delay * (2 ** retry_count) + uniform(0, jitter))
    """
    raw_delay = base_delay * (2 ** retry_count)
    random_jitter = random.uniform(0, jitter)
    return min(max_delay, round(raw_delay + random_jitter, 2))
