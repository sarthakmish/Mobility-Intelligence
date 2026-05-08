"""
============================================================
API ROUTES — Data Refresh Endpoints (Admin/Developer Only)
============================================================
These endpoints let the DEVELOPER trigger data refreshes manually.
Users do NOT have access to these — refresh is developer-controlled.

Why developer-controlled:
- Each full refresh costs ~$2-4 in LLM calls
- Uncontrolled user refreshes could blow the monthly budget
- Data sources (ACMA, SIAM) update monthly/quarterly, not hourly
- Automatic 6-hour refresh + manual admin trigger = right balance

In production, protect these with an API key or admin auth.
============================================================
"""

import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from agents.orchestrator import orchestrator
from services.cache_service import CacheService
from services.llm_service import llm

router = APIRouter()


# ── Simple API key auth for refresh endpoints ─────────────
# In production, replace with proper JWT/OAuth
ADMIN_KEY = "mi-admin-refresh-2026"  # Change this in .env


def verify_admin(x_admin_key: str = Header(None)):
    """Basic admin key verification. Replace with proper auth in production."""
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Admin key required for refresh operations")
    return True


@router.post("/full")
async def trigger_full_refresh(
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(verify_admin),
):
    """
    POST /api/refresh/full
    Header: X-Admin-Key: mi-admin-refresh-2026

    Triggers a COMPLETE data refresh in the BACKGROUND and returns immediately.
    The refresh runs asynchronously — check the backend terminal for live progress.

    Pipeline (runs in background):
    1. Scrape all web sources for latest news/data
    2. Run PESTEL discovery agent (find new factors)
    3. Run scoring agent (rate likelihood × impact)
    4. Run 4-model parallel validation on new/changed data
    5. Run tech category scan (Haiku)
    6. Store everything in PostgreSQL
    7. Invalidate Redis cache
    8. Launch post-refresh cache warmup (all 6 segments)

    Estimated time: 10–20 min (LLM Farm latency ~90s/call)
    Estimated cost: $3–6 per full refresh
    """
    triggered_at = datetime.now(timezone.utc).isoformat()

    async def _run():
        from db.connection import async_session
        async with async_session() as bg_db:
            await orchestrator.run_scheduled_refresh(bg_db, trigger_type="manual")

    asyncio.create_task(_run())

    return {
        "message": "Full refresh started in background — watch the backend terminal for live progress logs",
        "triggered_at": triggered_at,
        "note": "Health endpoint and all other APIs remain responsive during refresh",
    }


@router.post("/cache/clear")
async def clear_all_cache(
    _auth: bool = Depends(verify_admin),
):
    """
    POST /api/refresh/cache/clear
    
    Clears ALL Redis cache. Next user click will trigger fresh
    LLM generation for every analysis panel.
    
    Use when: You've manually updated the database and want
    users to see the changes immediately.
    """
    cache = CacheService()
    deleted = await cache.invalidate_all()
    return {
        "message": f"Cleared {deleted} cache entries",
        "cleared_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/status")
async def get_refresh_status(
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/refresh/status
    
    Returns the status of the last refresh and system health.
    No admin key needed — this is monitoring data.
    """
    # Get last refresh log
    result = await db.execute(
        text("SELECT * FROM refresh_logs ORDER BY created_at DESC LIMIT 5")
    )
    recent_refreshes = [dict(r._mapping) for r in result.fetchall()]

    # Get data counts
    pestel_count = await db.execute(
        text("SELECT COUNT(*) FROM pestel_factors WHERE is_active = TRUE")
    )
    tech_count = await db.execute(
        text("SELECT COUNT(*) FROM technologies WHERE is_active = TRUE")
    )
    validation_count = await db.execute(
        text("SELECT COUNT(*) FROM validation_logs")
    )

    # Cache stats
    cache = CacheService()
    cache_stats = await cache.get_stats()

    return {
        "last_refreshes": recent_refreshes,
        "data_counts": {
            "active_pestel_factors": pestel_count.scalar(),
            "active_technologies": tech_count.scalar(),
            "total_validations": validation_count.scalar(),
        },
        "llm_usage": {
            "total_calls": llm.call_count,
            "total_cost_usd": round(llm.total_cost_usd, 4),
        },
        "cache": cache_stats,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/logs")
async def get_refresh_logs(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/refresh/logs?limit=20
    
    Returns detailed refresh history — when each refresh ran,
    what it found, how many LLM calls it used, and what it cost.
    """
    result = await db.execute(
        text("SELECT * FROM refresh_logs ORDER BY created_at DESC LIMIT :limit"),
        {"limit": min(limit, 100)}
    )
    return {"logs": [dict(r._mapping) for r in result.fetchall()]}


@router.get("/validation-stats")
async def get_validation_stats(
    days: int = Query(7, description="Stats window in days"),
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/refresh/validation-stats?days=7

    Returns 4-LLM consensus distribution for recent validations.
    Used by the header badge to prove validation is running.
    """
    from sqlalchemy import text as _t
    result = await db.execute(
        _t("""
            SELECT consensus, COUNT(*) AS n
            FROM validation_logs
            WHERE created_at > NOW() - (:days || ' days')::interval
            GROUP BY consensus
        """),
        {"days": str(days)},
    )
    rows = result.fetchall()
    counts = {r[0]: r[1] for r in rows}

    latest = await db.execute(
        _t("""
            SELECT data_point, claimed_value, primary_verdict, validator_verdict,
                   consensus, created_at
            FROM validation_logs
            ORDER BY created_at DESC LIMIT 5
        """)
    )
    samples = [dict(r._mapping) for r in latest.fetchall()]

    return {
        "window_days": days,
        "verified": counts.get("VERIFIED", 0),
        "flagged": counts.get("FLAGGED", 0),
        "rejected": counts.get("REJECTED", 0),
        "human_review": counts.get("HUMAN_REVIEW", 0),
        "total": sum(counts.values()),
        "recent_samples": samples,
    }


@router.get("/exchange-rate")
async def get_exchange_rate():
    """
    GET /api/refresh/exchange-rate

    Returns INR↔EUR rate, cached 24h. Falls back to ECB-backed Frankfurter
    free API if cache empty. Falls back to hardcoded 106.5 if internet down.
    """
    cache = CacheService()
    cached = await cache.get("exchange_rate:EUR_INR")
    if cached:
        return cached

    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            res = await client.get("https://api.frankfurter.app/latest?from=EUR&to=INR")
            data = res.json()
            rate = float(data["rates"]["INR"])
            payload = {
                "rate_eur_to_inr": rate,
                "fetched_at": data.get("date"),
                "source": "Frankfurter (ECB)",
            }
            await cache.set("exchange_rate:EUR_INR", payload, ttl=86400)
            return payload
    except Exception:
        return {
            "rate_eur_to_inr": 106.5,
            "fetched_at": "fallback",
            "source": "Hardcoded fallback (Frankfurter unreachable)",
        }


@router.get("/audit-stats")
async def get_audit_stats(
    days: int = Query(7, description="Window in days"),
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/refresh/audit-stats?days=7

    Returns System Sanity Engine findings from the last N days.
    """
    from sqlalchemy import text as _t
    summary = await db.execute(
        _t("""
            SELECT severity, COUNT(*) as n
            FROM system_audit_logs
            WHERE created_at > NOW() - (:days || ' days')::interval
            GROUP BY severity
        """),
        {"days": str(days)},
    )
    summary_map = {r[0]: r[1] for r in summary.fetchall()}

    recent = await db.execute(
        _t("""
            SELECT check_name, severity, entity_type, entity_code,
                   entity_segment, message, auto_fixed, created_at
            FROM system_audit_logs
            ORDER BY created_at DESC LIMIT 30
        """)
    )
    findings = [dict(r._mapping) for r in recent.fetchall()]

    last_run = await db.execute(
        _t("SELECT MAX(created_at) FROM system_audit_logs")
    )
    last = last_run.scalar()

    return {
        "window_days": days,
        "info": summary_map.get("INFO", 0),
        "warn": summary_map.get("WARN", 0),
        "error": summary_map.get("ERROR", 0),
        "last_audit_at": last.isoformat() if last else None,
        "recent_findings": findings,
    }


@router.post("/quick")
async def quick_refresh(db: AsyncSession = Depends(get_db)):
    """
    POST /api/refresh/quick

    Fast partial refresh: runs sanity engine only, skipping the LLM
    discovery + validation steps. Useful for pre-demo data quality checks.
    """
    from agents.sanity_engine import sanity_engine
    audit = await sanity_engine.run_full_audit(db, auto_fix=True)
    return {"status": "quick_refresh_complete", "audit_run_id": audit["run_id"]}


@router.get("/source-health")
async def get_source_health():
    """
    GET /api/refresh/source-health

    Quick view of which scrape sources are healthy. Useful for surfacing
    "Reuters India broken — needs selector update" in admin UI or alerts.
    """
    from services.web_intelligence import WebIntelligenceService
    web = WebIntelligenceService()
    sources = getattr(web, "last_source_texts", []) or []
    return {
        "sources": [
            {
                "name": s["name"],
                "chars": s["chars"],
                "status": s.get("status", "unknown"),
                "scraped_at": s["scraped_at"],
            }
            for s in sources
        ],
        "total": len(sources),
        "healthy": sum(1 for s in sources if s.get("status") == "ok"),
    }
