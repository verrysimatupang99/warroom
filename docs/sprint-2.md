# Sprint 2 — log harian

**Goal:** *Jurnal bisa diaudit.*
**Periode resmi:** 6–12 Nov 2026.
**Catatan:** US2.1 dan US2.2 ditarik maju **30 Okt 2026** karena seluruh Sprint 1
selesai kecuali bukti trade pertama yang menunggu pasar. Sprint 2 tetap dievaluasi
pada jendela resminya.

---

## 30 Okt 2026 — ditarik maju

### Selesai

- **US2.2 — Edge eksekusi dari fills (3 SP).**
  - Implementasi sudah ada di `warroom_api.lokal.journal_edge`: slippage per jam dan
    per simbol, latensi rata-rata, dan `503` hanya bila `fills.csv` benar-benar kosong.
  - Yang ditambahkan: 3 tes yang mengunci perilaku itu
    (`services/api/tests/test_jurnal_lokal.py`): pengelompokan jam/simbol, kasus kosong,
    dan penolakan market crypto dengan alasan.
  - Bukti: `pytest services/api/tests/test_jurnal_lokal.py` → **9 passed**.
  - Tidak ada perubahan perilaku; ini verifikasi, bukan fitur baru.

- **US2.1 — Rekonsiliasi `deals.csv` vs statement MT5 (3 SP).**
  - Modul `warroom_core.rekonsiliasi_deal`:
    - parser statement MT5 (UTF-16LE/BOM atau UTF-8), hanya baris `Direction=out`;
    - net = profit + swap + commission;
    - cocokkan per tiket deal, selisih > toleransi (default $0,01) = temuan;
    - laporkan deal yang hanya ada di statement / hanya di `deals.csv`, duplikat,
      dan filter periode `--sejak/--sampai`.
  - CLI `tools/rekonsiliasi_forwardtest.py` — exit `0` cocok, `1` selisih,
    `2` statement tidak terbaca / tidak ada deal `out`.
  - `tools/ea_jurnal.py` sekarang memakai parser yang sama (tidak ada dua aturan).
  - Tes: `packages/core/tests/test_rekonsiliasi_deal.py` → **11 passed**.
  - Bukti sintetis: statement 2 deal (net $12,00) vs `deals.csv` (net $11,90) →
    `SELISIH ticket=102 … diff=-0.10`, exit 1. Sesuai harapan.
  - Batas jujur: **belum ada statement nyata** untuk periode demo; angka nyata baru
    bisa direkonsiliasi setelah trade pertama.

- **US2.3 — ADR sumber kebenaran jurnal (5 SP).**
  - `docs/adr/0009-sumber-kebenaran-jurnal.md`: **`deals.csv` sumber kebenaran forex**;
    tabel `trades` (0 baris, tanpa pembaca/penulis) tidak dipakai untuk forex dan
    ditandai deprecated di docstring model. Arah impor kelak wajib CSV → DB.
  - Penjaga yang sudah ada: tes jurnal forex dari `deals.csv`, tes rekonsiliasi, dan
    tracker DoD membaca berkas yang sama.

- **US3.2 — Scanlog forex vs crypto terpisah (3 SP).**
  - API `/api/v1/journal/scanlog?market=all|forex|crypto`:
    forex = riwayat evaluasi EA dari fakta `mt5_snapshot` (dedupe evaluasi identik);
    crypto = `verdicts.jsonl`. `all` mengembalikan dua bagian terpisah.
  - UI: panel **Riwayat evaluasi EA** di `/forex?sub=sinyal` (XAUUSD, sesi, alasan,
    ATR/spread/RSI/tren). `RiwayatKeputusan` kini menerima prop `market` dan halaman
    crypto memakai `market="crypto"`.
  - Bukti live: `market=forex` → 50 evaluasi berbeda; `market=crypto` → 777 verdict.
  - E2E `cek_panel_reaper.spec.ts` (2 tes) → **2 passed**, termasuk tidak ada `USDT`
    di panel forex.

- **US2.4 — Marker trade + drawdown di kurva ekuitas (2 SP).**
  - `/journal/performance?market=forex` kini mengembalikan `markers` (deal tertutup:
    waktu, ticket, simbol, net) dan `drawdown_max_pct` dari puncak berjalan.
  - **Bug diperbaiki:** `_deret_ekuitas` dulu mengambil 2000 titik **tertua**
    (`order by asc limit`), sehingga kurva membeku setelah ~33 jam. Sekarang
    mengambil yang **terbaru** lalu dibalik ke urutan waktu naik.
  - UI: komponen `KurvaEkuitas` (SVG) di panel **Kinerja ekuitas** `/jurnal`,
    penanda hijau/merah per deal, garis drawdown, dan daftar 5 penanda terakhir.
  - Bukti live: 1217 titik, ekuitas 1000→1000, drawdown 0,00%, 0 marker (belum ada deal).
  - E2E `cek_jurnal_ekuitas.spec.ts` → **1 passed** (kurva + drawdown + legenda).

### Regresi 30 Okt (setelah US2.3–US2.4)

- `ruff check .` bersih.
- Root `pytest`: **1099** terkumpul, exit 0. Perintah AGENTS: **900**.
- Web: `svelte-check` 0 error; vitest **70** (15 berkas); knip 0 unused.
- Build + deploy web lolos health gate; API restart; e2e panel/riwayat/kurva lulus.

### Temuan di luar Sprint 2

- **10 alert `strategi/benched:legacy-smc` menumpuk** sejak 18 Okt karena subjek harian
  tidak pernah ditutup saat hari berganti. Job `notify` kini menutup alert benched
  bertanggal lampau (dan format lama tanpa tanggal); `strategi/kill-switch` tidak
  disentuh. Tes: `test_alert_benched_housekeeping.py` (2 kasus).
- **Bukti kirim Telegram diperkuat.** `telegram 200` saja tidak membuktikan pesan masuk
  ke topik yang benar. `TelegramTransport` kini membaca JSON Bot API dan menolak
  `ok=false`, chat id beda, thread beda, atau `message_thread_id` hilang; detail sukses
  mencatat `msg=<id> chat=<id> thread=<id>`. 4 tes baru (20 total di notifier).
- **Percobaan pertama paper $20 selalu gagal kirim.** `paper20-cycle.service` membuat
  alert di prosesnya sendiri tetapi tidak memuat `/etc/warroom/notifier.env`, sehingga
  transport `null` dan pesan baru terkirim pada siklus `notify` worker (hingga 5 menit).
  Unit kini memuat env yang sama; dibuktikan lewat `systemd-run` dengan env unit:
  `transport=telegram chat=-1004383844873 thread=237 token=True`.

- **Jurnal sinyal terkirim (di luar 16 SP).** Validasi ulang 450 sinyal terkirim memakai
  candle Binance sejak jam setelah kirim (bukan cache waktu verdict): 97,8% sama, 10 beda.
  Hasil as-sent: WR 54,5%, gross +0,163R; setelah fee taker 5 bps/sisi net
  **+0,102R** (PREMIUM +0,230R; **STANDAR −0,012R**). Job `jurnal-sinyal` tiap 6 jam menjalankan `lt measure`, menulis
  `/var/lib/warroom/jurnal_sinyal.json`, menerbitkan fakta, dan menyajikan
  `/api/v1/journal/signals` + panel `/crypto?sub=sinyal`. Laporan:
  `docs/laporan-sinyal-20261030.md`.

### Berikutnya

- Bukti trade pertama (sesi 08–09 UTC) → rekonsiliasi statement nyata, marker pertama.
- Sprint 3 (13–19 Nov): UI *Obsidian Telemetry* — audit token/kontras, layout cockpit,
  komponen inti.

### Blocker

- Trade/statement nyata belum ada; US2.1 dan US2.4 baru terbukti pada data sintetis/telemetri.
- PR #61 (Sprint 1) menunggu review/merge; PR #62 (Sprint 2) stacked di atasnya dan
  menunggu retarget ke `main` setelah #61 merge.
