# Reset market & timer forex — langkah + rollback (14 Okt 2026)

## Apa yang dilakukan

Owner minta semua market direset dari 0 (poin 2). Hasil akhir:

| Market | Status |
|---|---|
| crypto | **bersih dari 0** ✓ |
| idx | **bersih dari 0** ✓ |
| gmgn | **bersih dari 0** ✓ |
| forex | **bersih dari 0** ✓ (lihat catatan timer di bawah) |
| polymarket | **tidak direset** — milik service `poly-pilot` terpisah |

## Akar forex

`~/.config/systemd/user/forex-refresh.timer` (tiap 30 menit) menjalankan
`~/warroom/scripts/forex_refresh.sh`, yang **menyalin baca-saja** jurnal dari server
Tencent (`ubuntu@43.155.219.37:~/.hermes/trading-journal/`) ke
`state/forex_journal.json`. Karena jurnal Tencent masih berisi trade lama
(7 XAUUSD + 19 multipair), file lokal **selalu kembali** tiap 30 menit -> reset tak
bertahan.

## PELAJARAN PENTING: hapus symlink TIDAK cukup

Percobaan pertama: menghapus symlink di `timers.target.wants/` — **GAGAL**. Timer
yang sedang aktif **tetap menembak** (bukti log: `[22:19:40Z] SEGAR xau 0->7 mp 0->19`
– file kosong jadi 7 lagi, walau symlink sudah hilang). Menghapus symlink hanya
mencegah auto-start **setelah reboot**, bukan menghentikan timer yang jalan.

Cara yang **benar**:

```bash
export XDG_RUNTIME_DIR=/run/user/$(id -u)   # WAJIB; tanpa ini "Failed to connect to bus"
systemctl --user stop forex-refresh.timer       # hentikan yang sedang jalan
systemctl --user disable forex-refresh.timer    # jangan auto-start
systemctl --user daemon-reload
systemctl --user is-active forex-refresh.timer  # -> inactive
```

**Catatan `systemctl --user` dari sesi agen:** gagal dengan `XDG_RUNTIME_DIR` kosong
("Failed to connect to bus: No medium found"). Setel `XDG_RUNTIME_DIR=/run/user/$(id -u)`
eksplisit -> **berhasil**. Ini juga berlaku untuk `infra-watchdog` dan timer user lain.

## Rollback (menyalakan lagi timer forex)

```bash
export XDG_RUNTIME_DIR=/run/user/$(id -u)
systemctl --user enable forex-refresh.timer
systemctl --user start forex-refresh.timer
systemctl --user is-active forex-refresh.timer   # -> active
```

## Kalau mau forex tetap dari 0 SETELAH timer dinyalakan lagi

Timer lokal hanya menyalin. Sumber sebenarnya ada di Tencent:
`ubuntu@43.155.219.37:~/.hermes/trading-journal/{xauusd_journal,multipair_journal}.json`.

Selama jurnal Tencent masih berisi trade lama, menyalakan timer akan mengembalikan
trade itu. Agar forex benar-benar nol secara permanen, jurnal di Tencent harus
direset/diarsipkan — **itu menyentuh Tencent, butuh keputusan eksplisit owner**
(batasan proyek).

Ringkas: **timer mati = forex tetap nol. Timer hidup = forex kembali berisi trade Tencent.**
