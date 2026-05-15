"""
============================================================
SEED — Competitor market shares for Solutions/Services/OS/Compute
============================================================
Adds entries to competitor_pillar_shares table.
Uses asyncpg directly (same pattern as seed_competitors.py).

Run:
  cd backend
  python -m scripts.seed_competitors_solutions             # dry-run
  python -m scripts.seed_competitors_solutions --apply     # commit
============================================================
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg

import os
DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/mobility_intelligence").replace("postgresql+asyncpg://", "postgresql://")
APPLY = "--apply" in sys.argv

# ── New competitors to register (only those not already in the DB) ──
NEW_COMPETITORS = [
    ("blackbuck",    "BlackBuck",           "BlackBuck",     "India",       "Tier-1",    "#f97316", "India-wide fleet operations"),
    ("rivigo",       "Rivigo",              "Rivigo",        "India",       "Tier-2",    "#8b5cf6", "India long-haul logistics"),
    ("locus",        "Locus.sh",            "Locus",         "India",       "Tier-2",    "#06b6d4", "India last-mile route optimization"),
    ("blue_dart",    "Blue Dart Express",   "Blue Dart",     "India",       "Tier-2",    "#0ea5e9", "India express logistics fleet"),
    ("delhivery",    "Delhivery",           "Delhivery",     "India",       "Tier-1",    "#10b981", "India ecommerce logistics"),
    ("ola",          "Ola Electric",        "Ola",           "India",       "Tier-1",    "#f59e0b", "India EV 2W + fleet"),
    ("ather",        "Ather Energy",        "Ather",         "India",       "Tier-2",    "#22c55e", "India premium EV 2W"),
    ("tvs",          "TVS Motor Company",   "TVS",           "India",       "Tier-1",    "#ef4444", "India 2W + EV"),
    ("yulu",         "Yulu Bikes",          "Yulu",          "India",       "Tier-3",    "#64748b", "India EV 2W shared mobility"),
    ("mahindra",     "Mahindra & Mahindra", "Mahindra",      "India",       "Tier-1",    "#dc2626", "India 4W PV/SUV/3W"),
    ("piaggio",      "Piaggio India",       "Piaggio",       "India",       "Tier-2",    "#6366f1", "India 3W"),
    ("bajaj",        "Bajaj Auto",          "Bajaj",         "India",       "Tier-1",    "#f97316", "India 2W + 3W"),
    ("hero",         "Hero MotoCorp",       "Hero",          "India",       "Tier-1",    "#3b82f6", "India 2W market leader"),
    ("zoomcar",      "Zoomcar",             "Zoomcar",       "India",       "Tier-3",    "#94a3b8", "India shared car platform"),
    ("kpit",         "KPIT Technologies",   "KPIT",          "India",       "Tier-1",    "#185FA5", "India ADAS/EV software"),
    ("tata_tech",    "Tata Technologies",   "Tata Tech",     "India",       "Tier-1",    "#D85A30", "India auto software services"),
    ("tata_elxsi",   "Tata Elxsi",         "Tata Elxsi",    "India",       "Tier-1",    "#1D9E75", "India auto ADAS software"),
    ("ashok_leyland","Ashok Leyland",       "Ashok Leyland", "India",       "Tier-1",    "#BA7517", "India HCV/LCV OEM"),
    ("vehant",       "Vehant Technologies", "Vehant",        "India",       "Tier-3",    "#534AB7", "India fleet AI startup"),
    ("mapmyindia",   "MapmyIndia (CE Info)", "MapmyIndia",   "India",       "Tier-1",    "#0F6E56", "India automotive maps leader"),
    ("here",         "HERE Technologies",   "HERE",          "Netherlands", "Tier-1",    "#185FA5", "Global HD maps"),
    ("google",       "Google Maps Automotive","Google",      "USA",         "Tech",      "#ef4444", "Global consumer maps"),
    ("tomtom",       "TomTom",              "TomTom",        "Netherlands", "Tier-1",    "#3b82f6", "Global automotive navigation"),
    ("nvidia",       "NVIDIA Corporation",  "NVIDIA",        "USA",         "Tech",      "#22c55e", "DRIVE Orin compute platform"),
    ("infineon",     "Infineon Technologies","Infineon",     "Germany",     "Tech",      "#f59e0b", "AURIX MCU + power semis"),
]

# ── Pillar-level market share data ──
# Format: {pillar: {segment: [(competitor_code, share_pct, source_note)]}}
SHARE_DATA = {
    "Solutions": {
        "4W_PV": [
            ("bosch",       18, "Bosch Connected Mobility Solutions India"),
            ("tata_tech",   15, "Tata Technologies Connected Vehicle platform"),
            ("kpit",        12, "KPIT cloud-mobility platforms"),
            ("mahindra",    10, "M&M digital mobility + connected SUV"),
            ("blackbuck",    8, "BlackBuck logistics + passenger fleet"),
            ("rivigo",       6, "Rivigo fleet OS + analytics"),
            ("ola",          7, "Ola Electric MoveOS for 4W fleet"),
            ("zoomcar",      4, "Zoomcar shared mobility ops"),
        ],
        "LCV": [
            ("blackbuck",   22, "BlackBuck dominant in LCV fleet tracking"),
            ("rivigo",      14, "Rivigo logistics LCV platform"),
            ("bosch",       12, "Bosch LCV connected services + RideCare"),
            ("tata_tech",   10, "Tata Tech LCV diagnostics"),
            ("locus",        8, "Locus.sh LCV last-mile routing"),
            ("blue_dart",    6, "Blue Dart in-house fleet OS"),
            ("delhivery",   10, "Delhivery proprietary LCV fleet OS"),
        ],
        "HCV": [
            ("bosch",       16, "Bosch HCV RideCare + predictive maintenance"),
            ("tata_tech",   14, "Tata Tech HCV connected services"),
            ("blackbuck",   18, "BlackBuck HCV truck tracking + scoring"),
            ("rivigo",      12, "Rivigo HCV long-haul platform"),
            ("ashok_leyland", 8, "Ashok Leyland Sumeru connected OS"),
            ("vehant",       6, "Vehant fleet AI platform"),
        ],
        "2W": [
            ("ola",         28, "Ola Electric MoveOS for 2W fleet"),
            ("ather",       16, "Ather AtherStack fleet management"),
            ("tvs",         12, "TVS Fleet App for e-2W fleets"),
            ("bosch",       10, "Bosch 2W fleet pilot programs"),
            ("hero",         8, "Hero VIDA fleet services"),
            ("yulu",         9, "Yulu Bikes fleet OS"),
        ],
        "3W": [
            ("ola",         18, "Ola Electric e-3W fleet platform"),
            ("mahindra",    16, "Mahindra Treo fleet services"),
            ("piaggio",     14, "Piaggio Apé fleet management"),
            ("bajaj",       12, "Bajaj RE fleet telematics"),
            ("bosch",        8, "Bosch 3W connected pilot"),
        ],
        "Tractor": [
            ("bosch",       20, "Bosch precision agri + tractor connected"),
            ("mahindra",    25, "Mahindra FarmEasy + JIVO connected"),
            ("tata_tech",   10, "Tata Tech farm services"),
        ],
    },
    "Services": {
        "4W_PV": [
            ("mapmyindia",  35, "MapmyIndia automotive maps market leader India"),
            ("here",        20, "HERE Technologies India automotive"),
            ("google",      15, "Google Maps automotive via Android Auto"),
            ("bosch",       12, "Bosch connected map + Battery-in-Cloud services"),
            ("tomtom",       8, "TomTom India automotive (limited presence)"),
        ],
        "LCV": [
            ("mapmyindia",  38, "MapmyIndia LCV navigation + fleet maps"),
            ("here",        22, "HERE LCV routing"),
            ("google",      14, "Google Maps LCV via infotainment"),
            ("bosch",       10, "Bosch connected LCV services"),
        ],
        "HCV": [
            ("mapmyindia",  40, "MapmyIndia AIS-140 compliant HCV maps"),
            ("here",        24, "HERE HD maps for HCV routing"),
            ("bosch",       12, "Bosch HCV connected services"),
            ("google",      10, "Google HCV navigation"),
        ],
        "2W": [
            ("mapmyindia",  30, "MapmyIndia 2W navigation + EVMap"),
            ("google",      25, "Google Maps dominant on 2W smartphones"),
            ("bosch",       12, "Bosch 2W connected services + eBike"),
            ("ola",         10, "Ola Maps (built from MapmyIndia data)"),
        ],
        "3W": [
            ("mapmyindia",  40, "MapmyIndia 3W + EV charging map"),
            ("google",      20, "Google Maps 3W routing"),
            ("ola",         15, "Ola Maps 3W routing"),
            ("bosch",        8, "Bosch connected 3W pilot"),
        ],
        "HCV": [
            ("mapmyindia",  40, "MapmyIndia AIS-140 compliant HCV maps"),
            ("here",        24, "HERE HD maps for HCV routing"),
            ("bosch",       12, "Bosch HCV connected services"),
            ("google",      10, "Google HCV navigation"),
        ],
    },
    "OS": {
        "4W_PV": [
            ("bosch",       28, "Bosch ADAS L0-L3 stack + VMM software"),
            ("kpit",        16, "KPIT autonomous & motion software India"),
            ("continental", 14, "Continental driving-functions stack"),
            ("zf",          10, "ZF cubiX motion-management software"),
            ("tata_elxsi",   8, "Tata Elxsi ADAS software services"),
            ("aptiv",        6, "Aptiv L2-L3 software stack"),
            ("mobileye",    10, "Mobileye SuperVision via OEM integrations"),
        ],
        "LCV": [
            ("bosch",       32, "Bosch LCV ADAS + motion software"),
            ("kpit",        18, "KPIT LCV software"),
            ("continental", 14, "Continental LCV driving functions"),
            ("tata_elxsi",  10, "Tata Elxsi LCV integration"),
        ],
        "HCV": [
            ("bosch",       30, "Bosch HCV ADAS stack (AEBS, DMS)"),
            ("kpit",        16, "KPIT HCV software"),
            ("ashok_leyland", 12, "Ashok Leyland in-house HCV motion software"),
            ("continental", 12, "Continental HCV driving functions"),
        ],
    },
    "Compute": {
        "4W_PV": [
            ("bosch",       22, "Bosch DASy ADAS domain controller"),
            ("nvidia",      18, "NVIDIA DRIVE Orin (via multiple OEMs)"),
            ("qualcomm",    15, "Qualcomm Snapdragon Ride platform"),
            ("continental", 12, "Continental High-Performance Computer"),
            ("aptiv",        8, "Aptiv Smart Vehicle Architecture compute"),
            ("mobileye",     7, "Mobileye EyeQ SoC"),
            ("tata_elxsi",   6, "Tata Elxsi DCU integration services"),
            ("infineon",     5, "Infineon AURIX TriCore MCU"),
        ],
        "LCV": [
            ("bosch",       28, "Bosch LCV compute module"),
            ("continental", 18, "Continental LCV ECU/DCU"),
            ("qualcomm",    12, "Qualcomm LCV compute"),
            ("tata_elxsi",  10, "Tata Elxsi LCV integration"),
        ],
        "HCV": [
            ("bosch",       25, "Bosch HCV compute + AEBS ECU"),
            ("continental", 20, "Continental HCV compute"),
            ("aptiv",       12, "Aptiv HCV architecture"),
            ("tata_elxsi",   8, "Tata Elxsi HCV integration"),
        ],
    },
}


async def ensure_competitor(conn, code, name, short_name, hq, tier, color, india_presence):
    existing = await conn.fetchval("SELECT code FROM competitors WHERE code = $1", code)
    if existing:
        return  # already there
    if APPLY:
        await conn.execute("""
            INSERT INTO competitors
                (code, name, short_name, headquarters, tier, color, india_presence, is_active)
            VALUES ($1,$2,$3,$4,$5,$6,$7,TRUE)
            ON CONFLICT (code) DO NOTHING
        """, code, name, short_name, hq, tier, color, india_presence)
        print(f"  [COMP+] {code}")
    else:
        print(f"  [COMP ] {code} — would register")


async def main():
    conn = await asyncpg.connect(DB_URL)
    try:
        # Ensure all new competitors exist
        print("Registering new competitors...")
        for args in NEW_COMPETITORS:
            await ensure_competitor(conn, *args)

        print("\nSeeding pillar shares...")
        added = 0
        for pillar, segs in SHARE_DATA.items():
            for seg, players in segs.items():
                for code, share_pct, note in players:
                    if not APPLY:
                        print(f"  [PLAN] {pillar:<12s} {seg:<8s} {code:<16s} {share_pct}%")
                        continue
                    await conn.execute("""
                        INSERT INTO competitor_pillar_shares
                            (competitor_code, pillar, segment, market_share_pct,
                             revenue_cr, confidence, source_note, fiscal_year)
                        VALUES ($1,$2,$3,$4,$5,'ai_estimate',$6,'FY25')
                        ON CONFLICT (competitor_code, pillar, segment)
                        DO UPDATE SET
                            market_share_pct = EXCLUDED.market_share_pct,
                            source_note      = EXCLUDED.source_note
                    """, code, pillar, seg,
                        float(share_pct),
                        float(share_pct * 10),  # rough revenue proxy
                        note or f"AI Estimate: {pillar} India players",
                    )
                    added += 1

        if APPLY:
            total_plan = sum(len(v) for segs in SHARE_DATA.values() for v in segs.values())
            print(f"\n  ✅ Inserted/updated {added} pillar-share rows.")
        else:
            total_plan = sum(len(v) for segs in SHARE_DATA.values() for v in segs.values())
            print(f"\n  Dry run: would insert {total_plan} pillar-share rows.")
            print(f"  Run with --apply to commit.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
