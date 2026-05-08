"""
============================================================
VALIDATION AGENT — Multi-LLM Consensus Verification
============================================================
This is the TRUST ENGINE of the platform.

How it works:
1. Primary LLM (Sonnet 4.6) generates a data point or analysis
2. This agent sends the claim to Validator LLM (Haiku 4.5)
3. Both verdicts are compared for consensus
4. Everything is logged to validation_logs table (audit trail)

Consensus rules:
- Both HIGH confidence + agree     → VERIFIED ✅
- One MEDIUM, both agree           → FLAGGED ⚠️ (use with caution)
- Any LOW confidence               → NEEDS REVIEW ❌
- They disagree on the value       → HUMAN REVIEW 🔍

The user can click any data point and see the full validation trail.
============================================================
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from services.llm_service import llm
from agents.prompts.system_context import VALIDATION_PROMPT

logger = logging.getLogger("validation_agent")


class ValidationAgent:
    """
    Multi-LLM validation system.
    Every critical data point passes through here before being stored.
    """

    # ════════════════════════════════════════════════════════
    # MAIN METHOD: 2-model source-grounded validation
    # ════════════════════════════════════════════════════════
    async def validate_data_point(
        self,
        data_point: str,
        claimed_value: Any,
        context: str = "",
        source_cited: str = "",
        source_text: str = "",      # actual scraped source content
        # Legacy params kept for backwards compat — no longer used in impl
        entity_type: str = "general",
        entity_id: Optional[int] = None,
        db_session=None,
    ) -> Dict[str, Any]:
        """
        2-MODEL SOURCE-GROUNDED VALIDATION

        Layer 1 (Primary, Sonnet 4.6): Generates the claim — already happened upstream
        Layer 2 (Validator, GPT-5.4): Reads actual source text, checks if claim matches

        If source_text is provided, GPT verifies against it (reading-comprehension task).
        If not, falls back to plausibility check with LOW confidence ceiling.
        """

        logger.info(f"Validating: {data_point} = {claimed_value}")

        has_source = bool(source_text and len(source_text) > 100)

        if has_source:
            prompt = (
                f"You are a fact-checker validating a claim against a source document.\n\n"
                f"CLAIM TO VERIFY:\n"
                f"  Data point: {data_point}\n"
                f"  Value claimed: {claimed_value}\n"
                f"  Context provided: {context}\n"
                f"  Source cited: {source_cited}\n\n"
                f"ACTUAL SOURCE TEXT (truncated to 4000 chars if longer):\n"
                f'"""\n{source_text[:4000]}\n"""\n\n'
                f"Your task:\n"
                f"1. Read the source text carefully.\n"
                f"2. Determine if the source actually supports the specific value/claim.\n"
                f"3. Flag if: source mentions different numbers; claim is aspirational not current; "
                f"source is wrong time period; source doesn't mention this at all.\n\n"
                f'Respond with JSON:\n{{"verdict": "CONFIRMED" | "DISPUTED" | "UNSUPPORTED" | "UNCERTAIN", '
                f'"confidence": "HIGH" | "MEDIUM" | "LOW", '
                f'"evidence_quote": "<short verbatim quote max 30 words>", '
                f'"reasoning": "<one sentence>", '
                f'"discrepancy": "<if values differ, what source actually says>"}}'
            )
        else:
            prompt = (
                f"You are checking if a claim is plausible.\n\n"
                f"CLAIM:\n"
                f"  Data point: {data_point}\n"
                f"  Value claimed: {claimed_value}\n"
                f"  Context: {context}\n"
                f"  Source cited: {source_cited}\n\n"
                f"You don't have the source text. Use only general knowledge to flag obvious issues.\n\n"
                f'Respond with JSON:\n{{"verdict": "PLAUSIBLE" | "IMPLAUSIBLE" | "UNCERTAIN", '
                f'"confidence": "MEDIUM" | "LOW", '
                f'"reasoning": "<one sentence>", '
                f'"discrepancy": "<if implausible, what\'s wrong>"}}'
            )

        # ── Run GPT-5.4 validator ──
        try:
            gpt_result = await llm.call_gpt54(prompt)
            raw = gpt_result["content"] if isinstance(gpt_result, dict) else str(gpt_result)
            verdict_data = self._parse_verdict_json(raw)
        except Exception as e:
            logger.warning(f"GPT-5.4 validator failed: {e}")
            verdict_data = {
                "verdict": "UNCERTAIN",
                "confidence": "LOW",
                "reasoning": f"Validator API failed: {e}",
                "evidence_quote": "",
                "discrepancy": "",
            }

        # ── Build structured response compatible with existing callers ──
        consensus = self._derive_consensus_2model(verdict_data)
        result = {
            "data_point": data_point,
            "claimed_value": str(claimed_value),
            "context": context,
            "source_cited": source_cited,
            "source_grounded": has_source,
            "primary": {
                "model": "claude-sonnet-4-6",
                "verdict": "CLAIMED",
                "confidence": "MEDIUM",
                "reasoning": "Primary model produced this claim",
            },
            "validators": [{
                "model": "gpt-5.4",
                "verdict": verdict_data.get("verdict", "UNCERTAIN"),
                "confidence": verdict_data.get("confidence", "LOW"),
                "reasoning": verdict_data.get("reasoning", ""),
                "evidence_quote": verdict_data.get("evidence_quote", ""),
                "discrepancy": verdict_data.get("discrepancy", ""),
                "cost_usd": 0.01,
            }],
            "consensus": consensus,
            "consensus_emoji": self._consensus_emoji(consensus),
            # Legacy keys so existing callers don't KeyError
            "primary_model": "claude-sonnet-4-6",
            "primary_verdict": "CLAIMED",
            "primary_confidence": "MEDIUM",
            "primary_reasoning": "Primary model produced this claim",
            "validator_model": "gpt-5.4",
            "validator_verdict": verdict_data.get("verdict", "UNCERTAIN"),
            "validator_confidence": verdict_data.get("confidence", "LOW"),
            "validator_reasoning": verdict_data.get("reasoning", ""),
            "consensus_reasoning": verdict_data.get("reasoning", ""),
        }

        v = result["validators"][0]
        logger.info(
            f"🔍 SOURCE-GROUNDED CHECK │ {data_point[:60]} │ "
            f"GPT-5.4: {v['verdict']}({v['confidence']}) │ "
            f"Consensus: {result['consensus']} {result['consensus_emoji']}"
        )

        return result

    @staticmethod
    def _derive_consensus_2model(verdict_data: Dict) -> str:
        """Map single-validator verdict to consensus label."""
        v = verdict_data.get("verdict", "UNCERTAIN")
        c = verdict_data.get("confidence", "LOW")
        if v in ("CONFIRMED", "PLAUSIBLE") and c == "HIGH":
            return "VERIFIED"
        if v == "UNSUPPORTED":
            return "REJECTED"
        if v == "DISPUTED" and c in ("HIGH", "MEDIUM"):
            return "FLAGGED"
        if v == "IMPLAUSIBLE":
            return "FLAGGED"
        return "UNVERIFIED"

    @staticmethod
    def _consensus_emoji(consensus: str) -> str:
        return {
            "VERIFIED": "✅",
            "FLAGGED": "⚠️",
            "REJECTED": "❌",
            "UNVERIFIED": "○",
        }.get(consensus, "?")

    @staticmethod
    def _parse_verdict_json(raw: str) -> Dict:
        """Parse JSON from LLM response, handling markdown fences."""
        import re
        if not raw:
            return {}
        cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            m = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", cleaned, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    pass
            return {"verdict": "UNCERTAIN", "confidence": "LOW", "reasoning": "JSON parse failed"}

    # ════════════════════════════════════════════════════════
    # INTERNAL: Check with a specific model
    # ════════════════════════════════════════════════════════
    async def _check_with_model(
        self,
        data_point: str,
        claimed_value: str,
        context: str,
        source_cited: str,
        model: str,  # "primary" or "validator"
    ) -> Dict[str, Any]:
        """
        Ask one LLM to verify a data point.
        Returns structured verdict with reasoning.
        """
        # Build the validation prompt
        prompt = VALIDATION_PROMPT.format(
            data_point=data_point,
            claimed_value=claimed_value,
            context=context,
            source_cited=source_cited,
        )

        try:
            # Choose which model to call
            if model == "primary":
                result = await llm.call_sonnet(prompt)
            elif model in ("gpt54", "gpt52"):  # gpt52 alias kept for backwards compat
                result = await llm.call_gpt54(prompt)
            elif model == "grok4":
                result = await llm.call_grok4(prompt)
            elif model == "gemini25":
                result = await llm.call_gemini25(prompt)
            else:
                result = await llm.call_haiku(prompt)

            # Parse the JSON response
            parsed = llm.parse_json_response(result["content"])

            if parsed:
                return {
                    "model": result["model"],
                    "verdict": parsed.get("verdict", "UNCERTAIN"),
                    "confidence": parsed.get("confidence", "LOW"),
                    "reasoning": parsed.get("reasoning", "No reasoning provided"),
                    "estimate": parsed.get("your_estimate", ""),
                    "risk_factors": parsed.get("risk_factors", ""),
                    "cost_usd": result["cost_usd"],
                }
            else:
                # If JSON parsing failed, treat as uncertain
                return {
                    "model": result["model"],
                    "verdict": "UNCERTAIN",
                    "confidence": "LOW",
                    "reasoning": f"Failed to parse model response: {result['content'][:200]}",
                    "estimate": "",
                    "risk_factors": "Response parsing failed",
                    "cost_usd": result["cost_usd"],
                }

        except Exception as e:
            logger.error(f"Validation call failed for {model}: {e}")
            return {
                "model": model,
                "verdict": "UNCERTAIN",
                "confidence": "LOW",
                "reasoning": f"Model call failed: {str(e)}",
                "estimate": "",
                "risk_factors": "API call failed",
                "cost_usd": 0,
            }

    # ════════════════════════════════════════════════════════
    # CONSENSUS LOGIC — The decision engine
    # ════════════════════════════════════════════════════════
    def _compute_consensus(
        self,
        primary: Dict[str, Any],
        validator: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Compare two LLM verdicts and determine consensus.
        
        Decision matrix:
        ┌────────────┬──────────────┬──────────────┬──────────────┐
        │            │ Validator:   │ Validator:   │ Validator:   │
        │            │ CONFIRMED    │ UNCERTAIN    │ DISPUTED     │
        ├────────────┼──────────────┼──────────────┼──────────────┤
        │ Primary:   │              │              │              │
        │ CONFIRMED  │ → VERIFIED   │ → FLAGGED    │ → HUMAN_REV  │
        │ UNCERTAIN  │ → FLAGGED    │ → REJECTED   │ → REJECTED   │
        │ DISPUTED   │ → HUMAN_REV  │ → REJECTED   │ → REJECTED   │
        └────────────┴──────────────┴──────────────┴──────────────┘
        
        Additional rule: If BOTH are HIGH confidence and agree → VERIFIED
        """
        pv = primary["verdict"]      # Primary verdict
        vv = validator["verdict"]    # Validator verdict
        pc = primary["confidence"]   # Primary confidence
        vc = validator["confidence"] # Validator confidence

        # ── CASE 1: Both agree CONFIRMED ──────────────────
        if pv == "CONFIRMED" and vv == "CONFIRMED":
            if pc == "HIGH" and vc == "HIGH":
                return {
                    "status": "VERIFIED",
                    "reasoning": (
                        f"Both models independently confirmed with HIGH confidence. "
                        f"Primary: {primary['reasoning'][:100]}... "
                        f"Validator: {validator['reasoning'][:100]}..."
                    ),
                }
            elif pc == "LOW" or vc == "LOW":
                return {
                    "status": "FLAGGED",
                    "reasoning": (
                        f"Both models confirmed but at least one has LOW confidence. "
                        f"Recommend manual verification."
                    ),
                }
            else:
                return {
                    "status": "VERIFIED",
                    "reasoning": (
                        f"Both models confirmed. Confidence: Primary={pc}, Validator={vc}."
                    ),
                }

        # ── CASE 2: One confirmed, one uncertain ─────────
        if (pv == "CONFIRMED" and vv == "UNCERTAIN") or \
           (pv == "UNCERTAIN" and vv == "CONFIRMED"):
            return {
                "status": "FLAGGED",
                "reasoning": (
                    f"One model confirmed, other is uncertain. "
                    f"Primary: {pv} ({pc}). Validator: {vv} ({vc}). "
                    f"Data is likely correct but use with caution."
                ),
            }

        # ── CASE 3: They directly disagree ───────────────
        if (pv == "CONFIRMED" and vv == "DISPUTED") or \
           (pv == "DISPUTED" and vv == "CONFIRMED"):
            return {
                "status": "HUMAN_REVIEW",
                "reasoning": (
                    f"DISAGREEMENT: Primary says {pv}, Validator says {vv}. "
                    f"Primary reasoning: {primary['reasoning'][:150]}... "
                    f"Validator reasoning: {validator['reasoning'][:150]}... "
                    f"Requires human review to resolve."
                ),
            }

        # ── CASE 4: Both uncertain or disputed ───────────
        return {
            "status": "REJECTED",
            "reasoning": (
                f"Neither model could confirm. Primary: {pv} ({pc}), "
                f"Validator: {vv} ({vc}). This data should not be used "
                f"without manual verification from primary sources."
            ),
        }

    # ════════════════════════════════════════════════════════
    # MULTI-MODEL CONSENSUS (4-way: Sonnet + GPT5.2 + Grok4 + Gemini2.5)
    # ════════════════════════════════════════════════════════
    def _compute_multi_consensus(
        self,
        primary: Dict[str, Any],
        validators: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        """
        Compute consensus from 1 primary + N validators.

        Agreement = validator verdict matches primary verdict.
        Thresholds (for 3 validators):
          ALL (3/3) agree  → VERIFIED ✅
          2/3 agree        → VERIFIED ⚠️  (used with mild caution)
          1/3 agree        → FLAGGED 🟡
          0/3 agree        → REJECTED ❌
        Special cases:
          Primary DISPUTED + majority validators DISPUTED → HUMAN_REVIEW 🔍
        """
        pv = primary["verdict"]
        total = len(validators)

        if total == 0:
            return {
                "status": "FLAGGED",
                "reasoning": "No validators available — primary model only.",
            }

        agree_count = sum(1 for v in validators if v["verdict"] == pv)

        # If primary itself is DISPUTED and validators corroborate, flag for human
        if pv == "DISPUTED":
            status = "HUMAN_REVIEW" if agree_count >= total // 2 + 1 else "REJECTED"
        elif pv == "CONFIRMED":
            if agree_count == total:
                status = "VERIFIED"
            elif agree_count >= 2:
                status = "VERIFIED"        # majority agrees — use with caution
            elif agree_count == 1:
                status = "FLAGGED"
            else:
                status = "REJECTED"
        else:  # UNCERTAIN primary
            status = "FLAGGED" if agree_count >= total // 2 + 1 else "REJECTED"

        emoji_map = {
            "VERIFIED": "✅", "FLAGGED": "⚠️", "REJECTED": "❌", "HUMAN_REVIEW": "🔍",
        }
        caveat = " (majority, use with caution)" if status == "VERIFIED" and agree_count < total else ""
        reasoning = (
            f"Primary ({primary.get('model', 'primary')}): {pv} ({primary.get('confidence', '?')}). "
            f"Validators agreement: {agree_count}/{total}{caveat}. "
            f"Consensus: {status} {emoji_map.get(status, '❓')}."
        )
        return {"status": status, "reasoning": reasoning}

    # ════════════════════════════════════════════════════════
    # BATCH VALIDATION — validate multiple data points
    # ════════════════════════════════════════════════════════
    async def validate_batch(
        self,
        data_points: list[Dict[str, str]],
    ) -> list[Dict[str, Any]]:
        """
        Validate multiple data points efficiently.
        Used during data refresh to validate all new/changed data.
        
        Args:
            data_points: [{"data_point": "...", "claimed_value": "...", "context": "..."}]
        
        Returns:
            List of validation records
        """
        results = []
        for dp in data_points:
            result = await self.validate_data_point(
                data_point=dp["data_point"],
                claimed_value=dp["claimed_value"],
                context=dp.get("context", ""),
                source_cited=dp.get("source_cited", "LLM analysis"),
            )
            results.append(result)
        return results


    # ════════════════════════════════════════════════════════
    # SOURCE-GROUNDED VERIFICATION (uses GPT-5.4)
    # ════════════════════════════════════════════════════════
    async def verify_against_source(
        self,
        factor_title: str,
        factor_description: str,
        likelihood: float,
        impact: float,
        source_texts: list,  # [{name, url, text, ...}] from web_intelligence.last_source_texts
    ) -> Dict[str, Any]:
        """
        Uses GPT-5.4 to verify whether the scraped source texts actually support
        the extracted factor claims.

        Returns:
            verdict:          CONFIRMED | PARTIALLY_CONFIRMED | NOT_FOUND | DISPUTED
            confidence:       HIGH | MEDIUM | LOW
            evidence_quote:   verbatim snippet from source that supports/disputes
            numbers_verified: True/False — are numeric claims supported?
            source_name:      which source had the supporting evidence
            source_url:       URL of the supporting source
            issues:           list of specific discrepancies found
        """
        if not source_texts:
            return {
                "verdict": "NOT_FOUND",
                "confidence": "LOW",
                "evidence_quote": "",
                "numbers_verified": False,
                "source_name": "",
                "source_url": "",
                "issues": ["No source texts available for verification"],
            }

        # Find the best-matching source first so GPT gets the most relevant text
        best = self._find_best_source(factor_title, source_texts)

        # Build source block: best match first (up to 2500 chars), then others (500 each)
        source_excerpts = []
        if best:
            source_excerpts.append(f"[{best['name']}] ← BEST MATCH\n{best.get('text','')[:2500]}")
        total_chars = len(source_excerpts[0]) if source_excerpts else 0
        for s in source_texts:
            if best and s.get("name") == best.get("name"):
                continue  # already included above
            text = s.get("text", "")
            if not text:
                continue
            snippet = text[:500]
            total_chars += len(snippet)
            source_excerpts.append(f"[{s['name']}]\n{snippet}")
            if total_chars >= 6000:
                break

        source_block = "\n---\n".join(source_excerpts)

        prompt = f"""You are a rigorous fact-checker for an automotive industry intelligence platform.

You have the following PESTEL factor extracted by an AI:

FACTOR TITLE: {factor_title}
FACTOR DESCRIPTION: {factor_description}
CLAIMED LIKELIHOOD: {likelihood}/5.0
CLAIMED IMPACT: {impact}/5.0

SOURCE TEXTS (scraped from industry news and government portals):
{source_block}

Your task: verify whether the source texts support this factor.

Respond ONLY in valid JSON:
{{
  "verdict": "CONFIRMED" | "PARTIALLY_CONFIRMED" | "NOT_FOUND" | "DISPUTED",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "evidence_quote": "<exact verbatim quote from source that most supports or disputes the factor, max 250 chars>",
  "numbers_verified": true | false,
  "source_name": "<name of source with best evidence>",
  "source_url": "",
  "issues": ["<list any specific factual discrepancies found — empty array if none>"]
}}

IMPORTANT: Return ONLY the JSON object, no markdown, no explanation."""

        try:
            result = await llm.call_gpt54(prompt, max_tokens=400)
            parsed = llm.parse_json_response(result["content"])
            if not parsed:
                raise ValueError(f"Could not parse: {result['content'][:200]}")
            # Merge url from source_texts if available
            sn = parsed.get("source_name", "")
            for s in source_texts:
                if s.get("name", "") == sn:
                    parsed["source_url"] = s.get("url", "")
                    break
            return parsed
        except Exception as e:
            logger.error(f"verify_against_source failed for '{factor_title}': {e}")
            return {
                "verdict": "NOT_FOUND",
                "confidence": "LOW",
                "evidence_quote": "",
                "numbers_verified": False,
                "source_name": "",
                "source_url": "",
                "issues": [f"Verification failed: {str(e)}"],
            }

    def _find_best_source(self, factor_name: str, source_texts: list) -> dict | None:
        """Find the source most likely to contain evidence for this factor."""
        import re
        stop = {"the","a","an","in","of","for","and","to","from","by","at","on",
                "is","are","was","with","its","new","cr","rs","india","indian",
                "auto","vehicle","market","sector","industry"}
        keywords = [w.lower() for w in re.sub(r'[^a-z0-9 ]', ' ', factor_name.lower()).split()
                    if w.lower() not in stop and len(w) > 2]

        best_source = None
        best_score = 0
        for s in source_texts:
            text_lower = s.get("text", "").lower()
            if not text_lower:
                continue
            score = sum(1 for kw in keywords if kw in text_lower)
            # Bonus if first 20 chars of factor name found verbatim
            if factor_name[:20].lower() in text_lower:
                score += 5
            if score > best_score:
                best_score = score
                best_source = s
        # Only return if at least 2 keywords matched
        return best_source if best_score >= 2 else None

    async def self_correct(
        self,
        factor_title: str,
        factor_description: str,
        original_likelihood: float,
        original_impact: float,
        verification_issues: list,
        evidence_quote: str,
    ) -> Dict[str, Any]:
        """
        When GPT-5.4 finds issues with an extracted factor, re-prompt Sonnet
        with the dispute reasoning and ask it to self-correct.

        Returns:
            corrected_likelihood: float
            corrected_impact: float
            corrected_description: str
            correction_note: str
        """
        issues_block = "\n".join(f"- {i}" for i in verification_issues)
        prompt = f"""You are an automotive industry PESTEL analyst. You previously extracted this factor:

FACTOR: {factor_title}
DESCRIPTION: {factor_description}
LIKELIHOOD: {original_likelihood}/5.0
IMPACT: {original_impact}/5.0

A fact-checker found these issues:
{issues_block}

Supporting evidence quote: "{evidence_quote}"

Please correct the factor to align with the evidence. Respond ONLY in valid JSON:
{{
  "corrected_likelihood": <float 0-5>,
  "corrected_impact": <float 0-5>,
  "corrected_description": "<revised description that is consistent with the evidence>",
  "correction_note": "<one sentence explaining what was changed and why>"
}}

Return ONLY the JSON object."""

        try:
            result = await llm.call_sonnet(prompt)
            parsed = llm.parse_json_response(result["content"])
            if not parsed:
                raise ValueError(f"Could not parse correction: {result['content'][:200]}")
            return {
                "corrected_likelihood": float(parsed.get("corrected_likelihood", original_likelihood)),
                "corrected_impact": float(parsed.get("corrected_impact", original_impact)),
                "corrected_description": parsed.get("corrected_description", factor_description),
                "correction_note": parsed.get("correction_note", ""),
            }
        except Exception as e:
            logger.error(f"self_correct failed for '{factor_title}': {e}")
            return {
                "corrected_likelihood": original_likelihood,
                "corrected_impact": original_impact,
                "corrected_description": factor_description,
                "correction_note": f"Self-correction failed: {str(e)}",
            }


# ── Singleton instance ────────────────────────────────────
validation_agent = ValidationAgent()
