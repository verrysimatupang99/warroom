# `strategi/` — unit mandiri, terpisah dari platform

Folder ini memuat **strategi saja**. Platform (web, API, bus, worker, ledger,
telemetri) ada di `apps/` + `services/` + `v1/` dan **tidak boleh** mengimpor isi
folder ini. Batas itu dijaga oleh `tests/test_platform_strategy_boundary.py`.

## Kenapa dipisah

Sebelum 2026-11-18 strategi forex tidak punya wujud berkas: hanya baris di tabel
`v1.strategy` dan berkas EA yang berserakan di prefix Wine. Akibatnya tidak ada
cara menjawab "strategi apa yang jalan, versi berapa, dari mana sumbernya" tanpa
membaca DB dan menebak.

Sekarang: **satu berkas manifest = satu strategi**, dan berkas itu satu-satunya
sumber kebenaran. DB hanya cermin yang disinkronkan.

## Susunan

```
strategi/
  _schema/strategy.schema.json    kontrak manifest
  _schema/status.schema.json      kontrak status JSON yang ditulis EA → platform
  forex/
    gold_reaper_hexa/manifest.yaml
    mtrb_pro/manifest.yaml
  crypto/
    breakout_donchian_crypto/manifest.yaml
    rsi_meanrevert_crypto/manifest.yaml
    memecoin_momentum/manifest.yaml
  openmarket/
    openmarket_breakout/manifest.yaml
  prediction/                     (belum ada strategi)
  equity/                         (belum ada strategi)
  *.yaml                          symlink nama lama → manifest (kompatibilitas CLI)
```

## Dua jenis executor

| `executor` | Dijalankan oleh | Wajib punya |
| --- | --- | --- |
| `python-engine` | `warroom_core.strategi_config` (dipanggil `ops/paper-bot.py`, `ops/screener-strategy.py`, `ops/backtest-strategy.py`) | `simbol`, `waktu`, `variabel`, `entry_*`, `exit`, `risiko` |
| `mt5-ea` | EA di terminal MT5 (via Wine) | blok `ea` (`file`, `terminal`, `magic`, `tf`) |

Manifest `python-engine` dibaca langsung oleh `muat_config()` — kunci registry
(`id`, `nama`, `market`, `executor`, …) diabaikan oleh loader karena ia hanya
membaca kunci yang dikenalnya.

## Alur data (kontrak antar dua dunia)

```
manifest.yaml ──(ops/strategi-sync.py)──> v1.strategy
       │
       └──(mt5-ea)──> EA menulis Common/Files/<x>_status.json
                              │
                              └──> platform baca → v1.feed (freshness) → v1.signal
```

Platform hanya melihat `v1.*`. Ia tidak tahu isi EA, tidak mengimpor kode
strategi, dan tidak mengubah manifest.

## Perintah

```bash
python3 ops/strategi-sync.py --check     # bandingkan manifest vs DB (tidak menulis)
python3 ops/strategi-sync.py --apply     # UPSERT v1.strategy dari manifest
python3 ops/mt5-inventory.py             # inventaris terminal MT5 + drift EA
python3 ops/ea-deploy.py --dry-run       # rencana deploy EA (default dry-run)
```

## Aturan

1. Menambah strategi = menambah satu folder + `manifest.yaml`. Bukan mengedit Python.
2. Mengubah perilaku trading = mengubah manifest, lalu `--apply` + review diff.
3. Nama lama (`strategi/<id>.yaml`) tetap ada sebagai symlink; jangan dijadikan
   tempat edit — edit manifest-nya.
4. Strategi `live` (uang nyata) tidak di-deploy/diubah saat pasar buka.
