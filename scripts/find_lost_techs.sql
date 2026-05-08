SELECT code, name, pillar FROM technologies
WHERE name ILIKE '%ECU%' OR name ILIKE '%gateway%' OR name ILIKE '%generic%module%'
   OR name ILIKE '%IGBT%' OR name ILIKE '%MOSFET%' OR name ILIKE '%SiC%' OR name ILIKE '%MEMS%' OR name ILIKE '%radar%module%' OR name ILIKE '%power semi%'
   OR name ILIKE '%fleet health%' OR name ILIKE '%charging%' OR name ILIKE '%logistics%'
ORDER BY pillar, name;
