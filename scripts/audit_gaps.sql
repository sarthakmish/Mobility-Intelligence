-- AUDIT 1: Tech market_data coverage by segment x pillar
SELECT 
  t.pillar,
  SUM(CASE WHEN (t.market_data->'4W_PV'->>'fy25')::numeric > 0 THEN 1 ELSE 0 END) AS "4W_PV",
  SUM(CASE WHEN (t.market_data->'2W'->>'fy25')::numeric > 0 THEN 1 ELSE 0 END) AS "2W",
  SUM(CASE WHEN (t.market_data->'3W'->>'fy25')::numeric > 0 THEN 1 ELSE 0 END) AS "3W",
  SUM(CASE WHEN (t.market_data->'LCV'->>'fy25')::numeric > 0 THEN 1 ELSE 0 END) AS "LCV",
  SUM(CASE WHEN (t.market_data->'HCV'->>'fy25')::numeric > 0 THEN 1 ELSE 0 END) AS "HCV",
  SUM(CASE WHEN (t.market_data->'Tractor'->>'fy25')::numeric > 0 THEN 1 ELSE 0 END) AS "Tractor",
  COUNT(*) AS total_techs
FROM technologies t
GROUP BY t.pillar ORDER BY t.pillar;
