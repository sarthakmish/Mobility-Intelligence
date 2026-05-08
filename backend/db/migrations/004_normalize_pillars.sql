-- 004: Normalize old pillar names to valid short IDs
-- Run once to fix API-stored factors that have verbose pillar names

DO $$
DECLARE
  r RECORD;
  new_pillars jsonb;
BEGIN
  FOR r IN SELECT id, affected_pillars FROM pestel_factors WHERE is_active = TRUE LOOP
    SELECT jsonb_agg(DISTINCT mapped) INTO new_pillars
    FROM (
      SELECT CASE elem
        WHEN 'Powertrain Solutions' THEN 'Motion'
        WHEN 'Chassis Systems' THEN 'Motion'
        WHEN 'Vehicle Motion' THEN 'Motion'
        WHEN 'Drivetrain' THEN 'Motion'
        WHEN 'EV Powertrain' THEN 'Energy'
        WHEN 'Energy & Charging' THEN 'Energy'
        WHEN 'Thermal Management' THEN 'Energy'
        WHEN 'Battery Systems' THEN 'Energy'
        WHEN 'Body Electronics' THEN 'Infotainment'
        WHEN 'Vehicle Diagnostics' THEN 'Infotainment'
        WHEN 'Infotainment & Connectivity' THEN 'Infotainment'
        WHEN 'Electronics' THEN 'Infotainment'
        WHEN 'Software & Services' THEN 'OS'
        WHEN 'Vehicle OS' THEN 'OS'
        WHEN 'Manufacturing & Industry 4.0' THEN 'Compute'
        WHEN 'Aftermarket & Retrofit' THEN 'Services'
        WHEN 'Aftermarket' THEN 'Services'
        WHEN 'Safety & Security' THEN 'ADAS'
        WHEN 'Autonomous Driving' THEN 'ADAS'
        WHEN 'Sensors & Actuators' THEN 'Actuators'
        WHEN 'Power Tools' THEN 'Actuators'
        ELSE elem
      END as mapped
      FROM jsonb_array_elements_text(r.affected_pillars) AS elem
    ) sub
    WHERE mapped IN (
      'ADAS','Motion','Energy','Body & Comfort','Infotainment',
      'OS','Compute','ECUs','Semiconductors','Actuators',
      'Solutions','Services','Cloud'
    );

    IF new_pillars IS NOT NULL AND new_pillars != r.affected_pillars THEN
      UPDATE pestel_factors SET affected_pillars = new_pillars WHERE id = r.id;
    END IF;
  END LOOP;
END $$;

SELECT 'Done' as status,
  COUNT(*) FILTER (WHERE affected_pillars::text ~ 'Powertrain Solutions') as old_names_remaining
FROM pestel_factors WHERE is_active = TRUE;
