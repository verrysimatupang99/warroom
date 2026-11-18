#!/usr/bin/env python3
"""Inventaris terminal MT5 (Wine) + deteksi drift EA.

Baca-saja. Tidak menyalin, menghapus, atau mengubah berkas apa pun.

Yang dilaporkan:
  * daftar terminal MT5 yang ditemukan di prefix Wine
  * jumlah EA total vs EA "custom" (MTRB / GOLD Reaper / pola nama tertentu)
  * md5 + ukuran + mtime per EA custom
  * drift: basename sama tapi md5 beda antar terminal
  * .mq5 tanpa .ex5 (belum dikompilasi) dan .ex5 tanpa .mq5 (tidak bisa di-rebuild)
  * terminal yang benar-benar dipakai unit systemd vs yang hanya sisa

Pemakaian:
    python3 ops/mt5-inventory.py                # tabel manusia
    python3 ops/mt5-inventory.py --json         # keluaran JSON
    python3 ops/mt5-inventory.py --custom-only  # sembunyikan EA stok

Contoh:
    python3 ops/mt5-inventory.py --json > /tmp/mt5.json
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Pola nama EA milik sendiri. Bisa ditambah lewat --match.
DEFAULT_CUSTOM_PATTERNS = (
    r"mtrb",
    r"gold[_\s-]?reaper",
)

WINE_GLOBS = (
    ".wine*",
)

SKIP_DIR_NAMES = {".git", "node_modules", "__pycache__", "history", "logs"}


@dataclass
class EaFile:
    name: str
    path: str
    kind: str  # "ex5" | "mq5" | "mqh" | "set"
    md5: str | None
    size: int
    mtime: str


@dataclass
class Terminal:
    name: str
    prefix: str
    experts_dir: str
    presets_dir: str | None
    ea_total: int = 0
    custom: list[EaFile] = field(default_factory=list)
    used_by_units: list[str] = field(default_factory=list)
    launchers: list[str] = field(default_factory=list)
    wine_bin: str | None = None


def md5_of(path: Path, chunk: int = 1 << 20) -> str | None:
    h = hashlib.md5()
    try:
        with path.open("rb") as fh:
            while True:
                b = fh.read(chunk)
                if not b:
                    break
                h.update(b)
    except OSError:
        return None
    return h.hexdigest()


def human_time(path: Path) -> str:
    try:
        return datetime.datetime.fromtimestamp(path.stat().st_mtime).strftime(
            "%Y-%m-%d %H:%M"
        )
    except OSError:
        return "?"


def is_custom(name: str, patterns: tuple[str, ...]) -> bool:
    low = name.lower()
    return any(re.search(p, low) for p in patterns)


def find_terminals(home: Path) -> list[Terminal]:
    """Temukan setiap direktori MQL5/Experts di semua prefix Wine."""
    out: list[Terminal] = []
    seen: set[str] = set()

    for prefix in sorted(home.glob("*")):
        if not prefix.is_dir():
            continue
        if not any(prefix.match(g) for g in WINE_GLOBS):
            continue

        program_files = prefix / "drive_c" / "Program Files"
        if not program_files.is_dir():
            continue

        for term_dir in sorted(program_files.iterdir()):
            experts = term_dir / "MQL5" / "Experts"
            if not experts.is_dir():
                continue
            key = str(experts.resolve())
            if key in seen:
                continue
            seen.add(key)

            presets = term_dir / "MQL5" / "Presets"
            out.append(
                Terminal(
                    name=term_dir.name,
                    prefix=prefix.name,
                    experts_dir=str(experts),
                    presets_dir=str(presets) if presets.is_dir() else None,
                )
            )
    return out


def scan_terminal(term: Terminal, patterns: tuple[str, ...]) -> None:
    experts = Path(term.experts_dir)
    total = 0
    for path in experts.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        suffix = path.suffix.lower()
        if suffix not in {".ex5", ".mq5", ".mqh", ".set"}:
            continue
        if suffix in {".ex5", ".mq5"}:
            total += 1
        if not is_custom(path.name, patterns):
            # EA stok tetap dihitung di ea_total, tapi tidak dirinci
            continue
        term.custom.append(
            EaFile(
                name=path.name,
                path=str(path),
                kind=suffix.lstrip("."),
                md5=md5_of(path),
                size=path.stat().st_size if path.exists() else 0,
                mtime=human_time(path),
            )
        )
    term.ea_total = total


def find_units_using(term: Terminal) -> list[str]:
    """Cari unit systemd yang (langsung atau lewat skrip launcher) menyebut terminal ini."""
    needles = {
        term.name,
        term.name.replace(" ", ""),
        term.name.lower().replace(" ", "-"),
        term.experts_dir.replace("/MQL5/Experts", ""),
    }
    needles = {n for n in needles if n}

    found: list[str] = []
    unit_dir = Path("/etc/systemd/system")
    if not unit_dir.is_dir():
        return found

    for unit in sorted(unit_dir.rglob("*.service")):
        try:
            text = unit.read_text(errors="ignore")
        except OSError:
            continue

        haystack = text + " " + " ".join(_follow_execstart_scripts(text))
        if any(n in haystack for n in needles):
            found.append(unit.name)
    return found


EXEC_LINE = re.compile(r"^ExecStart=\s*(.+)$", re.MULTILINE)
PATH_TOKEN = re.compile(r"(/[\w./+-]+\.(?:sh|bash|py))")
WINE_TOKEN = re.compile(r"(/[^\s\"']*bin/wine[^\s\"']*)")


def _follow_script_chain(unit_text: str, depth: int = 3) -> dict[str, str]:
    """Peta path -> isi skrip yang dirujuk ExecStart, ditelusuri sampai `depth` lapis."""
    found: dict[str, str] = {}
    queue = list(PATH_TOKEN.findall(unit_text))
    for _ in range(depth):
        nxt: list[str] = []
        for candidate in queue:
            if candidate in found:
                continue
            p = Path(candidate)
            if not p.is_file():
                continue
            try:
                body = p.read_text(errors="ignore")
            except OSError:
                continue
            found[candidate] = body
            nxt.extend(PATH_TOKEN.findall(body))
        if not nxt:
            break
        queue = nxt
    return found


def _follow_execstart_scripts(unit_text: str, depth: int = 3) -> list[str]:
    """Isi semua skrip dalam rantai ExecStart (untuk pencocokan nama terminal)."""
    return list(_follow_script_chain(unit_text, depth).values())


def find_units_using(term: Terminal) -> list[str]:
    """Cari unit systemd yang (langsung atau lewat rantai launcher) menyebut terminal ini."""
    needles = _needles(term)
    found: list[str] = []
    unit_dir = Path("/etc/systemd/system")
    if not unit_dir.is_dir():
        return found

    for unit in sorted(unit_dir.rglob("*.service")):
        try:
            text = unit.read_text(errors="ignore")
        except OSError:
            continue
        haystack = text + " " + " ".join(_follow_execstart_scripts(text))
        if any(n in haystack for n in needles):
            found.append(unit.name)
    return found


def _needles(term: Terminal) -> set[str]:
    install = term.experts_dir.replace("/MQL5/Experts", "")
    return {n for n in (term.name, install) if n}


def find_launchers(term: Terminal) -> None:
    """Isi term.launchers: skrip dalam rantai ExecStart yang benar-benar menyebut terminal ini."""
    needles = _needles(term)
    unit_dir = Path("/etc/systemd/system")
    chain: dict[str, str] = {}

    if unit_dir.is_dir():
        for unit in unit_dir.rglob("*.service"):
            try:
                text = unit.read_text(errors="ignore")
            except OSError:
                continue
            chain.update(_follow_script_chain(text))

    for script, body in sorted(chain.items()):
        mentions_terminal = any(n in body for n in needles)
        launches_wine = ("wine" in body and "terminal64" in body) or "WINEPREFIX" in body
        if mentions_terminal and launches_wine:
            term.launchers.append(script)
            m = WINE_TOKEN.search(body)
            if m and not term.wine_bin:
                term.wine_bin = m.group(1)


def detect_drift(terminals: list[Terminal]) -> dict[str, list[dict]]:
    """Basename sama, md5 beda antar terminal."""
    by_name: dict[str, list[dict]] = {}
    for term in terminals:
        for ea in term.custom:
            by_name.setdefault(ea.name, []).append(
                {
                    "terminal": term.name,
                    "prefix": term.prefix,
                    "md5": ea.md5,
                    "size": ea.size,
                    "path": ea.path,
                    "mtime": ea.mtime,
                }
            )

    drift = {}
    for name, entries in by_name.items():
        digests = {e["md5"] for e in entries}
        if len(entries) > 1 and len(digests) > 1:
            drift[name] = entries
    return drift


def detect_source_gaps(terminals: list[Terminal]) -> dict[str, list[str]]:
    """EA custom yang .ex5 tanpa .mq5 (tak bisa di-rebuild) atau .mq5 tanpa .ex5."""
    gaps: dict[str, list[str]] = {"ex5_without_source": [], "mq5_without_binary": []}
    for term in terminals:
        stems = {}
        for ea in term.custom:
            stem = Path(ea.name).stem
            stems.setdefault(stem, set()).add(ea.kind)
        for stem, kinds in stems.items():
            if "ex5" in kinds and "mq5" not in kinds:
                gaps["ex5_without_source"].append(f"{term.name}: {stem}.ex5")
            if "mq5" in kinds and "ex5" not in kinds:
                gaps["mq5_without_binary"].append(f"{term.name}: {stem}.mq5")
    return gaps


def render_text(terminals: list[Terminal], drift, gaps) -> str:
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("INVENTARIS MT5 / EA")
    lines.append("=" * 78)

    lines.append("")
    lines.append(f"{'Terminal':<34} {'Prefix':<13} {'EA':>4} {'Custom':>6}  Unit systemd")
    lines.append("-" * 78)
    for t in terminals:
        units = ",".join(t.used_by_units) if t.used_by_units else "-"
        lines.append(
            f"{t.name[:34]:<34} {t.prefix[:13]:<13} {t.ea_total:>4} {len(t.custom):>6}  {units[:28]}"
        )

    lines.append("")
    lines.append("EA CUSTOM (terperinci)")
    lines.append("-" * 78)
    for t in terminals:
        if not t.custom:
            continue
        lines.append(f"[{t.name}] {t.prefix}")
        for ea in sorted(t.custom, key=lambda e: (e.kind, e.name)):
            lines.append(
                f"  {ea.kind:<4} {(ea.md5 or '?')[:10]}  {ea.size:>9}  {ea.mtime}  {ea.name}"
            )
        if t.presets_dir:
            sets = sorted(Path(t.presets_dir).glob("*.set"))
            if sets:
                lines.append(f"  preset: {', '.join(p.name for p in sets)}")
        lines.append("")

    lines.append("DRIFT (nama sama, md5 beda)")
    lines.append("-" * 78)
    if not drift:
        lines.append("  tidak ada")
    else:
        for name, entries in sorted(drift.items()):
            lines.append(f"  {name}:")
            for e in entries:
                lines.append(
                    f"    {(e['md5'] or '?')[:10]}  {e['size']:>9}  {e['terminal']}  ({e['prefix']})"
                )

    lines.append("")
    lines.append("SUMBER TIDAK LENGKAP")
    lines.append("-" * 78)
    if not gaps["ex5_without_source"] and not gaps["mq5_without_binary"]:
        lines.append("  tidak ada")
    for item in gaps["ex5_without_source"]:
        lines.append(f"  .ex5 tanpa .mq5 (tidak bisa di-rebuild): {item}")
    for item in gaps["mq5_without_binary"]:
        lines.append(f"  .mq5 tanpa .ex5 (belum dikompilasi):     {item}")

    lines.append("")
    lines.append("LAUNCHER & RESIKO /tmp")
    lines.append("-" * 78)
    ephemeral = []
    for t in terminals:
        if not t.launchers:
            continue
        lines.append(f"  [{t.name}]")
        for s in t.launchers:
            flag = ""
            if s.startswith("/tmp/"):
                flag = "  <-- RENTAN: dihapus systemd-tmpfiles (>30 hari)"
                ephemeral.append(s)
            lines.append(f"    {s}{flag}")
        if t.wine_bin:
            lines.append(f"    wine: {t.wine_bin}")
    if not any(t.launchers for t in terminals):
        lines.append("  tidak ada launcher terdeteksi")
    if ephemeral:
        lines.append("")
        lines.append("  PERINGATAN: launcher di /tmp tidak permanen. systemd-tmpfiles")
        lines.append("  membersihkan /tmp yang lebih tua dari 30 hari, sehingga MT5 gagal")
        lines.append("  start otomatis setelah reboot berikutnya. Pindahkan ke /home/admin/opt/mt5/run/.")

    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Inventaris terminal MT5 + drift EA (baca-saja)")
    ap.add_argument("--home", default=str(Path.home()), help="home dir pemilik prefix Wine")
    ap.add_argument("--json", action="store_true", help="keluaran JSON")
    ap.add_argument(
        "--match",
        action="append",
        default=None,
        help="pola regex tambahan untuk EA custom (boleh berulang)",
    )
    args = ap.parse_args(argv)

    patterns = list(DEFAULT_CUSTOM_PATTERNS)
    if args.match:
        patterns.extend(args.match)
    ptrn = tuple(patterns)

    home = Path(args.home)
    terminals = find_terminals(home)
    if not terminals:
        print("Tidak ada terminal MT5 ditemukan.", file=sys.stderr)
        return 1

    for term in terminals:
        scan_terminal(term, ptrn)
        term.used_by_units = find_units_using(term)
        find_launchers(term)

    drift = detect_drift(terminals)
    gaps = detect_source_gaps(terminals)

    if args.json:
        payload = {
            "generated_at": human_time(Path(__file__)),
            "host": os.uname().nodename,
            "terminals": [
                {
                    "name": t.name,
                    "prefix": t.prefix,
                    "experts_dir": t.experts_dir,
                    "presets_dir": t.presets_dir,
                    "ea_total": t.ea_total,
                    "custom_count": len(t.custom),
                    "used_by_units": t.used_by_units,
                    "launchers": t.launchers,
                    "wine_bin": t.wine_bin,
                    "custom": [asdict(e) for e in t.custom],
                }
                for t in terminals
            ],
            "drift": drift,
            "gaps": gaps,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(render_text(terminals, drift, gaps))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
