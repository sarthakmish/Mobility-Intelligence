-- ════════════════════════════════════════════════════════════
-- SEED DATA CLEANUP: Zero out market sizes for impossible tech-segment combos
-- Run this ONCE against the mobility_intelligence database
-- ════════════════════════════════════════════════════════════

-- 1. Diesel aftertreatment (SCR/DPF/common rail): zero for 2W and 3W
UPDATE technologies SET market_data = jsonb_set(
    jsonb_set(market_data, '{2W}', '0'), '{3W}', '0'
)
WHERE name ILIKE '%SCR%DPF%' OR name ILIKE '%common rail diesel%'
   OR name ILIKE '%diesel injection%' OR name ILIKE '%diesel particulate%'
   OR name ILIKE '%aftertreatment%';

-- 2. Heavy ADAS (camera L2+, front radar, LiDAR, surround view, adaptive cruise,
--    lane keep, blind spot, traffic sign, driver monitoring, cabin camera, parking assist):
--    zero for 2W, 3W, Tractor
UPDATE technologies SET market_data = jsonb_set(
    jsonb_set(jsonb_set(market_data, '{2W}', '0'), '{3W}', '0'), '{Tractor}', '0'
)
WHERE name ILIKE '%L2+%camera%' OR name ILIKE '%front radar%'
   OR name ILIKE '%lidar%' OR name ILIKE '%surround view%'
   OR name ILIKE '%adaptive cruise%' OR name ILIKE '%lane keep%'
   OR name ILIKE '%blind spot%' OR name ILIKE '%traffic sign%'
   OR name ILIKE '%driver monitor%' OR name ILIKE '%cabin camera%'
   OR name ILIKE '%parking assist%';

-- 3. Battery swapping: zero for 4W_PV, HCV, Tractor (2W/3W only)
UPDATE technologies SET market_data = jsonb_set(
    jsonb_set(jsonb_set(market_data, '{4W_PV}', '0'), '{HCV}', '0'), '{Tractor}', '0'
)
WHERE name ILIKE '%battery swap%';

-- 4. 2W/3W EV hub motor: zero for 4W_PV, HCV, Tractor
UPDATE technologies SET market_data = jsonb_set(
    jsonb_set(jsonb_set(market_data, '{4W_PV}', '0'), '{HCV}', '0'), '{Tractor}', '0'
)
WHERE name ILIKE '%hub motor%' AND (name ILIKE '%2W%' OR name ILIKE '%3W%');

-- 5. Air disc brakes: zero for 2W, 3W, Tractor (HCV/bus technology)
UPDATE technologies SET market_data = jsonb_set(
    jsonb_set(jsonb_set(market_data, '{2W}', '0'), '{3W}', '0'), '{Tractor}', '0'
)
WHERE name ILIKE '%air disc brake%';

-- 6. Heavy-duty EV powertrain (eTruck/eBus): zero for 2W, 3W, 4W_PV, Tractor
UPDATE technologies SET market_data = jsonb_set(
    jsonb_set(jsonb_set(jsonb_set(market_data, '{2W}', '0'), '{3W}', '0'), '{4W_PV}', '0'), '{Tractor}', '0'
)
WHERE name ILIKE '%heavy-duty%ev%' OR name ILIKE '%etruck%' OR name ILIKE '%ebus%';

-- 7. In-vehicle infotainment / IVI & HMI: zero for 2W, 3W
UPDATE technologies SET market_data = jsonb_set(
    jsonb_set(market_data, '{2W}', '0'), '{3W}', '0'
)
WHERE name ILIKE '%in-vehicle infotainment%' OR name ILIKE '%ivi%' OR name ILIKE '%ivi%hmi%';

-- 8. Smart Grid / V2G: zero for 2W, 3W, Tractor
UPDATE technologies SET market_data = jsonb_set(
    jsonb_set(jsonb_set(market_data, '{2W}', '0'), '{3W}', '0'), '{Tractor}', '0'
)
WHERE name ILIKE '%smart grid%' OR name ILIKE '%v2g%';

-- 9. Wireless inductive charging: zero for 2W, 3W, Tractor
UPDATE technologies SET market_data = jsonb_set(
    jsonb_set(jsonb_set(market_data, '{2W}', '0'), '{3W}', '0'), '{Tractor}', '0'
)
WHERE name ILIKE '%wireless induct%';

-- 10. Hydrogen / Fuel Cell: zero for 2W, 3W
UPDATE technologies SET market_data = jsonb_set(
    jsonb_set(market_data, '{2W}', '0'), '{3W}', '0'
)
WHERE name ILIKE '%hydrogen%' OR name ILIKE '%fuel cell%';

-- 11. Tractor: zero for all advanced automotive-only tech
UPDATE technologies SET market_data = jsonb_set(market_data, '{Tractor}', '0')
WHERE name ILIKE '%adas%' OR name ILIKE '%lidar%'
   OR name ILIKE '%surround view%' OR name ILIKE '%adaptive cruise%'
   OR name ILIKE '%lane keep%' OR name ILIKE '%blind spot%'
   OR name ILIKE '%traffic sign%' OR name ILIKE '%driver monitor%'
   OR name ILIKE '%parking assist%' OR name ILIKE '%infotainment%'
   OR name ILIKE '%v2x%' OR name ILIKE '%5g auto%'
   OR name ILIKE '%smart grid%' OR name ILIKE '%v2g%'
   OR name ILIKE '%dc fast charg%' OR name ILIKE '%battery swap%'
   OR name ILIKE '%wireless induct%' OR name ILIKE '%ev hub motor%'
   OR name ILIKE '%air disc%' OR name ILIKE '%vehicle os%'
   OR name ILIKE '%cybersecurity%' OR name ILIKE '%cloud platform%'
   OR name ILIKE '%cobots%' OR name ILIKE '%additive manuf%'
   OR name ILIKE '%hydrogen%' OR name ILIKE '%fuel cell%';

-- 12. Camera-based ADAS for 2W: zero (ABS/ESC kept, camera L2+ zeroed)
UPDATE technologies SET market_data = jsonb_set(market_data, '{2W}', '0')
WHERE (name ILIKE '%L2+%camera%' OR name ILIKE '%front radar%AEB%'
    OR name ILIKE '%integrated AEB%' OR name ILIKE '%lidar%')
  AND (market_data->>'2W') IS NOT NULL
  AND (market_data->>'2W')::numeric > 0;

-- ════════════════════════════════════════════════════════════
-- VERIFY: Show remaining non-zero entries per segment
-- ════════════════════════════════════════════════════════════
SELECT name,
    (market_data->>'4W_PV')::numeric as "4W_PV",
    (market_data->>'LCV')::numeric   as "LCV",
    (market_data->>'HCV')::numeric   as "HCV",
    (market_data->>'2W')::numeric    as "2W",
    (market_data->>'3W')::numeric    as "3W",
    (market_data->>'Tractor')::numeric as "Tractor"
FROM technologies
WHERE is_active = TRUE
ORDER BY name;
