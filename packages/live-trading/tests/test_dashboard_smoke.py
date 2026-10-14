"""Smoke test: import relatif di panel dashboard harus benar.

Kenapa ada: PR #21 memecah `dashboard.py` -> paket `dashboard/`. Import relatif di
`panels.py` (`from .collectors`) TIDAK diperbarui ke `..collectors`, sehingga 27
import rusak. Semua tertelan `except Exception` -> bagian dashboard kosong senyap
("error": "ModuleNotFoundError: ...") sementara snapshot tetap "sukses".
Tidak ada tes yang menyentuh jalur ini, jadi bug itu lolos CI berhari-hari.

Tes ini menyelesaikan setiap modul relatif yang diimpor `panels.py` — cepat (tanpa
jaringan) dan deterministik. Salah satu relatif salah -> tes gagal seketika.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

PANELS = (
    Path(__file__).resolve().parents[1]
    / "src" / "live_trading" / "dashboard" / "panels.py"
)
PAKET = "live_trading.dashboard"


def _modul_relatif_dipakai() -> set[str]:
    """Modul absolut dari tiap `ImportFrom` ber-level yang mengimpor MODUL.

    Catatan: `from .format import e` mengimpor MODUL `live_trading.dashboard.format`
    (bukan simbol `e`). Yang diuji adalah modulnya — salah level = ModuleNotFoundError.
    """
    tree = ast.parse(PANELS.read_text(encoding="utf-8"))
    bagian = PAKET.split(".")
    modul: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.level:
            continue
        naik = node.level - 1  # level 1='.', 2='..'
        basis = ".".join(bagian[: len(bagian) - naik])
        if node.module:
            modul.add(f"{basis}.{node.module}")
    return modul


def test_semua_import_relatif_panels_bisa_diselesaikan() -> None:
    """Setiap MODUL yang diimpor relatif oleh panels.py harus bisa di-import."""
    modul = _modul_relatif_dipakai()
    assert modul, "tak ada import relatif terdeteksi — parser rusak?"

    gagal: dict[str, str] = {}
    for nama in sorted(modul):
        try:
            importlib.import_module(nama)
        except ModuleNotFoundError as exc:
            # Jaringan/kredensial BUKAN urusan tes ini; hanya modul yang benar-benar
            # tak ada (salah relatif) yang dihitung gagal.
            if exc.name and nama.startswith(exc.name.split(".")[0]):
                gagal[nama] = str(exc)
            else:
                gagal[nama] = str(exc)
        except Exception:
            pass  # butuh DB/kredensial saat import: bukan urusan tes ini

    assert not gagal, f"import relatif rusak di panels.py: {gagal}"
