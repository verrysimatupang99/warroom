"""Celah cakupan: POST /api/v1/live/dry-run (jalur eksekusi P6, khususnya `lt`).

Satu celah, dua gejala nyata yang lolos dari tes yang ada
(`services/api/tests/test_live_grants.py::test_dry_run_tidak_mengirim_order`):

  A. Tidak ada allowlist `subperintah`. Kontrak endpoint (docstring app.py:695 dan
     live.py:237) = "uji kering read-only, ukur kedalaman buku, tanpa order", tapi
     nilai dari body request diteruskan apa adanya ke
     `subprocess.run([lt, subperintah])` (live.py:244). Tes yang ada hanya pernah
     mengirim "depth" DAN memeriksa bahwa kata literal "order" tidak ada di argv —
     dua assert itu tetap lulus walaupun endpoint meneruskan `snapshot`,
     `dedupe`, atau `dashboard`. Padahal modul P6 menuntut owner+grant+gate
     (`/live/action` → 409) untuk hal yang menyentuh eksekusi; endpoint ini hanya
     butuh peran `operator`, tanpa grant, tanpa gate, tanpa pembatas laju.
  B. Biner yang dipakai tidak pernah diuji apa adanya. `jalankan_kering_kedalaman`
     memakai `$WARROOM_DOMAIN_HOME/.venv/bin/lt` saja (live.py:241) — jalur yang
     di host ini TIDAK ADA (`/home/admin/live-trading/.venv` sudah tidak ada),
     padahal `lt` tersedia di venv worker (`/home/admin/warroom/.venv/bin/lt`) dan
     worker punya aturan `_lt_bin()` khusus untuk ini (test_jobs_lt.py). Akibatnya
     endpoint hari ini selalu membalas HTTP 200 `{"status": "tidak-ada"}` — dan
     tes yang ada menyembunyikannya dengan `monkeypatch Path.exists → True`.

Semua tes di sini TIDAK PERNAH mengeksekusi biner sungguhan: `subprocess.run`
selalu diganti perekam yang hanya mencatat argv (balasan meniru tes lama,
returncode=0).
"""

from __future__ import annotations

from warroom_api import auth, live

# Subperintah `lt` yang mengubah keadaan (bukan sekadar membaca).
# snapshot = menimpa state/snapshot.json — persis berkas yang di-publish worker
# menjadi `facts` yang dipakai gate/verdict. dedupe = membersihkan catatan.
# dashboard = menjalankan server (memblokir sampai timeout 120 dtk).
BAHAYA = ("snapshot", "dedupe", "dashboard")


def _cookie(sid: str) -> dict[str, str]:
    return {"Cookie": f"{auth.COOKIE_NAME}={sid}"}


class _Perekam:
    """Pengganti `subprocess.run`: mencatat argv, TIDAK pernah mengeksekusi."""

    def __init__(self) -> None:
        self.panggilan: list[list[str]] = []

    def __call__(self, cmd, **kw):  # noqa: ANN001
        self.panggilan.append(list(cmd))

        class _H:
            returncode = 0  # meniru tes lama: perintah "berhasil", tanpa eksekusi nyata
            stdout = "kedalaman: 5 share @ 0.78\n"
            stderr = ""

        return _H()


def _pasang(monkeypatch) -> _Perekam:
    """Biner dianggap ADA (seperti tes lama) + semua subprocess dipalsukan."""
    rekam = _Perekam()
    monkeypatch.setattr(live.subprocess, "run", rekam)
    monkeypatch.setattr(live.Path, "exists", lambda self: True)
    return rekam


# --- A: allowlist subperintah ----------------------------------------------------------


def test_A1_subperintah_perubahan_keadaan_ditolak(client, make_user, monkeypatch) -> None:
    """Subperintah di luar kontrak read-only harus 4xx — bukan dieksekusi."""
    _pasang(monkeypatch)
    _, sid = make_user("gap-dryrun", role="operator")
    r = client.post("/api/v1/live/dry-run", json={"subperintah": "snapshot"}, headers=_cookie(sid))
    assert r.status_code in (400, 422), (
        f"subperintah 'snapshot' (menimpa state/snapshot.json) diterima dengan "
        f"HTTP {r.status_code}; seharusnya ditolak 400/422 karena di luar kontrak "
        f"read-only endpoint ini"
    )


def test_A2_subperintah_bahaya_tidak_memicu_subprocess(client, make_user, monkeypatch) -> None:
    """Bahkan sebelum balasan HTTP, tidak boleh ada proses yang dilahirkan."""
    rekam = _pasang(monkeypatch)
    _, sid = make_user("gap-dryrun2", role="operator")
    client.post("/api/v1/live/dry-run", json={"subperintah": "dedupe"}, headers=_cookie(sid))
    assert rekam.panggilan == [], (
        f"argv berbahaya diteruskan ke subprocess: {rekam.panggilan} — "
        f"endpoint read-only seharusnya tidak pernah memanggil biner untuk subperintah ini"
    )


def test_A3_daftar_bahaya_semua_ditolak(client, make_user, monkeypatch) -> None:
    rekam = _pasang(monkeypatch)
    _, sid = make_user("gap-dryrun3", role="operator")
    for sub in BAHAYA:
        r = client.post("/api/v1/live/dry-run", json={"subperintah": sub}, headers=_cookie(sid))
        assert r.status_code in (400, 422), f"subperintah '{sub}' lolos (HTTP {r.status_code})"
    assert rekam.panggilan == [], f"ada subprocess terpicu: {rekam.panggilan}"


# --- B: biner yang dipakai harus nyata tersedia ---------------------------------------


def test_B1_biner_lt_yang_dipakai_tersedia_di_host(client, make_user, monkeypatch) -> None:
    """Tanpa memalsukan `Path.exists`: biner yang dipakai harus ADA di host ini.

    `Path.exists` sengaja dibiarkan asli supaya tes ini jujur terhadap mesin;
    `subprocess.run` tetap dipalsukan supaya tidak ada eksekusi sungguhan.
    """
    rekam = _Perekam()
    monkeypatch.setattr(live.subprocess, "run", rekam)
    _, sid = make_user("gap-dryrun4", role="operator")
    r = client.post("/api/v1/live/dry-run", json={"subperintah": "depth"}, headers=_cookie(sid))
    body = r.json()
    assert body.get("status") != "tidak-ada", (
        f"endpoint memakai biner yang tidak ada: {body.get('detail')} — "
        f"jalur eksekusi ini mati di produksi dan hanya disembunyikan oleh tes lama "
        f"yang meng-`monkeypatch` Path.exists menjadi True"
    )
    assert body.get("status") in {"ok", "gagal"}, f"status tak terduga: {body}"


# --- kontrol: jalur yang sah tetap berjalan -------------------------------------------


def test_C1_kontrol_subperintah_depth_masih_dijalankan(client, make_user, monkeypatch) -> None:
    """Allowlist tidak boleh mematikan jalur sah: 'depth' tetap diteruskan utuh."""
    rekam = _pasang(monkeypatch)
    _, sid = make_user("gap-dryrun5", role="operator")
    r = client.post("/api/v1/live/dry-run", json={"subperintah": "depth"}, headers=_cookie(sid))
    assert r.status_code == 200
    assert r.json()["status"] in {"ok", "gagal"}
    assert rekam.panggilan and rekam.panggilan[0][-1] == "depth"


# --- DEMO: bukti kelemahan tes lama (baca dulu komentarnya) ----------------------------


