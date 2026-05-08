"""
============================================================
TECH AGENT — Technology Category Discovery
============================================================
Lightweight scan for new emerging technology categories
not yet tracked in the mobility intelligence platform.

Uses Claude Haiku for cost efficiency (this is a scout task,
not a CRITICAL analysis task).

IMPORTANT: Does NOT auto-add categories to the database.
All findings are flagged for manual analyst review.
============================================================
"""

import logging
from typing import Dict, Any, List

from services.llm_service import llm

logger = logging.getLogger("tech_agent")


_TECH_SCAN_PROMPT = """You are a technology intelligence analyst for the automotive and mobility sector.

Below is recent industry news content. The existing tracked technology categories in our platform are:
{existing_techs}

Your task: Identify any GENUINELY NEW technology categories that appear prominently in the news but are NOT already tracked in the list above.

Rules:
- Only flag truly new categories, not minor variations of existing ones
- Focus on automotive/mobility-relevant technologies only
- Must appear meaningfully in multiple news items to be worth flagging
- Do NOT suggest sub-categories of already-tracked items

Return JSON only (no markdown fences):
{{
    "new_categories": [
        {{
            "name": "Technology Category Name",
            "description": "1-2 sentence description from news context",
            "news_evidence": "Brief quote or paraphrase from news showing this is emerging",
            "suggested_cagr_range": "X%-Y% or null"
        }}
    ],
    "updated_cagr_hints": [
        {{
            "existing_category": "Exact name from the tracked list above",
            "new_cagr_hint": "X%-Y%",
            "source_note": "Where this figure was mentioned"
        }}
    ],
    "scan_summary": "One sentence summary of the tech landscape from this news batch"
}}

News content:
{news_content}
"""


class TechAgent:
    """
    Lightweight technology category discovery agent.
    Runs as part of the nightly refresh pipeline to surface new tech trends.
    All findings require manual analyst review before being added to the DB.
    """

    async def check_for_new_technologies(
        self,
        news_content: str,
        existing_techs: List[str],
    ) -> Dict[str, Any]:
        """
        Scan news for technology categories not yet tracked in the platform.

        Args:
            news_content: Aggregated news text from web intelligence service
            existing_techs: List of technology category names currently in DB

        Returns:
            {
                "new_categories": [...],        # flagged for manual review
                "updated_cagr_hints": [...],    # updated CAGR estimates for existing techs
                "scan_summary": "...",
                "flagged_count": 3,
                "cagr_hints_count": 2,
                "cost_usd": 0.0012,
            }
        """
        if not news_content or not news_content.strip():
            logger.info("🔬 TECH SCAN │ No news content — scan skipped")
            return {
                "new_categories": [], "updated_cagr_hints": [],
                "scan_summary": "No news content", "flagged_count": 0,
                "cagr_hints_count": 0, "cost_usd": 0.0,
            }

        # Truncate news to keep cost low — Haiku is cheap but let's be efficient
        news_snippet = news_content[:8000] if len(news_content) > 8000 else news_content
        existing_list = (
            "\n".join(f"  • {t}" for t in existing_techs)
            if existing_techs
            else "  (no categories tracked yet)"
        )

        prompt = _TECH_SCAN_PROMPT.format(
            existing_techs=existing_list,
            news_content=news_snippet,
        )

        try:
            result = await llm.call_haiku(prompt, max_tokens=1500)
            parsed = llm.parse_json_response(result["content"])

            if not parsed:
                logger.warning("🔬 TECH SCAN │ Could not parse Haiku response")
                return {
                    "new_categories": [], "updated_cagr_hints": [],
                    "scan_summary": "Parse failed", "flagged_count": 0,
                    "cagr_hints_count": 0, "cost_usd": result.get("cost_usd", 0.0),
                }

            new_cats = parsed.get("new_categories", [])
            cagr_hints = parsed.get("updated_cagr_hints", [])
            summary = parsed.get("scan_summary", "")

            logger.info(
                f"🔬 TECH SCAN │ {len(new_cats)} potential new categories │ "
                f"{len(cagr_hints)} CAGR updates │ Cost: ${result['cost_usd']:.4f} │ "
                f"Summary: {summary[:120]}"
            )

            # Log each flagged category so analysts can see them in the terminal
            for cat in new_cats:
                logger.info(
                    f"  ⚑ FLAG FOR REVIEW: {cat.get('name', '?')} — "
                    f"{cat.get('description', '')[:100]} "
                    f"[CAGR hint: {cat.get('suggested_cagr_range', 'n/a')}]"
                )

            return {
                "new_categories": new_cats,
                "updated_cagr_hints": cagr_hints,
                "scan_summary": summary,
                "flagged_count": len(new_cats),
                "cagr_hints_count": len(cagr_hints),
                "cost_usd": result["cost_usd"],
            }

        except Exception as e:
            logger.error(f"🔬 TECH SCAN │ Failed: {e}")
            return {
                "new_categories": [], "updated_cagr_hints": [],
                "scan_summary": f"Error: {e}", "flagged_count": 0,
                "cagr_hints_count": 0, "cost_usd": 0.0,
            }


# ── Singleton instance — import this everywhere ──
tech_agent = TechAgent()
