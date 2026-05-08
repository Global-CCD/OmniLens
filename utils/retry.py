"""
OmniLens v3.0 - Retry Utility
Configurable retry decorator with exponential backoff and jitter.
"""

import asyncio
import random
from functools import wraps
from typing import Type, Tuple, Optional


def with_retry(
    max_attempts: int = 3,
    backoff_factor: float = 1.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[callable] = None
):
    """
    Retry decorator with exponential backoff and jitter.

    Args:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Base multiplier for delay calculation
        max_delay: Maximum delay between retries in seconds
        exceptions: Tuple of exception types to catch and retry
        on_retry: Optional callback function called on each retry

    Usage:
        @with_retry(max_attempts=3, backoff_factor=2.0, exceptions=(HttpError,))
        async def my_function():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        break

                    # Calculate delay with exponential backoff and jitter
                    delay = min(
                        backoff_factor * (2 ** (attempt - 1)) + random.uniform(0, 1),
                        max_delay
                    )

                    if on_retry:
                        on_retry(attempt, delay, e)
                    else:
                        print(f"[Retry] Attempt {attempt}/{max_attempts} failed: {e}. Retrying in {delay:.1f}s...")

                    await asyncio.sleep(delay)

            raise last_exception

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        break

                    delay = min(
                        backoff_factor * (2 ** (attempt - 1)) + random.uniform(0, 1),
                        max_delay
                    )

                    if on_retry:
                        on_retry(attempt, delay, e)
                    else:
                        print(f"[Retry] Attempt {attempt}/{max_attempts} failed: {e}. Retrying in {delay:.1f}s...")

                    import time
                    time.sleep(delay)

            raise last_exception

        # Return async wrapper if function is async, else sync wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
