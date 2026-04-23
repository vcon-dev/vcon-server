"""Shared exponential-backoff retry decorator (Refactor #3).

Replaces per-link @retry(wait_exponential(...), stop_after_attempt(...))
incantations (deepgram_link, openai_transcribe, groq_whisper) with one
configurable helper. Thin wrapper over tenacity — pick a policy by passing
kwargs, get back a decorator.

Usage:

    from lib.retry import with_backoff
    from lib.logging_utils import init_logger

    logger = init_logger(__name__)

    @with_backoff(max_attempts=6, min_wait=1, max_wait=65, logger=logger)
    def call_flaky_api(...):
        ...
"""
from __future__ import annotations

import logging
from typing import Callable, Optional, Tuple, Type

from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)


def with_backoff(
    *,
    max_attempts: int = 6,
    multiplier: float = 2,
    min_wait: float = 1,
    max_wait: float = 65,
    logger: Optional[logging.Logger] = None,
    log_level: int = logging.INFO,
    retry_on: Optional[Tuple[Type[BaseException], ...]] = None,
) -> Callable:
    """Return a tenacity-based retry decorator using exponential backoff.

    Args:
        max_attempts: How many total attempts before giving up (default 6).
        multiplier: tenacity ``wait_exponential`` multiplier.
        min_wait: Minimum wait between attempts, seconds.
        max_wait: Maximum wait between attempts, seconds. Deepgram/OpenAI
            historically used 65; Groq used 100 (stricter rate limits).
        logger: If provided, logs a message at ``log_level`` before each sleep.
        retry_on: If provided, only retry on this tuple of exception types.
            Defaults to tenacity's "retry on any exception".

    Returns:
        A decorator suitable for ``@with_backoff(...)`` usage.
    """
    kwargs = {
        "wait": wait_exponential(multiplier=multiplier, min=min_wait, max=max_wait),
        "stop": stop_after_attempt(max_attempts),
        "reraise": True,
    }
    if logger is not None:
        kwargs["before_sleep"] = before_sleep_log(logger, log_level)
    if retry_on is not None:
        from tenacity import retry_if_exception_type

        kwargs["retry"] = retry_if_exception_type(retry_on)
    return retry(**kwargs)
