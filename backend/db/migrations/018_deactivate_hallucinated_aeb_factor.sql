-- Migration 018: Deactivate hallucinated AEB-for-4W-PV PESTEL factor
-- ---------------------------------------------------------------------------
-- Root cause: LLM compressed two stories into one false claim:
--   "AEBS for buses Apr 2026" + "ADAS becoming standard in PV"
--   → hallucinated "AEB mandatory for 4W PV new models April 2026"
--
-- Reality: AEBS/DDAWS/LDWS mandate (MoRTH Mar 2025 draft) applies ONLY to
-- M2/M3 (buses >8 pax) and N2/N3 (heavy trucks) categories.
-- For M1 (passenger cars), ADAS adoption is Bharat NCAP 2.0-driven
-- (voluntary, Oct 2027 launch) — not yet legally mandated.
--
-- The legitimate AEBS factor (hcv_safety_norms_aebs) already covers
-- the real mandate with 4W_PV = 'L', HCV = 'H' — correct.
-- ---------------------------------------------------------------------------

UPDATE pestel_factors
SET is_active = FALSE,
    last_refreshed = NOW()
WHERE name ILIKE '%AEB mandatory for 4W PV%'
   OR name ILIKE '%AEB mandatory for 4W%';
