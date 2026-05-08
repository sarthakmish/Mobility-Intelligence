"""One-shot script to fix segment_relevance and dedup pestel_factors."""
import asyncio
import asyncpg

SQL_FIXES = [
    (
        "UPDATE pestel_factors SET segment_relevance = "
        "'{\"4W_PV\":\"H\",\"LCV\":\"H\",\"HCV\":\"H\",\"2W\":\"M\",\"3W\":\"M\",\"Tractor\":\"M\"}'::jsonb "
        "WHERE name ILIKE '%india gdp growth%' AND is_active=TRUE",
        "GDP growth"
    ),
    (
        "UPDATE pestel_factors SET segment_relevance = "
        "'{\"4W_PV\":\"H\",\"LCV\":\"L\",\"HCV\":\"L\",\"2W\":\"L\",\"3W\":\"L\",\"Tractor\":\"L\"}'::jsonb "
        "WHERE (name ILIKE '%premiumisation%' OR name ILIKE '%premiumization%') AND is_active=TRUE",
        "Premiumisation"
    ),
    (
        "UPDATE pestel_factors SET segment_relevance = "
        "'{\"4W_PV\":\"H\",\"LCV\":\"L\",\"HCV\":\"L\",\"2W\":\"L\",\"3W\":\"L\",\"Tractor\":\"L\"}'::jsonb "
        "WHERE (name ILIKE '%multi-oem%suv%' OR name ILIKE '%multi oem%suv%' "
        "    OR name ILIKE '%multi-oem ev platform%' OR name ILIKE '%multi oem ev platform%') "
        "AND is_active=TRUE",
        "Multi-OEM SUV/EV"
    ),
    (
        "UPDATE pestel_factors SET segment_relevance = "
        "'{\"4W_PV\":\"H\",\"LCV\":\"H\",\"HCV\":\"H\",\"2W\":\"L\",\"3W\":\"L\",\"Tractor\":\"L\"}'::jsonb "
        "WHERE name ILIKE '%oem vehicle price increase%' AND is_active=TRUE",
        "OEM vehicle price increase"
    ),
    (
        "UPDATE pestel_factors SET "
        "name = 'INR/USD at Rs 85-86 — export competitiveness pressure', "
        "selection_reasoning = 'INR/USD at approximately Rs 85-86 (April 2026, RBI reference). Export competitiveness factor for all export-oriented segments.', "
        "segment_relevance = '{\"4W_PV\":\"H\",\"LCV\":\"H\",\"HCV\":\"H\",\"2W\":\"M\",\"3W\":\"L\",\"Tractor\":\"L\"}'::jsonb "
        "WHERE name ILIKE '%inr/usd at%84%' AND is_active=TRUE",
        "INR/USD stale name"
    ),
    (
        "UPDATE pestel_factors SET segment_relevance = "
        "'{\"4W_PV\":\"H\",\"LCV\":\"L\",\"HCV\":\"L\",\"2W\":\"L\",\"3W\":\"L\",\"Tractor\":\"L\"}'::jsonb "
        "WHERE name ILIKE '%adas%l3%radar%lidar%' AND is_active=TRUE",
        "ADAS L3 radar/LiDAR"
    ),
    (
        "UPDATE pestel_factors SET segment_relevance = "
        "'{\"4W_PV\":\"H\",\"LCV\":\"H\",\"HCV\":\"H\",\"2W\":\"M\",\"3W\":\"L\",\"Tractor\":\"L\"}'::jsonb "
        "WHERE name ILIKE '%auto component export%22.9%' AND is_active=TRUE",
        "Auto exports 22.9B"
    ),
    (
        "UPDATE pestel_factors SET likelihood=8, impact=5, "
        "segment_relevance = '{\"4W_PV\":\"H\",\"LCV\":\"H\",\"HCV\":\"H\",\"2W\":\"M\",\"3W\":\"M\",\"Tractor\":\"M\"}'::jsonb "
        "WHERE name ILIKE '%fy26 best-ever%' AND is_active=TRUE",
        "FY26 best-ever"
    ),
    (
        "UPDATE pestel_factors SET likelihood=8, impact=5, "
        "segment_relevance = '{\"4W_PV\":\"H\",\"LCV\":\"H\",\"HCV\":\"H\",\"2W\":\"M\",\"3W\":\"M\",\"Tractor\":\"M\"}'::jsonb "
        "WHERE name ILIKE '%auto component%h1%6.8%' AND is_active=TRUE",
        "Auto component H1"
    ),
    (
        "UPDATE pestel_factors SET likelihood=5, impact=6, "
        "segment_relevance = '{\"4W_PV\":\"H\",\"LCV\":\"H\",\"HCV\":\"H\",\"2W\":\"H\",\"3W\":\"H\",\"Tractor\":\"H\"}'::jsonb "
        "WHERE name ILIKE '%automotive mission%2047%' AND is_active=TRUE",
        "Automotive Mission 2047"
    ),
    (
        "UPDATE pestel_factors SET "
        "segment_relevance = '{\"4W_PV\":\"H\",\"LCV\":\"H\",\"HCV\":\"H\",\"2W\":\"M\",\"3W\":\"M\",\"Tractor\":\"H\"}'::jsonb "
        "WHERE name ILIKE '%west asia conflict%' AND is_active=TRUE",
        "West Asia conflict"
    ),
    (
        "UPDATE pestel_factors SET "
        "segment_relevance = '{\"4W_PV\":\"H\",\"LCV\":\"M\",\"HCV\":\"H\",\"2W\":\"H\",\"3W\":\"M\",\"Tractor\":\"L\"}'::jsonb "
        "WHERE name ILIKE '%rare earth magnet%' AND is_active=TRUE",
        "Rare earth magnet"
    ),
    (
        "UPDATE pestel_factors SET "
        "segment_relevance = '{\"4W_PV\":\"L\",\"LCV\":\"M\",\"HCV\":\"H\",\"2W\":\"L\",\"3W\":\"L\",\"Tractor\":\"L\"}'::jsonb "
        "WHERE (name ILIKE '%e-bus%truck%localisation%' OR name ILIKE '%ebus%truck%localisation%') AND is_active=TRUE",
        "E-bus/truck localisation"
    ),
    # Dedup: keep highest-scoring multi-OEM SUV factor only
    (
        "UPDATE pestel_factors SET is_active=FALSE "
        "WHERE name ILIKE '%multi-oem suv%' AND is_active=TRUE "
        "AND id NOT IN ("
        "  SELECT id FROM pestel_factors WHERE name ILIKE '%multi-oem suv%' AND is_active=TRUE "
        "  ORDER BY (likelihood * impact) DESC NULLS LAST LIMIT 1"
        ")",
        "Dedup multi-OEM SUV"
    ),
    # Dedup: keep highest-scoring multi-OEM EV platform factor only
    (
        "UPDATE pestel_factors SET is_active=FALSE "
        "WHERE name ILIKE '%multi oem ev%' AND is_active=TRUE "
        "AND id NOT IN ("
        "  SELECT id FROM pestel_factors WHERE name ILIKE '%multi oem ev%' AND is_active=TRUE "
        "  ORDER BY (likelihood * impact) DESC NULLS LAST LIMIT 1"
        ")",
        "Dedup multi-OEM EV"
    ),
]

VERIFY_SQL = """
SELECT name, category,
    likelihood, impact,
    segment_relevance->>'4W_PV' AS pv,
    segment_relevance->>'LCV'   AS lcv,
    segment_relevance->>'HCV'   AS hcv,
    segment_relevance->>'2W'    AS w2,
    segment_relevance->>'3W'    AS w3,
    segment_relevance->>'Tractor' AS tr
FROM pestel_factors WHERE is_active=TRUE
ORDER BY (likelihood * impact) DESC;
"""


async def run():
    conn = await asyncpg.connect(
        "postgresql://postgres:sarthak@localhost:5432/mobility_intelligence"
    )
    total_rows = 0
    print("Running segment_relevance fixes...\n")
    for sql, label in SQL_FIXES:
        try:
            status = await conn.execute(sql)
            rows = int(status.split()[-1]) if status else 0
            total_rows += rows
            print(f"  [{rows:2d} rows] {label}")
        except Exception as e:
            print(f"  [ERROR] {label}: {e}")

    print(f"\n--- Total rows affected: {total_rows} ---\n")

    # Show verification — top 20 by likelihood*impact
    print("Top 20 active factors (by L×I):\n")
    rows = await conn.fetch(VERIFY_SQL)
    print(f"{'NAME':<55} {'C':1} {'L':3} {'I':3}  {'4W':2} {'LCV':3} {'HCV':3} {'2W':2} {'3W':2} {'Tr':2}")
    print("-" * 85)
    for i, r in enumerate(rows[:20]):
        name_short = (r["name"] or "")[:54]
        print(f"{name_short:<55} {r['category']:1} {(r['likelihood'] or 0):3.0f} {(r['impact'] or 0):3.0f}  "
              f"{(r['pv'] or '-'):2} {(r['lcv'] or '-'):3} {(r['hcv'] or '-'):3} "
              f"{(r['w2'] or '-'):2} {(r['w3'] or '-'):2} {(r['tr'] or '-'):2}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
