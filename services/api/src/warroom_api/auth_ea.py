"""Helper autentikasi hybrid untuk integrasi EA MetaTrader 5 (MT5).

Mengamankan endpoint telemetry dan order levels dengan skema hybrid:
1. Mengizinkan IP Azure VM resmi (138.91.35.65) atau IP localhost/Tailscale.
2. Mengizinkan header X-Warroom-Token yang cocok dengan WARROOM_SERVICE_TOKEN.
3. Mengizinkan user terautentikasi (cookie sesi admin).
4. Menolak semua permintaan lain dengan HTTP 403 Forbidden.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import Header, HTTPException, Request

AZURE_MT5_IP = "138.91.35.65"
SERVICE_TOKEN_FILE = Path("/etc/warroom/service_token.env")


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
    # 1. Periksa Service Token
    expected_token = get_expected_service_token()
    if expected_token and x_warroom_token == expected_token:
        return

    # 2. Periksa IP Asli (Cloudflare CF-Connecting-IP atau X-Forwarded-For)
    xff = request.headers.get("x-forwarded-for")
    client_ip = (
        request.headers.get("cf-connecting-ip")
        or request.headers.get("x-real-ip")
        or (xff.split(",")[0].strip() if xff else None)
        or (request.client.host if request.client else "")
    )

    if client_ip in (AZURE_MT5_IP, "127.0.0.1", "::1", "100.126.10.74"):
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
        detail="Akses ditolak: Memerlukan X-Warroom-Token valid atau IP asal resmi MT5 Azure VM",
    )
