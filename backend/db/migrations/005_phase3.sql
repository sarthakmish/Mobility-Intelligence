-- ============================================================
-- MIGRATION 005 — Phase 3: CEO-Grade Hardening
-- ============================================================
-- Run: psql -U postgres -d mobility_intelligence -f 005_phase3.sql
-- ============================================================

-- ── Foundational factors flag ─────────────────────────────
-- Factors marked foundational are NEVER auto-removed by AI refresh
ALTER TABLE pestel_factors ADD COLUMN IF NOT EXISTS is_foundational BOOLEAN DEFAULT FALSE;

-- ── Source-grounded verification columns ──────────────────
ALTER TABLE pestel_factors ADD COLUMN IF NOT EXISTS verification_verdict VARCHAR(30) DEFAULT 'UNVERIFIED';
ALTER TABLE pestel_factors ADD COLUMN IF NOT EXISTS verification_source VARCHAR(200);
ALTER TABLE pestel_factors ADD COLUMN IF NOT EXISTS verification_evidence TEXT;

-- ── Financial context + key dates + citations ─────────────
ALTER TABLE pestel_factors ADD COLUMN IF NOT EXISTS financial_context JSONB DEFAULT '{}';
ALTER TABLE pestel_factors ADD COLUMN IF NOT EXISTS key_dates JSONB DEFAULT '{}';
ALTER TABLE pestel_factors ADD COLUMN IF NOT EXISTS citations JSONB DEFAULT '[]';

-- ── Tech: ensure source_note exists ──────────────────────
ALTER TABLE technologies ADD COLUMN IF NOT EXISTS source_note VARCHAR(200);

-- ── Mark foundational factors ─────────────────────────────
-- These are NEVER removed by AI refresh — they are structural/historical
UPDATE pestel_factors SET is_foundational = TRUE
WHERE code IN (
  'pli','fame3','make','gst','tariff','suv','ev','rare','geo',
  'safe','conn','rural','sic','sdv','l2','ai','bs6','nz','lw',
  'bncap','a189','a140','aebs','tremV','tractElec','obd2w','ev2w',
  'cvreg','cvfleet','3wev','euFta','euCbam'
);

-- ── Verify ────────────────────────────────────────────────
SELECT COUNT(*) AS foundational_count FROM pestel_factors WHERE is_foundational = TRUE;
SELECT COUNT(*) AS total_active FROM pestel_factors WHERE is_active = TRUE;
SELECT column_name FROM information_schema.columns
  WHERE table_name = 'pestel_factors'
  ORDER BY ordinal_position;
