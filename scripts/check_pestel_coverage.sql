SELECT p.id AS pillar,
  COUNT(DISTINCT f.code) AS pestel_forces
FROM (VALUES ('ADAS'),('Motion'),('Energy'),('Body & Comfort'),('Infotainment'),('OS'),('Compute'),('ECUs'),('Semiconductors'),('Actuators'),('Solutions'),('Services'),('Cloud')) AS p(id)
LEFT JOIN pestel_factors f ON f.affected_pillars::text LIKE '%' || p.id || '%'
GROUP BY p.id ORDER BY pestel_forces ASC, p.id;
