"""TTL-based cache manager utility for tool and model response reuse."""

from __future__ import annotations

import os
from typing import Any

from cachetools import TTLCache
from dotenv import load_dotenv

load_dotenv()


class CacheManager:
    """Centralized in-memory cache manager with hit/miss statistics."""

    MAX_SIZE = 200

    def __init__(self) -> None:
        """Initialize TTL cache settings and runtime counters."""
        ttl_value = os.getenv("CACHE_TTL_SECONDS", "300").strip()
        try:
            self.ttl_seconds = int(ttl_value)
        except ValueError:
            self.ttl_seconds = 300

        self._cache: TTLCache[str, Any] = TTLCache(maxsize=self.MAX_SIZE, ttl=self.ttl_seconds)
        self._hit_count = 0
        self._miss_count = 0

    def get(self, key: str) -> Any:
        """Retrieve a value from cache if present and not expired.

        Args:
            key: Cache key string.

        Returns:
            Cached value or None when absent/expired.
        """
        if key in self._cache:
            self._hit_count += 1
            return self._cache.get(key)

        self._miss_count += 1
        return None

    def set(self, key: str, value: Any) -> None:
        """Store a value in cache under the provided key.

        Args:
            key: Cache key string.
            value: Value to cache.
        """
        self._cache[key] = value

    def make_key(self, tool_name: str, action: str, **kwargs: Any) -> str:
        """Build a deterministic cache key from tool/action and named args.

        Args:
            tool_name: Source tool name (for example, "github").
            action: Action name (for example, "search_repos").
            **kwargs: Parameters influencing the result.

        Returns:
            A stable cache key string.
        """
        base = f"{tool_name}:{action}"
        if not kwargs:
            return base

        parts = [f"{name}={kwargs[name]}" for name in sorted(kwargs.keys())]
        return f"{base}:{':'.join(parts)}"

    def get_stats(self) -> dict[str, int]:
        """Return cache capacity and usage statistics."""
        return {
            "cache_size": len(self._cache),
            "max_size": self.MAX_SIZE,
            "ttl_seconds": self.ttl_seconds,
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
        }

    def clear(self) -> None:
        """Clear all cache entries and reset hit/miss counters."""
        self._cache.clear()
        self._hit_count = 0
        self._miss_count = 0


cache_manager = CacheManager()
