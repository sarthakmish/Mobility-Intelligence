"""
============================================================
SEED — OEM Sourcing Patterns for technologies
============================================================
Populates the oem_sourcing table so V4 drilldown shows
"OEM Sourcing Patterns" for every tech in every pillar.

Inserts per tech_code × segment rows derived from pillar-level
patterns. Safe to re-run (ON CONFLICT DO UPDATE).

Run:
  python -m scripts.seed_oem_sourcing             # dry run
  python -m scripts.seed_oem_sourcing --apply
============================================================
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncpg

APPLY = "--apply" in sys.argv

DB_URL = "postgresql://postgres:sarthak@localhost:5432/mobility_intelligence"

# Segments to seed for (skip Tractor for most pillars — lower relevance)
ALL_SEGS = ["4W_PV", "LCV", "HCV", "2W", "3W", "Tractor"]

# ── OEM sourcing patterns by pillar ──
# Each entry: (oem_name, supplier_codes_text, notes)
PILLAR_PATTERNS = {
    "ADAS": [
        ("Tata Motors",      "Bosch (radar+camera), Mobileye (vision), Continental (DCU)",       ""),
        ("Mahindra",         "Bosch (full ADAS stack), ZF (steering control)",                    ""),
        ("Maruti Suzuki",    "Denso (camera), Continental (radar)",                               ""),
        ("Hyundai India",    "Mobis (Tier-1), Mobileye (vision), HL Mando",                      ""),
        ("Toyota Kirloskar", "Denso (full stack), Aisin (steering)",                              ""),
        ("MG Motor",         "Bosch (radar), Mobileye (vision)",                                  ""),
    ],
    "Motion": [
        ("Tata Motors",      "Bosch (CRDi, EPS), ZF (transmission), Mando (brakes)",             ""),
        ("Mahindra",         "Bosch (powertrain), Sona Comstar (drivetrain), Rane (steering)",    ""),
        ("Maruti Suzuki",    "Denso (injection), Aisin (transmission), Endurance (brakes)",       ""),
        ("Ashok Leyland",    "Bosch (CRDi+SCR), ZF (transmission), Wabco (brakes)",              ""),
        ("TVS Motor",        "Bosch (FI), Endurance (brakes+suspension)",                         ""),
        ("Bajaj Auto",       "Bosch (FI), Endurance (clutch), Rane (steering)",                   ""),
    ],
    "Energy": [
        ("Tata Motors",      "Tata AutoComp (BMS), Exide (cells), Bosch (charging mgmt)",        ""),
        ("Mahindra",         "Volvo Eicher (cells), KPIT (BMS SW), Mahindra in-house pack",       ""),
        ("Ola Electric",     "LG Energy (cells), proprietary BMS+pack assembly",                  ""),
        ("Ather Energy",     "LGES/CATL (cells), proprietary BMS",                                ""),
        ("Hero Electric",    "Amperex (cells), Battrixx (BMS)",                                   ""),
    ],
    "Body & Comfort": [
        ("Tata Motors",      "Motherson (panels+wiring), Subros (HVAC), Lumax (lighting)",        ""),
        ("Mahindra",         "Motherson (interiors), Minda (switches), Valeo (HVAC)",             ""),
        ("Maruti Suzuki",    "Subros (HVAC), Bharat Seats, Lumax (lights)",                       ""),
        ("Hyundai India",    "Mobis (modules), Doowon (HVAC), Hyundai Wia",                       ""),
    ],
    "Infotainment": [
        ("Tata Motors",      "Harman (head unit), Bosch (cluster), Visteon (HMI)",                ""),
        ("Mahindra",         "Visteon (cluster+HU), KPIT (HMI software)",                         ""),
        ("Maruti Suzuki",    "Denso TEN (head unit), JVC Kenwood, Yazaki (cluster)",               ""),
        ("MG Motor",         "Continental (head unit+cluster), Tata Elxsi (HMI)",                 ""),
    ],
    "Semiconductors": [
        ("Tata Motors",      "Infineon (MCU), NXP (radar IC), STMicro (sensors), RIR Power (SiC)", ""),
        ("Mahindra",         "Infineon, Renesas (MCU), Bosch MEMS",                                ""),
        ("Maruti Suzuki",    "Renesas, Toshiba, Denso (custom ASIC)",                              ""),
        ("Hyundai India",    "Mobis-internal + NXP, Infineon",                                     ""),
    ],
    "Actuators": [
        ("Tata Motors",      "Bosch (e-motors), ZF (steering), Brembo (brakes), Mando (suspension)", ""),
        ("Mahindra",         "Bosch, Sona Comstar (e-motors), Rane (steering+brakes)",             ""),
        ("Maruti Suzuki",    "Denso (e-motors), Aisin (steering), Endurance (brakes)",             ""),
        ("Ashok Leyland",    "Wabco (brakes), ZF (steering), Brakes India",                        ""),
    ],
    "ECUs": [
        ("Tata Motors",      "Bosch (engine ECU), Continental (body), KPIT (integration)",         ""),
        ("Mahindra",         "Bosch+Continental, Minda (body ECUs), Tata Elxsi (integration)",     ""),
        ("Maruti Suzuki",    "Denso (full stack), Hitachi Astemo, Keihin",                          ""),
        ("Hyundai India",    "Mobis (in-group), Continental, KEFICO",                              ""),
    ],
    "OS": [
        ("Tata Motors",      "KPIT (AUTOSAR), Bosch (driving functions), Tata Elxsi (HMI SW)",    ""),
        ("Mahindra",         "KPIT (vehicle SW), Tata Elxsi, Mahindra Susten",                     ""),
        ("Maruti Suzuki",    "Suzuki Tech Centre, Denso, KPIT (consulting)",                        ""),
    ],
    "Compute": [
        ("Tata Motors",      "NVIDIA Orin (DCU), Qualcomm Ride (cockpit), Bosch DASy",             ""),
        ("Mahindra",         "NVIDIA, Continental HPC, KPIT integration",                          ""),
        ("Maruti Suzuki",    "Denso (DCU), Renesas (MCU), Suzuki Tech Centre integration",          ""),
    ],
    "Solutions": [
        ("Tata Motors",      "Bosch RideCare, Tata Tech (fleet), AWS infra",                       ""),
        ("Mahindra",         "Bosch fleet, KPIT cloud, M&M digital in-house",                      ""),
        ("Ola Electric",     "Ola MoveOS proprietary, AWS backbone",                               ""),
    ],
    "Services": [
        ("Tata Motors",      "MapmyIndia, HERE, Bosch services, Google Maps",                      ""),
        ("Maruti Suzuki",    "MapmyIndia primary, Google Maps, JVC Kenwood",                       ""),
    ],
    "Cloud": [
        ("Tata Motors",      "AWS (primary), Azure (analytics), Bosch IoT Suite",                  ""),
        ("Mahindra",         "Azure primary, AWS secondary, KPIT Sparkle",                         ""),
        ("Ola Electric",     "AWS primary, Google Cloud (analytics)",                              ""),
    ],
}

# Segments relevant per pillar (skip segments where pillar has no applicability)
PILLAR_SEGS = {
    "ADAS":           ["4W_PV", "LCV", "HCV"],
    "Motion":         ["4W_PV", "LCV", "HCV", "2W", "3W", "Tractor"],
    "Energy":         ["4W_PV", "LCV", "HCV", "2W", "3W"],
    "Body & Comfort": ["4W_PV", "LCV", "HCV"],
    "Infotainment":   ["4W_PV", "LCV", "HCV"],
    "Semiconductors": ["4W_PV", "LCV", "HCV", "2W", "3W", "Tractor"],
    "Actuators":      ["4W_PV", "LCV", "HCV", "2W", "3W"],
    "ECUs":           ["4W_PV", "LCV", "HCV", "2W", "3W"],
    "OS":             ["4W_PV", "LCV", "HCV"],
    "Compute":        ["4W_PV", "LCV", "HCV"],
    "Solutions":      ["4W_PV", "LCV", "HCV", "2W", "3W"],
    "Services":       ["4W_PV", "LCV", "HCV", "2W", "3W"],
    "Cloud":          ["4W_PV", "LCV", "HCV", "2W", "3W"],
}


async def main():
    conn = await asyncpg.connect(DB_URL)
    try:
        # Ensure oem_sourcing table exists (may not be in initial migration)
        table_exists = await conn.fetchval("""
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'oem_sourcing'
        """)
        if not table_exists:
            if APPLY:
                print("  Creating oem_sourcing table...")
                await conn.execute("""
                    CREATE TABLE oem_sourcing (
                        id              SERIAL PRIMARY KEY,
                        oem_name        VARCHAR(100) NOT NULL,
                        tech_code       VARCHAR(100) NOT NULL,
                        segment         VARCHAR(20) NOT NULL,
                        supplier_codes  TEXT,
                        notes           TEXT,
                        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        UNIQUE (oem_name, tech_code, segment)
                    )
                """)
            else:
                print("  [PLAN] oem_sourcing table would be created")

        # Get all active technologies
        techs = await conn.fetch(
            "SELECT id, code, name, pillar FROM technologies WHERE is_active = TRUE"
        )
        print(f"  Found {len(techs)} active technologies")

        updated = 0
        skipped = 0
        for tech in techs:
            patterns = PILLAR_PATTERNS.get(tech["pillar"])
            if not patterns:
                skipped += 1
                continue

            segs_for_pillar = PILLAR_SEGS.get(tech["pillar"], ALL_SEGS)

            for seg in segs_for_pillar:
                for oem_name, supplier_codes, notes in patterns:
                    if not APPLY:
                        print(f"  [PLAN] {tech['code']:<35s} {seg:<8s} {oem_name}")
                        continue
                    await conn.execute("""
                        INSERT INTO oem_sourcing
                            (oem_name, tech_code, segment, supplier_codes, notes)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (oem_name, tech_code, segment)
                        DO UPDATE SET supplier_codes = EXCLUDED.supplier_codes,
                                      notes = EXCLUDED.notes
                    """, oem_name, tech["code"], seg, supplier_codes,
                        notes or "AI Estimate: pillar-level OEM sourcing pattern (FY25)")
                    updated += 1

        if APPLY:
            print(f"\n  ✅ Inserted/updated {updated} OEM sourcing rows, skipped {skipped} techs (no pillar pattern).")
        else:
            total = sum(
                len(PILLAR_SEGS.get(t["pillar"], ALL_SEGS)) * len(PILLAR_PATTERNS[t["pillar"]])
                for t in techs if t["pillar"] in PILLAR_PATTERNS
            )
            print(f"\n  Would insert ~{total} OEM sourcing rows.")
            print("  Run with --apply to commit.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
