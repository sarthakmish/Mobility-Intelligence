-- Find PESTEL factors with missing segment_relevance keys
SELECT code, name, category, segment_relevance
FROM pestel_factors
WHERE NOT (
  segment_relevance ? '4W_PV' AND segment_relevance ? '2W' AND
  segment_relevance ? '3W' AND segment_relevance ? 'LCV' AND
  segment_relevance ? 'HCV' AND segment_relevance ? 'Tractor'
)
ORDER BY category, code;
