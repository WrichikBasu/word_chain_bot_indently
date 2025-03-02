import asyncio
import logging
import time
from functools import wraps


def log_execution_time(target_logger: logging.Logger):
    def decorator(function):
        if asyncio.iscoroutinefunction(function):
            @wraps(function)
            async def async_wrapper(*args, **kwargs):
                start_time = time.monotonic()
                result = await function(*args, **kwargs)
                end_time = time.monotonic()
                elapsed_time = end_time - start_time
                target_logger.debug(f"{function.__name__} executed in {elapsed_time:.4f} seconds")
                return result
            return async_wrapper
        else:
            @wraps(function)
            def sync_wrapper(*args, **kwargs):
                start_time = time.monotonic()
                result = function(*args, **kwargs)
                end_time = time.monotonic()
                elapsed_time = end_time - start_time
                target_logger.debug(f"{function.__name__} executed in {elapsed_time:.4f} seconds")
                return result
            return sync_wrapper
    return decorator