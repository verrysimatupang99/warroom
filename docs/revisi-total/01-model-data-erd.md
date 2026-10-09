# 01 — Model Data (ERD) War Room

Disusun: 2026-10-09 · Status: **DRAF** · Sumber: `packages/core/src/warroom_core/db/models.py`

> **Metode:** Semua yang di bawah dibaca langsung dari kode lewat `grep __tablename__`,
> bukan dari ingatan. Total **21 tabel** (terverifikasi). Kalau ada nama kolom yang
> saya sebut tanpa yakin, saya tandai `[verifikasi-baris-kode]`.

---

## 1. Prinsip model data (dari ADR yang terkunci)

Empat aturan ini **bukan selera saya** — semuanya sudah jadi keputusan terkunci:

1. **Tidak ada angka di UI/AI tanpa baris `facts`.** (ADR-005, komentar di `models.py:6`)
2. **`events` append-only**, tiap event menautkan `fact_ids` sebagai bukti. (ADR-005)
3. **Paper vs live dibedakan di level skema**, bukan di kode tampilan. (SDLC §2)
4. **Parameter berversi** dengan `locked`/`bounds`; hanya owner yang mengubah. (SDLC §2)

**Konsekuensi:** model data ini adalah **benteng keselamatan**, bukan sekadar penyimpanan.
Kalau tabelnya salah, janji keselamatan produk ikut hilang.

---

## 2. Peta 21 tabel, dikelompokkan berdasarkan **kursi** (peran)

Pengelompokan ini beririsan dengan 5 kursi tim di dok 00 — supaya jelas siapa yang
"memiliki" tabel mana.

### Kelompok A — Kebenaran angka (Kursi: Quant + Backend)

| Tabel | Apa yang disimpan | Kolom kunci |
|---|---|---|
| `facts` | Satu fakta terukur, berversi. **Sumber semua angka.** | `kind`, `key`, `observed_at` |
| `events` | Log append-only tindakan/kejadian | `kind`, `fact_ids` (JSONB) |
| `verdicts` | Penilaian per pasar/per strategi | `subject`, `rule`, `policy_version` |
| `strategies` | Definisi strategi per pasar | — |
| `trades` | Trade paper **dan** live (dibedakan) | status paper/live |

> **Celah terverifikasi:** `verdicts` punya `UniqueConstraint("subject","rule","policy_version","created_at")`
> — artinya verdict **tidak pernah ditimpa**, selalu baris baru. Bagus untuk audit.
> Tapi lihat §4 [celah-3]: tidak ada tautan ke **siapa** yang memutuskan.

### Kelompok B — Kendali & tata kelola (Kursi: Owner + Quant)

| Tabel | Apa yang disimpan |
|---|---|
| `parameters` | Parameter sistem berversi (`locked`, `bounds`) |
| `proposals` | Usulan perubahan parameter (belum berlaku sampai disetujui) |
| `grants` | Izin aksi live — **dikunci** |
| `audit` | Jejak tindakan istimewa |
| `users` | Akun: `viewer` / `operator` / `owner` |
| `sessions` | Sesi login (dasar auth web & E2E) |

> **Catatan penting:** `users.role` default `"viewer"` — jadi **tidak ada yang jadi
> `owner` secara tak sengaja**. Ini desain yang benar.
> `grants` = tabel yang menjaga janji "live tidak pernah dinyalakan agen".

### Kelompok C — AI & biaya (Kursi: Backend)

| Tabel | Apa yang disimpan |
|---|---|
| `prompts` | Prompt berversi (`UniqueConstraint("role","version")`) |
| `llm_calls` | Audit tiap panggilan LLM: biaya, fallback, `prompt_version` |

> **Kenapa penting:** ADR-004 bilang "setiap panggilan tercatat". Tabel ini **bukti**
> janji itu ditepati. Tanpa ini, "AI dipakai maksimal" = biaya tak terkendali.

### Kelompok D — Riset & anti-overfit (Kursi: QA + Quant)

| Tabel | Apa yang disimpan |
|---|---|
| `datasets` | Dataset yang dikelola |
| `research_runs` | Satu run riset/backtest |
| `research_records` | Hasil per run |
| `frozen_splits` | Split data **dibekukan sebelum melihat hasil** |

> **Ini kursi QA dalam bentuk tabel.** `frozen_splits` adalah cara sistem mencegah
> diri sendiri dari *overfitting* — aturan "split dibekukan sebelum lihat hasil"
> (ADR-003) jadi mustahil dilanggar tanpa jejak.

### Kelompok E — Operasional (Kursi: SRE)

| Tabel | Apa yang disimpan |
|---|---|
| `services` | Layanan yang dipantau: `host`, `unit`, `status`, `detail_json` |
| `heartbeats` | Denyut per layanan: `host`, `unit`, `beat_at` |
| `alerts` | Peringatan + status ack |
| `jobs` | Penjadwalan deklaratif worker ("tidak ada cron tersembunyi") |

---

## 3. Diagram relasi (versi akurat, 21 tabel)

```
KELOMPOK A — KEBENARAN ANGKA
   strategies ──1..n──► verdicts ◄──parameters (locked/bounds)
                          │
                     fact_ids (bukti)
                          ▼
        facts ◄───── events ─────► trades (paper│live)
          ▲
    ditautkan oleh semua angka

KELOMPOK B — KENDALI & TATA KELOLA
   proposals ──diusulkan ke──► parameters
   grants (izin live, dikunci)
   audit ◄── users ──► sessions

KELOMPOK C — AI & BIAYA
   prompts ──1..n──► llm_calls

KELOMPOK D — RISET & ANTI-OVERFIT
   datasets ──► research_runs ──► research_records
   frozen_splits (membekukan dataset sebelum hasil dilihat)

KELOMPOK E — OPERASIONAL
   services ──1..n──► heartbeats
   alerts · jobs
```

**Relasi antar-kelompok yang mengikat keselamatan:**
- Setiap `verdicts` → menautkan `facts` (tidak ada verdict tanpa bukti).
- Setiap `events` → menautkan `fact_ids` (bisa ditelusuri).
- `proposals` → `parameters` (perubahan parameter selalu lewat usulan).
- `grants` → aksi live (tanpa grant, live tidak jalan).

---

## 4. Celah & usulan perbaikan (jujur, dengan koreksi diri)

**Koreksi terhadap draf awal dokumen ini:** saya sempat menulis "tidak ada entitas
source_health" — **salah**. Verifikasi ulang menunjukkan `services` + `heartbeats`
**sudah ada dan berisi**. Fondasi pemantauan sudah setengah jalan. Tiga celah yang
benar-benar tersisa:

| # | Celah (terverifikasi) | Bukti | Usulan | Kursi |
|---|---|---|---|---|
| C1 | `services.status` belum punya state halus (`paused/frozen/degraded/unreachable`) | P1 backlog + `models.py` hanya punya `status` string | **Perluas `services`** (atau tabel status terpisah) | SRE+Backend |
| C2 | **Tidak ada jejak build ↔ proses** | `grep deploy\|restart\|build_id` di `models.py` = kosong | Tabel kecil `deployments` + `/health` kembalikan `build_id` | SRE |
| C3 | `audit` ada, tapi tidak menautkan perubahan ambang → **tanda tangan owner + alasan** | `parameters` berversi, tapi tak ada kolom keputusan eksplisit | Perluas `parameters`/`audit` dgn referensi keputusan | Owner+Backend |

> **C2 adalah penyebab langsung kejadian hari ini.** War Room down 8→9 Okt karena
> build (21:00) tidak cocok dengan proses (20:58), dan **tidak ada tabel yang bisa
> memberi tahu itu.** Menambah `deployments` = menutupnya selamanya.

---

## 5. Yang saya TIDAK usulkan (dan kenapa)

Supaya jelas batasnya — ini bukan daftar "semua yang bisa dibayangkan":

- **Tidak** memecah `facts` per pasar. Satu tabel + kolom `kind` cukup; memecah =
  menciptakan N sumber kebenaran (melanggar ADR-005).
- **Tidak** menambah tabel `markets`. 7 pasar stabil; pasar adalah *nilai* `kind`,
  bukan entitas. (Kalau nanti 50+ pasar, baru tinjau ulang.)
- **Tidak** menambah message queue (Kafka/RabbitMQ). `jobs` + `events` sudah cukup
  untuk 1 pengguna. Menambah infra = menambah risiko tanpa manfaat.
- **Tidak** menyentuh `gate.py` atau rumus BE dalam bentuk apa pun.

---

## 6. Pertanyaan terbuka untuk owner

1. **C2 (`deployments`)** — saya usulkan sebagai pekerjaan **R0** (dok 00). Setujui?
2. **C1** — apakah state `paused/frozen/degraded/unreachable` cukup, atau ada state
   lain yang kamu butuhkan dari pengalaman operasi?
3. **C3** — apakah "keputusan owner" cukup direkam sebagai kolom di `audit`, atau kamu
   mau halaman UI terpisah untuk melihat riwayat keputusan?
