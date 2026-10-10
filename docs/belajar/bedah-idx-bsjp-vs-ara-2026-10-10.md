# Bedah IDX: pisahkan BSJP dari ARA Hunter (Gelombang 2, poin 5)

Tanggal: 2026-10-10 · Sumber: `~/.hermes/cron/state/idx616_signal_ledger.db` (628 baris; 431 CLOSED)
· Status: temuan, **belum ada perubahan ambang/mesin** — keputusan milik pemilik

## Angka nyata (431 trade tuntas, R per trade)

| Setup | n | menang | total R | avg R |
|---|---|---|---|---|
| ARA_HUNTER | 346 | 135 | −152,85 | **−0,442** |
| INTRADAY (scalp) | 35 | 12 | −0,38 | −0,011 |
| BSJP_STRONG | 30 | 22 | +20,47 | **+0,682** |
| BSJP_ARA | 20 | 9 | +6,68 | +0,334 |
| **TOTAL (sekarang)** | **431** | | **−126,08** | **−0,293** |

## Uji: apakah membuang ARA menaikkan ekspektasi total?

| Skenario | n | total R | avg R |
|---|---|---|---|
| SEMUA (sekarang) | 431 | −126,08 | −0,293 |
| TANPA ARA_HUNTER | 85 | **+26,77** | **+0,315** |
| HANYA BSJP | 50 | +27,15 | +0,543 |

**Ya, tegas.** Membuang ARA membalik total dari −126,08R menjadi **+26,77R** (ekspektasi −0,293 →
+0,315 per trade). ARA_HUNTER **mendominasi volume (346/431 = 80%) dan mendominasi kerugian.**

## Uji pakem resmi (ambang pemilik: n≥30, ci=0,90, ci_low > BE)

| Setup | n | avg R | CI90 bawah | Vonis |
|---|---|---|---|---|
| BSJP_STRONG | 30 | +0,682 | **+0,254** | **LOLOS** |
| BSJP gabungan | 50 | +0,543 | **+0,198** | **LOLOS** |
| BSJP_ARA | 20 | +0,334 | −0,245 | BELUM (sampel < 30) |
| ARA_HUNTER | 346 | −0,442 | −0,815 | BELUM (rugi) |

**BSJP_STRONG lolos gate** dengan sampel cukup. Ini setup paling terpercaya dari mesin IDX.
ARA_HUNTER jelas **tidak layak** — n besar justru mempertegas bahwa ia merugi.

## Catatan jujur

- Ledger ini **beku sejak 6 Okt** (mesin Tencent di-pause). Mesin lokal (port A1) belum menambah
  baris baru — pasar tutup; akan mulai mengisi Senin 12 Okt.
- 350 baris CREATED belum tuntas (102 ≥10 hari) — dari era beku; mesin lokal akan menilai yang
  bisa dinilai.
- Angka R sudah termasuk biaya (BSJP_COST_PCT 0,40% sesuai mesin).

## Usulan (bukan keputusan)

1. **Matikan ARA_HUNTER** dari komposisi live; pertahankan **BSJP_STRONG + BSJP_ARA**.
2. Biarkan BSJP_ARA mengumpulkan sampel sampai n≥30, lalu uji ulang pakem.
3. **Laporkan pemisahan ini di UI** IDX: jangan campur ARA (rugi) dengan BSJP (untung) dalam
   satu angka total yang menyesatkan.
