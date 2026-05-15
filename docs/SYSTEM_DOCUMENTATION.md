# Mobility Intelligence Platform — System Documentation

**Version:** 1.0  
**Date:** March 2026  
**Owner:** Bosch Mobility Solutions — Strategic Intelligence  
**Audience:** Compliance, AI Deployment, Architecture Review

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Business Purpose](#2-business-purpose)
3. [System Architecture](#3-system-architecture)
4. [Technology Stack](#4-technology-stack)
5. [AI & LLM Usage](#5-ai--llm-usage)
6. [Data Sources & Web Scraping](#6-data-sources--web-scraping)
7. [Data Models & Storage](#7-data-models--storage)
8. [Agent System Design](#8-agent-system-design)
9. [API Endpoints](#9-api-endpoints)
10. [Security & Access Control](#10-security--access-control)
11. [Cost Tracking & Controls](#11-cost-tracking--controls)
12. [Observability & Logging](#12-observability--logging)
13. [Operational Runbook](#13-operational-runbook)
14. [Compliance Considerations](#14-compliance-considerations)
15. [Known Limitations](#15-known-limitations)

---

## 1. Executive Summary

The Mobility Intelligence Platform is an internal analytics tool that aggregates market intelligence about India's automotive component industry and presents it to Bosch strategic decision-makers through an interactive web dashboard.

**What it does:**
- Monitors 6 public web sources for industry news every 24 hours (daily)
- Uses AI (Claude Sonnet 4.6 via Bosch LLM Farm) to identify and score PESTEL factors
- Tracks 58 technology markets across 13 Bosch pillars and 6 vehicle segments
- Presents all data through three interactive dashboard views

**What it does NOT do:**
- Does not access any internal Bosch systems or confidential data
- Does not store or process personal data (no PII)
- Does not make autonomous business decisions — all output is advisory
- Does not interact with any production systems

---

## 2. Business Purpose

### Problem Statement
Bosch strategic planners need continuous awareness of macro forces (regulatory, economic, technological) affecting India's auto component industry. Previously this required manual research across 6+ sources, taking 2–4 hours per week per analyst.

### Solution
An automated platform that:
1. Scrapes public industry sources daily (every 24 hours)
2. Uses AI to extract and score relevant PESTEL factors
3. Validates AI outputs with a second independent LLM check (dual consensus)
4. Presents findings through an interactive bubble chart dashboard

### Users
Internal Bosch Mobility Solutions team — strategic planners, market analysts, leadership.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER BROWSER                             │
│              React 18 + Vite (localhost:5173-5176)               │
└──────────────────────────────┬──────────────────────────────────┘
                                │ HTTP REST API
┌──────────────────────────────▼──────────────────────────────────┐
│                      FASTAPI BACKEND (port 8000)                  │
│                                                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────────┐ │
│  │ API Routes  │  │  Scheduler  │  │    Agent Orchestrator    │ │
│  │ /pestel     │  │ (every 24h) │  │  coordinates all agents  │ │
│  │ /techs      │  └──────┬──────┘  └────────────┬─────────────┘ │
│  │ /analysis   │         │                      │               │
│  │ /refresh    │         └──────────────────────┘               │
│  │ /health     │                      │                         │
│  └─────────────┘                      │                         │
│                          ┌────────────▼─────────────┐           │
│                          │       Agent Pipeline      │           │
│                          │  1. Web Intelligence Svc  │           │
│                          │  2. PESTEL Discovery Agent│           │
│                          │  3. Validation Agent      │           │
│                          └────────────┬─────────────┘           │
└───────────────────────────────────────┼─────────────────────────┘
                                        │
        ┌───────────────────────────────┼───────────────────────┐
        │                               │                       │
┌───────▼───────┐          ┌────────────▼──────────┐  ┌────────▼───────┐
│  PostgreSQL   │          │   Bosch LLM Farm       │  │    Redis       │
│  Port 5432    │          │   (Corporate Proxy)    │  │   Port 6379    │
│               │          │   → Anthropic Claude   │  │   Analysis     │
│  - PESTEL     │          │   → OpenAI GPT         │  │   Cache        │
│  - Technologies│         │   → Embeddings         │  │   TTL: 24h     │
│  - Validation │          └───────────────────────-┘  └────────────────┘
│    Logs       │
│  - Refresh    │
│    Logs       │
└───────────────┘
```

### Infrastructure
All services run on the developer's local machine (or can be containerised via Docker Compose). No cloud infrastructure is provisioned by this application — it uses existing Bosch internal services (LLM Farm, PostgreSQL, Redis).

---

## 4. Technology Stack

### Backend
| Component | Library/Version | Purpose |
|---|---|---|
| Web framework | FastAPI 0.115.0 | Async REST API with auto-generated docs |
| ASGI server | uvicorn 0.30.0 | Production-grade Python HTTP server |
| Data validation | pydantic 2.9.0 | Request/response schema validation |
| Settings | pydantic-settings 2.5.0 | Environment variable management |
| Database driver | asyncpg 0.29.0 | Async PostgreSQL client (fastest available) |
| ORM | SQLAlchemy 2.0.35 | Database query builder + async sessions |
| DB migrations | alembic 1.13.0 | Schema version control |
| Cache client | redis[hiredis] 5.1.0 | Async Redis client with C extension parser |
| HTTP client | httpx 0.27.0 | Async HTTP for LLM calls and web scraping |
| HTML parsing | beautifulsoup4 4.12.3 | Parses news articles and HTML pages |
| XML parsing | lxml 5.3.0 | RSS feed parsing |
| Task scheduler | apscheduler 3.10.4 | Background job scheduling (6h refresh) |
| Retry logic | tenacity 9.0.0 | Automatic retry with backoff for LLM calls |
| Env loading | python-dotenv 1.0.1 | Load `.env` secrets |
| Date parsing | python-dateutil 2.9.0 | Parse article publication dates |

**Python version:** 3.11+ (conda env: `intel`)

**No LangChain, LangGraph, or similar AI framework is used.** All LLM calls are plain HTTP via `httpx`. This was a deliberate architectural decision for auditability, security, and dependency minimisation.

### Frontend
| Component | Library/Version | Purpose |
|---|---|---|
| Build tool | Vite 5.4.21 | Dev server + production bundler |
| UI framework | React 18 | Component-based UI |
| Language | JavaScript (JSX) | No TypeScript used |
| Charting | Custom SVG | Bubble charts rendered directly in SVG |
| HTTP | Browser fetch API | Calls backend REST API |

### Infrastructure
| Component | Technology | Purpose |
|---|---|---|
| Database | PostgreSQL 16 | All persistent data storage |
| Cache | Redis 7 | Analysis result caching, TTL-based |
| Containerisation | Docker + Docker Compose | Optional local deployment |
| LLM Gateway | Bosch LLM Farm (`aoai-farm.bosch-temp.com`) | Corporate-approved AI proxy |

---

## 5. AI & LLM Usage

### LLM Provider
All AI calls route through **Bosch LLM Farm** (`aoai-farm.bosch-temp.com`) — the Bosch corporate AI proxy. No direct calls to Anthropic or OpenAI are made. The platform uses Bosch-approved API keys managed through the LLM Farm.

### Models Used

| Model | Task Tier | Usage |
|---|---|---|
| `claude-sonnet-4-6` | CRITICAL | PESTEL discovery, analysis generation, detail reports shown to users |
| `claude-haiku-4-5` | HIGH | Scoring, filtering, tech category scan (light-cost scout tasks) |
| `claude-sonnet-4-5` | FALLBACK | Automatic fallback if Sonnet 4.6 is rate-limited |
| `gpt-5.2-2025-12-11` | VALIDATOR | Parallel validation of newly discovered PESTEL factors |
| `grok-4-fast-reasoning` | VALIDATOR | Parallel validation of newly discovered PESTEL factors |
| `google-gemini-2-5-pro` | VALIDATOR | Parallel validation of newly discovered PESTEL factors |
| `gpt-5-mini` | VOLUME | Reserved for batch sentiment tasks (not yet active) |
| `text-embedding-3-small` | EMBEDDING | Reserved for semantic search (not yet active) |

### Prompt Caching
The system prompt (~18,000 tokens, containing India auto industry baseline data) is cached using Anthropic's prompt caching feature. After the first call in a 5-minute window, subsequent calls pay 10% of the normal input price for the system portion. This reduces LLM cost by approximately 70%.

### Cost per Operation

| Operation | LLM Calls | Estimated Cost |
|---|---|---|
| Full data refresh | 40–50 Sonnet calls | $1.00–$2.00 |
| Single bubble click (PESTEL analysis) | 1 Sonnet call | $0.04–$0.07 |
| Single bubble click (Tech analysis) | 1 Sonnet call | $0.04–$0.07 |
| Validation of 1 new factor (during refresh) | 4 calls parallel (Sonnet + GPT-5.2 + Grok4 + Gemini2.5) | $0.10–$0.25 |
| Post-refresh cache warmup (all 6-segment analyses) | 6×(PESTEL+techs) Sonnet calls | ~$8–$12 |

### Fallback Chain
If the primary model fails (rate limit, timeout):
```
claude-sonnet-4-6  →  claude-sonnet-4-5  →  claude-haiku-4-5
```
Fallbacks are automatic and logged with `⚠️ FALLBACK` in the terminal.

### Multi-LLM Validation (4-Model Parallel Consensus)
For newly discovered PESTEL factors, a four-model parallel consensus check is applied:

```
New factor discovered by Sonnet 4.6 (primary)
         │
         └─► 3 validators run in PARALLEL via asyncio.gather:
               ├─► GPT-5.2         (LLM Farm, Bearer auth)
               ├─► Grok 4 Fast     (Azure AI endpoint, api-key auth)
               └─► Gemini 2.5 Pro  (LLM Farm, subscription-key auth)
               Each returns: CONFIRMED / DISPUTED / UNCERTAIN + confidence
                        │
                        ▼
              Consensus Engine (primary + 3 validators)
              ├─ All 3 validators agree with primary → VERIFIED ✅
              ├─ 2/3 validators agree                → VERIFIED ⚠️ (use with mild caution)
              ├─ 1/3 validators agree                → FLAGGED 🟡
              └─ 0/3 validators agree                → REJECTED ❌
```

Validation logs are stored permanently in the `validation_logs` PostgreSQL table. The `validator_model` column stores `multi: gpt-5.2 | grok-4 | gemini-2.5` and `validator_reasoning` stores a JSON array of per-model verdicts and reasoning.

### What AI is Allowed to Do
- Identify PESTEL factors from scraped news text
- Score factors on Likelihood (1–10) and Impact (1–10) scales
- Generate strategic analysis narratives for each factor/technology
- Suggest which Bosch pillars are affected by each factor

### What AI is NOT Allowed to Do
- Make investment or procurement decisions
- Access internal Bosch financial or product data
- Generate or modify code in production environments
- Execute any system commands or database writes autonomously (only via controlled API routes)

---

## 6. Data Sources & Web Scraping

### Sources Scraped

| Source | URL type | Category | Reliability |
|---|---|---|---|
| ET Auto | RSS feed | Industry news | High |
| Livemint Auto | RSS feed | Industry news | High |
| ACMA Press Releases | HTML | Industry body | High |
| SIAM Statistics | HTML | Industry body | High |
| MoRTH Notifications | HTML | Government | High |
| IBEF Auto Sector | HTML | Government agency | High |

### Scraping Policy
- **Only public pages** — no login, no credentials, no paywalls bypassed
- **Honest identification** — `User-Agent: MobilityIntelligencePlatform/1.0 (Research; contact@bosch.com)`
- **Request rate** — maximum 1 request per source per 6-hour cycle (no aggressive scraping)
- **No JavaScript execution** — static HTML/RSS only (no headless browser, no Selenium)
- **Timeout** — 30 seconds per request; failed sources are skipped, not retried
- **No personal data** — all sources are industry/market data, zero PII

### Scraping Frequency
Automated every **24 hours** (daily, aligned to industry news cycles) via APScheduler. Can be triggered manually via `POST /api/refresh/full` with admin key.

---

## 7. Data Models & Storage

### PostgreSQL Database: `mobility_intelligence`

#### Table: `pestel_factors`
Stores all PESTEL factors (currently 53 active).

| Column | Type | Description |
|---|---|---|
| `code` | VARCHAR UNIQUE | URL-safe identifier e.g. `india_eu_fta` |
| `name` | VARCHAR | Human-readable factor name |
| `category` | VARCHAR | `P` / `E` / `S` / `T` / `En` / `L` |
| `selection_reasoning` | TEXT | Why this factor was selected by AI |
| `likelihood` | FLOAT | 1–10 score |
| `likelihood_reasoning` | TEXT | AI's reasoning for the score |
| `impact` | FLOAT | 1–10 score |
| `impact_reasoning` | TEXT | AI's reasoning for the score |
| `segment_relevance` | JSONB | `{"4W_PV": "H", "2W": "M", ...}` |
| `affected_pillars` | JSONB | `["ADAS", "Energy", ...]` |
| `is_active` | BOOLEAN | Soft delete only — records never hard-deleted |

#### Table: `technologies`
Stores all technology markets (currently 58 active).

| Column | Type | Description |
|---|---|---|
| `code` | VARCHAR UNIQUE | URL-safe identifier |
| `pillar` | VARCHAR | One of 13 Bosch dashboard pillar IDs |
| `market_data` | JSONB | `{"4W_PV": {"fy25": 1200, "fy30": 3400, "cagr": 23.2}, ...}` |
| `maturity` | VARCHAR | `emerging` / `growth` / `mature` / `declining` |

#### Table: `validation_logs`
Permanent audit trail for every dual-LLM validation.

| Column | Type | Description |
|---|---|---|
| `entity_type` | VARCHAR | `pestel_factor` / `technology` |
| `data_point` | VARCHAR | What was validated (e.g. `exports_fy25`) |
| `claimed_value` | TEXT | The value that was checked |
| `primary_model` | VARCHAR | Model that ran first check |
| `primary_verdict` | VARCHAR | `CONFIRMED` / `DISPUTED` / `UNCERTAIN` |
| `validator_model` | VARCHAR | Model that ran second check |
| `validator_verdict` | VARCHAR | Same scale |
| `consensus` | VARCHAR | `VERIFIED` / `FLAGGED` / `REJECTED` / `HUMAN_REVIEW` |
| `consensus_reasoning` | TEXT | Explanation of consensus outcome |
| `created_at` | TIMESTAMPTZ | Immutable timestamp |

#### Table: `refresh_logs`
Audit trail for every data refresh cycle.

| Column | Description |
|---|---|
| `trigger_type` | `scheduled` / `manual` |
| `status` | `completed` / `failed` |
| `new_factors` | Count of new PESTEL factors discovered |
| `llm_calls_made` | Total LLM calls in this refresh |
| `estimated_cost_usd` | Estimated USD cost of this refresh |

### Redis Cache
- Key format: `pestel:{factor_code}:{segment}` and `tech:{tech_code}:{segment}`
- TTL: **24 hours** (all analysis results)
- Max memory: 256 MB with LRU eviction policy
- Cache is invalidated automatically when the scheduler refreshes data
- No sensitive data stored in cache — only AI-generated analysis JSON

---

## 8. Agent System Design

### Agent 1: Web Intelligence Service (`web_intelligence.py`)
**Role:** Fetches raw text from public web sources  
**Input:** List of configured news sources  
**Output:** Concatenated text (typically 10,000–20,000 characters of recent news)  
**LLM calls:** 0 (pure HTTP + HTML parsing)

### Agent 2: PESTEL Discovery Agent (`pestel_agent.py`)
**Role:** Reads scraped news and identifies new PESTEL factors  
**Input:** Web text + list of already-known factor names (deduplication)  
**Output:** List of new factor candidates with scores and reasoning  
**LLM calls:** 1–2 Sonnet calls per refresh  
**Prompt:** Instructs model to identify macro forces affecting India auto components, score Likelihood × Impact, assign PESTEL category and segment relevance

### Agent 3: Validation Agent (`validation_agent.py`)
**Role:** Independently verifies newly discovered data points with two LLMs  
**Input:** A data point (claim + context + source)  
**Output:** Consensus verdict with full reasoning from both models  
**LLM calls:** 2 per factor validated (Sonnet + Haiku)  
**Applied to:** Top 10 new factors per refresh cycle  
**All results logged to:** `validation_logs` table

### Agent 4: Orchestrator (`orchestrator.py`)
**Role:** Coordinates all agents for both scheduled refresh and on-demand analysis  
**Two modes:**

**Mode 1 — Scheduled/Manual Refresh:**
```
Web scrape → PESTEL discovery → Validation → PostgreSQL store → Redis invalidate → Refresh log
```

**Mode 2 — On-demand Analysis (bubble click):**
```
Check Redis cache → HIT: return immediately → MISS: Sonnet call → Cache result → Return
```

### LLM Service (`llm_service.py`)
Central singleton for all LLM interactions. Features:
- Automatic retry (3 attempts, exponential backoff)
- Prompt caching (saves ~70% on system prompt cost)
- Model fallback chain (Sonnet 4.6 → Sonnet 4.5 → Haiku 4.5)
- Full cost tracking (per call and cumulative)
- JSON response parsing with truncation recovery

---

## 9. API Endpoints

All endpoints are REST, served on `http://localhost:8000`. Auto-documentation available at `/docs`.

### Public Endpoints (no auth required)

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | System health — DB, Redis, LLM call count, total cost |
| GET | `/api/pestel/?segment=4W_PV` | All PESTEL factors for a segment |
| GET | `/api/techs/?segment=4W_PV` | All technologies with market data |
| GET | `/api/analysis/pestel/{code}?segment=` | AI analysis for one PESTEL factor |
| GET | `/api/analysis/tech/{code}?segment=` | AI analysis for one technology |
| GET | `/api/analysis/validation/{type}/{id}` | Full validation audit trail |
| GET | `/api/refresh/status` | Last refresh status and timing |
| GET | `/api/refresh/logs` | History of all refresh cycles |

### Admin Endpoints (require `X-Admin-Key` header)

| Method | Path | Description |
|---|---|---|
| POST | `/api/refresh/full` | Trigger full data refresh (~$1–2 cost) |
| POST | `/api/refresh/cache/clear` | Clear all Redis cache |
| POST | `/api/analysis/warmup?segment=` | Pre-generate all analyses for a segment |

### Segments Available
`4W_PV`, `2W`, `3W`, `LCV`, `HCV`, `Tractor`

---

## 10. Security & Access Control

### Authentication
- **Public endpoints:** No authentication. All data returned is internal analysis — no sensitive business data is exposed.
- **Admin endpoints (refresh, cache clear, warmup):** Protected by `X-Admin-Key` header. Current key: `mi-admin-refresh-2026`. **This should be rotated and stored in `.env` before any shared deployment.**

### Secrets Management
All secrets are in `.env` file (not committed to version control):
- `LLM_FARM_API_KEY` — Bosch LLM Farm API key
- `POSTGRES_PASSWORD` — Database password
- `REDIS_URL` — Redis connection string

### CORS Policy
Allowed origins: `localhost:3000`, `localhost:5173`, `localhost:5174`, `localhost:5175`, `localhost:5176`  
In production, this must be restricted to the actual deployment domain.

### No PII Processing
The system processes no personal data. All inputs are public industry news and market data. All outputs are strategic analysis.

### External Network Calls
The backend makes outbound calls to:
1. `aoai-farm.bosch-temp.com` — Bosch internal LLM Farm (approved)
2. `auto.economictimes.indiatimes.com` — Public RSS
3. `livemint.com` — Public RSS
4. `acma.in` — Public HTML (industry body)
5. `siam.in` — Public HTML (industry body)
6. `morth.nic.in` — Public HTML (Government of India)
7. `ibef.org` — Public HTML (government agency)

No calls to any other external services.

---

## 11. Cost Tracking & Controls

### Budget Controls
- Manual refresh is admin-key protected — users cannot trigger LLM spending
- Automatic refresh runs once per day (1/day × ~$2.50 = ~$2.50/day maximum)
- Per-call cost is logged in real-time; cumulative cost visible at `/api/health`
- `refresh_logs` table records cost per refresh cycle for audit

### Cost Visibility
```
GET /api/health
{
  "llm_calls_total": 6,
  "llm_cost_total_usd": 0.31,
  "status": "healthy"
}
```

### Approximate Monthly Cost Estimate

| Item | Quantity | Unit Cost | Monthly |
|---|---|---|---|
| Scheduled refresh | 4/day × 30 days = 120 | $1.50 avg | $180 |
| User bubble clicks (first-time only) | ~20/day | $0.05 | $30 |
| Post-refresh warmup (6 segments × all analyses) | 1/day, auto after refresh | ~$0.40 | ~$12 |
| **Total (with post-refresh full warmup)** | | | **~$100/month** |
| **Total (click-to-warm, no post-refresh warmup)** | | | **~$88/month** |

Prompt caching reduces the above by approximately 60–70% in practice.

---

## 12. Observability & Logging

### Log Format
```
HH:MM:SS | module_name         | LEVEL | message
```

### Log Modules and Levels

| Module | Level | What it logs |
|---|---|---|
| `main` | INFO | Startup, shutdown, config summary |
| `orchestrator` | DEBUG | Cache hits/misses, step progress, refresh summary |
| `pestel_agent` | DEBUG | Discovery results, scoring |
| `validation_agent` | DEBUG | Consensus decisions per factor |
| `llm_service` | DEBUG | Every LLM call: model, tokens, cost, latency, cache hit/miss |
| `web_intelligence` | DEBUG | Every source scraped: chars, HTTP status, latency |
| `source_tracker` | DEBUG | Source provenance events |

### Log Examples

**LLM call:**
```
12:09:03 | llm_service | INFO | 🤖 LLM CALL #1 │ Model: claude-sonnet-4-6 │ In: 1548 tok (cached: 0) │ Out: 3653 tok │ Cost: $0.0594 │ Latency: 88.0s │ Cache: MISS │ Cumulative: $0.0594 (1 calls)
```

**Web scrape:**
```
10:55:02 | web_intelligence | INFO | 🌐 SCRAPED │ ET Auto │ 6241 chars │ Status: 200 │ Latency: 0.8s
```

**Validation:**
```
10:55:15 | validation_agent | INFO | 🔍 VALIDATION │ general/india_exports │ Primary: 4-6 → CONFIRMED (HIGH) │ Validator: 4-5 → CONFIRMED (HIGH) │ Consensus: VERIFIED ✅
```

**LLM fallback:**
```
10:55:20 | llm_service | WARNING | ⚠️ FALLBACK │ claude-sonnet-4-6 → claude-sonnet-4-5 │ Reason: HTTP 529
```

### Database Audit Logs
Beyond terminal logs, the following are permanently stored in PostgreSQL:
- Every validation decision → `validation_logs` table
- Every refresh cycle (timing, cost, new factors) → `refresh_logs` table

---

## 13. Operational Runbook

### Starting the System

**Step 1 — Activate environment and start backend:**
```powershell
conda activate intel
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Step 2 — Start frontend (in a separate terminal):**
```powershell
cd frontend
npm run dev
```

**Step 3 — Open browser:**  
Navigate to `http://localhost:5173` (or 5174/5175 if that port is taken).

### Pre-Demo Cache Warmup
Run this once before a presentation to ensure all bubbles respond instantly:
```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/analysis/warmup?segment=4W_PV" -Headers @{"X-Admin-Key"="mi-admin-refresh-2026"}
```
Watch the uvicorn terminal. Takes ~15–25 minutes. Cache valid for 24 hours.

### Triggering a Manual Data Refresh
```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/refresh/full" -Headers @{"X-Admin-Key"="mi-admin-refresh-2026"}
```

### Clearing the Cache
```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/refresh/cache/clear" -Headers @{"X-Admin-Key"="mi-admin-refresh-2026"}
```

### Checking System Health
```powershell
Invoke-RestMethod "http://localhost:8000/api/health" | ConvertTo-Json
```

### Viewing Refresh History
```powershell
Invoke-RestMethod "http://localhost:8000/api/refresh/logs" | ConvertTo-Json -Depth 5
```

### Docker Deployment (optional)
```powershell
docker-compose up -d
docker-compose logs -f api   # Watch backend logs
```

---

## 14. Compliance Considerations

### Data Handling
| Data Category | Stored? | Details |
|---|---|---|
| Personal data (PII) | ❌ No | Platform processes no personal information |
| Internal Bosch data | ❌ No | All feeds are public industry sources |
| User session data | ❌ No | No login, no sessions, no tracking |
| LLM prompts | ✅ Partial | System prompt stored in code; user queries are transient |
| AI-generated analysis | ✅ Yes | Stored in Redis (24h TTL) and queryable via API |
| Source provenance | ✅ Yes | `sources` table records every scraped URL + excerpt |
| Validation decisions | ✅ Yes | `validation_logs` — permanent, with full LLM reasoning |

### AI Transparency
- Every AI-generated output includes `_meta.model`, `_meta.cost_usd`, `_meta.generated_at`
- Dual-LLM validation with stored reasoning addresses "black box" concerns
- The system prompt and all prompts are in `backend/agents/prompts/system_context.py` and are fully auditable

### AI is Advisory Only
This platform is an **intelligence aggregation tool**. All AI outputs are:
- Labelled as AI-generated
- Based on public data sources (traceable)
- Validated by a second independent LLM
- Intended for human review and decision-making — not autonomous action

### Regulatory Touchpoints
- **EU AI Act:** This system is a standard AI-assisted analytics tool, not a high-risk AI system under Article 6 classification. It does not affect employment, credit, access to services, or safety-critical domains.
- **GDPR:** No personal data processed or stored. Not applicable.
- **Bosch AI Guidelines:** Uses only Bosch LLM Farm (approved). No direct consumer-facing AI interaction. Human-in-the-loop for all strategic decisions.

### Intellectual Property
- All scraped content is from publicly available sources; excerpts only (100 lines max per source)
- AI analysis is original output, not a reproduction of source material
- No paywalled content is accessed

---

## 15. Known Limitations

| Limitation | Detail | Mitigation |
|---|---|---|
| LLM response latency | First bubble click takes 60–90s via Bosch LLM Farm | Startup warmup pre-caches top 15 factors; 24h TTL means most clicks are instant |
| JSON truncation risk | Very detailed factors may hit token limits and return incomplete JSON | `max_tokens=6000` + automatic JSON recovery in parser |
| Source scraping reliability | Some HTML sources (ACMA, SIAM) may block or restructure | Failed sources are skipped gracefully; RSS sources are more stable |
| Post-refresh warmup coverage | `post_refresh_warmup()` runs for all 6 segments × all PESTEL + tech codes after each nightly refresh | On startup, only top-15 factors for 4W_PV are pre-cached; the full warmup runs automatically after the nightly refresh completes |
| No authentication for read endpoints | Any user on the network can read analysis data | Acceptable for internal use; add JWT/SSO before public deployment |
| Admin key in code | `ADMIN_KEY = "mi-admin-refresh-2026"` is hardcoded fallback | Move to `.env` and rotate before production deployment |
| Prompt caching cold start | First LLM call after 5 minutes pays full system prompt price | Accounted for in cost estimates; prompt cache warms quickly |
| No data versioning | Updating a PESTEL factor does not keep its history | `is_active` flag allows soft delete; audit via `refresh_logs` |

---

*Document maintained by the Bosch Mobility Intelligence Platform team.*  
*For questions: refer to the `docs/ARCHITECTURE.md` for implementation detail, or the source code — every module has inline documentation.*
