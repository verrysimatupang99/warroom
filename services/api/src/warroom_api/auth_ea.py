"""Helper autentikasi hybrid untuk integrasi EA MetaTrader 5 (MT5).

Mengamankan endpoint telemetry, deal, fill, dan levels dengan skema hybrid:

1. **Service token**: header ``X-Warroom-Token`` cocok dengan ``WARROOM_SERVICE_TOKEN``.
   Ini jalur utama untuk EA (bridge MQL5 mengirim header ini dari ``InpToken``).
2. **IP asal resmi**: hanya diterima bila koneksi datang dari localhost/proxy tepercaya
   dan IP asli (header yang DI-SET oleh nginx, bukan yang dikirim klien) ada di allowlist.
3. **Cookie sesi admin**: user terautentikasi memakai panel.
4. Sisanya ditolak ``403``.

Keamanan header X-Forwarded-For / X-Real-IP / CF-Connecting-IP
--------------------------------------------------------------
Aplikasi ini hanya listen di ``127.0.0.1:8800`` di belakang nginx (``ops/nginx-warroom.conf``).
Akibatnya, ``request.client.host`` SELALU ``127.0.0.1`` — ia tidak membawa IP penyerang.
IP asli harus diambil dari header yang **ditulis ulang nginx**:

- ``X-Real-IP`` di-set nginx ke ``$remote_addr`` → selalu IP sebenarnya dari koneksi.
- ``X-Forwarded-For`` memakai ``$proxy_add_x_forwarded_for`` → nginx **menambahkan** IP
  klien ke nilai yang dikirim klien. Elemen pertama karena itu BISA PALSU.

Versi lama melihat ``CF-Connecting-IP`` lebih dulu. Header itu **tidak** di-set nginx, jadi
klien mana pun bisa mengirim ``CF-Connecting-IP: <ip-azure>`` dan lolos autentikasi.
Perbaikan ini (5 Nov 2026):

- IP asal **hanya** dipercaya dari proxy tepercaya: kalau ``request.client.host``
  bukan loopback/proxy-tepercaya, seluruh header diabaikan (pakai IP koneksi apa adanya).
- Urutan header: ``X-Real-IP`` (di-set nginx) > ``CF-Connecting-IP`` (hanya bila
  ``WARROOM_TRUST_CF`` aktif) > elemen **terakhir** ``X-Forwarded-For`` (yang ditambahkan
  nginx), bukan yang pertama.
- Allowlist IP kini mencakup VM trader live ``20.212.109.170`` (``mt5-trader-vm2``), selain
  IP Azure lama ``138.91.35.65`` dan loopback. Daftar bisa ditambah via env
  ``WARROOM_MT5_IPS`` (dipisah koma).
"""

from __future__ import annotations

import ipaddress
import os
from pathlib import Path

from fastapi import Header, HTTPException, Request

# IP lama (Azure demo) — dipertahankan agar telemetri demo yang masih berjalan tidak putus.
AZURE_MT5_IP = "138.91.35.65"
# VM trader live aktif: mt5-trader-vm2 (FOREX-MT5-RG), akun cent 36525553.
AZURE_MT5_VM2_IP = "20.212.109.170"
SERVICE_TOKEN_FILE = Path("/etc/warroom/service_token.env")

# Proxy/loopback yang dipercaya untuk menulis ulang header IP.
_TRUSTED_PROXY = {"127.0.0.1", "::1", "localhost"}


def _ip_allowlist() -> set[str]:
    """Allowlist IP asal EA (default + override env ``WARROOM_MT5_IPS``, koma)."""
    base = {AZURE_MT5_IP, AZURE_MT5_VM2_IP}
    extra = os.environ.get("WARROOM_MT5_IPS", "")
    for raw in extra.replace(";", ",").split(","):
        ip = raw.strip()
        if ip:
            base.add(ip)
    return base


def _is_trusted_proxy(host: str) -> bool:
    """True bila koneksi datang dari proxy/loopback tepercaya (header boleh dipercaya)."""
    if not host:
        return False
    if host in _TRUSTED_PROXY:
        return True
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return addr.is_loopback or addr.is_private


def _client_ip(request: Request) -> str:
    """IP klien sebenarnya, atau IP koneksi apa adanya bila header tidak tepercaya.

    Header IP hanya dipercaya bila koneksi berasal dari proxy tepercaya; kalau tidak,
    header diabaikan dan yang dipakai adalah IP koneksi apa adanya. Header palsu milik
    klien (terutama ``CF-Connecting-IP`` dan elemen awal ``X-Forwarded-For``) tidak
    pernah dipakai untuk mengizinkan akses.
    """
    peer = request.client.host if request.client else ""
    if not _is_trusted_proxy(peer):
        # Koneksi langsung: jangan percaya header apa pun.
        return peer

    # X-Real-IP ditulis ulang nginx ke $remote_addr → paling dipercaya.
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    # CF-Connecting-IP hanya bila di belakang Cloudflare (opt-in eksplisit).
    if os.environ.get("WARROOM_TRUST_CF", "0") == "1":
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip:
            return cf_ip.strip()

    # X-Forwarded-For: nginx MENAMBAHKAN IP klien di ujung, jadi ambil elemen TERAKHIR.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[-1].strip()

    return peer


def get_expected_service_token() -> str:
    token = os.environ.get("WARROOM_SERVICE_TOKEN", "")
    if not token and SERVICE_TOKEN_FILE.exists():
        try:
            for line in SERVICE_TOKEN_FILE.read_text().splitlines():
                if line.startswith("WARROOM_SERVICE_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        except Exception:
            pass
    return token


async def verify_mt5_or_admin(
    request: Request,
    x_warroom_token: str | None = Header(None, alias="X-Warroom-Token"),
) -> None:
    # 1. Periksa Service Token (jalur utama EA)
    expected_token = get_expected_service_token()
    if expected_token and x_warroom_token == expected_token:
        return

    # 2. Periksa IP asal (hanya header yang ditulis nginx, dari proxy tepercaya)
    client_ip = _client_ip(request)
    if client_ip and client_ip in _ip_allowlist():
        return

    # 3. Periksa Cookie Sesi Admin
    session_cookie = request.cookies.get("wr_session")
    if session_cookie:
        from warroom_api import auth

        lookup = auth._lookup(session_cookie)
        if lookup:
            return

    raise HTTPException(
        status_code=403,
        detail=(
            "Akses ditolak: Memerlukan X-Warroom-Token valid, IP asal resmi MT5, "
            "atau sesi admin"
        ),
    )
