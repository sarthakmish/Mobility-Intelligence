"""
============================================================
API ROUTES — PESTEL Endpoints
============================================================
All /api/pestel/* routes. Serves PESTEL factor data to frontend.
============================================================
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db

router = APIRouter()


@router.get("/")
async def get_all_pestel_factors(
    segment: str = Query("4W_PV", description="Vehicle segment filter"),
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/pestel/?segment=4W_PV

    Returns all active PESTEL factors with closest-to-anchor history points
    so the frontend can plot Jan 2025 / Jan 2026 / Now trajectories.
    """
    # ── Main query: factor + anchor history points ──
    # Try the full query with pestel_score_history subqueries first.
    # If the history table doesn't exist yet (e.g. migration 010 not run),
    # fall back to a simpler query so the API never returns 500.
    _FULL_SQL = text("""
        SELECT
            f.id, f.code, f.name, f.category,
            f.likelihood, f.likelihood_reasoning,
            f.impact, f.impact_reasoning,
            f.selection_reasoning, f.trend, f.time_horizon,
            f.segment_relevance, f.affected_pillars,
            f.source_ids, f.last_refreshed,
            f.origin_date, f.is_foundational,
            f.verification_verdict, f.verification_source,
            f.first_seen_date, f.last_confirmed_date, f.confirmation_count,
            CASE
                WHEN f.is_foundational = TRUE THEN 'ESTABLISHED'
                WHEN f.first_seen_date > NOW() - INTERVAL '7 days' THEN 'FRESH'
                WHEN COALESCE(f.confirmation_count, 1) >= 3 THEN 'ESTABLISHED'
                WHEN COALESCE(f.last_confirmed_date, f.last_refreshed) < NOW() - INTERVAL '30 days' THEN 'FADING'
                WHEN COALESCE(f.confirmation_count, 1) = 1
                     AND COALESCE(f.last_confirmed_date, f.last_refreshed) < NOW() - INTERVAL '14 days'
                     THEN 'DECAYING'
                ELSE 'EMERGING'
            END AS freshness_tier,
            (
                SELECT json_build_object('l', h.likelihood, 'i', h.impact, 'date', h.recorded_at)
                FROM pestel_score_history h
                WHERE h.factor_code = f.code
                  AND h.recorded_at <= '2025-06-30'::timestamptz
                ORDER BY ABS(EXTRACT(EPOCH FROM (h.recorded_at - '2025-01-15'::timestamptz)))
                LIMIT 1
            ) AS jan25_pt,
            (
                SELECT json_build_object('l', h.likelihood, 'i', h.impact, 'date', h.recorded_at)
                FROM pestel_score_history h
                WHERE h.factor_code = f.code
                  AND h.recorded_at >= '2025-07-01'::timestamptz
                  AND h.recorded_at <= '2026-06-30'::timestamptz
                ORDER BY ABS(EXTRACT(EPOCH FROM (h.recorded_at - '2026-01-15'::timestamptz)))
                LIMIT 1
            ) AS jan26_pt
        FROM pestel_factors f
        WHERE f.is_active = TRUE
        ORDER BY (f.likelihood * f.impact) DESC
    """)
    # Simpler fallback — no history columns, no optional columns added by later migrations
    _SIMPLE_SQL = text("""
        SELECT
            f.id, f.code, f.name, f.category,
            f.likelihood, f.likelihood_reasoning,
            f.impact, f.impact_reasoning,
            f.selection_reasoning, f.trend, f.time_horizon,
            f.segment_relevance, f.affected_pillars,
            f.source_ids, f.last_refreshed,
            NULL::date AS origin_date,
            FALSE AS is_foundational,
            'UNVERIFIED' AS verification_verdict,
            '' AS verification_source,
            NULL::timestamptz AS first_seen_date,
            NULL::timestamptz AS last_confirmed_date,
            1 AS confirmation_count,
            'EMERGING' AS freshness_tier,
            NULL AS jan25_pt,
            NULL AS jan26_pt
        FROM pestel_factors f
        WHERE f.is_active = TRUE
        ORDER BY (f.likelihood * f.impact) DESC
    """)
    try:
        result = await db.execute(_FULL_SQL)
    except Exception:
        await db.rollback()
        result = await db.execute(_SIMPLE_SQL)

    factors = []
    import json as _json
    for row in result.fetchall():
        r = dict(row._mapping)

        seg_rel = r.get("segment_relevance", {})
        if isinstance(seg_rel, str):
            seg_rel = _json.loads(seg_rel)

        # Parse anchor points (None if no history exists for that period)
        def _parse_anchor(pt):
            if pt is None:
                return None
            if isinstance(pt, str):
                pt = _json.loads(pt)
            return [float(pt["l"]), float(pt["i"])] if pt else None

        factors.append({
            "id": r["id"],
            "code": r["code"],
            "name": r["name"],
            "category": r["category"],
            "likelihood": r["likelihood"],
            "likelihood_reasoning": r["likelihood_reasoning"],
            "impact": r["impact"],
            "impact_reasoning": r["impact_reasoning"],
            "selection_reasoning": r["selection_reasoning"],
            "trend": r["trend"],
            "time_horizon": r["time_horizon"],
            "segment_relevance": seg_rel,
            "affected_pillars": r["affected_pillars"],
            "relevance_to_segment": seg_rel.get(segment, "M"),
            "last_refreshed": r["last_refreshed"],
            "origin_date": (r.get("origin_date").isoformat() if r.get("origin_date") else None),
            "is_foundational": r.get("is_foundational", False),
            "verification_verdict": r.get("verification_verdict", "UNVERIFIED"),
            "verification_source": r.get("verification_source", ""),
            # ── NEW: real anchor points from pestel_score_history ──
            "score_jan_2025": _parse_anchor(r.get("jan25_pt")),
            "score_jan_2026": _parse_anchor(r.get("jan26_pt")),
            # ── Freshness model ──
            "freshness_tier": r.get("freshness_tier", "EMERGING"),
            "first_seen_date": (r["first_seen_date"].isoformat() if r.get("first_seen_date") else None),
            "last_confirmed_date": (r["last_confirmed_date"].isoformat() if r.get("last_confirmed_date") else None),
            "confirmation_count": r.get("confirmation_count", 1),
        })

    return {
        "factors": factors,
        "count": len(factors),
        "segment": segment,
    }


@router.get("/history/{code}")
async def get_factor_history(code: str, db: AsyncSession = Depends(get_db)):
    """
    GET /api/pestel/history/{code}

    Returns timeline of L×I score snapshots for a factor, with origin
    estimate prepended when earlier than first tracked snapshot.
    """
    factor = await db.execute(
        text(
            "SELECT name, likelihood, impact, origin_date, created_at, trend "
            "FROM pestel_factors WHERE code = :code AND is_active = TRUE"
        ),
        {"code": code},
    )
    f = factor.fetchone()
    if not f:
        return {"error": "Factor not found"}

    try:
        history = await db.execute(
            text(
                "SELECT recorded_at, likelihood, impact, source "
                "FROM pestel_score_history WHERE factor_code = :code "
                "ORDER BY recorded_at ASC"
            ),
            {"code": code},
        )
        history_rows = history.fetchall()
    except Exception:
        await db.rollback()
        history_rows = []

    points = []
    for h in history_rows:
        points.append(
            {
                "date": h.recorded_at.isoformat(),
                "label": h.recorded_at.strftime("%b %Y"),
                "likelihood": float(h.likelihood),
                "impact": float(h.impact),
                "score": round(float(h.likelihood) * float(h.impact)),
            }
        )

    origin = f.origin_date or f.created_at
    if origin and (not points or points[0]["date"] > origin.isoformat()):
        initial_l = (
            max(1, float(f.likelihood) - 2)
            if f.trend == "escalating"
            else float(f.likelihood)
        )
        initial_i = (
            max(1, float(f.impact) - 1)
            if f.trend == "escalating"
            else float(f.impact)
        )
        points.insert(
            0,
            {
                "date": origin.isoformat(),
                "label": (
                    origin.strftime("%b %Y")
                    if hasattr(origin, "strftime")
                    else str(origin)
                ),
                "likelihood": initial_l,
                "impact": initial_i,
                "score": round(initial_l * initial_i),
            },
        )

    now_point = {
        "date": "now",
        "label": "Now",
        "likelihood": float(f.likelihood),
        "impact": float(f.impact),
        "score": round(float(f.likelihood) * float(f.impact)),
    }
    if not points or points[-1]["date"] != "now":
        points.append(now_point)

    return {
        "code": code,
        "name": f.name,
        "trend": f.trend,
        "timeline": points,
    }


@router.get("/{factor_code}")
async def get_pestel_factor_detail(
    factor_code: str,
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/pestel/{factor_code}
    
    Returns full detail for a single PESTEL factor,
    including source trail and validation history.
    """
    # Get the factor
    result = await db.execute(
        text("SELECT * FROM pestel_factors WHERE code = :code AND is_active = TRUE"),
        {"code": factor_code}
    )
    row = result.fetchone()
    if not row:
        return {"error": "Factor not found"}
    
    factor = dict(row._mapping)
    
    # Get validation history for this factor
    val_result = await db.execute(
        text("""SELECT * FROM validation_logs 
           WHERE entity_type = 'pestel_factor' AND entity_id = :id
           ORDER BY created_at DESC LIMIT 5"""),
        {"id": factor["id"]}
    )
    validations = [dict(r._mapping) for r in val_result.fetchall()]
    
    # Get source details
    sources = []
    if factor.get("source_ids"):
        src_result = await db.execute(
            text("SELECT * FROM sources WHERE id = ANY(:ids)"),
            {"ids": factor["source_ids"]}
        )
        sources = [dict(r._mapping) for r in src_result.fetchall()]
    
    return {
        "factor": factor,
        "validations": validations,
        "sources": sources,
    }
