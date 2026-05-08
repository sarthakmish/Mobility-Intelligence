-- Migration 009: System Sanity Engine

-- Audit log: every sanity check writes here, severity-tagged
CREATE TABLE IF NOT EXISTS system_audit_logs (
    id              SERIAL PRIMARY KEY,
    run_id          VARCHAR(50) NOT NULL,        -- groups a single audit pass
    check_name      VARCHAR(100) NOT NULL,       -- e.g. "tech_segment_exclusion"
    severity        VARCHAR(20) NOT NULL,        -- "INFO" | "WARN" | "ERROR"
    entity_type     VARCHAR(50),                 -- "technology" | "pestel_factor"
    entity_code     VARCHAR(100),
    entity_segment  VARCHAR(20),
    message         TEXT NOT NULL,
    auto_fixed      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_run ON system_audit_logs(run_id);
CREATE INDEX IF NOT EXISTS idx_audit_severity ON system_audit_logs(severity, created_at DESC);

-- Tech-segment exclusion rules — backend is now the single source of truth
-- (replaces / shadows the frontend TECH_EXCLUSIONS dict)
CREATE TABLE IF NOT EXISTS tech_segment_exclusions (
    id              SERIAL PRIMARY KEY,
    tech_pattern    VARCHAR(200) NOT NULL,       -- substring match (case-insensitive)
    excluded_segment VARCHAR(20) NOT NULL,       -- "Tractor" | "2W" | etc.
    reason          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tech_pattern, excluded_segment)
);

-- Seed exclusion rules from automotive domain knowledge
INSERT INTO tech_segment_exclusions (tech_pattern, excluded_segment, reason) VALUES
    -- Tractor
    ('adas',                 'Tractor', 'ADAS not applicable to off-road agricultural'),
    ('camera system',        'Tractor', 'Cameras not standard on tractors'),
    ('lidar',                'Tractor', 'No LiDAR on tractors'),
    ('radar sensor',         'Tractor', 'No radar on tractors'),
    ('lane keep',            'Tractor', 'No lane-keep — off-road'),
    ('blind spot',           'Tractor', 'Off-road — irrelevant'),
    ('parking assist',       'Tractor', 'Off-road — irrelevant'),
    ('infotainment',         'Tractor', 'Tractors have minimal infotainment'),
    ('5g auto',              'Tractor', '5G connectivity rare in farm equipment'),
    ('48v mild hybrid',      'Tractor', '48V architecture not in tractor segment'),
    ('hydrogen',             'Tractor', 'Hydrogen-fuelled tractors negligible market'),
    ('fuel cell',            'Tractor', 'Fuel cell not in agri'),
    -- 2W
    ('common rail diesel',   '2W',      '2W are gasoline only'),
    ('gasoline direct injection', '2W', 'Port injection only on 2W'),
    ('lidar',                '2W',      'No LiDAR on 2W'),
    ('l3+',                  '2W',      'L3 autonomy not on 2W'),
    ('parking assist',       '2W',      'No parking assist on 2W'),
    ('adaptive cruise',      '2W',      'No ACC on 2W'),
    ('lane keep',            '2W',      'No LKAS on 2W'),
    ('blind spot',           '2W',      'No BSM on 2W'),
    ('air disc brake',       '2W',      'Disc brakes are different on 2W'),
    ('heavy-duty',           '2W',      'Heavy-duty parts not for 2W'),
    ('hydrogen',             '2W',      'Hydrogen 2W negligible'),
    ('fuel cell',            '2W',      'Fuel cell 2W negligible'),
    ('48v mild hybrid',      '2W',      '48V architecture not on 2W'),
    -- 3W
    ('common rail diesel',   '3W',      'Most 3W are CNG/electric or 2-stroke'),
    ('gasoline direct',      '3W',      'Port injection on 3W'),
    ('lidar',                '3W',      'No LiDAR on 3W'),
    ('l3+',                  '3W',      'No L3 on 3W'),
    ('parking assist',       '3W',      'No parking assist on 3W'),
    ('adaptive cruise',      '3W',      'No ACC on 3W'),
    ('air disc brake',       '3W',      'Drum brakes typical on 3W'),
    ('heavy-duty',           '3W',      'Light-duty class'),
    ('hydrogen',             '3W',      'Hydrogen 3W negligible'),
    ('fuel cell',            '3W',      'Fuel cell 3W negligible'),
    -- 4W_PV
    ('battery swapping',     '4W_PV',   'Battery swap mostly 2W/3W'),
    ('ev hub motor',         '4W_PV',   'Hub motors mostly 2W'),
    ('heavy-duty ev',        '4W_PV',   'Heavy-duty EV is HCV territory'),
    ('etruck',               '4W_PV',   'E-truck is HCV'),
    ('ebus',                 '4W_PV',   'E-bus is HCV'),
    -- LCV / HCV
    ('battery swapping',     'LCV',     'Battery swap mostly 2W/3W'),
    ('ev hub motor',         'LCV',     'Hub motors mostly 2W'),
    ('battery swapping',     'HCV',     'HCV uses fixed batteries'),
    ('ev hub motor',         'HCV',     'No hub motors on HCV')
ON CONFLICT DO NOTHING;

SELECT COUNT(*) AS exclusion_rules_loaded FROM tech_segment_exclusions;
