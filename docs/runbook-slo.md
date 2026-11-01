# Runbook SLO — metrik dan alert

Dibuat 1 Nov 2026. Ambang disetujui owner: availability, p95, error 5xx, disk,
umur backup, dan umur drill.

## Metrik yang diekspos

`GET /metrics` (localhost; nginx tidak mem-proxy) memuat:

| Metrik | Arti |
|---|---|
| `warroom_http_requests_total` | Request `/api/` yang diukur sejak proses hidup |
| `warroom_http_errors_total` | Request `/api/` dengan status >= 500 |
| `warroom_http_error_rate` | Rasio 5xx terhadap total |
| `warroom_http_latency_p95_ms` | p95 latensi `/api/` dari 2.000 request terakhir |
| `warroom_facts_basi` | Fakta terbaru yang melewati TTL |
| `warroom_readiness` | Status dependency |

Sifat pengukuran:

- Di memori proses; restart API mengosongkan jendela. Ini disengaja: tidak ada angka
  historis yang dikarang.
- Hanya path `/api/` yang dihitung. `/metrics`, halaman web, dan SSE tidak masuk p95.
- Endpoint LLM (`/api/v1/ai/*`) ikut terukur dan boleh menaikkan p95 karena latency
  model. Jika itu mengganggu, kecualikan path tersebut dengan keputusan owner.

## Ambang dan aksi

| Sinyal | Ambang | Aksi |
|---|---|---|
| p95 API | > 1.000 ms, minimal 20 request | alert `slo/latency` |
| Error 5xx | > 1%, minimal 20 request | alert `slo/error_rate` |
| Disk | warn 80%, crit 90% | alert `slo/disk` |
| Umur backup | > 26 jam | alert `slo/backup` |
| Umur drill restore | > 35 hari | alert `slo/drill` |
| Probe `/api/v1/build` | gagal | alert `slo/api` |

Job `slo-check` berjalan tiap 60 detik, menerbitkan fakta `slo/ringkas` (TTL 180 s),
dan menutup alert otomatis saat kondisi pulih.

## Verifikasi

```bash
curl -s http://127.0.0.1:8800/metrics | grep -E 'warroom_http_(requests_total|errors_total|latency_p95_ms|error_rate)'
curl -s -b <cookie> http://127.0.0.1:8800/api/v1/cron/jobs/slo-check
curl -s -b <cookie> http://127.0.0.1:8800/api/v1/facts/slo/ringkas
bash ops/verify-final.sh
```

`ops/verify-final.sh` memeriksa tes tiga paket, metrik HTTP, readiness, job, alert,
umur backup, dan bukti drill. Keluar 0 hanya bila semuanya PASS.

## Batas

- Ambang ini tidak mengubah gate live atau keputusan trading.
- Alert hanya memberi tahu; tidak ada aksi otomatis ke broker atau VM.
