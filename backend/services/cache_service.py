"""
============================================================
CACHE SERVICE — Redis Caching Layer
============================================================
Caches AI-generated analysis to avoid redundant LLM calls.

Strategy:
- PESTEL analysis (V1 click): cached 4 hours
- Tech analysis (V3 click): cached 4 hours
- PESTEL factor list: cached 6 hours (invalidated on refresh)
- Technology list: cached 6 hours

Why these TTLs?
- Data doesn't change faster than our 6-hour refresh cycle
- 4-hour analysis cache means each analysis is generated
  at most 6 times/day, not 100+ times
- Saves ~80% of on-demand LLM costs
============================================================
"""

import json
import logging
from typing import Optional, Any

import redis.asyncio as redis

from config import settings

logger = logging.getLogger("cache_service")


class CacheService:
    """Redis-backed cache for AI analysis results."""

    def __init__(self):
        # ── Create async Redis connection pool ───────────
        self.redis = redis.from_url(
            settings.redis_url,
            decode_responses=True,  # Auto-decode bytes to strings
        )

    # ════════════════════════════════════════════════════════
    # GET — Retrieve cached data
    # ════════════════════════════════════════════════════════
    async def get(self, key: str) -> Optional[Any]:
        """
        Get a cached value. Returns None if not found or expired.
        
        Args:
            key: Cache key (e.g., "pestel:india_eu_fta:4W_PV")
        
        Returns:
            Parsed JSON data, or None if cache miss
        """
        try:
            value = await self.redis.get(f"mi:{key}")
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            # Cache failures should NEVER break the application
            # If Redis is down, we just skip cache and call the LLM
            logger.warning(f"Cache GET failed for {key}: {e}")
            return None

    # ════════════════════════════════════════════════════════
    # SET — Store data with TTL
    # ════════════════════════════════════════════════════════
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """
        Cache a value with automatic expiration.
        
        Args:
            key: Cache key
            value: Any JSON-serializable data
            ttl: Time-to-live in seconds (default: from config)
        
        Returns:
            True if cached successfully
        """
        ttl = ttl or settings.analysis_cache_ttl
        try:
            await self.redis.setex(
                f"mi:{key}",
                ttl,
                json.dumps(value, default=str),
            )
            return True
        except Exception as e:
            logger.warning(f"Cache SET failed for {key}: {e}")
            return False

    # ════════════════════════════════════════════════════════
    # INVALIDATE — Clear stale cache entries
    # ════════════════════════════════════════════════════════
    async def invalidate_pestel_cache(self) -> int:
        """
        Clear all cached PESTEL analysis.
        Called after a data refresh to ensure users see fresh data.
        
        Returns:
            Number of keys deleted
        """
        try:
            # Find all PESTEL cache keys using pattern matching
            keys = []
            async for key in self.redis.scan_iter(match="mi:pestel:*"):
                keys.append(key)

            if keys:
                deleted = await self.redis.delete(*keys)
                logger.info(f"Invalidated {deleted} PESTEL cache entries")
                return deleted
            return 0
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {e}")
            return 0

    async def invalidate_tech_cache(self) -> int:
        """Clear all cached technology analysis."""
        try:
            keys = []
            async for key in self.redis.scan_iter(match="mi:tech:*"):
                keys.append(key)
            if keys:
                deleted = await self.redis.delete(*keys)
                logger.info(f"Invalidated {deleted} tech cache entries")
                return deleted
            return 0
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {e}")
            return 0

    async def invalidate_all(self) -> int:
        """Nuclear option: clear ALL cached data."""
        try:
            keys = []
            async for key in self.redis.scan_iter(match="mi:*"):
                keys.append(key)
            if keys:
                deleted = await self.redis.delete(*keys)
                logger.info(f"Invalidated ALL {deleted} cache entries")
                return deleted
            return 0
        except Exception as e:
            logger.warning(f"Full cache invalidation failed: {e}")
            return 0

    # ════════════════════════════════════════════════════════
    # STATS — Cache hit/miss monitoring
    # ════════════════════════════════════════════════════════
    async def get_stats(self) -> dict:
        """Get Redis cache statistics for monitoring dashboard."""
        try:
            info = await self.redis.info("stats")
            keyspace = await self.redis.info("keyspace")
            return {
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "total_keys": sum(
                    db.get("keys", 0)
                    for db in keyspace.values()
                    if isinstance(db, dict)
                ),
                "memory_used": info.get("used_memory_human", "unknown"),
            }
        except Exception:
            return {"status": "unavailable"}

    async def close(self):
        """Close Redis connection."""
        await self.redis.close()
