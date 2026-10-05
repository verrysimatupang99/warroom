"""Regresi untuk temuan audit keamanan 5 Okt 2026.

Dua temuan yang ditutup di sini:
1. ``/api/v1/ai/verifier`` menerima **sesi apa pun** (termasuk `viewer`) dan tidak
   berkuota → kuota LLM berbayar bisa dibakar tanpa batas.
2. ``/api/v1/auth/login`` tanpa batas laju → brute force + amplifikasi scrypt
   (~16 MiB/percobaan).

Aturan yang dikodekan: jalur sesi pada endpoint berbiaya butuh peran `operator`;
setiap jalur berbiaya dibatasi laju; batas laju memancarkan **429** (kode yang
sebelumnya hanya terdaftar di `errors.py` tapi tak pernah dipakai).
"""

from __future__ import annotations

import pytest
from warroom_api import app as app_mod
from warroom_api import auth, limits


def _cookie(sid: str) -> dict[str, str]:
    return {"Cookie": f"{auth.COOKIE_NAME}={sid}"}


@pytest.fixture(autouse=True)
def _reset_limiter():
    """Pembatas laju adalah singleton modul — reset antar tes supaya tidak bocor."""
    for lim in (app_mod.LOGIN_LIMITER, app_mod.VERIFIER_LIMITER, app_mod.NARRATE_LIMITER):
        lim.reset()
    yield
    for lim in (app_mod.LOGIN_LIMITER, app_mod.VERIFIER_LIMITER, app_mod.NARRATE_LIMITER):
        lim.reset()


# --- unit: pembatas laju ---------------------------------------------------------------


def test_limiter_menolak_setelah_batas() -> None:
    lim = limits.Limiter(3, jendela_s=60.0)
    assert [lim.izinkan("ip", sekarang=float(i)) for i in range(4)] == [True, True, True, False]


def test_limiter_jendela_geser_mengizinkan_lagi() -> None:
    lim = limits.Limiter(2, jendela_s=10.0)
    assert lim.izinkan("ip", sekarang=0.0)
    assert lim.izinkan("ip", sekarang=1.0)
    assert not lim.izinkan("ip", sekarang=2.0)
    # setelah jendela lewat, yang lama keluar dari deque
    assert lim.izinkan("ip", sekarang=11.0)


def test_limiter_per_kunci_terpisah() -> None:
    lim = limits.Limiter(1, jendela_s=60.0)
    assert lim.izinkan("a", sekarang=0.0)
    assert lim.izinkan("b", sekarang=0.0)
    assert not lim.izinkan("a", sekarang=0.1)


def test_batas_dari_env_nilai_tak_sah_pakai_bawaan() -> None:
    assert limits.batas_dari_env("WARROOM_TIDAK_ADA_XXX", 7) == 7


# --- regresi: login dibatasi laju ------------------------------------------------------


def test_login_dibatasi_laju_429(client, make_user) -> None:
    """Setelah batas tercapai, percobaan berikutnya → 429 (bukan 401 lagi)."""
    batas = app_mod.LOGIN_LIMITER.batas
    for _ in range(batas):
        r = client.post("/api/v1/auth/login", json={"username": "tak-ada", "password": "salah"})
        assert r.status_code == 401
    r = client.post("/api/v1/auth/login", json={"username": "tak-ada", "password": "salah"})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"


# --- regresi: verifier butuh peran + dibatasi ------------------------------------------


def test_verifier_viewer_ditolak(client, make_user, monkeypatch) -> None:
    """Sesi `viewer` tidak boleh memanggil endpoint berbiaya."""
    monkeypatch.delenv("WARROOM_SERVICE_TOKEN", raising=False)
    _, sid = make_user("audit-viewer", role="viewer")
    r = client.post("/api/v1/ai/verifier", json={"klaim": []}, headers=_cookie(sid))
    assert r.status_code == 401


def test_verifier_tanpa_sesi_ditolak(client, monkeypatch) -> None:
    """TestClient berasal dari 'testserver' (bukan 127.0.0.1) → tanpa token harus 401."""
    monkeypatch.delenv("WARROOM_SERVICE_TOKEN", raising=False)
    r = client.post("/api/v1/ai/verifier", json={"klaim": []})
    assert r.status_code == 401


def test_verifier_operator_lolos_gerbang_auth_tanpa_bakar_token(client, make_user, monkeypatch) -> None:
    """Operator lolos gerbang auth; `klaim` kosong berhenti di 422 SEBELUM panggilan LLM.

    Inilah pembuktian bypass yang dipakai di laporan audit: klaim kosong sengaja
    supaya nol token provider terbakar.
    """
    monkeypatch.delenv("WARROOM_SERVICE_TOKEN", raising=False)
    _, sid = make_user("audit-operator", role="operator")
    r = client.post("/api/v1/ai/verifier", json={"klaim": []}, headers=_cookie(sid))
    assert r.status_code == 422
    assert r.json()["error"]["detail"]["code"] == "klaim_kosong"


def test_verifier_dibatasi_laju(client, make_user, monkeypatch) -> None:
    """Bahkan operator dibatasi laju — kuota tidak bisa dibakar beruntun."""
    monkeypatch.delenv("WARROOM_SERVICE_TOKEN", raising=False)
    _, sid = make_user("audit-operator-2", role="operator")
    batas = app_mod.VERIFIER_LIMITER.batas
    kode = [client.post("/api/v1/ai/verifier", json={"klaim": []}, headers=_cookie(sid)).status_code
            for _ in range(batas + 1)]
    assert kode[:-1] == [422] * batas
    assert kode[-1] == 429
