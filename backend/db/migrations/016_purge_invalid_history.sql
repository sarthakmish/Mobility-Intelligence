-- ─────────────────────────────────────────────────────────────────────
-- Migration 016: Remove history anchors for dates before factor origin
-- ─────────────────────────────────────────────────────────────────────
-- After migration 015 populated real origin_date values, some Jan 2025
-- and Jan 2026 history anchors are now invalid (they refer to dates
-- BEFORE the factor existed).
-- ─────────────────────────────────────────────────────────────────────

-- ── Delete Jan 2025 anchors for factors that emerged AFTER Jan 2025 ──
DELETE FROM pestel_score_history h
USING pestel_factors f
WHERE h.factor_code = f.code
  AND h.source = 'synthesized_jan2025'
  AND h.recorded_at = '2025-01-15 00:00:00+00'::timestamptz
  AND f.origin_date > '2025-01-15'::date;

-- ── Delete Jan 2026 anchors for factors that emerged AFTER Jan 2026 ──
DELETE FROM pestel_score_history h
USING pestel_factors f
WHERE h.factor_code = f.code
  AND h.source = 'synthesized_jan2026'
  AND h.recorded_at = '2026-01-15 00:00:00+00'::timestamptz
  AND f.origin_date > '2026-01-15'::date;

-- ── Verify ────────────────────────────────────────────────────────────
DO $$
DECLARE
    j25_count INT;
    j26_count INT;
    leaks_25 INT;
    leaks_26 INT;
BEGIN
    SELECT COUNT(*) INTO j25_count FROM pestel_score_history WHERE source = 'synthesized_jan2025';
    SELECT COUNT(*) INTO j26_count FROM pestel_score_history WHERE source = 'synthesized_jan2026';
    SELECT COUNT(*) INTO leaks_25 FROM pestel_score_history h
        JOIN pestel_factors f ON h.factor_code = f.code
        WHERE h.source = 'synthesized_jan2025' AND f.origin_date > '2025-01-15'::date;
    SELECT COUNT(*) INTO leaks_26 FROM pestel_score_history h
        JOIN pestel_factors f ON h.factor_code = f.code
        WHERE h.source = 'synthesized_jan2026' AND f.origin_date > '2026-01-15'::date;

    RAISE NOTICE 'Migration 016 complete:';
    RAISE NOTICE '  Jan 2025 anchors remaining: % (leaks: %)', j25_count, leaks_25;
    RAISE NOTICE '  Jan 2026 anchors remaining: % (leaks: %)', j26_count, leaks_26;
    IF leaks_25 > 0 OR leaks_26 > 0 THEN
        RAISE WARNING 'Some leaks remain — investigate manually';
    END IF;
END $$;
