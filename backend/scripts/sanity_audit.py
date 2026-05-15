#!/usr/bin/env python3
"""
sanity_audit.py — Pre-demo PESTEL data quality audit
=====================================================
Runs 8 data-quality rules against the pestel_factors table and reports
issues grouped by severity.  Run from the backend/ directory:

    python scripts/sanity_audit.py
    python scripts/sanity_audit.py --fix      # auto-fix CRITICAL issues

Rules
-----
R1  Future origin_date           — origin_date > today (should never happen)
R2  origin_date / key_dates mismatch — DB date older than LLM-produced announced date
R3  Aggregate EV% applied to 4W_PV=H — 8% aggregate but 4W ~3% (Rule 7)
R4  Mandate without gov.in citation  — L/P factor, no government source cited
R5  Five-or-more H-rated segments  — almost always wrong per Rule 7
R6  Mandate past effective date still marked FRESH or EMERGING
R7  Low-confidence + high-impact   — confirmation_count=1 AND impact>=8
R8  Stale last_refreshed           — active factor not refreshed >60 days
"""

import asyncio
import asyncpg
import json
import sys
from datetime import date, timedelta

DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/mobility_intelligence").replace("postgresql+asyncpg://", "postgresql://")
SEGS   = ["4W_PV", "2W", "3W", "HCV", "LCV", "Tractor"]

# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _announced_to_date(ann: str):
    """Convert key_dates.announced string to date or None."""
    if not ann:
        return None
    ann = ann.strip()
    try:
        if len(ann) == 7:
            return date.fromisoformat(ann + "-01")
        if len(ann) == 10:
            return date.fromisoformat(ann)
        if len(ann) == 4:
            return date.fromisoformat(ann + "-01-01")
    except ValueError:
        pass
    return None


def _h_count(seg_rel: dict) -> int:
    return sum(1 for s in SEGS if seg_rel.get(s) == "H")


# ─────────────────────────────────────────────────────────────────────────────
# Audit rules (each returns list of dicts with keys: code, name, detail)
# ─────────────────────────────────────────────────────────────────────────────

async def r1_future_origin(conn, rows):
    today = date.today()
    return [
        {"code": r["code"], "name": r["name"],
         "detail": f"origin_date={r['origin_date']} is in the future"}
        for r in rows
        if r["origin_date"] and r["origin_date"] > today
    ]


async def r2_origin_mismatch(conn, rows):
    issues = []
    for r in rows:
        kd = r["key_dates"]
        if isinstance(kd, str):
            try:
                kd = json.loads(kd)
            except Exception:
                kd = {}
        ann_s = (kd or {}).get("announced", "")
        ann_d = _announced_to_date(ann_s)
        if ann_d and r["origin_date"] and ann_d != r["origin_date"]:
            delta = abs((ann_d - r["origin_date"]).days)
            if delta > 60:   # flag only meaningful drift (>2 months)
                issues.append({
                    "code": r["code"], "name": r["name"],
                    "detail": f"origin_date={r['origin_date']} but key_dates.announced={ann_s!r} → {ann_d}"
                })
    return issues


async def r3_ev_aggregate_4w(conn, rows):
    issues = []
    for r in rows:
        if "ev penetration" not in r["name"].lower():
            continue
        if "8%" not in r["name"] and r.get("impact", 0) < 8:
            continue
        sr = r["segment_relevance"]
        if isinstance(sr, str):
            try:
                sr = json.loads(sr)
            except Exception:
                sr = {}
        if (sr or {}).get("4W_PV") == "H":
            issues.append({
                "code": r["code"], "name": r["name"],
                "detail": "4W_PV=H for EV aggregate factor — 4W EV ~3% not 8%; should be M"
            })
    return issues


async def r4_mandate_no_gov_source(conn, rows):
    issues = []
    for r in rows:
        if r["category"] not in ("L", "P"):
            continue
        src_ids = r.get("source_ids") or ""
        if isinstance(src_ids, list):
            src_ids = " ".join(str(x) for x in src_ids)
        if "gov.in" not in src_ids.lower() and "morth" not in src_ids.lower() and "gazette" not in src_ids.lower():
            issues.append({
                "code": r["code"], "name": r["name"],
                "detail": f"L/P factor with no government source: source_ids={str(src_ids)[:100]!r}"
            })
    return issues


async def r5_all_segments_h(conn, rows):
    issues = []
    for r in rows:
        sr = r["segment_relevance"]
        if isinstance(sr, str):
            try:
                sr = json.loads(sr)
            except Exception:
                sr = {}
        h = _h_count(sr or {})
        if h >= 5:
            issues.append({
                "code": r["code"], "name": r["name"],
                "detail": f"{h}/6 segments rated H — almost certainly an aggregate leakage (Rule 7)"
            })
    return issues


async def r6_mandate_past_effective_not_established(conn, rows):
    today = date.today()
    issues = []
    for r in rows:
        if r["category"] not in ("L", "P"):
            continue
        od = r.get("origin_date")
        if not od:
            continue
        if od <= today and r.get("freshness_tier") in ("FRESH", "EMERGING", "DECAYING"):
            issues.append({
                "code": r["code"], "name": r["name"],
                "detail": (
                    f"Legal/Policy mandate with origin_date={od} (past) "
                    f"still shows freshness_tier={r.get('freshness_tier')!r}; "
                    "should be ESTABLISHED"
                )
            })
    return issues


async def r7_low_conf_high_impact(conn, rows):
    return [
        {"code": r["code"], "name": r["name"],
         "detail": f"confirmation_count={r.get('confirmation_count',1)}, impact={r.get('impact')} — "
                   "single-source high-impact factor needs verification"}
        for r in rows
        if r.get("confirmation_count", 1) == 1 and (r.get("impact") or 0) >= 8
    ]


async def r8_stale_refreshed(conn, rows):
    cutoff = date.today() - timedelta(days=60)
    return [
        {"code": r["code"], "name": r["name"],
         "detail": f"last_refreshed={r['last_refreshed']} — not refreshed in >60 days"}
        for r in rows
        if r.get("last_refreshed") and r["last_refreshed"].date() < cutoff
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Auto-fix for CRITICAL issues (R1, R3, R6)
# ─────────────────────────────────────────────────────────────────────────────

async def auto_fix(conn, r1, r3, r6):
    fixed = 0

    # R1 — clamp future origin_date to today
    for issue in r1:
        await conn.execute(
            "UPDATE pestel_factors SET origin_date = CURRENT_DATE, last_refreshed = NOW() "
            "WHERE code = $1 AND is_active = TRUE",
            issue["code"]
        )
        fixed += 1
        print(f"  [FIX R1] {issue['code']}: origin_date clamped to today")

    # R3 — downgrade 4W_PV from H to M for EV aggregate
    for issue in r3:
        await conn.execute(
            "UPDATE pestel_factors "
            "SET segment_relevance = jsonb_set(segment_relevance, '{4W_PV}', '\"M\"'), "
            "    impact = LEAST(impact, 6), last_refreshed = NOW() "
            "WHERE code = $1 AND is_active = TRUE",
            issue["code"]
        )
        fixed += 1
        print(f"  [FIX R3] {issue['code']}: 4W_PV downgraded from H to M")

    # R6 — freshness inconsistency for past-dated mandates: force ESTABLISHED via confirmation bump
    for issue in r6:
        await conn.execute(
            "UPDATE pestel_factors "
            "SET confirmation_count = GREATEST(COALESCE(confirmation_count, 1), 3), "
            "    last_refreshed = NOW() "
            "WHERE code = $1 AND is_active = TRUE",
            issue["code"]
        )
        fixed += 1
        print(f"  [FIX R6] {issue['code']}: confirmation_count bumped to 3 (→ ESTABLISHED)")

    return fixed


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    do_fix = "--fix" in sys.argv

    conn = await asyncpg.connect(DB_URL)

    rows = await conn.fetch("""
        SELECT code, name, category, likelihood, impact,
               origin_date, key_dates, segment_relevance,
               source_ids, last_refreshed, confirmation_count,
               is_foundational,
               CASE
                   WHEN is_foundational = TRUE THEN 'ESTABLISHED'
                   WHEN category IN ('L','P') AND origin_date IS NOT NULL
                        AND origin_date <= CURRENT_DATE THEN 'ESTABLISHED'
                   WHEN COALESCE(confirmation_count,1) >= 3 THEN 'ESTABLISHED'
                   WHEN category NOT IN ('L','P','En') AND is_foundational IS NOT TRUE
                        AND COALESCE(last_confirmed_date, last_refreshed) < NOW() - INTERVAL '30 days'
                        THEN 'FADING'
                   WHEN COALESCE(confirmation_count,1) = 1
                        AND category NOT IN ('L','P','En') AND is_foundational IS NOT TRUE
                        AND COALESCE(last_confirmed_date, last_refreshed) < NOW() - INTERVAL '14 days'
                        THEN 'DECAYING'
                   ELSE 'EMERGING'
               END AS freshness_tier
        FROM pestel_factors
        WHERE is_active = TRUE
        ORDER BY (likelihood * impact) DESC
    """)

    rows = [dict(r) for r in rows]

    print(f"\n{'='*60}")
    print(f"PESTEL Sanity Audit — {date.today()}   ({len(rows)} active factors)")
    print(f"{'='*60}")

    results = {
        "R1 Future origin_date (CRITICAL)":        await r1_future_origin(conn, rows),
        "R2 origin_date / announced mismatch (HIGH)": await r2_origin_mismatch(conn, rows),
        "R3 EV aggregate leakage to 4W_PV (CRITICAL)": await r3_ev_aggregate_4w(conn, rows),
        "R4 Mandate without gov.in source (MEDIUM)": await r4_mandate_no_gov_source(conn, rows),
        "R5 5+ segments rated H (HIGH)":           await r5_all_segments_h(conn, rows),
        "R6 Past mandate not ESTABLISHED (HIGH)":  await r6_mandate_past_effective_not_established(conn, rows),
        "R7 Low-conf + high-impact (MEDIUM)":      await r7_low_conf_high_impact(conn, rows),
        "R8 Stale last_refreshed >60d (LOW)":      await r8_stale_refreshed(conn, rows),
    }

    total_issues = 0
    for rule, issues in results.items():
        total_issues += len(issues)
        if issues:
            print(f"\n❌ {rule} — {len(issues)} issue(s)")
            for i in issues[:10]:
                print(f"   [{i['code']}] {i['name'][:60]}")
                print(f"     → {i['detail']}")
            if len(issues) > 10:
                print(f"   … and {len(issues)-10} more")
        else:
            print(f"\n✅ {rule} — OK")

    # Quickest wins
    critical = (
        results["R1 Future origin_date (CRITICAL)"]
        + results["R3 EV aggregate leakage to 4W_PV (CRITICAL)"]
        + results["R6 Past mandate not ESTABLISHED (HIGH)"]
    )
    print(f"\n{'='*60}")
    print(f"SUMMARY: {total_issues} issues found — {len(critical)} CRITICAL/HIGH auto-fixable")
    print(f"{'='*60}")

    if do_fix:
        print("\n--- AUTO-FIX MODE ---")
        fixed = await auto_fix(
            conn,
            results["R1 Future origin_date (CRITICAL)"],
            results["R3 EV aggregate leakage to 4W_PV (CRITICAL)"],
            results["R6 Past mandate not ESTABLISHED (HIGH)"],
        )
        print(f"\nFixed {fixed} issue(s) in R1 / R3 / R6")
        print("For R2 / R4 / R5 / R7 / R8: manual review recommended.")
    elif critical:
        print("\nRun with --fix to auto-resolve CRITICAL/HIGH issues:")
        print("  python scripts/sanity_audit.py --fix")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
