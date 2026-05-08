"""
============================================================
SEED — Competitor shares for Semiconductors / Actuators /
       ECUs / Body & Comfort  (remaining V4 gap pillars)
============================================================
Idempotent. ON CONFLICT DO UPDATE so re-runs are safe.

Run:
  cd backend
  python -m scripts.seed_competitors_remaining             # dry run
  python -m scripts.seed_competitors_remaining --apply     # commit
============================================================
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncpg

import os
DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:sarthak@localhost:5432/mobility_intelligence").replace("postgresql+asyncpg://", "postgresql://")
APPLY = "--apply" in sys.argv

# ── New competitors that may not exist yet ──
# (code, name, short_name, hq, tier, color, india_presence)
NEW_COMPETITORS = [
    ("infineon",        "Infineon Technologies",    "Infineon",     "Germany",      "Tech",    "#f59e0b", "AURIX MCU, SiC, radar ICs"),
    ("nxp",             "NXP Semiconductors",       "NXP",          "Netherlands",  "Tech",    "#3b82f6", "S32 automotive MCU, radar RF"),
    ("st_micro",        "STMicroelectronics",       "ST Micro",     "Switzerland",  "Tech",    "#22c55e", "SiC MOSFETs, power ICs"),
    ("renesas",         "Renesas Electronics",      "Renesas",      "Japan",        "Tech",    "#ef4444", "RH850 MCU, R-Car SoC"),
    ("ti",              "Texas Instruments",        "TI",           "USA",          "Tech",    "#f97316", "TDA4 SoC, LiDAR/radar AFE"),
    ("rir_power",       "RIR Power Electronics",    "RIR Power",    "India",        "Tier-2",  "#8b5cf6", "India SiC power modules"),
    ("tata_electronics","Tata Electronics",         "Tata Elec",    "India",        "Tier-1",  "#D85A30", "India semiconductor fab"),
    ("on_semi",         "onsemi",                   "onsemi",       "USA",          "Tech",    "#06b6d4", "SiC, IGBT, image sensors"),
    ("microchip",       "Microchip Technology",     "Microchip",    "USA",          "Tech",    "#64748b", "PIC MCU, CAN/LIN transceiver"),
    ("zf",              "ZF Friedrichshafen",       "ZF",           "Germany",      "Tier-1",  "#0ea5e9", "Brakes, steering, driveline"),
    ("denso",           "Denso Corporation",        "Denso",        "Japan",        "Tier-1",  "#10b981", "ECU, HVAC, actuators"),
    ("mando",           "HL Mando",                 "Mando",        "Korea",        "Tier-1",  "#f59e0b", "EPS, brakes, shock absorbers"),
    ("brembo",          "Brembo S.p.A.",            "Brembo",       "Italy",        "Tier-1",  "#ef4444", "Performance brakes"),
    ("sona_blw",        "Sona Comstar / BLW",       "Sona BLW",     "India",        "Tier-1",  "#185FA5", "India EV drivetrain, gears"),
    ("nhk",             "NHK Spring",               "NHK",          "Japan",        "Tier-1",  "#64748b", "Suspension springs"),
    ("autoliv",         "Autoliv",                  "Autoliv",      "Sweden",       "Tier-1",  "#22c55e", "Airbags, seatbelts"),
    ("rane",            "Rane Group",               "Rane",         "India",        "Tier-1",  "#dc2626", "India steering, brakes, joints"),
    ("endurance",       "Endurance Technologies",   "Endurance",    "India",        "Tier-1",  "#7c3aed", "India 2W/3W castings, brakes"),
    ("ucal",            "UCAL Fuel Systems",        "UCAL",         "India",        "Tier-2",  "#94a3b8", "India carburetor, throttle body"),
    ("escorts",         "Escorts Kubota",           "Escorts",      "India",        "Tier-1",  "#f59e0b", "India tractor + 3W components"),
    ("hella",           "HELLA GmbH",               "HELLA",        "Germany",      "Tier-1",  "#0ea5e9", "Lighting, sensors, electronics"),
    ("hitachi_astemo",  "Hitachi Astemo",           "H-Astemo",     "Japan",        "Tier-1",  "#ef4444", "Chassis, powertrain, ADAS ECU"),
    ("minda",           "Uno Minda",                "UnoMinda",     "India",        "Tier-1",  "#f97316", "India switches, horns, ECU"),
    ("uno_minda",       "Uno Minda Group",          "Uno Minda",    "India",        "Tier-1",  "#f97316", "India body electronics"),
    ("keihin",          "Keihin (Hitachi Astemo)",  "Keihin",       "Japan",        "Tier-1",  "#64748b", "Fuel injection, ECU"),
    ("motherson",       "Samvardhana Motherson",    "Motherson",    "India",        "Tier-1",  "#22c55e", "India wiring, mirrors, bumpers"),
    ("samvardhana",     "Samvardhana Group",        "Samvardhana",  "India",        "Tier-1",  "#16a34a", "India body modules"),
    ("valeo",           "Valeo S.A.",               "Valeo",        "France",       "Tier-1",  "#3b82f6", "HVAC, lighting, wipers"),
    ("magna",           "Magna International",      "Magna",        "Canada",       "Tier-1",  "#8b5cf6", "Body, seating, exteriors"),
    ("brose",           "Brose Fahrzeugteile",      "Brose",        "Germany",      "Tier-1",  "#f59e0b", "Window regulators, seat motors"),
    ("subros",          "Subros Limited",           "Subros",       "India",        "Tier-1",  "#0ea5e9", "India HVAC AC compressors"),
    ("lumax",           "Lumax Industries",         "Lumax",        "India",        "Tier-1",  "#fbbf24", "India automotive lighting"),
    ("jbm_auto",        "JBM Auto",                 "JBM Auto",     "India",        "Tier-1",  "#64748b", "India body-in-white, bus"),
    ("aptiv",           "Aptiv PLC",                "Aptiv",        "Ireland",      "Tier-1",  "#185FA5", "Wiring, connectors, ADAS ECU"),
    ("continental",     "Continental AG",           "Continental",  "Germany",      "Tier-1",  "#6366f1", "Tires, ADAS, brakes, ECU"),
    ("bosch",           "Robert Bosch GmbH",        "Bosch",        "Germany",      "Tier-1",  "#ef4444", "Full-stack auto supplier"),
    ("mobileye",        "Mobileye",                 "Mobileye",     "Israel",       "Tech",    "#3b82f6", "EyeQ SoC, SuperVision"),
    ("qualcomm",        "Qualcomm",                 "Qualcomm",     "USA",          "Tech",    "#22c55e", "Snapdragon Ride, telematics"),
]

# ── Pillar shares ──
# Format: pillar → segment → [(competitor_code, share_pct, source_note)]
SHARES = {
    "Semiconductors": {
        "4W_PV": [
            ("infineon",        22, "Infineon AURIX + SiC market leader"),
            ("nxp",             18, "NXP S32 MCU dominant in ADAS/body"),
            ("st_micro",        14, "STMicro SiC MOSFET + power ICs"),
            ("renesas",         12, "Renesas RH850/R-Car platform"),
            ("ti",               8, "TI TDA4 SoC + sensing ICs"),
            ("bosch",            8, "Bosch MEMS sensors (IMU, pressure)"),
            ("rir_power",        6, "RIR Power — India SiC fab"),
            ("tata_electronics", 5, "Tata Electronics — India fab push"),
            ("on_semi",          4, "onsemi SiC + IGBT"),
            ("microchip",        3, "Microchip PIC MCU + CAN transceivers"),
        ],
        "LCV": [
            ("infineon",  24, "Infineon AURIX LCV dominant"),
            ("nxp",       18, "NXP S32 LCV"),
            ("st_micro",  14, "STMicro LCV power"),
            ("renesas",   12, "Renesas LCV MCU"),
            ("ti",        10, "TI LCV sensing"),
            ("bosch",     10, "Bosch MEMS LCV"),
            ("on_semi",    6, "onsemi LCV power"),
            ("microchip",  6, "Microchip LCV CAN/LIN"),
        ],
        "HCV": [
            ("infineon",  22, "Infineon AURIX HCV dominant"),
            ("nxp",       18, "NXP HCV S32"),
            ("st_micro",  14, "STMicro HCV"),
            ("renesas",   12, "Renesas HCV"),
            ("ti",        10, "TI HCV"),
            ("bosch",     12, "Bosch MEMS HCV + radar"),
            ("on_semi",    6, "onsemi HCV"),
            ("microchip",  6, "Microchip HCV"),
        ],
        "2W": [
            ("infineon",  18, "Infineon 2W power semis"),
            ("nxp",       14, "NXP 2W telematics chip"),
            ("st_micro",  12, "STMicro 2W SiC"),
            ("renesas",   10, "Renesas 2W MCU"),
            ("ti",        10, "TI 2W BMS + sensing"),
            ("bosch",     14, "Bosch MEMS 2W (ABS, IMU)"),
            ("rir_power",  8, "RIR Power India SiC 2W EV"),
            ("microchip",  8, "Microchip 2W CAN/LIN"),
            ("on_semi",    6, "onsemi 2W IGBT"),
        ],
        "3W": [
            ("infineon",  16, "Infineon 3W power"),
            ("nxp",       14, "NXP 3W"),
            ("st_micro",  12, "STMicro 3W"),
            ("renesas",   10, "Renesas 3W MCU"),
            ("ti",        12, "TI 3W BMS"),
            ("bosch",     14, "Bosch MEMS 3W"),
            ("rir_power",  8, "RIR Power India 3W EV SiC"),
            ("microchip",  8, "Microchip 3W"),
            ("on_semi",    6, "onsemi 3W"),
        ],
        "Tractor": [
            ("infineon",  14, "Infineon Tractor MCU"),
            ("nxp",       12, "NXP Tractor"),
            ("st_micro",  10, "STMicro Tractor"),
            ("renesas",   10, "Renesas Tractor MCU"),
            ("ti",        14, "TI Tractor sensing"),
            ("bosch",     16, "Bosch Tractor MEMS + fuel"),
            ("microchip", 12, "Microchip Tractor CAN/LIN"),
            ("on_semi",    6, "onsemi Tractor power"),
            ("rir_power",  6, "RIR Power India Tractor EV"),
        ],
    },

    "Actuators": {
        "4W_PV": [
            ("bosch",      24, "Bosch DPB, EPS, e-motor leader"),
            ("continental",18, "Continental brakes + EPS India"),
            ("zf",         12, "ZF Active Kinematics + brakes"),
            ("denso",      10, "Denso window motors, HVAC blower"),
            ("mando",       8, "HL Mando EPS, brakes"),
            ("brembo",      6, "Brembo performance brakes India"),
            ("sona_blw",    8, "Sona BLW e-motor + differential"),
            ("rane",        5, "Rane India EPS + steering"),
            ("nhk",         5, "NHK suspension springs"),
            ("autoliv",     4, "Autoliv airbag + pretensioner"),
        ],
        "LCV": [
            ("bosch",      26, "Bosch LCV brakes + EPS"),
            ("continental",16, "Continental LCV actuators"),
            ("zf",         12, "ZF LCV driveline"),
            ("denso",      10, "Denso LCV motors"),
            ("mando",       8, "Mando LCV brakes"),
            ("rane",       12, "Rane India LCV steering"),
            ("endurance",   8, "Endurance India LCV brakes"),
            ("autoliv",     8, "Autoliv LCV safety"),
        ],
        "HCV": [
            ("bosch",      28, "Bosch HCV brakes + EBS + ABS"),
            ("zf",         16, "ZF HCV driveline + retarder"),
            ("continental",14, "Continental HCV brakes + EPS"),
            ("denso",      10, "Denso HCV actuators"),
            ("rane",       14, "Rane India HCV steering"),
            ("mando",       8, "Mando HCV brakes"),
            ("endurance",  10, "Endurance India HCV"),
        ],
        "2W": [
            ("bosch",      22, "Bosch 2W ABS + IMU + e-motor"),
            ("continental",14, "Continental 2W ABS + EMS"),
            ("rane",       16, "Rane India 2W steering/suspension"),
            ("endurance",  14, "Endurance India 2W brakes + forks"),
            ("ucal",       12, "UCAL India 2W throttle body"),
            ("denso",       8, "Denso 2W FI system"),
            ("sona_blw",    8, "Sona BLW 2W EV e-motor"),
            ("autoliv",     6, "Autoliv 2W safety"),
        ],
        "3W": [
            ("bosch",      20, "Bosch 3W ABS + brakes"),
            ("rane",       18, "Rane India 3W steering"),
            ("endurance",  16, "Endurance India 3W"),
            ("ucal",       14, "UCAL India 3W throttle"),
            ("continental",10, "Continental 3W ABS"),
            ("denso",       8, "Denso 3W FI"),
            ("sona_blw",    8, "Sona BLW 3W EV motor"),
            ("autoliv",     6, "Autoliv 3W"),
        ],
        "Tractor": [
            ("bosch",      22, "Bosch Tractor brakes + fuel"),
            ("zf",         18, "ZF Tractor driveline + PTO"),
            ("rane",       16, "Rane India Tractor steering"),
            ("escorts",    14, "Escorts Kubota Tractor OEM"),
            ("denso",      10, "Denso Tractor"),
            ("endurance",   8, "Endurance India Tractor"),
            ("sona_blw",    6, "Sona BLW Tractor"),
            ("autoliv",     6, "Autoliv Tractor"),
        ],
    },

    "ECUs": {
        "4W_PV": [
            ("bosch",      28, "Bosch ECU/DCU — largest auto ECU supplier"),
            ("continental",16, "Continental powertrain + body ECU"),
            ("denso",      14, "Denso engine/body ECU"),
            ("aptiv",      10, "Aptiv central architecture ECU"),
            ("hella",       8, "HELLA body ECU, BCM, junction box"),
            ("kpit",        7, "KPIT ECU software + integration India"),
            ("tata_elxsi",  6, "Tata Elxsi ECU software services India"),
            ("hitachi_astemo", 5, "Hitachi Astemo ECU Japan"),
            ("minda",       6, "Uno Minda India BCM + body ECU"),
        ],
        "LCV": [
            ("bosch",      30, "Bosch LCV ECU"),
            ("continental",16, "Continental LCV ECU"),
            ("denso",      14, "Denso LCV ECU"),
            ("minda",      12, "Uno Minda India LCV BCM"),
            ("aptiv",      10, "Aptiv LCV"),
            ("hella",       8, "HELLA LCV BCM"),
            ("kpit",        6, "KPIT LCV integration"),
            ("tata_elxsi",  4, "Tata Elxsi LCV"),
        ],
        "HCV": [
            ("bosch",      32, "Bosch HCV ECU, AEBS, telematics ECU"),
            ("continental",16, "Continental HCV"),
            ("denso",      12, "Denso HCV ECU"),
            ("minda",      12, "Uno Minda India HCV body"),
            ("hitachi_astemo", 10, "Hitachi Astemo HCV"),
            ("aptiv",       8, "Aptiv HCV"),
            ("kpit",        5, "KPIT HCV integration"),
            ("tata_elxsi",  5, "Tata Elxsi HCV"),
        ],
        "2W": [
            ("bosch",      24, "Bosch 2W ABS + FI ECU"),
            ("denso",      14, "Denso 2W FI ECU"),
            ("minda",      22, "Uno Minda India 2W ECU dominant"),
            ("keihin",     12, "Keihin 2W FI ECU (via H-Astemo)"),
            ("ucal",       10, "UCAL India 2W throttle ECU"),
            ("continental", 8, "Continental 2W EMS"),
            ("hitachi_astemo", 6, "Hitachi Astemo 2W"),
            ("bosch",       4, "Bosch 2W additional"),
        ],
        "3W": [
            ("bosch",      22, "Bosch 3W ECU + FI"),
            ("denso",      12, "Denso 3W ECU"),
            ("minda",      24, "Uno Minda India 3W ECU"),
            ("keihin",     14, "Keihin 3W FI"),
            ("ucal",       10, "UCAL 3W throttle"),
            ("continental", 8, "Continental 3W"),
            ("hitachi_astemo", 6, "H-Astemo 3W"),
            ("kpit",        4, "KPIT 3W integration"),
        ],
        "Tractor": [
            ("bosch",      24, "Bosch Tractor ECU + fuel pump"),
            ("denso",      14, "Denso Tractor ECU"),
            ("minda",      18, "Uno Minda India Tractor body ECU"),
            ("escorts",    14, "Escorts Kubota OEM Tractor ECU"),
            ("continental",10, "Continental Tractor"),
            ("kpit",        8, "KPIT Tractor integration"),
            ("hitachi_astemo", 6, "H-Astemo Tractor"),
            ("tata_elxsi",  6, "Tata Elxsi Tractor"),
        ],
    },

    "Body & Comfort": {
        "4W_PV": [
            ("motherson",   18, "Samvardhana Motherson — India #1 body supplier"),
            ("samvardhana", 14, "Samvardhana wiring + bumper + mirrors"),
            ("minda",       12, "Uno Minda switches, horns, lighting connectors"),
            ("valeo",       10, "Valeo HVAC, wiper, lighting India"),
            ("magna",        8, "Magna seating, exteriors India"),
            ("brose",        7, "Brose window regulators, seat actuators"),
            ("denso",        6, "Denso HVAC blower India"),
            ("subros",       6, "Subros India AC compressor leader"),
            ("lumax",        5, "Lumax India lighting"),
            ("jbm_auto",     5, "JBM Auto India body panels"),
            ("hella",        9, "HELLA lighting India"),
        ],
        "LCV": [
            ("motherson",   20, "Motherson LCV wiring + body"),
            ("samvardhana", 14, "Samvardhana LCV"),
            ("minda",       14, "Uno Minda LCV switches + BCM"),
            ("valeo",       10, "Valeo LCV HVAC"),
            ("subros",      12, "Subros LCV AC"),
            ("magna",        8, "Magna LCV body"),
            ("lumax",        6, "Lumax LCV lighting"),
            ("jbm_auto",     8, "JBM Auto LCV body"),
            ("hella",        8, "HELLA LCV lighting"),
        ],
        "HCV": [
            ("motherson",   22, "Motherson HCV wiring + cabin"),
            ("samvardhana", 14, "Samvardhana HCV"),
            ("minda",       14, "Uno Minda HCV switches"),
            ("subros",      14, "Subros HCV AC"),
            ("jbm_auto",    10, "JBM Auto HCV body panels"),
            ("valeo",        8, "Valeo HCV HVAC"),
            ("lumax",        6, "Lumax HCV lighting"),
            ("hella",       12, "HELLA HCV lighting"),
        ],
        "2W": [
            ("minda",       22, "Uno Minda 2W switches, horns, lights"),
            ("motherson",   16, "Motherson 2W wiring harness"),
            ("uno_minda",   14, "Uno Minda 2W accessories"),
            ("lumax",       12, "Lumax 2W lighting leader India"),
            ("samvardhana", 10, "Samvardhana 2W"),
            ("endurance",    8, "Endurance 2W body castings"),
            ("hella",        8, "HELLA 2W lighting"),
            ("valeo",        4, "Valeo 2W wipers"),
            ("brose",        6, "Brose 2W mirror actuator"),
        ],
        "3W": [
            ("minda",       24, "Uno Minda 3W switches dominant India"),
            ("motherson",   14, "Motherson 3W wiring"),
            ("uno_minda",   16, "Uno Minda 3W accessories"),
            ("lumax",       12, "Lumax 3W lighting"),
            ("endurance",    8, "Endurance 3W body"),
            ("samvardhana",  8, "Samvardhana 3W"),
            ("hella",       10, "HELLA 3W lighting"),
            ("valeo",        8, "Valeo 3W HVAC/wipers"),
        ],
        "Tractor": [
            ("motherson",   18, "Motherson Tractor wiring + cabin"),
            ("samvardhana", 14, "Samvardhana Tractor"),
            ("minda",       14, "Uno Minda Tractor switches"),
            ("escorts",     12, "Escorts Kubota OEM Tractor body"),
            ("lumax",        8, "Lumax Tractor lighting"),
            ("jbm_auto",     8, "JBM Auto Tractor body"),
            ("hella",       10, "HELLA Tractor lighting"),
            ("valeo",        6, "Valeo Tractor HVAC"),
            ("subros",      10, "Subros Tractor AC"),
        ],
    },
}


async def ensure_competitor(conn, code, name, short_name, hq, tier, color, india_presence):
    existing = await conn.fetchval("SELECT code FROM competitors WHERE code = $1", code)
    if existing:
        return
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
        print("Registering new competitors...")
        for code, name, sn, hq, tier, color, ip in NEW_COMPETITORS:
            await ensure_competitor(conn, code, name, sn, hq, tier, color, ip)

        print("\nSeeding pillar shares...")
        added = 0
        for pillar, by_seg in SHARES.items():
            for seg, players in by_seg.items():
                for code, share_pct, note in players:
                    if not APPLY:
                        print(f"  [PLAN] {pillar:<18s} {seg:<8s} {code:<20s} {share_pct}%")
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
                        float(share_pct * 12),
                        note or f"AI Estimate: {pillar} India players")
                    added += 1

        if APPLY:
            print(f"\n  ✅ Inserted/updated {added} pillar-share rows.")
        else:
            total = sum(len(players) for by_seg in SHARES.values() for players in by_seg.values())
            print(f"\n  Dry run: would insert {total} pillar-share rows.")
            print(f"  Run with --apply to commit.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
