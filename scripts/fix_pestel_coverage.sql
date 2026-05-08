-- Add "Cloud" to connectivity/OTA/data factors
UPDATE pestel_factors
SET affected_pillars = affected_pillars || '["Cloud"]'::jsonb
WHERE code IN (
  'sdv_software_defined_vehicle',
  'connected_car_consumer_expectation',
  'cybersecurity_regulations_un155',
  'data_privacy_adas_regulations',
  'ai_ml_in_vehicle_diagnostics'
) AND NOT (affected_pillars @> '["Cloud"]'::jsonb);

-- Add "ECUs" to factors that reshape ECU architecture
UPDATE pestel_factors
SET affected_pillars = affected_pillars || '["ECUs"]'::jsonb
WHERE code IN (
  'sdv_software_defined_vehicle',
  'multi_oem_ev_platform_proliferation_-_software_fra',
  'cybersecurity_regulations_un155',
  'bsvi_stage2_mandate',
  'ev_transition_acceleration'
) AND NOT (affected_pillars @> '["ECUs"]'::jsonb);

-- Broader ECU match for the refresh-generated codes (code may be truncated)
UPDATE pestel_factors
SET affected_pillars = affected_pillars || '["ECUs"]'::jsonb
WHERE (name ILIKE '%software-defined%' OR name ILIKE '%OBD%' OR name ILIKE '%cybersecurity%' OR name ILIKE '%ECU%')
  AND NOT (affected_pillars @> '["ECUs"]'::jsonb);

-- Add "Semiconductors" to factors driving chip demand
UPDATE pestel_factors
SET affected_pillars = affected_pillars || '["Semiconductors"]'::jsonb
WHERE code IN (
  'semiconductor_supply_normalisation',
  'ev_transition_acceleration',
  'battery_cost_decline'
) AND NOT (affected_pillars @> '["Semiconductors"]'::jsonb);

UPDATE pestel_factors
SET affected_pillars = affected_pillars || '["Semiconductors"]'::jsonb
WHERE (name ILIKE '%semiconductor%' OR name ILIKE '%SiC%' OR name ILIKE '%chip%')
  AND NOT (affected_pillars @> '["Semiconductors"]'::jsonb);

-- Add "Solutions" to fleet/aftermarket/service factors
UPDATE pestel_factors
SET affected_pillars = affected_pillars || '["Solutions"]'::jsonb
WHERE code IN (
  'corporate_fleet_decarbonisation',
  'scrappage_policy_fleet_renewal',
  'gig_economy_3w_ev_demand',
  'ai_ml_in_vehicle_diagnostics'
) AND NOT (affected_pillars @> '["Solutions"]'::jsonb);

UPDATE pestel_factors
SET affected_pillars = affected_pillars || '["Solutions"]'::jsonb
WHERE (name ILIKE '%fleet%' OR name ILIKE '%aftermarket%' OR name ILIKE '%maintenance%' OR name ILIKE '%scrappage%')
  AND NOT (affected_pillars @> '["Solutions"]'::jsonb);

-- Final coverage report
SELECT p.id AS pillar,
  COUNT(DISTINCT f.code) AS pestel_forces
FROM (VALUES ('ADAS'),('Motion'),('Energy'),('Body & Comfort'),('Infotainment'),('OS'),('Compute'),('ECUs'),('Semiconductors'),('Actuators'),('Solutions'),('Services'),('Cloud')) AS p(id)
LEFT JOIN pestel_factors f ON f.affected_pillars::text LIKE '%' || p.id || '%'
GROUP BY p.id ORDER BY pestel_forces ASC, p.id;
