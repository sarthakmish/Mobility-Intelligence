"""
============================================================
DIAGNOSE — V4 competitor data coverage matrix
============================================================
Prints a 13 × 6 matrix (pillars × segments) showing how many
competitor rows exist for each combination.  A cell with "⚠ 0"
means V4 will show "No competitor data" for that pillar+segment.

Run:
  cd backend
  python -m scripts.diagnose_v4_gaps
============================================================
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncpg

DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/mobility_intelligence").replace("postgresql+asyncpg://", "postgresql://")

PILLARS = [
    "ADAS", "Motion", "Energy", "Body & Comfort", "Infotainment",
    "OS", "Compute", "ECUs", "Semiconductors", "Actuators",
    "Solutions", "Services", "Cloud",
]
SEGS = ["4W_PV", "LCV", "HCV", "2W", "3W", "Tractor"]


async def main():
    conn = await asyncpg.connect(DB_URL)
    try:
        rows = await conn.fetch("""
            SELECT pillar, segment, COUNT(*) AS n
            FROM competitor_pillar_shares
            GROUP BY pillar, segment
        """)
        counts = {(r["pillar"], r["segment"]): r["n"] for r in rows}

        print(f"\n{'='*74}")
        print(f"  V4 COMPETITOR COVERAGE — competitor_pillar_shares")
        print(f"{'='*74}\n")
        hdr = f"  {'Pillar':<20}"
        for s in SEGS:
            hdr += f"{s:>9}"
        print(hdr)
        print(f"  {'-'*20}{'-'*9*len(SEGS)}")

        gaps = 0
        for p in PILLARS:
            row = f"  {p:<20}"
            for s in SEGS:
                n = counts.get((p, s), 0)
                if n == 0:
                    row += f"{'⚠ 0':>9}"
                    gaps += 1
                else:
                    row += f"{n:>9}"
            print(row)

        print(f"\n  Total cells with 0 rows: {gaps} / {len(PILLARS) * len(SEGS)}")

        # Tech-level coverage
        tech_rows = await conn.fetch("""
            SELECT t.pillar, t.code, t.name,
                   (SELECT COUNT(*) FROM competitor_tech_shares cts
                    WHERE cts.tech_code = t.code) AS n_shares
            FROM technologies t
            WHERE t.is_active = TRUE
            ORDER BY t.pillar, t.code
        """)
        tech_gaps = [(r["pillar"], r["code"], r["name"]) for r in tech_rows if r["n_shares"] == 0]

        print(f"\n  Technologies with ZERO tech-level competitor rows: {len(tech_gaps)}")
        for p, c, n in tech_gaps[:20]:
            print(f"    [{p:<16s}] {c:<36s} {n[:40]}")
        if len(tech_gaps) > 20:
            print(f"    ... {len(tech_gaps) - 20} more")
        print()
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
