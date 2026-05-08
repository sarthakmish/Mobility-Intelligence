"""
============================================================
API ROUTES — AI Analysis Endpoints (On-Click Generation)
============================================================
These endpoints are called when a user clicks a bubble on the dashboard.
They return AI-generated analysis, served from cache when available.

Flow: User clicks bubble → Frontend calls /api/analysis/* → 
      Check Redis cache → Cache hit? Return immediately :
      Cache miss? Call Sonnet 4.6 → Cache result → Return
============================================================
"""

import asyncio
import logging
from fastapi import APIRouter, Depends, Query, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db, async_session
from agents.orchestrator import orchestrator
from config import settings

logger = logging.getLogger("analysis")

router = APIRouter()


@router.get("/pestel/{factor_code}")
async def get_pestel_analysis(
    factor_code: str,
    segment: str = Query("4W_PV", description="Vehicle segment context"),
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/analysis/pestel/{factor_code}?segment=4W_PV
    
    Returns AI-generated analysis for a PESTEL factor.
    This is what appears in the detail panel when user clicks
    a bubble in View 1.
    
    Cache strategy:
    - Cached for 4 hours (analysis_cache_ttl)
    - Invalidated on data refresh
    - First click: ~3-5 seconds (LLM generation)
    - Subsequent clicks: instant (cache hit)
    """
    analysis = await orchestrator.get_pestel_analysis(
        factor_code=factor_code,
        segment=segment,
        db_session=db,
    )
    return analysis


@router.get("/tech/{tech_code}")
async def get_tech_analysis(
    tech_code: str,
    segment: str = Query("4W_PV", description="Vehicle segment context"),
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/analysis/tech/{tech_code}?segment=4W_PV
    
    Returns AI-generated analysis for a technology.
    This populates the AI Agent Analysis panel in View 3.
    
    Includes: Pillar overview, Growth drivers, Strategic outlook,
    Growth trajectory, PESTEL forces, Key players, Cross-segment comparison.
    """
    analysis = await orchestrator.get_tech_analysis(
        tech_code=tech_code,
        segment=segment,
        db_session=db,
    )
    return analysis


@router.get("/validation/{entity_type}/{entity_id}")
async def get_validation_trail(
    entity_type: str,
    entity_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/analysis/validation/pestel_factor/42
    
    Returns the multi-LLM validation audit trail for any data point.
    Shows: which models verified it, their confidence levels,
    reasoning, and the consensus decision.
    
    This is what the user sees when they click "View source trail"
    on any data point in the dashboard.
    """
    result = await db.execute(
        text(
            """SELECT * FROM validation_logs
           WHERE entity_type = :type AND entity_id = :id
           ORDER BY created_at DESC"""
        ),
        {"type": entity_type, "id": entity_id}
    )
    validations = [dict(r._mapping) for r in result.fetchall()]
    
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "validations": validations,
        "total": len(validations),
    }


@router.post("/warmup")
async def warmup_analysis_cache(
    x_admin_key: str = Header(None, alias="X-Admin-Key"),
    segment: str = Query("4W_PV"),
    db: AsyncSession = Depends(get_db),
):
    """
    POST /api/analysis/warmup?segment=4W_PV
    Header: X-Admin-Key: <admin key>

    Pre-generates AI analysis for ALL PESTEL factors and technologies
    for the given segment, storing results in Redis.

    After this runs, every bubble click is instant (cache HIT).
    Takes ~5-10 min to complete (one LLM call per factor).
    Runs entirely in the background — returns immediately.
    """
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")

    # Fetch all factor codes and tech codes from DB
    factors_result = await db.execute(text("SELECT code FROM pestel_factors ORDER BY id"))
    factor_codes = [r[0] for r in factors_result.fetchall()]

    techs_result = await db.execute(text("SELECT code FROM technologies ORDER BY id"))
    tech_codes = [r[0] for r in techs_result.fetchall()]

    total = len(factor_codes) + len(tech_codes)
    logger.info(
        f"🔥 CACHE WARMUP started │ segment={segment} │ "
        f"{len(factor_codes)} PESTEL + {len(tech_codes)} techs = {total} total"
    )

    async def _run_warmup():
        warmed = 0
        skipped = 0
        async with async_session() as bg_db:
            for code in factor_codes:
                try:
                    cache_key = f"pestel:{code}:{segment}"
                    cached = await orchestrator.cache.get(cache_key)
                    if cached:
                        skipped += 1
                        logger.debug(f"  ⏭ SKIP (cached) pestel:{code}")
                        continue
                    await orchestrator.get_pestel_analysis(code, segment, bg_db)
                    warmed += 1
                    logger.info(f"  ✅ Warmed pestel:{code} ({warmed}/{len(factor_codes)})")
                    await asyncio.sleep(0.5)  # small gap to avoid hammering LLM Farm
                except Exception as e:
                    logger.warning(f"  ⚠ Failed pestel:{code}: {e}")

            for code in tech_codes:
                try:
                    cache_key = f"tech:{code}:{segment}"
                    cached = await orchestrator.cache.get(cache_key)
                    if cached:
                        skipped += 1
                        logger.debug(f"  ⏭ SKIP (cached) tech:{code}")
                        continue
                    await orchestrator.get_tech_analysis(code, segment, bg_db)
                    warmed += 1
                    logger.info(f"  ✅ Warmed tech:{code} ({warmed}/{len(tech_codes)})")
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning(f"  ⚠ Failed tech:{code}: {e}")

        logger.info(
            f"🔥 CACHE WARMUP complete │ Warmed: {warmed} │ "
            f"Skipped (already cached): {skipped} │ Total cost: ${orchestrator.cache._service_name if hasattr(orchestrator.cache, '_service_name') else 'see llm_service log'}"
        )

    # Launch as background task — don't block the HTTP response
    asyncio.create_task(_run_warmup())

    return {
        "status": "warmup_started",
        "segment": segment,
        "pestel_factors": len(factor_codes),
        "technologies": len(tech_codes),
        "total_to_warm": total,
        "message": f"Warming {total} analyses in background. Watch uvicorn terminal for progress.",
    }
