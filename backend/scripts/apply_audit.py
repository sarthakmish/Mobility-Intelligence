"""
Apply corrections from audit_preview.json to the database.
Run: cd backend && python -m scripts.apply_audit
"""

import asyncio
import json
import logging
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from db.connection import async_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-5s | %(message)s",
)
logger = logging.getLogger("apply_audit")

# ── Fix double-letter typos introduced by AI in source names ──────────────────
_TYPO_FIXES = [
    (re.compile(r'\bCRRISIL\b', re.I), "CRISIL"),
    (re.compile(r'\bACCMA\b', re.I), "ACMA"),
    (re.compile(r'\bAACMA\b', re.I), "ACMA"),
    (re.compile(r'\bFrrost\b', re.I), "Frost"),
    (re.compile(r'\bMoordor\b', re.I), "Mordor"),
    (re.compile(r'\bIntellliigence\b', re.I), "Intelligence"),
    (re.compile(r'\bIntelliigence\b', re.I), "Intelligence"),
    (re.compile(r'\bIntellligence\b', re.I), "Intelligence"),
    (re.compile(r'\bGrrand\b', re.I), "Grand"),
    (re.compile(r'\bMaarketsandMarkets\b', re.I), "MarketsandMarkets"),
    (re.compile(r'\bMaarkets\b', re.I), "Markets"),
    (re.compile(r'\blooosely\b', re.I), "loosely"),
    (re.compile(r'\bPSS\b'), "PSS"),   # keep as-is
    (re.compile(r'\bCRISIIL\b', re.I), "CRISIL"),
    (re.compile(r'\bIIndustry\b', re.I), "Industry"),
    (re.compile(r'\bIndustrry\b', re.I), "Industry"),
]


def fix_typos(s: str) -> str:
    if not s:
        return s
    for pat, replacement in _TYPO_FIXES:
        s = pat.sub(replacement, s)
    return s


async def apply_all(tech_corr, pestel_corr, stale_corr, badge_corr):
    logger.info("\n" + "=" * 60)
    logger.info("APPLYING ALL CORRECTIONS")
    logger.info("=" * 60)

    applied = {
        "tech_zeroed": 0, "tech_adjusted": 0,
        "pestel_segments": 0, "pestel_scores": 0,
        "stale_updated": 0, "badges_fixed": 0,
    }

    # ── Tech segment corrections (one session each to avoid cascade aborts) ──
    SAFE_SEGMENTS = {"4W_PV", "LCV", "HCV", "2W", "3W", "Tractor"}
    for c in tech_corr:
        seg = c["segment"]
        if seg not in SAFE_SEGMENTS:
            logger.warning(f"  ⚠️  Skipping unknown segment {seg!r}")
            continue
        if c["type"] == "tech_zero":
            try:
                async with async_session() as db:
                    # Inline the segment key — safe because it's from our enum above.
                    # async pg cannot bind text[] params via :placeholder; use literal path.
                    await db.execute(text(
                        f"UPDATE technologies "
                        f"SET market_data = jsonb_set(market_data, '{{{seg}}}', '0'::jsonb, true) "
                        f"WHERE name = :name"
                    ), {"name": c["name"]})
                    await db.commit()
                applied["tech_zeroed"] += 1
                logger.info(f"  ✅ Zeroed {c['name']} / {seg}")
            except Exception as e:
                logger.error(f"  ❌ Failed to zero {c['name']}/{seg}: {e}")

        elif c["type"] == "tech_adjust":
            try:
                val = str(c["new_value"])
                async with async_session() as db:
                    await db.execute(text(
                        f"UPDATE technologies "
                        f"SET market_data = jsonb_set(market_data, '{{{seg}}}', '{val}'::jsonb, true) "
                        f"WHERE name = :name"
                    ), {"name": c["name"]})
                    await db.commit()
                applied["tech_adjusted"] += 1
                logger.info(f"  ✅ Adjusted {c['name']} / {seg} → ₹{val} Cr")
            except Exception as e:
                logger.error(f"  ❌ Failed to adjust {c['name']}: {e}")

    # ── PESTEL segment + score corrections ────────────
    for c in pestel_corr:
        try:
            updates = []
            params = {"name": c["name"]}
            if c.get("corrected_segments"):
                updates.append("segment_relevance = :sr")
                params["sr"] = json.dumps(c["corrected_segments"])
                applied["pestel_segments"] += 1
            if c.get("corrected_L") is not None:
                updates.append("likelihood = :lk")
                params["lk"] = c["corrected_L"]
                applied["pestel_scores"] += 1
            if c.get("corrected_I") is not None:
                updates.append("impact = :imp")
                params["imp"] = c["corrected_I"]
            if updates:
                async with async_session() as db:
                    await db.execute(text(
                        f"UPDATE pestel_factors SET {', '.join(updates)} WHERE name = :name"
                    ), params)
                    await db.commit()
        except Exception as e:
            logger.error(f"  ❌ Failed to update PESTEL {c['name']}: {e}")

    # ── Stale factor updates ──────────────────────────
    for c in stale_corr:
        if c.get("updated_reasoning"):
            try:
                async with async_session() as db:
                    await db.execute(text(
                        "UPDATE pestel_factors SET selection_reasoning = :sr, "
                        "last_refreshed = NOW() WHERE name = :name"
                    ), {"sr": c["updated_reasoning"], "name": c["name"]})
                    await db.commit()
                applied["stale_updated"] += 1
            except Exception as e:
                logger.error(f"  ❌ Failed to update stale {c['name']}: {e}")

    # ── Badge corrections (with typo fixes) ──────────
    for c in badge_corr:
        corrected_source = fix_typos(c.get("corrected_source", ""))
        try:
            async with async_session() as db:
                await db.execute(text(
                    "UPDATE technologies SET source_note = :sn, confidence = :conf "
                    "WHERE name = :name"
                ), {
                    "sn": corrected_source,
                    "conf": c.get("corrected_confidence", "medium"),
                    "name": c["name"],
                })
                await db.commit()
            applied["badges_fixed"] += 1
            logger.info(f"  ✅ Badge fixed: {c['name'][:35]} → {corrected_source}")
        except Exception as e:
            logger.error(f"  ❌ Failed to fix badge {c['name']}: {e}")

    logger.info("\n╔══════════════════════════════════════════╗")
    logger.info("║         AUDIT RESULTS APPLIED             ║")
    logger.info("╠══════════════════════════════════════════╣")
    logger.info(f"║ Tech segments zeroed:     {applied['tech_zeroed']:>4}            ║")
    logger.info(f"║ Tech markets adjusted:    {applied['tech_adjusted']:>4}            ║")
    logger.info(f"║ PESTEL segments fixed:    {applied['pestel_segments']:>4}            ║")
    logger.info(f"║ PESTEL scores adjusted:   {applied['pestel_scores']:>4}            ║")
    logger.info(f"║ Stale factors updated:    {applied['stale_updated']:>4}            ║")
    logger.info(f"║ Source badges corrected:  {applied['badges_fixed']:>4}            ║")
    logger.info("╚══════════════════════════════════════════╝")
    return applied


async def main():
    preview_path = os.path.join(os.path.dirname(__file__), "..", "audit_preview.json")
    if not os.path.exists(preview_path):
        logger.error("audit_preview.json not found. Run audit_all.py first.")
        sys.exit(1)

    with open(preview_path) as f:
        preview = json.load(f)

    tech_corr = preview.get("tech", [])
    pestel_corr = preview.get("pestel", [])
    stale_corr = preview.get("stale", [])
    badge_corr = preview.get("badges", [])

    logger.info(f"Loaded audit_preview.json:")
    logger.info(f"  Tech corrections:   {len(tech_corr)}")
    logger.info(f"  PESTEL corrections: {len(pestel_corr)}")
    logger.info(f"  Stale factors:      {len(stale_corr)}")
    logger.info(f"  Badge corrections:  {len(badge_corr)}")

    await apply_all(tech_corr, pestel_corr, stale_corr, badge_corr)

    logger.info("\n✅ ALL CORRECTIONS APPLIED")
    logger.info("Next steps:")
    logger.info("  1. Clear Redis cache")
    logger.info("  2. Restart uvicorn")


if __name__ == "__main__":
    asyncio.run(main())
