from __future__ import annotations

import functools
import threading
import time


class TimeoutError(Exception):
    pass


def timeout(seconds: int):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = {}
            error = {}

            def runner():
                try:
                    result["value"] = func(*args, **kwargs)
                except Exception as exc:  # pragma: no cover
                    error["value"] = exc

            thread = threading.Thread(target=runner, daemon=True)
            thread.start()
            thread.join(seconds)
            if thread.is_alive():
                raise TimeoutError(f"{func.__name__} timed out after {seconds}s")
            if "value" in error:
                raise error["value"]
            return result.get("value")

        return wrapper

    return decorator


def retry(max_attempts: int = 3, delay: float = 1.0):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:  # pragma: no cover
                    last_error = exc
                    if attempt == max_attempts:
                        raise
                    if delay:
                        time.sleep(delay)
            raise last_error

        return wrapper

    return decorator
