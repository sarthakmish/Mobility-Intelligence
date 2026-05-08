-- PESTEL: H/M relevance forces per segment x pillar
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
