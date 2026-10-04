# F3 — Merge repo: hasil + runbook cutover (4 Okt 2026)

Tujuan: **satu repo, dua paket, satu CI.** Kode domain `live-trading` masuk ke dalam repo
`warroom`; tidak ada lagi ketergantungan path ke `../live-trading`.

Status: **SELESAI & TERVERIFIKASI DI BRANCH** `merge/live-trading` (commit `e165696`).
Cutover produksi **belum dijalankan** — menunggu keputusan owner (lihat §4).

---

## 1. Kenapa ini menyentuh produksi

Sebelumnya (`packages/core/pyproject.toml`):

```toml
live-trading = { path = "../../../live-trading", editable = true }
```

Dan `warroom-api` + `warroom-worker` **benar-benar meng-import kode itu** —
dibuktikan: `import live_trading` dari warroom → `/home/admin/live-trading/src/live_trading/__init__.py`.

Jadi memindahkan path editable = **mengubah venv produksi** → perlu `uv sync` + restart.
Itu sebabnya seluruh pekerjaan ini dilakukan di **env terpisah** (`.venv-merge`), bukan di `.venv` produksi.

| Yang dipakai produksi | Nilai |
|---|---|
| `warroom-api` ExecStart | `/home/admin/warroom/.venv/bin/uvicorn …` · `WARROOM_DOMAIN_HOME=/home/admin/live-trading` |
| `warroom-worker` ExecStart | `/home/admin/warroom/.venv/bin/python -m warroom_worker.run --every 30` |
| Unit lain yang menyentuh `live-trading` | 5 unit `live-trading-*` (dashboard, collect, snapshot, backup, watchdog) — pakai venv sendiri |

---

## 2. Yang diubah

| Berkas | Perubahan |
|---|---|
| `packages/live-trading/` | **baru** — `src/`, `tests/`, `frontend/`, `vendor/`, `scripts/`, `baselines/`, `pyproject.toml` (1,3 MB) |
| `packages/core/pyproject.toml` | `path = "../../../live-trading"` → **`workspace = true`** |
| root `pyproject.toml` | `live-trading` masuk `dependencies` + `[tool.uv.sources]` |
| root `pyproject.toml` | pytest: **`--import-mode=importlib`** (dua `tests/test_config.py` bertabrakan basename) |
| root `pyproject.toml` | ruff: kecualikan `vendor/`, `crypto/`, `.venv-merge` |
| `uv.lock` | diregenerasi — `live-trading` kini `source = { editable = "packages/live-trading" }` |
| `.gitignore` | + `.venv-merge/` |

**Tidak disalin** (memang benar): `state/` (29 M, runtime), `backups/` (51 M), `logs/` (92 K),
`secrets/`, `crypto/`→disalin, dan `scripts/ops/infra-watchdog.py` — berkas itu **tidak ter-track**
di repo asal dan tidak dirujuk unit/kron mana pun, jadi bukan bagian merge.

---

## 3. Verifikasi (dijalankan, bukan diklaim)

| Uji | Hasil |
|---|---|
| `import live_trading` dari env merge | ✅ `packages/live-trading/src/live_trading/__init__.py` |
| `uv.lock` sumber paket | ✅ `editable = "packages/live-trading"` |
| **Suite gabungan** | ✅ **431 lulus** (204 warroom + 227 live-trading) |
| `ruff check .` | ✅ **All checks passed** |
| Produksi selama kerja | ✅ 4 service `active`, publik 200, api 401, dash 200, **0 failed** |
| Venv produksi | ✅ **tidak tersentuh** — masih import dari `/home/admin/live-trading/...` |

Dua tes sempat gagal saat pertama (`test_multipage`, `test_sinkron`) karena `frontend/` belum
disalin — `_css()` membaca `packages/live-trading/frontend/assets/style.css`. Setelah `frontend/`,
`crypto/`, `baselines/`, `scripts/` disalin: hijau.

---

## 4. Runbook cutover (SATU-SATUNYA langkah yang menyentuh produksi)

Perlu persetujuan owner. Estimasi: <2 menit, downtime ~5 detik per servis.

```bash
# 0. pastikan branch sudah di-merge ke main
cd /home/admin/warroom && git log --oneline -1

# 1. TITIK BALIK — pakai commit SEBELUM merge, bukan HEAD sesudahnya.
#    (Koreksi 4 Okt: `git rev-parse HEAD` dicatat setelah merge, jadi hash itu tidak
#     mengembalikan venv ke lokasi lama. Yang benar: 8fb10f3.)
#    Cek: jalankan `git show 8fb10f3:packages/core/pyproject.toml | grep live-trading`
#    → harus masih `path = "../../../live-trading"`, dan `git ls-tree 8fb10f3 packages/`
#      harus TIDAK punya packages/live-trading.
TITIK_BALIK=8fb10f3
echo "$TITIK_BALIK" > /tmp/warroom-sebelum-cutover.txt

# 2. sync venv PRODUKSI ke struktur baru
uv sync

# 3. buktikan import mengarah ke dalam repo
.venv/bin/python -c "import live_trading;print(live_trading.__file__)"
#   diharapkan: /home/admin/warroom/packages/live-trading/src/live_trading/__init__.py

# 4. restart hanya 3 unit warroom (unit live-trading-* TIDAK perlu)
sudo systemctl restart warroom-api warroom-worker warroom-web

# 5. verifikasi
systemctl is-active warroom-api warroom-web warroom-worker
curl -s -o /dev/null -w '%{http_code}\n' https://0xgunsl1ng3r.xyz   # 200
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8800/api/v1/health  # 401 (tanpa cookie)
uv run pytest -q    # 431 lulus
```

**Rollback (kalau ada yang merah):**

```bash
cd /home/admin/warroom
git checkout main && git reset --hard 8fb10f3      # commit SEBELUM merge (bukan HEAD pasca-merge)
uv sync && sudo systemctl restart warroom-api warroom-worker warroom-web
```

---

## 5. Yang TIDAK berubah (aman)

- **State runtime tetap** di `/home/admin/live-trading` lewat `WARROOM_DOMAIN_HOME` — 48 berkas state
  (snapshot, radar_cache, arjum_quota, idx616_mirror, …) tidak dipindah.
- **Unit `live-trading-*` tidak tersentuh** — dashboard `:8799`, collect, snapshot, backup, watchdog
  tetap jalan dari `/home/admin/live-trading/.venv` dengan `LT_HOME=/home/admin/live-trading`.
- **Tencent read-only** — cuma dibaca.

## 6. Langkah lanjutan setelah cutover (kalau owner mau benar-benar "satu")

Pindahkan `state/` + `secrets/` + `backups/` masuk ke dalam repo (atau ke `/var/lib/warroom/`),
lalu ubah `WARROOM_DOMAIN_HOME` + `LT_HOME`. Itu fase terpisah — butuh jendela pemeliharaan
sendiri karena semua 5 unit `live-trading-*` ikut berubah.
