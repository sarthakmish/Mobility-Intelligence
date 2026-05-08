-- Fix Semiconductors x Tractor: update segment_relevance for semiconductor factors
-- Tractors use ECUs/sensors/MCUs so semiconductor supply is M-relevance
UPDATE pestel_factors
SET segment_relevance = segment_relevance || '{"Tractor": "M"}'::jsonb
WHERE code = 'semiconductor_supply_normalisation'
  AND (segment_relevance->>'Tractor') NOT IN ('H', 'M');

-- Also widen the EV transition factor for Tractor (EV tractors are growing)
UPDATE pestel_factors
SET segment_relevance = jsonb_set(segment_relevance, '{Tractor}', '"M"')
WHERE code IN ('ev_transition_acceleration', 'battery_cost_decline')
  AND (segment_relevance->>'Tractor') = 'L';

-- Verify the fix
SELECT 
  p.id AS pillar,
  COUNT(DISTINCT CASE WHEN (f.segment_relevance->>'4W_PV') IN ('H','M') THEN f.code END) AS "4W_PV",
  COUNT(DISTINCT CASE WHEN (f.segment_relevance->>'2W') IN ('H','M') THEN f.code END) AS "2W",
  COUNT(DISTINCT CASE WHEN (f.segment_relevance->>'3W') IN ('H','M') THEN f.code END) AS "3W",
  COUNT(DISTINCT CASE WHEN (f.segment_relevance->>'LCV') IN ('H','M') THEN f.code END) AS "LCV",
  COUNT(DISTINCT CASE WHEN (f.segment_relevance->>'HCV') IN ('H','M') THEN f.code END) AS "HCV",
  COUNT(DISTINCT CASE WHEN (f.segment_relevance->>'Tractor') IN ('H','M') THEN f.code END) AS "Tractor"
FROM (VALUES ('ADAS'),('Motion'),('Energy'),('Body & Comfort'),('Infotainment'),
     ('OS'),('Compute'),('ECUs'),('Semiconductors'),('Actuators'),
     ('Solutions'),('Services'),('Cloud')) AS p(id)
LEFT JOIN pestel_factors f ON f.affected_pillars::text LIKE '%' || p.id || '%'
  AND f.is_active = true
GROUP BY p.id ORDER BY p.id;
