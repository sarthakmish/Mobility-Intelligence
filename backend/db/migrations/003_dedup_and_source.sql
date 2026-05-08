-- ============================================================
-- Migration 003: PESTEL dedup (3-step) + technologies source_note
-- ============================================================
-- Run AFTER 002_normalize_pillars.sql.
-- Safe to re-run — all UPDATEs are idempotent or use IF NOT EXISTS.
-- ============================================================

-- ── PART A: PESTEL factor de-duplication ─────────────────────

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Step 1: Exact name duplicates — keep the first (lowest id)
UPDATE pestel_factors SET is_active = FALSE
WHERE id NOT IN (
    SELECT MIN(id) FROM pestel_factors WHERE is_active = TRUE GROUP BY name
) AND name IN (
    SELECT name FROM pestel_factors WHERE is_active = TRUE
    GROUP BY name HAVING COUNT(*) > 1
);

-- Step 2: Near-duplicates via first 25 chars of normalised name — keep lowest id
UPDATE pestel_factors SET is_active = FALSE
WHERE id NOT IN (
    SELECT MIN(id) FROM pestel_factors WHERE is_active = TRUE
    GROUP BY LEFT(LOWER(REGEXP_REPLACE(name, '[^a-z0-9 ]', '', 'gi')), 25)
) AND LEFT(LOWER(REGEXP_REPLACE(name, '[^a-z0-9 ]', '', 'gi')), 25) IN (
    SELECT LEFT(LOWER(REGEXP_REPLACE(name, '[^a-z0-9 ]', '', 'gi')), 25)
    FROM pestel_factors WHERE is_active = TRUE
    GROUP BY LEFT(LOWER(REGEXP_REPLACE(name, '[^a-z0-9 ]', '', 'gi')), 25)
    HAVING COUNT(*) > 1
);

-- Step 3: Fuzzy similarity > 0.45 — keep lowest id (older/first entry)
UPDATE pestel_factors SET is_active = FALSE
WHERE id IN (
    SELECT b.id FROM pestel_factors a
    JOIN pestel_factors b ON a.id < b.id
    WHERE a.is_active = TRUE AND b.is_active = TRUE
      AND similarity(lower(a.name), lower(b.name)) > 0.45
);

-- Step 4: Verify count (target: 40-55 active factors)
SELECT COUNT(*) AS remaining_active FROM pestel_factors WHERE is_active = TRUE;


-- ── PART B: technologies source_note column ───────────────────

ALTER TABLE technologies ADD COLUMN IF NOT EXISTS source_note VARCHAR(200);

-- Populate from analysis_reasoning for short entries (original hand-seeded data)
UPDATE technologies
SET source_note = analysis_reasoning
WHERE source_note IS NULL
  AND analysis_reasoning IS NOT NULL
  AND LENGTH(analysis_reasoning) < 100;

-- Long analysis_reasoning means it was AI-generated — label as estimate
UPDATE technologies
SET source_note = 'Industry estimate'
WHERE source_note IS NULL
  AND analysis_reasoning IS NOT NULL
  AND LENGTH(analysis_reasoning) >= 100;

-- Mark well-known published sources for core tech codes
UPDATE technologies SET source_note = 'ACMA FY25', confidence = 'high'
WHERE code IN (
    'powertrain_engine','transmission_and_drivetrain','braking_systems',
    'suspension_system','steering_eps','body_panels_and_structures',
    'chassis_frame','wiring_and_harness','wheels_and_components'
);

UPDATE technologies SET source_note = 'Mordor Intelligence', confidence = 'high'
WHERE code ILIKE '%auto_emergency%'
   OR code ILIKE '%adaptive_cruise%'
   OR code ILIKE '%lane_keep%'
   OR code ILIKE '%blind_spot%'
   OR code ILIKE '%driver_monitor%';

UPDATE technologies SET source_note = 'IBEF', confidence = 'medium'
WHERE code ILIKE '%battery_pack%';

UPDATE technologies SET source_note = 'IMARC Group', confidence = 'high'
WHERE code ILIKE '%safety_electronics%';

UPDATE technologies SET source_note = 'PS Market Research', confidence = 'high'
WHERE code ILIKE '%infotainment%' OR code ILIKE '%sensors_o2%';

-- Set SIAM Verified for segment volume data that's already in source_note
UPDATE technologies SET source_note = 'SIAM Verified'
WHERE source_note IS NULL AND pillar IN ('Motion', 'Actuators', 'ECUs');

-- Fallback: anything still NULL
UPDATE technologies SET source_note = 'Industry estimate'
WHERE source_note IS NULL;

-- Verify
SELECT source_note, COUNT(*) FROM technologies GROUP BY source_note ORDER BY COUNT(*) DESC;
