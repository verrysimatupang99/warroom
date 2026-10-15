WITH t AS (
  SELECT DISTINCT ON (kind, key) kind, key, observed_at, ttl_s
  FROM facts ORDER BY kind, key, observed_at DESC
)
SELECT kind || '/' || key || ' | basi dgn umur(mnt)=' || round(EXTRACT(EPOCH FROM (now()-observed_at))/60)
FROM t
WHERE (now()-observed_at) > make_interval(secs=>ttl_s);
SELECT 'SISA ALERT TERBUKA: ' || severity || ' | ' || left(subject,36) || ' | pulih=' || (ack_at IS NOT NULL)
FROM alerts WHERE ack_at IS NULL ORDER BY created_at;
