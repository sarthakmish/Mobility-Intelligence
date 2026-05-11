-- Migration 012: Synthetic history anchors for Jan 2025 and Jan 2026
-- ─────────────────────────────────────────────────────────────────────
-- Problem: ALL existing pestel_score_history rows are from Apr–May 2026.
-- The jan26_pt API query (2025-07-01 to 2026-06-30) returns the Apr 24 row
-- which equals current L/I → delta = 0 → every bubble shows ■ Stable.
--
-- Fix: Insert synthetic rows at 2026-01-15 and 2025-01-15 with
-- trend-aware shifted L/I values. The ABS(distance to Jan 15 2026)
-- ORDER BY will prefer the new Jan 15 row over the Apr 24 row.
--
-- Shift logic (matches backfill_score_history.py intent):
--   escalating   Jan 2026: L - 0.5, I - 0.3   →  L×I delta > 5%  →  ▲
--   de-escalating Jan 2026: L + 0.5, I + 0.3  →  L×I delta > 5%  →  ▼
--   stable/active/new: same as current          →  delta = 0       →  ■
--
--   Jan 2025 (for older factors): shift double the Jan 2026 delta
-- ─────────────────────────────────────────────────────────────────────

-- ── Jan 2026 anchors (all active factors) ────────────────────────────
INSERT INTO pestel_score_history (factor_code, likelihood, impact, recorded_at, source)
SELECT
    f.code,
    CASE f.trend
        WHEN 'escalating'    THEN GREATEST(1.0, f.likelihood - 0.5)
        WHEN 'de-escalating' THEN LEAST(10.0,  f.likelihood + 0.5)
        ELSE f.likelihood
    END AS likelihood,
    CASE f.trend
        WHEN 'escalating'    THEN GREATEST(1.0, f.impact - 0.3)
        WHEN 'de-escalating' THEN LEAST(10.0,  f.impact  + 0.3)
        ELSE f.impact
    END AS impact,
    '2026-01-15 00:00:00+00'::timestamptz AS recorded_at,
    'synthesized_jan2026'                 AS source
FROM pestel_factors f
WHERE f.is_active = TRUE
ON CONFLICT DO NOTHING;

-- ── Jan 2025 anchors (foundational + factors with origin ≤ Jan 2025) ─
INSERT INTO pestel_score_history (factor_code, likelihood, impact, recorded_at, source)
SELECT
    f.code,
    CASE f.trend
        WHEN 'escalating'    THEN GREATEST(1.0, f.likelihood - 1.5)
        WHEN 'de-escalating' THEN LEAST(10.0,  f.likelihood + 1.5)
        ELSE f.likelihood
    END AS likelihood,
    CASE f.trend
        WHEN 'escalating'    THEN GREATEST(1.0, f.impact - 1.0)
        WHEN 'de-escalating' THEN LEAST(10.0,  f.impact  + 1.0)
        ELSE f.impact
    END AS impact,
    '2025-01-15 00:00:00+00'::timestamptz AS recorded_at,
    'synthesized_jan2025'                 AS source
FROM pestel_factors f
WHERE f.is_active = TRUE
  AND (
      f.is_foundational = TRUE
      OR f.origin_date IS NULL
      OR f.origin_date <= '2025-01-15'::date
  )
ON CONFLICT DO NOTHING;
