"""
Simple thread-safe TTL cache for the Dashboard API.

Phase 6 — item 7.8.

Provides an in-process LRU+TTL cache suitable for caching infrequently
changing API responses (user profiles, statistics) to reduce SQLite load.

Design
------
- Thread-safe via a per-cache RLock.
- Entries expire after *ttl* seconds from insertion time.
- ``maxsize`` entries evicted LRU-style when capacity is exceeded.
- No external dependencies (no Redis, no memcached).

Usage
-----
    from app.dashboard.utils.cache import TTLCache

    # Create once at module level (or inject via app.extensions)
    _profile_cache = TTLCache(maxsize=512, ttl=60)

    def get_profile(jid: str):
        cached = _profile_cache.get(jid)
        if cached is not None:
            return cached
        result = expensive_db_query(jid)
        _profile_cache.set(jid, result)
        return result

    # Invalidate when data changes
    _profile_cache.delete(jid)
    _profile_cache.clear()
"""

import threading
import time
from collections import OrderedDict
from typing import Any, Optional


class TTLCache:
    """
    Thread-safe TTL+LRU in-memory cache.

    Parameters
    ----------
    maxsize : int
        Maximum number of entries (oldest evicted when exceeded).
    ttl : float
        Time-to-live in seconds.  Expired entries are lazily purged on access.
    """

    def __init__(self, maxsize: int = 256, ttl: float = 60.0) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        if ttl <= 0:
            raise ValueError("ttl must be > 0")
        self._maxsize = maxsize
        self._ttl = ttl
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[Any]:
        """Return the cached value for *key*, or ``None`` if missing/expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return None
            # Move to end to mark as recently used (LRU update)
            self._store.move_to_end(key)
            return value

    def set(self, key: str, value: Any) -> None:
        """Insert or update *key* with *value*.  Evicts LRU entry if full."""
        with self._lock:
            expires_at = time.monotonic() + self._ttl
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (value, expires_at)
            if len(self._store) > self._maxsize:
                self._store.popitem(last=False)  # evict oldest

    def delete(self, key: str) -> None:
        """Remove *key* from the cache (no-op if missing)."""
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """Remove all entries."""
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    # ------------------------------------------------------------------
    # Introspection helpers (useful for tests + monitoring)
    # ------------------------------------------------------------------

    @property
    def maxsize(self) -> int:
        return self._maxsize

    @property
    def ttl(self) -> float:
        return self._ttl

    def stats(self) -> dict:
        """Return a snapshot of cache state (for monitoring/testing)."""
        with self._lock:
            now = time.monotonic()
            live = sum(1 for _, (_, exp) in self._store.items() if exp > now)
            return {
                "size": len(self._store),
                "live": live,
                "expired": len(self._store) - live,
                "maxsize": self._maxsize,
                "ttl": self._ttl,
            }
