# SOP Postmortem — War Room

Dibuat: **2026-10-09** (R6, revisi total) · Kursi: SRE · Pelengkap: `ops/runbook-deploy.md`

---

## Kenapa SOP ini ada

Runbook deploy (`ops/runbook-deploy.md`) mengajarkan cara **melakukan** deploy dengan benar.
SOP ini mengatur hal yang berbeda: **apa yang dilakukan setelah sesuatu gagal** — supaya
insiden yang sama tidak terulang, dan supaya penyebab dilaporkan **apa adanya** tanpa
mengarang.

SOP ini lahir dari insiden nyata 8–9 Okt 2026 (web 500 di semua rute). Ia sengaja
diarahkan ke **kelas** masalah, bukan kejadian tunggal.

---

## Aturan dasar postmortem

1. **Blameless.** Postmortem meneliti **sistem**, bukan menyalahkan orang. Pertanyaan selalu
   "kenapa sistem mengizinkan ini terjadi?", bukan "siapa yang lupa?".
2. **Bukti, bukan tafsir.** Setiap klaim di postmortem harus punya bukti: potongan log,
   output perintah, hash, timestamp. Yang tak terbukti → ditulis `hipotesis`, bukan fakta.
3. **Label jelas:** `observed` (terlihat langsung) · `inferred` (disimpulkan dari bukti) ·
   `unknown` (belum tahu). Jangan menyamarkan `inferred` sebagai `observed`.
4. **Akar ≠ gejala.** "Web 500" itu gejala. Akarnya "proses memegang manifest lama".
   Postmortem yang berhenti di gejala tidak berguna.
5. **Satu aksi per akar.** Tiap temuan ditutup dengan: aksi nyata + pemilik + tanggal, atau
   keputusan sadar untuk **tidak** bertindak (dengan alasan).

---

## Alur saat insiden (dari gejala ke akar)

```
1. AMATI    — apa gejalanya? kapan mulai? seberapa luas? (semua rute atau satu?)
2. BUKTI    — tarik log/timestamp SEBELUM mengubah apa pun.
3. PULIHKAN — kembalikan layanan dulu (restart/rollback), jangan sambil mendiagnosis.
4. AKAR     — cari penyebab, pisahkan observed vs inferred.
5. CEGAH    — apa yang membuat ini mustahil terjadi lagi?
6. CATAT    — tulis postmortem singkat (template di bawah).
```

**Urutan 2 sebelum 3 itu wajib.** Kalau Anda restart dulu lalu mencari log, Anda sering
kehilangan bukti akar (log lama tertimpa). Ambil bukti **dulu**, walau hanya beberapa detik.

---

## Kelas insiden yang sudah terbukti (jangan ulangi)

### K-1 · Build ditimpa, proses lama masih hidup → 500 di semua rute

**Gejala:** SEMUA halaman 500 (bukan cuma satu). Log memuat
`ERR_MODULE_NOT_FOUND ... chunks/nodes/*.js`.

**Akar (observed):** proses node memegang `manifest.js` lama di memori; `build/` di disk
sudah ditimpa build baru → nama chunk lama tak ada lagi.

**Deteksi cepat:**
```bash
sudo journalctl -u warroom-web -n 50 --no-pager | grep -iE 'MODULE_NOT_FOUND|error'
# bandingkan build_id proses vs disk:
curl -sS https://0xgunsl1ng3r.xyz/api/v1/build       # build_id proses API
cat /home/admin/warroom/apps/web/build/build-id.txt   # build_id disk
```
**Pemulihan:** `sudo systemctl restart warroom-web` (~2 detik).
**Pencegahan:** `deploy = build + restart + verifikasi` sebagai satu unit (`ops/deploy-web.sh`).

### K-2 · E2E dijalankan ke target yang salah → gagal massal yang menyesatkan

**Gejala:** banyak tes ber-sesi gagal serentak dengan "timeout"; halaman yang diperiksa
ternyata form login, bukan konten.

**Akar (observed):** E2E dijalankan ke `127.0.0.1:3100` (node mentah) **tanpa nginx**. Di
port itu `/api/v1/auth/login` → **404** (tak ada proxy `/api/`), jadi `global-setup` gagal
login → sesi kosong → semua halaman jatuh ke `/masuk`.

**Deteksi cepat:**
```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3100/api/v1/build  # 404 = salah target
curl -sS -o /dev/null -w '%{http_code}\n' https://0xgunsl1ng3r.xyz/api/v1/build # 200 = benar
```
**Pencegahan:** selalu jalankan E2E lewat **origin produksi** (`baseURL` default), jangan
paksa `WARROOM_E2E_BASE=http://127.0.0.1:3100`. (Ini penyebab "14 gagal" yang ternyata
tinggal 2 setelah target dibetulkan.)

### K-3 · Sesi E2E basi dipakai ulang → gagal serentak yang ambigu

**Gejala:** semua tes ber-sesi gagal; gejala tampak seperti server mati.

**Akar (observed):** file `e2e/.auth/sesi.json` lama dipakai lagi padahal sesi server sudah
tidak valid.
**Pencegahan (sudah ada):** `global-setup.ts` **selalu** membuat sesi baru tiap run dan
menggagalkan run dengan pesan jelas (HTTP + isi respons) bila login tak berhasil.

### K-4 · Ambang/rumus gate diubah lewat jalur selain owner

**Gejala:** verdict `lolos` muncul di luar kebijakan, atau ambang bergeser tanpa jejak.

**Akar:** perubahan menyentuh `gate.py` / rumus BE tanpa persetujuan owner.
**Pencegahan:** ADR-003 + ADR-006 — ambang & rumus **hanya** boleh diubah manusia; agen
dilarang. `gate.py` murni (tanpa I/O/DB/LLM); `ci_low > be` satu-satunya jalur `lolos`.

---

## Template postmortem (isi singkat, jujur)

```markdown
# Postmortem — <judul singkat>

- Tanggal insiden: <YYYY-MM-DD HH:MM UTC>
- Durasi dampak: <menit/jam>
- Tingkat: <ringan/sedang/berat>
- Penulis: <peran>

## Ringkasan
<Satu paragraf: apa yang terjadi, dampak, bagaimana pulih.>

## Garis waktu (dengan bukti)
| Waktu (UTC) | Kejadian | Bukti |
|---|---|---|
| ... | ... | <log/hash/output perintah> |

## Akar masalah
- observed: <yang terlihat langsung>
- inferred: <yang disimpulkan dari bukti>
- unknown:  <yang belum diketahui>

## Dampak
<Apa yang tidak bisa dipakai, berapa lama, siapa/apa yang terdampak.>

## Pemulihan
<Langkah konkret yang memulihkan layanan.>

## Pencegahan (satu aksi per akar)
| Aksi | Pemilik | Tanggal | Status |
|---|---|---|---|
| ... | ... | ... | ... |

## Pelajaran
<Pola yang bisa dipakai ulang; kelas insiden (K-1..K-4) bila cocok.>
```

---

## Yang TIDAK boleh dilakukan

- ❌ **Jangan** menyunting log supaya "kelihatan bersih".
- ❌ **Jangan** menulis penyebab yang tak Anda buktikan (no fabricated evidence).
- ❌ **Jangan** menutup postmortem tanpa aksi (atau tanpa alasan sadar untuk tidak beraksi).
- ❌ **Jangan** menyalahkan orang; tanyakan kenapa sistem mengizinkannya.
- ❌ **Jangan** melewati langkah bukti sebelum pemulihan (K-1: log lama bisa tertimpa).

---

## Kaitan dengan dokumen lain

| Dokumen | Peran |
|---|---|
| `ops/runbook-deploy.md` | cara deploy benar (build+restart+verifikasi) |
| `docs/adr/0006-keputusan-owner.md` | siapa yang berhak memutuskan apa |
| `docs/revisi-total/` | konteks revisi & rencana R0–R6 |
| `/api/v1/build` | sumber kebenaran build↔proses (verifikasi cepat) |
