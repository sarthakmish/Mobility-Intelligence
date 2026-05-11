-- ============================================================
-- Migration 013: Fix ADAS technology market_data
-- ============================================================
-- Root cause: ADAS tech market_data stores some segments as plain
-- numbers ("LCV": 60) instead of nested objects ("LCV": {"fy25":200, "cagr":20.1}).
-- The API's JSON path query market_data->'LCV'->>'fy25' returns NULL on plain
-- numbers, so LCV / 2W / 3W / Tractor showed zero in View 4.
-- This migration normalises all 6 ADAS technologies to proper nested format
-- with correct fy25 values for every segment (sourced from JSX TECHS array
-- and Mordor Intelligence estimates).
-- ============================================================

-- AEB / Actuator — "Auto Emergency Braking" equivalent
UPDATE technologies SET market_data = '{
  "4W_PV": {"fy25": 1500, "cagr": 20.1, "fy30": 3727},
  "LCV":   {"fy25": 200,  "cagr": 20.1, "fy30":  497},
  "HCV":   {"fy25": 350,  "cagr": 20.1, "fy30":  870},
  "2W":    {"fy25": 50,   "cagr": 12.0, "fy30":   88},
  "3W":    {"fy25": 12,   "cagr": 10.0, "fy30":   19},
  "Tractor":{"fy25": 8,   "cagr":  8.0, "fy30":   12}
}'::jsonb
WHERE code = 'adas_aeb_actuator';

-- DMS — "Driver Monitoring System"
UPDATE technologies SET market_data = '{
  "4W_PV": {"fy25": 550,  "cagr": 28.4, "fy30": 1937},
  "LCV":   {"fy25": 45,   "cagr": 22.0, "fy30":  121},
  "HCV":   {"fy25": 180,  "cagr": 25.0, "fy30":  547},
  "2W":    {"fy25": 18,   "cagr": 15.0, "fy30":   36},
  "3W":    {"fy25": 5,    "cagr": 12.0, "fy30":    9},
  "Tractor":{"fy25": 3,   "cagr":  8.0, "fy30":    4}
}'::jsonb
WHERE code = 'adas_dms_driver_monitor';

-- L2 Camera — "Lane Keep Assist / Camera System"
UPDATE technologies SET market_data = '{
  "4W_PV": {"fy25": 950,  "cagr": 22.5, "fy30": 2626},
  "LCV":   {"fy25": 90,   "cagr": 18.0, "fy30":  205},
  "HCV":   {"fy25": 200,  "cagr": 20.0, "fy30":  498},
  "2W":    {"fy25": 25,   "cagr": 14.0, "fy30":   48},
  "3W":    {"fy25": 8,    "cagr": 10.0, "fy30":   13},
  "Tractor":{"fy25": 5,   "cagr":  7.0, "fy30":    7}
}'::jsonb
WHERE code = 'adas_l2_camera';

-- L3 LiDAR — primarily 4W_PV and HCV, nascent in others
UPDATE technologies SET market_data = '{
  "4W_PV": {"fy25": 340,  "cagr": 43.8, "fy30": 2100},
  "HCV":   {"fy25": 60,   "cagr": 35.0, "fy30":  281},
  "LCV":   {"fy25": 15,   "cagr": 30.0, "fy30":   56},
  "2W":    {"fy25": 3,    "cagr": 25.0, "fy30":    9},
  "3W":    {"fy25": 1,    "cagr": 20.0, "fy30":    2},
  "Tractor":{"fy25": 1,   "cagr": 15.0, "fy30":    2}
}'::jsonb
WHERE code = 'adas_l3_lidar';

-- Radar Front — "Adaptive Cruise Control / Front Radar"
UPDATE technologies SET market_data = '{
  "4W_PV": {"fy25": 1200, "cagr": 19.2, "fy30": 2879},
  "LCV":   {"fy25": 90,   "cagr": 17.0, "fy30":  200},
  "HCV":   {"fy25": 220,  "cagr": 20.0, "fy30":  548},
  "2W":    {"fy25": 25,   "cagr": 10.0, "fy30":   40},
  "3W":    {"fy25": 5,    "cagr":  8.0, "fy30":    7},
  "Tractor":{"fy25": 15,  "cagr":  9.0, "fy30":   23}
}'::jsonb
WHERE code = 'adas_radar_front';

-- V2X — primarily 4W_PV and HCV, negligible in 2W/3W/Tractor
UPDATE technologies SET market_data = '{
  "4W_PV": {"fy25": 180,  "cagr": 43.7, "fy30": 1100},
  "HCV":   {"fy25": 40,   "cagr": 35.0, "fy30":  187},
  "LCV":   {"fy25": 20,   "cagr": 28.0, "fy30":   68},
  "2W":    {"fy25": 5,    "cagr": 22.0, "fy30":   14},
  "3W":    {"fy25": 2,    "cagr": 18.0, "fy30":    5},
  "Tractor":{"fy25": 1,   "cagr": 12.0, "fy30":    2}
}'::jsonb
WHERE code = 'adas_v2x_communication';
