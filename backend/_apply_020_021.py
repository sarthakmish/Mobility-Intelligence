import asyncio, asyncpg

async def main():
    c = await asyncpg.connect("postgresql://postgres:sarthak@localhost:5432/mobility_intelligence")
    
    for mig in ["020_fix_ev_aggregate_factor.sql", "021_sync_origin_with_key_dates.sql"]:
        sql = open(f"db/migrations/{mig}").read()
        print(f"\n--- Running {mig} ---")
        await c.execute(sql)
        print("Done")
    
    # Verify P10
    rows = await c.fetch("SELECT code, name, segment_relevance->>'4W_PV' AS rel_4w, impact FROM pestel_factors WHERE name ILIKE '%EV penetration%8%' AND is_active = TRUE LIMIT 3")
    print("\n=== P10: EV penetration factor ===")
    for r in rows:
        print(f"  {r['code']}: 4W_PV={r['rel_4w']}, impact={r['impact']}")
        print(f"    Name: {r['name'][:80]}")
    
    # Verify P13: mismatches
    mismatches = await c.fetchval("""
        SELECT COUNT(*) FROM pestel_factors
        WHERE is_active = TRUE
          AND key_dates->>'announced' IS NOT NULL
          AND key_dates->>'announced' != ''
          AND (CASE WHEN (key_dates->>'announced') ~ '^\\d{4}-\\d{2}$'
                    THEN ((key_dates->>'announced') || '-01')::date
                    WHEN (key_dates->>'announced') ~ '^\\d{4}-\\d{2}-\\d{2}$'
                    THEN (key_dates->>'announced')::date
                    ELSE NULL END) != origin_date
          AND (CASE WHEN (key_dates->>'announced') ~ '^\\d{4}-\\d{2}$'
                    THEN ((key_dates->>'announced') || '-01')::date
                    WHEN (key_dates->>'announced') ~ '^\\d{4}-\\d{2}-\\d{2}$'
                    THEN (key_dates->>'announced')::date
                    ELSE NULL END) IS NOT NULL
    """)
    print(f"\n=== P13: origin_date mismatches remaining: {mismatches} ===")
    
    # Verify UN R155
    unr = await c.fetchrow("SELECT code, name, origin_date, key_dates->>'announced' AS ann FROM pestel_factors WHERE is_active = TRUE AND (name ILIKE '%UN R155%' OR code ILIKE '%un_r155%') LIMIT 1")
    if unr:
        print(f"\n=== UN R155: origin={unr['origin_date']} announced={unr['ann']} ===")
    
    await c.close()

asyncio.run(main())
