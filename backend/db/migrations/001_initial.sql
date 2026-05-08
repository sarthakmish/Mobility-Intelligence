-- ============================================================
-- MOBILITY INTELLIGENCE — Initial Database Schema
-- ============================================================
-- This file runs automatically on first docker-compose up.
-- It creates all tables needed for the platform.
-- ============================================================

-- ────────────────────────────────────────────────────────────
-- TABLE: sources
-- Every piece of data in the system traces back to a source.
-- This is the "source trail" — user clicks to see provenance.
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sources (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,       -- "ACMA Annual Report FY2025"
    url             TEXT,                         -- "https://acma.in/reports/fy2025"
    source_type     VARCHAR(50) NOT NULL,         -- "official_report" | "news" | "government" | "llm_estimate"
    accessed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),  -- When we scraped/accessed it
    reliability     VARCHAR(20) DEFAULT 'high',   -- "high" | "medium" | "low"
    raw_excerpt     TEXT,                         -- The exact text we extracted from
    notes           TEXT,                         -- Any caveats about this source
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for quick lookups by type
CREATE INDEX IF NOT EXISTS idx_sources_type ON sources(source_type);


-- ────────────────────────────────────────────────────────────
-- TABLE: pestel_factors
-- Each row is one PESTEL factor (e.g., "India-EU FTA")
-- Contains the factor definition, category, and selection reasoning
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pestel_factors (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(50) UNIQUE NOT NULL,  -- "india_eu_fta" (URL-safe identifier)
    name            VARCHAR(200) NOT NULL,        -- "India-EU FTA signed Jan 2026"
    category        VARCHAR(20) NOT NULL,         -- "P" | "E" | "S" | "T" | "En" | "L"
    
    -- WHY THIS FACTOR WAS SELECTED (the reasoning trail)
    -- This answers "why this factor and not 100 others?"
    selection_reasoning TEXT NOT NULL,             -- "Selected because: EU is India's 2nd largest..."
    
    -- SCORING (with reasoning for each score)
    likelihood      FLOAT NOT NULL,               -- 1-10 scale
    likelihood_reasoning TEXT NOT NULL,            -- "Score 8 because: FTA signed, timeline confirmed..."
    impact          FLOAT NOT NULL,               -- 1-10 scale
    impact_reasoning TEXT NOT NULL,                -- "Score 7 because: $5.2B export market affected..."
    
    -- TEMPORAL DATA
    origin_date     DATE,                         -- When this factor first appeared
    trend           VARCHAR(20) DEFAULT 'stable', -- "escalating" | "de-escalating" | "stable" | "new"
    time_horizon    VARCHAR(20) DEFAULT 'medium', -- "immediate" | "short" | "medium" | "long"
    
    -- SEGMENT RELEVANCE (which vehicle segments are affected)
    -- Stored as JSONB: {"4W_PV": "H", "2W": "M", "HCV": "H", ...}
    segment_relevance JSONB NOT NULL DEFAULT '{}',
    
    -- PILLAR IMPACT (which Bosch pillars are affected)
    -- Stored as JSONB array: ["Powertrain", "Chassis Systems", ...]
    affected_pillars JSONB NOT NULL DEFAULT '[]',
    
    -- SOURCE TRAIL — links to sources table
    source_ids      INTEGER[] DEFAULT '{}',       -- Array of source.id values
    
    -- METADATA
    is_active       BOOLEAN DEFAULT TRUE,         -- Soft delete: set to false, never hard delete
    last_refreshed  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pestel_category ON pestel_factors(category);
CREATE INDEX IF NOT EXISTS idx_pestel_active ON pestel_factors(is_active);


-- ────────────────────────────────────────────────────────────
-- TABLE: technologies
-- Each row is one technology (e.g., "ADAS L2+ Camera Systems")
-- Contains market sizing, CAGR, maturity, and component breakdown
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS technologies (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(100) UNIQUE NOT NULL,  -- "adas_l2_camera" (URL-safe)
    name            VARCHAR(200) NOT NULL,         -- "ADAS L2+ Camera Systems"
    pillar          VARCHAR(100) NOT NULL,         -- "Vehicle Motion" (Bosch pillar)
    
    -- MARKET DATA (per segment, in Crore INR)
    -- Stored as JSONB: {"4W_PV": {"fy25": 1200, "fy30": 3400, "cagr": 23.2}, ...}
    market_data     JSONB NOT NULL DEFAULT '{}',
    
    -- AGGREGATE MARKET SIZE
    total_market_fy25_cr  FLOAT,                  -- Total across all segments (₹ Cr)
    total_market_fy30_cr  FLOAT,                  -- Projected FY2030
    cagr                  FLOAT,                  -- Compound annual growth rate %
    
    -- MATURITY & CONFIDENCE
    maturity        VARCHAR(20) NOT NULL,          -- "emerging" | "growth" | "mature" | "declining"
    confidence      VARCHAR(20) DEFAULT 'medium',  -- "high" | "medium" | "low"
    
    -- COMPONENT BREAKDOWN
    -- What's included in this technology (for "Includes:" display)
    includes        TEXT,                          -- "Front camera, radar, sensor fusion ECU, ..."
    
    -- SOURCE TRAIL
    source_ids      INTEGER[] DEFAULT '{}',
    
    -- REASONING
    analysis_reasoning TEXT,                       -- Why this market size, why this CAGR
    
    -- METADATA
    is_active       BOOLEAN DEFAULT TRUE,
    last_refreshed  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tech_pillar ON technologies(pillar);
CREATE INDEX IF NOT EXISTS idx_tech_maturity ON technologies(maturity);


-- ────────────────────────────────────────────────────────────
-- TABLE: validation_logs
-- AUDIT TRAIL for multi-LLM validation.
-- Every data point that passes through validation gets logged here.
-- This is what you show when someone asks "how do we trust this data?"
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS validation_logs (
    id              SERIAL PRIMARY KEY,
    
    -- WHAT was validated
    entity_type     VARCHAR(50) NOT NULL,          -- "pestel_factor" | "technology" | "market_data"
    entity_id       INTEGER,                       -- FK to pestel_factors.id or technologies.id
    data_point      VARCHAR(200) NOT NULL,          -- "exports_fy25" | "adas_market_size"
    claimed_value   TEXT NOT NULL,                  -- "$22.9B" | "₹1,200 Cr"
    
    -- PRIMARY LLM verdict
    primary_model   VARCHAR(100) NOT NULL,          -- "claude-sonnet-4-6"
    primary_verdict VARCHAR(20) NOT NULL,           -- "CONFIRMED" | "DISPUTED" | "UNCERTAIN"
    primary_confidence VARCHAR(20) NOT NULL,        -- "HIGH" | "MEDIUM" | "LOW"
    primary_reasoning TEXT NOT NULL,                -- Full reasoning text
    
    -- VALIDATOR LLM verdict (the second opinion)
    validator_model VARCHAR(100) NOT NULL,           -- "claude-haiku-4-5"
    validator_verdict VARCHAR(20) NOT NULL,
    validator_confidence VARCHAR(20) NOT NULL,
    validator_reasoning TEXT NOT NULL,
    
    -- CONSENSUS RESULT
    -- This is the final decision after both LLMs have spoken
    consensus       VARCHAR(20) NOT NULL,           -- "VERIFIED" | "FLAGGED" | "REJECTED" | "HUMAN_REVIEW"
    consensus_reasoning TEXT,                       -- Why this consensus was reached
    
    -- WEB SOURCE VERIFICATION (did we find a source confirming this?)
    web_source_url  TEXT,                           -- URL of confirming source
    web_source_excerpt TEXT,                        -- Relevant excerpt from source
    
    -- METADATA
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_validation_entity ON validation_logs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_validation_consensus ON validation_logs(consensus);


-- ────────────────────────────────────────────────────────────
-- TABLE: refresh_logs
-- Tracks every data refresh cycle — when it ran, what changed,
-- how many LLM calls it used, what it cost
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS refresh_logs (
    id              SERIAL PRIMARY KEY,
    trigger_type    VARCHAR(20) NOT NULL,          -- "scheduled" | "manual" | "startup"
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    status          VARCHAR(20) DEFAULT 'running', -- "running" | "completed" | "failed"
    
    -- What changed in this refresh
    new_factors     INTEGER DEFAULT 0,             -- How many new PESTEL factors discovered
    updated_factors INTEGER DEFAULT 0,             -- How many existing factors updated
    new_techs       INTEGER DEFAULT 0,
    updated_techs   INTEGER DEFAULT 0,
    
    -- Cost tracking
    llm_calls_made  INTEGER DEFAULT 0,
    estimated_cost_usd FLOAT DEFAULT 0,
    
    -- Errors
    error_message   TEXT,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ────────────────────────────────────────────────────────────
-- TABLE: analysis_cache
-- Stores pre-generated AI analysis for quick serving.
-- When user clicks a bubble, we serve from here if fresh enough.
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analysis_cache (
    id              SERIAL PRIMARY KEY,
    cache_key       VARCHAR(300) UNIQUE NOT NULL,  -- "pestel:india_eu_fta:4W_PV"
    analysis_type   VARCHAR(50) NOT NULL,          -- "pestel_detail" | "tech_agent" | "pillar_overview"
    content         JSONB NOT NULL,                -- The full analysis JSON
    segment         VARCHAR(20),                   -- "4W_PV" | "2W" | etc.
    generated_by    VARCHAR(100),                  -- Model that generated this
    expires_at      TIMESTAMPTZ NOT NULL,          -- When this cache entry expires
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cache_key ON analysis_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON analysis_cache(expires_at);
