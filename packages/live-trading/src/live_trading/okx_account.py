"""Klien OKX read-only: saldo dan posisi akun, tanpa pernah menulis order.

Kunci dibaca dari environment (`OKX_API_KEY`, `OKX_SECRET_KEY`, `OKX_PASSPHRASE`)
yang disuntik systemd dari `/etc/warroom/okx.env` (600 root). Modul ini tidak
mencetak kunci, signature, atau isi header apa pun.

Dua jebakan nyata yang dikodekan di sini:
- OKX memakai Cloudflare; User-Agent urllib default ditolak (`error code: 1010`).
- Resolusi DNS host ini memilih IPv6, sedangkan whitelist API key hanya IPv4
  (`50110 IP not included`). Permintaan karena itu dipaksa ke IPv4 selama satu
  panggilan, lalu resolver dikembalikan.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import hmac
import json
import os
import socket
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

__all__ = ["OkxError", "ringkas_akun", "ringkas_posisi"]

BASE = "https://www.okx.com"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_resolver_lock = threading.Lock()


class OkxError(RuntimeError):
    """Kegagalan OKX yang harus dilaporkan apa adanya, bukan ditebak."""


@contextlib.contextmanager
def _ipv4_only():
    with _resolver_lock:
        asli = socket.getaddrinfo

        def v4(host, port, family=0, type=0, proto=0, flags=0):  # noqa: A002
            return asli(host, port, socket.AF_INET, type, proto, flags)

        socket.getaddrinfo = v4  # type: ignore[assignment]
        try:
            yield
        finally:
            socket.getaddrinfo = asli  # type: ignore[assignment]


def _env() -> tuple[str, str, str]:
    kunci = os.environ.get("OKX_API_KEY")
    rahasia = os.environ.get("OKX_SECRET_KEY")
    frasa = os.environ.get("OKX_PASSPHRASE")
    if not (kunci and rahasia and frasa):
        raise OkxError(
            "kunci OKX tidak ada di environment worker "
            "(OKX_API_KEY/OKX_SECRET_KEY/OKX_PASSPHRASE)"
        )
    return kunci, rahasia, frasa


def _get(path: str, *, timeout: float = 20.0) -> dict[str, Any]:
    kunci, rahasia, frasa = _env()
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    tanda = base64.b64encode(
        hmac.new(rahasia.encode(), (ts + "GET" + path).encode(), hashlib.sha256).digest()
    ).decode()
    req = urllib.request.Request(
        BASE + path,
        headers={
            "OK-ACCESS-KEY": kunci,
            "OK-ACCESS-SIGN": tanda,
            "OK-ACCESS-TIMESTAMP": ts,
            "OK-ACCESS-PASSPHRASE": frasa,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": UA,
        },
    )
    try:
        with _ipv4_only():
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = json.load(r)
    except urllib.error.HTTPError as e:
        teks = e.read().decode("utf-8", "replace")
        try:
            galat = json.loads(teks)
            pesan = f"{galat.get('code')}: {galat.get('msg')}"
        except json.JSONDecodeError:
            pesan = teks[:200]
        raise OkxError(f"HTTP {e.code} — {pesan}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise OkxError(f"jaringan OKX gagal: {type(e).__name__}: {e}") from e

    if str(body.get("code")) != "0":
        raise OkxError(f"{body.get('code')}: {body.get('msg')}")
    return body


def ringkas_akun() -> dict[str, Any]:
    """Ringkasan saldo: total ekuitas USD, jumlah mata uang, waktu ambil."""
    body = _get("/api/v5/account/balance")
    data = body.get("data") or []
    if not data:
        raise OkxError("OKX mengembalikan data saldo kosong")
    utama = data[0]
    detail = utama.get("details") or []
    return {
        "total_eq_usd": round(float(utama.get("totalEq") or 0.0), 4),
        "mata_uang": len(detail),
        "diambil_at": datetime.now(UTC).isoformat(),
        "sumber": "OKX /account/balance (read-only)",
    }


def ringkas_posisi() -> dict[str, Any]:
    """Ringkasan posisi terbuka: daftar ringkas + total uPnL."""
    body = _get("/api/v5/account/positions")
    baris = body.get("data") or []
    posisi = [
        {
            "instId": p.get("instId"),
            "posSide": p.get("posSide"),
            "pos": p.get("pos"),
            "avgPx": p.get("avgPx"),
            "upl": p.get("upl"),
            "lever": p.get("lever"),
            "mgnMode": p.get("mgnMode"),
        }
        for p in baris
    ]
    upl = 0.0
    for p in posisi:
        try:
            upl += float(p.get("upl") or 0.0)
        except (TypeError, ValueError):
            continue
    return {
        "jumlah": len(posisi),
        "upl_total_usd": round(upl, 4),
        "posisi": posisi,
        "diambil_at": datetime.now(UTC).isoformat(),
        "sumber": "OKX /account/positions (read-only)",
    }
