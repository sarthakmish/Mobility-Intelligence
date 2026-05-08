-- ============================================================
-- Re-home techs to populate empty pillars: ECUs, Semiconductors, Solutions
-- ============================================================

-- SEMICONDUCTORS: MEMS + HV sensors are fundamentally semiconductor components
UPDATE technologies SET pillar = 'Semiconductors'
WHERE code IN ('mems_inertial_sensors', 'ev_current_voltage_sensors');

-- ECUs: Airbag ECU and BCM (Body Control Module) are literally ECU hardware
UPDATE technologies SET pillar = 'ECUs'
WHERE code IN ('airbag_occupant_safety', 'bcm_body_control_module');

-- SOLUTIONS: Aftermarket digital platform + AI predictive maintenance = service solutions
UPDATE technologies SET pillar = 'Solutions'
WHERE code IN ('aftermarket_parts_platform', 'predictive_maintenance_fleet');

-- VERIFY: All 13 pillars with tech counts and total market
SELECT pillar, COUNT(*) AS techs, SUM(total_market_fy25_cr) AS total_market_cr
FROM technologies
GROUP BY pillar
ORDER BY pillar;
