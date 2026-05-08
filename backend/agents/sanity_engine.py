"""
============================================================
SANITY ENGINE — Deterministic system-wide audit
============================================================
Runs after every refresh. Catches:
  L1: Tech-segment exclusion violations  (ADAS L3 in 2W, etc.)
  L2: Numeric / structural sanity        (CAGR > 100%, market > industry)
  L3: Cross-view consistency             (V3 tech without V4 players, etc.)
  L4: Source-grounded LLM verification   (already in validation_agent)

Findings are written to system_audit_logs. Severity ERROR findings can be
auto-fixed (e.g., zero out wrong tech-segment market data).
============================================================
"""

import logging
import uuid
import json
from datetime import datetime, timezone
from typing import Dict, Any

from sqlalchemy import text

logger = logging.getLogger("sanity_engine")


SEGMENTS = ["4W_PV", "LCV", "HCV", "2W", "3W", "Tractor"]

# Industry totals (FY25, ₹ Cr) — used for upper-bound sanity
SEGMENT_INDUSTRY_TOTAL = {
    "4W_PV": 280000,    # ~₹2.8L Cr addressable PV component market
    "LCV":    65000,
    "HCV":    85000,
    "2W":     95000,
    "3W":     12000,
    "Tractor": 40000,
}


class SanityEngine:

    async def run_full_audit(self, db_session, auto_fix: bool = True) -> Dict[str, Any]:
        """
        Execute all three deterministic sanity layers. Returns summary + run_id.
        """
        run_id = (
            f"audit_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            f"_{uuid.uuid4().hex[:6]}"
        )
        logger.info("╔══════════════════════════════════════════════╗")
        logger.info(f"║  SANITY ENGINE — run_id: {run_id:<24}║")
        logger.info("╚══════════════════════════════════════════════╝")

        findings: Dict[str, int] = {"info": 0, "warn": 0, "error": 0, "fixed": 0}

        for layer_fn in (
            self._layer1_tech_segment_exclusions,
            self._layer2_numeric_sanity,
            self._layer3_cross_view,
        ):
            layer_args = (db_session, run_id, auto_fix) if layer_fn != self._layer3_cross_view else (db_session, run_id)
            result = await layer_fn(*layer_args)
            for k, v in result.items():
                findings[k] = findings.get(k, 0) + v

        await db_session.commit()

        logger.info("┌──────────────────────────────────────────────┐")
        logger.info("│  SANITY AUDIT COMPLETE                        │")
        logger.info(f"│  INFO:  {findings['info']:>4}                                  │")
        logger.info(f"│  WARN:  {findings['warn']:>4}                                  │")
        logger.info(f"│  ERROR: {findings['error']:>4}                                  │")
        logger.info(f"│  AUTO-FIXED: {findings['fixed']:>4}                              │")
        logger.info("└──────────────────────────────────────────────┘")
        return {"run_id": run_id, **findings}

    # ────────────────────────────────────────────────────────
    # LAYER 1: Tech-segment exclusions
    # ────────────────────────────────────────────────────────
    async def _layer1_tech_segment_exclusions(self, db, run_id, auto_fix):
        """
        Find techs with non-zero market_data for excluded segments.
        Auto-fix: zero out the offending segment in market_data JSON.
        """
        rules = await db.execute(text(
            "SELECT tech_pattern, excluded_segment, reason FROM tech_segment_exclusions"
        ))
        rule_list = rules.fetchall()

        techs = await db.execute(text(
            "SELECT id, code, name, market_data FROM technologies WHERE is_active = TRUE"
        ))
        tech_list = techs.fetchall()

        info = warn = err = fixed = 0

        for tech in tech_list:
            md = tech.market_data
            if isinstance(md, str):
                try:
                    md = json.loads(md)
                except Exception:
                    md = {}
            md = md or {}

            tech_name_lower = (tech.name or "").lower()
            for rule in rule_list:
                if rule.tech_pattern.lower() in tech_name_lower:
                    seg = rule.excluded_segment
                    seg_data = md.get(seg)
                    if isinstance(seg_data, dict) and (seg_data.get("fy25") or 0) > 0:
                        msg = (
                            f"Tech '{tech.name}' has ₹{seg_data['fy25']} Cr in {seg} "
                            f"but rule says: {rule.reason}"
                        )
                        await self._log(db, run_id, "tech_segment_exclusion",
                                        "ERROR", "technology", tech.code, seg,
                                        msg, auto_fixed=auto_fix)
                        err += 1
                        if auto_fix:
                            md[seg] = {"fy25": 0, "fy30": 0, "cagr": 0}
                            await db.execute(
                                text("UPDATE technologies SET market_data = :m WHERE id = :i"),
                                {"m": json.dumps(md), "i": tech.id},
                            )
                            fixed += 1

        return {"info": info, "warn": warn, "error": err, "fixed": fixed}

    # ────────────────────────────────────────────────────────
    # LAYER 2: Numeric sanity
    # ────────────────────────────────────────────────────────
    async def _layer2_numeric_sanity(self, db, run_id, auto_fix):
        """
        - Segment FY25 > 50% of segment industry total → WARN
        - CAGR < -50 or > 80 → WARN
        - Pillar not in canonical 13 → ERROR
        """
        VALID_PILLARS = {
            "ADAS", "Motion", "Energy", "Body & Comfort", "Infotainment",
            "OS", "Compute", "ECUs", "Semiconductors", "Actuators",
            "Solutions", "Services", "Cloud",
        }

        info = warn = err = fixed = 0

        techs = await db.execute(text(
            "SELECT id, code, name, pillar, market_data, cagr "
            "FROM technologies WHERE is_active = TRUE"
        ))
        for tech in techs.fetchall():
            # Pillar check
            if tech.pillar not in VALID_PILLARS:
                await self._log(db, run_id, "invalid_pillar", "ERROR",
                                "technology", tech.code, None,
                                f"Tech '{tech.name}' has pillar '{tech.pillar}' "
                                f"not in canonical 13 pillars")
                err += 1

            md = tech.market_data
            if isinstance(md, str):
                try:
                    md = json.loads(md)
                except Exception:
                    md = {}
            md = md or {}

            for seg in SEGMENTS:
                seg_data = md.get(seg, {})
                if not isinstance(seg_data, dict):
                    continue
                fy25 = seg_data.get("fy25", 0) or 0
                cagr = seg_data.get("cagr", 0) or 0

                ind_max = SEGMENT_INDUSTRY_TOTAL.get(seg, 1_000_000)
                if fy25 > ind_max * 0.5:
                    await self._log(db, run_id, "implausible_market_size", "WARN",
                                    "technology", tech.code, seg,
                                    f"Tech '{tech.name}' claims ₹{fy25} Cr in {seg} "
                                    f"but segment industry is ~₹{ind_max} Cr — implausible")
                    warn += 1
                if cagr > 80 or cagr < -50:
                    await self._log(db, run_id, "implausible_cagr", "WARN",
                                    "technology", tech.code, seg,
                                    f"Tech '{tech.name}' has CAGR {cagr}% in {seg} — "
                                    f"outside reasonable bounds")
                    warn += 1

        # Top-level CAGR also
        techs2 = await db.execute(text(
            "SELECT code, name, cagr FROM technologies WHERE is_active = TRUE"
        ))
        for t in techs2.fetchall():
            if (t.cagr or 0) > 80 or (t.cagr or 0) < -50:
                await self._log(db, run_id, "implausible_cagr_top", "WARN",
                                "technology", t.code, None,
                                f"Tech '{t.name}' top-level CAGR is {t.cagr}%")
                warn += 1

        return {"info": info, "warn": warn, "error": err, "fixed": fixed}

    # ────────────────────────────────────────────────────────
    # LAYER 3: Cross-view consistency
    # ────────────────────────────────────────────────────────
    async def _layer3_cross_view(self, db, run_id):
        """
        Check: every tech with market data should have at least one competitor
        share row, otherwise V4 will show "no players" while V3 shows market.
        Also validates PESTEL pillar references against the canonical 13.
        """
        info = warn = err = fixed = 0

        VALID_PILLARS = {
            "ADAS", "Motion", "Energy", "Body & Comfort", "Infotainment",
            "OS", "Compute", "ECUs", "Semiconductors", "Actuators",
            "Solutions", "Services", "Cloud",
        }

        # V3↔V4 player gap
        gaps = await db.execute(text("""
            SELECT t.code, t.name, t.pillar
            FROM technologies t
            WHERE t.is_active = TRUE
              AND COALESCE(t.total_market_fy25_cr, 0) > 0
              AND NOT EXISTS (
                  SELECT 1 FROM competitor_tech_shares cts
                  WHERE cts.tech_code = t.code
              )
            LIMIT 100
        """))
        for r in gaps.fetchall():
            await self._log(db, run_id, "v3_v4_player_gap", "WARN",
                            "technology", r.code, None,
                            f"Tech '{r.name}' ({r.pillar}) has market in V3 "
                            f"but no competitor rows — V4 will show no players")
            warn += 1

        # PESTEL invalid pillar references
        pestels = await db.execute(text(
            "SELECT code, name, affected_pillars FROM pestel_factors WHERE is_active = TRUE"
        ))
        for p in pestels.fetchall():
            ap = p.affected_pillars
            if isinstance(ap, str):
                try:
                    ap = json.loads(ap)
                except Exception:
                    ap = []
            ap = ap or []
            for pillar in ap:
                if pillar not in VALID_PILLARS:
                    await self._log(db, run_id, "pestel_invalid_pillar", "WARN",
                                    "pestel_factor", p.code, None,
                                    f"PESTEL '{p.name}' references invalid pillar '{pillar}'")
                    warn += 1

        return {"info": info, "warn": warn, "error": err, "fixed": fixed}

    # ────────────────────────────────────────────────────────
    # Helpers
    # ────────────────────────────────────────────────────────
    async def _log(self, db, run_id, check_name, severity, etype, ecode,
                   eseg, msg, auto_fixed=False):
        await db.execute(
            text("""
                INSERT INTO system_audit_logs
                    (run_id, check_name, severity, entity_type, entity_code,
                     entity_segment, message, auto_fixed)
                VALUES (:r, :c, :s, :et, :ec, :es, :m, :f)
            """),
            {
                "r": run_id, "c": check_name, "s": severity, "et": etype,
                "ec": ecode, "es": eseg, "m": msg, "f": auto_fixed,
            },
        )
        emoji = {"INFO": "ℹ️", "WARN": "⚠️", "ERROR": "❌"}.get(severity, "?")
        logger.info(f"   {emoji} {check_name} · {ecode or '-'} · {msg[:80]}")


sanity_engine = SanityEngine()
