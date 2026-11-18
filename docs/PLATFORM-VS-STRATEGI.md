# Platform vs Strategi — peta batas

Ditetapkan 2026-11-18. Dokumen ini menjawab satu pertanyaan: **"kalau ada yang
rusak, ini salah platform atau salah strategi?"**

Sebelumnya tidak bisa dijawab. Strategi forex hanya hidup sebagai baris tabel
`v1.strategy` + berkas EA berserakan di prefix Wine; strategi crypto sebagai
empat YAML di folder yang sama dengan kode platform.

---

## 1. Garis batas

```
┌──────────────────────────────── PLATFORM ────────────────────────────────┐
│  apps/web            UI SvelteKit (:3100)                                │
│  services/api        API lama (:8800)                                    │
│  v1/api              API v1 read-only (:8830)                            │
│  services/worker     job periodik (publish-facts, freshness, …)           │
│  services/notifier   alert Telegram                                       │
│  services/llm        (nonaktif sejak 3 Nov)                               │
│  bus                 papan diskusi agent (:8820)                          │
│  DB  v1.venue  v1.instrument  v1.feed  v1.strategy  v1.signal  v1.position│
└───────────────────────────────┬──────────────────────────────────────────┘
                                │  hanya lewat kontrak data
                    ┌───────────┴────────────┐
                    │  v1.strategy (registry) │  ← diisi ops/strategi-sync.py
                    │  v1.feed    (freshness) │  ← diisi status JSON EA
                    └───────────┬────────────┘
┌───────────────────────────────┴──────────────────────────────────────────┐
│                                STRATEGI                                   │
│  strategi/forex/<id>/        manifest.yaml + ea/ + preset/ (EA MT5)      │
│  strategi/crypto/<id>/       manifest.yaml (mesin Python)                │
│  strategi/openmarket/<id>/   manifest.yaml (mesin Python)                │
│  strategi/prediction/        (kosong — belum ada strategi)               │
│  strategi/equity/            (kosong — belum ada strategi)               │
└───────────────────────────────────────────────────────────────────────────┘
```

**Aturan tunggal:** platform tidak mengimpor apa pun dari `strategi/`, dan
`strategi/` tidak mengimpor apa pun dari `services/` atau `v1/api/`.
Keduanya hanya bertemu di tabel `v1.*`.

Dijaga oleh `tests/test_platform_strategy_boundary.py` (11 test).

---

## 2. Siapa memiliki apa

| Hal | Pemilik | Boleh diubah oleh |
| --- | --- | --- |
| UI, route, endpoint API | platform | pekerja platform |
| Skema & migrasi `v1.*` | platform | perubahan skema + review |
| Isi `v1.venue` / `v1.instrument` / `v1.feed` | platform (ingest) | collector, bukan strategi |
| Rumus entry/exit, SL/TP, risiko | **strategi** (`manifest.yaml`) | pemilik strategi |
| Kode EA (`.mq5`, `.mqh`) | **strategi** (`strategi/forex/<id>/ea/`) | pemilik strategi |
| Preset EA (`.set`) | **strategi** (`preset/`) | pemilik strategi |
| `manifest_json` di `v1.strategy` | diturunkan dari manifest | `ops/strategi-sync.py` (jangan edit manual) |
| Status JSON `*_status.json` | **strategi** (ditulis EA) | EA, bukan platform |

---

## 3. Kontrak antara keduanya

### 3.1 Manifest → registry

```
strategi/<market>/<id>/manifest.yaml
        │
        └── ops/strategi-sync.py --apply ──> v1.strategy
                (code, name, market, version, repo_ref, manifest_json, status)
```

`manifest.yaml` adalah satu-satunya sumber kebenaran. `v1.strategy` hanya cermin;
kalau berbeda, manifest yang benar.

### 3.2 EA → telemetri platform

```
EA (di terminal MT5, via Wine)
   └── menulis  Common/Files/<nama>_status.json      (lihat _schema/status.schema.json)
          └── v1.ingest  ──>  v1.feed.status = ok, last_ok_at
                            └──  v1.signal / v1.position
```

Platform **tidak** membaca interna EA. Kalau EA berhenti menulis, `v1.feed`
menjadi basi (`now() - last_ok_at > sla_seconds`) — itu satu-satunya cara
platform tahu ada masalah. Tidak ada polling ke dalam proses EA.

### 3.3 Strategi Python → sinyal

```
ops/paper-bot.py --config strategi/<...>/manifest.yaml
   └── warroom_core.strategi_config.muat_config()
          └── sinyal ──> v1.signal
```

---

## 4. Diagnosa cepat: platform atau strategi?

| Gejala | Kandidat penyebab | Cara memastikan |
| --- | --- | --- |
| `v1.feed` basi, UI lain normal | **strategi** (EA mati/tidak menulis) | `ops/mt5-inventory.py`, cek `last_ok_at` per feed |
| UI/API 500, feed segar | **platform** | `systemctl status warroom-web warroom-api`, log unit |
| Angka strategi tidak muncul di UI | manifest belum di-apply | `ops/strategi-sync.py --check` |
| Dua sumber angka berbeda untuk strategi sama | drift EA | `ops/mt5-inventory.py` (bagian DRIFT) |
| `mt5-ex-*` gagal start setelah reboot | launcher `/tmp` hilang | lihat `strategi/forex/mtrb_pro/arsip/drift-20261118.md` §4 |

---

## 5. Perintah verifikasi

```bash
# batas platform/strategi tidak bocor (harus hijau)
./.venv/bin/python -m pytest tests/test_platform_strategy_boundary.py -q

# registry sinkron dengan manifest (semua baris harus "=")
sudo sh -c 'set -a; . /etc/warroom/strategi-sync.env; set +a; \
  cd /home/admin/warroom && ./.venv/bin/python ops/strategi-sync.py --check'

# terminal MT5 + drift EA
cd /home/admin/warroom && ./.venv/bin/python ops/mt5-inventory.py

# deploy EA (dry-run dulu, selalu)
cd /home/admin/warroom && ./.venv/bin/python ops/ea-deploy.py
```

---

## 6. Batas yang belum ditegakkan otomatis

Jujur soal yang belum ada:

1. **Import arah sebaliknya** — `strategi/` mengimpor platform belum dicek test.
   Saat ini tidak terjadi, tapi belum dijaga.
2. **Skema manifest** belum divalidasi dengan JSON Schema saat runtime; test
   memeriksa kunci wajib + enum saja (tanpa dependensi `jsonschema`).
3. **Kesegaran status per strategi** belum dipetakan ke satu baris `v1.strategy`;
   freshness masih per feed (`v1.feed`), bukan per strategi.
4. **`v1.instrument` belum lengkap untuk crypto** — simbol manifest
   (`BTCUSDT`) belum ada padanannya di `v1.instrument` okx (yang memakai
   `BTC-USDT`). `strategi-sync.py` melaporkannya sebagai peringatan, bukan galat.
