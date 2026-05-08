-- Fix PESTEL pillar coverage using actual DB factor codes
-- ADAS: safety regs, bharat ncap, road safety awareness, L3 radar, AEB mandate, product liability, cybersecurity, DMS
UPDATE pestel_factors
SET affected_pillars = affected_pillars || '["ADAS"]'::jsonb
WHERE (
  code IN (
    'bharat_ncap_mandatory',
    'road_safety_awareness',
    'adas_l3_radar_lidar_readiness',
    'hcv_safety_norms_aebs',
    'aeb_mandate_2026',
    'product_liability_adas',
    'data_privacy_adas_regulations',
    'cybersecurity_regulations_un155',
    'sdv_software_defined_vehicle',
    'bsvi_stage2_mandate'
  )
  OR name ILIKE '%ADAS%'
  OR name ILIKE '%AEB%'
  OR name ILIKE '%NCAP%'
  OR name ILIKE '%LiDAR%'
  OR name ILIKE '%radar%'
  OR name ILIKE '%autonomous%'
  OR name ILIKE '%driver monitor%'
  OR name ILIKE '%safety norm%'
)
AND NOT (affected_pillars @> '["ADAS"]'::jsonb);

-- Actuators: brake norms, AEBS, BS-VI, emission controls, safety actuators, EPS
UPDATE pestel_factors
SET affected_pillars = affected_pillars || '["Actuators"]'::jsonb
WHERE (
  code IN (
    'bharat_ncap_mandatory',
    'hcv_safety_norms_aebs',
    'aeb_mandate_2026',
    'bsvi_stage2_mandate',
    'euro7_rde_compliance_export',
    'road_safety_awareness',
    'ethanol_blending_programme_-_e20_mandate_driving_f',
    'scrappage_policy_fleet_renewal'
  )
  OR name ILIKE '%brake%'
  OR name ILIKE '%actuator%'
  OR name ILIKE '%sensor%'
  OR name ILIKE '%AEBS%'
  OR name ILIKE '%BS-VI%'
  OR name ILIKE '%emission%'
  OR name ILIKE '%exhaust%'
  OR name ILIKE '%steering%'
)
AND NOT (affected_pillars @> '["Actuators"]'::jsonb);

-- Semiconductors: supply chain, SiC demand, EV transition (drives power electronics), PLI chip
UPDATE pestel_factors
SET affected_pillars = affected_pillars || '["Semiconductors"]'::jsonb
WHERE (
  code IN (
    'semiconductor_supply_normalisation',
    'ev_transition_acceleration',
    'battery_cost_decline',
    'sdv_software_defined_vehicle',
    'pli_scheme_disbursement',
    'adas_l3_radar_lidar_readiness',
    'india_eu_fta',
    'us_tariffs_2025'
  )
  OR name ILIKE '%semiconductor%'
  OR name ILIKE '%SiC%'
  OR name ILIKE '%chip%'
  OR name ILIKE '%power electronics%'
  OR name ILIKE '%IGBT%'
  OR name ILIKE '%MEMS%'
)
AND NOT (affected_pillars @> '["Semiconductors"]'::jsonb);

-- ECUs: SDV/OTA reshapes ECU architecture, OBD-II compliance, cybersecurity mandates, AEB ECU, airbag ECU
UPDATE pestel_factors
SET affected_pillars = affected_pillars || '["ECUs"]'::jsonb
WHERE (
  code IN (
    'sdv_software_defined_vehicle',
    'bsvi_stage2_mandate',
    'cybersecurity_regulations_un155',
    'data_privacy_adas_regulations',
    'aeb_mandate_2026',
    'bharat_ncap_mandatory',
    'hcv_safety_norms_aebs',
    'multi_oem_ev_platform_proliferation_-_software_fra',
    'adas_l3_radar_lidar_readiness'
  )
  OR name ILIKE '%ECU%'
  OR name ILIKE '%OBD%'
  OR name ILIKE '%software-defined%'
  OR name ILIKE '%cybersecurity%'
  OR name ILIKE '%type approval%'
)
AND NOT (affected_pillars @> '["ECUs"]'::jsonb);

-- Solutions: fleet decarbonisation, gig economy fleet, predictive maintenance, scrappage, PLI
UPDATE pestel_factors
SET affected_pillars = affected_pillars || '["Solutions"]'::jsonb
WHERE (
  code IN (
    'corporate_fleet_decarbonisation',
    'scrappage_policy_fleet_renewal',
    'gig_economy_3w_ev_demand',
    'ai_ml_in_vehicle_diagnostics',
    'fame_iii_charging',
    'pli_scheme_disbursement',
    'india_auto_exports_22b'
  )
  OR name ILIKE '%fleet%'
  OR name ILIKE '%aftermarket%'
  OR name ILIKE '%maintenance%'
  OR name ILIKE '%scrappage%'
  OR name ILIKE '%workshop%'
  OR name ILIKE '%retrofit%'
)
AND NOT (affected_pillars @> '["Solutions"]'::jsonb);

-- Services: connected car, fleet management, AI diagnostics, telematics
UPDATE pestel_factors
SET affected_pillars = affected_pillars || '["Services"]'::jsonb
WHERE (
  code IN (
    'connected_car_consumer_expectation',
    'ai_ml_in_vehicle_diagnostics',
    'corporate_fleet_decarbonisation',
    'gig_economy_3w_ev_demand',
    'sdv_software_defined_vehicle',
    'data_privacy_adas_regulations'
  )
  OR name ILIKE '%connected%'
  OR name ILIKE '%telematics%'
  OR name ILIKE '%diagnostic%'
  OR name ILIKE '%service%'
  OR name ILIKE '%subscription%'
  OR name ILIKE '%maps%'
  OR name ILIKE '%rideshare%'
)
AND NOT (affected_pillars @> '["Services"]'::jsonb);

-- Cloud: OTA, connected, AI/ML cloud, SDV, telematics
UPDATE pestel_factors
SET affected_pillars = affected_pillars || '["Cloud"]'::jsonb
WHERE (
  code IN (
    'sdv_software_defined_vehicle',
    'connected_car_consumer_expectation',
    'cybersecurity_regulations_un155',
    'data_privacy_adas_regulations',
    'ai_ml_in_vehicle_diagnostics',
    'corporate_fleet_decarbonisation',
    'multi_oem_ev_platform_proliferation_-_software_fra'
  )
  OR name ILIKE '%OTA%'
  OR name ILIKE '%telematics%'
  OR name ILIKE '%cloud%'
  OR name ILIKE '%connected%'
  OR name ILIKE '%data monetis%'
  OR name ILIKE '%cybersecurity%'
  OR name ILIKE '%software%update%'
)
AND NOT (affected_pillars @> '["Cloud"]'::jsonb);

-- Final coverage check
SELECT p.id AS pillar,
  COUNT(DISTINCT f.code) AS pestel_forces
FROM (VALUES ('ADAS'),('Motion'),('Energy'),('Body & Comfort'),('Infotainment'),
     ('OS'),('Compute'),('ECUs'),('Semiconductors'),('Actuators'),
     ('Solutions'),('Services'),('Cloud')) AS p(id)
LEFT JOIN pestel_factors f ON f.affected_pillars::text LIKE '%' || p.id || '%'
GROUP BY p.id ORDER BY pestel_forces DESC;
