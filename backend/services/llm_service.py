"""
============================================================
LLM SERVICE — Unified Client for All LLM API Calls
============================================================
This is the SINGLE entry point for all LLM calls in the system.
Handles:
  - Claude Sonnet 4.6 (CRITICAL tasks: analysis, reports)
  - Claude Haiku 4.5 (HIGH tasks: validation, scoring)
  - GPT-5 mini (VOLUME tasks: sentiment, batch)
  - Embeddings (text-embedding-3-small)
  
Features:
  - Automatic retry with exponential backoff
  - Prompt caching (saves ~$15-20/month)
  - Model fallback if primary is unavailable
  - Cost tracking per call
  - Full request/response logging
============================================================
"""

import json
import time
import logging
from typing import Optional, Dict, Any, List

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import settings

logger = logging.getLogger("llm_service")


# ────────────────────────────────────────────────────────────
# COST TRACKING — logs every LLM call's estimated cost
# This data feeds into the monthly cost dashboard
# ────────────────────────────────────────────────────────────
PRICING = {
    # Model name → (input $/M tokens, output $/M tokens)
    "claude-sonnet-4-6":  (3.00, 15.00),
    "claude-sonnet-4-5":  (3.00, 15.00),   # fallback — same price
    "claude-haiku-4-5":   (1.00, 5.00),
    "claude-3-5-haiku":   (0.80, 4.00),    # fallback for Haiku
    "gpt-5-mini":         (0.25, 2.00),
    "gpt-4.1-mini":       (0.40, 1.60),    # fallback for GPT-5 mini
    "text-embedding-3-small": (0.027, 0),
    # ── Additional Validator Models ──────────────────────────────
    "gpt-5.4":            (5.00, 15.00),
    "grok-4-fast":        (3.00, 15.00),
    "gemini-2.5-pro":     (1.25, 10.00),
}



# ────────────────────────────────────────────────────────────
# LLM FARM MODEL → URL SEGMENT MAPPING
# The Vertex AI proxy encodes the Claude model in the URL path.
# Haiku 4.5 requires the @date suffix as per LLM Farm docs.
# ────────────────────────────────────────────────────────────
CLAUDE_URL_SEGMENTS = {
    "claude-sonnet-4-6": "claude-sonnet-4-6",
    "claude-sonnet-4-5": "claude-sonnet-4-5@20250929",  # confirmed LLM Farm segment
    "claude-haiku-4-5":  "claude-haiku-4-5@20251001",
    "claude-3-5-haiku":  "claude-3-5-haiku",              # legacy fallback
}

# OpenAI-compatible API version to use for GPT deployments
_GPT_API_VERSION = "2025-04-01-preview"
# OpenAI-compatible API version to use for embedding deployments
_EMBED_API_VERSION = "2024-10-21"


class LLMService:
    """
    Unified LLM client. All agents call this service — never call
    LLM Farm endpoints directly from agent code.

    All models (Claude Sonnet, Haiku, GPT-5 mini, embeddings) are
    routed through the Bosch LLM Farm proxy using a single shared key.
    """

    def __init__(self):
        # ── Claude + GPT: Authorization: Bearer ──────────
        # Both Claude (rawPredict) and GPT (chat/completions) use Bearer token.
        self._bearer_headers = {
            "Authorization": f"Bearer {settings.llm_farm_api_key}",
            "Content-Type": "application/json",
        }
        # ── Embeddings: subscription key header ──────────
        # Only the embedding endpoint uses this different auth scheme.
        self._embed_headers = {
            "genaiplatform-farm-subscription-key": settings.llm_farm_api_key,
            "Content-Type": "application/json",
        }
        self.farm_client = httpx.AsyncClient(
            base_url=settings.llm_farm_base_url,
            headers=self._bearer_headers,
            timeout=300.0,
        )
        # ── Grok 4: separate Azure AI endpoint with api-key auth ──────────
        self.grok_client = httpx.AsyncClient(
            base_url=settings.grok_base_url,
            headers={
                "api-key": settings.grok_api_key,
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

        # ── Cost tracking accumulator ────────────────────
        self.total_cost_usd = 0.0
        self.call_count = 0

    # ════════════════════════════════════════════════════════
    # PRIMARY METHOD: Call Claude (Sonnet or Haiku)
    # ════════════════════════════════════════════════════════
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectTimeout, httpx.ReadTimeout)),
    )
    async def call_claude(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        cache_system_prompt: bool = True,
    ) -> Dict[str, Any]:
        """
        Call Claude API (Sonnet 4.6 or Haiku 4.5).
        
        Args:
            messages: Conversation messages [{"role": "user", "content": "..."}]
            model: Override model (default: primary from config)
            system: System prompt (will be cached if cache_system_prompt=True)
            max_tokens: Maximum output tokens
            temperature: 0.0=deterministic, 1.0=creative. 0.3 for analysis.
            cache_system_prompt: Enable 5-minute prompt caching (saves ~70% input cost)
        
        Returns:
            {
                "content": "The AI response text",
                "model": "claude-sonnet-4-6",
                "input_tokens": 2500,
                "output_tokens": 1200,
                "cost_usd": 0.025,
                "cached_input_tokens": 18000,   # tokens served from cache
                "latency_ms": 3200
            }
        """
        model = model or settings.primary_model
        start_time = time.time()

        # ── Map model name → LLM Farm URL segment ────────
        url_segment = CLAUDE_URL_SEGMENTS.get(model, model)
        endpoint = (
            f"/api/google/v1/publishers/anthropic/models/{url_segment}:rawPredict"
        )

        # ── Build the request body ────────────────────────
        # LLM Farm uses Vertex AI's rawPredict format:
        # - anthropic_version goes in the BODY (not as a header)
        # - model is NOT in the body (it's encoded in the URL)
        body = {
            "anthropic_version": "vertex-2023-10-16",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }

        # ── System prompt with caching ────────────────────
        # The system prompt (~18K tokens for our platform context)
        # is identical across T1, T2, T5, T6, T9, T12.
        # With cache_control, Anthropic caches it for 5 minutes.
        # Subsequent calls pay $0.30/M (cache hit) instead of $3/M.
        # This saves ~$15-20/month on our 2,094 Sonnet calls.
        if system:
            if cache_system_prompt:
                # Anthropic's prompt caching: add cache_control to system prompt
                body["system"] = [
                    {
                        "type": "text",
                        "text": system,
                        "cache_control": {"type": "ephemeral"}  # 5-min cache
                    }
                ]
            else:
                body["system"] = system

        # ── Make the API call ─────────────────────────────
        try:
            response = await self.farm_client.post(endpoint, json=body)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            # Cascading fallback: sonnet-4-6 → sonnet-4-5 → haiku-4-5
            fallback_chain = [
                settings.primary_fallback_model,    # claude-sonnet-4-5 (same quality)
                settings.primary_fallback_model_2,  # claude-haiku-4-5 (speed tier)
            ]
            if model in [settings.primary_model] + fallback_chain[:-1]:
                # Pick the next model in the chain after the one that just failed
                current_idx = ([settings.primary_model] + fallback_chain).index(model)
                fallback = ([settings.primary_model] + fallback_chain)[current_idx + 1]
                logger.warning(
                    f"⚠️ FALLBACK │ {model} → {fallback} │ "
                    f"Reason: HTTP {e.response.status_code}"
                )
                fallback_segment = CLAUDE_URL_SEGMENTS.get(fallback, fallback)
                fallback_endpoint = (
                    f"/api/google/v1/publishers/anthropic/models/"
                    f"{fallback_segment}:rawPredict"
                )
                body.pop("model", None)  # Vertex reads model from URL, not body
                response = await self.farm_client.post(fallback_endpoint, json=body)
                response.raise_for_status()
                model = fallback
            else:
                raise

        result = response.json()
        latency_ms = int((time.time() - start_time) * 1000)

        # ── Extract response text ─────────────────────────
        content = ""
        for block in result.get("content", []):
            if block.get("type") == "text":
                content += block["text"]

        # ── Calculate cost ────────────────────────────────
        usage = result.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cached_tokens = usage.get("cache_read_input_tokens", 0)
        
        # Cost calculation:
        # Fresh input tokens: full price ($3/M for Sonnet)
        # Cached input tokens: cache hit price ($0.30/M for Sonnet)
        # Output tokens: always full price ($15/M for Sonnet)
        in_price, out_price = PRICING.get(model, (3.0, 15.0))
        cache_hit_price = in_price * 0.10  # Cache hit = 10% of input price
        
        fresh_input = input_tokens - cached_tokens
        cost = (
            (fresh_input / 1_000_000 * in_price) +
            (cached_tokens / 1_000_000 * cache_hit_price) +
            (output_tokens / 1_000_000 * out_price)
        )

        # ── Track cumulative cost ─────────────────────────
        self.total_cost_usd += cost
        self.call_count += 1

        cache_label = "HIT" if cached_tokens > 0 else "MISS"
        logger.info(
            f"\U0001f916 LLM CALL #{self.call_count} │ Model: {model} │ "
            f"In: {input_tokens} tok (cached: {cached_tokens}) │ Out: {output_tokens} tok │ "
            f"Cost: ${cost:.4f} │ Latency: {latency_ms / 1000:.1f}s │ "
            f"Cache: {cache_label} │ Cumulative: ${self.total_cost_usd:.4f} ({self.call_count} calls)"
        )

        return {
            "content": content,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_input_tokens": cached_tokens,
            "cost_usd": round(cost, 6),
            "latency_ms": latency_ms,
        }

    # ════════════════════════════════════════════════════════
    # CONVENIENCE: Call Sonnet (CRITICAL tasks)
    # ════════════════════════════════════════════════════════
    async def call_sonnet(self, prompt: str, system: str = None, **kwargs) -> Dict:
        """Shorthand for Claude Sonnet 4.6 — used for all CRITICAL tasks."""
        return await self.call_claude(
            messages=[{"role": "user", "content": prompt}],
            model=settings.primary_model,
            system=system,
            **kwargs,
        )

    # ════════════════════════════════════════════════════════
    # CONVENIENCE: Call Haiku (HIGH tasks — validation, scoring)
    # ════════════════════════════════════════════════════════
    async def call_haiku(self, prompt: str, system: str = None, **kwargs) -> Dict:
        """Shorthand for Claude Haiku 4.5 — used for validation and scoring."""
        return await self.call_claude(
            messages=[{"role": "user", "content": prompt}],
            model=settings.validator_model,
            system=system,
            temperature=0.1,  # Lower temperature for structured tasks
            **kwargs,
        )

    # ════════════════════════════════════════════════════════
    # VALIDATOR: GPT-5.4 (parallel validation + source verification)
    # ════════════════════════════════════════════════════════
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def call_gpt54(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 1500,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """Call GPT-5.4 via LLM Farm (Bearer auth) — validator + source verification."""
        model_name = "gpt-5.4"
        start_time = time.time()

        deployment = settings.gpt54_deployment
        endpoint = (
            f"/api/openai/deployments/{deployment}/chat/completions"
            f"?api-version=2025-04-01-preview"
        )
        body = {
            "model": deployment,
            "messages": [
                *([{"role": "system", "content": system}] if system else []),
                {"role": "user", "content": prompt},
            ],
            "max_completion_tokens": max_tokens,
            "temperature": temperature,
        }

        response = await self.farm_client.post(endpoint, json=body)
        response.raise_for_status()
        result = response.json()
        latency_ms = int((time.time() - start_time) * 1000)

        content = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        in_price, out_price = PRICING.get(model_name, (5.0, 15.0))
        cost = (input_tokens / 1e6 * in_price) + (output_tokens / 1e6 * out_price)
        self.total_cost_usd += cost
        self.call_count += 1

        return {
            "content": content,
            "model": model_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 6),
            "latency_ms": latency_ms,
        }

    # ════════════════════════════════════════════════════════
    # VALIDATOR: Grok 4 (parallel validation)
    # ════════════════════════════════════════════════════════
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def call_grok4(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """Call Grok 4 via Azure AI endpoint (api-key auth) — used as validator model."""
        model_name = "grok-4-fast"
        start_time = time.time()

        endpoint = (
            f"/openai/deployments/{settings.grok_deployment}/chat/completions"
            f"?api-version=2024-05-01-preview"
        )
        body = {
            "model": settings.grok_deployment,
            "messages": [
                *([{"role": "system", "content": system}] if system else []),
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        response = await self.grok_client.post(endpoint, json=body)
        response.raise_for_status()
        result = response.json()
        latency_ms = int((time.time() - start_time) * 1000)

        content = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        in_price, out_price = PRICING.get(model_name, (3.0, 15.0))
        cost = (input_tokens / 1e6 * in_price) + (output_tokens / 1e6 * out_price)
        self.total_cost_usd += cost
        self.call_count += 1

        return {
            "content": content,
            "model": model_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 6),
            "latency_ms": latency_ms,
        }

    # ════════════════════════════════════════════════════════
    # VALIDATOR: Gemini 2.5 Pro (parallel validation)
    # ════════════════════════════════════════════════════════
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def call_gemini25(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 8000,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """Call Gemini 2.5 Pro via LLM Farm (subscription-key auth) — used as validator model.

        Gemini 2.5 Pro is a thinking model: it spends internal reasoning tokens before producing
        output.  We default max_tokens=8000 so there is always room for both thinking and the
        actual response.  With smaller budgets the message arrives with no 'content' key.
        """
        model_name = "gemini-2.5-pro"
        start_time = time.time()

        deployment = settings.gemini_deployment
        endpoint = f"/api/openai/deployments/{deployment}/chat/completions"
        body = {
            "model": model_name,
            "messages": [
                *([{"role": "system", "content": system}] if system else []),
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # Gemini uses the subscription-key header (same as embeddings, different from Claude/GPT)
        response = await self.farm_client.post(
            endpoint, json=body, headers=self._embed_headers
        )
        response.raise_for_status()
        result = response.json()
        latency_ms = int((time.time() - start_time) * 1000)

        # Gemini 2.5 Pro (thinking model) may omit 'content' when finish_reason=='length'.
        # Guard against that so we raise a clear error rather than a cryptic KeyError.
        message = result["choices"][0]["message"]
        if "content" not in message:
            finish = result["choices"][0].get("finish_reason", "unknown")
            raise ValueError(
                f"Gemini response has no 'content' (finish_reason={finish!r}). "
                "Thinking budget exhausted — increase max_tokens."
            )
        content = message["content"]
        usage = result.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        in_price, out_price = PRICING.get(model_name, (1.25, 10.0))
        cost = (input_tokens / 1e6 * in_price) + (output_tokens / 1e6 * out_price)
        self.total_cost_usd += cost
        self.call_count += 1

        return {
            "content": content,
            "model": model_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 6),
            "latency_ms": latency_ms,
        }

    # ════════════════════════════════════════════════════════
    # OPENAI: GPT-5 mini (VOLUME tasks — sentiment scoring)
    # ════════════════════════════════════════════════════════
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def call_gpt(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """
        Call GPT-5 mini via LLM Farm's Azure OpenAI deployment endpoint.
        Used for high-volume classification tasks.
        News sentiment scoring (2000/month) and trend detection.
        """
        model = model or settings.volume_model
        start_time = time.time()

        # LLM Farm: model is identified by the deployment name in the URL
        deployment = settings.llm_farm_gpt_deployment
        endpoint = (
            f"/api/openai/deployments/{deployment}/chat/completions"
            f"?api-version={_GPT_API_VERSION}"
        )

        body = {
            "model": deployment,
            "messages": [
                *([{"role": "system", "content": system}] if system else []),
                {"role": "user", "content": prompt},
            ],
            "max_completion_tokens": max_tokens,
            "temperature": temperature,
        }

        response = await self.farm_client.post(endpoint, json=body)
        response.raise_for_status()
        result = response.json()
        latency_ms = int((time.time() - start_time) * 1000)

        content = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        # Use the logical model name for pricing lookup
        in_price, out_price = PRICING.get(settings.volume_model, (0.25, 2.0))
        cost = (input_tokens / 1e6 * in_price) + (output_tokens / 1e6 * out_price)

        self.total_cost_usd += cost
        self.call_count += 1

        return {
            "content": content,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 6),
            "latency_ms": latency_ms,
        }

    # ════════════════════════════════════════════════════════
    # EMBEDDINGS (for future RAG)
    # ════════════════════════════════════════════════════════
    async def get_embedding(self, text: str) -> List[float]:
        """Generate embedding vector for RAG storage via LLM Farm."""
        deployment = settings.llm_farm_embedding_deployment
        endpoint = (
            f"/api/openai/deployments/{deployment}/embeddings"
            f"?api-version={_EMBED_API_VERSION}"
        )
        # Embeddings use a different auth header than Claude/GPT
        response = await self.farm_client.post(
            endpoint,
            json={"input": text},
            headers=self._embed_headers,
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]

    # ════════════════════════════════════════════════════════
    # PARSE JSON from LLM response (handles markdown fences)
    # ════════════════════════════════════════════════════════
    @staticmethod
    def parse_json_response(text: str) -> Any:
        """
        LLMs often wrap JSON in ```json ... ``` blocks.
        This strips that and parses the JSON safely.
        If the response was truncated (hit max_tokens), attempts to
        recover a partial result by closing the JSON object.
        """
        # Remove markdown code fences if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            # Remove first line (```json) and last line (```)
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1])
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Try to recover truncated JSON by closing open braces/brackets
            logger.warning(f"JSON truncated (likely hit max_tokens) — attempting recovery: {e}")
            recovered = cleaned.rstrip()
            # Count unclosed braces/brackets and close them
            opens = recovered.count('{') - recovered.count('}')
            array_opens = recovered.count('[') - recovered.count(']')
            # Strip trailing incomplete value (e.g. half-written string)
            # Find last complete key-value pair by trimming to last complete },
            for trim_char in [',', '"', ':']:
                if recovered.endswith(trim_char):
                    recovered = recovered[:-1].rstrip()
            # Close any open arrays then objects
            recovered += ']' * max(0, array_opens) + '}' * max(0, opens)
            try:
                result = json.loads(recovered)
                logger.info("JSON recovery succeeded — partial response returned")
                return result
            except json.JSONDecodeError:
                logger.error(f"Failed to parse LLM JSON response (recovery also failed): {e}\nRaw text: {text[:500]}")
                return None

    # ════════════════════════════════════════════════════════
    # CLEANUP — close HTTP clients on shutdown
    # ════════════════════════════════════════════════════════
    async def close(self):
        """Close HTTP clients. Called on application shutdown."""
        await self.farm_client.aclose()
        await self.grok_client.aclose()
        logger.info(
            f"LLM Service shutdown. Total calls: {self.call_count}, "
            f"Total cost: ${self.total_cost_usd:.4f}"
        )


# ── Singleton instance — import this in agents ───────────
llm = LLMService()
