"""Penjaga drift kontrak: bentuk `SinyalPasar` backend harus sama dengan tipe TS frontend.

KENAPA INI ADA
--------------
`SinyalPasar` adalah kontrak UI yang dipakai Home (satu sinyal terbaik per pasar).
Bentuknya ditulis DUA kali: dataclass Python di `warroom_core.market_signal` dan interface
TypeScript di `apps/web/src/lib/api/types.ts`. Kalau salah satu menambah/menghapus
field tanpa yang lain, TypeScript tetap kompilasi (field hilang jadi `undefined`
saat runtime) dan UI menampilkan `—` tanpa sebab yang terlihat — kelas bug yang
paling sulit dilacak karena tidak ada yang gagal.

Tes ini membandingkan daftar field KEDUANYA dan gagal bila berbeda.
"""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

from warroom_core.market_signal import SinyalPasar

# packages/core/tests/ -> repo root -> apps/web/src/lib/api/types.ts
_ROOT = Path(__file__).resolve().parents[3]
_TYPES = _ROOT / "apps" / "web" / "src" / "lib" / "api" / "types.ts"


def _field_ts(interface: str) -> set[str]:
    """Ambil nama field dari sebuah `export interface <interface> { ... }`."""
    m = re.search(
        rf"export interface {interface} \{{(.*?)\n\}}",
        _TYPES.read_text(encoding="utf-8"),
        re.DOTALL,
    )
    assert m, f"interface {interface} tidak ditemukan di {_TYPES}"
    blok = m.group(1)
    # Baris field: `nama: tipe;` — abaikan komentar dan baris kosong.
    return {
        mm.group(1)
        for mm in re.finditer(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*[?]?\s*:", blok, re.MULTILINE)
    }


def test_field_sinyal_pasar_sama_di_backend_dan_frontend() -> None:
    py = {f.name for f in fields(SinyalPasar)}
    ts = _field_ts("SinyalPasar")
    assert py == ts, (
        "Kontrak SinyalPasar drift antara backend dan frontend.\n"
        f"  Hanya di Python : {sorted(py - ts)}\n"
        f"  Hanya di TS     : {sorted(ts - py)}\n"
        "Perbarui packages/core/src/warroom_core/market_signal.py DAN "
        "apps/web/src/lib/api/types.ts bersamaan."
    )


def test_types_ts_ada() -> None:
    """Gagal cepat bila path berpindah — supaya tes ini tidak 'hijau karena kosong'."""
    assert _TYPES.exists(), f"types.ts tidak ditemukan di {_TYPES}"
