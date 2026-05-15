"""
============================================================
SEED — Cloud pillar competitor data
============================================================
Populates competitor_pillar_shares for the Cloud pillar across
all 6 segments. India-active cloud + connected mobility players.

Idempotent. Safe to re-run.

Run:
  python -m scripts.seed_cloud_competitors             # dry run
  python -m scripts.seed_cloud_competitors --apply
============================================================
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncpg

APPLY = "--apply" in sys.argv

import os
DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/mobility_intelligence").replace("postgresql+asyncpg://", "postgresql://")

# ── Cloud pillar players: connected vehicle clouds, V2X infra, OTA platforms ──
CLOUD_PLAYERS = {
    "4W_PV": [
        ("aws",           18, "AWS for Automotive — Tata, Mahindra, Maruti backends"),
        ("azure",         16, "Microsoft Azure connected vehicle — used by JLR, Mercedes"),
        ("google_cloud",  12, "Google Cloud Platform — Hyundai, Renault India infra"),
        ("bosch",         14, "Bosch IoT Suite + Mobility Cloud Platform"),
        ("kpit",          10, "KPIT Sparkle cloud platform for OEMs"),
        ("wipro",          8, "Wipro IoT + connected mobility services"),
        ("tcs",           10, "TCS DAEMON connected vehicle platform"),
        ("infosys",        6, "Infosys edge analytics for telematics"),
        ("airtel",         4, "Airtel IoT connectivity for connected cars"),
        ("jio",            2, "Jio Platforms — connected car APIs (early stage)"),
    ],
    "LCV": [
        ("aws",           22, ""),
        ("azure",         18, ""),
        ("bosch",         14, ""),
        ("tcs",           12, ""),
        ("kpit",          10, ""),
        ("airtel",         8, "Fleet IoT connectivity"),
        ("jio",            6, ""),
        ("wipro",         10, ""),
    ],
    "HCV": [
        ("aws",           20, ""),
        ("azure",         16, ""),
        ("bosch",         18, "Bosch RideCare for fleet HCV"),
        ("kpit",          12, ""),
        ("ashok_leyland", 10, "Ashok Leyland iAlert proprietary cloud"),
        ("tcs",           14, ""),
        ("airtel",         6, ""),
        ("jio",            4, ""),
    ],
    "2W": [
        ("aws",           16, ""),
        ("azure",         12, ""),
        ("google_cloud",  14, ""),
        ("ola",           18, "Ola MoveOS cloud — Ola Electric proprietary"),
        ("ather",         14, "Ather AtherStack cloud"),
        ("tvs",           10, "TVS SmartXConnect cloud"),
        ("bosch",          8, ""),
        ("airtel",         4, ""),
        ("jio",            4, ""),
    ],
    "3W": [
        ("aws",           18, ""),
        ("azure",         14, ""),
        ("ola",           20, "Ola Electric e-3W telematics cloud"),
        ("mahindra",      14, "Mahindra Treo telematics"),
        ("bajaj",         12, "Bajaj RE connected fleet"),
        ("piaggio",       10, "Piaggio Apé fleet cloud"),
        ("airtel",         6, ""),
        ("jio",            6, ""),
    ],
    "Tractor": [
        ("aws",           16, ""),
        ("azure",         14, ""),
        ("mahindra",      22, "Mahindra Krish-e tractor cloud platform"),
        ("escorts",       18, "Escorts NXT connected tractor"),
        ("tafe",          14, "TAFE J-Farm cloud agriculture platform"),
        ("john_deere",    10, "John Deere Operations Center India"),
        ("bosch",          6, ""),
    ],
}

NEW_COMPETITORS = [
    ("aws",          "Amazon Web Services",    "tier_tech", "USA"),
    ("azure",        "Microsoft Azure",        "tier_tech", "USA"),
    ("google_cloud", "Google Cloud Platform",  "tier_tech", "USA"),
    ("wipro",        "Wipro IoT",              "tier1",     "India"),
    ("tcs",          "Tata Consultancy Svcs",  "tier1",     "India"),
    ("infosys",      "Infosys",                "tier1",     "India"),
    ("airtel",       "Bharti Airtel IoT",      "tier1",     "India"),
    ("jio",          "Jio Platforms",          "tier1",     "India"),
    ("tafe",         "TAFE Tractors",          "tier1",     "India"),
    ("john_deere",   "John Deere India",       "tier1",     "USA"),
]


async def main():
    conn = await asyncpg.connect(DB_URL)
    try:
        # Register new competitor records
        for code, name, tier, country in NEW_COMPETITORS:
            exists = await conn.fetchval("SELECT 1 FROM competitors WHERE code=$1", code)
            if not exists:
                if APPLY:
                    await conn.execute("""
                        INSERT INTO competitors
                            (code, name, short_name, headquarters, tier,
                             india_presence, color, is_active)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,TRUE)
                        ON CONFLICT (code) DO NOTHING
                    """, code, name, name[:20], country, tier, "Active", "#0ea5e9")
                    print(f"  [NEW] competitor: {code}")
                else:
                    print(f"  [PLAN] new competitor: {code} ({name})")

        # Insert pillar shares for Cloud
        added = 0
        for seg, players in CLOUD_PLAYERS.items():
            for code, share_pct, note in players:
                if not APPLY:
                    print(f"  [PLAN] Cloud · {seg:<8s} {code:<16s} {share_pct}%")
                    continue
                await conn.execute("""
                    INSERT INTO competitor_pillar_shares
                        (competitor_code, pillar, segment, market_share_pct,
                         revenue_cr, confidence, source_note)
                    VALUES ($1, 'Cloud', $2, $3, $4, 'low', $5)
                    ON CONFLICT (competitor_code, pillar, segment)
                    DO UPDATE SET market_share_pct = EXCLUDED.market_share_pct,
                                  source_note = EXCLUDED.source_note
                """, code, seg, share_pct, share_pct * 8,
                    note or "AI Estimate: Cloud pillar India players (FY25)")
                added += 1

        if APPLY:
            print(f"\n  ✅ Inserted/updated {added} Cloud pillar share rows.")
        else:
            total = sum(len(v) for v in CLOUD_PLAYERS.values())
            print(f"\n  Would insert {total} Cloud share rows.")
            print("  Run with --apply to commit.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
