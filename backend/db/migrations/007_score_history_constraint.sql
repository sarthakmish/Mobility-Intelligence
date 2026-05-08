-- Migration 007: prevent duplicate snapshots on same date
-- The backfill script (Prompt 2) uses ON CONFLICT DO NOTHING
-- so this unique index needs to exist first.

CREATE UNIQUE INDEX IF NOT EXISTS idx_score_history_unique
ON pestel_score_history (factor_code, DATE(recorded_at));

-- Index for fast timeline lookup
CREATE INDEX IF NOT EXISTS idx_score_history_factor
ON pestel_score_history (factor_code, recorded_at ASC);
