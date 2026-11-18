"""Penjaga batas: platform TIDAK boleh bergantung pada isi strategi.

Aturan yang dijaga (lihat docs/PLATFORM-VS-STRATEGI.md):

1. Kode platform (`services/`, `v1/api/`, `apps/web/src`) tidak boleh mengimpor
   mesin strategi (`warroom_core.strategi_config`).
2. Kode platform tidak boleh merujuk berkas spec strategi (`strategi/**.yaml`).
   Platform hanya boleh melihat `v1.*` (venue/feed/strategy/signal), bukan manifest.
3. Setiap manifest strategi harus sah: `id` == nama folder, YAML terbaca,
   kunci wajib ada, dan enum market/status dikenali.

Kenapa: sebelum 2026-11-18 hal ini tidak dijaga, sehingga strategi forex hanya
hidup sebagai baris DB + EA liar di prefix Wine, dan tidak ada cara memisahkan
"platform rusak" dari "strategi rusak".

Test ini murni statis (baca berkas + AST). Tidak menyentuh DB atau jaringan.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]

# Direktori yang merupakan PLATFORM (bukan strategi).
PLATFORM_DIRS = (
    ROOT / "services",
    ROOT / "v1" / "api",
    ROOT / "apps" / "web" / "src",
)

SKIP_PARTS = {
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "build",
    "dist",
    ".git",
    ".svelte-kit",
}

PY_SUFFIXES = {".py"}
JS_SUFFIXES = {".js", ".mjs", ".cjs", ".ts", ".svelte"}

# Modul mesin strategi yang tidak boleh diimpor platform.
TERLARANG_MODUL = ("strategi_config", "warroom_core.strategi_config")

# Rujukan berkas spec strategi, mis. "strategi/crypto/x/manifest.yaml".
POLA_SPEC = re.compile(r"strategi/[A-Za-z0-9_./-]+\.yaml")

MARKET_DIKENAL = {"forex", "crypto", "memecoin", "openmarket", "prediction", "equity"}
STATUS_DIKENAL = {"live", "paper", "draft", "dihentikan", "retired"}
EXECUTOR_DIKENAL = {"python-engine", "mt5-ea"}


def _iter_files(roots, suffixes):
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in suffixes:
                continue
            if SKIP_PARTS & set(path.parts):
                continue
            yield path


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _python_imports(path: Path) -> set[str]:
    """Semua nama modul yang diimpor berkas ini (best-effort, abaikan syntax error)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return set()

    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mods.add(node.module)
                for alias in node.names:
                    mods.add(f"{node.module}.{alias.name}")
    return mods


def test_platform_tidak_mengimpor_mesin_strategi():
    pelanggaran = []
    for path in _iter_files(PLATFORM_DIRS, PY_SUFFIXES):
        for modul in _python_imports(path):
            if any(t in modul for t in TERLARANG_MODUL):
                pelanggaran.append(f"{_rel(path)} mengimpor {modul}")

    assert not pelanggaran, (
        "Kode platform mengimpor mesin strategi — batas platform/strategi bocor:\n  "
        + "\n  ".join(sorted(pelanggaran))
        + "\n\nPlatform hanya boleh membaca v1.* (venue/feed/strategy/signal)."
    )


def test_platform_tidak_merujuk_berkas_spec_strategi():
    pelanggaran = []
    for path in _iter_files(PLATFORM_DIRS, PY_SUFFIXES | JS_SUFFIXES):
        try:
            body = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in POLA_SPEC.findall(body):
            pelanggaran.append(f"{_rel(path)}: {match}")

    assert not pelanggaran, (
        "Kode platform merujuk berkas spec strategi:\n  "
        + "\n  ".join(sorted(pelanggaran))
        + "\n\nPindahkan pembacaan manifest ke ops/ (mis. ops/strategi-sync.py)."
    )


def _manifests() -> list[Path]:
    base = ROOT / "strategi"
    if not base.is_dir():
        return []
    return sorted(p for p in base.glob("*/*/manifest.yaml") if not p.parent.parent.name.startswith("_"))


def test_manifest_strategi_ada():
    found = _manifests()
    assert found, "Tidak ada manifest di strategi/*/*/manifest.yaml"


@pytest.mark.parametrize("path", _manifests(), ids=lambda p: p.parent.name)
def test_manifest_sah(path: Path):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{_rel(path)}: manifest harus mapping"

    for kunci in ("id", "nama", "market", "executor", "status"):
        assert data.get(kunci), f"{_rel(path)}: kunci wajib hilang: {kunci}"

    assert data["id"] == path.parent.name, (
        f"{_rel(path)}: id '{data['id']}' tidak sama dengan nama folder '{path.parent.name}'"
    )
    assert data["market"] in MARKET_DIKENAL, f"{_rel(path)}: market tidak dikenal: {data['market']}"
    assert data["status"] in STATUS_DIKENAL, f"{_rel(path)}: status tidak dikenal: {data['status']}"
    assert data["executor"] in EXECUTOR_DIKENAL, (
        f"{_rel(path)}: executor tidak dikenal: {data['executor']}"
    )


def test_strategi_mt5_ea_punya_blok_ea():
    for path in _manifests():
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data.get("executor") != "mt5-ea":
            continue
        ea = data.get("ea")
        assert isinstance(ea, dict), f"{_rel(path)}: executor mt5-ea wajib punya blok ea"
        for kunci in ("file", "terminal", "magic", "tf"):
            assert ea.get(kunci) is not None, f"{_rel(path)}: ea.{kunci} wajib diisi"


def test_nama_lama_masih_bisa_dibaca():
    """Kompatibilitas: path lama strategi/<id>.yaml harus tetap resolve."""
    lama = ROOT / "strategi"
    for nama in (
        "breakout_donchian_crypto.yaml",
        "rsi_meanrevert_crypto.yaml",
        "memecoin_momentum.yaml",
        "openmarket_breakout.yaml",
    ):
        p = lama / nama
        assert p.exists(), f"path lama hilang: strategi/{nama} (CLI lama akan pecah)"
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert isinstance(data, dict) and data.get("id")
