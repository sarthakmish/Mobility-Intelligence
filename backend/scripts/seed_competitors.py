"""
Seed competitor data using the platform's LLMService (Claude Sonnet via LLM Farm).
Run: cd backend && python -m scripts.seed_competitors

Cost: ~$5-8 total for all pillars × segments.
All shares marked 'ai_estimate' — honest about methodology.
"""
import asyncio
import json
import re
import asyncpg
import sys
import os

# Allow imports from backend root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.llm_service import LLMService

DB_URL = "postgresql://postgres:sarthak@localhost:5432/mobility_intelligence"
llm = LLMService()


PILLARS = ["ADAS", "Motion", "Energy", "Body & Comfort", "Infotainment"]
SEGMENTS = ["4W_PV", "LCV", "HCV", "2W", "3W", "Tractor"]

COMPETITORS_SEED = [
    {"code": "bosch", "name": "Robert Bosch GmbH", "short_name": "Bosch", "headquarters": "Germany", "tier": "Tier-1", "color": "#ef4444", "india_presence": "Bosch India, Nashik + Bengaluru plants"},
    {"code": "continental", "name": "Continental AG", "short_name": "Continental", "headquarters": "Germany", "tier": "Tier-1", "color": "#3b82f6", "india_presence": "Continental India, multiple plants"},
    {"code": "zf", "name": "ZF Friedrichshafen AG", "short_name": "ZF", "headquarters": "Germany", "tier": "Tier-1", "color": "#8b5cf6", "india_presence": "ZF India, Pune + Chennai"},
    {"code": "denso", "name": "DENSO Corporation", "short_name": "Denso", "headquarters": "Japan", "tier": "Tier-1", "color": "#f59e0b", "india_presence": "Denso India, Manesar"},
    {"code": "aptiv", "name": "Aptiv PLC", "short_name": "Aptiv", "headquarters": "Ireland", "tier": "Tier-1", "color": "#06b6d4", "india_presence": "Limited India presence"},
    {"code": "valeo", "name": "Valeo SA", "short_name": "Valeo", "headquarters": "France", "tier": "Tier-1", "color": "#10b981", "india_presence": "Valeo India, Chennai + Pune"},
    {"code": "mobileye", "name": "Mobileye Global Inc", "short_name": "Mobileye", "headquarters": "Israel", "tier": "Tech", "color": "#f97316", "india_presence": "Software only"},
    {"code": "qualcomm", "name": "Qualcomm Technologies", "short_name": "Qualcomm", "headquarters": "USA", "tier": "Tech", "color": "#6366f1", "india_presence": "Bangalore R&D"},
    {"code": "nxp", "name": "NXP Semiconductors", "short_name": "NXP", "headquarters": "Netherlands", "tier": "Tech", "color": "#0ea5e9", "india_presence": "India design center"},
    {"code": "autoliv", "name": "Autoliv Inc", "short_name": "Autoliv", "headquarters": "Sweden", "tier": "Tier-1", "color": "#ec4899", "india_presence": "Autoliv India, Chennai"},
    {"code": "magna", "name": "Magna International", "short_name": "Magna", "headquarters": "Canada", "tier": "Tier-1", "color": "#64748b", "india_presence": "Limited"},
    {"code": "brembo", "name": "Brembo SpA", "short_name": "Brembo", "headquarters": "Italy", "tier": "Tier-1", "color": "#dc2626", "india_presence": "Brembo India"},
]

PROMPT_PILLAR_SHARES = """You are an automotive market intelligence analyst specializing in India.
Estimate market share percentages for the following Tier-1 automotive suppliers in the {pillar} technology domain for the {segment} vehicle segment in India (FY2025).

Competitors: {competitors}

Rules:
- Shares should sum to approximately 100% for the top players (others = rest of market)
- Focus only on suppliers that are ACTUALLY present in {pillar} for {segment}
- If a supplier has no meaningful presence, set share to 0
- Be realistic: Bosch, Continental, ZF dominate ADAS; Denso, Bosch dominate Motion; etc.
- Revenue in INR Crore (rough estimate based on overall Indian auto component market being ~₹6.73 lakh crore)

Respond ONLY with valid JSON array:
[
  {{"competitor_code": "bosch", "market_share_pct": 28.5, "revenue_cr": 850, "source_note": "Estimated from Bosch India annual reports and market position"}},
  ...
]
Only include competitors with share > 0."""

PROMPT_TECH_SHARES = """You are an automotive market intelligence analyst.
For the technology "{tech_name}" (code: {tech_code}) in the {segment} segment in India (FY2025),
estimate which suppliers have what market share.

Known suppliers: {competitors}

Respond ONLY with valid JSON array:
[
  {{"competitor_code": "bosch", "market_share_pct": 35.0, "revenue_cr": 120, "strength": "market_leader", "source_note": "Dominant in radar-based ADAS for 4W PV"}},
  ...
]
strength values: "market_leader" | "strong_presence" | "present" | "emerging"
Only include competitors with actual presence (share > 0)."""

PROMPT_OEM_SOURCING = """For the technology "{tech_name}" (code: {tech_code}) in {segment} vehicles in India (FY2025),
list which OEMs source from which suppliers.

Known OEMs in India for {segment}: {oems}
Known suppliers: {competitors}

Respond ONLY with valid JSON array:
[
  {{"oem_name": "Maruti Suzuki", "supplier_codes": "bosch,continental", "notes": "Bosch for radar, Continental for camera stack"}},
  ...
]
Only include OEMs that actually use this technology."""

SEGMENT_OEMS = {
    "4W_PV": "Maruti Suzuki, Hyundai India, Tata Motors, Mahindra, Toyota Kirloskar, Honda Cars, Kia India",
    "LCV": "Tata Motors, Mahindra, Ashok Leyland, Force Motors",
    "HCV": "Tata Motors, Ashok Leyland, Volvo India, Eicher Motors",
    "2W": "Hero MotoCorp, Honda Motorcycle, TVS Motors, Bajaj Auto, Royal Enfield",
    "3W": "Bajaj Auto, TVS Motors, Mahindra Electric, Piaggio India",
    "Tractor": "Mahindra Tractors, TAFE, Sonalika, John Deere India, New Holland India",
}


async def seed_competitors(conn):
    """Upsert base competitor records."""
    for c in COMPETITORS_SEED:
        await conn.execute("""
            INSERT INTO competitors (code, name, short_name, headquarters, tier, color, india_presence, is_active)
            VALUES ($1,$2,$3,$4,$5,$6,$7,TRUE)
            ON CONFLICT (code) DO UPDATE SET
                name=EXCLUDED.name, short_name=EXCLUDED.short_name,
                color=EXCLUDED.color, india_presence=EXCLUDED.india_presence
        """, c["code"], c["name"], c["short_name"], c["headquarters"],
            c["tier"], c["color"], c["india_presence"])
    print(f"  Seeded {len(COMPETITORS_SEED)} competitors")


async def seed_pillar_shares(conn):
    """Use Sonnet to estimate pillar-level market shares per segment."""
    comp_list = [f"{c['code']} ({c['short_name']})" for c in COMPETITORS_SEED]

    for pillar in PILLARS:
        for segment in SEGMENTS:
            print(f"  Pillar shares: {pillar} × {segment} ...", end=" ", flush=True)
            prompt = PROMPT_PILLAR_SHARES.format(
                pillar=pillar,
                segment=segment,
                competitors=", ".join(comp_list),
            )
            try:
                result = await llm.call_claude(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1024,
                    temperature=0.2,
                )
                raw = result["content"].strip()
                # Extract JSON array
                m = re.search(r'\[.*\]', raw, re.DOTALL)
                if not m:
                    print("SKIP (no JSON)")
                    continue
                shares = json.loads(m.group())
                count = 0
                for s in shares:
                    if not s.get("competitor_code") or not s.get("market_share_pct"):
                        continue
                    await conn.execute("""
                        INSERT INTO competitor_pillar_shares
                            (competitor_code, pillar, segment, market_share_pct, revenue_cr, confidence, source_note, fiscal_year)
                        VALUES ($1,$2,$3,$4,$5,'ai_estimate',$6,'FY25')
                        ON CONFLICT (competitor_code, pillar, segment) DO UPDATE SET
                            market_share_pct=EXCLUDED.market_share_pct,
                            revenue_cr=EXCLUDED.revenue_cr
                    """, s["competitor_code"], pillar, segment,
                        float(s["market_share_pct"]), float(s.get("revenue_cr") or 0),
                        s.get("source_note", "AI estimate"))
                    count += 1
                print(f"OK ({count} players)")
            except Exception as e:
                print(f"ERR: {e}")


async def seed_tech_shares(conn):
    """Use Sonnet to estimate tech-level shares for top technologies per pillar."""
    # Get top technologies by market size
    rows = await conn.fetch("""
        SELECT code, name, pillar,
            COALESCE((market_data->'4W_PV'->>'fy25')::numeric, 0) +
            COALESCE((market_data->'LCV'->>'fy25')::numeric, 0) +
            COALESCE((market_data->'HCV'->>'fy25')::numeric, 0) as total_size
        FROM technologies
        WHERE is_active = TRUE AND pillar = ANY($1)
        ORDER BY total_size DESC
        LIMIT 40
    """, PILLARS)

    comp_codes = ", ".join([c["code"] for c in COMPETITORS_SEED])

    for row in rows:
        for segment in ["4W_PV", "2W", "HCV"]:  # top 3 segments for tech
            print(f"  Tech shares: {row['name'][:30]} × {segment} ...", end=" ", flush=True)
            prompt = PROMPT_TECH_SHARES.format(
                tech_name=row["name"],
                tech_code=row["code"],
                segment=segment,
                competitors=comp_codes,
            )
            try:
                result = await llm.call_claude(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=800,
                    temperature=0.2,
                )
                raw = result["content"].strip()
                m = re.search(r'\[.*\]', raw, re.DOTALL)
                if not m:
                    print("SKIP")
                    continue
                shares = json.loads(m.group())
                count = 0
                for s in shares:
                    if not s.get("competitor_code") or not s.get("market_share_pct"):
                        continue
                    await conn.execute("""
                        INSERT INTO competitor_tech_shares
                            (competitor_code, tech_code, segment, market_share_pct, revenue_cr, strength, confidence, source_note)
                        VALUES ($1,$2,$3,$4,$5,$6,'ai_estimate',$7)
                        ON CONFLICT (competitor_code, tech_code, segment) DO UPDATE SET
                            market_share_pct=EXCLUDED.market_share_pct,
                            strength=EXCLUDED.strength
                    """, s["competitor_code"], row["code"], segment,
                        float(s["market_share_pct"]), float(s.get("revenue_cr") or 0),
                        s.get("strength", "present"),
                        s.get("source_note", "AI estimate"))
                    count += 1
                print(f"OK ({count})")
            except Exception as e:
                print(f"ERR: {e}")


async def seed_oem_sourcing(conn):
    """Seed OEM sourcing patterns for top technologies."""
    rows = await conn.fetch("""
        SELECT DISTINCT tech_code FROM competitor_tech_shares
        WHERE segment = '4W_PV' LIMIT 20
    """)
    comp_codes = ", ".join([c["code"] for c in COMPETITORS_SEED])

    for row in rows:
        tech = await conn.fetchrow("SELECT name FROM technologies WHERE code=$1", row["tech_code"])
        if not tech:
            continue
        for segment in ["4W_PV", "2W"]:
            print(f"  OEM sourcing: {tech['name'][:25]} × {segment} ...", end=" ", flush=True)
            prompt = PROMPT_OEM_SOURCING.format(
                tech_name=tech["name"],
                tech_code=row["tech_code"],
                segment=segment,
                oems=SEGMENT_OEMS.get(segment, ""),
                competitors=comp_codes,
            )
            try:
                result = await llm.call_claude(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=600,
                    temperature=0.2,
                )
                raw = result["content"].strip()
                m = re.search(r'\[.*\]', raw, re.DOTALL)
                if not m:
                    print("SKIP")
                    continue
                sourcing = json.loads(m.group())
                count = 0
                for s in sourcing:
                    if not s.get("oem_name") or not s.get("supplier_codes"):
                        continue
                    await conn.execute("""
                        INSERT INTO oem_sourcing (oem_name, tech_code, segment, supplier_codes, notes)
                        VALUES ($1,$2,$3,$4,$5)
                        ON CONFLICT (oem_name, tech_code, segment) DO UPDATE SET
                            supplier_codes=EXCLUDED.supplier_codes, notes=EXCLUDED.notes
                    """, s["oem_name"], row["tech_code"], segment,
                        s["supplier_codes"], s.get("notes", ""))
                    count += 1
                print(f"OK ({count})")
            except Exception as e:
                print(f"ERR: {e}")


async def main():
    print("Connecting to database...")
    conn = await asyncpg.connect(DB_URL)
    try:
        print("\n=== Pass 1: Seeding competitor records ===")
        await seed_competitors(conn)

        print("\n=== Pass 2: Pillar-level market shares (Sonnet) ===")
        print("  This runs Sonnet for each pillar × segment (~30 calls, ~$2-3)")
        await seed_pillar_shares(conn)

        print("\n=== Pass 3: Technology-level market shares (Sonnet) ===")
        print("  Top 40 technologies × 3 segments (~120 calls, ~$3-5)")
        await seed_tech_shares(conn)

        print("\n=== Pass 4: OEM sourcing patterns (Sonnet) ===")
        await seed_oem_sourcing(conn)

        print("\n=== DONE ===")
        player_count = await conn.fetchval("SELECT COUNT(*) FROM competitor_pillar_shares")
        tech_count = await conn.fetchval("SELECT COUNT(*) FROM competitor_tech_shares")
        oem_count = await conn.fetchval("SELECT COUNT(*) FROM oem_sourcing")
        print(f"  {player_count} pillar share rows")
        print(f"  {tech_count} tech share rows")
        print(f"  {oem_count} OEM sourcing rows")
    finally:
        await conn.close()
        await llm.farm_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
