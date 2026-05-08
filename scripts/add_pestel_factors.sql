INSERT INTO pestel_factors (
  code, name, category, selection_reasoning,
  likelihood, likelihood_reasoning,
  impact, impact_reasoning,
  trend, time_horizon,
  segment_relevance, affected_pillars,
  is_active, last_refreshed
)
VALUES
(
  'cafe_iii_2027',
  'CAFE III norms (FY2027): 91 g CO2/km fleet average',
  'L',
  'India CAFE Phase III mandates 91 g CO2/km fleet average for PVs from FY2027, down from 130 g Phase I. OEMs must electrify or hybridize >=20% of volumes. Non-compliance penalty: Rs.25,000/km excess per vehicle. Hyundai, Maruti, Tata Motors most exposed.',
  8.0, 'CAFE Phase III is gazetted law effective April 2027; auto industry compliance tracking is well-documented.',
  8.0, 'Forces significant BOM changes including 48V mild hybrid, BEV integration; affects entire PV fleet.',
  'escalating', 'medium',
  '{"4W_PV":"H","LCV":"M","HCV":"L","2W":"L","3W":"L","Tractor":"L"}',
  '["Energy","ADAS","Motion"]',
  TRUE, NOW()
),
(
  'gati_shakti_infra',
  'PM Gati Shakti: Rs.11.1L Cr infra investment accelerating LCV/HCV demand',
  'E',
  'PM Gati Shakti targets 100 logistics parks, dedicated freight corridors, 25,000 km highway construction by 2027. Drives LCV demand +18% CAGR, HCV +12% CAGR. AEBS and telematics mandates scale with fleet growth.',
  7.0, 'Gati Shakti is an active government programme with annual budget allocations and Q3 FY26 progress report.',
  8.0, 'Infra spend directly expands addressable market for commercial vehicle technology suppliers.',
  'stable', 'short',
  '{"4W_PV":"L","LCV":"H","HCV":"H","2W":"L","3W":"M","Tractor":"L"}',
  '["Motion","ADAS","Body & Comfort"]',
  TRUE, NOW()
),
(
  'trem_v_2025',
  'TREM V emission norms mandatory from Oct 2025 for tractors >50 HP',
  'L',
  'Tractor TREM V effective October 2025 for tractors >50 HP. Requires diesel oxidation catalyst, DPF, and SCR aftertreatment. BOM increase Rs.80k-1.2L per tractor. M&M, TAFE, Sonalika, John Deere all affected. Aligns with BS-VI philosophy for off-road segment.',
  9.0, 'TREM V is gazetted regulation; October 2025 deadline is firm per MoRTH circular.',
  7.0, 'Mandates DOC/DPF/SCR adoption across >50 HP tractors; large aftertreatment component market creation.',
  'stable', 'short',
  '{"4W_PV":"L","LCV":"L","HCV":"L","2W":"L","3W":"L","Tractor":"H"}',
  '["Energy","Motion"]',
  TRUE, NOW()
)
ON CONFLICT (code) DO UPDATE SET
  selection_reasoning = EXCLUDED.selection_reasoning,
  likelihood = EXCLUDED.likelihood,
  impact = EXCLUDED.impact,
  segment_relevance = EXCLUDED.segment_relevance,
  affected_pillars = EXCLUDED.affected_pillars,
  last_refreshed = NOW();

