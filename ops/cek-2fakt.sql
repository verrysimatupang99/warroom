WITH t AS (
  SELECT DISTINCT ON (kind, key) kind, key, observed_at, ttl_s, value_json
  FROM facts ORDER BY kind, key, observed_at DESC
)
SELECT kind, key, round(EXTRACT(EPOCH FROM (now()-observed_at))/60) AS menit, ttl_s/60 AS ttl
FROM t
WHERE (kind = 'gmgn' AND key = 'lp_mark') OR (kind = 'snapshot' AND key = 'state/snapshot.json');
