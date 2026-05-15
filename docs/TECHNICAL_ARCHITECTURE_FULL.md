# Mobility Intelligence Platform
## Full Technical Architecture & Operations Guide
### Prepared for: Cloud Deployment, Stress Testing & Internal Hosting Review
### Date: April 2026 | Status: Production-ready (v3)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [High-Level Architecture Diagram](#2-high-level-architecture-diagram)
3. [Technology Stack — Complete Inventory](#3-technology-stack--complete-inventory)
4. [Frontend Architecture](#4-frontend-architecture)
5. [Backend Architecture](#5-backend-architecture)
6. [AI Agent System & LLM Workflows](#6-ai-agent-system--llm-workflows)
7. [LLM Services & Models Used](#7-llm-services--models-used)
8. [Database Schema & Data Model](#8-database-schema--data-model)
9. [Caching Layer](#9-caching-layer)
10. [Web Intelligence / Data Ingestion Pipeline](#10-web-intelligence--data-ingestion-pipeline)
11. [API Reference](#11-api-reference)
12. [Data Flow — End to End](#12-data-flow--end-to-end)
13. [Deployment Architecture (Docker / Cloud)](#13-deployment-architecture-docker--cloud)
14. [Environment Configuration](#14-environment-configuration)
15. [Maintenance & Operations Runbook](#15-maintenance--operations-runbook)
16. [Stress Testing Guidelines](#16-stress-testing-guidelines)
17. [Security Considerations](#17-security-considerations)
18. [Known Limitations & Technical Debt](#18-known-limitations--technical-debt)

---

## 1. System Overview

**Product name:** Mobility Intelligence Platform
**Purpose:** An agentic AI dashboard providing strategic market intelligence for India's automotive component industry. Covers Bosch Mobility Solutions' 13 technology pillars across 6 vehicle segments.

**What it does:**
- Continuously scrapes 10+ public industry sources (ACMA, SIAM, MoRTH, ET Auto, Livemint, IBEF, Vahan, Autocar India, Overdrive India)
- Uses Claude Sonnet 4.6 to discover and score PESTEL factors (Political, Economic, Social, Technological, Environmental, Legal) from live news
- Uses Claude Haiku 4.5 to validate and classify discovered factors
- Uses GPT-5.4, Grok 4, and Gemini 2.5 Pro as independent validator models
- Serves a React single-page application with four interactive analysis views
- Caches all AI analysis results in Redis to minimise repeat LLM calls

**Current data scope:**
- ~30–40 active PESTEL factors, refreshed every 24 hours
- Technology market data across 13 pillars × 6 segments (FY25 actuals + FY30 projections)
- Competitor landscape: 12 tier-1 global suppliers, 250+ pillar×segment share records, 630+ technology×segment share records, 99 OEM sourcing rows
- All figures in INR Crore; optional EUR conversion at runtime

**Intended users:** Bosch Mobility Solutions India — Strategy, Sales, R&D leadership teams.

---

## 2. High-Level Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                          USER BROWSER                                   │
│  React 18 SPA (Vite dev server or static build)                        │
│  Single JSX file: mobility-intelligence-platform-live.jsx (~1700 lines)│
│  Port: 5173 (dev) | Static files (prod)                                │
└───────────────────────────┬────────────────────────────────────────────┘
                            │  HTTP REST  (JSON)
                            │  API_BASE = http://<host>:8000
                            ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   FASTAPI APPLICATION (backend/)                        │
│   Uvicorn ASGI server · Python 3.11 · Port 8000                        │
│                                                                         │
│  ┌─────────────────────────────────────────────────────┐               │
│  │  API LAYER  (backend/api/)                          │               │
│  │  pestel.py · technology.py · analysis.py            │               │
│  │  refresh.py · competitors.py                        │               │
│  └──────────────┬──────────────────────────────────────┘               │
│                 │                                                        │
│  ┌──────────────▼──────────────────────────────────────┐               │
│  │  AGENT LAYER  (backend/agents/)                     │               │
│  │  orchestrator.py   — coordinates all agents         │               │
│  │  pestel_agent.py   — discover / score PESTEL        │               │
│  │  validation_agent.py — multi-LLM consensus          │               │
│  │  tech_agent.py     — technology market scan         │               │
│  └──────────────┬──────────────────────────────────────┘               │
│                 │                                                        │
│  ┌──────────────▼──────────────────────────────────────┐               │
│  │  SERVICE LAYER  (backend/services/)                 │               │
│  │  llm_service.py      — unified LLM client           │               │
│  │  cache_service.py    — Redis abstraction            │               │
│  │  web_intelligence.py — HTTP scraper                 │               │
│  │  source_tracker.py   — provenance chain             │               │
│  └──────────────┬───────────────────┬──────────────────┘               │
│                 │                   │                                   │
└─────────────────┼───────────────────┼───────────────────────────────────┘
                  │                   │
    ┌─────────────▼──────┐  ┌─────────▼──────────┐
    │   PostgreSQL 16    │  │    Redis 7-alpine   │
    │   Port 5432        │  │    Port 6379        │
    │   mobility_intel.. │  │    maxmem: 256 MB   │
    │   (6 tables)       │  │    policy: LRU      │
    └────────────────────┘  └────────────────────┘
                  │
    ┌─────────────▼──────────────────────────────────────┐
    │   EXTERNAL LLM SERVICES  (via Bosch LLM Farm)      │
    │                                                     │
    │   aoai-farm.bosch-temp.com  (primary proxy)        │
    │   ├── Claude Sonnet 4.6   (analysis, discovery)    │
    │   ├── Claude Sonnet 4.5   (fallback tier-1)        │
    │   ├── Claude Haiku 4.5    (validation, scoring)    │
    │   ├── GPT-5.4             (cross-validation)       │
    │   ├── GPT-5-mini          (batch/volume tasks)     │
    │   └── text-embedding-3-small (RAG, future)         │
    │                                                     │
    │   rbinbdo-vismai-mbr-resource.cognitiveservices... │
    │   └── Grok 4 Fast Reasoning  (validator)           │
    └─────────────────────────────────────────────────────┘
```

---

## 3. Technology Stack — Complete Inventory

### 3.1 Frontend

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| UI Framework | React | 18.3.1 | Component rendering, state management |
| Build Tool | Vite | 5.4.2 | Dev server (HMR), production bundler |
| Vite React Plugin | @vitejs/plugin-react | 4.3.1 | JSX transform, Fast Refresh |
| Language | JavaScript (JSX) | ES2022+ | Single file SPA |
| HTTP Client | Native `fetch` API | Browser built-in | API calls to backend |
| Styling | Inline CSS-in-JS | — | Dynamic theming (dark/light mode) |
| Font | DM Sans | Google Fonts CDN | Loaded at runtime via `<link>` |
| State Management | React `useState`, `useEffect`, `useRef`, `useMemo`, `useCallback` | Built-in | No Redux/Zustand — intentionally minimal |

**No external UI component libraries** — all chart bars, cards, and panels are built with plain `<div>` elements and CSS.

### 3.2 Backend — Core Framework

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Web Framework | FastAPI | 0.115.0 | Async REST API, automatic OpenAPI docs |
| ASGI Server | Uvicorn[standard] | 0.30.0 | Serves FastAPI; supports WebSocket, lifespan events |
| Data Validation | Pydantic | 2.9.0 | Request/response models, automatic validation |
| Settings Management | pydantic-settings | 2.5.0 | Load all config from `.env` with type validation |
| Language | Python | 3.11 | Async-first, type-annotated |

### 3.3 Backend — Database

| Technology | Version | Purpose |
|-----------|---------|---------|
| PostgreSQL | 16-alpine (Docker) | Primary data store — PESTEL factors, technologies, competitor data, validation logs, source trail |
| asyncpg | 0.29.0 | Async PostgreSQL driver — fastest Python→Postgres driver available |
| SQLAlchemy (async) | 2.0.35 | Async ORM / connection pool management; `engine` with pool_size=10, max_overflow=20 |
| Alembic | 1.13.0 | Database schema migration management |

### 3.4 Backend — Cache

| Technology | Version | Purpose |
|-----------|---------|---------|
| Redis | 7-alpine (Docker) | AI analysis result cache, rate limiting |
| redis[hiredis] | 5.1.0 | Async Python Redis client with C-extension parser (hiredis — faster than pure Python) |

### 3.5 Backend — HTTP & Scraping

| Technology | Version | Purpose |
|-----------|---------|---------|
| httpx | 0.27.0 | Async HTTP client used for all LLM Farm API calls AND web scraping |
| BeautifulSoup4 | 4.12.3 | HTML parsing — extracts content from ACMA, SIAM, IBEF pages |
| lxml | 5.3.0 | Fast XML/HTML parser backend used by BeautifulSoup4 for RSS and HTML |

### 3.6 Backend — Scheduling & Reliability

| Technology | Version | Purpose |
|-----------|---------|---------|
| APScheduler | 3.10.4 | Background job scheduler; triggers data refresh every 24 hours via `AsyncIOScheduler` |
| tenacity | 9.0.0 | Retry logic with exponential backoff on all LLM API calls (3 attempts, 2–30s wait) |

### 3.7 Backend — Utilities

| Technology | Version | Purpose |
|-----------|---------|---------|
| python-dotenv | 1.0.1 | Load `.env` files during local development |
| python-dateutil | 2.9.0 | Date parsing for news article timestamps |

### 3.8 Infrastructure

| Technology | Version | Purpose |
|-----------|---------|---------|
| Docker | 20.x+ | Containerise backend API |
| Docker Compose | 3.8 | Orchestrate API + PostgreSQL + Redis locally and in cloud |
| Python base image | python:3.11-slim | Lean container for backend |
| PostgreSQL image | postgres:16-alpine | Lean production-grade PostgreSQL |
| Redis image | redis:7-alpine | Lean Redis with 256 MB memory cap |

### 3.9 Python Standard Library modules used

`json`, `logging`, `asyncio`, `re`, `time`, `datetime`, `typing`, `contextlib`, `os`, `sys`

---

## 4. Frontend Architecture

### 4.1 File Structure

```
frontend/
├── package.json              # React 18, Vite 5.4, @vitejs/plugin-react
├── vercel.json               # Static hosting headers (X-Frame-Options, etc.)
├── vite.config.js            # Vite build config
└── src/
    └── mobility-intelligence-platform-live.jsx   # ENTIRE frontend (~1,700 lines)
```

The entire frontend is a single JSX file. There are no separate component files, no routing library, no global state library. This was an intentional design choice for:
- Zero build complexity
- Easy debugging (one file to look at)
- Fast iteration (Vite HMR reloads in < 200ms)

### 4.2 API_BASE Configuration

```javascript
const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? "http://localhost:8000"
  : `http://${window.location.hostname}:8000`;
```

The frontend dynamically derives the backend URL from the browser's hostname. This makes it IP-change-proof — when a developer changes network and gets a new DHCP address, the frontend still finds the backend correctly without any code change.

### 4.3 The Four Views

| View | Name | What it shows | Key API calls |
|------|------|---------------|---------------|
| View 1 | PESTEL Risk Map | Likelihood × Impact bubble chart of 30–40 PESTEL factors. Click a bubble → AI analysis panel slides in. | `GET /api/pestel/?segment=` `GET /api/analysis/pestel/{code}?segment=` |
| View 2 | Technology Stack | Bosch's 13 pillars mapped to PESTEL forces and individual technologies. Visual matrix with hover cards. | `GET /api/techs/?segment=` |
| View 3 | Market Landscape | CAGR × Market Size scatter; FY25→FY30 growth bars; detailed tech panel with AI Agent Analysis. | `GET /api/techs/?segment=` `GET /api/analysis/tech/{code}?segment=` |
| View 4 | Competitor Landscape | Pillar-level market share bars, technology drill-down, cross-segment stacked bars, OEM sourcing. | `GET /api/competitors/pillar?pillar=&segment=` `GET /api/competitors/tech?tech_code=&segment=` |

### 4.4 Data Transformers

The backend returns raw PostgreSQL rows; the frontend transforms them into display structures:

- `transformPestel()` — maps `{code, likelihood, impact, trend, segment_relevance, affected_pillars}` → chart-compatible `{id, cat, pos, rel, pil}` shape
- `transformTechs()` — maps `{code, name, pillar, market_data, cagr, maturity}` → `{n, p, mat, sz, cagr, conf}` shape
- `getSourceConfidence()` — maps source notes to three tiers: Published (green), Derived (orange), Estimate (red)

### 4.5 State Variables (key ones)

```javascript
// Global
const [view, setView] = useState(1);          // active view 1-4
const [seg, setSeg] = useState("4W_PV");       // vehicle segment
const [dk, setDk] = useState(true);            // dark/light theme
const [curr, setCurr] = useState("INR");       // INR / EUR

// API status
const [apiStatus, setApiStatus] = useState("loading");
const [pestelFactors, setPestelFactors] = useState([]);
const [techs, setTechs] = useState([]);

// View 4: Competitor Landscape
const [v4Pillar, setV4Pillar] = useState("ADAS");
const [v4Data, setV4Data] = useState(null);
const [v4TechData, setV4TechData] = useState(null);
const [v4Mode, setV4Mode] = useState("overview");
const [v4DrillTech, setV4DrillTech] = useState(null);
const [v4Loading, setV4Loading] = useState(false);
```

### 4.6 Fallback Strategy

On startup, the frontend hits `GET /api/health`. If the backend is unreachable, it falls back to a hardcoded static JSON dataset embedded in the JSX (the "offline data"), showing a "○ Offline — Fallback Data" status pill. This means the dashboard always has something to show, even if the backend is down.

### 4.7 Theme System

A single `t` object is computed via `useMemo` from the `dk` (dark) flag:

```javascript
const t = useMemo(() => dk ? {
  bg:"#0f172a", card:"#1e293b", btn:"#334155",
  border:"#334155", c:"#f1f5f9", c2:"#94a3b8",
  c3:"#64748b", acc:"#3b82f6", bar:"#1e293b"
} : {
  bg:"#f8fafc", card:"#ffffff", /* ... */
}, [dk]);
```

All inline styles reference `t.bg`, `t.card`, etc., so dark/light switching is instantaneous with no CSS class toggling.

---

## 5. Backend Architecture

### 5.1 File Structure

```
backend/
├── main.py              # FastAPI app factory, CORS, lifespan, route registration
├── config.py            # All settings via pydantic-settings (reads .env)
├── requirements.txt     # All Python dependencies pinned
├── Dockerfile           # python:3.11-slim image
│
├── api/                 # HTTP route handlers (thin layer — no business logic)
│   ├── pestel.py        # GET /api/pestel/
│   ├── technology.py    # GET /api/techs/
│   ├── analysis.py      # GET /api/analysis/pestel/{code} | /tech/{code}
│   ├── refresh.py       # POST /api/refresh/full | /cache/clear
│   └── competitors.py   # GET /api/competitors/pillar | /tech
│
├── agents/              # AI agent logic
│   ├── orchestrator.py  # Coordinates all agents; handles scheduled + on-demand
│   ├── pestel_agent.py  # PESTEL discovery, scoring, filtering
│   ├── validation_agent.py  # Multi-LLM consensus validation
│   ├── tech_agent.py    # Technology category scan
│   └── prompts/
│       ├── system_context.py  # 18K-token shared system prompt (cached)
│       └── __init__.py
│
├── services/            # Infrastructure services
│   ├── llm_service.py   # Unified LLM client for all models
│   ├── cache_service.py # Redis get/set/invalidate abstraction
│   ├── web_intelligence.py  # HTTP scraper for all news/data sources
│   └── source_tracker.py    # Provenance chain management
│
├── db/
│   ├── connection.py    # SQLAlchemy async engine + session factory
│   └── migrations/
│       └── 001_initial.sql  # Full schema (runs on first docker-compose up)
│
├── models/              # Pydantic response models (for API docs)
│
└── scripts/             # One-time admin scripts (not part of the running app)
    ├── seed_competitors.py        # Seeds 12 competitors, 250 pillar shares, 630 tech shares
    ├── fix_skipped_pillar_shares.py
    ├── fix_skipped_tech_shares.py
    ├── fix_adas_camera.py
    └── seed_initial_data.py
```

### 5.2 Application Lifecycle (main.py)

On startup (`lifespan` async context manager):
1. Verify PostgreSQL connection (`SELECT 1`)
2. Verify Redis connection (`PING`)
3. Start APScheduler (`AsyncIOScheduler`) — fires `run_scheduled_refresh()` every 24 hours
4. Launch startup cache warmup (background `asyncio.Task`) — pre-warms top-20 PESTEL factors for 4W_PV segment, sleeping 1.5s between LLM calls to avoid rate-limit bursts

On shutdown:
- `scheduler.shutdown()`
- `llm.close()` (closes httpx clients)
- `cache.close()` (closes Redis pool)
- `engine.dispose()` (closes PostgreSQL connection pool)

### 5.3 Connection Pool Settings

**PostgreSQL (SQLAlchemy):**
- `pool_size=10` — 10 persistent connections always open
- `max_overflow=20` — up to 20 extra during traffic spikes (total max 30)
- `pool_recycle=3600` — recycle connections every hour to prevent stale TCP connections

**Redis:**
- Default `redis-py` connection pool (10 connections)
- `decode_responses=True` — auto-decode bytes to strings

**LLM Farm (httpx):**
- `timeout=300.0s` — 5-minute timeout per LLM call (Sonnet 4.6 can take 60–90s for long prompts)
- Grok 4 client: separate `httpx.AsyncClient`, `timeout=120.0s`

---

## 6. AI Agent System & LLM Workflows

### 6.1 Orchestrator — Two Operating Modes

**Mode 1: Scheduled Data Refresh** (every 24 hours, or `POST /api/refresh/full`)

```
┌─────────────────────────────────────────────────────────────────┐
│  SCHEDULED REFRESH PIPELINE                                      │
│                                                                  │
│  Step 1: Web Intelligence                                        │
│    WebIntelligenceService scrapes 10 sources (RSS + HTML)        │
│    → news_content (text blob), market_data (dict)               │
│                                                                  │
│  Step 2: Load existing factors from PostgreSQL                   │
│    → list of factor names (to avoid duplicates)                 │
│                                                                  │
│  Step 3: PESTEL Agent — Discovery                               │
│    Claude Sonnet 4.6 reads news_content                         │
│    → Returns 40–60 candidate PESTEL factors as JSON             │
│    Claude Haiku 4.5 filters down to ~35 relevant factors        │
│    Claude Sonnet 4.6 details each (likelihood, impact, reasoning│
│                                                                  │
│  Step 3b: Tech Agent — New Technology Scan                       │
│    Claude Haiku 4.5 scans news for tech categories not tracked  │
│    → Flags for manual review only (nothing auto-inserted)       │
│                                                                  │
│  Step 4: Store to PostgreSQL                                     │
│    Upsert pestel_factors; upsert technologies                   │
│                                                                  │
│  Step 4b: Source-Grounded Validation                            │
│    GPT-5.4 reads actual scraped source texts                    │
│    Verifies each new factor's claims against text               │
│    Verdicts: CONFIRMED / PARTIALLY_CONFIRMED / DISPUTED         │
│    If DISPUTED → Sonnet self-corrects before storing            │
│                                                                  │
│  Step 5: Invalidate Redis cache                                  │
│    All pestel:* and tech:* keys flushed                         │
│                                                                  │
│  Step 6: Log refresh stats to refresh_logs table                │
│    (llm_calls_made, estimated_cost_usd, new_factors, duration)  │
└─────────────────────────────────────────────────────────────────┘
```

**Mode 2: On-Demand Analysis** (user clicks a bubble in View 1 or View 3)

```
User clicks factor/tech bubble
       │
       ▼
GET /api/analysis/pestel/{code}?segment=
       │
       ▼
Orchestrator.get_pestel_analysis()
       │
       ├──▶ Cache check: redis GET "mi:pestel:{code}:{segment}"
       │         │
       │    HIT ─┘ → return cached JSON immediately (< 5ms)
       │
       └── MISS → Load factor from PostgreSQL
                     │
                     ▼
                 Call Claude Sonnet 4.6
                 (system: SYSTEM_CONTEXT ~18K tokens, cached)
                 (user: factor details + segment context)
                 max_tokens=3000, temperature=0.2
                     │
                     ▼
                 Parse + structure JSON response
                     │
                     ▼
                 Redis SET with TTL=86400s (24hr)
                     │
                     ▼
                 Return to frontend
                 (first call: 3–8s | repeat: instant)
```

### 6.2 PESTEL Agent Prompt Flow

The PESTEL agent uses three distinct prompt stages:

| Stage | Model | Prompt | Temperature | Max Tokens | Purpose |
|-------|-------|--------|-------------|------------|---------|
| Discovery | Sonnet 4.6 | `PESTEL_DISCOVERY_PROMPT` + news_content (capped 15K chars) | 0.4 | 16,000 | Find new candidate factors from current news |
| Filtering | Haiku 4.5 | Compact JSON candidates list | 0.1 | 2,000 | Eliminate duplicates / off-topic / low-relevance |
| Detail scoring | Sonnet 4.6 | `PESTEL_DETAIL_PROMPT` per factor | 0.3 | 4,096 | Assign likelihood (1–10), impact (1–10) with detailed reasoning |

### 6.3 Validation Agent — Multi-LLM Consensus

Every new data point that passes through discovery goes through source-grounded validation:

```
Factor discovered by Sonnet 4.6
        │
        ▼
GPT-5.4 reads scraped source texts (actual article text)
Checks: "Is this factor's claim supported in the text?"
        │
        ├── CONFIRMED: proceed to store
        │
        ├── PARTIALLY_CONFIRMED: log warning, store with flag
        │
        └── DISPUTED: 
               │
               ▼
           Sonnet 4.6 self-corrects using GPT-5.4's critique
               │
               ▼
           Store corrected version + log both versions
```

All validation runs are written to the `validation_logs` table for full audit trail.

### 6.4 System Prompt Caching

The shared `SYSTEM_CONTEXT` is approximately 18,000 tokens. It contains:
- India auto component industry baseline (FY25 verified numbers)
- Vehicle segment sales data (SIAM/ACMA)
- EV market data (Vahan)
- Key policy context (India-EU FTA, PLI, BS-VI, Bharat NCAP)
- Bosch's 13 technology pillars
- PESTEL scoring rubric

This prompt is sent with `cache_control: {"type": "ephemeral"}` to Anthropic's prompt caching. The cache window is 5 minutes. After the first call:
- Cache miss: costs $3.00/M input tokens
- Cache hit: costs $0.30/M input tokens (~10× cheaper)

With the startup warmup running 20 calls in sequence at 1.5s intervals, the system prompt stays hot for the duration of warmup.

### 6.5 Model Fallback Chain

```
Primary request → Claude Sonnet 4.6
       │ HTTP 429 / 5xx
       ▼
Fallback 1 → Claude Sonnet 4.5
       │ still failing
       ▼
Fallback 2 → Claude Haiku 4.5
       │ still failing
       ▼
Exception raised → logged, 500 returned to client
```

Tenacity retry: 3 attempts, exponential backoff (2s → 4s → 8s, max 30s).

---

## 7. LLM Services & Models Used

All LLM calls go through `backend/services/llm_service.py` — **no direct API calls from agent code**.

### 7.1 Bosch LLM Farm (Primary Gateway)

**URL:** `https://aoai-farm.bosch-temp.com`
**Auth:** `Authorization: Bearer <llm_farm_api_key>` (single shared key for all models)

This is the Bosch-internal proxy that routes to Anthropic Vertex AI and Azure OpenAI. All Claude and GPT calls go here.

### 7.2 Models Accessed via LLM Farm

| Model | Internal Name | URL Pattern | Role | Cost ($/M in/out) | Typical Latency |
|-------|--------------|-------------|------|-------------------|-----------------|
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | `.../publishers/anthropic/models/claude-sonnet-4-6:rawPredict` | Primary — PESTEL discovery, market analysis, on-demand user analysis | $3.00 / $15.00 | 30–90s |
| Claude Sonnet 4.5 | `claude-sonnet-4-5@20250929` | `.../publishers/anthropic/models/claude-sonnet-4-5@20250929:rawPredict` | Fallback tier-1 (same quality) | $3.00 / $15.00 | 30–60s |
| Claude Haiku 4.5 | `claude-haiku-4-5@20251001` | `.../publishers/anthropic/models/claude-haiku-4-5@20251001:rawPredict` | Validation, scoring, tech scan — structured/fast tasks | $1.00 / $5.00 | 5–15s |
| GPT-5.4 | `gpt-5.4-2026-03-05` | `.../openai/deployments/gpt-5.4-2026-03-05/chat/completions` | Source-grounded validation (cross-checks Sonnet claims) | $5.00 / $15.00 | 10–30s |
| GPT-5-mini | `gpt-5-mini-2025-08-07` | `.../openai/deployments/.../chat/completions` | Batch/volume tasks (news sentiment, future use) | $0.25 / $2.00 | 2–5s |
| text-embedding-3-small | Azure deployment | `.../openai/deployments/.../embeddings` | Embeddings (RAG, currently unused in prod) | $0.027 / — | 1–2s |
| Gemini 2.5 Pro | `google-gemini-2-5-pro` | `.../...` (LLM Farm, subscription-key auth) | Additional validator (currently integrated, low usage) | $1.25 / $10.00 | 15–30s |

**Note on auth for Gemini:** The Gemini endpoint on LLM Farm uses `genaiplatform-farm-subscription-key` header instead of Bearer token.

### 7.3 Grok 4 (Separate Azure AI Endpoint)

**URL:** `https://rbinbdo-vismai-mbr-resource.cognitiveservices.azure.com`
**Auth:** `api-key` header (separate from LLM Farm key)
**Deployment:** `grok-4-fast-reasoning`
**Role:** Independent validator — used when Sonnet + GPT-5.4 disagree or for high-stakes data points
**Cost:** ~$3.00 / $15.00 per million tokens

### 7.4 API Protocol Differences

| Model Family | Protocol | Body Format | Model in URL or Body? |
|-------------|----------|-------------|----------------------|
| Claude (via Vertex AI rawPredict) | `POST .../models/{segment}:rawPredict` | `{anthropic_version, max_tokens, temperature, messages, system}` | **URL** — model NOT in body |
| GPT (Azure OpenAI chat/completions) | `POST .../deployments/{name}/chat/completions?api-version=...` | `{model, messages, max_completion_tokens, temperature}` | Body |
| Grok 4 (Azure AI) | `POST .../openai/deployments/{name}/chat/completions?api-version=...` | `{model, messages, max_tokens, temperature}` | Body |
| Embeddings | `POST .../deployments/{name}/embeddings?api-version=...` | `{input}` | Deployment in URL |

### 7.5 Cost Tracking

Every LLM call is tracked at runtime:
- `llm.call_count` — cumulative call counter (reset on restart)
- `llm.total_cost_usd` — cumulative estimated cost (reset on restart)
- Exposed at `GET /api/health` → `{llm_calls_total, llm_cost_total_usd}`

**Estimated monthly costs (typical usage pattern):**

| Task | Model | Calls/day | Est. cost/month |
|------|-------|-----------|-----------------|
| Scheduled refresh (1/day) | Sonnet 4.6 + Haiku 4.5 + GPT-5.4 | 1 full pipeline | ~$3–6 |
| On-demand analysis (users clicking) | Sonnet 4.6 (cache hit after first) | ~20 cache misses/day | ~$2–4 |
| Startup warmup | Sonnet 4.6 (cached system prompt) | 20 per restart | ~$0.40/restart |
| **Total** | | | **~$80–150/month** |

---

## 8. Database Schema & Data Model

**Database:** `mobility_intelligence` on PostgreSQL 16
**Connection string:** `postgresql+asyncpg://postgres:<password>@<host>:5432/mobility_intelligence`

### Table: `sources`

Provenance records for every data point in the system.

```sql
id              SERIAL PRIMARY KEY
name            VARCHAR(200)     -- "ACMA Annual Report FY2025"
url             TEXT             -- source URL
source_type     VARCHAR(50)      -- "official_report" | "news" | "government" | "llm_estimate" | "derived"
accessed_at     TIMESTAMPTZ
reliability     VARCHAR(20)      -- "high" | "medium" | "low"
raw_excerpt     TEXT             -- exact text extracted from source
notes           TEXT
created_at      TIMESTAMPTZ
```

### Table: `pestel_factors`

~30–40 rows. One row per active PESTEL factor.

```sql
id                  SERIAL PRIMARY KEY
code                VARCHAR(50) UNIQUE   -- "india_eu_fta"
name                VARCHAR(200)         -- "India-EU FTA signed Jan 2026"
category            VARCHAR(20)          -- "P" | "E" | "S" | "T" | "En" | "L"
selection_reasoning TEXT                 -- why this factor was selected
likelihood          FLOAT                -- 1–10
likelihood_reasoning TEXT
impact              FLOAT                -- 1–10
impact_reasoning    TEXT
origin_date         DATE
trend               VARCHAR(20)          -- "escalating" | "de-escalating" | "stable" | "new"
time_horizon        VARCHAR(20)          -- "immediate" | "short" | "medium" | "long"
segment_relevance   JSONB                -- {"4W_PV": "H", "2W": "M", ...}
affected_pillars    JSONB                -- ["ADAS", "Motion", ...]
source_ids          INTEGER[]            -- FK array → sources.id
is_active           BOOLEAN DEFAULT TRUE
last_refreshed      TIMESTAMPTZ
created_at          TIMESTAMPTZ
updated_at          TIMESTAMPTZ
```

### Table: `technologies`

One row per technology (e.g. "ADAS L2+ Camera Systems"). Multi-segment market data stored as JSONB.

```sql
id                    SERIAL PRIMARY KEY
code                  VARCHAR(100) UNIQUE  -- "adas_l2_camera"
name                  VARCHAR(200)         -- "ADAS L2+ Camera Systems"
pillar                VARCHAR(100)         -- "ADAS"
market_data           JSONB                -- {"4W_PV": {"fy25": 1200, "fy30": 3400, "cagr": 23.2}, ...}
total_market_fy25_cr  FLOAT
total_market_fy30_cr  FLOAT
cagr                  FLOAT
maturity              VARCHAR(20)          -- "emerging" | "growth" | "mature" | "declining"
confidence            VARCHAR(20)          -- "high" | "medium" | "low"
includes              TEXT                 -- component breakdown
source_ids            INTEGER[]
analysis_reasoning    TEXT
source_note           TEXT                 -- shown in UI: "Published: Mordor Intelligence Jan 2026"
is_active             BOOLEAN
last_refreshed        TIMESTAMPTZ
```

### Table: `competitors`

12 rows (seeded manually via `seed_competitors.py`).

```sql
code            VARCHAR(50) UNIQUE   -- "bosch", "continental", "zf"
name            VARCHAR(200)         -- "Robert Bosch GmbH"
short_name      VARCHAR(100)         -- "Bosch"
headquarters    VARCHAR(100)         -- "Germany"
tier            VARCHAR(50)          -- "Tier-1" | "Tech"
india_presence  TEXT
key_products    TEXT
color           VARCHAR(10)          -- hex colour for UI bars
is_active       BOOLEAN
```

### Table: `competitor_pillar_shares`

~250 rows. Market share of each competitor per pillar × segment.

```sql
competitor_code   VARCHAR(50) → competitors.code
pillar            VARCHAR(100)   -- "ADAS"
segment           VARCHAR(20)    -- "4W_PV"
market_share_pct  NUMERIC(5,2)
revenue_cr        NUMERIC(10,2)
confidence        VARCHAR(20)    -- "ai_estimate"
source_note       TEXT
PRIMARY KEY (competitor_code, pillar, segment)
```

### Table: `competitor_tech_shares`

~630 rows. Per-technology competitor shares.

```sql
competitor_code   VARCHAR(50)
tech_code         VARCHAR(100)   -- FK → technologies.code
segment           VARCHAR(20)
market_share_pct  NUMERIC(5,2)
revenue_cr        NUMERIC(10,2)
strength          VARCHAR(20)    -- "market_leader" | "strong_presence" | "present" | "emerging"
confidence        VARCHAR(20)
source_note       TEXT
PRIMARY KEY (competitor_code, tech_code, segment)
```

### Table: `oem_sourcing`

~99 rows. Which OEMs source which technology from which supplier.

```sql
id              SERIAL PRIMARY KEY
oem_name        VARCHAR(100)    -- "Maruti Suzuki"
tech_code       VARCHAR(100)
segment         VARCHAR(20)
supplier_codes  TEXT            -- comma-separated competitor codes
notes           TEXT
```

### Table: `validation_logs`

Audit trail for multi-LLM validation runs.

```sql
id                  SERIAL PRIMARY KEY
entity_type         VARCHAR(50)    -- "pestel_factor" | "technology"
entity_id           INTEGER
data_point          VARCHAR(200)
claimed_value       TEXT
primary_model       VARCHAR(100)
primary_verdict     VARCHAR(20)    -- "CONFIRMED" | "DISPUTED" | "UNCERTAIN"
primary_confidence  VARCHAR(20)
primary_reasoning   TEXT
validator_model     VARCHAR(100)
validator_verdict   VARCHAR(20)
validator_confidence VARCHAR(20)
validator_reasoning TEXT
consensus           VARCHAR(20)    -- "VERIFIED" | "FLAGGED" | "REJECTED" | "HUMAN_REVIEW"
consensus_reasoning TEXT
web_source_url      TEXT
web_source_excerpt  TEXT
created_at          TIMESTAMPTZ
```

### Table: `refresh_logs`

Refresh cycle audit trail.

```sql
id                  SERIAL PRIMARY KEY
trigger_type        VARCHAR(20)    -- "scheduled" | "manual" | "startup"
started_at          TIMESTAMPTZ
completed_at        TIMESTAMPTZ
status              VARCHAR(20)    -- "running" | "completed" | "failed"
new_factors         INTEGER
updated_factors     INTEGER
llm_calls_made      INTEGER
estimated_cost_usd  FLOAT
error_message       TEXT
```

### Table: `analysis_cache`

PostgreSQL-side analysis cache (Redis is primary; this is secondary/backup).

```sql
cache_key       VARCHAR(300) UNIQUE  -- "pestel:india_eu_fta:4W_PV"
analysis_type   VARCHAR(50)
content         JSONB
segment         VARCHAR(20)
generated_by    VARCHAR(100)
expires_at      TIMESTAMPTZ
created_at      TIMESTAMPTZ
```

---

## 9. Caching Layer

### 9.1 Redis Cache (Primary)

All AI analysis results are cached in Redis with key prefix `mi:`.

| Cache Key Pattern | TTL | Contents |
|-------------------|-----|---------|
| `mi:pestel:{code}:{segment}` | 86,400s (24h) | Full PESTEL analysis JSON (Sonnet-generated) |
| `mi:tech:{code}:{segment}` | 86,400s (24h) | Technology AI analysis JSON |
| `mi:pestel_list:{segment}` | 21,600s (6h) | All active PESTEL factors for segment |
| `mi:tech_list:{segment}` | 21,600s (6h) | All active technologies for segment |

**Invalidation:** On every scheduled/manual refresh, `cache.invalidate_pestel_cache()` and `cache.invalidate_tech_cache()` flush all matching keys via `SCAN` + `DEL`.

### 9.2 Redis Configuration

```yaml
command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
```

LRU eviction: if Redis hits 256 MB, it evicts the least-recently-used keys. This means during cache pressure, older analysis results are dropped and regenerated on next access.

### 9.3 Cache Hit Rate (expected)

For a typical team of 5 users:
- Factor list: near-100% hit rate (fetched on view load, TTL 6h)
- PESTEL detail analysis: first user to click a bubble gets a miss (3–8s wait); all subsequent users get a hit
- Expected savings: ~80% reduction in on-demand LLM calls vs. no cache

---

## 10. Web Intelligence / Data Ingestion Pipeline

### 10.1 Data Sources

`WebIntelligenceService` scrapes these on every scheduled refresh:

| Source | URL | Type | Content |
|--------|-----|------|---------|
| ET Auto | `auto.economictimes.indiatimes.com/rss/topstories` | RSS | Latest auto industry news |
| Livemint Auto | `livemint.com/rss/auto` | RSS | Financial/auto news |
| ACMA Press Releases | `acma.in/` | HTML | Industry body announcements |
| SIAM Statistics | `siam.in/statistics.aspx` | HTML | Vehicle sales data |
| MoRTH Notifications | `morth.gov.in/notifications` | HTML | Regulatory notifications |
| IBEF Auto Sector | `ibef.org/industry/autocomponents-india` | HTML | Sector overview + data |
| Autocar India | `autocarindia.com/RSS/rss.ashx` | RSS | Product / market news |
| Overdrive India | `overdrive.in/feed/` | RSS | Technical + market news |

### 10.2 Scraping Policy

- **All sources are public web pages** — no authentication, no CAPTCHA, no paywalled content
- RSS feeds are parsed with `lxml` via BeautifulSoup4
- HTML pages use CSS selectors (configurable per source) to extract main content
- `httpx` timeout: 30s per source; failures are silently skipped (non-blocking)
- Total scrape time: ~60–120s for all sources (async, but httpx is used synchronously inside the service — improvement opportunity)

### 10.3 SerpAPI (Optional — not active in current deployment)

Config has `serpapi_key` field (free tier: 250 searches/month). Not currently called in the codebase — stubbed for future use to supplement scraping with targeted Google searches.

---

## 11. API Reference

All routes are prefixed `/api/`. Auto-generated docs available at `http://localhost:8000/docs` (Swagger UI).

### Health

| Method | Path | Auth | Response |
|--------|------|------|---------|
| GET | `/api/health` | None | `{status, service, version, llm_calls_total, llm_cost_total_usd}` |

### PESTEL

| Method | Path | Params | Response |
|--------|------|--------|---------|
| GET | `/api/pestel/` | `segment=4W_PV` | Array of all active PESTEL factors |
| GET | `/api/pestel/{code}` | — | Single factor detail |
| GET | `/api/pestel/score-history` | `segment=` | Historical likelihood×impact scores |

### Technologies

| Method | Path | Params | Response |
|--------|------|--------|---------|
| GET | `/api/techs/` | `segment=4W_PV` | All technologies with market_data |
| GET | `/api/techs/{code}` | `segment=` | Single technology detail |
| GET | `/api/techs/pillar/{pillar}` | `segment=` | All techs under a pillar |

### AI Analysis

| Method | Path | Params | Response |
|--------|------|--------|---------|
| GET | `/api/analysis/pestel/{code}` | `segment=4W_PV` | AI-generated factor analysis (cached) |
| GET | `/api/analysis/tech/{code}` | `segment=4W_PV` | AI-generated tech analysis (cached) |
| GET | `/api/analysis/validation/{type}/{id}` | — | Validation audit trail for entity |

### Competitors

| Method | Path | Params | Response |
|--------|------|--------|---------|
| GET | `/api/competitors/pillar` | `pillar=ADAS&segment=4W_PV` | Players + market shares + technology list for pillar |
| GET | `/api/competitors/tech` | `tech_code=adas_l2_camera&segment=4W_PV` | Per-technology competitor shares + OEM sourcing + cross-segment data |

### Refresh (Admin only)

| Method | Path | Auth Header | Response |
|--------|------|-------------|---------|
| POST | `/api/refresh/full` | `X-Admin-Key: mi-admin-refresh-2026` | Triggers background refresh, returns immediately |
| POST | `/api/refresh/cache/clear` | `X-Admin-Key: mi-admin-refresh-2026` | Clears all Redis cache keys |
| GET | `/api/refresh/status` | None | Last refresh log entry |

---

## 12. Data Flow — End to End

### 12.1 User loads the dashboard (View 1 — PESTEL)

```
1. Browser opens http://<host>:5173
2. Vite serves mobility-intelligence-platform-live.jsx
3. React renders initial state (empty, loading spinners)
4. useEffect fires: GET /api/health → sets apiStatus="live" or "offline"
5. useEffect fires: GET /api/pestel/?segment=4W_PV
6. Backend: check Redis cache "mi:pestel_list:4W_PV"
   HIT → return immediately from Redis
   MISS → SELECT from pestel_factors WHERE is_active=TRUE ORDER BY likelihood*impact DESC
7. Response: JSON array of 30-40 factors
8. transformPestel() maps API shape → chart-compatible shape
9. React re-renders: bubble chart appears, one bubble per factor
```

### 12.2 User clicks a PESTEL bubble (on-demand AI analysis)

```
1. User clicks bubble → onBubbleClick() fires
2. GET /api/analysis/pestel/{factor_code}?segment=4W_PV
3. Backend orchestrator:
   a. Check Redis: "mi:pestel:{code}:4W_PV"
      HIT (< 5ms) → return JSON to frontend
   b. MISS (~3–8s) →
      - Load factor row from PostgreSQL
      - Build prompt: SYSTEM_CONTEXT + factor details + segment context
      - POST to Sonnet 4.6 via LLM Farm
      - Parse JSON response
      - Redis SET with TTL=86400
      - Return to frontend
4. Frontend renders detail panel (right-side slide-in)
```

### 12.3 Scheduled refresh (every 24h)

```
00:00 → APScheduler fires run_scheduled_refresh()
  ├── httpx scrapes 8+ sources (30–120s total)
  ├── Sonnet 4.6 discovery call (~$1.50, 60–90s)
  ├── Haiku 4.5 filter call (~$0.05, 10–15s)
  ├── Sonnet 4.6 detail scoring (up to 40 factors × $0.08 = ~$3.20)
  ├── Haiku 4.5 tech scan (~$0.10)
  ├── GPT-5.4 source validation (up to 40 factors × $0.05 = ~$2.00)
  ├── PostgreSQL upserts
  ├── Redis cache flush
  └── refresh_logs INSERT
Total: ~10–20 minutes, ~$5–8 cost
```

---

## 13. Deployment Architecture (Docker / Cloud)

### 13.1 Current Local Deployment

```bash
# Start all services
docker-compose up -d

# Or run individually (dev mode)
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload \
  --reload-dir api --reload-dir agents --reload-dir db \
  --reload-dir models --reload-dir services

cd frontend
npm run dev   # Vite dev server on port 5173
```

### 13.2 Docker Compose Services

```yaml
services:
  api:       # FastAPI + all agents
    build: ./backend
    ports: ["8000:8000"]
    depends_on: [postgres (healthy), redis (healthy)]
    healthcheck: curl http://localhost:8000/api/health
    restart: unless-stopped

  postgres:
    image: postgres:16-alpine
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
    # First-boot migration: 001_initial.sql runs automatically

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes: [redisdata:/data]
```

### 13.3 Recommended Cloud Deployment (Bosch Internal Cloud)

```
┌──────────────────────────────────────────────────────────────────┐
│  BOSCH INTERNAL CLOUD  (e.g., Bosch Azure subscription or        │
│  private Kubernetes cluster)                                     │
│                                                                  │
│  ┌─────────────────┐   ┌─────────────────┐                      │
│  │  Frontend CDN   │   │  Backend Pod    │                      │
│  │  (Static build) │   │  FastAPI/Uvicorn│                      │
│  │  nginx or CDN   │   │  2 replicas     │                      │
│  │  Port 80/443    │   │  Port 8000      │                      │
│  └────────┬────────┘   └────────┬────────┘                      │
│           │                     │                                │
│           └─────────────────────┤                                │
│                                 │                                │
│                    ┌────────────▼──────────────┐                │
│                    │  Internal Load Balancer    │                │
│                    └────────────┬──────────────┘                │
│                                 │                                │
│             ┌───────────────────┴──────────────────┐            │
│             │                                       │            │
│   ┌─────────▼──────────┐              ┌────────────▼───────┐   │
│   │  PostgreSQL        │              │  Redis Cluster      │   │
│   │  Managed DB service│              │  or Redis Pod       │   │
│   │  (persistent)      │              │  (ephemeral OK)     │   │
│   └────────────────────┘              └────────────────────┘   │
│                                                                  │
│  External calls (outbound only):                                 │
│  ├── aoai-farm.bosch-temp.com (LLM Farm)                        │
│  ├── rbinbdo-vismai-mbr-resource.cognitiveservices.azure.com    │
│  └── public web sources (ACMA, SIAM, ET Auto, etc.)             │
└──────────────────────────────────────────────────────────────────┘
```

**Minimum resource requirements per pod:**
- API: 2 vCPU, 4 GB RAM (LLM calls are I/O-bound, not CPU-bound)
- PostgreSQL: 2 vCPU, 8 GB RAM, 50 GB SSD
- Redis: 1 vCPU, 512 MB RAM

**Production uvicorn command (no `--reload`):**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4 --timeout-keep-alive 60
```

Use `--workers 4` for multi-core utilisation. Each worker is a separate process — all share the PostgreSQL pool and Redis.

### 13.4 Frontend Production Build

```bash
cd frontend
npm run build   # outputs to dist/
```

Serve `dist/` from any static file server (nginx, Azure Static Web Apps, CDN). The `vercel.json` config sets `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY` headers.

### 13.5 CORS Configuration

In `backend/config.py`, `cors_origins` lists every allowed frontend origin. For production, update this to only include the actual internal IP range or hostname:

```python
cors_origins: str = "https://your-internal-hostname.bosch.com"
```

---

## 14. Environment Configuration

All settings are loaded via pydantic-settings from `.env` at the project root.

### 14.1 Required Variables

```bash
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<your-password>
POSTGRES_DB=mobility_intelligence
POSTGRES_HOST=localhost          # "postgres" in Docker Compose
POSTGRES_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0   # "redis://redis:6379/0" in Docker

# LLM Farm — Main gateway (Claude + GPT + Gemini)
LLM_FARM_API_KEY=<bosch-llm-farm-key>
LLM_FARM_BASE_URL=https://aoai-farm.bosch-temp.com

# Grok 4 — Separate Azure AI endpoint
GROK_BASE_URL=https://rbinbdo-vismai-mbr-resource.cognitiveservices.azure.com
GROK_API_KEY=<grok-api-key>

# CORS (comma-separated list of allowed frontend origins)
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://<internal-ip>:5173
```

### 14.2 Optional Variables

```bash
# Override model names if LLM Farm changes deployment names
LLM_FARM_GPT_DEPLOYMENT=gpt-5-mini-2025-08-07
GPT54_DEPLOYMENT=gpt-5.4-2026-03-05
GEMINI_DEPLOYMENT=google-gemini-2-5-pro
GROK_DEPLOYMENT=grok-4-fast-reasoning

# Scheduling
AUTO_REFRESH_HOURS=24         # default: refresh once per day

# Cache TTL
ANALYSIS_CACHE_TTL=86400      # seconds (24h)
PESTEL_CACHE_TTL=86400
TECH_CACHE_TTL=86400

# Optional web search augmentation
SERPAPI_KEY=                  # free tier: 250 searches/month

# Admin key for manual refresh endpoint
# (hardcoded in refresh.py as "mi-admin-refresh-2026" — move to .env for prod)
```

---

## 15. Maintenance & Operations Runbook

### 15.1 Routine Operations

#### Check system health
```bash
curl http://localhost:8000/api/health
# Returns: {"status":"healthy", "llm_calls_total":142, "llm_cost_total_usd":3.24}
```

#### Trigger manual data refresh
```bash
curl -X POST http://localhost:8000/api/refresh/full \
  -H "X-Admin-Key: mi-admin-refresh-2026"
# Watch backend logs for progress
```

#### Clear Redis cache (force all users to get fresh data)
```bash
curl -X POST http://localhost:8000/api/refresh/cache/clear \
  -H "X-Admin-Key: mi-admin-refresh-2026"
```

#### View last refresh log
```bash
curl http://localhost:8000/api/refresh/status
```

#### Check DB record counts
```sql
SELECT COUNT(*) FROM pestel_factors WHERE is_active = TRUE;
SELECT COUNT(*) FROM technologies WHERE is_active = TRUE;
SELECT COUNT(*) FROM competitors;
SELECT COUNT(*) FROM competitor_pillar_shares;
SELECT COUNT(*) FROM competitor_tech_shares;
SELECT COUNT(*) FROM oem_sourcing;
SELECT * FROM refresh_logs ORDER BY created_at DESC LIMIT 5;
```

### 15.2 Adding a New Vehicle Segment

1. Add the segment code to `SEGS` in the frontend JSX (line ~108)
2. Add CORS origins for any new IPs if required in `config.py`
3. Add the segment to `SEGMENTS` list in `scripts/seed_competitors.py`
4. Re-run seed scripts for the new segment
5. Update the system context in `agents/prompts/system_context.py` with segment data

### 15.3 Updating the LLM Farm API Key

1. Update `.env`: `LLM_FARM_API_KEY=<new-key>`
2. Restart the backend: `docker-compose restart api`
3. Verify: `curl http://localhost:8000/api/health`

### 15.4 Updating Model Names (if LLM Farm changes deployment names)

All model names are in `config.py` and `llm_service.py`:
- `config.py` → `primary_model`, `validator_model`, `llm_farm_gpt_deployment`, etc.
- `llm_service.py` → `CLAUDE_URL_SEGMENTS` dict maps model name → URL segment

### 15.5 Adding a New PESTEL Factor Manually

```sql
INSERT INTO pestel_factors
  (code, name, category, selection_reasoning, likelihood, likelihood_reasoning,
   impact, impact_reasoning, trend, time_horizon, segment_relevance, affected_pillars)
VALUES
  ('new_factor_code', 'Factor Name', 'T',
   'Why this matters to India auto components...',
   7.5, 'Score 7.5 because...',
   8.0, 'Score 8.0 because...',
   'escalating', 'medium',
   '{"4W_PV":"H","LCV":"M","2W":"L"}',
   '["ADAS","Motion"]');
```

Then clear Redis cache so the frontend picks it up immediately.

### 15.6 Competitor Data Refresh

Competitor data (pillar/tech shares) is AI-estimated and seeded manually — it does not update during the scheduled refresh. To refresh:

```bash
cd backend
# Full re-seed (overwrites existing records)
& "C:\Users\IXS3KOR\.conda\envs\intel\python.exe" -m scripts.seed_competitors

# Fix specific skipped entries
& "C:\Users\IXS3KOR\.conda\envs\intel\python.exe" -m scripts.fix_skipped_pillar_shares
& "C:\Users\IXS3KOR\.conda\envs\intel\python.exe" -m scripts.fix_skipped_tech_shares
```

**Note:** The Python executable is used directly instead of `conda activate` because `conda activate` does not work in PowerShell without the Conda shell hooks.

### 15.7 Backend Won't Start — Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Port 8000 already in use` | Previous instance still running | `netstat -ano | findstr :8000` → `taskkill /PID <pid> /F` |
| `ModuleNotFoundError: anthropic` | Wrong Python env | Use `& "C:\Users\IXS3KOR\.conda\envs\intel\python.exe"` explicitly |
| Reload loop (scripts/ changing) | `--reload` watching all dirs | Use `--reload-dir api --reload-dir agents ...` to exclude scripts/ |
| `could not translate host name "postgres"` | Running outside Docker without host mapping | Set `POSTGRES_HOST=localhost` in `.env` |
| Redis connection error | Redis not running | `docker-compose start redis` |

---

## 16. Stress Testing Guidelines

The primary bottlenecks are LLM API latency (60–90s per Sonnet call) and PostgreSQL query performance under concurrent reads. The system is designed for internal use by ~10–20 concurrent users.

### 16.1 What to Test

| Component | Test | Expected Result |
|-----------|------|----------------|
| `/api/health` | 100 rps for 60s | < 5ms p99, 0 errors |
| `/api/pestel/?segment=4W_PV` | 50 rps for 60s | < 50ms p99 (DB query) |
| `/api/techs/?segment=4W_PV` | 50 rps for 60s | < 50ms p99 |
| `/api/analysis/pestel/{code}` (cache warm) | 20 rps for 60s | < 10ms p99 (Redis hit) |
| `/api/analysis/pestel/{code}` (cache cold) | 5 concurrent | Up to 90s per call, all succeed eventually |
| `/api/competitors/pillar` | 20 rps for 60s | < 100ms p99 (JOIN query) |
| Full scheduled refresh | 1 run | Completes in < 20 min, no DB deadlocks |

### 16.2 Concurrency Limits

| Resource | Limit | Notes |
|----------|-------|-------|
| PostgreSQL connections | 30 (pool_size=10 + max_overflow=20) | Each uvicorn worker has its own pool; with 4 workers = 120 total possible, but pool is shared via async |
| Redis connections | 10 (default pool) | Per worker |
| LLM Farm rate limit | Unknown (Bosch-managed) | If 429 received, tenacity retries up to 3× with backoff |
| Uvicorn async workers | 1 per `--workers` flag | Default = 1 in dev; set to 4 in prod |

### 16.3 Recommended Load Test Tool

Use `k6` or `locust`:

```python
# locust basic scenario
from locust import HttpUser, task, between

class DashboardUser(HttpUser):
    wait_time = between(1, 3)

    @task(10)
    def load_pestel_list(self):
        self.client.get("/api/pestel/?segment=4W_PV")

    @task(5)
    def load_tech_list(self):
        self.client.get("/api/techs/?segment=4W_PV")

    @task(3)
    def load_analysis_cached(self):
        self.client.get("/api/analysis/pestel/india_eu_fta?segment=4W_PV")

    @task(1)
    def load_competitors(self):
        self.client.get("/api/competitors/pillar?pillar=ADAS&segment=4W_PV")
```

### 16.4 Expected Failure Modes Under Stress

1. **LLM calls under concurrent cold-cache requests:** If 10 users all click different bubbles simultaneously, 10 concurrent Sonnet calls will be initiated. LLM Farm may throttle. Tenacity will retry — users may see 90–180s wait. Mitigation: startup warmup covers the top-20 factors.

2. **PostgreSQL connection exhaustion:** Under 30+ concurrent API requests (each needing a DB connection), the pool will queue. SQLAlchemy handles this gracefully with `queue_timeout`. Set `pool_timeout=30` to surface errors cleanly rather than hanging.

3. **Redis unavailable:** The cache service logs a warning and falls through to LLM/DB. The app continues working but every request becomes an LLM call. This is expensive but not fatal.

---

## 17. Security Considerations

### 17.1 Current Security Posture

| Control | Status | Notes |
|---------|--------|-------|
| HTTPS | Not implemented | Termination must be done at load balancer / reverse proxy in cloud |
| Authentication | None (frontend) | Internal network only; no user auth on the dashboard |
| API Key for refresh | Basic static key (`mi-admin-refresh-2026`) | Acceptable for internal; change before cloud deployment |
| CORS | Explicit allowlist | Only listed IP:port combinations allowed |
| LLM API keys | In `.env` (not in code) | Do not commit `.env` to git |
| SQL injection | Parameterised queries | All `db.execute(text(...), {"param": value})` — safe |
| No arbitrary code exec | ✅ | No `eval`, no user-controlled shell commands |
| X-Frame-Options: DENY | ✅ | Set in `vercel.json` |
| X-Content-Type-Options: nosniff | ✅ | Set in `vercel.json` |

### 17.2 Recommended Before Cloud Deployment

1. **Rotate the admin key** — move `ADMIN_KEY` out of `refresh.py` into `.env`
2. **Add HTTPS** — terminate TLS at nginx/load balancer; backend stays HTTP internally
3. **Restrict CORS** — update to only the final internal hostname, not IP wildcards
4. **Add rate limiting** on the analysis endpoints — prevent a single user from triggering hundreds of expensive LLM calls
5. **Secrets management** — move `.env` values to Azure Key Vault or Kubernetes Secrets
6. **Network policy** — allow outbound only to LLM Farm and known web scraping targets

---

## 18. Known Limitations & Technical Debt

| Item | Impact | Suggested Fix |
|------|--------|--------------|
| Single JSX file (~1700 lines) | Developer experience; merge conflicts | Split into component files (React Router + folder structure) — medium effort |
| Web scraping is synchronous within the service | Refresh takes longer than needed | Convert `WebIntelligenceService` methods to `asyncio.gather()` for concurrent fetching |
| Admin API key hardcoded in `refresh.py` | Security risk | Move to `.env` variable, document in deployment guide |
| No user authentication | Any internal user can view all data | Add OIDC / Azure AD SSO for internal deployment |
| Competitor data refreshes are manual | Stale after ~6 months | Integrate competitor seed into scheduled refresh pipeline |
| `pestel_score_history` table not populated | View 1 has no historical trend chart | Add score snapshotting logic to `_store_pestel_results()` |
| `tech_agent.py` only flags, never auto-inserts | New tech categories require manual intervention | Add confidence threshold for auto-insertion |
| No database migrations (Alembic not wired up) | Schema changes require manual SQL | Wire up `alembic upgrade head` into Docker entrypoint |
| Grok 4 API key in `config.py` default value | Exposed if config file is shared | Move to `.env` only, no default |
| `analysis_cache` PostgreSQL table unused | Redis is primary; Postgres table is stale | Either wire it up as backup or drop the table |

---

*Document prepared April 2026. For questions contact the platform maintainer.*
