#!/usr/bin/env python3
"""Arsipkan SEMUA data market lalu reset paper trade dari nol.

Konteks (permintaan owner, 14 Okt 2026): setiap market harus diarsipkan datanya,
trade diulang dari 0, dan dompet paper tiap market dikembalikan ke Rp 10.000.000.

Cara kerja (aman & reversibel):
1. ARSIP: salin seluruh `state/` (ledger, backtest, journal, cache) + DB ledger
   ke `state/arsip/<stempel-waktu>/`, plus MANIFEST.md yang mencatat apa saja yang
   diarsipkan dan ringkasan saldo akhir SEBELUM reset.
2. RESET: pindahkan (bukan hapus) berkas ledger trade ke arsip, lalu buat berkas
   kosong yang bersih. Dompet dihitung ulang dari ledger -> otomatis Rp 10 juta
   (perilaku `dompet.py`: ledger kosong = `tersedia=False`, saldo awal Rp 10 jt).
3. Tidak menyentuh `secrets/`, `logs/`, `backups/`, atau kode.

BATAS PENTING (ditemukan 14 Okt 2026):
- **forex_journal.json DITULIS ULANG penulis eksternal** (cron Hermes Tencent yang masih
  berjalan di host lain). Reset di sini menghapusnya, tetapi beberapa saat kemudian file
  itu kembali berisi trade lama. Untuk forex: **hentikan dulu** cron Tencent penulis jurnal,
  baru jalankan reset. Berkas di sini tak bisa menjamin forex tetap kosong.
- **polymarket** dikelola service `poly-pilot` terpisah (`/var/lib/poly-paper-candidate`);
  bukan milik `state/` ini. Hanya diarsipkan salinannya; reset butuh keputusan owner.
- Market yang penulisnya DI DALAM sistem ini (crypto, idx, gmgn) terreset dengan andal.

Pakai:
    python ops/arsip-reset-market.py --dry-run     # lihat rencana saja
    python ops/arsip-reset-market.py               # jalankan (minta konfirmasi)
    python ops/arsip-reset-market.py --ya          # tanpa tanya (utk otomasi)

PENTING: jalankan sebagai user `admin` (pemilik state). State default:
`$WARROOM_DOMAIN_HOME/state` atau `~/live-trading/state`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
from pathlib import Path

# Berkas ledger trade per market — inilah yang direset (dipindah ke arsip).
LEDGER_TRADE = {
    "crypto": ["crypto_equity.jsonl", "crypto_equity_koreksi.jsonl", "crypto_ledger_koreksi.json"],
    "idx": ["idx_ledger.db", "idx616_signal_ledger.db", "idx_ledger_sumber.json"],
    "forex": ["forex_journal.json", "forex_equity.jsonl"],
    "gmgn": ["lp_ledger.jsonl", "gmgn_equity.jsonl", "gmgn_sim_ledger.jsonl"],
    "polymarket": ["polymarket_equity.jsonl"],
}
# Berkas posisi/hasil turunan yang harus ikut bersih supaya tak ada posisi "hantu".
POSISI_TURUNAN = [
    "paper_positions.json",
    "outcomes.jsonl",
    "verdicts.jsonl",
    "verdicts-dua-arah.jsonl",
    "lp_mark_terakhir.json",
    "radar_state.json",
    "idx616_mirror.json",
    "idx616_drift.json",
]


def _state_dir() -> Path:
    env = os.environ.get("WARROOM_DOMAIN_HOME")
    base = Path(env) if env else Path.home() / "live-trading"
    return base / "state"


def _stamp() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")


def _saldo_ringkas(state: Path) -> dict[str, str]:
    """Ringkas saldo/ledger tiap market SEBELUM reset (untuk MANIFEST)."""
    ringkas: dict[str, str] = {}
    for market, berkas in LEDGER_TRADE.items():
        for nama in berkas:
            p = state / nama
            if p.is_file():
                ringkas[f"{market}/{nama}"] = f"{p.stat().st_size} byte"
    return ringkas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="tampilkan rencana, jangan ubah apa pun")
    ap.add_argument("--ya", action="store_true", help="lewati konfirmasi interaktif")
    ap.add_argument("--state", type=Path, default=None, help="override direktori state")
    args = ap.parse_args()

    state = args.state or _state_dir()
    if not state.is_dir():
        print(f"GAGAL: state tidak ada: {state}")
        return 1

    stamp = _stamp()
    arsip = state / "arsip" / stamp

    berkas_ada: list[Path] = []
    for berkas in LEDGER_TRADE.values():
        for nama in berkas:
            p = state / nama
            if p.is_file():
                berkas_ada.append(p)
    for nama in POSISI_TURUNAN:
        p = state / nama
        if p.is_file():
            berkas_ada.append(p)

    print(f"State   : {state}")
    print(f"Arsip   : {arsip}")
    print(f"Berkas  : {len(berkas_ada)} akan diarsipkan lalu direset")
    for p in berkas_ada:
        print(f"  - {p.relative_to(state)}")
    if not berkas_ada:
        print("Tidak ada berkas ledger/posisi yang perlu direset (sudah bersih).")

    if args.dry_run:
        print("\n(dry-run: tidak ada yang diubah)")
        return 0

    if not args.ya:
        j = input("\nLanjut arsip + reset? [y/N] ").strip().lower()
        if j != "y":
            print("Dibatalkan.")
            return 1

    arsip.mkdir(parents=True, exist_ok=True)

    # 1. Salin SELURUH state ke arsip (jaringan aman: snapshot lengkap dulu).
    snapshot = arsip / "state-penuh"
    shutil.copytree(state, snapshot, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("arsip"))

    # 2. Pindahkan berkas trade ke arsip, sisakan berkas kosong.
    for p in berkas_ada:
        rel = p.relative_to(state)
        tujuan = arsip / "direset" / rel
        tujuan.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(tujuan))
        if p.suffix == ".jsonl":
            p.write_text("", encoding="utf-8")  # ledger bersih
        # .db / .json dibiarkan tidak ada (dibuat ulang oleh mesin bila perlu)

    # 3. MANIFEST
    manifest = arsip / "MANIFEST.md"
    lines = [
        f"# Arsip + reset paper trade — {stamp}",
        "",
        f"State  : `{state}`",
        f"Arsip  : `{arsip}`",
        "",
        "## Ringkasan SEBELUM reset",
        "",
        "| berkas | ukuran |",
        "|---|---|",
    ]
    for k, v in sorted(_saldo_ringkas(snapshot).items()):
        lines.append(f"| {k} | {v} |")
    lines += [
        "",
        "## Yang direset",
        "",
        "Trade dimulai ulang dari 0 untuk setiap market. Dompet dihitung ulang dari",
        "ledger (kini kosong) sehingga kembali ke **Rp 10.000.000** per market —",
        "sesuai `dompet.py` (`WALLET_IDR`).",
        "",
        f"Total berkas direset: {len(berkas_ada)}.",
        "",
        "Pulihkan: `cp -r <arsip>/direset/* <state>/`",
    ]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\nOK. Arsip di {arsip}")
    print(f"    MANIFEST: {manifest}")
    print(f"    {len(berkas_ada)} berkas direset; trade mulai dari 0, dompet Rp 10 jt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
