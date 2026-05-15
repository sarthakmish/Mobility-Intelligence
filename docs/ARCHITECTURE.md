# Mobility Intelligence Platform — Full Stack Architecture

## Table of Contents
1. [Architecture Decisions](#architecture-decisions)
2. [Project Structure](#project-structure)
3. [Data Flow](#data-flow)
4. [Agent System Design](#agent-system-design)
5. [Multi-LLM Validation](#multi-llm-validation)
6. [Hosting Strategy](#hosting-strategy)
7. [Refresh Strategy](#refresh-strategy)

---

## Architecture Decisions

### Why NOT LangChain/LangGraph

After careful evaluation as an AI developer, here's my honest recommendation:

**LangChain** — DO NOT USE
- Adds 50+ dependencies, many with security vulnerabilities flagged in corporate scans
- Abstracts away LLM calls behind layers that make debugging nearly impossible
- Updates frequently with breaking changes — risky for production
- For our use case (structured API calls with validation), it's massive overkill
- Corporate security teams routinely flag LangChain's dependency tree

**LangGraph** — NOT NEEDED
- Useful for complex branching agent workflows with cycles
- Our validation flow is linear: Generate → Validate → Store
- A simple Python async pipeline achieves the same thing with 0 dependencies
- If we need graph-based orchestration later, we add it then

**Our approach: Plain Python + httpx + asyncio**
- Zero unnecessary dependencies
- Every line of code is auditable (critical for corporate)
- Easy to explain to any developer
- Full control over retry logic, caching, error handling
- Uses only: FastAPI, httpx, asyncpg, redis, APScheduler

### Infrastructure Stack (All Free/Open Source)

| Component | Technology | Why |
|-----------|-----------|-----|
| Backend | FastAPI (Python) | Fastest Python API framework, async native, auto-docs |
| Database | PostgreSQL (yours) | Already available, JSONB for flexible schema |
| Cache | Redis (yours) | Already available, TTL-based caching |
| Task Queue | APScheduler | Lightweight, no Celery/RabbitMQ overhead needed |
| LLM Calls | httpx (async) | Direct API calls, no framework bloat |
| Web Scraping | httpx + BeautifulSoup4 | Lightweight, corporate-safe |
| Frontend Host | Vercel (free tier) | Best for React, 100GB bandwidth/month free |
| Backend Host | Docker (local) → Railway (free) | Free tier: 500 hrs/month, 1GB RAM |
| Migrations | Alembic | Standard SQLAlchemy migration tool |

### Why NOT Wix/Netlify
- **Wix**: Not suitable — it's a website builder, not a React host
- **Netlify**: Good but Vercel has better React/Next.js integration
- **Vercel**: Best free tier for React SPAs, edge functions, 100GB bandwidth

---

## Project Structure

```
mobility-intelligence/
│
├── docker-compose.yml              # Orchestrates all services
├── .env.example                    # Environment variables template
├── README.md                       # Setup instructions
│
├── backend/
│   ├── Dockerfile                  # Python 3.11 slim container
│   ├── requirements.txt            # Minimal dependencies
│   ├── main.py                     # FastAPI app entry point + CORS + startup
│   ├── config.py                   # All configuration from env vars
│   │
│   ├── models/                     # ═══ DATABASE MODELS ═══
│   │   ├── __init__.py
│   │   ├── pestel.py               # PESTEL factors + scores + reasoning
│   │   ├── technology.py           # Technologies + market data + maturity
│   │   ├── source_trail.py         # Source provenance for every data point
│   │   └── validation_log.py       # Multi-LLM validation audit trail
│   │
│   ├── agents/                     # ═══ AI AGENT SYSTEM ═══
│   │   ├── __init__.py
│   │   ├── orchestrator.py         # MAIN BRAIN — coordinates all agents
│   │   ├── pestel_agent.py         # Discovers + scores PESTEL factors
│   │   ├── tech_agent.py           # Technology intelligence + market sizing
│   │   ├── validation_agent.py     # Multi-LLM consensus validation
│   │   ├── analysis_agent.py       # On-click analysis generation (V1/V3)
│   │   └── prompts/                # All LLM prompts (version controlled)
│   │       ├── __init__.py
│   │       ├── pestel_discovery.py # "Scan India auto market for PESTEL forces"
│   │       ├── pestel_scoring.py   # "Score this factor: likelihood × impact"
│   │       ├── tech_analysis.py    # "Analyse this technology for this segment"
│   │       ├── validation.py       # "Cross-check this data for accuracy"
│   │       └── system_context.py   # Shared 18K system prompt (CACHED)
│   │
│   ├── services/                   # ═══ BUSINESS LOGIC ═══
│   │   ├── __init__.py
│   │   ├── llm_service.py          # Unified LLM API client (Claude + OpenAI)
│   │   ├── web_intelligence.py     # Web scraping + news collection
│   │   ├── source_tracker.py       # Source provenance management
│   │   ├── cache_service.py        # Redis caching layer
│   │   └── scheduler.py            # APScheduler cron jobs
│   │
│   ├── api/                        # ═══ REST API ROUTES ═══
│   │   ├── __init__.py
│   │   ├── pestel.py               # /api/pestel/* endpoints
│   │   ├── technology.py           # /api/techs/* endpoints
│   │   ├── analysis.py             # /api/analysis/* (on-click AI)
│   │   ├── refresh.py              # /api/refresh/* (admin-triggered)
│   │   └── health.py               # /api/health (monitoring)
│   │
│   └── db/
│       ├── __init__.py
│       ├── connection.py           # Async PostgreSQL connection pool
│       └── migrations/             # Alembic migration files
│           └── 001_initial.sql
│
├── frontend/
│   ├── vercel.json                 # Vercel deployment config
│   ├── src/
│   │   └── mobility-intelligence-platform.jsx  # Your existing dashboard
│   └── .env.production             # API URL for production
│
├── scripts/
│   ├── seed_initial_data.py        # Seeds DB with verified FY2025 baseline
│   └── run_full_refresh.py         # Manual full data refresh trigger
│
└── docs/
    └── ARCHITECTURE.md             # This file
```

---

## Data Flow

### How Fresh Data Gets Into The System

```
┌─────────────────────────────────────────────────────────┐
│                    DATA FRESHNESS PIPELINE               │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  1. SCHEDULED REFRESH (Every 24 hours via APScheduler)   │
│     │                                                    │
│     ├── Web Intelligence Service scrapes:                │
│     │   • ACMA press releases (acma.in)                  │
│     │   • SIAM monthly data (siam.in)                    │
│     │   • MoRTH notifications (morth.nic.in)             │
│     │   • Economic Times Auto RSS                        │
│     │   • Livemint Auto RSS                              │
│     │   • Moneycontrol Auto RSS                          │
│     │   • IBEF sector reports                            │
│     │   • Vahan dashboard (EV registrations)             │
│     │                                                    │
│     ├── Raw text → Claude Sonnet 4.6 extracts:           │
│     │   • New PESTEL factors                             │
│     │   • Updated market numbers                         │
│     │   • Policy/regulation changes                      │
│     │   • Trade developments                             │
│     │                                                    │
│     ├── Dedup Check (3+ word overlap → skip)             │
│     ├── Pillar Normalization (long names → valid IDs)    │
│     ├── Source Attribution (which source per factor)     │
│     │                                                    │
│     └── Stored data → PostgreSQL + Redis cache warmup    │
│                                                          │
│  2. ADMIN MANUAL REFRESH (Developer-triggered)           │
│     POST /api/refresh/full — triggers complete rescan    │
│     POST /api/refresh/pestel — PESTEL factors only       │
│     POST /api/refresh/tech — Technologies only           │
│                                                          │
│  3. ON-CLICK ANALYSIS (User-triggered, cached)           │
│     • User clicks a PESTEL bubble or tech bubble          │
│     • Check Redis cache (TTL: 24 hours)                  │
│     • If miss: Claude Sonnet 4.6 generates fresh analysis │
│     • Cache result for next user                         │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Refresh Control Decision: DEVELOPER controls refresh, NOT user

**Why:**
- Each full refresh costs ~$0.60 in LLM calls (source attribution, no 4-model validation)
- Uncontrolled user refreshes could blow the budget
- Data doesn't change every hour — ACMA publishes monthly, SIAM quarterly
- A 24-hour auto-refresh (nightly) + admin manual trigger is the right balance
- User sees `● healthy` status badge, not a refresh button

---

## Agent System Design

### Why These PESTEL Factors? The Discovery Process

The system doesn't start with 33 hardcoded factors. Here's the pipeline:

```
STEP 1: PESTEL DISCOVERY AGENT (Sonnet 4.6)
────────────────────────────────────────────
Input:  Latest scraped news + policy updates + market data
Prompt: "You are a PESTEL analyst for India's automotive component
         industry (₹6.73L Cr / $80.2B FY25). Scan the following
         recent developments and identify ALL factors that could
         impact Bosch Mobility Solutions' 13 technology pillars.
         
         For each factor, provide:
         - Category (P/E/S/T/En/L)
         - Factor name (concise, 5-8 words)
         - WHY you selected this (2-3 sentences of reasoning)
         - Which Bosch pillars are affected
         - Is this NEW or an UPDATE to an existing factor?"
         
Output: 40-60 candidate factors with reasoning

STEP 2: RELEVANCE FILTERING (Haiku 4.5)
────────────────────────────────────────
Input:  Candidate factors from Step 1
Prompt: "Score each factor's relevance to India auto components
         on a scale of 1-10. Remove anything below 6.
         Merge duplicates. Flag factors that are too broad."
         
Output: 30-40 filtered factors

STEP 3: SCORING AGENT (Sonnet 4.6)
───────────────────────────────────
Input:  Filtered factors + historical context
Prompt: "For each PESTEL factor, score:
         - Likelihood (1-10): How probable is this?
         - Impact (1-10): If it happens, how severe?
         
         SHOW YOUR REASONING for each score:
         'Likelihood 8 because: India-EU FTA was signed Jan 2026,
          implementation timeline is confirmed, 6.5%→0% over 7 years
          is locked in. Only risk: political change in either bloc.'
         
         'Impact 7 because: EU is India's 2nd largest auto component
          export destination ($5.2B FY25). Zero tariff would make
          Indian components 6.5% cheaper vs competitors.'"

Output: Scored factors with full reasoning trail

STEP 4: SOURCE ATTRIBUTION (replaces multi-LLM validation)
────────────────────────────────────────────────────────────
Input:  New PESTEL factors + list of scraped sources
Logic:  Match factor keywords → source name (free, instant)
Output: Each factor tagged with originating source name + URL

Why not multi-LLM validation on every refresh?
- LLMs can't verify NEW news — it's past their training cutoff
- 4 models validating 20 factors = 80 LLM calls = ~$15/refresh
- They consistently return UNCERTAIN for all recent events
- Source attribution is free, instant, and actually useful
- Quarterly baseline validation with demo_validation.py remains available
```

### Why Not 100+ Factors?

The system DOES scan for 100+ factors. Here's what happens:

1. **Discovery finds ~60 factors** from recent news/data
2. **Relevance filter removes ~20** (too generic, not India-specific, already captured)
3. **Scoring + validation keeps ~35** (the meaningful ones)
4. **The "Why selected" reasoning is stored** — user can click any factor and see:
   - "Selected because: This factor directly impacts 4/13 Bosch pillars"
   - "Reasoning: BS-VI Stage 2 mandates catalytic converter upgrades..."
   - "Source: MoRTH Notification dated 15-Feb-2026, accessed via morth.nic.in"
   - "Validation: Confirmed by Claude Sonnet 4.6 ✓ and Haiku 4.5 ✓"

---

---

## Source Attribution & Validation Strategy

### Real-Time Source Attribution (Every Refresh)

Each new PESTEL factor discovered during a refresh is tagged with which
scraped source it likely originated from (keyword matching — free, instant):

```
Step 4b/6: Tagging source attribution...
  📋 India-EU FTA Implementation Phase…            → Source: ACMA Press Releases
  📋 Rare Earth Magnet Localization Signal…         → Source: ET Auto
  📋 BS-VII Emission Norms Roadmap…                 → Source: MoRTH Notifications
```

### Why Multi-LLM Validation Was Removed From The Refresh Loop

**The original design:** 4 models validate every new factor on every refresh.

**Why it doesn't work for fresh news:**
- LLMs can't verify news past their training cutoff — they return UNCERTAIN for all recent events
- 4 models × 20 factors = 80 LLM calls = ~$15/refresh = $450/month
- Zero practical benefit for data that postdates training cutoffs

**What validation IS good for:**
- Quarterly baseline data verification (ACMA annual report numbers, SIAM statistics)
- These are stable numbers that LLMs have in training data
- Use `demo_validation.py` for this quarterly check

### Pillar Normalization

PESTEL factors discovered by AI often use long descriptive pillar names
(e.g. `"Powertrain Solutions"`, `"Energy & Charging"`) that don't match
the short IDs used in the technology table (`"Motion"`, `"Energy"`).

If pillar IDs don't match, the Financial Overlay shows `—` because
`TECHS.filter(tt => tt.p === pid)` finds no technologies.

**Fix applied in two places:**
1. `orchestrator.py` — `_normalize_pillars()` runs on every new factor before INSERT
2. `db/migrations/002_normalize_pillars.sql` — one-time fix for existing DB records

**Valid pillar IDs** (must match technology table):
`ADAS`, `Motion`, `Energy`, `Body & Comfort`, `Infotainment`,
`OS`, `Compute`, `ECUs`, `Semiconductors`, `Actuators`, `Solutions`, `Services`, `Cloud`

---

## Cache Warmup Strategy (Budget-Scoped)

**Previous approach (broken):** Warm all 128 analyses × 6 segments = 768 Sonnet calls
- At 90s/call → 19 hours to complete
- 19 hours > 24h refresh cycle → warmup never finishes before next refresh clears cache
- Cost: $47.62/day = $1,448/month

**Current approach (fixed):** Top 20 PESTEL × 4W_PV only
- ~20 calls × 90s = ~30 minutes → completes well within refresh cycle
- Tech bubbles: warm on first click (24h TTL = at most one miss per user per day)
- Monthly cost: 30 warmups × 20 Sonnet calls × $0.062 = $37/month

---

## Impact × Likelihood Scoring — The Reasoning

### How Scores Are Computed (Not Random)

Each PESTEL factor gets scored through a structured rubric:

**Likelihood Score (1-10):**
```
10: Already enacted/happened (e.g., India-EU FTA signed Jan 2026)
 9: Officially announced, timeline set
 8: Strong signals, multiple credible sources confirm
 7: Probable based on policy trajectory
 6: Likely but uncertain timeline
 5: 50/50 — depends on elections/global events
 4: Possible but significant barriers
 3: Unlikely without major policy shift
 2: Very unlikely in 2025-2030 timeframe
 1: Near impossible
```

**Impact Score (1-10):**
```
10: Industry-transforming (>20% revenue impact)
 9: Major disruption to multiple pillars
 8: Significant impact on key segments
 7: Material impact on 3+ Bosch pillars
 6: Moderate impact, adaptation needed
 5: Noticeable but manageable
 4: Minor impact, some adjustment
 3: Minimal direct impact
 2: Negligible for Bosch specifically
 1: No measurable impact
```

**The LLM must cite its reasoning:**
```json
{
  "factor": "US 25-50% tariffs on auto imports",
  "likelihood": 9,
  "likelihood_reasoning": "Already enacted April 2025. Reduced to 18% 
    in Feb 2026 bilateral deal. Score 9 not 10 because further 
    changes possible under new trade negotiations.",
  "impact": 7,
  "impact_reasoning": "US is India's largest auto component export 
    market ($7.2B FY25). 18% tariff erodes price competitiveness 
    vs Mexico (USMCA: 0%) and Thailand (bilateral: 2.5%). Affects 
    Powertrain, Chassis, Body Electronics pillars directly.",
  "sources": ["USTR announcement Apr-2025", "bilateral deal Feb-2026"],
  "affected_pillars": ["Powertrain", "Chassis Systems", "Body Electronics"]
}
```

---

## Hosting Strategy

### Phase 1: Free Hosting (Now)
```
Frontend:  Vercel Free Tier (vercel.com)
           - 100GB bandwidth/month
           - Automatic HTTPS
           - GitHub auto-deploy
           
Backend:   Docker on your local machine
           - Exposed via ngrok or Cloudflare Tunnel (free)
           - OR Railway.app free tier (500 hrs/month)
           
Database:  PostgreSQL in Docker (local)
Redis:     Redis in Docker (local)
```

### Phase 2: Production (When budget allows)
```
Frontend:  Same Vercel (upgrade to Pro if needed)
Backend:   AWS ECS or DigitalOcean ($12/month)
Database:  Managed PostgreSQL (Supabase free / Neon free)
Redis:     Upstash Redis (free tier: 10K commands/day)
```
