"""Kolektor data per market."""

from __future__ import annotations

import httpx

UA = "Mozilla/5.0 (compatible; warroom-live-trading/0.1)"


def make_client(timeout: float = 15.0, **kwargs: object) -> httpx.Client:
    """Client HTTP bersama: UA konsisten + redirect diikuti.

    Semua kolektor menerima ``client`` opsional supaya bisa diuji tanpa jaringan
    (httpx.MockTransport).
    """
    headers = {"User-Agent": UA, "Accept": "application/json"}
    return httpx.Client(timeout=timeout, follow_redirects=True, headers=headers, **kwargs)  # type: ignore[arg-type]
