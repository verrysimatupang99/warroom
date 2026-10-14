# Reset market & timer forex — langkah + rollback (14 Okt 2026)

## Apa yang dilakukan

Owner minta semua market direset dari 0 (poin 2). Reset berhasil untuk market yang
penulisnya di dalam sistem: **crypto, idx, gmgn**. **Forex** sempat "balik" karena
timer lokal menarik ulang jurnal dari Tencent.

### Akar forex
`~/.config/systemd/user/forex-refresh.timer` (tiap 30 menit) menjalankan
`~/warroom/scripts/forex_refresh.sh`, yang **menyalin baca-saja** jurnal dari server
Tencent (`ubuntu@43.155.219.37:~/.hermes/trading-journal/`) ke
`state/forex_journal.json`. Karena jurnal Tencent masih berisi trade lama, file lokal
selalu kembali tiap 30 menit -> reset tak bertahan.

### Yang dikerjakan
1. **Disable** `forex-refresh.timer` (hapus symlink di `timers.target.wants/`).
   Symlink asal disimpan untuk rollback (lihat bawah).
2. **Reset** ulang -> `forex_journal.json` diarsipkan ke
   `state/arsip/20261014T221803Z/`, forex bersih (dompet `tersedia=False` = Rp 10 jt).

## Rollback (menyalakan lagi timer forex)

```bash
# Kembalikan symlink (pulihkan auto-start timer)
cp -a /tmp/forex-timer-rollback.link \
      ~/.config/systemd/user/timers.target.wants/forex-refresh.timer
systemctl --user daemon-reload
systemctl --user start forex-refresh.timer
```

Bila `/tmp/forex-timer-rollback.link` sudah hilang (tmp dibersihkan), buat ulang:

```bash
ln -s /home/admin/.config/systemd/user/forex-refresh.timer \
      ~/.config/systemd/user/timers.target.wants/forex-refresh.timer
systemctl --user daemon-reload
systemctl --user start forex-refresh.timer
```

## Kalau mau forex IKUT ter-reset sampai sumbernya

Timer lokal hanya menyalin. Sumber sebenarnya ada di Tencent:
`ubuntu@43.155.219.37:~/.hermes/trading-journal/{xauusd_journal,multipair_journal}.json`.

Agar forex benar-benar dari 0 **dan tetap begitu** setelah timer dinyalakan lagi,
jurnal di Tencent harus direset/diarsipkan lebih dulu. Itu menyentuh Tencent —
**butuh keputusan eksplisit owner** (batasan proyek: jangan sentuh Tencent tanpa izin).

## Catatan tentang `systemctl --user`

Dari sesi agen, `systemctl --user` gagal ("Failed to connect to bus: No medium found").
Karena itu disable dilakukan lewat **file symlink**, yang efeknya sama. Verifikasi:
`ls ~/.config/systemd/user/timers.target.wants/forex-refresh.timer` -> harus kosong.
