"""
============================================================
BACKFILL — pestel_score_history with synthesized trajectories
============================================================
For every active factor that has fewer than 3 history points,
synthesize anchor points so right-click compare in View 1 shows
a real trajectory instead of a single dot.

Synthesis rules (deterministic, NOT random):
- We never invent scores. We extrapolate BACKWARDS from current scores
  using the factor's recorded `trend` direction, with bounded deltas.

For trend = "escalating":
  Origin point:     L = max(1, current_L - 2),  I = max(1, current_I - 1)
  Midpoint:         L = max(1, current_L - 1),  I = current_I

For trend = "de-escalating":
  Origin point:     L = min(10, current_L + 2), I = min(10, current_I + 1)
  Midpoint:         L = min(10, current_L + 1), I = current_I

For trend = "stable":
  Origin point:     L = current_L,              I = current_I
  Midpoint:         L = current_L,              I = current_I

For trend = "new" (factor emerged < 90 days ago):
  Skip backfill — only the current snapshot is meaningful.

Anchor dates by origin age:
- origin >= 18 months ago → Origin + Jan 2025 + Jan 2026 + Now (4 points)
- origin >= 12 months ago → Origin + Jan 2026 + Now (3 points)
- origin >= 6 months ago  → Origin + Midpoint + Now (3 points)
- origin <  6 months ago  → Origin + Now (2 points)

Run:
    cd <project-root>
    $env:PYTHONPATH="backend"
    conda run -n intel python backend/scripts/backfill_score_history.py
============================================================
"""

import asyncio
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from sqlalchemy import text
from db.connection import async_session


JAN_2025 = datetime(2025, 1, 15, tzinfo=timezone.utc)
JAN_2026 = datetime(2026, 1, 15, tzinfo=timezone.utc)
NOW = datetime.now(timezone.utc)


def synth_origin(current_l: float, current_i: float, trend: str) -> tuple:
    if trend == "escalating":
        return (max(1.0, current_l - 2.0), max(1.0, current_i - 1.0))
    if trend == "de-escalating":
        return (min(10.0, current_l + 2.0), min(10.0, current_i + 1.0))
    return (current_l, current_i)


def synth_midpoint(current_l: float, current_i: float, trend: str) -> tuple:
    if trend == "escalating":
        return (max(1.0, current_l - 1.0), current_i)
    if trend == "de-escalating":
        return (min(10.0, current_l + 1.0), current_i)
    return (current_l, current_i)


def build_history_points(origin_dt, current_l, current_i, trend, is_foundational):
    """Return list of (recorded_at, likelihood, impact, source) tuples."""
    if not origin_dt:
        return []  # no origin → no synthesis possible

    # Skip "new" trend — current snapshot is enough
    if trend == "new" and not is_foundational:
        return []

    age_months = (NOW - origin_dt).days / 30.0
    points = []

    # Origin point
    o_l, o_i = synth_origin(current_l, current_i, trend)
    points.append((origin_dt, o_l, o_i, "synthesized_origin"))

    if age_months >= 18 and origin_dt < JAN_2025:
        # 4 anchor points for old foundational factors
        m_l, m_i = synth_midpoint(current_l, current_i, trend)
        points.append((JAN_2025, m_l, m_i, "synthesized_jan2025"))
        # current_l/current_i is "Jan 2026 baseline" approximation
        points.append((JAN_2026, current_l, current_i, "synthesized_jan2026"))
    elif age_months >= 12 and origin_dt < JAN_2026:
        points.append((JAN_2026, current_l, current_i, "synthesized_jan2026"))
    elif age_months >= 6:
        m_dt = origin_dt + (NOW - origin_dt) / 2
        m_l, m_i = synth_midpoint(current_l, current_i, trend)
        points.append((m_dt, m_l, m_i, "synthesized_midpoint"))

    # Current snapshot
    points.append((NOW, current_l, current_i, "backfill_current"))

    # De-duplicate by date (origin might equal midpoint for very old factors)
    seen = set()
    deduped = []
    for p in points:
        key = p[0].strftime("%Y-%m-%d")
        if key not in seen:
            seen.add(key)
            deduped.append(p)
    return deduped


async def main():
    inserted = 0
    skipped = 0
    factors_updated = 0

    async with async_session() as db:
        # Pull all active factors plus their existing history count
        result = await db.execute(text("""
            SELECT
                f.code, f.name, f.likelihood, f.impact, f.trend,
                f.origin_date, f.created_at, f.is_foundational,
                (SELECT COUNT(*) FROM pestel_score_history h
                 WHERE h.factor_code = f.code) AS history_count
            FROM pestel_factors f
            WHERE f.is_active = TRUE
            ORDER BY f.is_foundational DESC, f.code
        """))
        factors = result.fetchall()

        print(f"Found {len(factors)} active factors. Synthesizing history...\n")

        for f in factors:
            # If already has 3+ snapshots, skip
            if f.history_count >= 3:
                skipped += 1
                continue

            origin_dt = f.origin_date or f.created_at
            if origin_dt is not None and hasattr(origin_dt, 'tzinfo') and origin_dt.tzinfo is None:
                origin_dt = origin_dt.replace(tzinfo=timezone.utc)

            points = build_history_points(
                origin_dt=origin_dt,
                current_l=float(f.likelihood),
                current_i=float(f.impact),
                trend=f.trend or "stable",
                is_foundational=f.is_foundational or False,
            )

            if not points:
                skipped += 1
                continue

            # Wipe existing synthesized rows for this factor (may conflict)
            await db.execute(
                text("DELETE FROM pestel_score_history WHERE factor_code = :c "
                     "AND source LIKE 'synthesized_%'"),
                {"c": f.code},
            )

            for recorded_at, l, i, src in points:
                await db.execute(text("""
                    INSERT INTO pestel_score_history
                        (factor_code, recorded_at, likelihood, impact, source)
                    VALUES (:c, :ts, :l, :i, :s)
                    ON CONFLICT DO NOTHING
                """), {
                    "c": f.code, "ts": recorded_at,
                    "l": l, "i": i, "s": src,
                })
                inserted += 1

            factors_updated += 1
            if factors_updated % 10 == 0:
                print(f"  [{factors_updated}] Backfilled: {f.name[:50]} ({len(points)} pts)")

        await db.commit()

    print(f"\n{'='*60}")
    print(f"  Factors processed:    {len(factors)}")
    print(f"  Factors backfilled:   {factors_updated}")
    print(f"  Factors skipped:      {skipped} (already had 3+ snapshots)")
    print(f"  Total points inserted: {inserted}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
