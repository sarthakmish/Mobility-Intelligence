"""
Fill missing segment keys in technologies.market_data.
Derives missing segments proportionally from existing values using pillar-based ratios.
"""
import psycopg2
import psycopg2.extras
import json
import math

import os as _os, urllib.parse as _up
_db_url = _os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/mobility_intelligence").replace("postgresql+asyncpg://", "postgresql://")
_p = _up.urlparse(_db_url)
DB = dict(host=_p.hostname, port=_p.port or 5432, dbname=_p.path.lstrip("/"),
          user=_p.username, password=_p.password)

SEGMENTS = ["4W_PV", "2W", "3W", "LCV", "HCV", "Tractor"]

# Ratios relative to 4W_PV fy25 value
PILLAR_RATIOS = {
    "ADAS":          {"4W_PV": 1.00, "2W": 0.02, "3W": 0.01, "LCV": 0.12, "HCV": 0.18, "Tractor": 0.005},
    "Motion":        {"4W_PV": 1.00, "2W": 0.15, "3W": 0.08, "LCV": 0.30, "HCV": 0.28, "Tractor": 0.12},
    "Energy":        {"4W_PV": 1.00, "2W": 0.25, "3W": 0.12, "LCV": 0.20, "HCV": 0.15, "Tractor": 0.04},
    "Body & Comfort":{"4W_PV": 1.00, "2W": 0.03, "3W": 0.02, "LCV": 0.15, "HCV": 0.08, "Tractor": 0.01},
    "Infotainment":  {"4W_PV": 1.00, "2W": 0.10, "3W": 0.05, "LCV": 0.08, "HCV": 0.05, "Tractor": 0.01},
    "OS":            {"4W_PV": 1.00, "2W": 0.05, "3W": 0.02, "LCV": 0.10, "HCV": 0.12, "Tractor": 0.02},
    "Compute":       {"4W_PV": 1.00, "2W": 0.05, "3W": 0.03, "LCV": 0.10, "HCV": 0.15, "Tractor": 0.10},
    "ECUs":          {"4W_PV": 1.00, "2W": 0.05, "3W": 0.03, "LCV": 0.20, "HCV": 0.15, "Tractor": 0.08},
    "Semiconductors":{"4W_PV": 1.00, "2W": 0.10, "3W": 0.05, "LCV": 0.15, "HCV": 0.12, "Tractor": 0.05},
    "Actuators":     {"4W_PV": 1.00, "2W": 0.08, "3W": 0.05, "LCV": 0.20, "HCV": 0.25, "Tractor": 0.15},
    "Solutions":     {"4W_PV": 1.00, "2W": 0.05, "3W": 0.08, "LCV": 0.15, "HCV": 0.20, "Tractor": 0.03},
    "Services":      {"4W_PV": 1.00, "2W": 0.05, "3W": 0.08, "LCV": 0.20, "HCV": 0.30, "Tractor": 0.02},
    "Cloud":         {"4W_PV": 1.00, "2W": 0.03, "3W": 0.02, "LCV": 0.10, "HCV": 0.15, "Tractor": 0.02},
}

# CAGR adjustment (percentage points) relative to 4W_PV cagr
CAGR_ADJ = {"4W_PV": 0, "2W": 5, "3W": 8, "LCV": -2, "HCV": -3, "Tractor": -5}


def fill_tech(code: str, pillar: str, market_data: dict) -> dict | None:
    """Return updated market_data with all segments filled, or None if already complete."""
    ratios = PILLAR_RATIOS.get(pillar)
    if not ratios:
        print(f"  WARN: No ratios for pillar '{pillar}' (code={code})")
        return None

    # Find anchor: prefer 4W_PV, else highest fy25 value
    anchor_seg = None
    if "4W_PV" in market_data and isinstance(market_data["4W_PV"], dict):
        anchor_seg = "4W_PV"
    else:
        best_fy25 = 0
        for seg, val in market_data.items():
            if isinstance(val, dict) and val.get("fy25", 0) > best_fy25:
                best_fy25 = val["fy25"]
                anchor_seg = seg
    
    if not anchor_seg:
        print(f"  WARN: No valid anchor for {code}, skipping")
        return None

    anchor = market_data[anchor_seg]
    anchor_fy25 = anchor.get("fy25", 0)
    anchor_cagr = anchor.get("cagr", 10.0)
    anchor_ratio = ratios[anchor_seg]

    if anchor_fy25 == 0:
        return None

    updated = dict(market_data)
    changed = False

    for seg in SEGMENTS:
        if seg in market_data and isinstance(market_data[seg], dict):
            continue  # already has this segment
        
        seg_ratio = ratios[seg]
        # Derive fy25 from anchor, scaled by ratio difference
        raw_fy25 = anchor_fy25 * (seg_ratio / anchor_ratio)
        seg_fy25 = max(1, round(raw_fy25))
        
        seg_cagr = round(anchor_cagr + CAGR_ADJ[seg] - CAGR_ADJ[anchor_seg], 1)
        seg_cagr = max(1.0, seg_cagr)  # floor at 1%
        
        seg_fy30 = max(seg_fy25, round(seg_fy25 * ((1 + seg_cagr / 100) ** 5)))

        updated[seg] = {"cagr": seg_cagr, "fy25": seg_fy25, "fy30": seg_fy30}
        changed = True
        print(f"    + {seg}: fy25={seg_fy25}, cagr={seg_cagr}%, fy30={seg_fy30}")

    return updated if changed else None


def main():
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT code, pillar, market_data FROM technologies ORDER BY pillar, code")
    rows = cur.fetchall()

    update_cur = conn.cursor()
    updates = 0

    for row in rows:
        code = row["code"]
        pillar = row["pillar"]
        market_data = row["market_data"] or {}

        missing = [s for s in SEGMENTS if s not in market_data or not isinstance(market_data.get(s), dict)]
        if not missing:
            continue

        print(f"\n[{pillar}] {code} — missing: {missing}")
        updated = fill_tech(code, pillar, market_data)
        if updated:
            update_cur.execute(
                "UPDATE technologies SET market_data = %s WHERE code = %s",
                (json.dumps(updated), code)
            )
            updates += 1

    conn.commit()
    cur.close()
    update_cur.close()
    conn.close()
    print(f"\nDone. Updated {updates} technologies.")


if __name__ == "__main__":
    main()
