"""ECOS 缓存工具"""

import functools
import time
from typing import Any, Callable, Optional


class LRUCache:
    """LRU 缓存"""

    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self.max_size = max_size
        self.ttl = ttl
        self._cache: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        if len(self._cache) >= self.max_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
        self._cache[key] = (value, time.time())

    def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        self._cache.clear()


def lru_cache(max_size: int = 1000, ttl: int = 300) -> Callable:
    """LRU 缓存装饰器"""

    def decorator(func: Callable) -> Callable:
        cache = LRUCache(max_size, ttl)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = f"{func.__name__}:{args}:{kwargs}"
            result = cache.get(key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        wrapper.cache = cache  # type: ignore
        return wrapper

    return decorator
