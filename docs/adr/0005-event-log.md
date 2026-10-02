# ADR-005 — Event log append-only + fakta berversi (`fact_id`)

Status: **diterima** · Tanggal: 2026-10-02 · Fase: P0 (implementasi P1-T1/T5)

## Konteks

Sekarang tidak ada riwayat. Pertanyaan "apa yang berubah sejak terakhir saya lihat", "siapa
mengubah parameter ini dan atas dasar apa", atau "verdict mana yang naik melewati BE" tidak bisa
dijawab. Angka juga tidak punya sumber: UI lama menampilkan nilai dari snapshot tanpa jejak
asal-usul, sehingga klaim uang pernah salah tampil (state melaporkan `claimablePayout $8,62`;
verifikasi on-chain menunjukkan saldo share 0,000000 — klaim itu palsu).

## Keputusan

1. **`facts`** — nilai tunggal berversi: `kind`, `key`, `value_json`, `source`, `observed_at`,
   `ttl_s`, `hash`. Kunci `(kind, key, observed_at)`. Setiap angka di UI dan setiap angka yang
   dikutip AI wajib menunjuk `fact_id`.
2. **`events`** — append-only: `type`, `actor`, `payload_json`, `fact_ids[]`, `severity`,
   `created_at`. Sinyal, verdict, trade, usulan/parameter, panggilan LLM, alert, dan aksi operator
   semuanya menulis ke sini. Tidak ada update/delete.
3. **Kesegaran dihitung sekali**: `observed_at + ttl_s` vs sekarang. Lewat TTL → badge basi
   (`segar/basi/cache/n/a`). Tidak ada dua definisi "basi" (UI vs alert memakai sumber sama).
4. **Data hilang = `unknown`/`n/a` + kode error**, bukan nol dan bukan nilai lama.
5. Klaim uang **wajib** direkonsiliasi ke sumber (on-chain/venue) sebelum tampil sebagai "nyata"
   (job `reconcile`, P4-T5).
6. Retensi: `events` 24 bulan (partisi bulanan), `llm_calls` 12 bulan, arsip parquet tahunan;
   `facts` menyimpan nilai terbaru + snapshot 90 hari.

## Konsekuensi

- Notifier, UI, dan AI membaca dari satu tempat → tidak ada logika ganda yang bisa berbeda.
- Menambah jenis kejadian = menambah `type`, bukan tabel baru.
- Volume tumbuh: perlu partisi bulanan + kebijakan retensi sejak awal (bukan ditambal belakangan).
- Uji parity (P1-T5/T6) menjadi mungkin: bandingkan nilai `facts` dengan `state/snapshot.json`
  untuk 20 fakta acak, otomatis.

## Alternatif yang ditolak

- **Hanya `state/snapshot.json` (tanpa DB)**: tidak ada riwayat, tidak ada audit, tidak bisa
  di-query lintas area, dan dua pembaca bisa menafsirkan berkas yang sama secara berbeda.
- **Log teks bebas**: tidak bisa dipakai UI/notifier tanpa parsing rapuh.
- **Update-in-place untuk `events`**: menghapus bukti; audit jadi tidak bisa dipercaya.