-- Audit alert & fakta (15 Okt) — header-only, tanpa payload sensitif
\echo === alert duplikat terbuka
SELECT COALESCE(kind,'-') kind, left(COALESCE(judul,'-'),34) judul, status, count(*) n
FROM alerts WHERE acknowledged_at IS NULL
GROUP BY 1,2,3 HAVING count(*)>1 ORDER BY n DESC, judul LIMIT 12;
\echo === total per status
SELECT status, count(*) FROM alerts GROUP BY 1 ORDER BY 2 DESC;
\echo === fakta basi detail (kind/key/umur_jam/ttl_h)
SELECT kind, key, round(EXTRACT(EPOCH FROM (now()-observed_at))/3600,1) umur_j, round(ttl_s/3600.0,1) ttl_h
FROM facts WHERE EXISTS (
  SELECT 1 FROM facts f2 WHERE f2.kind=facts.kind AND f2.key=facts.key
    AND f2.observed_at=facts.observed_at AND (now()-facts.observed_at) > make_interval(secs=>facts.ttl_s)
) ORDER BY umur_j DESC LIMIT 12;
