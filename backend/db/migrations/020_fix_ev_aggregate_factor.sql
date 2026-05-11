-- Migration 020: Fix "EV penetration reaches 8%" aggregate-vs-segment mismatch
-- ---------------------------------------------------------------------------
-- Root cause: The LLM created one factor with the all-segment EV aggregate
-- (8% CY2025) and leaked H ratings to 4W PV and 2W even though:
--   4W PV: ~3% CY2025 (FADA: 5.8% Apr 2026, ~3% CY2025 average)
--   2W: ~6.5% CY2025
--   3W: ~58% CY2025 — this is the driver of the aggregate
--
-- Fix 1: Rename to make scope explicit (leadership sees the breakdown)
-- Fix 2: Downgrade 4W_PV and 2W from H to M; 3W stays H
-- Fix 3: Lower impact to reflect 4W-segment-accurate exposure
-- ---------------------------------------------------------------------------

UPDATE pestel_factors
SET
    name = 'India total EV penetration 8% CY2025 (3W:58%, 2W:7%, 4W:3%)',
    segment_relevance = jsonb_set(
        jsonb_set(
            COALESCE(segment_relevance, '{}'::jsonb),
            '{4W_PV}', '"M"'
        ),
        '{2W}', '"M"'
    ),
    impact = LEAST(impact, 6),
    impact_reasoning = 'All-segment aggregate 8% is dominated by 3W (58%) and 2W (~7%). For 4W PV specifically, EV penetration was ~3% in CY2025, rising to 5.8% by Apr 2026. Impact = 6 reflects 4W-segment-accurate exposure to EV-driven BOM restructuring.',
    last_refreshed = NOW()
WHERE name ILIKE '%EV penetration reaches 8%'
   OR name ILIKE '%EV penetration%8%%inflection%'
   OR name ILIKE '%EV penetration%CY2025%';

-- Also sync any variant names that follow the same pattern
-- (discovery agent may have created duplicates with slight name variation)
UPDATE pestel_factors
SET
    segment_relevance = jsonb_set(
        jsonb_set(
            COALESCE(segment_relevance, '{}'::jsonb),
            '{4W_PV}', '"M"'
        ),
        '{2W}', '"M"'
    ),
    last_refreshed = NOW()
WHERE is_active = TRUE
  AND name ILIKE '%EV penetration%8%'
  AND (segment_relevance->>'4W_PV') = 'H'
  AND (segment_relevance->>'3W') = 'H'
  AND (segment_relevance->>'2W') = 'H';

-- Verify
DO $$
DECLARE
    ev_factor RECORD;
BEGIN
    SELECT code, name, segment_relevance->>'4W_PV' AS rel_4w,
           segment_relevance->>'3W' AS rel_3w, impact
    INTO ev_factor
    FROM pestel_factors
    WHERE name ILIKE '%EV penetration%8%' AND is_active = TRUE
    LIMIT 1;

    IF FOUND THEN
        RAISE NOTICE 'Migration 020: EV factor "%"', ev_factor.name;
        RAISE NOTICE '  4W_PV=%  3W=%  impact=%',
            ev_factor.rel_4w, ev_factor.rel_3w, ev_factor.impact;
        IF ev_factor.rel_4w = 'H' THEN
            RAISE WARNING '  4W_PV still H — check name pattern';
        ELSE
            RAISE NOTICE '  4W_PV correctly downgraded from H to %', ev_factor.rel_4w;
        END IF;
    ELSE
        RAISE NOTICE 'Migration 020: EV 8%% factor not found (may already be correct or named differently)';
    END IF;
END $$;
