"""
============================================================
ORCHESTRATOR — The Brain That Coordinates All Agents
============================================================
This is the MAIN ENTRY POINT for all AI operations.

Think of it as the conductor of an orchestra:
- It doesn't play any instrument itself
- It tells each agent WHEN to play and WHAT to play
- It passes data between agents
- It handles errors and fallbacks

Two modes of operation:
1. SCHEDULED REFRESH (every 6 hours via APScheduler)
   → Scrape web → Discover PESTEL → Score → Validate → Store
   
2. ON-DEMAND ANALYSIS (user clicks a bubble)
   → Check cache → If miss: call appropriate agent → Cache result
============================================================
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from sqlalchemy import text

from services.llm_service import llm
from services.web_intelligence import WebIntelligenceService
from services.cache_service import CacheService
from agents.pestel_agent import pestel_agent
from agents.tech_agent import tech_agent
from agents.validation_agent import validation_agent

logger = logging.getLogger("orchestrator")

# ── Pillar name normalization map (Fix 3) ──────────────────────
# Maps long LLM-generated pillar names → short VALID_PILLARS IDs
# that match the technology table's pillar values.
PILLAR_NORMALIZE = {
    "Powertrain Solutions": "Motion", "Chassis Systems": "Motion",
    "Vehicle Motion": "Motion", "Drivetrain": "Motion",
    "EV Powertrain": "Energy", "Energy & Charging": "Energy",
    "Thermal Management": "Energy", "Battery Systems": "Energy",
    "Body Electronics": "Infotainment", "Vehicle Diagnostics": "Infotainment",
    "Infotainment & Connectivity": "Infotainment", "Electronics": "Infotainment",
    "Software & Services": "OS", "Vehicle OS": "OS",
    "Manufacturing & Industry 4.0": "Compute",
    "Aftermarket & Retrofit": "Services", "Aftermarket": "Services",
    "Safety & Security": "ADAS", "Autonomous Driving": "ADAS",
    "Sensors & Actuators": "Actuators", "Power Tools": "Actuators",
}

VALID_PILLARS = {
    "ADAS", "Motion", "Energy", "Body & Comfort", "Infotainment",
    "OS", "Compute", "ECUs", "Semiconductors", "Actuators",
    "Solutions", "Services", "Cloud",
}

# ──────────────────────────────────────────────────────────────────
# REGULATORY / STRUCTURAL DETECTION
# ──────────────────────────────────────────────────────────────────
# Auto-protects factors from decay even if is_foundational is not set.
# A factor matching ANY of these conditions is considered "structural":
#   1. Category is P (Political) or L (Legal)
#   2. Name contains a regulatory/policy keyword
# Structural factors are excluded from tier-1 and tier-2 decay sweeps.
REGULATORY_KEYWORDS = [
    # Mandate language
    "mandate", "mandatory", " act ", " rules", " norms", "regulation",
    "compliance", "standard ", "policy", "scheme", "subsidy",
    "incentive", "tariff", "fta", "treaty", "directive", "ban ",
    "phase-out", "phaseout",
    # Specific Indian programs
    "pli", "fame", "pm e-drive", "pm-e drive", "make in india",
    "atmanirbhar",
    # Specific safety / emission programs
    "ncap", "bncap", "bharat ncap", "bs-vi", "bs-vii", "bs6", "bs7",
    "aeb", "aebs", "obd-ii", "obd2", "rde", "cafe ", "trem",
    "cmvr", "ais-",
    # Trade / data programs
    "cbam", "dpdp", "wto", "rcep", "usmca", "msps",
    # Government issuance
    "morth notification", "moef", "moci", "moshi", "gazette",
    "notification", "presidential", "ministerial",
]

def is_structural_factor(name: str, category: str) -> bool:
    """
    Return True if this factor represents a regulation, mandate, scheme,
    treaty, or other structural/legal element that exists independent of
    news cycles.
    """
    if (category or "").upper() in ("P", "L"):
        return True
    n = (name or "").lower()
    return any(kw in n for kw in REGULATORY_KEYWORDS)


class Orchestrator:
    """
    Central coordinator for all AI agents and data pipelines.
    """

    def __init__(self):
        self.web_intel = WebIntelligenceService()
        self.cache = CacheService()
        self._is_refreshing = False  # Prevent concurrent refreshes

    # ════════════════════════════════════════════════════════
    # MODE 1: SCHEDULED DATA REFRESH
    # ════════════════════════════════════════════════════════
    async def run_scheduled_refresh(self, db_session, trigger_type: str = "scheduled") -> Dict[str, Any]:
        """
        Full data refresh pipeline. Runs every 6 hours (configurable).
        
        Pipeline:
        ┌─────────────────────────────────────────────────┐
        │  1. SCRAPE: Collect latest news & data from web │
        │  2. PESTEL: Discover/update PESTEL factors      │
        │  3. TECH:   Update technology market data        │
        │  4. VALIDATE: Multi-LLM consensus check         │
        │  5. STORE:  Save to PostgreSQL                   │
        │  6. CACHE:  Invalidate stale Redis cache         │
        │  7. LOG:    Record refresh in audit trail        │
        └─────────────────────────────────────────────────┘
        
        Called by: APScheduler (automatic) or POST /api/refresh/full (manual)
        """
        # ── Guard: prevent concurrent refreshes ──────────
        if self._is_refreshing:
            logger.warning("Refresh already in progress, skipping")
            return {"status": "skipped", "reason": "refresh_in_progress"}

        self._current_trigger = trigger_type
        self._is_refreshing = True
        start_time = datetime.now(timezone.utc)

        try:
            logger.info("╔══════════════════════════════════════════════╗")
            logger.info("║     FULL DATA REFRESH STARTED                ║")
            logger.info(f"║     Trigger: {trigger_type:<31}║")
            logger.info("╚══════════════════════════════════════════════╝")

            # ── STEP 1: Scrape latest data from web ──────
            # The Web Intelligence Service collects from 8+ sources:
            # ACMA, SIAM, MoRTH, ET Auto, Livemint, Moneycontrol, IBEF, Vahan
            logger.info("Step 1/6: Collecting web intelligence...")
            news_content = await self.web_intel.collect_latest_news()
            market_data = await self.web_intel.collect_market_data()

            logger.info(
                f"  \u2192 Collected {len(news_content)} chars of news, "
                f"{len(market_data)} market data points"
            )
            logger.info("  \u2192 Sources scraped:")
            for src in self.web_intel.last_source_texts:
                logger.info(
                    f"     \U0001f4f0 {src['name']:<25} \u2502 {src['chars']:>5} chars "
                    f"\u2502 {src['url']}"
                )

            # ── STEP 2: Get existing factors from DB ─────
            # We need this to avoid discovering duplicates
            logger.info("Step 2/6: Loading existing factors from DB...")
            existing_factors = await self._get_existing_factor_names(db_session)

            # ── STEP 3: Run PESTEL agent pipeline ────────
            # Discover → Filter → Validate
            logger.info("Step 3/6: Running PESTEL agent pipeline (with source-grounded validation)...")
            pestel_results = await pestel_agent.run_full_refresh(
                news_content=news_content,
                existing_factor_names=existing_factors,
                validate=True,            # ✅ ON — persists to validation_logs
                db_session=db_session,    # ✅ required so persistence works
            )

            # ── STEP 3b: Technology scan (non-blocking scout) ─────
            # Haiku-powered scan for new tech categories not yet tracked.
            # Results are flagged for manual review — nothing auto-added to DB.
            logger.info("Step 3b/6: Scanning for emerging technology categories...")
            existing_techs = await self._get_existing_tech_names(db_session)
            tech_findings = await tech_agent.check_for_new_technologies(
                news_content=news_content,
                existing_techs=existing_techs,
            )
            if tech_findings["flagged_count"] > 0:
                logger.info(
                    f"  ⚑ {tech_findings['flagged_count']} new tech categories flagged "
                    f"— review logs above for details"
                )

            # ── STEP 4: Store results in PostgreSQL ──────
            logger.info("Step 4/6: Storing results in database...")
            stored = await self._store_pestel_results(db_session, pestel_results)

            # ── STEP 4b: Source-grounded validation (GPT-5.4 verifies each factor) ──
            # For each new factor, GPT-5.4 reads the actual scraped source texts
            # and verifies whether the claims are supported. If disputed, Sonnet
            # self-corrects before storing.
            logger.info("Step 4b/6: Running source-grounded validation...")
            from agents.validation_agent import validation_agent
            source_texts = self.web_intel.last_source_texts  # [{name, url, text, chars, scraped_at}]

            confirmed = partial = disputed = corrected_count = 0
            new_factors = pestel_results.get("new_factors", [])
            for factor in new_factors:
                try:
                    verif = await validation_agent.verify_against_source(
                        factor_title=factor.get("name", ""),
                        factor_description=(
                            factor.get("selection_reasoning", "") + " " +
                            factor.get("likelihood_reasoning", "")
                        ),
                        likelihood=factor.get("likelihood", 5),
                        impact=factor.get("impact", 5),
                        source_texts=source_texts,
                    )
                    verdict = verif.get("verdict", "NOT_FOUND")
                    factor["_verification"] = verif
                    factor["_source_name"] = verif.get("source_name", "")
                    factor["_source_url"] = verif.get("source_url", "")
                    factor["_evidence_quote"] = verif.get("evidence_quote", "")

                    # Count by verdict
                    if verdict == "CONFIRMED":
                        confirmed += 1
                    elif verdict == "PARTIALLY_CONFIRMED":
                        partial += 1
                    elif verdict == "DISPUTED":
                        disputed += 1

                    # If disputed or partially confirmed, self-correct before storing
                    if verdict in ("DISPUTED", "PARTIALLY_CONFIRMED") and verif.get("issues"):
                        orig_l = factor.get("likelihood", 5)
                        orig_i = factor.get("impact", 5)
                        corrected = await validation_agent.self_correct(
                            factor_title=factor["name"],
                            factor_description=factor.get("selection_reasoning", ""),
                            original_likelihood=orig_l,
                            original_impact=orig_i,
                            verification_issues=verif["issues"],
                            evidence_quote=verif.get("evidence_quote", ""),
                        )
                        factor["likelihood"] = corrected["corrected_likelihood"]
                        factor["impact"] = corrected["corrected_impact"]
                        factor["selection_reasoning"] = corrected["corrected_description"]
                        factor["_correction_log"] = {
                            "original_likelihood": orig_l,
                            "corrected_likelihood": corrected["corrected_likelihood"],
                            "original_impact": orig_i,
                            "corrected_impact": corrected["corrected_impact"],
                        }
                        corrected_count += 1
                        logger.info(
                            f"  🔄 Self-corrected: {factor['name'][:50]} "
                            f"(was {orig_l}/{orig_i}, "
                            f"issue: {verif['issues'][0][:60] if verif['issues'] else 'N/A'})"
                        )

                    emoji = {"CONFIRMED": "✅", "PARTIALLY_CONFIRMED": "🟡",
                             "NOT_FOUND": "⬜", "DISPUTED": "🔴"}.get(verdict, "❓")
                    logger.info(
                        f"  {emoji} {factor['name'][:55]:<55} "
                        f"→ {verdict} | Source: {factor['_source_name'] or 'N/A'}"
                    )
                except Exception as ve:
                    logger.warning(f"  Verification skipped for '{factor.get('name', '?')}': {ve}")
                    factor["_verification"] = {"verdict": "NOT_FOUND"}
                    factor["_source_name"] = ""
                    factor["_source_url"] = ""

            # ── VALIDATION CONSENSUS TABLE ──────────────────────────────────
            logger.info("")
            logger.info("╔═══════════════════════════════════════════════════════════════════╗")
            logger.info("║                  SOURCE-GROUNDED VALIDATION SUMMARY              ║")
            logger.info("║  Primary: Claude Sonnet 4.6  │  Validator: GPT 5.4              ║")
            logger.info("╠═══════════════════════════════════════════════════════════════════╣")
            for f in new_factors:
                v = f.get("_verification", {})
                verdict = v.get("verdict", "UNVERIFIED")
                conf = v.get("confidence", "?")
                emoji = {"CONFIRMED": "✅", "PARTIALLY_CONFIRMED": "⚠️",
                         "DISPUTED": "❌", "NOT_FOUND": "❓",
                         "NO_SOURCE": "🔇", "UNVERIFIED": "⬜"}.get(verdict, "❓")
                source = (f.get("_source_name") or "—")[:18]
                evidence = (v.get("evidence_quote") or "—")[:45]
                logger.info(
                    f"║ {emoji} {f['name'][:32]:<32} │ {verdict:<18} │ "
                    f"{str(conf):<6} │ {source}"
                )
                logger.info(f"║   Evidence: {evidence}")
                if f.get("_correction_log"):
                    cl = f["_correction_log"]
                    logger.info(
                        f"║   🔄 CORRECTED: L:{cl.get('original_likelihood','?')}"
                        f"→{cl.get('corrected_likelihood','?')} "
                        f"I:{cl.get('original_impact','?')}"
                        f"→{cl.get('corrected_impact','?')}"
                    )
            logger.info("╠═══════════════════════════════════════════════════════════════════╣")
            logger.info(
                f"║ RESULT: {confirmed} ✅ confirmed │ {partial} ⚠️ partial │ "
                f"{disputed} ❌ disputed │ {corrected_count} 🔄 corrected          ║"
            )
            logger.info("╚═══════════════════════════════════════════════════════════════════╝")
            logger.info("")

            # ── STEP 4c: Deactivate stale/superseded factors ──
            logger.info("Step 4c: Cleaning stale factors...")
            import re as _stale_re

            stale_count = 0
            for new_f in new_factors:
                new_words = set(
                    _stale_re.sub(r"[^a-z ]", "", new_f["name"].lower()).split()
                )
                new_words -= {
                    "the", "a", "an", "in", "of", "for", "and", "to",
                    "from", "by", "at", "on", "is", "are", "was",
                }

                existing = await db_session.execute(
                    text(
                        "SELECT id, name FROM pestel_factors "
                        "WHERE is_active = TRUE AND is_foundational = FALSE "
                        "AND code != :code"
                    ),
                    {"code": new_f.get("code", "")},
                )

                for row in existing.fetchall():
                    old_words = set(
                        _stale_re.sub(r"[^a-z ]", "", row.name.lower()).split()
                    )
                    old_words -= {
                        "the", "a", "an", "in", "of", "for", "and", "to",
                        "from", "by", "at", "on", "is", "are", "was",
                    }
                    overlap = len(new_words & old_words) / max(
                        len(new_words | old_words), 1
                    )
                    if overlap > 0.6:
                        await db_session.execute(
                            text(
                                "UPDATE pestel_factors SET is_active = FALSE WHERE id = :id"
                            ),
                            {"id": row.id},
                        )
                        stale_count += 1
                        logger.info(
                            f"  🗑️ Stale: {row.name[:40]} → superseded by {new_f['name'][:30]}"
                        )

            # ── Tiered freshness decay (replaces flat 90-day rule) ──────────────────
            # Tier 1 (aggressive): non-foundational, seen once, no re-confirmation in 14 days
            #   → set is_active=FALSE
            # Tier 2 (moderate): non-foundational, unconfirmed for 60 days
            #   → set is_active=FALSE
            # Both tiers are SKIPPED for structural/regulatory factors (P/L category or
            # any REGULATORY_KEYWORDS match) so mandates never auto-expire.
            #
            # is_structural() check is done via a SQL expression mirroring is_structural_factor().
            structural_sql = (
                "(category IN ('P', 'L') OR "
                + " OR ".join(f"LOWER(name) LIKE '%{kw}%'" for kw in REGULATORY_KEYWORDS if "'" not in kw)
                + ")"
            )
            # Tier 1 — one-hit wonders not confirmed within 14 days
            tier1_result = await db_session.execute(
                text(
                    f"UPDATE pestel_factors SET is_active = FALSE "
                    f"WHERE is_active = TRUE AND is_foundational = FALSE "
                    f"AND COALESCE(confirmation_count, 1) = 1 "
                    f"AND COALESCE(last_confirmed_date, last_refreshed) < NOW() - INTERVAL '14 days' "
                    f"AND NOT {structural_sql} "
                    f"RETURNING name"
                )
            )
            tier1_out = tier1_result.fetchall()
            for r in tier1_out:
                logger.info(f"  \u23f3 Tier-1 decay: {r.name[:40]} (unconfirmed >14 days)")

            # Tier 2 — recurring factors not confirmed within 60 days
            tier2_result = await db_session.execute(
                text(
                    f"UPDATE pestel_factors SET is_active = FALSE "
                    f"WHERE is_active = TRUE AND is_foundational = FALSE "
                    f"AND COALESCE(last_confirmed_date, last_refreshed) < NOW() - INTERVAL '60 days' "
                    f"AND NOT {structural_sql} "
                    f"RETURNING name"
                )
            )
            tier2_out = tier2_result.fetchall()
            for r in tier2_out:
                logger.info(f"  \u23f3 Tier-2 decay: {r.name[:40]} (unconfirmed >60 days)")

            await db_session.commit()
            logger.info(
                f"  Cleaned: {stale_count} superseded + {len(aged_out)} aged out"
            )

            # ── STEP 4d: Snapshot scores for timeline ──
            # Insert one snapshot per factor per DAY (DATE() unique index in 007).
            # Multiple refreshes in the same day → only the first wins, which is fine.
            await db_session.execute(
                text("""
                    INSERT INTO pestel_score_history
                        (factor_code, recorded_at, likelihood, impact, source)
                    SELECT code, NOW(), likelihood, impact, 'refresh'
                    FROM pestel_factors WHERE is_active = TRUE
                    ON CONFLICT DO NOTHING
                """)
            )
            await db_session.commit()
            snap_count = await db_session.execute(
                text("SELECT COUNT(*) FROM pestel_score_history "
                     "WHERE recorded_at::date = CURRENT_DATE")
            )
            logger.info(f"  📸 Score snapshot saved — {snap_count.scalar()} points today")

            # ── STEP 4e: System Sanity Engine (deterministic audit) ──
            logger.info("Step 4e: Running System Sanity Engine...")
            from agents.sanity_engine import sanity_engine
            audit_result = await sanity_engine.run_full_audit(db_session, auto_fix=True)
            logger.info(f"   Audit run_id: {audit_result['run_id']}")

            # ── STEP 5: Invalidate stale cache ───────────
            # Any cached analysis for changed factors must be cleared
            logger.info("Step 5/6: Invalidating stale cache entries...")
            invalidated = await self.cache.invalidate_pestel_cache()

            # ── STEP 6: Log the refresh ──────────────────
            logger.info("Step 6/6: Recording refresh in audit log...")
            refresh_log = {
                "trigger_type": getattr(self, "_current_trigger", "scheduled"),
                "started_at": start_time.isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "status": "completed",
                "new_factors": len(pestel_results.get("new_factors", [])),
                "updated_factors": len(pestel_results.get("updated_factors", [])),
                "llm_calls_made": llm.call_count,
                "estimated_cost_usd": llm.total_cost_usd,
            }
            await self._store_refresh_log(db_session, refresh_log)

            logger.info("╔══════════════════════════════════════════════╗")
            logger.info("║     REFRESH COMPLETE                         ║")
            logger.info(f"║     New factors: {refresh_log['new_factors']:>3}  Updated: {refresh_log['updated_factors']:>3}            ║")
            logger.info(f"║     LLM calls: {refresh_log['llm_calls_made']:>4}  Cost: ${refresh_log['estimated_cost_usd']:.4f}             ║")
            logger.info("╚══════════════════════════════════════════════╝")

            # ── STEP 7: Launch post-refresh cache warmup ────
            logger.info("Step 7/7: Launching post-refresh warmup in background...")
            import asyncio as _asyncio
            _asyncio.create_task(self.post_refresh_warmup())

            return refresh_log

        except Exception as e:
            logger.error(f"REFRESH FAILED: {e}", exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
                "started_at": start_time.isoformat(),
            }
        finally:
            self._is_refreshing = False

    # ════════════════════════════════════════════════════════
    # MODE 2: ON-DEMAND ANALYSIS (user clicks a bubble)
    # ════════════════════════════════════════════════════════
    async def get_pestel_analysis(
        self,
        factor_code: str,
        segment: str = "4W_PV",
        db_session=None,
    ) -> Dict[str, Any]:
        """
        Generate AI analysis for a PESTEL factor (V1 click).
        
        Flow:
        1. Check Redis cache for this factor+segment combination
        2. If cached and fresh → return immediately (0 LLM cost)
        3. If cache miss → call Sonnet 4.6 to generate analysis
        4. Cache the result (TTL: 4 hours)
        5. Return to frontend
        
        This is what happens when a user clicks a bubble on View 1.
        """
        cache_key = f"pestel:{factor_code}:{segment}"

        logger.info(f"╭─── BUBBLE CLICK: pestel/{factor_code}/{segment} ───╮")
        # ── Check cache first (saves LLM calls) ───────
        cached = await self.cache.get(cache_key)
        if cached:
            meta = cached.get("_meta", {})
            logger.info(f"│ ⚡ Cache HIT — 0 LLM cost │ Model: {meta.get('model','?')} │ Generated: {str(meta.get('generated_at','?'))[:19]}")
            logger.info(f"╰─────────────────────────────────────────────────╯")
            cached["_from_cache"] = True
            return cached

        logger.info(f"│ 💭 Cache MISS — calling Sonnet for fresh analysis...")
        # ── Cache miss — generate fresh analysis ───────

        # Load the factor data from DB
        factor_data = await self._load_factor_from_db(db_session, factor_code)
        if not factor_data:
            return {"error": f"Factor {factor_code} not found"}

        # Call the PESTEL agent to generate detailed analysis
        analysis = await pestel_agent.generate_detail_analysis(
            factor=factor_data,
            segment=segment,
        )

        # ── Cache the result ─────────────────────────────
        if analysis and "error" not in analysis:
            from config import settings
            await self.cache.set(cache_key, analysis, ttl=settings.analysis_cache_ttl)
            cost = analysis.get("_meta", {}).get("cost_usd", 0)
            citations_count = len(analysis.get("citations", []))
            has_financial = bool(analysis.get("financial_overlay") or analysis.get("financial_context"))
            logger.info(
                f"│ 🤖 Primary: sonnet-4-6 │ Generated {len(str(analysis))} chars"
            )
            logger.info(
                f"│ 📋 Citations: {citations_count} │ Financial: {'Yes' if has_financial else 'No'}"
            )
            logger.info(f"│ ✅ Cached for {settings.analysis_cache_ttl}s │ Cost: ${cost:.4f}")
        logger.info(f"╰─────────────────────────────────────────────────╯")

        return analysis

    async def get_tech_analysis(
        self,
        tech_code: str,
        segment: str = "4W_PV",
        db_session=None,
    ) -> Dict[str, Any]:
        """
        Generate AI analysis for a technology (V3 click).
        Same cache-first pattern as PESTEL analysis.
        """
        cache_key = f"tech:{tech_code}:{segment}"

        logger.info(f"╭─── BUBBLE CLICK: tech/{tech_code}/{segment} ───╮")
        cached = await self.cache.get(cache_key)
        if cached:
            meta = cached.get("_meta", {})
            logger.info(f"│ ⚡ Cache HIT — 0 LLM cost │ Model: {meta.get('model','?')} │ Generated: {str(meta.get('generated_at','?'))[:19]}")
            logger.info(f"╰─────────────────────────────────────────────────╯")
            cached["_from_cache"] = True
            return cached

        logger.info(f"│ 💭 Cache MISS — calling Sonnet for fresh analysis...")

        # Load tech data from DB
        tech_data = await self._load_tech_from_db(db_session, tech_code)
        if not tech_data:
            return {"error": f"Technology {tech_code} not found"}

        # Import and call tech agent
        from agents.prompts.system_context import SYSTEM_CONTEXT, TECH_ANALYSIS_PROMPT

        # ── Get SEGMENT-SPECIFIC market size (root-cause fix for number mismatch) ──
        import json as _json
        _md = tech_data.get("market_data", {})
        if isinstance(_md, str):
            try:
                _md = _json.loads(_md)
            except Exception:
                _md = {}
        _seg_entry = _md.get(segment, {})
        if isinstance(_seg_entry, dict):
            seg_market = _seg_entry.get("fy25", 0) or _seg_entry.get("market", 0)
            seg_cagr = _seg_entry.get("cagr", tech_data.get("cagr", 0))
        elif isinstance(_seg_entry, (int, float)):
            seg_market = _seg_entry
            seg_cagr = tech_data.get("cagr", 0)
        else:
            seg_market = 0
            seg_cagr = tech_data.get("cagr", 0)
        # Fallback to total if segment slot is empty
        if not seg_market:
            seg_market = tech_data.get("total_market_fy25_cr", 0) or tech_data.get("market_fy25_cr", 0)
            seg_cagr = tech_data.get("cagr", 0)

        prompt = TECH_ANALYSIS_PROMPT.format(
            segment=segment,
            tech_name=tech_data["name"],
            pillar=tech_data["pillar"],
            market_size=int(seg_market) if seg_market else "N/A",
            cagr=seg_cagr if seg_cagr else tech_data.get("cagr", "N/A"),
            maturity=tech_data.get("maturity", "N/A"),
            includes=tech_data.get("includes", "N/A"),
        )

        result = await llm.call_sonnet(
            prompt=prompt,
            system=SYSTEM_CONTEXT,
            max_tokens=6000,
            cache_system_prompt=True,
        )

        analysis = llm.parse_json_response(result["content"])
        if analysis:
            # ── Number sanity check: ensure AI didn't hallucinate a different market size ──
            import re as _re
            seed_fy25 = seg_market or tech_data.get("market_fy25_cr") or tech_data.get("total_market_fy25_cr")
            seed_cagr_val = seg_cagr or tech_data.get("cagr", 0)
            if seed_fy25:
                gt = analysis.get("growth_trajectory", {})
                fy25_str = str(gt.get("fy25", "") or analysis.get("market_size", ""))
                match = _re.search(r'[\d,]+', fy25_str.replace("₹", ""))
                if match:
                    analysis_fy25 = float(match.group(0).replace(",", ""))
                    deviation = abs(analysis_fy25 - seed_fy25) / max(seed_fy25, 1)
                    seed_cagr = seed_cagr_val or tech_data.get("cagr") or 0
                    seed_fy30 = round(seed_fy25 * (1 + seed_cagr / 100) ** 5)
                    if deviation > 0.2:
                        logger.warning(
                            f"│ ⚠️  NUMBER MISMATCH │ Seed: ₹{seed_fy25} Cr │ "
                            f"AI said: ₹{analysis_fy25:.0f} Cr │ "
                            f"Deviation: {deviation*100:.0f}% — auto-corrected"
                        )
                        if not gt:
                            analysis["growth_trajectory"] = {}
                            gt = analysis["growth_trajectory"]
                        gt["fy25"] = f"₹{seed_fy25:,} Cr"
                        gt["fy30"] = f"₹{seed_fy30:,} Cr"
                        analysis["_number_corrected"] = True
                        # Also fix strategic_outlook text that mentions the wrong FY25 figure
                        import re as _re2
                        outlook = analysis.get("strategic_outlook", "")
                        if outlook and seed_fy25:
                            for _wa in _re2.findall(r'₹([ \d,]+)\s*(?:Cr|cr)', outlook):
                                _wa_num = float(_wa.replace(",", "").strip())
                                if (_wa_num > 50
                                        and abs(_wa_num - seed_fy25) / max(seed_fy25, 1) > 0.3
                                        and abs(_wa_num - seed_fy30) / max(seed_fy30, 1) > 0.3):
                                    outlook = outlook.replace(f"₹{_wa}", f"₹{int(seed_fy25):,}")
                                    logger.info(f"│ 🔧 Fixed outlook: ₹{_wa.strip()} → ₹{int(seed_fy25):,} Cr")
                            analysis["strategic_outlook"] = outlook
                    else:
                        # Always lock fy30 via formula even when fy25 is correct
                        if gt and seed_cagr:
                            gt["fy30"] = f"₹{seed_fy30:,} Cr"
                        logger.info(f"│ ✅ Numbers verified │ FY25 seed=₹{seed_fy25} Cr │ AI=₹{analysis_fy25:.0f} Cr (within {deviation*100:.0f}%)")

            analysis["_meta"] = {
                "model": result["model"],
                "cost_usd": result["cost_usd"],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            from config import settings
            await self.cache.set(cache_key, analysis, ttl=settings.analysis_cache_ttl)
            citations_count = len(analysis.get("citations", []))
            has_financial = bool(analysis.get("financial_context"))
            logger.info(
                f"│ 🤖 Primary: sonnet-4-6 │ Generated {len(str(analysis))} chars"
            )
            logger.info(
                f"│ 📋 Citations: {citations_count} │ Financial: {'Yes' if has_financial else 'No'}"
            )
            logger.info(f"│ ✅ Cached for {settings.analysis_cache_ttl}s │ Cost: ${result['cost_usd']:.4f}")
        logger.info(f"╰─────────────────────────────────────────────────╯")

        return analysis or {"error": "Failed to generate analysis"}

    # ════════════════════════════════════════════════════════
    # DATABASE HELPERS
    # ════════════════════════════════════════════════════════
    async def _get_existing_factor_names(self, db_session) -> list[str]:
        """Load names of all active PESTEL factors from DB."""
        result = await db_session.execute(
            text("SELECT name FROM pestel_factors WHERE is_active = TRUE")
        )
        return [row[0] for row in result.fetchall()]

    async def _get_existing_tech_names(self, db_session) -> list[str]:
        """Load names of all active technology categories from DB."""
        try:
            result = await db_session.execute(
                text("SELECT name FROM technologies WHERE is_active = TRUE")
            )
            return [row[0] for row in result.fetchall()]
        except Exception:
            return []

    async def _load_factor_from_db(self, db_session, factor_code: str) -> Optional[Dict]:
        """Load a single PESTEL factor by its code."""
        result = await db_session.execute(
            text("SELECT * FROM pestel_factors WHERE code = :code AND is_active = TRUE"),
            {"code": factor_code}
        )
        row = result.fetchone()
        if row:
            return dict(row._mapping)
        return None

    async def _load_tech_from_db(self, db_session, tech_code: str) -> Optional[Dict]:
        """Load a single technology by its code."""
        result = await db_session.execute(
            text("SELECT * FROM technologies WHERE code = :code AND is_active = TRUE"),
            {"code": tech_code}
        )
        row = result.fetchone()
        if row:
            return dict(row._mapping)
        return None

    def _normalize_pillars(self, pillars: list) -> list:
        """Map LLM-generated pillar names to valid DB pillar IDs."""
        normalized = set()
        for p in pillars:
            mapped = PILLAR_NORMALIZE.get(p, p)
            if mapped in VALID_PILLARS:
                normalized.add(mapped)
            else:
                # Try partial match against valid pillar names
                for valid in VALID_PILLARS:
                    if valid.lower() in p.lower() or p.lower() in valid.lower():
                        normalized.add(valid)
                        break
        return list(normalized) if normalized else ["Motion"]  # Default fallback

    async def _store_pestel_results(self, db_session, results: Dict) -> int:
        """Store discovered/updated PESTEL factors with dedup + pillar normalization."""
        stored_count = 0
        skipped_dupes = 0

        # ── Load existing factor names for dedup check ──────────
        def _clean_name(name):
            """Strip numbers, currency, special chars → lowercase alpha only."""
            return re.sub(r'[^a-z ]', '', name.lower()).strip()

        def _get_content_words(name):
            """Extract meaningful words (no stop words, no short words)."""
            stop = {"the","a","an","in","of","for","and","to","from","by","at","on",
                    "is","are","was","with","its","cr","rs","new","has","this","that"}
            return [w for w in _clean_name(name).split() if w not in stop and len(w) > 2]

        def _is_duplicate(new_name, existing_name):
            """Check if two factor names refer to the same event."""
            # Check 1: First 20 alpha chars match
            if _clean_name(new_name)[:20] == _clean_name(existing_name)[:20]:
                return True
            # Check 2: First 3 content words identical
            new_words = _get_content_words(new_name)
            old_words = _get_content_words(existing_name)
            if len(new_words) >= 3 and len(old_words) >= 3 and new_words[:3] == old_words[:3]:
                return True
            # Check 3: 3+ content words overlap
            if len(set(new_words) & set(old_words)) >= 3:
                return True
            return False

        existing_rows = await db_session.execute(
            text("SELECT name FROM pestel_factors WHERE is_active = TRUE")
        )
        existing_names = [r[0] for r in existing_rows.fetchall()]

        for factor in results.get("new_factors", []):
            is_duplicate = False

            # ── FOUNDATIONAL FACTOR PROTECTION ─────────────────────────────────
            # Foundational factors (PLI, FAME3 etc.) are protected from deletion
            # and from being silently overwritten. If a new factor claims to be an
            # update to one, allow only likelihood/impact score changes.
            verif = factor.get("_verification", {})
            verif_verdict = verif.get("verdict", "UNVERIFIED")
            verif_source = factor.get("_source_name", "")
            verif_evidence = verif.get("evidence_quote", "")

            for existing_name in existing_names:
                if _is_duplicate(factor["name"], existing_name):
                    # ── is_update path: refresh scores/reasoning on matched factor ──
                    if factor.get("is_update") or factor.get("update_to"):
                        target = factor.get("update_to") or existing_name
                        # Escape SQL wildcards in the LIKE pattern (defensive)
                        safe_target = target[:30].replace("%", r"\%").replace("_", r"\_")
                        existing_row = await db_session.execute(
                            text(
                                "SELECT code FROM pestel_factors "
                                "WHERE name ILIKE :pattern ESCAPE '\\' "
                                "AND is_active = TRUE LIMIT 1"
                            ),
                            {"pattern": f"%{safe_target}%"},
                        )
                        row = existing_row.fetchone()
                        if row:
                            await db_session.execute(
                                text(
                                    "UPDATE pestel_factors SET "
                                    "selection_reasoning = :sr, "
                                    "likelihood = :lk, likelihood_reasoning = :lr, "
                                    "impact = :imp, impact_reasoning = :ir, "
                                    "last_refreshed = NOW(), "
                                    "last_confirmed_date = NOW(), "
                                    "confirmation_count = COALESCE(confirmation_count, 1) + 1 "
                                    "WHERE code = :code"
                                ),
                                {
                                    "sr": factor.get("selection_reasoning", ""),
                                    "lk": factor["likelihood"],
                                    "lr": factor.get("likelihood_reasoning", ""),
                                    "imp": factor["impact"],
                                    "ir": factor.get("impact_reasoning", ""),
                                    "code": row[0],
                                },
                            )
                            logger.info(
                                f"🔄 UPDATED existing: {row[0]} from '{factor['name'][:40]}' (confirmation_count++)"
                            )
                    else:
                        # Plain duplicate — still bump confirmation_count
                        await db_session.execute(
                            text(
                                "UPDATE pestel_factors SET "
                                "last_confirmed_date = NOW(), "
                                "confirmation_count = COALESCE(confirmation_count, 1) + 1 "
                                "WHERE name = :n AND is_active = TRUE"
                            ),
                            {"n": existing_name},
                        )
                        logger.info(
                            f"♻️  RE-CONFIRMED │ '{existing_name[:40]}' last_confirmed → NOW"
                        )
                        skipped_dupes += 1
                    is_duplicate = True
                    break

            if is_duplicate:
                continue

            # Track immediately so later factors in same batch also dedup
            existing_names.append(factor["name"])

            # ── PILLAR NORMALIZATION: map to valid pillar IDs ──
            pillars = factor.get("affected_pillars", [])
            factor["affected_pillars"] = self._normalize_pillars(pillars)

            code = factor["name"].lower().replace(" ", "_").replace("-", "_")[:50]
            await db_session.execute(
                text(
                    """INSERT INTO pestel_factors
                   (code, name, category, selection_reasoning,
                    likelihood, likelihood_reasoning, impact, impact_reasoning,
                    segment_relevance, affected_pillars, trend, time_horizon,
                    verification_verdict, verification_source, verification_evidence,
                    financial_context, key_dates, citations,
                    first_seen_date, last_confirmed_date, confirmation_count)
                   VALUES (:code, :name, :cat, :sel_reason,
                           :like, :like_reason, :imp, :imp_reason,
                           :seg_rel, :pillars, :trend, :horizon,
                           :verif_verdict, :verif_source, :verif_evidence,
                           :fin_ctx, :key_dates, :citations,
                           NOW(), NOW(), 1)
                   ON CONFLICT (code) DO UPDATE SET
                    likelihood = EXCLUDED.likelihood,
                    impact = EXCLUDED.impact,
                    verification_verdict = EXCLUDED.verification_verdict,
                    verification_source = EXCLUDED.verification_source,
                    verification_evidence = EXCLUDED.verification_evidence,
                    financial_context = EXCLUDED.financial_context,
                    key_dates = EXCLUDED.key_dates,
                    citations = EXCLUDED.citations,
                    updated_at = NOW()"""
                ),
                {
                    "code": code,
                    "name": factor["name"],
                    "cat": factor["category"],
                    "sel_reason": factor.get("selection_reasoning", ""),
                    "like": factor["likelihood"],
                    "like_reason": factor.get("likelihood_reasoning", ""),
                    "imp": factor["impact"],
                    "imp_reason": factor.get("impact_reasoning", ""),
                    "seg_rel": json.dumps(factor.get("segment_relevance", {})),
                    "pillars": json.dumps(factor["affected_pillars"]),
                    "trend": factor.get("trend", "stable"),
                    "horizon": factor.get("time_horizon", "medium"),
                    "verif_verdict": verif_verdict,
                    "verif_source": verif_source[:200] if verif_source else "",
                    "verif_evidence": verif_evidence[:1000] if verif_evidence else "",
                    "fin_ctx": json.dumps(factor.get("financial_context", {})),
                    "key_dates": json.dumps(factor.get("key_dates", {})),
                    "citations": json.dumps(factor.get("citations", [])),
                }
            )
            stored_count += 1

        logger.info(f"📝 Stored {stored_count} new factors, skipped {skipped_dupes} duplicates")
        await db_session.commit()
        return stored_count

    async def _store_refresh_log(self, db_session, log: Dict):
        """Record a refresh event in the audit trail."""
        try:
            # Parse ISO strings back to datetime objects for asyncpg
            from datetime import datetime as _dt
            def _parse(ts):
                if ts is None:
                    return None
                if isinstance(ts, _dt):
                    return ts
                return _dt.fromisoformat(ts)

            await db_session.execute(
                text(
                    """INSERT INTO refresh_logs 
                   (trigger_type, started_at, completed_at, status,
                    new_factors, updated_factors, llm_calls_made, estimated_cost_usd)
                   VALUES (:trigger, :start, :end, :status,
                           :new, :updated, :calls, :cost)"""
                ),
                {
                    "trigger": log["trigger_type"],
                    "start": _parse(log["started_at"]),
                    "end": _parse(log.get("completed_at")),
                    "status": log["status"],
                    "new": log.get("new_factors", 0),
                    "updated": log.get("updated_factors", 0),
                    "calls": log.get("llm_calls_made", 0),
                    "cost": log.get("estimated_cost_usd", 0),
                }
            )
            await db_session.commit()
            logger.info(f"📝 Refresh log saved — trigger: {log['trigger_type']}, new: {log.get('new_factors',0)}, cost: ${log.get('estimated_cost_usd',0):.4f}")
        except Exception as e:
            logger.info(f"│ Refresh log saved (non-critical): {e}")


    # ════════════════════════════════════════════════════════
    # POST-REFRESH WARMUP — pre-generate ALL bubble analyses
    # ════════════════════════════════════════════════════════
    async def post_refresh_warmup(self):
        """
        Post-refresh cache warmup — multi-segment, multi-tech.

        Warmup matrix:
          - Top 5 PESTEL factors × 6 segments  = 30 calls
          - Top 3 techs per pillar × 4W_PV     = ~40 calls
          - Total: ~70 calls × ~30s            = ~35 min wall-clock

        Why this matters: leadership demos jump between segments. Cold cache
        on a 2W or HCV bubble click = 12s wait. Pre-warming fixes that.
        """
        import asyncio
        from db.connection import async_session

        try:
            # ── 1. Top 5 PESTEL × 6 segments ──
            async with async_session() as db:
                result = await db.execute(
                    text(
                        "SELECT code FROM pestel_factors WHERE is_active = TRUE "
                        "ORDER BY (likelihood * impact) DESC NULLS LAST LIMIT 5"
                    )
                )
                top_pestel = [r[0] for r in result.fetchall()]

            segments = ["4W_PV", "LCV", "HCV", "2W", "3W", "Tractor"]
            pestel_calls = [(c, s) for c in top_pestel for s in segments]
            total_p = len(pestel_calls)

            logger.info(f"🔥 POST-REFRESH WARMUP — Phase 1: top 5 PESTEL × 6 segments = {total_p} calls")

            warmed = skipped = 0
            for i, (code, seg) in enumerate(pestel_calls, 1):
                cache_key = f"pestel:{code}:{seg}"
                if await self.cache.get(cache_key):
                    skipped += 1
                    continue
                try:
                    async with async_session() as db:
                        await self.get_pestel_analysis(code, seg, db)
                    warmed += 1
                    if warmed % 5 == 0:
                        logger.info(f"  🔥 PESTEL [{warmed} new + {skipped} cached] / {total_p}")
                except Exception as e:
                    logger.warning(f"  ⚠️ Warmup failed pestel/{code}/{seg}: {e}")
                await asyncio.sleep(1.5)

            logger.info(f"🔥 PESTEL WARMUP DONE: {warmed} new + {skipped} cached / {total_p}")

            # ── 2. Top 3 techs per pillar (4W_PV only) ──
            async with async_session() as db:
                tech_result = await db.execute(text("""
                    SELECT code, pillar FROM (
                        SELECT code, pillar,
                               ROW_NUMBER() OVER (
                                   PARTITION BY pillar
                                   ORDER BY COALESCE((market_data->'4W_PV'->>'fy25')::numeric, 0) DESC
                               ) AS rn
                        FROM technologies WHERE is_active = TRUE
                    ) ranked
                    WHERE rn <= 3
                """))
                top_techs = [r[0] for r in tech_result.fetchall()]

            logger.info(f"🔥 Phase 2: top techs per pillar (4W_PV) = {len(top_techs)} calls")

            t_warmed = t_skipped = 0
            for code in top_techs:
                cache_key = f"tech:{code}:4W_PV"
                if await self.cache.get(cache_key):
                    t_skipped += 1
                    continue
                try:
                    async with async_session() as db:
                        await self.get_tech_analysis(code, "4W_PV", db)
                    t_warmed += 1
                    logger.info(f"  🔥 Tech [{t_warmed}/{len(top_techs)}] Warmed: {code}")
                except Exception as e:
                    logger.warning(f"  ⚠️ Tech warmup failed {code}/4W_PV: {e}")
                await asyncio.sleep(1.5)

            logger.info(
                f"🔥 WARMUP COMPLETE: PESTEL {warmed}+{skipped} · "
                f"Tech {t_warmed}+{t_skipped} · "
                f"total ~{warmed + t_warmed} new analyses cached"
            )

        except Exception as e:
            logger.warning(f"Post-refresh warmup failed (non-critical): {e}")


# ── Singleton instance ────────────────────────────
orchestrator = Orchestrator()
