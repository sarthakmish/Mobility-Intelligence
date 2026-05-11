from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db

router = APIRouter()


@router.get("/pillar")
async def get_pillar_competitors(
    pillar: str = Query("ADAS"),
    segment: str = Query("4W_PV"),
    db: AsyncSession = Depends(get_db),
):
    players = await db.execute(
        text(
            "SELECT c.code, c.name, c.short_name, c.headquarters, c.tier, "
            "c.india_presence, c.key_products, c.color, "
            "cs.market_share_pct, cs.revenue_cr, cs.confidence, cs.source_note "
            "FROM competitors c "
            "JOIN competitor_pillar_shares cs ON c.code = cs.competitor_code "
            "WHERE cs.pillar = :pillar AND cs.segment = :seg AND c.is_active = TRUE "
            "ORDER BY cs.market_share_pct DESC"
        ),
        {"pillar": pillar, "seg": segment},
    )

    # market_data may store segments as nested {"fy25":X,"cagr":Y} OR as a flat number X.
    # Try nested first, fall back to flat number so both formats work correctly.
    techs = await db.execute(
        text(
            "SELECT code, name, "
            "COALESCE((market_data->:seg->>'fy25')::numeric, "
            "         (market_data->>:seg)::numeric, 0) as fy25, "
            "COALESCE(cagr, 0) as cagr, maturity, confidence, source_note "
            "FROM technologies WHERE pillar = :pillar AND is_active = TRUE "
            "AND COALESCE((market_data->:seg->>'fy25')::numeric, "
            "             (market_data->>:seg)::numeric, 0) > 0 "
            "ORDER BY fy25 DESC"
        ),
        {"seg": segment, "pillar": pillar},
    )

    p_list = [dict(r._mapping) for r in players.fetchall()]
    t_list = [dict(r._mapping) for r in techs.fetchall()]
    total = sum(float(t.get("fy25", 0)) for t in t_list)
    avg_cagr = sum(
        float(t.get("cagr", 0)) * float(t.get("fy25", 0)) for t in t_list
    ) / max(total, 1)

    return {
        "pillar": pillar,
        "segment": segment,
        "market_total_fy25_cr": total,
        "avg_cagr": round(avg_cagr, 1),
        "market_fy30_cr": round(total * (1 + avg_cagr / 100) ** 5),
        "players": p_list,
        "technologies": t_list,
        "player_count": len(p_list),
    }


@router.get("/tech")
async def get_tech_competitors(
    tech_code: str = Query("l2_camera"),
    segment: str = Query("4W_PV"),
    db: AsyncSession = Depends(get_db),
):
    players = await db.execute(
        text(
            "SELECT c.name, c.short_name, c.color, "
            "cts.market_share_pct, cts.revenue_cr, cts.strength, cts.confidence "
            "FROM competitors c "
            "JOIN competitor_tech_shares cts ON c.code = cts.competitor_code "
            "WHERE cts.tech_code = :tech AND cts.segment = :seg "
            "ORDER BY cts.market_share_pct DESC"
        ),
        {"tech": tech_code, "seg": segment},
    )

    oems = await db.execute(
        text(
            "SELECT oem_name, supplier_codes, notes FROM oem_sourcing "
            "WHERE tech_code = :tech AND segment = :seg"
        ),
        {"tech": tech_code, "seg": segment},
    )

    cross = await db.execute(
        text(
            "SELECT name, maturity, confidence, source_note, cagr, "
            "COALESCE((market_data->'4W_PV'->>'fy25')::numeric,0) as pv, "
            "COALESCE((market_data->'LCV'->>'fy25')::numeric,0) as lcv, "
            "COALESCE((market_data->'HCV'->>'fy25')::numeric,0) as hcv, "
            "COALESCE((market_data->'2W'->>'fy25')::numeric,0) as w2, "
            "COALESCE((market_data->'3W'->>'fy25')::numeric,0) as w3, "
            "COALESCE((market_data->'Tractor'->>'fy25')::numeric,0) as tr "
            "FROM technologies WHERE code = :tech"
        ),
        {"tech": tech_code},
    )
    td = cross.fetchone()

    return {
        "tech_code": tech_code,
        "segment": segment,
        "players": [dict(r._mapping) for r in players.fetchall()],
        "oem_sourcing": [dict(r._mapping) for r in oems.fetchall()],
        "cross_segments": (
            {
                "4W_PV": float(td.pv),
                "LCV": float(td.lcv),
                "HCV": float(td.hcv),
                "2W": float(td.w2),
                "3W": float(td.w3),
                "Tractor": float(td.tr),
            }
            if td
            else {}
        ),
        "tech_name": td.name if td else tech_code,
        "maturity": td.maturity if td else "",
        "cagr": float(td.cagr or 0) if td else 0,
        "confidence": td.confidence if td else "",
        "source_note": td.source_note if td else "",
    }
