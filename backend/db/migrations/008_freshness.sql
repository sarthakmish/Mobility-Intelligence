-- Migration 008: Freshness tracking for PESTEL factors
-- Distinguishes "we found this 3 hours ago and 4 sources confirmed it"
-- from "we found this 90 days ago, nobody's mentioned it since."

ALTER TABLE pestel_factors
    ADD COLUMN IF NOT EXISTS first_seen_date TIMESTAMPTZ;

ALTER TABLE pestel_factors
    ADD COLUMN IF NOT EXISTS last_confirmed_date TIMESTAMPTZ;

ALTER TABLE pestel_factors
    ADD COLUMN IF NOT EXISTS confirmation_count INTEGER DEFAULT 1;

-- Backfill existing rows: first_seen = created_at, last_confirmed = last_refreshed
UPDATE pestel_factors
SET first_seen_date = COALESCE(first_seen_date, created_at, NOW()),
    last_confirmed_date = COALESCE(last_confirmed_date, last_refreshed, NOW())
WHERE first_seen_date IS NULL OR last_confirmed_date IS NULL;

-- For foundational factors that have been around forever, set first_seen
-- to origin_date so the freshness tier is always "established," not "fresh"
UPDATE pestel_factors
SET first_seen_date = COALESCE(origin_date, first_seen_date)
WHERE is_foundational = TRUE AND origin_date IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_pestel_last_confirmed
    ON pestel_factors (last_confirmed_date DESC NULLS LAST)
    WHERE is_active = TRUE;

-- Verify
SELECT
    is_foundational,
    COUNT(*) AS count,
    MIN(first_seen_date) AS oldest_first_seen,
    MAX(last_confirmed_date) AS newest_confirm
FROM pestel_factors WHERE is_active = TRUE
GROUP BY is_foundational;
