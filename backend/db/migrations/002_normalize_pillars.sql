-- ============================================================
-- Migration 002: Normalize affected_pillars on existing PESTEL factors
-- ============================================================
-- Problem: Factors added by AI during refresh use long pillar names
-- (e.g. "Powertrain Solutions") that don't match the short IDs used
-- in the technologies table (e.g. "Motion").
-- This causes the Financial Overlay to show "—" because
-- TECHS.filter(tt => tt.p === pid) finds no match.
--
-- Run once after deploying the orchestrator Fix 3.
-- Safe to re-run (CASE ELSE preserves already-correct values).
-- ============================================================

UPDATE pestel_factors
SET affected_pillars = (
    SELECT COALESCE(
        jsonb_agg(DISTINCT
            CASE elem
                WHEN 'Powertrain Solutions'       THEN 'Motion'
                WHEN 'Chassis Systems'            THEN 'Motion'
                WHEN 'Vehicle Motion'             THEN 'Motion'
                WHEN 'Drivetrain'                 THEN 'Motion'
                WHEN 'EV Powertrain'              THEN 'Energy'
                WHEN 'Energy & Charging'          THEN 'Energy'
                WHEN 'Thermal Management'         THEN 'Energy'
                WHEN 'Battery Systems'            THEN 'Energy'
                WHEN 'Body Electronics'           THEN 'Infotainment'
                WHEN 'Vehicle Diagnostics'        THEN 'Infotainment'
                WHEN 'Infotainment & Connectivity' THEN 'Infotainment'
                WHEN 'Electronics'               THEN 'Infotainment'
                WHEN 'Software & Services'        THEN 'OS'
                WHEN 'Vehicle OS'                 THEN 'OS'
                WHEN 'Manufacturing & Industry 4.0' THEN 'Compute'
                WHEN 'Aftermarket & Retrofit'     THEN 'Services'
                WHEN 'Aftermarket'                THEN 'Services'
                WHEN 'Safety & Security'          THEN 'ADAS'
                WHEN 'Autonomous Driving'         THEN 'ADAS'
                WHEN 'Sensors & Actuators'        THEN 'Actuators'
                WHEN 'Power Tools'                THEN 'Actuators'
                ELSE elem   -- already a valid short ID — keep as-is
            END
        ),
        '["Motion"]'::jsonb   -- fallback if array is NULL/empty
    )
    FROM jsonb_array_elements_text(affected_pillars) AS elem
)
WHERE affected_pillars IS NOT NULL
  AND affected_pillars != '[]'::jsonb;

-- Verify: show any factors that still have non-standard pillar values
-- (i.e. values not in the VALID_PILLARS set used by the frontend)
SELECT code, name, affected_pillars
FROM pestel_factors
WHERE is_active = TRUE
  AND affected_pillars::text !~ '"(ADAS|Motion|Energy|Body & Comfort|Infotainment|OS|Compute|ECUs|Semiconductors|Actuators|Solutions|Services|Cloud)"'
ORDER BY updated_at DESC
LIMIT 20;

-- ============================================================
-- Step 3: De-duplicate near-identical factor names via pg_trgm
-- ============================================================
-- Requires pg_trgm extension (ships with standard PostgreSQL).
-- Marks lower-scoring duplicates inactive.
-- Run AFTER Step 1 above so pillars are normalised first.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Mark the lower-scoring factor inactive when two factors share
-- similarity > 0.4 (roughly "same 3+ words in same order").
-- The one with the higher L×I score is kept active.
UPDATE pestel_factors AS p
SET is_active = FALSE
WHERE p.id IN (
    SELECT p2.id
    FROM pestel_factors p1
    JOIN pestel_factors p2 ON p1.id < p2.id
    WHERE similarity(p1.name, p2.name) > 0.4
      AND p1.is_active = TRUE
      AND p2.is_active = TRUE
      AND (p1.likelihood * p1.impact) >= (p2.likelihood * p2.impact)
);

-- Step 4: Verify final count (target: 40-55 active factors)
SELECT COUNT(*) AS active_factor_count FROM pestel_factors WHERE is_active = TRUE;
