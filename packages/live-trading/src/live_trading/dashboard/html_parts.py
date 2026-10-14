"""Helper HTML murni — dipakai lintas modul dashboard (memutus siklus impor).

Dulu `_card/_lencana/_sumber/_arti/_e` tinggal di modul fragmen, tetapi panel
data juga memakainya — setelah pemecahan itu jadi impor melingkar. Di sini jadi
lapisan dasar tanpa dependensi ke panels/fragments/server.
"""

from __future__ import annotations

import html

_e = html.escape


def _card(title: str, body: str) -> str:
    import re as _re

    _tanpa_badge = _re.sub(r"<span[^>]*>.*?</span>", "", title)
    _polos = _re.sub(r"<[^>]+>", "", _tanpa_badge)
    _slug = _re.sub(r"[^a-z0-9]+", "-", _polos.lower()).strip("-")
    _judul = title if "<" in title else html.escape(title)
    return f"<section id='{_slug}'><h2>{_judul}</h2>{body}</section>"


def _lencana(jenis: str, teks: str) -> str:
    return f"<span class='badge {jenis}'>{_e(teks)}</span>"


def _sumber(teks: str) -> str:
    return f"<p class='src'>sumber: {_e(teks)}</p>"


def _arti(teks: str) -> str:
    return f"<p class='arti'><b>Artinya:</b> {teks}</p>"
