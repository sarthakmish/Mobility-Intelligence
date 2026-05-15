"""SQL schema + backfill for competitor tables and score history."""
import asyncio
import asyncpg
import os

SQL = """
CREATE TABLE IF NOT EXISTS competitors (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    short_name VARCHAR(50),
    headquarters VARCHAR(100),
    tier VARCHAR(20) DEFAULT 'Tier-1',
    india_presence TEXT,
    key_products TEXT,
    color VARCHAR(10) DEFAULT '#888780',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS competitor_pillar_shares (
    id SERIAL PRIMARY KEY,
    competitor_code VARCHAR(50) REFERENCES competitors(code),
    pillar VARCHAR(50) NOT NULL,
    segment VARCHAR(20) NOT NULL,
    market_share_pct DECIMAL(5,2),
    revenue_cr DECIMAL(10,1),
    confidence VARCHAR(20) DEFAULT 'ai_estimate',
    source_note TEXT,
    fiscal_year VARCHAR(10) DEFAULT 'FY25',
    UNIQUE(competitor_code, pillar, segment)
);

CREATE TABLE IF NOT EXISTS competitor_tech_shares (
    id SERIAL PRIMARY KEY,
    competitor_code VARCHAR(50) REFERENCES competitors(code),
    tech_code VARCHAR(100) NOT NULL,
    segment VARCHAR(20) NOT NULL,
    market_share_pct DECIMAL(5,2),
    revenue_cr DECIMAL(10,1),
    strength VARCHAR(20) DEFAULT 'present',
    confidence VARCHAR(20) DEFAULT 'ai_estimate',
    source_note TEXT,
    UNIQUE(competitor_code, tech_code, segment)
);

CREATE TABLE IF NOT EXISTS oem_sourcing (
    id SERIAL PRIMARY KEY,
    oem_name VARCHAR(100) NOT NULL,
    tech_code VARCHAR(100) NOT NULL,
    segment VARCHAR(20) NOT NULL,
    supplier_codes TEXT NOT NULL,
    notes TEXT,
    UNIQUE(oem_name, tech_code, segment)
);

CREATE TABLE IF NOT EXISTS pestel_score_history (
    id SERIAL PRIMARY KEY,
    factor_code VARCHAR(50) NOT NULL,
    recorded_at TIMESTAMP DEFAULT NOW(),
    likelihood FLOAT NOT NULL,
    impact FLOAT NOT NULL,
    source VARCHAR(50) DEFAULT 'refresh',
    UNIQUE(factor_code, recorded_at)
);
"""

BACKFILL = """
INSERT INTO pestel_score_history (factor_code, recorded_at, likelihood, impact, source)
SELECT code, NOW(), likelihood, impact, 'initial_backfill'
FROM pestel_factors WHERE is_active = TRUE
ON CONFLICT DO NOTHING;
"""

async def run():
    conn = await asyncpg.connect(
        os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/mobility_intelligence").replace("postgresql+asyncpg://", "postgresql://")
    )
    await conn.execute(SQL)
    print("Tables created.")
    status = await conn.execute(BACKFILL)
    print(f"Score history backfill: {status}")
    count = await conn.fetchval("SELECT COUNT(*) FROM pestel_score_history")
    print(f"Total score history rows: {count}")
    await conn.close()

asyncio.run(run())
