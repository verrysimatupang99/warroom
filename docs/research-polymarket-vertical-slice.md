# Polymarket vertical slice — registration and data gate

Tanggal: 2026-10-08 UTC
Status: `draft`, belum replay-ready, belum promotion-ready.

## Hipotesis terdaftar

```text
ID: polymarket-favorite-070-095-v1
Market: Polymarket
Instrument: favorite 5m, Arm B
Entry: buy favorite outcome hanya pada band 0.70–0.95 setelah executable ask check
Exit: settlement atau pre-resolution exit yang harus dibekukan sebelum replay
Risk: fixed paper risk, capped by liquidity
Baseline: market-implied probability + no-trade
Invalidation: net EV tidak mengalahkan baseline pada frozen holdout
Mode: paper
```

Contract fingerprints:

```text
hypothesis: 6e3893980b79444c49947c3f2fdb0be3ce74c36548451177a5f17b9a118ac3ce
execution: 003e1b6bbd4b5b66d00fe625e780fc4cb8d2cdba40dc3da42e3581e8e4afefe4
```

Registration artifact:

```text
/tmp/warroom-materi/polymarket-vertical-slice-registration.json
```

## Data inventory yang dapat diverifikasi melalui allowlist read-only

```text
/var/lib/poly-research/paired
files: 2477
bytes: 6217878894

/var/lib/poly-research/dataset
files: 6
bytes: 95042876

/var/lib/poly-research/orderflow-confirm
files: 4
bytes: 22442
```

Verdict tool yang tersedia mengembalikan raw operational summary:

```text
n: 4133
wins: 3234
verdict: EDGE
```

Label `EDGE` itu **tidak diterima sebagai verdict research** karena tool tersebut belum membuktikan frozen split dan independent holdout untuk vertical slice ini.

## Blocker replay

Agent hanya memiliki allowlist untuk:

- menjalankan verdict script;
- menghitung jumlah/ukuran dataset;
- membaca summary/tail tertentu.

Agent belum memiliki akses read-only yang sah untuk membaca isi dataset paired/dataset/orderflow secara utuh. Saya tidak akan memperluas sudoers atau mengubah `/opt/polymarket` secara otomatis.

## Next gate

Sediakan salah satu jalur aman:

1. export read-only dataset terpilih ke staging War Room dengan manifest/hash; atau
2. allowlist command agregator yang hanya mengeluarkan schema, timestamp range, row count, dan fields; atau
3. grant read-only khusus ke dataset staging, tanpa akses write/restart/live.

Sebelum itu, status tetap:

```text
registered: yes
replay: blocked_data_access
baseline: specified
cost model: specified, not executed
promotion: blocked
live: NO-GO
```
