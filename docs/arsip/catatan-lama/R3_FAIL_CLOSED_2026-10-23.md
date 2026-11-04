# R3 deployed — gerbang Laya fail-closed (23 Okt 2026)

## Sebelum vs sesudah

| Kondisi | Sebelum | Sesudah |
|---|---|---|
| Model tidak termuat | `True, 0.85` (**lolos**) | `False, 0.0` (**blokir**) |
| Verdict tidak dikenali | `True, 0.0` (**lolos**) | `False, 0.0` (**blokir**) |
| Inferensi exception | `True, 0.0` (**lolos**) | `False, 0.0` (**blokir**) |
| EXECUTE p < ambang | blokir | blokir (tetap) |

Angka `0.85` pada versi lama tidak pernah dihitung dari data apa pun — itu sebabnya
seluruh nilai "middleware Laya" tidak bisa dibuktikan.

## Perubahan

### `multi_session_laya.py`
- tiga jalur gagal sekarang **memblokir** dengan alasan eksplisit menyebut cabang
- setiap verdict dicatat: `Gerbang Laya: LOLOS|DIBLOKIR -> <alasan>`
- `last_block_reason` disimpan saat blokir, dibersihkan saat sinyal lolos

### `engine.py`
Respons `WAITING_SETUP` kini menyertakan `blocked_reason`, sehingga penolakan
gerbang bisa dibedakan dari "pasar memang belum ada setup".

Contoh nyata setelah deploy:
```json
{
  "status": "WAITING_SETUP",
  "reason": "Kondisi pasar saat ini belum memenuhi kriteria strategi PNP aktif",
  "blocked_reason": "Laya SKIP p=0.228 (ambang 0.60) side=LONG sesi=NEW_YORK"
}
```

## Verifikasi

```
pytest packages/core : 143 lulus
test_laya_fail_closed: 6 kasus (model mati, evaluator None, exception,
                       verdict tak dikenal, keyakinan rendah -> BLOKIR;
                       EXECUTE p=0.93 -> LOLOS)
ruff                 : All checks passed
commit               : 1de2873
deploy               : build 1de2873-20261023T195717Z
push                 : 6c3217c..1de2873
EA                   : connected=True, heartbeat 3 detik, 0 posisi
```

## Temuan penting dari verifikasi: LATENSI

| Kondisi | Waktu respons `/forex/levels` |
|---|---|
| Cold start (model baru dimuat) | **30 detik** |
| Warm (model sudah di memori) | **1,5 – 2,2 detik** |
| Timeout WebRequest EA | **3 detik** |

Konsekuensi:
- Setelah API restart, poll pertama EA **akan timeout** (30 s > 3 s). EA retry 5 detik
  kemudian, lalu normal.
- Warm inference (2,2 s) hanya menyisakan margin ~0,8 detik di bawah batas 3 detik.
  Bila mesin sedang sibuk, poll bisa gagal sesekali.
- **Laya masih berjalan di dalam proses API** (jalur panas). Ini belum diperbaiki
  dan tetap menjadi risiko: model ~1 GB di proses yang juga melayani dashboard.

Mitigasi yang disarankan (belum dikerjakan):
1. Naikkan timeout WebRequest EA ke 8–10 detik (murah, langsung hilangkan
   timeout cold-start), atau
2. Pindahkan Laya ke job terjadwal + cache verdict (menghilangkan latensi dari
   jalur permintaan sepenuhnya) — ini Opsi A pada rekomendasi arsitektur.

## Catatan perilaku

Laya saat ini konsisten memberi `SKIP` dengan p≈0,23 untuk setup LONG di sesi
NEW_YORK. Artinya selama model menilai demikian, **EA tidak akan membuka posisi** —
dan itu memang perilaku yang benar untuk gerbang fail-closed.

## Masih terbuka
- R4 — satu sumber kebenaran SL/TP (API snapshot vs fill EA)
- R5 — Laya belum menerima konteks akun (balance/equity/posisi)
- R7 — `min_rrr=1.6` belum jadi penjaga keras
- Laya di jalur panas (lihat bagian latensi)
