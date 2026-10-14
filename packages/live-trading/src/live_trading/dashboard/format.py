"""Format angka & waktu (dipisah dari dashboard.py)."""

from __future__ import annotations

import datetime as dt
import html
import logging

e = html.escape
log = logging.getLogger("live_trading.dashboard")

log = logging.getLogger(__name__)


e = html.escape


def _persen(x) -> str:
    """Persen atau n/a bila data kosong."""
    return f"{x:.1f}%" if isinstance(x, (int, float)) else "n/a"


def fharga(x) -> str:
    """Format harga adaptif: 2 desimal utk besar, presisi utk kecil."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return e(str(x))
    if v >= 100:
        return f"{v:,.2f}"
    if v >= 1:
        return f"{v:,.4f}"
    return f"{v:,.6f}"


MODEL_POD = "mimo-v2.6-flash"


def _wib() -> str:
    return (dt.datetime.now(dt.UTC) + dt.timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S WIB")


