"""
============================================================
AUDIT — Compute pillar segment data (also reusable for ECUs / OS)
============================================================
Why: View 3 / View 2 show empty Compute for some segments (esp. LCV).
This script identifies which Compute technologies have zero or missing
market_data for each segment, and either:
  (a) prints a report (default), or
  (b) auto-fills with proportional sizing if --fix is passed.

Run:
  python backend/scripts/audit_compute_segments.py            # report
  python backend/scripts/audit_compute_segments.py --fix      # apply
  python backend/scripts/audit_compute_segments.py --fix ECUs # other pillars
============================================================
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from sqlalchemy import text
from backend.db.connection import async_session

SEGMENTS = ["4W_PV", "LCV", "HCV", "2W", "3W", "Tractor"]

# Per-pillar reasonable ratios vs 4W_PV. Adjust as you learn real data.
PILLAR_RATIOS = {
    "Compute":    {"4W_PV": 1.00, "LCV": 0.20, "HCV": 0.30, "2W": 0.06, "3W": 0.04, "Tractor": 0.12},
    "ECUs":       {"4W_PV": 1.00, "LCV": 0.25, "HCV": 0.20, "2W": 0.06, "3W": 0.04, "Tractor": 0.10},
    "OS":         {"4W_PV": 1.00, "LCV": 0.15, "HCV": 0.18, "2W": 0.05, "3W": 0.03, "Tractor": 0.04},
}

PILLAR = sys.argv[2] if len(sys.argv) > 2 else "Compute"
APPLY_FIX = "--fix" in sys.argv


async def main():
    if PILLAR not in PILLAR_RATIOS:
        print(f"No ratio table for pillar '{PILLAR}'. Add it to PILLAR_RATIOS.")
        return
    ratios = PILLAR_RATIOS[PILLAR]

    async with async_session() as db:
        rows = await db.execute(text(
            "SELECT code, name, market_data FROM technologies "
            "WHERE pillar = :p AND is_active = TRUE"
        ), {"p": PILLAR})
        techs = rows.fetchall()

        print(f"\n{'='*70}\nAudit: {PILLAR} pillar — {len(techs)} technologies\n{'='*70}\n")

        gaps_found = 0
        fixed = 0
        for tech in techs:
            md = tech.market_data
            if isinstance(md, str):
                md = json.loads(md)
            md = md or {}

            # Find anchor (4W_PV preferred, else largest available)
            anchor_seg = None
            anchor_fy25 = 0
            anchor_cagr = 10.0
            if "4W_PV" in md and isinstance(md["4W_PV"], dict):
                anchor_seg = "4W_PV"
                anchor_fy25 = md["4W_PV"].get("fy25", 0) or 0
                anchor_cagr = md["4W_PV"].get("cagr", 10) or 10
            else:
                for s, val in md.items():
                    if isinstance(val, dict) and (val.get("fy25") or 0) > anchor_fy25:
                        anchor_seg = s
                        anchor_fy25 = val.get("fy25", 0)
                        anchor_cagr = val.get("cagr", 10)

            if not anchor_seg or anchor_fy25 <= 0:
                print(f"  ⚠️  {tech.code}: no usable anchor segment, skipping")
                continue

            anchor_ratio = ratios.get(anchor_seg, 1.0)
            row_gaps = []
            row_updates = dict(md)
            for s in SEGMENTS:
                if s in md and isinstance(md[s], dict) and (md[s].get("fy25", 0) or 0) > 0:
                    continue
                target_ratio = ratios.get(s, 0.10)
                derived_fy25 = max(1, round(anchor_fy25 * (target_ratio / anchor_ratio)))
                derived_cagr = max(1.0, round(anchor_cagr - 2.0, 1))
                derived_fy30 = max(derived_fy25, round(derived_fy25 * (1 + derived_cagr / 100) ** 5))
                row_gaps.append((s, derived_fy25, derived_cagr))
                row_updates[s] = {
                    "fy25": derived_fy25,
                    "fy30": derived_fy30,
                    "cagr": derived_cagr,
                }

            if row_gaps:
                gaps_found += 1
                print(f"  📌 {tech.code} ({tech.name})")
                print(f"     Anchor: {anchor_seg} @ ₹{anchor_fy25} Cr · CAGR {anchor_cagr}%")
                for s, v, c in row_gaps:
                    print(f"      → {s}: derived ₹{v} Cr @ {c}%")
                if APPLY_FIX:
                    await db.execute(
                        text(
                            "UPDATE technologies SET market_data = :md, source_note = "
                            "COALESCE(NULLIF(source_note,''), 'Derived: ratio audit (FY25 baseline) | Proportional sizing') "
                            "WHERE code = :c"
                        ),
                        {"md": json.dumps(row_updates), "c": tech.code},
                    )
                    fixed += 1

        if APPLY_FIX:
            await db.commit()

        print(f"\n{'='*70}")
        print(f"  Technologies with gaps: {gaps_found}")
        if APPLY_FIX:
            print(f"  Fixed: {fixed}")
        else:
            print(f"  Run with --fix to apply.")
        print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
