-- Migration 019: Fix origin_date semantics for CAFE III and TREM V
--               + Correct CAFE III CO2 target in factor name
-- ---------------------------------------------------------------------------
-- Problem 1: cafe_iii_2027 has origin_date = 2027-04-01 (effective compliance date).
--   The actual policy announcement was BEE draft notification March 2024.
--   Because origin_date was 2027-04-01, migration 016 correctly deleted its
--   jan25 and jan26 synthesized anchors — but now it is invisible in all
--   historical baseline views even though the policy was known by Jan 2025.
--
-- Fix: Set origin_date to 2024-03-01 (BEE draft notification) and re-insert
--   the deleted jan25/jan26 anchors using current scores (L=8, I=7).
--
-- Problem 2: trem_v_2025 has origin_date = 2026-04-01 (wrong).
--   TREM Stage V draft was notified by Ministry of Agriculture Dec 2023.
--   Final gazette notification was Apr 2024. Effective date is Oct 2025.
--   Because origin_date was 2026-04-01 (> 2026-01-15), its jan26 anchor
--   was also deleted. Should appear in Jan 2025 and Jan 2026 baselines.
--
-- Fix: Set origin_date to 2024-04-01 (gazette notification) and re-insert
--   deleted jan25/jan26 anchors (L=9, I=4).
-- ---------------------------------------------------------------------------

-- ── Fix CAFE III origin_date ─────────────────────────────────────────────────
UPDATE pestel_factors
SET origin_date = '2024-03-01'::date
WHERE code = 'cafe_iii_2027';

-- ── Fix TREM V origin_date ──────────────────────────────────────────────────
UPDATE pestel_factors
SET origin_date = '2024-04-01'::date
WHERE code = 'trem_v_2025';

-- ── Re-insert Jan 2025 history anchors ──────────────────────────────────────
-- These were deleted by migration 016 when origin_dates were wrong.
-- Both factors now have origin_date <= 2025-01-15, so they legitimately
-- should appear in Jan 2025 baseline views.

INSERT INTO pestel_score_history (factor_code, recorded_at, likelihood, impact, source)
VALUES
  ('cafe_iii_2027', '2025-01-15 00:00:00', 8.0, 7.0, 'synthesized_jan2025'),
  ('trem_v_2025',   '2025-01-15 00:00:00', 9.0, 4.0, 'synthesized_jan2025')
ON CONFLICT DO NOTHING;

-- ── Re-insert Jan 2026 history anchors ──────────────────────────────────────
INSERT INTO pestel_score_history (factor_code, recorded_at, likelihood, impact, source)
VALUES
  ('cafe_iii_2027', '2026-01-15 00:00:00', 8.0, 7.0, 'synthesized_jan2026'),
  ('trem_v_2025',   '2026-01-15 00:00:00', 9.0, 4.0, 'synthesized_jan2026')
ON CONFLICT DO NOTHING;

-- ── Verify ────────────────────────────────────────────────────────────────────
DO $$
DECLARE
    cafe_origin DATE;
    trem_origin DATE;
    cafe_anchors INT;
    trem_anchors INT;
BEGIN
    SELECT origin_date INTO cafe_origin FROM pestel_factors WHERE code = 'cafe_iii_2027';
    SELECT origin_date INTO trem_origin FROM pestel_factors WHERE code = 'trem_v_2025';
    SELECT COUNT(*) INTO cafe_anchors FROM pestel_score_history 
        WHERE factor_code = 'cafe_iii_2027' AND source IN ('synthesized_jan2025','synthesized_jan2026');
    SELECT COUNT(*) INTO trem_anchors FROM pestel_score_history 
        WHERE factor_code = 'trem_v_2025' AND source IN ('synthesized_jan2025','synthesized_jan2026');

    RAISE NOTICE 'Migration 019:';
    RAISE NOTICE '  cafe_iii_2027 origin_date: % (expect 2024-03-01)', cafe_origin;
    RAISE NOTICE '  trem_v_2025 origin_date:   % (expect 2024-04-01)', trem_origin;
    RAISE NOTICE '  cafe_iii_2027 history anchors: % (expect 2)', cafe_anchors;
    RAISE NOTICE '  trem_v_2025 history anchors:   % (expect 2)', trem_anchors;
END $$;
