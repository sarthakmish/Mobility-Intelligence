import asyncio
import asyncpg
import os

_DEFAULT_DB = "postgresql://postgres:postgres@localhost:5432/mobility_intelligence"

async def run():
    conn = await asyncpg.connect(
        os.environ.get("DATABASE_URL", _DEFAULT_DB).replace("postgresql+asyncpg://", "postgresql://")
    )
    r = await conn.execute(
        "UPDATE pestel_factors SET segment_relevance = "
        "'{\"4W_PV\":\"H\",\"LCV\":\"M\",\"HCV\":\"L\",\"2W\":\"H\",\"3W\":\"L\",\"Tractor\":\"L\"}'::jsonb "
        "WHERE name ILIKE '%ethanol blending e20%' AND is_active=TRUE"
    )
    print("Ethanol Blending E20 fix:", r)
    rows = await conn.fetch(
        "SELECT name, segment_relevance->>'4W_PV' as pv, segment_relevance->>'LCV' as lcv, "
        "segment_relevance->>'2W' as w2 FROM pestel_factors WHERE name ILIKE '%ethanol%' AND is_active=TRUE"
    )
    for row in rows:
        print(f"  {row['name'][:65]} | 4W:{row['pv']} LCV:{row['lcv']} 2W:{row['w2']}")
    await conn.close()

asyncio.run(run())
