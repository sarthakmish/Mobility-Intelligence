"""
============================================================
AUDIT — Rewrite every technologies.source_note into a structured
        "TIER: SOURCE | METHODOLOGY" string so the frontend badges
        are honest and consistent across all tech-segment combos.
============================================================
Format:
  Published: <source-name> (FY25 baseline) | <method>
  Derived:   <source-name> (FY25 baseline) | Proportional sizing
  AI Estimate: <source-name> (FY25 baseline) | LLM extrapolation

Run:
  python backend/scripts/audit_source_notes.py             # report
  python backend/scripts/audit_source_notes.py --apply     # commit
============================================================
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from sqlalchemy import text
from backend.db.connection import async_session

APPLY = "--apply" in sys.argv

# Ordered match rules: (predicate(code, pillar), (tier, source, method))
# First match wins — most specific rules first.
RULES = [
    # ── Genuinely published market data ──────────────────────────────
    (
        lambda c, p: (
            c.startswith("powertrain_")
            or c in (
                "transmission_and_drivetrain", "braking_systems", "suspension_system",
                "steering_eps", "body_panels_and_structures", "chassis_frame",
                "wiring_and_harness", "wheels_and_components",
            )
        ),
        ("Published", "ACMA FY25", "Direct industry report"),
    ),
    (
        lambda c, p: any(
            x in c for x in [
                "adas", "l2_camera", "auto_emergency", "adaptive_cruise",
                "lane_keep", "blind_spot", "driver_monitor", "l2_radar",
            ]
        ),
        ("Published", "Mordor Intelligence Jan 2026", "Direct quote from market report"),
    ),
    (
        lambda c, p: "battery_pack" in c or "ev_traction" in c,
        ("Published", "IBEF + IndexBox", "Aggregated published figures"),
    ),
    (
        lambda c, p: "infotainment" in c,
        ("Published", "PS Market Research", "Direct quote"),
    ),
    (
        lambda c, p: "safety_electronics" in c,
        ("Published", "IMARC Group", "Direct quote"),
    ),
    (
        lambda c, p: "sensors_o2" in c,
        ("Published", "PS Market Research", "Direct quote"),
    ),
    # ── Pillar-level derivations from ACMA totals ─────────────────────
    (
        lambda c, p: (
            p in ("Motion", "Body & Comfort", "Energy")
            and any(x in c for x in ["thermal", "hvac", "airbag", "interior", "panel", "comfort"])
        ),
        ("Derived", "ACMA FY25 totals", "Proportional sizing by pillar share"),
    ),
    # ── Everything else: AI Estimate ──────────────────────────────────
]

DEFAULT = ("AI Estimate", "ACMA FY25 + industry interviews", "LLM extrapolation from pillar totals")


def classify(code: str, pillar: str):
    for fn, result in RULES:
        try:
            if fn(code, pillar):
                return result
        except Exception:
            continue
    return DEFAULT


async def main():
    async with async_session() as db:
        rows = await db.execute(text(
            "SELECT code, name, pillar, source_note, confidence "
            "FROM technologies WHERE is_active = TRUE"
        ))
        techs = rows.fetchall()

        print(f"\n{'='*80}\nAuditing source_note across {len(techs)} technologies\n{'='*80}\n")

        tier_counts = {"Published": 0, "Derived": 0, "AI Estimate": 0}
        changed = 0

        for tech in techs:
            tier, source, method = classify(tech.code, tech.pillar)
            new_note = f"{tier}: {source} (FY25 baseline) | {method}"
            new_conf = {"Published": "high", "Derived": "medium", "AI Estimate": "low"}[tier]
            tier_counts[tier] += 1

            if tech.source_note != new_note or tech.confidence != new_conf:
                changed += 1
                if not APPLY:
                    print(f"  [{tech.pillar:>15s}] {tech.code[:35]:<35s}")
                    print(f"      OLD: {(tech.source_note or '<NULL>')[:75]}")
                    print(f"      NEW: {new_note}")
                else:
                    await db.execute(
                        text(
                            "UPDATE technologies SET source_note = :s, confidence = :c "
                            "WHERE code = :code"
                        ),
                        {"s": new_note, "c": new_conf, "code": tech.code},
                    )

        if APPLY:
            await db.commit()

        print(f"\n{'='*80}")
        print(f"  Distribution after audit:")
        for tier, n in tier_counts.items():
            pct = 100 * n / max(len(techs), 1)
            print(f"    {tier:<15s}  {n:>4d} techs ({pct:.1f}%)")
        print(f"  Rows that would change: {changed}")
        if not APPLY:
            print(f"  Run with --apply to commit.")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(main())
