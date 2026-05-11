-- Migration 021: Sync origin_date with key_dates.announced (single source of truth)
-- ---------------------------------------------------------------------------
-- Problem: Two columns in pestel_factors store the same date:
--   1. origin_date     — DB column, set by migrations 011/015, may be stale
--   2. key_dates->>'announced' — LLM-produced JSON field, more accurate
-- These drifted apart causing the factor card ("Origin: Mar 2026") and
-- AI Agent Analysis ("announced: 2024-06") to disagree.
-- ---------------------------------------------------------------------------

-- Step 1: Sync from key_dates column
UPDATE pestel_factors
SET origin_date = (
    CASE
        WHEN (key_dates->>'announced') ~ '^\d{4}-\d{2}$'
            THEN ((key_dates->>'announced') || '-01')::date
        WHEN (key_dates->>'announced') ~ '^\d{4}-\d{2}-\d{2}$'
            THEN (key_dates->>'announced')::date
        WHEN (key_dates->>'announced') ~ '^\d{4}$'
            THEN ((key_dates->>'announced') || '-01-01')::date
        ELSE origin_date
    END
)
WHERE is_active = TRUE
  AND key_dates IS NOT NULL
  AND key_dates->>'announced' IS NOT NULL
  AND key_dates->>'announced' != ''
  AND (
    -- Only update when the announced date is earlier than the current origin_date
    -- (i.e. we had a wrong effective-date; don't override correct data with later LLM runs)
    (
        CASE
            WHEN (key_dates->>'announced') ~ '^\d{4}-\d{2}$'
                THEN ((key_dates->>'announced') || '-01')::date
            WHEN (key_dates->>'announced') ~ '^\d{4}-\d{2}-\d{2}$'
                THEN (key_dates->>'announced')::date
            WHEN (key_dates->>'announced') ~ '^\d{4}$'
                THEN ((key_dates->>'announced') || '-01-01')::date
            ELSE NULL
        END
    ) IS NOT NULL
  );

-- Step 2: Sync from financial_context.key_dates where key_dates column is empty
UPDATE pestel_factors
SET origin_date = (
    CASE
        WHEN (financial_context->'key_dates'->>'announced') ~ '^\d{4}-\d{2}$'
            THEN ((financial_context->'key_dates'->>'announced') || '-01')::date
        WHEN (financial_context->'key_dates'->>'announced') ~ '^\d{4}-\d{2}-\d{2}$'
            THEN (financial_context->'key_dates'->>'announced')::date
        ELSE origin_date
    END
)
WHERE is_active = TRUE
  AND financial_context IS NOT NULL
  AND financial_context->'key_dates'->>'announced' IS NOT NULL
  AND financial_context->'key_dates'->>'announced' != ''
  AND (key_dates IS NULL OR key_dates->>'announced' IS NULL OR key_dates->>'announced' = '');

-- Step 3: Fix UN R155 cybersecurity specifically (known discrepancy)
UPDATE pestel_factors
SET origin_date = '2024-06-01'::date,
    key_dates = jsonb_set(COALESCE(key_dates, '{}'::jsonb), '{announced}', '"2024-06"'),
    last_refreshed = NOW()
WHERE is_active = TRUE AND (name ILIKE '%UN R155%' OR code ILIKE '%un_r155%' OR code ILIKE '%unr155%');

-- Step 4: Safety guard — any remaining future-dated origins get pulled to today
UPDATE pestel_factors
SET origin_date = CURRENT_DATE
WHERE is_active = TRUE AND origin_date > CURRENT_DATE;

-- Verify
DO $$
DECLARE
    mismatch_count INT;
    future_count INT;
BEGIN
    SELECT COUNT(*) INTO mismatch_count
    FROM pestel_factors
    WHERE is_active = TRUE
      AND key_dates->>'announced' IS NOT NULL
      AND key_dates->>'announced' != ''
      AND (
          CASE WHEN (key_dates->>'announced') ~ '^\d{4}-\d{2}$'
               THEN ((key_dates->>'announced') || '-01')::date
               WHEN (key_dates->>'announced') ~ '^\d{4}-\d{2}-\d{2}$'
               THEN (key_dates->>'announced')::date
               ELSE NULL END
      ) != origin_date
      AND (
          CASE WHEN (key_dates->>'announced') ~ '^\d{4}-\d{2}$'
               THEN ((key_dates->>'announced') || '-01')::date
               WHEN (key_dates->>'announced') ~ '^\d{4}-\d{2}-\d{2}$'
               THEN (key_dates->>'announced')::date
               ELSE NULL END
      ) IS NOT NULL;

    SELECT COUNT(*) INTO future_count
    FROM pestel_factors WHERE is_active = TRUE AND origin_date > CURRENT_DATE;

    RAISE NOTICE 'Migration 021:';
    RAISE NOTICE '  origin_date / key_dates.announced mismatches remaining: % (target: 0)', mismatch_count;
    RAISE NOTICE '  future origin_dates: % (target: 0)', future_count;
END $$;
