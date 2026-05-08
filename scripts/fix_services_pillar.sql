-- Move telematics and cybersecurity services to Services pillar
UPDATE technologies SET pillar = 'Services'
WHERE code IN ('telematics_connected_vehicle', 'vsoc_cybersecurity');

-- Add 4W_PV market data to fleet_management_saas
UPDATE technologies
SET market_data = market_data || '{"4W_PV": {"cagr": 31.2, "fy25": 120, "fy30": 480}}'::jsonb
WHERE code = 'fleet_management_saas';

-- Verify Services pillar
SELECT code, name, pillar, total_market_fy25_cr, LEFT(market_data::text, 100) as mkt
FROM technologies WHERE pillar = 'Services' ORDER BY code;

-- Final all-pillar summary
SELECT pillar, COUNT(*) AS techs, SUM(total_market_fy25_cr) AS market_cr
FROM technologies GROUP BY pillar ORDER BY pillar;
