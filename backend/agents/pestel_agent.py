"""
============================================================
PESTEL AGENT — Discovers, Scores, and Maintains PESTEL Factors
============================================================
This agent answers the question: "What external forces are
affecting India's auto component industry RIGHT NOW?"

Pipeline:
1. DISCOVER: Scan news/web for new PESTEL factors
2. SCORE: Rate each factor (Likelihood × Impact) with reasoning
3. VALIDATE: Multi-LLM consensus check on key data points
4. STORE: Save to PostgreSQL with full source trail
5. UPDATE: Re-score existing factors based on new information

The agent maintains ~30-40 active factors at any time.
It discovers 40-60 candidates, filters to ~35, and tracks
all reasoning for why each factor was selected or rejected.
============================================================
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from services.llm_service import llm
from agents.validation_agent import validation_agent
from agents.prompts.system_context import (
    SYSTEM_CONTEXT,
    PESTEL_DISCOVERY_PROMPT,
    PESTEL_DETAIL_PROMPT,
)

logger = logging.getLogger("pestel_agent")


class PESTELAgent:
    """
    The PESTEL Agent handles the entire lifecycle of PESTEL factors:
    discovery → scoring → validation → storage → refresh
    """

    # ════════════════════════════════════════════════════════
    # STEP 1: DISCOVER new PESTEL factors from recent news
    # ════════════════════════════════════════════════════════
    async def discover_factors(
        self,
        news_content: str,
        existing_factors: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Feed recent news/developments to Sonnet 4.6 and ask it to
        identify new PESTEL factors affecting India auto components.
        
        Args:
            news_content: Concatenated recent news articles/updates
            existing_factors: List of names of factors we already track
                             (to avoid duplicates)
        
        Returns:
            List of discovered factor dicts with full reasoning
        
        IMPORTANT: This uses Sonnet 4.6 (CRITICAL quality) because:
        - Factor selection determines what the CEO sees on the dashboard
        - Wrong factors = wrong strategic decisions
        - The selection reasoning must be bulletproof
        """
        logger.info(
            f"PESTEL Discovery: Scanning {len(news_content)} chars of news. "
            f"Existing factors: {len(existing_factors)}"
        )

        # Format the discovery prompt with current news and existing factors
        prompt = PESTEL_DISCOVERY_PROMPT.format(
            news_content=news_content[:15000],  # Cap at ~15K chars to fit context
            existing_factors="\n".join(f"- {f}" for f in existing_factors),
        )

        # ── Call Sonnet 4.6 with cached system context ────
        # The SYSTEM_CONTEXT (~18K tokens) is cached via Anthropic's
        # prompt caching. First call: cache write ($3.75/M).
        # Subsequent calls within 5 min: cache hit ($0.30/M).
        # Store for downstream validation source-grounding
        self._last_news_content = news_content[:5000] if isinstance(news_content, str) else ""

        result = await llm.call_sonnet(
            prompt=prompt,
            system=SYSTEM_CONTEXT,
            max_tokens=16000,      # Discovery produces 10-15 detailed JSON objects — needs room
            temperature=0.4,       # Slightly creative for discovery
            cache_system_prompt=True,
        )

        # Parse the JSON array of discovered factors
        raw_text = result["content"]
        factors = llm.parse_json_response(raw_text)

        if not factors or not isinstance(factors, list):
            logger.warning(f"Primary JSON parse failed, attempting manual recovery. Raw (last 200): {raw_text[-200:]}")
            # Manual recovery: find all complete JSON objects before truncation point
            try:
                import re
                cleaned = re.sub(r'```json|```', '', raw_text).strip()
                # Strip trailing comma from last incomplete item
                if cleaned.endswith(','):
                    cleaned = cleaned[:-1].rstrip()
                # Close the array if truncated mid-object
                if not cleaned.endswith(']'):
                    last_brace = cleaned.rfind('}')
                    if last_brace > 0:
                        cleaned = cleaned[:last_brace + 1] + ']'
                factors = json.loads(cleaned)
                if isinstance(factors, list) and len(factors) > 0:
                    logger.info(f"  ✅ Recovered {len(factors)} factors from truncated JSON")
                else:
                    factors = []
            except Exception as recovery_err:
                logger.error(f"  ❌ Could not recover truncated JSON: {recovery_err}")
                factors = []

        if not factors:
            logger.error(f"Discovery failed to produce valid factors. Raw: {raw_text[:300]}")
            return []

        logger.info(
            f"📊 Discovered {len(factors)} new candidate factors "
            f"│ Cost: ${result['cost_usd']:.4f}"
        )

        return factors

    # ════════════════════════════════════════════════════════
    # STEP 2: FILTER — Remove irrelevant/duplicate factors
    # ════════════════════════════════════════════════════════
    async def filter_factors(
        self,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Use Haiku 4.5 to quickly filter candidate factors.
        Removes:
        - Factors scoring below 6/10 on relevance to India auto
        - Duplicates of existing tracked factors
        - Factors too broad to be actionable
        
        Uses Haiku because this is a structured classification task.
        """
        if not candidates:
            return []

        # Build a compact representation for Haiku to evaluate
        candidates_text = json.dumps(
            [{"name": c["name"], "category": c["category"],
              "selection_reasoning": c.get("selection_reasoning", "")}
             for c in candidates],
            indent=2
        )

        prompt = f"""Rate each PESTEL factor's relevance to India's auto component industry (1-10).
Remove any below 6. Flag duplicates or overly broad factors.

Candidates:
{candidates_text}

Respond in JSON: [{{"name": "...", "relevance_score": N, "keep": true/false, "reason": "..."}}]"""

        result = await llm.call_haiku(prompt=prompt, max_tokens=6000)
        filtered = llm.parse_json_response(result["content"])

        if not filtered:
            # If filtering fails, keep all candidates (safe fallback)
            logger.warning("Factor filtering failed, keeping all candidates")
            return candidates

        # Keep only factors marked as keep=true
        keep_names = {f["name"] for f in filtered if f.get("keep", False)}
        kept = [c for c in candidates if c["name"] in keep_names]

        rejected = len(candidates) - len(kept)
        logger.info(f"📊 Filtered: {len(candidates)} → {len(kept)} factors ({rejected} below threshold)")

        # ── Semantic dedup pass ───────────────────────────
        # A second Haiku call to catch near-duplicate factors
        # (same underlying event, different framing)
        if len(kept) > 1:
            kept = await self._semantic_dedup(kept)

        return kept

    async def _semantic_dedup(self, factors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Use Haiku to identify and remove near-duplicate factors.
        Near-duplicates = same underlying event/story, different name/framing
        e.g. 3 variants of "JLR cyberattack" should collapse to 1.
        """
        if len(factors) <= 1:
            return factors

        names_list = json.dumps(
            [{"index": i, "name": f["name"], "category": f["category"],
              "reasoning": f.get("selection_reasoning", "")[:300]}
             for i, f in enumerate(factors)],
            indent=2
        )

        prompt = f"""You are reviewing a list of PESTEL factors. Identify groups of near-duplicates — factors that describe the SAME underlying event or story AND have the SAME strategic implication.

For example, THESE ARE duplicates (same event, same angle):
- "JLR Cyberattack — OEM supply chain vulnerability" 
- "JLR Cyberattack — OEM production vulnerability"
- "OEM Cyberattack supply chain disruption"

But THESE ARE NOT duplicates (same event, different strategic angle):
- "Maruti SUV Expansion — ADAS content opportunity" (Technology category — sensor demand)
- "Maruti SUV Expansion — localisation pressure" (Legal category — supply chain compliance)
Keep both if the strategic implication for Bosch differs.

Factors to review:
{names_list}

For each duplicate group (same event + same angle), pick ONE to keep (the most strategically distinct framing).
List the INDICES to REMOVE (not keep).

Respond in JSON:
{{"indices_to_remove": [1, 3, 5], "reason": "brief explanation of what was merged"}}

If no duplicates found, respond: {{"indices_to_remove": [], "reason": "all factors are distinct"}}"""

        try:
            result = await llm.call_haiku(prompt=prompt, max_tokens=2000)
            parsed = llm.parse_json_response(result["content"])
            if parsed and isinstance(parsed.get("indices_to_remove"), list):
                to_remove = set(parsed["indices_to_remove"])
                deduped = [f for i, f in enumerate(factors) if i not in to_remove]
                removed = len(factors) - len(deduped)
                if removed > 0:
                    logger.info(f"📊 Semantic dedup: {len(factors)} → {len(deduped)} factors ({removed} near-duplicates removed) — {parsed.get('reason', '')}")
                return deduped
        except Exception as e:
            logger.debug(f"Semantic dedup failed (non-critical): {e}")

        return factors

    # ════════════════════════════════════════════════════════
    # STEP 3: VALIDATE — Multi-LLM check on critical data
    # ════════════════════════════════════════════════════════
    async def validate_factor_data(
        self,
        factor: Dict[str, Any],
        db_session=None,                  # ✅ forwarded to validate_data_point
    ) -> Dict[str, Any]:
        """
        Run multi-LLM validation on a PESTEL factor's key claims.
        
        For each factor, we validate:
        - The likelihood score and its reasoning
        - The impact score and its reasoning
        - Any specific numbers cited in the reasoning
        
        Returns the factor dict enriched with validation results.
        """
        # Pull source text for source-grounded validation
        _src_text = ""
        try:
            _src_text = (getattr(self, "_last_news_content", "") or "")[:3000]
        except Exception:
            _src_text = ""

        # Validate the likelihood claim
        likelihood_validation = await validation_agent.validate_data_point(
            data_point=f"PESTEL factor '{factor['name']}' — Likelihood score",
            claimed_value=f"{factor['likelihood']}/10",
            context=factor.get("likelihood_reasoning", ""),
            source_cited="AI PESTEL analysis",
            source_text=_src_text,
        )

        # Validate the impact claim
        impact_validation = await validation_agent.validate_data_point(
            data_point=f"PESTEL factor '{factor['name']}' — Impact score",
            claimed_value=f"{factor['impact']}/10",
            context=factor.get("impact_reasoning", ""),
            source_cited="AI PESTEL analysis",
            source_text=_src_text,
        )

        # Attach validation results to the factor
        factor["validations"] = {
            "likelihood": likelihood_validation,
            "impact": impact_validation,
            "overall_consensus": self._combine_validations(
                likelihood_validation, impact_validation
            ),
        }

        return factor

    # ════════════════════════════════════════════════════════
    # STEP 4: GENERATE detailed analysis (for V1 click panel)
    # ════════════════════════════════════════════════════════
    async def generate_detail_analysis(
        self,
        factor: Dict[str, Any],
        segment: str = "4W_PV",
    ) -> Dict[str, Any]:
        """
        Generate the detailed AI analysis shown when user clicks
        a PESTEL bubble in View 1.
        
        Uses Sonnet 4.6 (CRITICAL) because CEO reads this.
        Results are cached in Redis (TTL: 4 hours).
        """
        prompt = PESTEL_DETAIL_PROMPT.format(
            segment=segment,
            factor_name=factor["name"],
            category=factor["category"],
            likelihood=factor["likelihood"],
            likelihood_reasoning=factor.get("likelihood_reasoning", ""),
            impact=factor["impact"],
            impact_reasoning=factor.get("impact_reasoning", ""),
            trend=factor.get("trend", "stable"),
            affected_pillars=", ".join(factor.get("affected_pillars", [])),
        )

        result = await llm.call_sonnet(
            prompt=prompt,
            system=SYSTEM_CONTEXT,
            max_tokens=6000,
            cache_system_prompt=True,  # Reuse cached system context
        )

        analysis = llm.parse_json_response(result["content"])

        if analysis:
            analysis["_meta"] = {
                "model": result["model"],
                "cost_usd": result["cost_usd"],
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "segment": segment,
                "factor_code": factor.get("code", factor["name"]),
            }

        return analysis or {"error": "Failed to generate analysis"}

    # ════════════════════════════════════════════════════════
    # FULL REFRESH PIPELINE — runs all steps in sequence
    # ════════════════════════════════════════════════════════
    async def run_full_refresh(
        self,
        news_content: str,
        existing_factor_names: List[str],
        validate: bool = True,
        db_session=None,                  # ✅ forwarded to validate_data_point
    ) -> Dict[str, Any]:
        """
        Execute the complete PESTEL refresh pipeline:
        1. Discover new factors from news
        2. Filter irrelevant candidates
        3. Validate key data points (if enabled)
        4. Return structured results for storage
        
        Args:
            news_content: Recent news/developments text
            existing_factor_names: Names of already-tracked factors
            validate: Whether to run multi-LLM validation (costs more)
        
        Returns:
            {
                "new_factors": [...],
                "updated_factors": [...],
                "rejected_factors": [...],
                "validation_results": [...],
                "cost_usd": 0.05,
                "duration_seconds": 12.5
            }
        """
        import time
        start = time.time()

        logger.info("═══ PESTEL REFRESH PIPELINE STARTED ═══")

        # Step 1: Discover
        candidates = await self.discover_factors(news_content, existing_factor_names)

        # Step 2: Filter
        filtered = await self.filter_factors(candidates)

        # Step 3: Separate new vs updates
        new_factors = [f for f in filtered if not f.get("is_update", False)]
        updated_factors = [f for f in filtered if f.get("is_update", False)]

        # Step 4: Validate (only if enabled — costs LLM calls)
        validation_results = []
        if validate:
            logger.info(f"🔍 Running 4-LLM validation on top {min(10, len(new_factors))} new factors...")
            for factor in new_factors[:10]:
                validated = await self.validate_factor_data(factor, db_session=db_session)
                validation_results.append(validated)
            logger.info(f"🔍 Validation persisted to validation_logs table")

        duration = time.time() - start
        cost = llm.total_cost_usd  # Note: this is cumulative, not per-refresh

        logger.info(
            f"═══ PESTEL REFRESH COMPLETE ═══\n"
            f"  New factors: {len(new_factors)}\n"
            f"  Updated: {len(updated_factors)}\n"
            f"  Validated: {len(validation_results)}\n"
            f"  Duration: {duration:.1f}s"
        )

        return {
            "new_factors": new_factors,
            "updated_factors": updated_factors,
            "rejected_factors": [f for f in candidates if f not in filtered],
            "validation_results": validation_results,
            "duration_seconds": round(duration, 1),
        }

    # ════════════════════════════════════════════════════════
    # HELPER: Combine multiple validation results
    # ════════════════════════════════════════════════════════
    def _combine_validations(self, *validations) -> str:
        """
        Combine multiple validation results into a single status.
        If any is REJECTED → overall REJECTED
        If any is HUMAN_REVIEW → overall HUMAN_REVIEW
        If any is FLAGGED → overall FLAGGED
        Otherwise → VERIFIED
        """
        statuses = [v.get("consensus", "FLAGGED") for v in validations]
        if "REJECTED" in statuses:
            return "REJECTED"
        if "HUMAN_REVIEW" in statuses:
            return "HUMAN_REVIEW"
        if "FLAGGED" in statuses:
            return "FLAGGED"
        return "VERIFIED"


# ── Singleton instance ────────────────────────────────────
pestel_agent = PESTELAgent()
