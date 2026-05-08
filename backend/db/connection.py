"""
============================================================
DATABASE CONNECTION — Async PostgreSQL Connection Pool
============================================================
Uses asyncpg for high-performance async database access.
Connection pool is created once at startup and shared across
all requests — no connection-per-request overhead.
============================================================
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from config import settings

# ── Create the async engine ──────────────────────────────
# pool_size=10: Maintain 10 persistent connections
# max_overflow=20: Allow up to 20 more during spikes
# pool_recycle=3600: Recycle connections every hour (prevents stale connections)
engine = create_async_engine(
    settings.db_url,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    echo=False,  # Set True to see SQL queries in logs (noisy but useful for debugging)
)

# ── Session factory — creates new database sessions ──────
# expire_on_commit=False: Objects remain usable after commit
# (important for returning data from API endpoints)
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """
    Dependency injection for FastAPI endpoints.
    Usage in routes:
        @router.get("/pestel")
        async def get_pestel(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
