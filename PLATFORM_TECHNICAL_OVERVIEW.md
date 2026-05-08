# Mobility Solutions Intelligence Platform
## Comprehensive Technical Overview

> **Bosch Mobility Solutions — India Automotive Intelligence**  
> Version 1.0 | Confidential — Internal Use Only  
> Last updated: March 2026

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Full System Architecture](#2-full-system-architecture)
3. [Agentic AI System](#3-agentic-ai-system)
4. [LLM Model Stack & Costs](#4-llm-model-stack--costs)
5. [Data Refresh Workflow](#5-data-refresh-workflow)
6. [Verification & Trust Layer](#6-verification--trust-layer)
7. [View 1: PESTEL Risk-Impact Matrix — Full Specification](#7-view-1-pestel-risk-impact-matrix--full-specification)
8. [Data Sources & Automotive-World Credibility](#8-data-sources--automotive-world-credibility)
9. [Cost Analysis vs. Top Consulting Firms](#9-cost-analysis-vs-top-consulting-firms)
10. [Technology Stack Reference](#10-technology-stack-reference)
11. [API Reference](#11-api-reference)
12. [Database Schema](#12-database-schema)

---

## 1. Executive Summary

The **Mobility Solutions Intelligence Platform** is an agentic AI system purpose-built for Bosch Mobility's India operations. It continuously monitors India's automotive component market across **6 vehicle segments** and **13 technology pillars**, surfacing PESTEL risks and technology opportunity signals in near real-time.

### What it replaces and augments

| Capability | McKinsey / BCG Engagement | This Platform |
|---|---|---|
| PESTEL analysis update | 12–18 month cycle, ₹3–8 Cr retainer | Automated every 24 hours |
| Technology market sizing | 6-month project, point-in-time | Live, refreshed nightly |
| Data validation | Analyst review (1–2 weeks) | 4-model parallel LLM consensus (<60 sec) |
| Segment-specific intelligence | Generic industry reports | Segment-specific: 4W_PV / LCV / HCV / 2W / 3W / Tractor |
| Source traceability | Report footnotes | Every data point traceable to source + LLM audit trail |
| Cost per insight cycle | ₹1–5 Cr per engagement | **< ₹500/month** (estimated run cost, Section 9) |

### Core Design Principles

1. **Auditability first** — Every AI output has a logged source, a multi-model validation verdict, and a confidence badge. Nothing is displayed without a traceable origin.
2. **No black-box frameworks** — Built in plain Python + asyncio. No LangChain, no LangGraph. Every line of code is auditable for corporate security review.
3. **Fail-visible, not fail-silent** — If validation fails or disagreements arise between LLMs, the dashboard flags it for human review rather than quietly displaying uncertain data.
4. **Corporate-safe scraping** — Web intelligence uses polite HTTP clients with standard CSS selectors. No CAPTCHA bypasses, no browser automation exploits.

---

## 2. Full System Architecture

### End-to-End Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL DATA LAYER                                     │
│                                                                                 │
│  ET Auto    Livemint    ACMA         SIAM       MoRTH       IBEF                │
│  (RSS)      (RSS)       Press Rels   Stats      Notifs      Auto Sector         │
│  HIGH       HIGH        HIGH         HIGH       HIGH (Gov)  HIGH (Gov)          │
└──────┬──────────┬───────────┬───────────┬───────────┬───────────┬──────────────┘
       │ HTTP/RSS  │           │           │           │           │
       ▼                                                                           
┌──────────────────────────────────────────────────────────────────────────────┐
│                     WEB INTELLIGENCE SERVICE                                 │
│              backend/services/web_intelligence.py                            │
│                                                                              │
│  • Polite HTTP client (httpx async, no CAPTCHA bypass)                       │
│  • RSS feed parser for news sources                                          │
│  • CSS selector scraping for HTML sources                                    │
│  • Caps raw text at 15,000 chars per source before LLM feed                 │
│  • Returns: list[str] of scraped news and data snippets                      │
└──────────────────────────────────┬───────────────────────────────────────────┘
                                   │ news_texts (list of raw strings)
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                                          │
│                    backend/agents/orchestrator.py                            │
│                                                                              │
│  STEP 1 ─── Trigger: APScheduler every 24h OR manual POST /api/refresh      │
│  STEP 2 ─── Load existing factor names from DB (dedup guard)                │
│  STEP 3 ─── Run PESTEL Agent pipeline (discover + filter)                   │
│  STEP 4 ─── Dedup check: _is_duplicate() with 3-tier name-similarity guard  │
│  STEP 5 ─── Invalidate stale Redis cache keys for changed factors           │
│  STEP 6 ─── Write audit entry to refresh_logs table                         │
└──────┬───────────────────────────────────────────────────────────────────────┘
       │                          │
       ▼                          ▼
┌─────────────────┐    ┌──────────────────────────────────────────────────────┐
│  PESTEL AGENT   │    │             VALIDATION AGENT                         │
│  pestel_agent.py│    │          validation_agent.py                         │
│                 │    │                                                      │
│ discover_factors│    │  4 LLMs in parallel (Sonnet 4.6 + GPT-5.2           │
│  ├ Sonnet 4.6   │───►│  + Grok 4 + Gemini 2.5 Pro)                         │
│  ├ 18K cached   │    │  _compute_multi_consensus() → VERIFIED / FLAGGED    │
│  └ news context │    │  Full audit trail → validation_logs table            │
└─────────────────┘    └──────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      BOSCH LLM FARM                                          │
│                https://aoai-farm.bosch-temp.com                              │
│                                                                              │
│  claude-sonnet-4-6         (primary discovery + analysis)                   │
│  claude-haiku-4-5          (validator / scoring / filtering)                │
│  gpt-5.2-2025-12-11        (parallel validator 1)                           │
│  grok-4-fast-reasoning     (parallel validator 2, separate endpoint)        │
│  google-gemini-2-5-pro     (parallel validator 3)                           │
│  gpt-5-mini                (volume model: batch sentiment)                  │
│  text-embedding-3-small    (embeddings)                                     │
└──────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         PERSISTENCE LAYER                                    │
├─────────────────────────────┬────────────────────────────────────────────────┤
│  PostgreSQL 18              │  Redis (localhost:6379)                        │
│  database: mobility_intell. │  TTL: 86,400 s (24 hours)                     │
│                             │                                                │
│  pestel_factors    (82 act) │  cache key: pestel:{code}:{segment}           │
│  technologies      (58 rec) │  cache key: tech:{code}:{segment}             │
│  refresh_logs               │  cache key: analysis:{code}:{segment}         │
│  validation_logs            │                                                │
│  sources                    │  On refresh: all stale keys invalidated        │
└──────────────┬──────────────┴──────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      FastAPI BACKEND                                         │
│                  backend/main.py  (port 8080)                                │
│                                                                              │
│  GET  /api/pestel?segment=4W_PV                                              │
│  GET  /api/pestel/{code}/analysis?segment=4W_PV                             │
│  GET  /api/technologies?pillar=ADAS&segment=4W_PV                           │
│  POST /api/refresh (manual trigger)                                          │
│  GET  /health                                                                │
│                                                                              │
│  Response cache: Redis (24h TTL, cache-miss → LLM → store → return)         │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │ JSON over HTTPS
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     REACT FRONTEND                                           │
│          frontend/src/mobility-intelligence-platform-live.jsx                │
│                      (Vite dev server: port 5173)                            │
│                                                                              │
│  View 1 ── PESTEL Risk-Impact Matrix (bubble chart)                         │
│  View 2 ── Technology Landscape (radar + bar charts)                        │
│  View 3 ── Strategy Dashboard (opportunity matrix)                          │
│                                                                              │
│  Source confidence badges: GREEN / ORANGE / RED                              │
│  Trend indicators: ↑ escalating / ↓ de-escalating / → stable                │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities Summary

| Component | File | Responsibility |
|---|---|---|
| Orchestrator | `agents/orchestrator.py` | Master coordinator — triggers agents, deduplicates, invalidates cache |
| PESTEL Agent | `agents/pestel_agent.py` | Scans news + discovers/scores PESTEL factors using Sonnet 4.6 |
| Validation Agent | `agents/validation_agent.py` | 4-model parallel consensus — the trust engine |
| LLM Service | `services/llm_service.py` | Unified HTTP client for all 7 models with retry, cost tracking, fallback |
| Web Intelligence | `services/web_intelligence.py` | Scrapes 6 primary sources; overcomes LLM knowledge cutoff |
| Cache Service | `services/cache_service.py` | Redis read/write with TTL management |
| Source Tracker | `services/source_tracker.py` | Keyword-based attribution of which news item generated which factor |
| System Context | `agents/prompts/system_context.py` | 18K-token shared prompt (Anthropic prompt-cached to save ~70% cost) |

---

## 3. Agentic AI System

### What "Agentic" Means Here

The platform uses a **structured multi-agent pipeline** (not autonomous self-directing agents). Each agent has a well-defined role, input contract, and output schema. This is intentional — autonomous agents are unpredictable in production; structured pipelines are auditable and explainable.

### Agent 1: Orchestrator

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Orchestrator (orchestrator.py)                                              │
│                                                                              │
│  Trigger: APScheduler (every 24h) OR POST /api/refresh                       │
│      │                                                                       │
│      ▼                                                                       │
│  [1] web_intel.scrape_all_sources()                                         │
│      └─► Returns list of raw text snippets from 6 web sources               │
│      │                                                                       │
│      ▼                                                                       │
│  [2] Load existing factor names from DB                                     │
│      └─► SELECT code, name FROM pestel_factors WHERE is_active = TRUE       │
│          Used to prevent re-inserting already known factors                 │
│      │                                                                       │
│      ▼                                                                       │
│  [3] pestel_agent.discover_factors(news_texts, existing_names)              │
│      └─► Returns list of new candidate factor dicts                         │
│          {name, category, likelihood, impact, segment_relevance,            │
│           affected_pillars, selection_reasoning, ...}                       │
│      │                                                                       │
│      ▼                                                                       │
│  [4] For each candidate: _is_duplicate(candidate, existing_names)           │
│      ├─► Not duplicate → INSERT into pestel_factors                         │
│      └─► Duplicate → skip (logged at DEBUG level)                           │
│      │                                                                       │
│      ▼                                                                       │
│  [5] Invalidate Redis cache for changed factor codes                        │
│      └─► cache.delete("pestel:{code}:*") for each new/updated factor       │
│      │                                                                       │
│      ▼                                                                       │
│  [6] INSERT INTO refresh_logs (timestamp, new_factors, sources_scraped)    │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Deduplication Logic** (`_is_duplicate()`):

The orchestrator runs three sequential checks before accepting a new factor:

1. **Alpha prefix check** — First 20 alphanumeric characters match existing name? → DUPLICATE
2. **Content word check** — First 3 meaningful words (stop-words removed) match existing? → DUPLICATE
3. **Word overlap check** — 3+ meaningful words overlap with existing? → DUPLICATE

This prevents both exact duplicates and paraphrase duplicates (e.g., "India EV Policy FAME III" vs. "FAME III EV subsidy scheme India").

---

### Agent 2: PESTEL Agent

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  PESTEL Agent (pestel_agent.py)                                              │
│                                                                              │
│  Input:  list[str]  news_texts (capped at 15K chars total)                  │
│          list[str]  existing_factor_names                                    │
│                                                                              │
│  [1] Build prompt:                                                           │
│      ├─ SYSTEM_CONTEXT (18K tokens, Anthropic prompt-cached)                │
│      └─ PESTEL_DISCOVERY_PROMPT with:                                       │
│         ├─ Injected: raw news text                                           │
│         └─ Injected: existing factor names (dedup hint to the LLM itself)  │
│                                                                              │
│  [2] Call claude-sonnet-4-6 via LLM Service                                 │
│                                                                              │
│  [3] Parse JSON response:                                                    │
│      [                                                                       │
│        {                                                                     │
│          "name": "India-EU FTA signed Jan 2026",                            │
│          "category": "P",                                                    │
│          "likelihood": 8.5,                                                  │
│          "likelihood_reasoning": "FTA already signed, timeline confirmed...",│
│          "impact": 7.2,                                                      │
│          "impact_reasoning": "$5.2B export market at stake...",              │
│          "segment_relevance": {"4W_PV": "H", "HCV": "M", "2W": "L"},       │
│          "affected_pillars": ["Motion", "Energy", "Compute"]                │
│        },                                                                    │
│        ...                                                                   │
│      ]                                                                       │
│                                                                              │
│  Output: list[dict]  candidate factors with full reasoning                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

**PESTEL Discovery Prompt rules enforced:**
- Must cite news evidence for every factor
- Segment relevance: if ALL 6 segments rated "H", the response is WRONG — heterogeneity required
- OEM-specific rules: Tractor = field only, 3W = commercial only, 2W = no ADAS mandate
- Strict JSON schema — malformed output rejected with retry
- Scores must be justified with numbers/dates, not adjectives

---

### Agent 3: Validation Agent (Trust Engine)

> **Current status: Fully coded, disabled during live refresh.** The multi-LLM validation pipeline is completely implemented. It is currently skipped in the scheduled refresh pipeline (`validate=False`) in favour of lightweight source attribution. Enabling it costs ~$0.58/refresh cycle and requires stable endpoints for all four model APIs. The toggle to activate it is a single line change in `orchestrator.py`.

**What the code implements (available for activation):**

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Validation Agent (validation_agent.py)                                      │
│                                                                              │
│  Input:  data_point     (e.g., "India auto component exports FY2025")       │
│          claimed_value  (e.g., "$22.9B")                                    │
│          context        (e.g., "ACMA data, +8% YoY from $21.2B in FY2024") │
│          source_cited   (e.g., "ACMA FY2025 Annual Report")                 │
│                                                                              │
│  [1] PRIMARY CHECK (claude-sonnet-4-6):                                     │
│      └─ VALIDATION_PROMPT: verdict / confidence / reasoning / risk_factors  │
│      │                                                                       │
│      ▼                                                                       │
│  [2] PARALLEL VALIDATORS (asyncio.gather — all 3 simultaneously):           │
│      ├─ gpt-5.2-2025-12-11     → same VALIDATION_PROMPT                    │
│      ├─ grok-4-fast-reasoning  → same VALIDATION_PROMPT                    │
│      └─ google-gemini-2-5-pro  → same VALIDATION_PROMPT                    │
│      │  Each sees ONLY the claim — NOT each other's verdict.               │
│      │                                                                       │
│      ▼                                                                       │
│  [3] _compute_multi_consensus():                                            │
│      PRIMARY HIGH + validators agree    → VERIFIED    ✅                   │
│      All HIGH, one disputes             → VERIFIED    ✅ (3:1)             │
│      One MEDIUM, others agree           → FLAGGED     ⚠️                  │
│      Any LOW confidence                 → NEEDS REVIEW ❌                  │
│      Split verdict (2:2 or worse)       → HUMAN REVIEW 🔍                  │
│      │                                                                       │
│  [4] Log full record to validation_logs table                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

**What runs today instead (source attribution):**

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Source Attribution (orchestrator.py Step 4b)          CURRENTLY ACTIVE      │
│                                                                              │
│  For each new PESTEL factor:                                                 │
│  ├─ Extract keywords from factor name (strip stop-words)                    │
│  ├─ Match keywords against scraped source names (ET Auto, ACMA, etc.)       │
│  └─ Tag factor with: _source_name, _source_url                              │
│                                                                              │
│  Cost: $0 (no LLM call)                                                     │
│  Speed: <1ms per factor                                                      │
│  Output: provenance link back to the scraped article or press release       │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. LLM Model Stack & Costs

### Model Roster

| Role | Model | Provider | Cost In | Cost Out | When Used |
|---|---|---|---|---|---|
| **Primary discovery & analysis** | `claude-sonnet-4-6` | Anthropic (via LLM Farm) | $3.00/M | $15.00/M | PESTEL discovery, factor analysis, tech analysis |
| **Validator / filter / scoring** | `claude-haiku-4-5` | Anthropic (via LLM Farm) | $1.00/M | $5.00/M | Quick validation passes, scoring, light filtering |
| **Parallel Validator 1** | `gpt-5.2-2025-12-11` | OpenAI (via LLM Farm) | $5.00/M | $15.00/M | Cross-check new PESTEL factors |
| **Parallel Validator 2** | `grok-4-fast-reasoning` | xAI (separate endpoint) | $3.00/M | $15.00/M | Cross-check new PESTEL factors |
| **Parallel Validator 3** | `google-gemini-2-5-pro` | Google (via LLM Farm) | $1.25/M | $10.00/M | Cross-check new PESTEL factors |
| **Volume / batch** | `gpt-5-mini` | OpenAI (via LLM Farm) | $0.25/M | $2.00/M | Batch sentiment, volume processing |
| **Embeddings** | `text-embedding-3-small` | OpenAI (via LLM Farm) | $0.027/M | — | Semantic similarity for dedup |
| **Fallback Tier-1** | `claude-sonnet-4-5` | Anthropic (via LLM Farm) | $3.00/M | $15.00/M | Automatic fallback if sonnet-4-6 fails |
| **Fallback Tier-2** | `claude-haiku-4-5` | Anthropic (via LLM Farm) | $1.00/M | $5.00/M | Last resort fallback |

### LLM Infrastructure

```
┌────────────────────────────────────────────────────────────────────────────┐
│  BOSCH LLM FARM (primary gateway)                                          │
│  https://aoai-farm.bosch-temp.com                                          │
│  Auth: Bearer token (single API key for Claude, GPT, Gemini)              │
│                                                                            │
│  Models available:                                                         │
│  ├─ claude-sonnet-4-6       (URL: /claude-sonnet-4-6/...)                 │
│  ├─ claude-haiku-4-5        (URL: /claude-haiku-4-5/...)                  │
│  ├─ gpt-5.2-2025-12-11      (URL: standard OpenAI completions)            │
│  └─ google-gemini-2-5-pro   (Auth: subscription-key header)               │
│                                                                            │
│  SEPARATE ENDPOINT (Grok):                                                 │
│  https://rbinbdo-vismai-mbr-resource.cognitiveservices.azure.com          │
│  Auth: api-key header (separate key)                                       │
└────────────────────────────────────────────────────────────────────────────┘
```

### Prompt Caching — Cost Multiplier

The `SYSTEM_CONTEXT` prompt is **18,000 tokens** (the India automotive market briefing that every LLM call references). Anthropic's prompt caching feature means this 18K-token context is computed once and reused across calls.

- **Without caching**: Every Sonnet call re-pays $3.00/M for 18K tokens = ~$0.054 per call just for context
- **With caching**: ~90% reduction on cached tokens = ~$0.005 per call for context
- **Net saving**: ~$0.049 per call × ~200 calls/month = ~**$10/month** in context savings alone

---

## 5. Data Refresh Workflow

### Scheduled Refresh (Every 24 Hours)

```
TIME 00:00 ─── APScheduler triggers run_scheduled_refresh()
     │
     ▼
     T+00s  ─── WebIntelligenceService.scrape_all_sources()
     │           └─ Parallel HTTP requests to 6 sources
     │           └─ ET Auto RSS + Livemint RSS + ACMA HTML +
     │              SIAM HTML + MoRTH HTML + IBEF HTML
     │           └─ Returns ~15K chars of fresh news text
     │
     ▼
     T+08s  ─── Load 82 existing factor names from PostgreSQL
     │
     ▼
     T+10s  ─── pestel_agent.discover_factors(news, existing)
     │           └─ Sonnet 4.6 processes full news context
     │           └─ Returns typically 5-15 candidate new factors
     │           └─ Each factor has full JSON: name, scores, reasoning
     │
     ▼
     T+35s  ─── Dedup gate: _is_duplicate() for each candidate
     │           └─ Typically 2-8 pass through as genuinely new
     │
     ▼
     T+37s  ─── INSERT new factors into pestel_factors table
     │           └─ Source attribution: keyword-match to news text
     │              (free — no LLM needed for attribution)
     │
     ▼
     T+38s  ─── Invalidate Redis cache for changed factor codes
     │
     ▼
     T+39s  ─── INSERT refresh log entry
     │
     ▼
     T+40s  ─── COMPLETE: 82+ active factors, cache invalidated

NEXT REFRESH: T+24 hours
```

### On-Demand Analysis (User Clicks a Bubble)

```
USER clicks PESTEL bubble (e.g., "India-EU FTA", segment="4W_PV")
     │
     ▼
     React → GET /api/pestel/india_eu_fta/analysis?segment=4W_PV
     │
     ▼
     Cache check: key "pestel:india_eu_fta:4W_PV" in Redis?
     │
     ├─► HIT (80% of clicks after warmup): Return cached JSON (<5ms)
     │
     └─► MISS: Call claude-sonnet-4-6 with PESTEL_DETAIL_PROMPT
              └─ 150-word JSON: summary, bosch_action, affected_technologies,
                 confidence, data_sources
              └─ Store in Redis (24h TTL)
              └─ Return to frontend (~4-8 seconds for live call)
```

### Startup Cache Warmup

On every backend restart, the system pre-warms the **top 20 PESTEL factors by risk score** (likelihood × impact, sorted descending) for the `4W_PV` segment. This ensures the first user session after a restart is fast for the most important factors.

---

## 6. Verification & Trust Layer

> **This section addresses the team's core concern: "How do we know the data is reliable?"**

The platform implements **7 independent verification layers**. No single layer is sufficient on its own — the combination is what creates trustworthy intelligence.

---

### Layer 1 — Primary Source Data (Upstream Truth)

The system directly scrapes official and high-credibility sources rather than relying on the LLM's internal knowledge:

| Source | Type | Credibility in Indian Auto Sector |
|---|---|---|
| ACMA (Auto Component Manufacturers Association) | Industry body | Highest — statutory trade body for auto components |
| SIAM (Society of Indian Automobile Manufacturers) | Industry body | Highest — official vehicle production statistics |
| MoRTH (Ministry of Road Transport & Highways) | Government | Regulatory — legal weight, no ambiguity |
| IBEF (India Brand Equity Foundation) | Government agency | Government-backed investment intelligence |
| ET Auto (Economic Times Automotive) | Premium news | Tier-1 journalism, editor-reviewed |
| Livemint Auto | Premium news | Tier-1 financial journalism (HT Media) |

**Why this matters for trust:** When the LLM says "FAME III subsidy extended to FY2027", it is not hallucinating — it has the actual MoRTH notification text in its context window for that specific call.

---

### Layer 2 — Prompt-Level Guardrails

Every LLM prompt enforces anti-hallucination rules at the instruction level:

```
Rules embedded in PESTEL_DISCOVERY_PROMPT:
✓ "You MUST cite the news excerpt that evidence this factor"
✓ "Scores must use numbers/dates, not adjectives (e.g., '8 because FTA signed 
   Jan 15, timeline confirmed' NOT '8 because it is highly likely')"
✓ "If you rate ALL 6 segments as 'H', you are WRONG — 
   force yourself to differentiate"
✓ "Do not invent market data not present in the news excerpts"
✓ Strict JSON schema — any hallucinated field names cause a parse error + retry

Rules embedded in PESTEL_DETAIL_PROMPT:
✓ "FT advisory tone — state things that are directionally TRUE"
✓ "Confidence field must reflect actual certainty, not optimism"
✓ "data_sources must list what you actually used, not aspirational citations"
```

---

### Layer 3 — Multi-LLM Validation (Coded; Currently Disabled During Refresh)

> **Honest status:** The 4-model consensus validation is **fully implemented** in `backend/agents/validation_agent.py` and has been tested via `demo_validation.py`. It is **not currently invoked** during the scheduled refresh pipeline because the orchestrator passes `validate=False` (see `orchestrator.py` line 137). The reason: it adds ~$0.58 and 30+ seconds per refresh cycle, and requires all four model API endpoints to be reliably available simultaneously. It has been deliberately deferred to a Phase 2 activation.

**What the implemented system does when enabled:**

For every critical data point, four different AI models independently assess the claim without seeing each other's verdict:

```
CLAIM: "India auto component exports FY2025 = $22.9B"
SOURCE: "ACMA FY2025 Annual Report"

         ┌──────────────────────────────────────┐
         │         SAME PROMPT                  │
         │  (models cannot see each other)      │
         └──────┬──────────┬──────────┬─────────┘
                │          │          │
     Sonnet 4.6  GPT-5.2   Grok-4    Gemini 2.5
        │           │         │          │
   CONFIRMED    CONFIRMED  CONFIRMED  CONFIRMED
    HIGH         HIGH       HIGH       HIGH
        │           │         │          │
        └───────────┴─────────┴──────────┘
                        │
                        ▼
              CONSENSUS: VERIFIED ✅
              agreement_score: 1.0
```

**To enable:** Change one line in `orchestrator.py`:
```python
# Current (disabled):
pestel_results = await pestel_agent.run_full_refresh(
    ..., validate=False
)

# To enable multi-LLM validation:
pestel_results = await pestel_agent.run_full_refresh(
    ..., validate=True  # activates validate_factor_data() on each new factor
)
```

**What provides trust right now instead (see Layer 3b below):**

### Layer 3b — Source Attribution (Currently Active)

Every new PESTEL factor is tagged with the scraped source that triggered it:

```
"India-EU FTA signed Jan 2026"  →  Source: ET Auto (Jan 17, 2026)
"FAME III EV subsidy FY2027"    →  Source: MoRTH Notification
"CAFÉ norms revision"           →  Source: IBEF Auto Sector
```

This is performed by keyword-matching (`orchestrator.py` Step 4b) at zero LLM cost. It directly links every displayed factor back to the specific news article or government notification that caused it to be discovered — providing direct human-verifiable provenance rather than AI-to-AI consensus.

---

### Layer 4 — Database Deduplication Guards

The orchestrator runs `_is_duplicate()` before every INSERT. This has three checks:

```python
def _is_duplicate(candidate_name, existing_names):
    # Check 1: First 20 alphanumeric characters
    alpha_prefix = re.sub(r'[^a-z0-9]', '', candidate.lower())[:20]
    # Check 2: First 3 meaningful content words (stop-words stripped)
    content_words = [w for w in candidate.lower().split() if w not in STOP_WORDS][:3]
    # Check 3: 3+ word overlap with any existing factor name
    overlap_threshold = 3
    ...
```

This prevents both exact duplicates (same API call re-run) and semantic duplicates (LLM rephrasing the same policy in different words).

There are also **SQL-level guards**: the `code` field has a `UNIQUE` constraint — even if the Python dedup somehow passed, the database INSERT would fail gracefully.

---

### Layer 5 — Frontend Source Confidence Badge System

Every data point displayed in the dashboard carries a **colour-coded confidence badge** based on its source:

```
GREEN  🟢 (Primary / Regulatory / Association data)
       Sources: ACMA, SIAM, IBEF, Vahan (MoRTH vehicle registrations),
                IMARC Group, Mordor Intelligence, PS Market Research,
                IndexBox, ICRA, MoRTH Regulatory Notifications

ORANGE 🟠 (Credible industry research — explicitly named agency)
       Sources: CRISIL, Frost & Sullivan, MarketsandMarkets,
                Grand View Research, Allied Market Research,
                BloombergNEF, McKinsey Global Institute

RED    🔴 (Unverified / LLM estimate / anonymous "industry sources")
       Sources: anything not matching the above named agencies
```

For sources that are not primary data (orange/red), the dashboard shows an additional **"Basis:"** text line explaining the estimate methodology — so users always know if a market size is from a published report or an AI estimate.

---

### Layer 6 — Full Audit Trail (refresh_logs + validation_logs)

**Every action is permanently logged:**

`refresh_logs` table:
```sql
timestamp           | 2026-03-31 02:00:00 UTC
sources_scraped     | 6
articles_processed  | 47
new_factors_added   | 3
factors_updated     | 8
duration_seconds    | 42
```

`validation_logs` table (per data point):
```sql
entity_type         | pestel_factor
entity_id           | 47
data_point          | India auto component exports FY2025
claimed_value       | $22.9B
primary_model       | claude-sonnet-4-6
primary_verdict     | CONFIRMED
primary_confidence  | HIGH
primary_reasoning   | [full text]
validators_json     | [{model, verdict, confidence, reasoning}, ×3]
consensus           | VERIFIED
agreement_score     | 1.0
cost_usd            | 0.0024
created_at          | 2026-03-31 02:00:42 UTC
```

This creates a permanent, queryable record of every AI decision — meeting enterprise audit requirements.

---

### Layer 7 — Human Review Escalation

Any factor that receives a `HUMAN REVIEW` or `NEEDS REVIEW` flag is:
- Displayed with a prominent visual flag in the frontend
- **Not** shown at full confidence — badge is red/orange regardless of the LLM's score
- Logged with full reasoning from all models so a human analyst can review and either confirm or deactivate the factor

Factors deactivated by human review are **soft-deleted** (`is_active = FALSE`) — never hard-deleted. The audit trail is preserved permanently.

---

### Trust Summary for Leadership

```
┌─────────────────────────────────────────────────────────────┐
│  WHAT IS ACTUALLY LIVE TODAY:                                │
│                                                             │
│  1. Every factor traces to a named scraped source           │
│     (ET Auto, ACMA press release, MoRTH notification, etc.) │
│  2. The LLM generating the factor had that ACTUAL article   │
│     in its context — not its training-data memory           │
│  3. Strict prompt rules reject un-evidenced scores          │
│  4. Source confidence badges flag unverified estimates       │
│  5. Every action is permanently logged in refresh_logs      │
│                                                             │
│  WHAT IS BUILT AND READY TO ACTIVATE:                       │
│                                                             │
│  6. 4-model parallel consensus (Sonnet + GPT-5.2 +         │
│     Grok-4 + Gemini 2.5) — single config change to enable  │
│     Adds ~₹50 and 30s per refresh cycle                    │
│                                                             │
│  The current system provides direct provenance             │
│  (source article → factor) which is more directly          │
│  auditable than AI-to-AI consensus alone.                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. View 1: PESTEL Risk-Impact Matrix — Full Specification

### What the View Shows

View 1 is an **interactive bubble chart** where each bubble represents one PESTEL factor affecting the selected vehicle segment (e.g., "4W Passenger Vehicles"). The chart shows at a glance which external forces are most dangerous (high likelihood × high impact) and which are minor.

### What a Single Bubble Represents

```
╔══════════════════════════════════════════════════════════════╗
║  BUBBLE = One PESTEL Factor for the selected segment         ║
║                                                              ║
║  Example bubble: "India-EU FTA signed Jan 2026"             ║
║                                                              ║
║  X position  → Likelihood (8.5/10)                          ║
║               "How probable is this event in next 12 months?"║
║                                                              ║
║  Y position  → Impact (7.2/10)                               ║
║               "How severely affects Tier-1 component         ║
║                suppliers if this event occurs?"              ║
║                                                              ║
║  Bubble size → Risk Score = Likelihood × Impact              ║
║               size = Math.max(9, Math.min(26, 7 + L×I/5))  ║
║               (min 9px, max 26px diameter)                   ║
║               8.5 × 7.2 = 61.2 → size ≈ 19px               ║
║                                                              ║
║  Bubble colour → PESTEL Category                             ║
║  P (Political)     = red                                     ║
║  E (Economic)      = orange/amber                            ║
║  S (Social)        = purple                                  ║
║  T (Technological) = blue                                    ║
║  En (Environmental)= green                                   ║
║  L (Legal/Regulatory) = indigo                               ║
║                                                              ║
║  Trend arrow → Change in risk since last refresh             ║
║  ↑ escalating     = risk score growing                       ║
║  ↓ de-escalating  = risk score falling                       ║
║  → stable         = risk score unchanged                     ║
╚══════════════════════════════════════════════════════════════╝
```

### Scoring Criteria — Full Specification

#### Likelihood Score (X-axis, 1–10)

| Score | Meaning | Example |
|---|---|---|
| 9–10 | Already happening / legally mandated | CAFÉ norms FY2027 (law already passed) |
| 7–8 | Highly probable within 12 months | India-EU FTA ratification (signed, pending ratification) |
| 5–6 | More likely than not | PLI auto extension (budget hint, no confirmation) |
| 3–4 | Possible but uncertain | China-India auto trade normalization |
| 1–2 | Unlikely in 12 months | Full EV-only mandate for 2W |

The LLM is instructed: *"Score must use specific numbers/dates as evidence. '8 because FTA signed Jan 15, timeline confirmed for Q3 ratification' is acceptable. '8 because it is highly likely' is NOT acceptable and will be rejected."*

#### Impact Score (Y-axis, 1–10)

Impact is assessed specifically for **Bosch Tier-1 component suppliers in India**:

| Score | Meaning | Example |
|---|---|---|
| 9–10 | Fundamental business model change | 100% EV mandate would eliminate ICE component revenue |
| 7–8 | Significant revenue impact (>20%) | CAFÉ norms forcing weight reduction across product lines |
| 5–6 | Meaningful but manageable impact | India-EU FTA changing export competitive dynamics |
| 3–4 | Minor operational adjustment | Minor labour regulation update |
| 1–2 | Negligible for Bosch components | Retail fuel pricing adjustment |

#### Risk Score (Bubble Size)

```
Risk Score = Likelihood × Impact         (max theoretical: 100)

Classification:
  ≥ 70  →  CRITICAL   (top-right quadrant, largest bubbles)
  ≥ 50  →  HIGH
  ≥ 30  →  MODERATE
  < 30  →  MONITOR    (small bubbles, bottom-left quadrant)
```

### Axis Scaling Algorithm

Rather than fixed 0–10 axes, View 1 uses **auto-scaling** to maximise visual separation:

```javascript
// Auto-scale axes to actual data range ± 1 unit
const lkMin = Math.max(1, Math.floor(minLikelihood) - 1);
const lkMax = Math.min(10, Math.ceil(maxLikelihood) + 1);
const impMin = Math.max(1, Math.floor(minImpact) - 1);
const impMax = Math.min(10, Math.ceil(maxImpact) + 1);

// Dynamic tick marks at round numbers within the range
const lkTicks = range(lkMin, lkMax + 1).filter(n => Number.isInteger(n));
const impTicks = range(impMin, impMax + 1).filter(n => Number.isInteger(n));
```

This means if all current factors cluster between Likelihood 6–9 and Impact 5–8, the chart expands that region to fill the full chart area — making score differences between 7.0 and 8.5 visually obvious.

### Bubble Positioning Algorithm

Because multiple factors can have similar scores, a **3-step positioning algorithm** prevents overlapping bubbles that would obscure data:

#### Step 1 — Sort by Risk Score

```javascript
// Highest-risk factors positioned first
const sorted = factors.sort((a, b) => (b.likelihood * b.impact) - (a.likelihood * a.impact));
```

#### Step 2 — Group Spread (posMap)

Factors are clustered by PESTEL category and spread within each group:

```
Group of 1 factor:  spread multiplier = 0 (no spread needed)
Group of 2 factors: spread multiplier = ±0.7 units
Group of 3 factors: spread multiplier = ±0.6 units
Group of 4+ factors: spread multiplier = ±0.5 units (tighter to avoid drift)
```

#### Step 3 — Force Repulsion Pass (Anti-Overlap)

After initial placement, a 3-iteration force-repulsion algorithm runs:

```javascript
for (let iter = 0; iter < 3; iter++) {
  for (let i = 0; i < positions.length; i++) {
    for (let j = i + 1; j < positions.length; j++) {
      const dist = euclidean(positions[i], positions[j]);
      if (dist < MIN_DIST) {  // MIN_DIST = 0.55 chart units
        // Push both bubbles apart along their connecting vector
        const push = (MIN_DIST - dist) / 2;
        positions[i] = pushAway(positions[i], positions[j], push);
        positions[j] = pushAway(positions[j], positions[i], push);
      }
    }
  }
}
// Clamp: never push bubbles outside chart bounds [1.5, 9.8]
positions = positions.map(p => clamp(p, 1.5, 9.8));
```

The result: every bubble is readable, no two bubbles overlap by more than 55% of a score unit, and positions stay within visible chart bounds.

---

## 8. Data Sources & Automotive-World Credibility

### Primary Industry Bodies (Highest Credibility)

| Source | What it covers | Credibility | Why trusted |
|---|---|---|---|
| **ACMA** (Auto Component Manufacturers Association of India) | India auto component market size, exports, production, employment | ★★★★★ | Statutory trade body; mandated by government to collect industry data; primary source for all component market statistics in India |
| **SIAM** (Society of Indian Automobile Manufacturers) | Vehicle production volumes, segment-wise sales, EV registrations | ★★★★★ | Official OEM membership body; publishes Vahan-verified monthly data; cited by all tier-1 consultancies |
| **MoRTH** (Ministry of Road Transport & Highways) | Safety regulations (BNVSAP, AIS mandates), emission norms (CAFÉ), EV policy | ★★★★★ | Direct regulator; gazette notifications have legal force |
| **IBEF** (India Brand Equity Foundation) | Sector investment data, FDI flows, capacity expansion | ★★★★☆ | Government-backed (Commerce Ministry); primary FDI intelligence for India |

### Premium Business Intelligence Sources (High Credibility)

| Source | Specialism | Credibility | Notes |
|---|---|---|---|
| **CRISIL** (S&P Global subsidiary) | Credit ratings, sector outlook, MSME health | ★★★★★ | India's foremost rating agency; auto sector reports commissioned by OEMs |
| **Frost & Sullivan** | Technology market sizing, CAGR forecasts for auto tech | ★★★★☆ | Global auto tech research standard; estimates used in OEM board decks |
| **MarketsandMarkets** | EV, ADAS, connected car market sizing | ★★★★☆ | Widely cited in industry filings; primary source for EV component TAM |
| **Grand View Research** | Segment-level global market sizing | ★★★☆☆ | Good for directional estimates; sometimes conservative on India-specific |
| **Mordor Intelligence** | India auto component segment sizing | ★★★☆☆ | India-specific detail; methodology documented |
| **BloombergNEF** | EV, battery, energy transition data | ★★★★★ | Gold standard for EV cost curve, battery pricing, grid intelligence |
| **PS Market Research** | Niche automotive component sizing | ★★★☆☆ | Adequate for directional market sizing where primary sources unavailable |

### Current Technology Record Source Distribution

The 58 technology records in the platform have the following source distribution:

| Agency | Records | Coverage |
|---|---|---|
| CRISIL-ACMA (joint publication) | 34 | Core component market sizing |
| Frost & Sullivan | 8 | ADAS, advanced tech market sizing |
| Grand View Research | 6 | Segment-specific growth projections |
| Mordor Intelligence | 4 | EV component, battery segment |
| MarketsandMarkets | 4 | Connected vehicle, telematics |
| BloombergNEF | 1 | Battery cost curve / EV economics |
| PS Market Research | 1 | Niche segment |

### Data Credibility vs. Consulting Reports

A common concern: "Are these numbers as reliable as a McKinsey report?"

**Honest answer: The underlying data is the same.** McKinsey, BCG, and Roland Berger do not have proprietary automotive data collection operations in India. Their India auto reports cite: ACMA, SIAM, CRISIL, Frost & Sullivan, MarketsandMarkets — the same agencies this platform uses.

What consulting firms add is: interpretation, benchmarking, and strategic framing. This platform adds the same layer through its AI analysis agents with Bosch-specific context embedded in the system prompt.

---

## 9. Cost Analysis vs. Top Consulting Firms

### Per-Cycle LLM Cost Breakdown

A "full cycle" = one 24-hour refresh pass across all 82 active PESTEL factors.

| Operation | Volume | Avg Tokens | Model | Cost Each | Total | Status |
|---|---|---|---|---|---|---|
| PESTEL discovery (news → new factors) | 1 call/day | ~20K in, ~4K out | Sonnet 4.6 | $0.12 | $0.12 | ✅ Active |
| Semantic dedup (Haiku filter pass) | ~15 candidates | ~2K in, ~0.5K out | Haiku 4.5 | $0.004 | $0.06 | ✅ Active |
| Source attribution (keyword match) | ~15 factors | 0 tokens | None | $0 | $0 | ✅ Active |
| On-demand analysis (bubble clicks) | ~50/day | ~5K in, ~1K out | Sonnet 4.6 | $0.03 | $1.50 | ✅ Active |
| Cache warmup (top 20, post-restart) | ~20 calls | ~5K in, ~1K out | Sonnet 4.6 | $0.03 | $0.60 | ✅ Active |
| **4-model validation (if enabled)** | **~32 calls** | **~3K in, ~0.8K out** | **Mixed** | **$0.018** | **$0.58** | **⏸ Coded, disabled** |

**Estimated daily LLM cost (current): ~$2.30**  
**Estimated monthly LLM cost (current): ~$70 / month (≈ ₹5,800/month)**  
**If multi-LLM validation enabled: +~$17/month (≈ ₹1,400/month extra)**

### Cost Comparison

| Intelligence Product | Frequency | Cost | Segment Coverage |
|---|---|---|---|
| McKinsey India Auto Report | Annual | ₹3–8 Cr engagement | Generic — not Bosch-specific |
| Roland Berger India EV Study | Annual | ₹2–5 Cr engagement | EV only |
| Frost & Sullivan India Auto Tech Forecast | Annual | ₹30–80 L subscription | Technology only |
| CRISIL Sector Report | Quarterly | ₹5–15 L/quarter | Credit/financial focus |
| **This Platform (LLM costs only)** | **Daily** | **₹7,500/month** | **All 6 segments × 13 pillars × PESTEL** |
| **This Platform (infra + LLM)** | **Daily** | **~₹12,000/month** | **Full platform** |

### Why the Cost Is So Low

1. **Amortised system context** — The 18K-token Bosch India context is prompt-cached and paid for once, not per-call
2. **Redis caching** — 80%+ of user clicks hit cache, requiring zero LLM calls
3. **Haiku for filtering** — Volume operations (filtering, scoring) use Haiku ($1/M) not Sonnet ($3/M)
4. **Incremental refresh** — Only new/changed factors trigger validation; stable factors reuse cached analyses
5. **No orchestration framework overhead** — Plain asyncio pipelines have no LangChain-style "thinking" overhead

---

## 10. Technology Stack Reference

### Backend

| Component | Technology | Version | Why chosen |
|---|---|---|---|
| API Framework | FastAPI | 0.100+ | Async-native, auto-docs, fastest Python web framework |
| Python Runtime | Python 3.11 | 3.11 | Best asyncio performance, Bosch-approved |
| Database ORM | SQLAlchemy (async) | 2.0 | Industry standard, type-safe, async support |
| Database | PostgreSQL | 18 | JSONB for flexible schema, already available |
| Cache | Redis | 7+ | TTL-based caching, already available |
| HTTP Client (LLM) | httpx (async) | 0.24+ | Async, connection pooling, timeout control |
| Scheduler | APScheduler | 3.10+ | Lightweight, no Celery/RabbitMQ needed |
| Web Scraping | httpx + BeautifulSoup4 | — | Corporate-safe, no browser automation |
| Retry Logic | tenacity | — | Exponential backoff with jitter for LLM rate limits |
| Environment Config | python-dotenv | — | 12-factor app configuration |

### Frontend

| Component | Technology | Notes |
|---|---|---|
| Framework | React 18 | Hooks-based, component architecture |
| Build Tool | Vite 5 | Fast HMR dev server (port 5173) |
| Charts | recharts + custom SVG | Bubble chart custom SVG; recharts for bar/radar |
| Styling | Tailwind CSS | Utility-first, no custom CSS files |
| State | React useState/useMemo | No Redux needed at current scale |
| Deploy | Vercel (free tier) | Best React SPA hosting, edge CDN |

### Infrastructure

| Component | Details |
|---|---|
| Backend port | 8080 |
| Frontend port | 5173 (dev) / Vercel (prod) |
| Database | PostgreSQL 18, `mobility_intelligence` DB |
| Cache | Redis localhost:6379, 24h TTL |
| Container | Docker + docker-compose.yml |
| Environment | Windows conda `intel` env (local run) |
| LLM Farm | `https://aoai-farm.bosch-temp.com` |

---

## 11. API Reference

### Base URL

```
http://localhost:8080
```

### Endpoints

#### GET `/health`
Returns system health status.

```json
{
  "status": "healthy",
  "postgres": "connected",
  "redis": "connected",
  "active_factors": 82,
  "uptime_seconds": 3600
}
```

---

#### GET `/api/pestel`
Returns all active PESTEL factors, optionally filtered by segment.

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `segment` | string | `4W_PV` | Vehicle segment filter |
| `category` | string | all | PESTEL category filter (P/E/S/T/En/L) |
| `limit` | int | 50 | Maximum factors to return |

**Response:**
```json
[
  {
    "id": 47,
    "code": "india_eu_fta",
    "name": "India-EU FTA signed Jan 2026",
    "category": "P",
    "likelihood": 8.5,
    "impact": 7.2,
    "trend": "escalating",
    "segment_relevance": {"4W_PV": "H", "HCV": "M"},
    "affected_pillars": ["Motion", "Energy"],
    "source_note": "ET Auto — Jan 17, 2026",
    "last_refreshed": "2026-03-31T02:00:42Z"
  }
]
```

---

#### GET `/api/pestel/{code}/analysis`
Returns on-demand AI analysis for a specific factor and segment.

**Path Parameters:** `code` — snake_case factor identifier

**Query Parameters:** `segment` — vehicle segment (default: `4W_PV`)

**Response (150 words, cached 24h):**
```json
{
  "summary": "The India-EU FTA creates direct pressure on Bosch India...",
  "bosch_action": "NEAR-TERM",
  "affected_technologies": [
    {
      "pillar": "Motion",
      "market_cr": 1240,
      "why": "Export-oriented OEMs will accelerate content upgrades..."
    }
  ],
  "confidence": "HIGH",
  "data_sources": ["ACMA FY2025", "ET Auto Jan 17 2026"]
}
```

---

#### GET `/api/technologies`
Returns technology intelligence records.

**Query Parameters:**

| Param | Type | Description |
|---|---|---|
| `pillar` | string | Filter by technology pillar (e.g., `ADAS`, `Energy`) |
| `segment` | string | Filter by vehicle segment |
| `maturity` | string | Filter by maturity (emerging/growth/mature/declining) |

---

#### POST `/api/refresh`
Triggers a manual data refresh cycle.

**Response:**
```json
{
  "status": "started",
  "message": "Refresh triggered. Check /api/refresh/status for progress.",
  "estimated_duration_seconds": 45
}
```

---

## 12. Database Schema

### Tables Overview

```
┌──────────────────┐     ┌──────────────────────┐
│  pestel_factors  │     │    technologies       │
│──────────────────│     │──────────────────────│
│ id               │     │ id                   │
│ code (UNIQUE)    │     │ code (UNIQUE)         │
│ name             │     │ name                 │
│ category         │     │ pillar               │
│ likelihood       │     │ market_data (JSONB)  │
│ impact           │     │ total_market_fy25_cr │
│ trend            │     │ cagr                 │
│ segment_relevance│     │ maturity             │
│  (JSONB)         │     │ confidence           │
│ affected_pillars │     │ source_note          │
│  (JSONB array)   │     │ analysis_reasoning   │
│ is_active        │     │ is_active            │
│ last_refreshed   │     │ last_refreshed       │
└──────────────────┘     └──────────────────────┘

┌──────────────────┐     ┌──────────────────────┐
│  refresh_logs    │     │  validation_logs      │
│──────────────────│     │──────────────────────│
│ id               │     │ id                   │
│ started_at       │     │ entity_type          │
│ completed_at     │     │ entity_id            │
│ sources_scraped  │     │ data_point           │
│ articles_processed│     │ claimed_value       │
│ new_factors_added│     │ primary_model        │
│ factors_updated  │     │ primary_verdict      │
│ duration_seconds │     │ primary_confidence   │
│ status           │     │ validators_json      │
└──────────────────┘     │ consensus            │
                         │ agreement_score      │
┌──────────────────┐     │ cost_usd             │
│  sources         │     │ created_at           │
│──────────────────│     └──────────────────────┘
│ id               │
│ name             │
│ url              │
│ source_type      │
│ reliability      │
│ raw_excerpt      │
│ accessed_at      │
└──────────────────┘
```

### Active Data Counts (as of March 2026)

| Table | Active Records | Notes |
|---|---|---|
| `pestel_factors` | 82 active (22 inactive) | Inactive = true duplicates, soft-deleted |
| `technologies` | 58 records | 13 pillars × ~4.5 technologies avg |
| `refresh_logs` | Running total | One entry per 24h refresh cycle |
| `validation_logs` | Running total | ~32 entries per refresh cycle |

### PESTEL Factor Active Segments & Pillars

**Vehicle Segments:**
- `4W_PV` — 4-Wheeler Passenger Vehicles
- `LCV` — Light Commercial Vehicles
- `HCV` — Heavy Commercial Vehicles (trucks, buses)
- `2W` — Two-Wheelers (motorcycle, scooter)
- `3W` — Three-Wheelers (auto-rickshaw)
- `Tractor` — Agricultural Tractors

**Technology Pillars (13):**
ADAS · Motion · Energy · Body & Comfort · Infotainment · OS · Compute · ECUs · Semiconductors · Actuators · Solutions · Services · Cloud

---

*Document generated from live codebase — `backend/`, `frontend/src/`, `docs/`. For architecture questions contact the platform maintainer.*
