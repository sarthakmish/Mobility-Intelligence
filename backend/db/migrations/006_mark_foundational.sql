-- Mark foundational factors — long-standing policy, regulatory, structural factors
-- These are NEVER auto-removed by the AI refresh pipeline

UPDATE pestel_factors
SET is_foundational = TRUE
WHERE
    -- Key regulatory mandates
    code LIKE '%bsvi%'
    OR code LIKE '%aeb_mandate%'
    OR code LIKE '%aebs%'
    OR code LIKE '%fame%'
    OR code LIKE '%ethanol%'
    OR code LIKE '%sdv%'
    -- Key trade / macro factors
    OR code LIKE '%india_eu_fta%'
    OR code LIKE '%us_tariff%'
    OR code LIKE '%localisation%'
    OR code LIKE '%euro7%'
    -- Structural technology trends
    OR code LIKE '%ev_transition%'
    OR code LIKE '%battery_cost%'
    OR code LIKE '%gig_economy%'
    OR code LIKE '%premiumisation%';

-- Verify
SELECT COUNT(*) AS foundational_count FROM pestel_factors WHERE is_foundational = TRUE;
SELECT code, name, category FROM pestel_factors WHERE is_foundational = TRUE ORDER BY category, name;
