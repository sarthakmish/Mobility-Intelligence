"""
============================================================
MOBILITY SOLUTIONS INTELLIGENCE PLATFORM — API Entry Point
============================================================
This is the MAIN file. Everything starts here.

When you run `docker-compose up`, this file:
1. Creates the FastAPI app
2. Configures CORS (so your Vercel frontend can talk to it)
3. Connects to PostgreSQL and Redis
4. Starts the scheduled data refresh (every 6 hours)
5. Registers all API routes
6. Starts serving on port 8001 (configurable via PORT env var or settings.api_port)

API Documentation: http://localhost:8001/docs (auto-generated)
============================================================
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from config import settings
from db.connection import engine
from services.llm_service import llm
from services.cache_service import CacheService
from agents.orchestrator import orchestrator


# ── Configure logging ─────────────────────────────────────
# All agents and services log through Python's standard logging.
# In Docker, logs appear in `docker-compose logs -f api`
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
# Detailed DEBUG traces for our AI modules
for _mod in ["orchestrator", "pestel_agent", "validation_agent",
              "llm_service", "web_intelligence", "source_tracker"]:
    logging.getLogger(_mod).setLevel(logging.DEBUG)
logger = logging.getLogger("main")


# ════════════════════════════════════════════════════════════
# APPLICATION LIFECYCLE — Startup and Shutdown
# ════════════════════════════════════════════════════════════
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application startup and shutdown.
    
    ON STARTUP:
    - Verify database connection
    - Verify Redis connection
    - Start the scheduled refresh job
    - Log the configuration
    
    ON SHUTDOWN:
    - Close LLM HTTP clients
    - Close database connections
    - Stop the scheduler
    """
    # ── STARTUP ──────────────────────────────────────────
    logger.info("╔══════════════════════════════════════════════════╗")
    logger.info("║  MOBILITY SOLUTIONS INTELLIGENCE PLATFORM        ║")
    logger.info("║  Starting up...                                  ║")
    logger.info("╚══════════════════════════════════════════════════╝")

    # Verify database connection
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("✅ PostgreSQL connected")
    except Exception as e:
        logger.error(f"❌ PostgreSQL connection failed: {e}")

    # Verify Redis connection
    cache = CacheService()
    try:
        stats = await cache.get_stats()
        logger.info(f"✅ Redis connected — {stats}")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")

    # Log configuration
    logger.info("╔════════════════════════════════════════════╗")
    logger.info("║  Mobility Intelligence — LLM Configuration ║")
    logger.info("╠════════════════════════════════════════════╣")
    logger.info(f"║  PRIMARY:   Claude Sonnet 4.6             ║")
    logger.info(f"║  VALIDATOR: GPT 5.4                       ║")
    logger.info("╚════════════════════════════════════════════╝")
    logger.info(f"   Auto refresh:    Every {settings.auto_refresh_hours} hours")
    logger.info(f"   CORS origins:    {settings.cors_origins_list}")
    logger.info(f"   Analysis cache:  {settings.analysis_cache_ttl}s TTL")

    # Start the scheduled data refresh
    # APScheduler runs in the background, triggering refresh every N hours
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    scheduler = AsyncIOScheduler()
    
    async def scheduled_refresh():
        """Background job: refresh data from web sources."""
        from db.connection import async_session
        async with async_session() as db:
            await orchestrator.run_scheduled_refresh(db)
    
    scheduler.add_job(
        scheduled_refresh,
        trigger="interval",
        hours=settings.auto_refresh_hours,
        id="data_refresh",
        name="Scheduled Data Refresh",
    )
    scheduler.start()
    logger.info(f"⏰ Scheduler started: refresh every {settings.auto_refresh_hours}h")

    # ── Startup cache warmup (top 15 PESTEL factors by impact) ──
    # Pre-warm the highest-impact bubbles so first clicks are instant.
    # Runs in background — doesn't block startup.
    async def _startup_warmup():
        import asyncio
        from db.connection import async_session as _session
        await asyncio.sleep(5)  # let uvicorn finish startup banner first
        logger.info("🔥 Startup warmup: top 5 PESTEL × 6 segments...")
        try:
            from sqlalchemy import text as _text
            async with _session() as db:
                result = await db.execute(_text(
                    "SELECT code FROM pestel_factors WHERE is_active = TRUE "
                    "ORDER BY (likelihood * impact) DESC NULLS LAST LIMIT 5"
                ))
                top_codes = [r[0] for r in result.fetchall()]

            segments = ["4W_PV", "LCV", "HCV", "2W", "3W", "Tractor"]
            pairs = [(c, s) for c in top_codes for s in segments]

            warmed = skipped = 0
            for code, seg in pairs:
                cache_key = f"pestel:{code}:{seg}"
                if await orchestrator.cache.get(cache_key):
                    skipped += 1
                    continue
                try:
                    async with _session() as db:
                        await orchestrator.get_pestel_analysis(code, seg, db)
                    warmed += 1
                    if warmed % 6 == 0:
                        logger.info(f"  🔥 [{warmed}/{len(pairs)}] segment-pair warmup progress")
                except Exception as call_err:
                    logger.warning(f"  ⚠️ Startup warmup skipped {code}/{seg}: {call_err}")
                await asyncio.sleep(1.5)

            logger.info(f"🔥 Startup warmup complete: {warmed} new + {skipped} cached / {len(pairs)}")
        except Exception as e:
            logger.warning(f"Startup warmup failed (non-critical): {e}")

    import asyncio as _asyncio
    _asyncio.create_task(_startup_warmup())

    logger.info("🚀 Platform is READY")
    logger.info(f"📖 API docs: http://localhost:{settings.api_port}/docs")

    yield  # ← Application runs here

    # ── SHUTDOWN ─────────────────────────────────────────
    logger.info("Shutting down...")
    scheduler.shutdown()
    await llm.close()
    await cache.close()
    await engine.dispose()
    logger.info("Goodbye! 👋")


# ════════════════════════════════════════════════════════════
# CREATE THE FASTAPI APP
# ════════════════════════════════════════════════════════════
app = FastAPI(
    title="Mobility Solutions Intelligence API",
    description=(
        "Agentic AI platform for India's automotive component industry. "
        "Provides PESTEL analysis, technology intelligence, and market sizing "
        "for Bosch Mobility Solutions' 13 technology pillars."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS Configuration ────────────────────────────────────
# Allows your Vercel-hosted frontend to call this API.
# allow_origin_regex covers any private-network IP (10.x, 172.16-31.x, 192.168.x)
# on any port so you never have to update a hardcoded list when your LAN IP changes.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=(
        r"http://(localhost|127\.0\.0\.1"
        r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
        r"|192\.168\.\d{1,3}\.\d{1,3})"
        r"(:\d+)?"
        r"|https://[a-zA-Z0-9-]+\.netlify\.app"
        r"|https://[a-zA-Z0-9-]+\.railway\.app"
        r"|https://[a-zA-Z0-9-]+\.vercel\.app"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ════════════════════════════════════════════════════════════
# API ROUTES
# ════════════════════════════════════════════════════════════

# ── Health Check ──────────────────────────────────────────
@app.get("/api/health", tags=["System"])
async def health_check():
    """
    Health check endpoint. Used by Docker healthcheck and monitoring.
    Returns OK if the API is running and can reach the database.
    """
    return {
        "status": "healthy",
        "service": "mobility-intelligence-api",
        "version": "1.0.0",
        "llm_calls_total": llm.call_count,
        "llm_cost_total_usd": round(llm.total_cost_usd, 4),
    }


# ── Import and register route modules ────────────────────
from api.pestel import router as pestel_router
from api.technology import router as tech_router
from api.analysis import router as analysis_router
from api.refresh import router as refresh_router
from api.competitors import router as competitors_router

app.include_router(pestel_router, prefix="/api/pestel", tags=["PESTEL"])
app.include_router(tech_router, prefix="/api/techs", tags=["Technologies"])
app.include_router(analysis_router, prefix="/api/analysis", tags=["AI Analysis"])
app.include_router(refresh_router, prefix="/api/refresh", tags=["Data Refresh"])
app.include_router(competitors_router, prefix="/api/competitors", tags=["Competitors"])
