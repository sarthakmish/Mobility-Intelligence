-- ============================================================
-- MIGRATION 010: Competitors, market shares, OEM sourcing,
--                and PESTEL score history tables.
-- These were missing from earlier migrations.
-- All statements use IF NOT EXISTS — safe to re-run.
-- ============================================================

-- ── competitors ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS competitors (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(50) UNIQUE NOT NULL,
    name            VARCHAR(200) NOT NULL,
    short_name      VARCHAR(100),
    headquarters    VARCHAR(100),
    tier            VARCHAR(50),          -- 'Tier-1', 'Tech', 'OEM', etc.
    color           VARCHAR(20),          -- hex colour for UI
    india_presence  TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_competitors_active ON competitors(is_active);

-- ── competitor_pillar_shares ────────────────────────────────
CREATE TABLE IF NOT EXISTS competitor_pillar_shares (
    id                  SERIAL PRIMARY KEY,
    competitor_code     VARCHAR(50) NOT NULL REFERENCES competitors(code) ON DELETE CASCADE,
    pillar              VARCHAR(100) NOT NULL,
    segment             VARCHAR(50) NOT NULL,
    market_share_pct    NUMERIC(6,2) NOT NULL DEFAULT 0,
    revenue_cr          NUMERIC(12,2),
    confidence          VARCHAR(30) DEFAULT 'ai_estimate',
    source_note         TEXT,
    fiscal_year         VARCHAR(10) DEFAULT 'FY25',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (competitor_code, pillar, segment)
);
CREATE INDEX IF NOT EXISTS idx_comp_pillar_shares_pillar_seg ON competitor_pillar_shares(pillar, segment);

-- ── competitor_tech_shares ──────────────────────────────────
CREATE TABLE IF NOT EXISTS competitor_tech_shares (
    id                  SERIAL PRIMARY KEY,
    competitor_code     VARCHAR(50) NOT NULL REFERENCES competitors(code) ON DELETE CASCADE,
    tech_code           VARCHAR(100) NOT NULL,
    segment             VARCHAR(50) NOT NULL,
    market_share_pct    NUMERIC(6,2) NOT NULL DEFAULT 0,
    revenue_cr          NUMERIC(12,2),
    strength            VARCHAR(30) DEFAULT 'present',   -- 'market_leader','strong_presence','present','emerging'
    confidence          VARCHAR(30) DEFAULT 'ai_estimate',
    source_note         TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (competitor_code, tech_code, segment)
);
CREATE INDEX IF NOT EXISTS idx_comp_tech_shares_tech_seg ON competitor_tech_shares(tech_code, segment);

-- ── oem_sourcing ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS oem_sourcing (
    id              SERIAL PRIMARY KEY,
    oem_name        VARCHAR(200) NOT NULL,
    tech_code       VARCHAR(100) NOT NULL,
    segment         VARCHAR(50) NOT NULL,
    supplier_codes  TEXT[],               -- array of competitor codes
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (oem_name, tech_code, segment)
);
CREATE INDEX IF NOT EXISTS idx_oem_sourcing_tech_seg ON oem_sourcing(tech_code, segment);

-- ── pestel_score_history ────────────────────────────────────
CREATE TABLE IF NOT EXISTS pestel_score_history (
    id              SERIAL PRIMARY KEY,
    factor_code     VARCHAR(100) NOT NULL,
    likelihood      NUMERIC(4,2) NOT NULL,
    impact          NUMERIC(4,2) NOT NULL,
    segment         VARCHAR(50) DEFAULT 'ALL',
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source          VARCHAR(100) DEFAULT 'manual',
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_score_history_code ON pestel_score_history(factor_code, recorded_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_score_history_daily
    ON pestel_score_history (factor_code, DATE(recorded_at));
