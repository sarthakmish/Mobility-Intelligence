"""
============================================================
SEED — Solutions Business + missing Bosch-stack technologies
============================================================
Idempotent: uses ON CONFLICT DO NOTHING. Safe to re-run.

Adds 16 technologies across 6 pillars to make the Bosch
Mobility stack feature-complete in View 2 / View 3 / View 4.

Run:
  cd backend
  python -m scripts.seed_solutions_techs             # dry-run
  python -m scripts.seed_solutions_techs --apply     # commit
============================================================
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg

import os
DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:sarthak@localhost:5432/mobility_intelligence").replace("postgresql+asyncpg://", "postgresql://")
APPLY = "--apply" in sys.argv


def md(seg_data):
    """Build market_data dict: {seg: {fy25, fy30, cagr}} — skips zero-market segments."""
    out = {}
    for seg, (fy25, cagr) in seg_data.items():
        if fy25 == 0:
            continue
        fy30 = round(fy25 * (1 + cagr / 100) ** 5)
        out[seg] = {"fy25": fy25, "fy30": fy30, "cagr": cagr}
    return out


TECHS = [
    # ── SOLUTIONS (4 techs) ────────────────────────────────────────────────────
    {
        "code": "ridecare_fleet_health",
        "name": "RideCare / Fleet Health Platform",
        "pillar": "Solutions",
        "maturity": "Emerging",
        "cagr_top": 25.0,
        "confidence": "low",
        "source_note": "AI Estimate: Bosch Connected, Microsoft Azure, AWS Connected Mobility (FY25 baseline) | LLM extrapolation",
        "includes": "Vibration analytics, predictive maintenance, OBD diagnostics, fleet uptime dashboards",
        "market": md({
            "4W_PV": (400, 25), "LCV": (200, 26), "HCV": (350, 28),
            "2W": (50, 22), "3W": (30, 20),
        }),
    },
    {
        "code": "charging_emobility_service",
        "name": "Charging Service (eMobility)",
        "pillar": "Solutions",
        "maturity": "Emerging",
        "cagr_top": 40.0,
        "confidence": "medium",
        "source_note": "Derived: 29K+ stations Aug 2025 + Vahan EV penetration data (FY25 baseline) | Aggregated published figures",
        "includes": "AC/DC chargers, charge management software, payment integration, load balancing",
        "market": md({
            "4W_PV": (600, 40), "LCV": (50, 35), "HCV": (100, 38),
            "2W": (300, 42), "3W": (100, 36),
        }),
    },
    {
        "code": "state_of_health_report",
        "name": "State of Health Report (Battery)",
        "pillar": "Solutions",
        "maturity": "Emerging",
        "cagr_top": 35.0,
        "confidence": "low",
        "source_note": "AI Estimate: Bosch Battery in Cloud + IBEF EV market (FY25 baseline) | LLM extrapolation",
        "includes": "SOH prediction, residual value analytics, warranty risk scoring, second-life routing",
        "market": md({
            "4W_PV": (180, 35), "LCV": (25, 30), "HCV": (40, 32),
            "2W": (100, 38), "3W": (50, 30),
        }),
    },
    {
        "code": "logistics_fleet_os",
        "name": "Logistics Fleet OS",
        "pillar": "Solutions",
        "maturity": "Emerging",
        "cagr_top": 22.0,
        "confidence": "low",
        "source_note": "Derived: AIS-140 mandate + BlackBuck/Rivigo public data (FY25 baseline) | Industry estimate",
        "includes": "Route optimization, fuel monitoring, driver scoring, AIS-140 compliance",
        "market": md({
            "4W_PV": (200, 18), "LCV": (300, 22), "HCV": (500, 24), "3W": (150, 20),
        }),
    },

    # ── SERVICES (3 techs) ─────────────────────────────────────────────────────
    {
        "code": "wrong_way_driver_warning",
        "name": "Wrong-Way Driver Warning Service",
        "pillar": "Services",
        "maturity": "Emerging",
        "cagr_top": 28.0,
        "confidence": "low",
        "source_note": "AI Estimate: Bosch service portfolio + V2X market data (FY25 baseline) | LLM extrapolation",
        "includes": "Cloud-based wrong-way detection, driver alert via head unit, V2X broadcast",
        "market": md({
            "4W_PV": (50, 28), "LCV": (10, 24), "HCV": (30, 26),
        }),
    },
    {
        "code": "connected_map_services",
        "name": "Connected Map Services",
        "pillar": "Services",
        "maturity": "Growth",
        "cagr_top": 18.0,
        "confidence": "medium",
        "source_note": "Derived: MapmyIndia + HERE India + TomTom share of automotive maps (FY25 baseline) | Aggregated estimates",
        "includes": "HD maps, real-time traffic, EV range maps, POI data, lane-level routing",
        "market": md({
            "4W_PV": (600, 18), "LCV": (100, 16), "HCV": (200, 20), "2W": (150, 22),
        }),
    },
    {
        "code": "battery_in_the_cloud",
        "name": "Battery in the Cloud",
        "pillar": "Services",
        "maturity": "Emerging",
        "cagr_top": 35.0,
        "confidence": "low",
        "source_note": "AI Estimate: Bosch Battery-in-Cloud product + IBEF EV growth (FY25 baseline) | LLM extrapolation",
        "includes": "BMS analytics, degradation modeling, warranty optimization, cell-level diagnostics",
        "market": md({
            "4W_PV": (200, 35), "LCV": (20, 30), "HCV": (30, 32),
            "2W": (150, 38), "3W": (50, 30),
        }),
    },

    # ── OS / Application Software (3 techs) ───────────────────────────────────
    {
        "code": "driving_functions_l0_l3",
        "name": "Driving Functions L0-L3 Software",
        "pillar": "OS",
        "maturity": "Growth",
        "cagr_top": 22.0,
        "confidence": "medium",
        "source_note": "Derived: Mordor ADAS market + Bosch driving-functions revenue share (FY25 baseline) | Industry mapping",
        "includes": "Path planning, behavior prediction, sensor fusion, driving policy, OEDR",
        "market": md({
            "4W_PV": (1100, 22), "LCV": (90, 18), "HCV": (200, 20),
        }),
    },
    {
        "code": "parking_software",
        "name": "Parking Software (APA / Valet)",
        "pillar": "OS",
        "maturity": "Growth",
        "cagr_top": 18.0,
        "confidence": "low",
        "source_note": "AI Estimate: Mordor parking-assist segment (FY25 baseline) | LLM split from ADAS umbrella",
        "includes": "Automated parking algorithms, valet parking software, parking spot detection",
        "market": md({
            "4W_PV": (350, 18), "LCV": (40, 15), "HCV": (30, 14),
        }),
    },
    {
        "code": "vehicle_motion_management",
        "name": "Vehicle Motion Management (VMM)",
        "pillar": "OS",
        "maturity": "Emerging",
        "cagr_top": 26.0,
        "confidence": "low",
        "source_note": "AI Estimate: Bosch VMM platform launches + steer-by-wire trends (FY25 baseline) | LLM extrapolation",
        "includes": "Coordinated steer-brake-drive control, dynamic torque vectoring, integrated chassis control",
        "market": md({
            "4W_PV": (480, 26), "LCV": (60, 20), "HCV": (110, 22),
        }),
    },

    # ── COMPUTE (2 techs) ─────────────────────────────────────────────────────
    {
        "code": "adas_integration_platform",
        "name": "ADAS Integration Platform",
        "pillar": "Compute",
        "maturity": "Growth",
        "cagr_top": 24.0,
        "confidence": "medium",
        "source_note": "Derived: Mordor ADAS DCU market + Bosch product portfolio (FY25 baseline) | Aggregated industry data",
        "includes": "ADAS domain controller, sensor fusion ECU, NVIDIA DRIVE / Qualcomm Snapdragon Ride / Bosch DASy",
        "market": md({
            "4W_PV": (1400, 24), "LCV": (110, 20), "HCV": (220, 22),
        }),
    },
    {
        "code": "vehicle_integration_platform",
        "name": "Vehicle Integration Platform (VIP)",
        "pillar": "Compute",
        "maturity": "Emerging",
        "cagr_top": 28.0,
        "confidence": "low",
        "source_note": "AI Estimate: SDV transition + zonal architecture industry roadmaps (FY25 baseline) | LLM extrapolation",
        "includes": "Central vehicle computer, zonal compute, cross-domain orchestration, service-oriented arch",
        "market": md({
            "4W_PV": (900, 28), "LCV": (80, 22), "HCV": (140, 24),
        }),
    },

    # ── ECUs (1 tech) ─────────────────────────────────────────────────────────
    {
        "code": "generic_electronic_control_unit",
        "name": "Generic Electronic Control Unit",
        "pillar": "ECUs",
        "maturity": "Mature",
        "cagr_top": 5.0,
        "confidence": "medium",
        "source_note": "Derived: ACMA electronics segment + Bosch global ECU revenue (FY25 baseline) | Industry mapping",
        "includes": "Window lift, mirror, seat, wiper, HVAC control modules, body domain controller",
        "market": md({
            "4W_PV": (5000, 5), "LCV": (400, 6), "HCV": (700, 7),
            "2W": (300, 8), "3W": (80, 6), "Tractor": (150, 5),
        }),
    },

    # ── SEMICONDUCTORS (1 tech) ───────────────────────────────────────────────
    {
        "code": "automotive_asic",
        "name": "Automotive ASIC",
        "pillar": "Semiconductors",
        "maturity": "Growth",
        "cagr_top": 16.0,
        "confidence": "low",
        "source_note": "AI Estimate: IndexBox auto-IC + custom-chip programs at Tata Electronics (FY25 baseline) | LLM extrapolation",
        "includes": "Custom ICs for radar, camera serializers, ADAS-specific accelerators, BMS ICs",
        "market": md({
            "4W_PV": (700, 16), "LCV": (60, 12), "HCV": (100, 14),
            "2W": (100, 14), "3W": (25, 10), "Tractor": (20, 10),
        }),
    },

    # ── ACTUATORS (1 tech) ────────────────────────────────────────────────────
    {
        "code": "comfort_actuators",
        "name": "Comfort Actuators",
        "pillar": "Actuators",
        "maturity": "Mature",
        "cagr_top": 7.5,
        "confidence": "medium",
        "source_note": "Derived: ACMA body & comfort + Bosch comfort-systems portfolio (FY25 baseline) | Industry mapping",
        "includes": "Power window motors, seat motors, sunroof actuators, mirror motors, HVAC blower",
        "market": md({
            "4W_PV": (1800, 7.5), "LCV": (200, 6), "HCV": (350, 7),
            "2W": (60, 5), "3W": (15, 4), "Tractor": (40, 4),
        }),
    },
]


async def main():
    conn = await asyncpg.connect(DB_URL)
    try:
        added = 0
        skipped = 0
        for tech in TECHS:
            existing = await conn.fetchval(
                "SELECT id FROM technologies WHERE code = $1 OR name = $2 LIMIT 1",
                tech["code"], tech["name"]
            )
            if existing:
                skipped += 1
                if not APPLY:
                    print(f"  [SKIP] {tech['code']:<40s} — already exists")
                continue

            total_fy25 = sum(s["fy25"] for s in tech["market"].values())
            total_fy30 = sum(s["fy30"] for s in tech["market"].values())

            if APPLY:
                await conn.execute("""
                    INSERT INTO technologies
                        (code, name, pillar, maturity, cagr,
                         confidence, source_note, includes,
                         market_data, total_market_fy25_cr, total_market_fy30_cr,
                         is_active)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,$11,TRUE)
                    ON CONFLICT (code) DO NOTHING
                """,
                    tech["code"], tech["name"], tech["pillar"], tech["maturity"],
                    tech["cagr_top"], tech["confidence"], tech["source_note"],
                    tech["includes"], json.dumps(tech["market"]),
                    float(total_fy25), float(total_fy30),
                )
                added += 1
                print(f"  [ADD ] {tech['code']:<40s} {tech['pillar']:<15s} ₹{total_fy25:,} Cr")
            else:
                print(f"  [PLAN] {tech['code']:<40s} {tech['pillar']:<15s} ₹{total_fy25:,} Cr")

        if APPLY:
            print(f"\n  ✅ Added {added} technologies, skipped {skipped} existing.")
        else:
            would_add = sum(1 for t in TECHS)
            print(f"\n  Dry run: would add {would_add - skipped} technologies ({skipped} already present).")
            print(f"  Run with --apply to commit.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
