-- ─────────────────────────────────────────────────────────────────────
-- Migration 015: Backfill origin_date for factors imported with NULL
-- ─────────────────────────────────────────────────────────────────────
-- Problem: All 108 active factors imported via migration 011 have origin_date = NULL.
-- This causes migration 012 to insert Jan 2025 history anchors for ALL factors,
-- which means a 2026 factor (e.g., India-EU FTA Jan 2026) appears in the
-- Jan 2025 baseline view — a visible bug.
--
-- Fix: derive origin_date from three sources, in priority order:
--   1. key_dates.announced from financial_context JSON (most reliable)
--   2. Year mentioned in factor name (e.g., "FY2027 norms", "Jan 2026")
--   3. created_at as a last resort (best available proxy)
-- ─────────────────────────────────────────────────────────────────────

-- ── Step 1: Extract from financial_context->key_dates.announced ──────
UPDATE pestel_factors f
SET origin_date = (
    CASE
        WHEN (financial_context->'key_dates'->>'announced') ~ '^\d{4}-\d{2}$'
            THEN ((financial_context->'key_dates'->>'announced') || '-01')::date
        WHEN (financial_context->'key_dates'->>'announced') ~ '^\d{4}-\d{2}-\d{2}$'
            THEN (financial_context->'key_dates'->>'announced')::date
        WHEN (financial_context->'key_dates'->>'announced') ~ '^\d{4}$'
            THEN ((financial_context->'key_dates'->>'announced') || '-01-01')::date
        ELSE NULL
    END
)
WHERE f.origin_date IS NULL
  AND f.financial_context IS NOT NULL
  AND (f.financial_context->'key_dates'->>'announced') IS NOT NULL
  AND (f.financial_context->'key_dates'->>'announced') != '';

-- ── Step 2: Extract from key_dates JSON column (separate from financial_context) ──
UPDATE pestel_factors f
SET origin_date = (
    CASE
        WHEN (key_dates->>'announced') ~ '^\d{4}-\d{2}$'
            THEN ((key_dates->>'announced') || '-01')::date
        WHEN (key_dates->>'announced') ~ '^\d{4}-\d{2}-\d{2}$'
            THEN (key_dates->>'announced')::date
        WHEN (key_dates->>'announced') ~ '^\d{4}$'
            THEN ((key_dates->>'announced') || '-01-01')::date
        ELSE NULL
    END
)
WHERE f.origin_date IS NULL
  AND f.key_dates IS NOT NULL
  AND (f.key_dates->>'announced') IS NOT NULL
  AND (f.key_dates->>'announced') != '';

-- ── Step 3: Pattern-match obvious year mentions in factor names ──────
UPDATE pestel_factors
SET origin_date = '2026-01-27'::date
WHERE origin_date IS NULL
  AND (name ILIKE '%india-eu fta%' OR name ILIKE '%india eu fta%');

UPDATE pestel_factors
SET origin_date = '2026-04-01'::date
WHERE origin_date IS NULL
  AND name ILIKE '%aeb mandatory%';

UPDATE pestel_factors
SET origin_date = '2026-04-01'::date
WHERE origin_date IS NULL
  AND name ILIKE '%trem v%';

UPDATE pestel_factors
SET origin_date = '2025-09-01'::date
WHERE origin_date IS NULL
  AND name ILIKE '%gst 2.0%';

UPDATE pestel_factors
SET origin_date = '2025-04-01'::date
WHERE origin_date IS NULL
  AND name ILIKE '%us tariff%';

UPDATE pestel_factors
SET origin_date = '2027-04-01'::date
WHERE origin_date IS NULL
  AND name ILIKE '%cafe iii%';

UPDATE pestel_factors
SET origin_date = '2024-10-01'::date
WHERE origin_date IS NULL
  AND (name ILIKE '%pm e-drive%' OR name ILIKE '%pm e drive%' OR name ILIKE '%fame iii%');

UPDATE pestel_factors
SET origin_date = '2021-09-15'::date
WHERE origin_date IS NULL
  AND name ILIKE '%pli scheme%';

UPDATE pestel_factors
SET origin_date = '2024-09-01'::date
WHERE origin_date IS NULL
  AND (name ILIKE '%fy26 record%' OR name ILIKE '%fy26 best%' OR name ILIKE '%fy26 sales%');

-- Generic regex fallback — extract first YYYY mention from name
UPDATE pestel_factors
SET origin_date = (substring(name from '(\d{4})') || '-01-01')::date
WHERE origin_date IS NULL
  AND name ~ '\d{4}'
  AND substring(name from '(\d{4})')::int BETWEEN 2014 AND 2027;

-- ── Step 4: Final fallback — use first_seen_date or created_at ──
UPDATE pestel_factors
SET origin_date = COALESCE(first_seen_date, created_at)::date
WHERE origin_date IS NULL;

-- ── Verify ─────────────────────────────────────────────────────────
DO $$
DECLARE
    null_count INT;
    total_count INT;
    by_year RECORD;
BEGIN
    SELECT COUNT(*) INTO null_count FROM pestel_factors WHERE origin_date IS NULL AND is_active = TRUE;
    SELECT COUNT(*) INTO total_count FROM pestel_factors WHERE is_active = TRUE;
    RAISE NOTICE 'Migration 015 complete: % factors total, % still NULL origin_date', total_count, null_count;

    FOR by_year IN
        SELECT EXTRACT(YEAR FROM origin_date) AS yr, COUNT(*) AS n
        FROM pestel_factors WHERE is_active = TRUE
        GROUP BY yr ORDER BY yr
    LOOP
        RAISE NOTICE '  Origin year %: % factors', by_year.yr, by_year.n;
    END LOOP;
END $$;
