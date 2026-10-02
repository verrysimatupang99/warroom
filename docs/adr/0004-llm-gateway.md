# ADR-004 — LLM gateway: nutaraline utama, qonek fallback, setiap panggilan tercatat

Status: **diterima** · Tanggal: 2026-10-02 · Fase: P0 (implementasi P3-T1)

## Konteks

AI sekarang terpakai sepotong-sepotong: `live-trading/pods/nilai.py` memanggil nutaraline untuk
"setuju/tidak + 1 kalimat"; proyek Polymarket punya klien sendiri (`/opt/polymarket/agent/llm.mjs`,
qonek primary + fallback, dengan `scrub()` dan `providerOrder()`), plus loop belajar berbatas.
Keduanya tidak berbagi kebijakan, pencatatan, atau anggaran. Tanpa jejak audit, biaya dan fallback
tidak bisa dipertanggungjawabkan — padahal AI akan dipakai maksimal.

## Keputusan

1. Satu layanan `services/llm` sebagai **gateway**: `primary=nutaraline`, `fallback=qonek`
   (keduanya OpenAI-compatible). Gagal (non-2xx, timeout, jawaban kosong/tidak valid) → fallback.
   Dua-duanya gagal → `insufficient` + alert. **Tidak pernah** mengarang angka.
2. Circuit breaker per provider (5 kegagalan / 120 dtk → dilewati 300 dtk), retry 2× backoff 800 ms,
   timeout 45 dtk, cache TTL 15 mnt, anggaran harian total + per peran.
3. **Setiap panggilan dicatat** di `llm_calls`: peran, provider, model, versi prompt, token masuk/keluar,
   latensi, `ok`, `fallback_from`, hash hasil, `fact_ids[]`.
4. Konfigurasi kredensial: `/etc/warroom/llm.json` **root-only** — tidak pernah masuk
   repo/log/percakapan (pola `/etc/poly-pilot/agent-llm.json`).
5. **Angka tidak pernah lahir dari LLM.** Nilai diinjeksi sebagai blok `FAKTA` bernomor; kalimat
   yang menyebut angka tanpa `fact_id` ditolak `verifier`.
6. Konten eksternal dibungkus `UNTRUSTED_DATA`; instruksi di dalamnya diabaikan; allowlist alat
   per peran; `scrub()` sebelum kirim dan sebelum simpan.
7. Peran yang diizinkan: narrator, verifier, anomaly, hypothesis, auditor, teacher, ops-copilot,
   classify/extract. Peran tulis (hypothesis) **paper saja**; menyentuh live/gate/ambang → `prohibited`.

## Konsekuensi

- `pods/nilai.py` diganti gateway pada P3-T5, tetapi disimpan sebagai fallback lokal satu rilis;
  kontraknya (`{setuju, catatan}`) dipetakan ke peran `verifier`.
- Fallback rate, latensi p50/p95, dan biaya per peran bisa ditampilkan (LLMConsole) **dari
  `llm_calls`**, tanpa perhitungan manual.
- Kegagalan penyedia tidak menghentikan halaman: keluaran menjadi `insufficient` beserta fakta
  apa yang dibutuhkan.
- Kredensial tetap di luar repo; `gitleaks` di CI jadi pengaman tambahan, bukan pengaman utama.

## Alternatif yang ditolak

- **Tiap proyek punya klien LLM sendiri**: kebijakan provider berbeda-beda dan biaya tidak terlihat.
- **LLM sebagai pengambil keputusan gate**: melanggar prinsip "yang bisa dihitung, dihitung".
- **Hanya satu provider (tanpa fallback)**: satu gangguan penyedia mematikan seluruh fitur AI.
- **Simpan kunci di `.env` repo**: kredensial bisa bocor lewat git. Ditolak.