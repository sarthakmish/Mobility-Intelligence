"""
============================================================
API ROUTES — Technology Endpoints
============================================================
All /api/techs/* routes. Serves technology data for View 2 and 3.
============================================================
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db

router = APIRouter()


@router.get("/")
async def get_all_technologies(
    segment: str = Query("4W_PV", description="Vehicle segment"),
    pillar: str = Query(None, description="Filter by Bosch pillar"),
    maturity: str = Query(None, description="Filter by maturity stage"),
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/techs/
    
    Returns all active technologies for View 2 (Bosch Stack) and View 3 (Market Landscape).
    Supports filtering by segment, pillar, and maturity.
    """
    query = """SELECT id, code, name, pillar, market_data,
                      total_market_fy25_cr, total_market_fy30_cr, cagr,
                      maturity, confidence, includes, analysis_reasoning,
                      source_note, source_ids, last_refreshed
               FROM technologies WHERE is_active = TRUE"""
    params = {}
    
    if pillar:
        query += " AND pillar = :pillar"
        params["pillar"] = pillar
    if maturity:
        query += " AND maturity = :maturity"
        params["maturity"] = maturity
    
    query += " ORDER BY total_market_fy25_cr DESC NULLS LAST"
    
    result = await db.execute(text(query), params)
    
    techs = []
    for row in result.fetchall():
        r = dict(row._mapping)
        import json
        market = r.get("market_data", {})
        if isinstance(market, str):
            market = json.loads(market)
        if not market:
            market = {}

        # Build flat market_data for frontend: {"4W_PV": 1050, "LCV": 220, ...}
        # DB may store nested {"4W_PV": {"fy25": 1050, "cagr": 5.0}} or flat {"4W_PV": 1050}
        flat_market = {}
        seg_cagr = r.get("cagr")
        for seg_key, seg_val in market.items():
            if isinstance(seg_val, dict):
                flat_market[seg_key] = seg_val.get("fy25") or seg_val.get("fy25_cr") or 0
                if seg_key == segment:
                    seg_cagr = seg_val.get("cagr", seg_cagr)
            elif isinstance(seg_val, (int, float)):
                flat_market[seg_key] = seg_val

        seg_fy25 = flat_market.get(segment, r.get("total_market_fy25_cr"))

        techs.append({
            "id": r["id"],
            "code": r["code"],
            "name": r["name"],
            "pillar": r["pillar"],
            "market_data": flat_market,     # flat {"4W_PV": 1050, ...} for frontend
            "market_fy25_cr": seg_fy25,
            "market_fy30_cr": r.get("total_market_fy30_cr"),
            "cagr": seg_cagr,
            "maturity": r["maturity"],
            "confidence": r["confidence"],
            "includes": r["includes"],
            "analysis_reasoning": r.get("analysis_reasoning"),
            "source_note": r.get("source_note", ""),
            "last_refreshed": r["last_refreshed"],
        })
    
    return {"technologies": techs, "count": len(techs), "segment": segment}


@router.get("/pillars")
async def get_pillar_summary(db: AsyncSession = Depends(get_db)):
    """
    GET /api/techs/pillars
    
    Returns summary data for each Bosch pillar (for View 2 Bosch Stack).
    """
    result = await db.execute(
        text(
            """SELECT pillar, COUNT(*) as tech_count,
                  SUM(total_market_fy25_cr) as total_fy25,
                  AVG(cagr) as avg_cagr
           FROM technologies WHERE is_active = TRUE
           GROUP BY pillar ORDER BY total_fy25 DESC NULLS LAST"""
        )
    )
    return {"pillars": [dict(r._mapping) for r in result.fetchall()]}
