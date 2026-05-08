# Mobility Solutions Intelligence Platform

Agentic AI dashboard for Bosch India auto-component industry intelligence.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite (single-file SPA) |
| Backend | FastAPI + Python 3.11, port **8001** |
| Database | PostgreSQL 18 — `mobility_intelligence` |
| Cache | Redis (24 h TTL on all API responses) |
| LLM — Primary | Claude Sonnet 4.6 (PESTEL discovery + AI analysis) |
| LLM — Filter | Claude Haiku 4.5 (relevance scoring) |
| LLM — Validator | GPT-5.4 (source-grounded validation) |
| News sources | SerpAPI + RSS (ET Auto, Livemint, IBEF, Team-BHP, ACMA, MoRTH) |

## Four views

1. **PESTEL Risk Map** — Likelihood × Impact bubble chart with Now / Jan 2026 / Jan 2025 baseline toggle and right-click trajectory
2. **Technology Stack** — Bosch Tech Stack · Growth Drivers (13-pillar SVG with CAGR dots + ₹ market sizes)
3. **Market Landscape** — CAGR × Market Size bubble chart with pillar color encoding
4. **Competitor Landscape** — Market share · Players · OEM sourcing patterns per tech × segment

## Run locally

```bash
# Backend (conda env: intel)
cd backend
conda activate intel
uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# Frontend
cd frontend
npm install
npm run dev
# → http://localhost:5173 (or next available port)
```

## First-time database setup

```bash
# Run all seed scripts in order from backend/ with conda env intel active:
python -m scripts.seed_competitors             # pillar-level competitor shares
python -m scripts.seed_solutions_techs --apply # 15 Solutions-pillar techs
python -m scripts.seed_competitors_solutions --apply
python -m scripts.seed_competitors_remaining --apply
python -m scripts.seed_cloud_competitors --apply
python -m scripts.seed_oem_sourcing --apply
python -m scripts.seed_tech_shares_complete --apply  # fills all tech × segment shares
```

## Refresh data

```bash
# Trigger a full refresh via API (backend must be running):
curl -X POST http://localhost:8001/api/refresh/full \
  -H "X-Admin-Key: mi-admin-refresh-2026"
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | System health + LLM cost tracking |
| GET | `/api/pestel/?segment=4W_PV` | All PESTEL factors |
| GET | `/api/pestel/{code}` | Single factor + source trail |
| GET | `/api/techs/?segment=4W_PV` | All technologies |
| GET | `/api/techs/pillars` | Pillar summary (View 2) |
| GET | `/api/analysis/pestel/{code}` | AI detail on click (cached) |
| GET | `/api/analysis/tech/{code}` | AI tech analysis on click (cached) |
| GET | `/api/competitors/pillar?pillar=ADAS&segment=4W_PV` | Competitor shares for a pillar |
| GET | `/api/competitors/tech/{tech_code}?segment=4W_PV` | Tech drilldown + OEM sourcing |
| POST | `/api/refresh/full` | Admin: trigger full refresh |
| POST | `/api/refresh/cache/clear` | Admin: clear Redis cache |
| GET | `/api/refresh/status` | Refresh status + data counts |

Auto-generated docs: `http://localhost:8001/docs`

## Architecture

```
Frontend (Vite/React SPA)
        ↕  REST JSON
Backend API (FastAPI · port 8001)
        ↕
  ┌─────────────────────────────────────┐
  │  Agent System                       │
  │  ├── Orchestrator                   │
  │  ├── PESTEL Agent (discover+score)  │
  │  ├── Validation Agent (GPT-5.4)     │
  │  └── Web Intelligence (10+ sources) │
  └─────────────────────────────────────┘
        ↕
  PostgreSQL 18 + Redis cache
```

## Key constants

- Industry size FY25: ₹6.73 Lakh Crore ($80.2B), ACMA verified
- Segments: 4W PV · LCV · HCV · 2W · 3W · Tractor
- 13 Bosch pillars: ADAS · Motion · Energy · Body & Comfort · Infotainment · OS · Compute · ECUs · Semiconductors · Actuators · Solutions · Services · Cloud
- 73 active technologies seeded across all pillars
- 1,781 competitor_tech_shares rows · 582 competitor_pillar_shares rows · 1,402 OEM sourcing rows
- Refresh schedule: every 24 h via APScheduler
- Estimated cost: ~$0.28 per full refresh, ~$1.10/month

## License

Internal Bosch tool. Not for redistribution.
