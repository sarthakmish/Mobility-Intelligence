"""
============================================================
SOURCE TRACKER — Provenance Chain for Every Data Point
============================================================
Every number, every PESTEL factor, every market size in the
platform traces back to a source. This service manages that chain.

When a user clicks "Source trail" on any data point, they see:
  → Primary source: ACMA FY2025 Annual Report (acma.in/reports)
  → Extracted: 16-Mar-2026 14:30 UTC
  → Verified by: Claude Sonnet 4.6 (CONFIRMED, HIGH)
  → Cross-checked: Claude Haiku 4.5 (CONFIRMED, HIGH)
  → Consensus: VERIFIED ✅

Even estimated values have a trail:
  → Estimate basis: FY24 value ($21.2B) × 8% SIAM growth forecast
  → Estimated by: Claude Sonnet 4.6
  → Cross-checked: Claude Haiku 4.5
  → Consensus: FLAGGED ⚠️ (estimate, not official figure)
============================================================
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List

from sqlalchemy import text

logger = logging.getLogger("source_tracker")


class SourceTracker:
    """
    Manages source provenance for all data in the platform.
    Every piece of data gets a source record in the sources table.
    """

    async def create_source(
        self,
        db_session,
        name: str,
        url: Optional[str] = None,
        source_type: str = "llm_estimate",
        reliability: str = "medium",
        raw_excerpt: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> int:
        """
        Create a source record and return its ID.
        
        Source types:
        - "official_report": ACMA/SIAM/IBEF published reports
        - "government": MoRTH notifications, ministry press releases
        - "news": ET Auto, Livemint, Moneycontrol articles
        - "llm_estimate": Value estimated by AI (clearly marked)
        - "derived": Calculated from other verified sources
        
        Reliability levels:
        - "high": Official published data from ACMA, SIAM, government
        - "medium": Reputable news sources, analyst estimates
        - "low": Single unverified source, older data, LLM estimates
        """
        result = await db_session.execute(
            text(
                """INSERT INTO sources (name, url, source_type, reliability, 
                                    raw_excerpt, notes, accessed_at)
               VALUES (:name, :url, :type, :rel, :excerpt, :notes, :accessed)
               RETURNING id"""
            ),
            {
                "name": name,
                "url": url,
                "type": source_type,
                "rel": reliability,
                "excerpt": raw_excerpt[:2000] if raw_excerpt else None,
                "notes": notes,
                "accessed": datetime.now(timezone.utc),
            }
        )
        source_id = result.scalar()
        await db_session.commit()
        
        logger.info(
            f"Source created: #{source_id} '{name}' "
            f"(type={source_type}, reliability={reliability})"
        )
        return source_id

    async def get_source_trail(
        self,
        db_session,
        source_ids: List[int],
    ) -> List[Dict]:
        """
        Get full source details for a list of source IDs.
        Used when rendering the "Source trail" panel in the UI.
        """
        if not source_ids:
            return []
        
        result = await db_session.execute(
            text("SELECT * FROM sources WHERE id = ANY(:ids) ORDER BY accessed_at DESC"),
            {"ids": source_ids}
        )
        return [dict(r._mapping) for r in result.fetchall()]

    async def attach_sources_to_factor(
        self,
        db_session,
        factor_id: int,
        source_ids: List[int],
    ):
        """Link source records to a PESTEL factor."""
        await db_session.execute(
            text(
                """UPDATE pestel_factors 
               SET source_ids = source_ids || :new_ids
               WHERE id = :fid"""
            ),
            {"new_ids": source_ids, "fid": factor_id}
        )
        await db_session.commit()

    async def attach_sources_to_tech(
        self,
        db_session,
        tech_id: int,
        source_ids: List[int],
    ):
        """Link source records to a technology."""
        await db_session.execute(
            text(
                """UPDATE technologies 
               SET source_ids = source_ids || :new_ids
               WHERE id = :tid"""
            ),
            {"new_ids": source_ids, "tid": tech_id}
        )
        await db_session.commit()


# ── Singleton ─────────────────────────────────────────────
source_tracker = SourceTracker()
