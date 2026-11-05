"""Tes keamanan `warroom_api.auth_ea` — murni, tanpa DB.

Fokus: **tidak ada bypass autentikasi lewat header IP yang bisa dipalsukan klien.**
Temuan 5 Nov 2026: versi lama menerima `CF-Connecting-IP` apa adanya, sehingga siapa pun
bisa mengirim `CF-Connecting-IP: <ip-azure>` dan lolos ke semua endpoint `/mt5/*`.

Tes ini tidak memerlukan Postgres: ia memanggil `_client_ip` dan `verify_mt5_or_admin`
dengan objek `Request` sintetis (Starlette) saja.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from warroom_api import auth_ea

# ---------------------------------------------------------------------------
# Helper: bangun Request dengan peer tertentu dan header/​cookie apa pun.
# ---------------------------------------------------------------------------


def _req(peer: str, headers: dict[str, str] | None = None, cookies: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "client": (peer, 12345),
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    # Cookie mentah dalam header `cookie` (Starlette membacanya dari sana).
    if cookies:
        jar = "; ".join(f"{k}={v}" for k, v in cookies.items())
        scope["headers"].append((b"cookie", jar.encode()))
    return Request(scope)


# ---------------------------------------------------------------------------
# 1. CELAH: header palsu dari klien tidak boleh mengizinkan akses
# ---------------------------------------------------------------------------


def test_cf_connecting_ip_palsu_dari_klien_langsung_ditolak(monkeypatch):
    """Klien langsung (bukan proxy) mengirim CF-Connecting-IP palsu → tetap ditolak."""
    monkeypatch.delenv("WARROOM_SERVICE_TOKEN", raising=False)
    # peer non-loopback: meniru penyerang yang entah bagaimana mencapai port 8800 langsung.
    r = _req("203.0.113.9", {"CF-Connecting-IP": auth_ea.AZURE_MT5_IP})
    assert auth_ea._client_ip(r) == "203.0.113.9"
    with pytest.raises(HTTPException) as exc:
        import asyncio

        asyncio.run(auth_ea.verify_mt5_or_admin(r, None))
    assert exc.value.status_code == 403


def test_xff_elemen_pertama_palsu_dari_klien_langsung_ditolak(monkeypatch):
    """X-Forwarded-For yang dikirim klien langsung tidak dipercaya."""
    monkeypatch.delenv("WARROOM_SERVICE_TOKEN", raising=False)
    r = _req("203.0.113.9", {"X-Forwarded-For": f"{auth_ea.AZURE_MT5_IP}, 203.0.113.9"})
    assert auth_ea._client_ip(r) == "203.0.113.9"


# ---------------------------------------------------------------------------
# 2. Jalur SAH tetap jalan
# ---------------------------------------------------------------------------


def test_ip_vm2_live_diizinkan_via_x_real_ip(monkeypatch):
    """nginx menulis X-Real-IP; IP VM live 20.212.109.170 (mt5-trader-vm2) harus lolos."""
    monkeypatch.delenv("WARROOM_SERVICE_TOKEN", raising=False)
    r = _req("127.0.0.1", {"X-Real-IP": auth_ea.AZURE_MT5_VM2_IP})
    assert auth_ea._client_ip(r) == auth_ea.AZURE_MT5_VM2_IP
    # Tidak raise = lolos.
    import asyncio

    assert asyncio.run(auth_ea.verify_mt5_or_admin(r, None)) is None


def test_ip_azure_lama_tetap_diizinkan(monkeypatch):
    """Telemetri demo Azure lama (138.91.35.65) tidak boleh putus."""
    monkeypatch.delenv("WARROOM_SERVICE_TOKEN", raising=False)
    r = _req("127.0.0.1", {"X-Real-IP": auth_ea.AZURE_MT5_IP})
    import asyncio

    assert asyncio.run(auth_ea.verify_mt5_or_admin(r, None)) is None


def test_xff_memakai_elemen_terakhir_yang_ditambahkan_nginx(monkeypatch):
    """Bila hanya ada XFF, dipakai elemen TERAKHIR (yang ditambahkan nginx)."""
    monkeypatch.delenv("WARROOM_SERVICE_TOKEN", raising=False)
    # Klien mengirim "ip-azure" di depan; nginx menambahkan IP asli di akhir.
    r = _req("127.0.0.1", {"X-Forwarded-For": f"{auth_ea.AZURE_MT5_IP}, 198.51.100.7"})
    assert auth_ea._client_ip(r) == "198.51.100.7"


def test_cf_connecting_ip_hanya_bila_trust_cf_aktif(monkeypatch):
    """CF-Connecting-IP dihormati hanya bila WARROOM_TRUST_CF=1."""
    monkeypatch.delenv("WARROOM_SERVICE_TOKEN", raising=False)
    monkeypatch.delenv("X-Real-IP", raising=False)
    r = _req("127.0.0.1", {"CF-Connecting-IP": "198.51.100.8"})
    # default: tidak dipercaya → jatuh ke peer loopback
    assert auth_ea._client_ip(r) == "127.0.0.1"
    # aktif: dipercaya
    monkeypatch.setenv("WARROOM_TRUST_CF", "1")
    assert auth_ea._client_ip(r) == "198.51.100.8"


# ---------------------------------------------------------------------------
# 3. Service token & sesi admin
# ---------------------------------------------------------------------------


def test_service_token_sah_lolos(monkeypatch):
    monkeypatch.setenv("WARROOM_SERVICE_TOKEN", "tok-rahasia-uji")
    r = _req("203.0.113.9")  # bahkan dari IP asing
    import asyncio

    assert asyncio.run(auth_ea.verify_mt5_or_admin(r, "tok-rahasia-uji")) is None


def test_service_token_salah_ditolak(monkeypatch):
    monkeypatch.setenv("WARROOM_SERVICE_TOKEN", "tok-rahasia-uji")
    r = _req("203.0.113.9")
    import asyncio

    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth_ea.verify_mt5_or_admin(r, "tok-salah"))
    assert exc.value.status_code == 403


def test_ip_asing_tanpa_token_ditolak(monkeypatch):
    monkeypatch.delenv("WARROOM_SERVICE_TOKEN", raising=False)
    r = _req("127.0.0.1", {"X-Real-IP": "198.51.100.99"})
    import asyncio

    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth_ea.verify_mt5_or_admin(r, None))
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# 4. Allowlist via env (WARROOM_MT5_IPS)
# ---------------------------------------------------------------------------


def test_allowlist_env_menambah_ip(monkeypatch):
    monkeypatch.setenv("WARROOM_MT5_IPS", "198.51.100.50, 198.51.100.51")
    allow = auth_ea._ip_allowlist()
    assert {"198.51.100.50", "198.51.100.51"} <= allow
    assert auth_ea.AZURE_MT5_VM2_IP in allow  # default tetap ada
