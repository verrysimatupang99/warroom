## Apa yang berubah

<!-- Ringkas 1–3 poin: berkas/fitur yang disentuh dan efeknya. -->

-

## Kenapa

<!-- Alasan/masalah yang diselesaikan. Tempel tautan isu/audit bila ada. -->

-

## Sudah dicek

<!-- Centang yang benar-benar dijalankan; jangan centang yang belum. -->

- [ ] `uv run ruff check .` (warroom)
- [ ] `uv run pytest -q` (warroom, suite platform)
- [ ] `cd ~/live-trading && uv run ruff check . && uv run pytest -q` (domain)
- [ ] `cd apps/web && npm run check && npm run test` (web)
- [ ] `bash ops/ci-local.sh` (versi CI yang sama, termasuk gitleaks)
- [ ] Bukti perintah ditempel di bawah ini

```
# tempel output ringkas bukti di sini (atau tulis path berkas bukti)
```

## Selanjutnya

<!-- Sisa pekerjaan / tindak lanjut / risiko yang belum tertutup. "tidak ada" juga jawaban sah. -->

-

---

### Batas keselamatan (isi hanya bila PR menyentuh area ini — hapus baris yang tak relevan)

- [ ] Tidak menyentuh `/opt/polymarket` (baca-saja)
- [ ] Tidak menyentuh Tencent (baca-saja)
- [ ] Tidak menyentuh gate live (`/etc/poly-pilot/activation-approved`)
- [ ] Tidak ada kredensial masuk repo/log/percakapan (`gitleaks` bersih)
- [ ] Tidak mengarang angka; ketiadaan data ditulis `tidak-izin`/`n/a`/`—`, bukan `0`
- [ ] Ambang gate & rumus BE tidak diubah (hanya owner) — atau perubahan disetujui owner: ____
