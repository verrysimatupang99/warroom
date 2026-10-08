# Polymarket Arm B — audit/replay gate

Tanggal pemeriksaan: 2026-10-08 UTC  
Scope: `polymarket-favorite-070-095-v1`, favorit 0,70–0,95, paper/research only.

## Kesimpulan

Status tetap **`blocked_data_access`** untuk frozen replay yang defensible. Tidak ada profit claim, promosi, live order, restart, atau perubahan production.

Data yang boleh dibaca memberikan ringkasan dan tail, tetapi belum memberikan artefak lengkap untuk membuktikan satu replay beku dengan baseline dan all-in cost yang dapat diaudit per trade.

## Bukti read-only yang berhasil

Perintah yang berhasil melalui allowlist:

```text
sudo -n cat /var/lib/poly-research/dataset/summary.json
sudo -n cat /var/lib/poly-research/dataset/favorite-replay-summary.json
sudo -n cat /var/lib/poly-research/dataset/quote-lag-summary.json
sudo -n cat /var/lib/poly-research/orderflow-confirm/agreement.json
sudo -n cat /var/lib/poly-research/orderflow-confirm/imbalance.json
sudo -n tail -n 3 /var/lib/poly-research/dataset/favorite-replay-entries.jsonl
sudo -n tail -n 3 /var/lib/poly-research/dataset/decisions.jsonl
sudo -n tail -n 3 /var/lib/poly-research/dataset/replay-entries.jsonl
sudo -n python3 /opt/polymarket/current/qa/favorite-live-verdict.py --json
```

Observed, tanpa menganggapnya sebagai hasil baru yang tervalidasi:

- Inventory yang terdokumentasi: `paired` 2.477 files / 6.217.878.894 bytes; `dataset` 6 files / 95.042.876 bytes; `orderflow-confirm` 4 files / 22.442 bytes.
- `favorite-replay-summary.json`: band `[0.7, 0.95]`, `windows=304`, `cumulativeEntries=24418`, `decisionRowsWithBothQuotes=15265`, skip `noLabel=28`, `noBandQuote=93`.
- Summary favorit melaporkan `first n=5069`, `late n=5069`, dan cohort delay 0/20/30/39/45/60 detik. Ini adalah ringkasan sumber, bukan hasil replay yang dapat diaudit ulang dari export penuh.
- Tail `favorite-replay-entries.jsonl` hanya menunjukkan: `key`, `mode`, `coin`, `secs`, `side`, `price`, `stake`, `pnl`, `won`. Tidak terlihat `partition`, `fee`, `slippage`, `depth`, atau quote timestamp pada record tersebut.
- Tail `decisions.jsonl` menunjukkan adanya `partition="holdout"` dan field quote/depth/fee, tetapi contoh yang terbaca semuanya `reason="outside_price_band"` dengan quote fields null. Ini tidak cukup untuk menghubungkan seluruh entry favorit ke split, quote yang dipakai, dan biaya.
- `favorite-live-verdict.py --json` mengembalikan `n=4133`, `wins=3234`, `ask=0.7666`, `breakEven=76.66`, `evPerStake=2.07`, `ci95=[76.75,79.67]`, `deff=1.342`, `verdict=EDGE`, `nNeeded=7392`. Label `EDGE` tidak diterima sebagai verdict research karena output ini tidak membuktikan split beku/holdout independen maupun all-in cost per entry.
- Dua ringkasan orderflow yang terbaca sama-sama `verdict="BELUM"` karena `ciOk=false`; tidak dipakai untuk mengubah scope Arm B.

Direct enumeration tanpa sudo menghasilkan `Permission denied` pada `/var/lib/poly-research`; akses yang dipakai sesudahnya hanya perintah allowlist read-only di atas.

## Mengapa replay belum boleh dijalankan

Missing atau belum terverifikasi untuk **setiap accepted entry** Arm B:

1. **Frozen manifest**: daftar run/file, cutoff/freeze epoch, row count, dan hash yang mengikat dataset ke replay.
2. **Split membership**: `train/validation/holdout` atau ID split pada entry favorit; summary hanya menyebut runs/windows, sedangkan tail entry favorit tidak memiliki `partition`.
3. **Market identity/resolution**: market/condition/token identifier dan outcome resolution yang mengikat `won` ke kontrak market tertentu.
4. **Event timing**: timestamp quote/decision/entry/settlement yang eksplisit dan timezone; `key` epoch + `secs` pada tail belum cukup untuk seluruh lifecycle.
5. **Executable quote evidence**: ask, available depth, selected side/token, quote age, dan fill assumption pada saat entry.
6. **All-in cost**: fee rate/amount, spread/slippage rule, size cap/liquidity cap, dan apakah `stake`/`pnl` sudah net atau gross. `quoteFee` ada di schema decision yang terlihat, tetapi tidak ada pada tail accepted favorite entries dan tidak ada bukti seluruh 24.418 entry tercakup.
7. **Baseline inputs**: counterfactual no-trade dan market-implied baseline pada row yang sama, dengan aturan settlement/exit identik.
8. **Deduplication/provenance**: deterministic entry ID, duplicate policy, parser/schema version, dan source file membership.

Tanpa item tersebut, menghitung ulang ROI dari summary atau tail akan mencampur angka precomputed dengan asumsi dan tidak memenuhi standar evidence-lock. Tidak ada angka profit yang diklaim.

## Minimal sanctioned next-step artifact

Owner/operator cukup menyediakan **satu export agregator read-only** ke staging War Room (bukan raw dump dan bukan akses write) dengan dua keluaran:

### A. `manifest.json`

Wajib memuat:

```json
{
  "dataset_id": "...",
  "schema_version": "...",
  "generated_at": "...",
  "freeze_epoch": 0,
  "source_roots": ["..."],
  "files": [{"path": "...", "rows": 0, "bytes": 0, "sha256": "..."}],
  "splits": {"train": ["..."], "validation": ["..."], "holdout": ["..."]}
}
```

### B. `arm_b_entries.jsonl` (satu baris per accepted entry)

Wajib memuat field berikut, dengan `null` eksplisit bila memang tidak tersedia:

```text
entry_id, market_id, condition_id, token_id, coin, window_id,
partition, decision_ts, quote_ts, entry_ts, settlement_ts,
side, outcome, resolved, won, ask, depth, size_usd,
fee_rate, fee_usd, slippage_bps, gross_pnl_usd, net_pnl_usd,
baseline_pnl_usd, source_file, source_row, parser_version
```

Aggregator harus sekaligus mencetak ke stdout (tanpa raw payload/secret): total rows, unique entry IDs, duplicate count, min/max timestamp, counts per partition, counts missing per required field, total gross/net/baseline PnL, dan cost components. Export harus ditulis ke staging War Room dengan mode read-only setelah dibuat; tidak perlu dan tidak boleh menyentuh `/opt/polymarket`, service execution, activation gate, atau credentials.

## Gate setelah export

1. Validasi manifest/hash dan schema.
2. Bekukan split dan cutoff; fail closed bila missing required fields atau duplicate policy tidak deterministik.
3. Jalankan replay Arm B pada holdout saja dengan baseline no-trade/market-implied dan all-in fee/slippage.
4. Laporkan denominator, coverage, missingness, gross vs net, baseline delta, CI, dan provenance.
5. Tetap **paper-only**; hasil positif tidak mengizinkan live trading.
