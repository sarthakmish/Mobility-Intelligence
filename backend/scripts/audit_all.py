"""
COMPREHENSIVE DATA AUDIT
Uses Sonnet 4.6's automotive industry knowledge to:
1. Verify every technology is in the right segment
2. Verify every PESTEL factor is in the right segment
3. Recalibrate L×I scores with industry expertise
4. Flag stale factors needing data refresh
5. Verify source badges are honest

Run: cd backend && python -m scripts.audit_all
Cost: ~$3-5 (approximately 20-25 Sonnet calls)
Time: ~10 minutes
"""

import asyncio
import json
import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from db.connection import async_session
from services.llm_service import llm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-5s | %(message)s",
)
logger = logging.getLogger("audit")

SEGMENTS = ["4W_PV", "LCV", "HCV", "2W", "3W", "Tractor"]

SEG_DESC = {
    "4W_PV":   "Passenger cars, SUVs, vans (petrol/diesel/CNG/EV). 43L units. Domestic + exports to EU/US.",
    "LCV":     "Light commercial ≤7.5T GVW — pickups, small trucks, delivery vans. 5.2L units.",
    "HCV":     "Heavy commercial >7.5T GVW — trucks, buses, tippers. 4.4L units.",
    "2W":      "Motorcycles, scooters (petrol/EV). 1.96Cr units. NO DIESEL engines. Basic electronics only.",
    "3W":      "Auto-rickshaws, cargo 3W (CNG/EV dominant). 7.41L units. NO DIESEL. Basic electronics.",
    "Tractor": "Agricultural tractors ONLY. Diesel engines, basic hydraulics, minimal electronics. NO ADAS, NO infotainment, NO EV (yet). 10.6L units.",
}


# ═══════════════════════════════════════════════════════
# AUDIT A: Technology-Segment Relevance
# ═══════════════════════════════════════════════════════
async def audit_tech_segments():
    logger.info("\n" + "=" * 60)
    logger.info("AUDIT A: Technology-Segment Relevance")
    logger.info("=" * 60)

    async with async_session() as db:
        result = await db.execute(text(
            "SELECT code, name, market_data, confidence, source_note "
            "FROM technologies WHERE is_active = TRUE ORDER BY name"
        ))
        techs = [dict(r._mapping) for r in result.fetchall()]

    all_corrections = []

    for segment in SEGMENTS:
        seg_techs = []
        for t in techs:
            md = t["market_data"] if isinstance(t["market_data"], dict) else json.loads(t["market_data"] or "{}")
            val = md.get(segment, 0)
            if isinstance(val, dict):
                val = val.get("fy25", 0)
            if val and val > 0:
                seg_techs.append({
                    "name": t["name"],
                    "code": t["code"],
                    "market_cr": val,
                    "source": t.get("source_note", ""),
                })

        if not seg_techs:
            continue

        prompt = f"""You are a senior Indian automotive component industry analyst.

TASK: Review each technology below and determine if it is GENUINELY relevant
for the {segment} vehicle segment in India.

SEGMENT: {segment}
{SEG_DESC[segment]}

TECHNOLOGIES CURRENTLY ASSIGNED TO {segment}:
{chr(10).join(f"- {t['name']}: ₹{t['market_cr']} Cr (source: {t['source']})" for t in seg_techs)}

For EACH technology, return:
[
  {{
    "name": "exact technology name",
    "relevant": true or false,
    "reason": "10 words max",
    "suggested_market_cr": null or realistic number if current value seems wrong
  }}
]

KEY KNOWLEDGE:
- Diesel aftertreatment (SCR, DPF, common rail diesel injection) does NOT exist in 2W/3W
- Camera-based ADAS (L2+, LiDAR, surround view) does NOT exist in 2W/3W/Tractor
- Battery swapping in India is ONLY for 2W/3W, not 4W PV
- Air disc brakes are HCV/Bus only
- Infotainment with touchscreen HMI does NOT exist in 2W/3W
- Tractors have NO: ADAS, infotainment, V2X, cloud, cybersecurity, EV powertrain
- ABS is mandatory for 2W >125cc (so relevant for 2W) but NOT for tractors

Return ONLY the JSON array."""

        logger.info(f"  Auditing {len(seg_techs)} techs for {segment}...")
        result = await llm.call_sonnet(prompt, max_tokens=6000)
        parsed = llm.parse_json_response(result["content"])

        if parsed:
            for item in parsed:
                if not item.get("relevant", True):
                    all_corrections.append({
                        "type": "tech_zero",
                        "segment": segment,
                        "name": item["name"],
                        "reason": item.get("reason", ""),
                    })
                    logger.info(f"    ❌ {item['name']} → NOT relevant for {segment}: {item.get('reason', '')}")
                elif item.get("suggested_market_cr") is not None:
                    all_corrections.append({
                        "type": "tech_adjust",
                        "segment": segment,
                        "name": item["name"],
                        "new_value": item["suggested_market_cr"],
                        "reason": item.get("reason", ""),
                    })
                    logger.info(f"    ⚠️  {item['name']} → ADJUST to ₹{item['suggested_market_cr']} Cr: {item.get('reason', '')}")

    logger.info(f"  Total tech corrections: {len(all_corrections)}")
    return all_corrections


# ═══════════════════════════════════════════════════════
# AUDIT B: PESTEL Factor-Segment Assignment
# ═══════════════════════════════════════════════════════
async def audit_pestel_segments():
    logger.info("\n" + "=" * 60)
    logger.info("AUDIT B: PESTEL Factor-Segment Assignment")
    logger.info("=" * 60)

    async with async_session() as db:
        result = await db.execute(text(
            "SELECT code, name, category, likelihood, impact, segment_relevance, "
            "selection_reasoning FROM pestel_factors "
            "WHERE is_active = TRUE ORDER BY (likelihood * impact) DESC"
        ))
        factors = [dict(r._mapping) for r in result.fetchall()]

    all_corrections = []
    batch_size = 12

    for i in range(0, len(factors), batch_size):
        batch = factors[i:i + batch_size]
        factor_list = []
        for f in batch:
            sr = f["segment_relevance"] if isinstance(f["segment_relevance"], dict) else json.loads(f["segment_relevance"] or "{}")
            factor_list.append(
                f"- [{f['category']}] {f['name']} (L:{f['likelihood']} I:{f['impact']}) "
                f"Segments: 4W={sr.get('4W_PV', '?')} LCV={sr.get('LCV', '?')} HCV={sr.get('HCV', '?')} "
                f"2W={sr.get('2W', '?')} 3W={sr.get('3W', '?')} Tractor={sr.get('Tractor', '?')}"
            )

        prompt = f"""You are a senior Indian automotive industry strategist with 20 years of experience.

TASK: Review each PESTEL factor and correct the segment relevance ratings AND the
Likelihood/Impact scores. Use your deep knowledge of the Indian auto component market.

FACTORS TO REVIEW:
{chr(10).join(factor_list)}

SEGMENT DEFINITIONS:
- 4W_PV: Passenger cars/SUVs. 43L units. Domestic + exports to EU/US.
- LCV: Light commercial ≤7.5T. 5.2L units. Last-mile delivery, small fleet.
- HCV: Heavy commercial >7.5T. 4.4L units. Trucks, buses, tippers.
- 2W: Motorcycles/scooters. 1.96Cr units. Petrol + EV (~7%).
- 3W: Auto-rickshaws/cargo. 7.41L units. CNG + EV (~55%).
- Tractor: Agricultural. 10.6L units. Diesel. Basic.

CRITICAL RULES FOR SEGMENT ASSIGNMENT:
- "H" = This factor DIRECTLY and SIGNIFICANTLY affects this segment
- "M" = INDIRECT but measurable effect
- "L" = NO meaningful effect. THIS IS THE DEFAULT.
- EU CBAM: Affects steel/aluminium EXPORTS → HCV=H, LCV=H, 4W_PV=M (exports only), 2W=L, 3W=L, Tractor=L
- CAFE norms: Apply to passenger + light commercial ONLY → 4W_PV=H, LCV=H, others=L
- Connected car: Consumer feature for 4W PV ONLY (fleet telematics ≠ connected car) → 4W_PV=H, others=L
- OEM-specific: ONLY segments that OEM operates in (JLR=4W only, Ola=2W only, Bajaj=2W+3W)
- CV financing: LCV=H, HCV=H, 3W=M (for fleet), 4W=L, 2W=L, Tractor=L
- An investment by ONE company: Impact should be 5-7 max (not industry-wide)
- A government MANDATE/LAW: Likelihood should be 8-10 (it's enacted)
- A market TREND: Likelihood 6-8 (probable but not certain)
- A geopolitical risk: Impact based on actual India exposure, not global headlines

SCORING CALIBRATION:
- L:10 = Already enacted/happened with certainty
- L:8-9 = Officially announced, timeline confirmed
- L:6-7 = Highly probable based on policy trajectory
- L:4-5 = Speculative but plausible
- I:9-10 = Affects >30% of the ₹6.73L Cr industry
- I:7-8 = Affects ₹50,000+ Cr market
- I:5-6 = Affects ₹10,000-50,000 Cr
- I:3-4 = Affects ₹1,000-10,000 Cr
- I:1-2 = Affects <₹1,000 Cr

Return JSON array:
[
  {{
    "name": "exact factor name",
    "corrected_segments": {{"4W_PV":"H/M/L","LCV":"H/M/L","HCV":"H/M/L","2W":"H/M/L","3W":"H/M/L","Tractor":"H/M/L"}},
    "corrected_L": number or null,
    "corrected_I": number or null,
    "reasoning": "15 words max"
  }}
]

Return ONLY the JSON array."""

        logger.info(f"  Auditing PESTEL batch {i // batch_size + 1} ({len(batch)} factors)...")
        result = await llm.call_sonnet(prompt, max_tokens=5000)
        parsed = llm.parse_json_response(result["content"])

        if parsed:
            for item in parsed:
                all_corrections.append(item)
                orig = next((f for f in batch if f["name"] == item["name"]), None)
                if orig:
                    orig_sr = orig["segment_relevance"] if isinstance(orig["segment_relevance"], dict) else json.loads(orig["segment_relevance"] or "{}")
                    new_sr = item.get("corrected_segments", {})
                    changes = []
                    for s in SEGMENTS:
                        if orig_sr.get(s, "L") != new_sr.get(s, orig_sr.get(s, "L")):
                            changes.append(f"{s}:{orig_sr.get(s, '?')}→{new_sr.get(s, '?')}")
                    score_change = ""
                    if item.get("corrected_L") and item["corrected_L"] != orig["likelihood"]:
                        score_change += f" L:{orig['likelihood']}→{item['corrected_L']}"
                    if item.get("corrected_I") and item["corrected_I"] != orig["impact"]:
                        score_change += f" I:{orig['impact']}→{item['corrected_I']}"
                    if changes or score_change:
                        logger.info(f"    🔄 {item['name'][:45]}")
                        if changes:
                            logger.info(f"       Segments: {', '.join(changes)}")
                        if score_change:
                            logger.info(f"       Scores:{score_change}")

    logger.info(f"  Total PESTEL corrections: {len(all_corrections)}")
    return all_corrections


# ═══════════════════════════════════════════════════════
# AUDIT C: Stale Factor Check
# ═══════════════════════════════════════════════════════
async def audit_stale_factors():
    logger.info("\n" + "=" * 60)
    logger.info("AUDIT C: Stale Factor Data Check")
    logger.info("=" * 60)

    async with async_session() as db:
        result = await db.execute(text(
            "SELECT code, name, selection_reasoning, likelihood_reasoning, "
            "impact_reasoning, last_refreshed "
            "FROM pestel_factors WHERE is_active = TRUE AND is_foundational = TRUE "
            "ORDER BY name"
        ))
        factors = [dict(r._mapping) for r in result.fetchall()]

    factor_summaries = []
    for f in factors:
        factor_summaries.append(
            f"- {f['name']}: {(f.get('selection_reasoning') or '')[:100]}"
        )

    prompt = f"""You are an Indian automotive industry analyst. Today is April 2026.

These are FOUNDATIONAL PESTEL factors in our system. Some may have STALE data
(e.g., US tariffs showing February 2026 rates when April 2026 may be different).

For each factor, tell me:
1. Is the data likely still current as of April 2026?
2. What should be updated?

FACTORS:
{chr(10).join(factor_summaries)}

Return JSON:
[
  {{
    "name": "factor name",
    "is_stale": true/false,
    "what_to_update": "description of what needs updating, or 'Current' if fine",
    "updated_reasoning": "new description if stale, or null"
  }}
]

KEY KNOWLEDGE (April 2026):
- INR/USD: approximately ₹85-86 (check latest RBI reference rate)
- US tariffs on India auto: 25% base + reciprocal tariffs announced April 2025,
  various negotiations ongoing. Check if any new bilateral deals since Feb 2026.
- EU CBAM: Phase 2 reporting started Jan 2026, financial adjustment from 2027
- India-EU FTA: Signed Jan 2026, ratification in progress
- PLI Auto: ₹25,938 Cr sanctioned, disbursement ongoing
- FAME III: ₹2,671 Cr for EV charging, FY2025-27
- BS-VI Stage 2: Fully implemented April 2025

Return ONLY the JSON array."""

    logger.info(f"  Checking {len(factors)} foundational factors for staleness...")
    result = await llm.call_sonnet(prompt, max_tokens=4000)
    parsed = llm.parse_json_response(result["content"])

    corrections = []
    if parsed:
        for item in parsed:
            if item.get("is_stale"):
                corrections.append(item)
                logger.info(f"    ⏰ STALE: {item['name'][:40]} — {item.get('what_to_update', '')[:60]}")

    logger.info(f"  Stale factors found: {len(corrections)}")
    return corrections


# ═══════════════════════════════════════════════════════
# AUDIT D: Source Badge Verification
# ═══════════════════════════════════════════════════════
async def audit_source_badges():
    logger.info("\n" + "=" * 60)
    logger.info("AUDIT D: Source Badge Verification")
    logger.info("=" * 60)

    async with async_session() as db:
        result = await db.execute(text(
            "SELECT code, name, source_note, confidence, total_market_fy25_cr "
            "FROM technologies WHERE is_active = TRUE ORDER BY name"
        ))
        techs = [dict(r._mapping) for r in result.fetchall()]

    tech_list = [
        f"- {t['name']}: ₹{t.get('total_market_fy25_cr', 0)} Cr | "
        f"Badge: {t.get('confidence', '?')} | Source: {t.get('source_note', 'none')}"
        for t in techs[:40]
    ]

    prompt = f"""You are a data integrity auditor for an automotive intelligence platform.

Each technology below has a market size, a confidence badge, and a source attribution.
Verify: is the source badge HONEST? Does this specific market size genuinely come from
the cited source? Or was it likely ESTIMATED and wrongly labelled as "published"?

TECHNOLOGIES:
{chr(10).join(tech_list)}

For each, return:
[
  {{
    "name": "tech name",
    "badge_honest": true/false,
    "corrected_source": "what the source should say",
    "corrected_confidence": "high/medium/low"
  }}
]

RULES:
- "ACMA FY25" is honest ONLY if ACMA publishes a SPECIFIC market size for this exact technology.
  ACMA publishes TOTAL industry size (₹6.73L Cr) and broad category breakdowns,
  but NOT individual technology market sizes like "₹850 Cr for ADAS L2+ Camera".
- "Mordor Intelligence" is honest if there IS a Mordor report specifically covering this technology.
  Mordor has reports on: Indian ADAS market, EV market, auto component market.
- If the number was DERIVED (total market × segment share × technology proportion) then
  the badge should say "Derived from [source]" not "[source]".
- If genuinely published in a named report: confidence = high
- If derived from a published total: confidence = medium
- If estimated by AI: confidence = low

Return ONLY the JSON array."""

    logger.info(f"  Verifying source badges for {min(len(techs), 40)} technologies...")
    result = await llm.call_sonnet(prompt, max_tokens=5000)
    parsed = llm.parse_json_response(result["content"])

    corrections = []
    if parsed:
        for item in parsed:
            if not item.get("badge_honest", True):
                corrections.append(item)
                logger.info(f"    ⚠️  {item['name'][:35]} — should be: {item.get('corrected_source', '?')}")

    logger.info(f"  Badges needing correction: {len(corrections)}")
    return corrections


# ═══════════════════════════════════════════════════════
# APPLY ALL CORRECTIONS
# ═══════════════════════════════════════════════════════
async def apply_all(tech_corr, pestel_corr, stale_corr, badge_corr):
    logger.info("\n" + "=" * 60)
    logger.info("APPLYING ALL CORRECTIONS")
    logger.info("=" * 60)

    async with async_session() as db:
        applied = {
            "tech_zeroed": 0, "tech_adjusted": 0,
            "pestel_segments": 0, "pestel_scores": 0,
            "stale_updated": 0, "badges_fixed": 0,
        }

        # ── Tech segment corrections ───────────────────────
        for c in tech_corr:
            if c["type"] == "tech_zero":
                try:
                    await db.execute(text(
                        "UPDATE technologies SET market_data = jsonb_set("
                        "market_data, :path, '0'::jsonb) WHERE name = :name"
                    ), {"path": "{" + c["segment"] + "}", "name": c["name"]})
                    applied["tech_zeroed"] += 1
                    logger.info(f"  ✅ Zeroed {c['name']} / {c['segment']}")
                except Exception as e:
                    logger.error(f"  ❌ Failed to zero {c['name']}/{c['segment']}: {e}")
            elif c["type"] == "tech_adjust":
                try:
                    await db.execute(text(
                        "UPDATE technologies SET market_data = jsonb_set("
                        "market_data, :path, :val::jsonb) WHERE name = :name"
                    ), {"path": "{" + c["segment"] + "}", "val": str(c["new_value"]), "name": c["name"]})
                    applied["tech_adjusted"] += 1
                    logger.info(f"  ✅ Adjusted {c['name']} / {c['segment']} → ₹{c['new_value']} Cr")
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
                    await db.execute(text(
                        f"UPDATE pestel_factors SET {', '.join(updates)} WHERE name = :name"
                    ), params)
            except Exception as e:
                logger.error(f"  ❌ Failed to update PESTEL {c['name']}: {e}")

        # ── Stale factor updates ──────────────────────────
        for c in stale_corr:
            if c.get("updated_reasoning"):
                try:
                    await db.execute(text(
                        "UPDATE pestel_factors SET selection_reasoning = :sr, "
                        "last_refreshed = NOW() WHERE name = :name"
                    ), {"sr": c["updated_reasoning"], "name": c["name"]})
                    applied["stale_updated"] += 1
                except Exception as e:
                    logger.error(f"  ❌ Failed to update stale {c['name']}: {e}")

        # ── Badge corrections ─────────────────────────────
        for c in badge_corr:
            try:
                await db.execute(text(
                    "UPDATE technologies SET source_note = :sn, confidence = :conf "
                    "WHERE name = :name"
                ), {
                    "sn": c.get("corrected_source", ""),
                    "conf": c.get("corrected_confidence", "medium"),
                    "name": c["name"],
                })
                applied["badges_fixed"] += 1
            except Exception as e:
                logger.error(f"  ❌ Failed to fix badge {c['name']}: {e}")

        await db.commit()

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


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════
async def main():
    logger.info("╔═══════════════════════════════════════════════════╗")
    logger.info("║  MOBILITY INTELLIGENCE — COMPREHENSIVE DATA AUDIT ║")
    logger.info("║  Using Sonnet 4.6 automotive industry knowledge   ║")
    logger.info("║  Estimated cost: $3-5 │ Time: ~10 minutes         ║")
    logger.info("╚═══════════════════════════════════════════════════╝")

    tech_corrections = await audit_tech_segments()
    pestel_corrections = await audit_pestel_segments()
    stale_corrections = await audit_stale_factors()
    badge_corrections = await audit_source_badges()

    logger.info("\n" + "=" * 60)
    logger.info("AUDIT SUMMARY (before applying)")
    logger.info("=" * 60)
    logger.info(f"Tech segments to zero:     {sum(1 for c in tech_corrections if c['type'] == 'tech_zero')}")
    logger.info(f"Tech markets to adjust:    {sum(1 for c in tech_corrections if c['type'] == 'tech_adjust')}")
    logger.info(f"PESTEL segments to fix:    {len(pestel_corrections)}")
    logger.info(f"Stale factors to update:   {len(stale_corrections)}")
    logger.info(f"Source badges to correct:  {len(badge_corrections)}")

    # Save full preview
    preview = {
        "tech": tech_corrections,
        "pestel": pestel_corrections,
        "stale": stale_corrections,
        "badges": badge_corrections,
    }
    with open("audit_preview.json", "w") as f:
        json.dump(preview, f, indent=2, default=str)
    logger.info("\nFull preview saved to audit_preview.json — review before confirming.")

    confirm = input("\nApply all corrections to database? (yes/no): ")
    if confirm.strip().lower() == "yes":
        await apply_all(tech_corrections, pestel_corrections, stale_corrections, badge_corrections)
        logger.info("\n✅ ALL CORRECTIONS APPLIED")
        logger.info("Next steps:")
        logger.info("  1. Clear Redis cache:  redis-cli FLUSHALL")
        logger.info("  2. Restart uvicorn:    uvicorn main:app --host 0.0.0.0 --port 8000 --reload")
    else:
        logger.info("\nCorrections NOT applied. Review audit_preview.json and run again.")


if __name__ == "__main__":
    asyncio.run(main())
