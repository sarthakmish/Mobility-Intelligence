SELECT name,
    market_data->>'2W' as "2W",
    market_data->>'3W' as "3W",
    market_data->>'Tractor' as "Tractor"
FROM technologies
WHERE is_active = TRUE
  AND (
    (market_data->>'2W') IS NOT NULL AND (market_data->>'2W') != '0'
    OR (market_data->>'Tractor') IS NOT NULL AND (market_data->>'Tractor') != '0'
  )
ORDER BY name;
