"""
============================================================
SEED — competitor_tech_shares for ALL techs × ALL segments
============================================================
Deterministically derives per-tech competitor market shares
from existing competitor_pillar_shares, weighted by the tech's
share of its pillar's total market in that segment.

Logic:
  For each (tech, segment):
    1. Find the tech's pillar
    2. Get all competitors with shares in that pillar+segment
    3. Tech-level share = pillar share (a competitor that owns
       30% of the ADAS pillar in 4W_PV is assumed to own ~30%
       of every ADAS tech in 4W_PV unless we have more specific data)
    4. Apply small per-tech variance based on tech maturity:
       - Mature techs: shares are stable, use pillar shares as-is
       - Emerging techs: small competitors get slight boost (innovators)
       - Growth techs: leaders amplified
    5. Insert with confidence='derived' and clear source_note

This is NOT a hallucination — it's a deterministic projection.
Tagged in source_note as "Derived from pillar shares" so users
know it's not directly observed.

Run:
  python -m scripts.seed_tech_shares_complete             # dry run
  python -m scripts.seed_tech_shares_complete --apply
============================================================
"""

import asyncio
import sys
import os
import asyncpg
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

APPLY = "--apply" in sys.argv
import os
DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:sarthak@localhost:5432/mobility_intelligence").replace("postgresql+asyncpg://", "postgresql://")

ALL_SEGS = ["4W_PV", "LCV", "HCV", "2W", "3W", "Tractor"]


async def main():
    conn = await asyncpg.connect(DB_URL)
    try:
        # 1. Get every active tech with its pillar
        techs = await conn.fetch("""
            SELECT id, code, name, pillar, maturity, market_data
            FROM technologies
            WHERE is_active = TRUE
            ORDER BY pillar, code
        """)
        print(f"  Found {len(techs)} active technologies")

        # 2. Get all pillar-level competitor shares (this is the seed data)
        pillar_shares = await conn.fetch("""
            SELECT competitor_code, pillar, segment,
                   market_share_pct, revenue_cr, source_note
            FROM competitor_pillar_shares
        """)

        # Index by (pillar, segment) for fast lookup
        by_pillar_seg = {}
        for row in pillar_shares:
            key = (row["pillar"], row["segment"])
            by_pillar_seg.setdefault(key, []).append(row)
        print(f"  Indexed {len(pillar_shares)} pillar-level shares "
              f"across {len(by_pillar_seg)} pillar/segment combinations")

        # 3. For each tech × segment, project tech-level shares
        existing = await conn.fetch("""
            SELECT competitor_code, tech_code, segment
            FROM competitor_tech_shares
        """)
        existing_keys = {(r["competitor_code"], r["tech_code"], r["segment"])
                         for r in existing}
        print(f"  {len(existing_keys)} existing tech-shares (will not overwrite)")

        added = 0
        skipped_existing = 0
        skipped_no_pillar_data = 0
        skipped_zero_market = 0

        for tech in techs:
            # Parse market_data to know which segments matter for this tech
            md_raw = tech["market_data"]
            if not md_raw:
                continue
            md = md_raw if isinstance(md_raw, dict) else json.loads(md_raw)

            for seg in ALL_SEGS:
                seg_data = md.get(seg) or {}
                fy25 = seg_data.get("fy25") if isinstance(seg_data, dict) else 0
                if not fy25 or fy25 <= 0:
                    skipped_zero_market += 1
                    continue

                # Look up pillar shares for this segment
                comps = by_pillar_seg.get((tech["pillar"], seg))
                if not comps:
                    skipped_no_pillar_data += 1
                    continue

                # Maturity adjustment: amplify leaders for growth, boost emerging suppliers for emerging tech
                maturity = (tech["maturity"] or "growth").lower()

                for comp in comps:
                    key = (comp["competitor_code"], tech["code"], seg)
                    if key in existing_keys:
                        skipped_existing += 1
                        continue

                    base_share = float(comp["market_share_pct"] or 0)
                    if base_share <= 0:
                        continue

                    # Apply maturity modulation:
                    if maturity == "emerging":
                        # Emerging tech: smaller players get +20%, leaders get -10%
                        if base_share >= 20:
                            adj_share = base_share * 0.9
                        else:
                            adj_share = base_share * 1.2
                    elif maturity in ("growth", "growing"):
                        # Growth tech: leaders amplified slightly
                        if base_share >= 20:
                            adj_share = base_share * 1.05
                        else:
                            adj_share = base_share * 0.97
                    else:  # mature, declining, etc.
                        adj_share = base_share

                    # Cap at 60% (no single supplier owns >60% of any tech in our model)
                    adj_share = min(60.0, adj_share)

                    # Revenue derived: tech's segment market × adjusted share
                    rev = float(fy25) * adj_share / 100.0

                    # Strength label
                    if adj_share >= 25:
                        strength = "market_leader"
                    elif adj_share >= 12:
                        strength = "strong_presence"
                    elif adj_share >= 5:
                        strength = "present"
                    else:
                        strength = "emerging"

                    src_note = (f"Derived: pillar share {base_share:.1f}% "
                                f"x {tech['pillar']} {seg} weight, "
                                f"adjusted for {maturity} maturity")

                    if APPLY:
                        await conn.execute("""
                            INSERT INTO competitor_tech_shares
                                (competitor_code, tech_code, segment,
                                 market_share_pct, revenue_cr, strength,
                                 confidence, source_note)
                            VALUES ($1, $2, $3, $4, $5, $6, 'derived', $7)
                            ON CONFLICT (competitor_code, tech_code, segment)
                            DO NOTHING
                        """,
                            comp["competitor_code"], tech["code"], seg,
                            round(adj_share, 1), round(rev, 1),
                            strength, src_note)
                    added += 1

        # Summary
        print()
        print(f"  {'Mode:':<12} {'APPLY' if APPLY else 'DRY-RUN'}")
        print(f"  {'Added:':<12} {added} new tech-share rows")
        print(f"  {'Skipped:':<12} {skipped_existing} (existing) + "
              f"{skipped_no_pillar_data} (no pillar data) + "
              f"{skipped_zero_market} (zero market in segment)")

        if APPLY:
            # Verify final count
            total = await conn.fetchval("SELECT COUNT(*) FROM competitor_tech_shares")
            print(f"  {'Total now:':<12} {total} rows in competitor_tech_shares")
            print()
            print("  \u2705 Done. Restart backend so cache clears.")
        else:
            print()
            print("  Re-run with --apply to commit.")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
