#!/usr/bin/env python3
"""Deploy sumber EA dari repo ke terminal MT5 — idempoten, dry-run default.

Sumber kebenaran ada di repo:

    strategi/forex/<id>/ea/*        (.mq5, .mqh, .ex5)
    strategi/forex/<id>/preset/*    (.set)

Tujuan ditentukan oleh `ea.terminal` di manifest strategi.

Perilaku:
  * Membandingkan sha256; hanya menyalin berkas yang BERBEDA.
  * `--dry-run` adalah bawaan; menulis hanya bila `--apply` diberikan.
  * MENOLAK menyalin ke folder `Free Robots` (EA stok broker) atau path di luar
    MQL5/Experts & MQL5/Presets terminal.
  * Melaporkan `.ex5` yang lebih tua dari `.mq5` (perlu kompilasi ulang di
    MetaEditor) — tidak mengompilasi sendiri.
  * Tidak pernah attach EA ke chart; itu tetap tindakan manual di terminal.

Pemakaian:
    python3 ops/ea-deploy.py                       # rencana untuk semua target
    python3 ops/ea-deploy.py --target ex-live      # satu target saja
    python3 ops/ea-deploy.py --target ex-live --apply
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FOREX_DIR = ROOT / "strategi" / "forex"
HOME = Path.home()

# nama target CLI -> nama folder terminal
TARGET_ALIAS = {
    "ex-live": "MT5-EX-Live",
    "ex-demo": "MT5-EX-Demo",
}

# Folder yang tidak boleh disentuh.
DILARANG = ("free robots",)

EKSTENSI_EA = {".mq5", ".mqh", ".ex5"}
EKSTENSI_PRESET = {".set"}


@dataclass
class Rencana:
    strategi: str
    terminal: str
    sumber: Path
    tujuan: Path
    jenis: str  # "EA" | "preset"
    aksi: str  # "sama" | "salin" | "baru"


def sha256(path: Path) -> str | None:
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for blok in iter(lambda: fh.read(1 << 20), b""):
                h.update(blok)
    except OSError:
        return None
    return h.hexdigest()


def peta_terminal() -> dict[str, Path]:
    """nama terminal -> folder MQL5 terminal (induk Experts/Presets)."""
    out: dict[str, Path] = {}
    for prefix in sorted(HOME.glob(".wine*")):
        prog = prefix / "drive_c" / "Program Files"
        if not prog.is_dir():
            continue
        for term in sorted(prog.iterdir()):
            mql5 = term / "MQL5"
            if (mql5 / "Experts").is_dir():
                out.setdefault(term.name, mql5)
    return out


def cek_jalur_aman(tujuan: Path) -> None:
    bagian = [p.lower() for p in tujuan.parts]
    if any(d in bagian for d in DILARANG):
        raise SystemExit(f"REFUSED: tujuan ada di folder EA stok: {tujuan}")
    if "mql5" not in bagian:
        raise SystemExit(f"REFUSED: tujuan di luar MQL5: {tujuan}")


def muat_manifest(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: manifest tidak valid")
    return data


def susun_rencana(target_filter: str | None) -> tuple[list[Rencana], list[str]]:
    terminal_peta = peta_terminal()
    rencana: list[Rencana] = []
    catatan: list[str] = []

    for man_path in sorted(FOREX_DIR.glob("*/manifest.yaml")):
        data = muat_manifest(man_path)
        if data.get("executor") != "mt5-ea":
            continue

        ea = data.get("ea") or {}
        nama_terminal = str(ea.get("terminal") or "")
        if not nama_terminal:
            catatan.append(f"{man_path.parent.name}: manifest tanpa ea.terminal, dilewati")
            continue

        if target_filter and TARGET_ALIAS.get(target_filter) != nama_terminal:
            continue

        mql5 = terminal_peta.get(nama_terminal)
        if mql5 is None:
            catatan.append(
                f"{man_path.parent.name}: terminal '{nama_terminal}' tidak ditemukan di prefix Wine"
            )
            continue

        basis = man_path.parent
        for jenis, sub, tujuan_sub, ekst in (
            ("EA", "ea", "Experts", EKSTENSI_EA),
            ("preset", "preset", "Presets", EKSTENSI_PRESET),
        ):
            sumber_dir = basis / sub
            if not sumber_dir.is_dir():
                continue
            for src in sorted(sumber_dir.iterdir()):
                if not src.is_file() or src.suffix.lower() not in ekst:
                    continue
                dst = mql5 / tujuan_sub / src.name
                cek_jalur_aman(dst)
                if not dst.exists():
                    aksi = "baru"
                elif sha256(src) == sha256(dst):
                    aksi = "sama"
                else:
                    aksi = "salin"
                rencana.append(
                    Rencana(
                        strategi=man_path.parent.name,
                        terminal=nama_terminal,
                        sumber=src,
                        tujuan=dst,
                        jenis=jenis,
                        aksi=aksi,
                    )
                )

    # deteksi .ex5 lebih tua dari .mq5 (perlu kompilasi)
    for man_path in sorted(FOREX_DIR.glob("*/manifest.yaml")):
        ea_dir = man_path.parent / "ea"
        if not ea_dir.is_dir():
            continue
        for mq5 in ea_dir.glob("*.mq5"):
            ex5 = mq5.with_suffix(".ex5")
            if ex5.exists() and ex5.stat().st_mtime < mq5.stat().st_mtime:
                catatan.append(
                    f"{man_path.parent.name}: {ex5.name} lebih tua dari {mq5.name} "
                    f"— perlu kompilasi ulang di MetaEditor"
                )
    return rencana, catatan


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Deploy EA repo -> terminal MT5 (idempoten)")
    ap.add_argument("--target", choices=sorted(TARGET_ALIAS), help="batasi ke satu terminal")
    ap.add_argument("--apply", action="store_true", help="benar-benar menyalin (bawaan dry-run)")
    ap.add_argument("--dry-run", action="store_true", help="hanya tampilkan rencana (bawaan)")
    args = ap.parse_args(argv)

    dry = not args.apply
    rencana, catatan = susun_rencana(args.target)

    if not rencana:
        print("Tidak ada berkas EA/preset yang ditemukan untuk dideploy.", file=sys.stderr)
        for c in catatan:
            print(f"  ! {c}", file=sys.stderr)
        return 2

    print("=" * 92)
    print("DEPLOY EA" + (" (DRY-RUN)" if dry else " (APPLY)"))
    print("=" * 92)
    print()
    print(f"{'strategi':<20} {'terminal':<15} {'jenis':<7} {'aksi':<6} berkas")
    print("-" * 92)
    for r in rencana:
        print(f"{r.strategi[:20]:<20} {r.terminal[:15]:<15} {r.jenis:<7} {r.aksi:<6} {r.sumber.name}")

    perlu = [r for r in rencana if r.aksi != "sama"]

    if not dry:
        for r in perlu:
            r.tujuan.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(r.sumber, r.tujuan)
        print()
        print(f"Disalin: {len(perlu)} berkas.")

    if catatan:
        print()
        print("CATATAN:")
        for c in catatan:
            print(f"  ! {c}")

    print()
    if dry:
        if perlu:
            print(f"Rencana: {len(perlu)} berkas perlu disalin. Jalankan dengan --apply.")
        else:
            print("Semua berkas sudah identik (sha256 sama). Tidak ada yang perlu dilakukan.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
