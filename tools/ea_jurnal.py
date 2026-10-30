#!/usr/bin/env python3
"""Impor deal EA (vendor atau sendiri) ke jurnal paper War Room.

Kenapa file terpisah dari fills.csv: fills.csv mencatat ORDER yang dikirim War Room,
lengkap dengan harga permintaan, slippage terukur, latency, dan retcode. Deal EA yang
dijalankan langsung di terminal tidak punya data permintaan itu. Kalau dicampur,
kolom slippage akan berisi 0 padahal artinya "tidak diketahui" — dan nol akan terbaca
sebagai "eksekusi sempurna". Itu bohong, jadi dipisah.

Pakai:
    ea_jurnal.py --statement galaxius_3y.htm --strategi galaxius --akun 434434290
    ea_jurnal.py --statement X.htm --strategi goldenball --akun 434434290 --tulis
    ea_jurnal.py --statement X.htm --strategi x --akun 1 --push

Tanpa --tulis/--push hanya membaca dan meringkas (dry run).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "core" / "src"))

from warroom_core.rekonsiliasi_deal import baca_statement as _baca_statement  # noqa: E402

KOLOM = [
    "iso", "akun", "strategi", "ticket", "symbol", "side", "volume",
    "open_price", "close_price", "profit", "swap", "commission", "sumber",
]
DEFAULT_CSV = Path.home() / "paper_fills.csv"
SERVER_CSV = "/var/lib/warroom/ea_deals.csv"



def baca_statement(path: Path, strategi: str, akun: str) -> list[dict]:
    """Baca deal penutup dari statement MT5, lalu beri label akun/strategi.

    Parser-nya tinggal di `warroom_core.rekonsiliasi_deal` supaya alat impor dan alat
    rekonsiliasi memakai aturan yang sama (UTF-16, hanya `Direction=out`, net lengkap).
    """
    hasil = []
    for d in _baca_statement(path):
        hasil.append(
            {
                "iso": d["iso"],
                "akun": akun,
                "strategi": strategi,
                "ticket": d["ticket"],
                "symbol": d["symbol"],
                "side": d["side"],
                "volume": d["volume"],
                "open_price": d.get("open_price", ""),
                "close_price": d["close_price"],
                "profit": d["profit"],
                "swap": d["swap"],
                "commission": d["commission"],
                "sumber": "ea_statement",
            }
        )
    return hasil


def sidik(d: dict) -> str:
    """Kunci dedupe: ticket + simbol + volume. Import ulang tidak menggandakan."""
    bahan = f"{d['akun']}|{d['strategi']}|{d['ticket']}|{d.get('symbol','')}|{d['volume']}"
    return hashlib.sha1(bahan.encode()).hexdigest()[:16]


def tulis_lokal(deals: list[dict], path: Path = DEFAULT_CSV) -> tuple[int, int]:
    ada: set[str] = set()
    if path.exists():
        with path.open(newline="") as f:
            for baris in csv.DictReader(f):
                ada.add(sidik({**baris, "volume": float(baris["volume"])}))
    baru = []
    for d in deals:
        s = sidik(d)
        if s in ada:
            continue
        ada.add(s)
        baru.append({**d, "id": s})

    tulis_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", *KOLOM])
        if tulis_header:
            w.writeheader()
        for d in baru:
            w.writerow(d)
    return len(baru), len(deals) - len(baru)


def _satu_batch(baris: list[dict], target: str) -> str:
    """Satu panggilan push untuk sekumpulan baris (argumen harus di bawah ~128 KB)."""
    import base64
    import json
    import os
    from pathlib import Path as _P

    b64 = base64.b64encode(json.dumps(baris).encode()).decode()
    skrip = (
        "import base64, csv, json, os\n"
        f"rows = json.loads(base64.b64decode('{b64}'))\n"
        f"path = '{target}'\n"
        "ada = set()\n"
        "if os.path.exists(path):\n"
        "    with open(path, newline='') as f:\n"
        "        ada = {r['id'] for r in csv.DictReader(f)}\n"
        "baru = [r for r in rows if r['id'] not in ada]\n"
        "mode = 'a' if os.path.exists(path) else 'w'\n"
        "with open(path, mode, newline='') as f:\n"
        f"    w = csv.DictWriter(f, fieldnames=['id', *{KOLOM!r}])\n"
        "    if mode == 'w':\n"
        "        w.writeheader()\n"
        "    for r in baru:\n"
        "        w.writerow(r)\n"
        "print(len(baru), len(rows) - len(baru))\n"
    )
    b64_skrip = base64.b64encode(skrip.encode()).decode()
    perintah = (
        f"echo {b64_skrip} | base64 -d > /tmp/ea_push.py && sudo -n python3 /tmp/ea_push.py"
    )
    jumper = _P.home() / "bin" / "via-jump"
    hasil = subprocess.run(
        [str(jumper), "poly", perintah],
        capture_output=True, text=True, timeout=240,
        env={**os.environ, "HOME": str(_P.home())},
    )
    return (hasil.stdout or hasil.stderr).strip()


def push_server(deals: list[dict], target: str = SERVER_CSV) -> str:
    """Kirim ke server lewat via-jump, dipotong per batch, dedupe per batch."""
    baris = [{**d, "id": sidik(d)} for d in deals]
    if not baris:
        return "tidak ada yang dikirim"

    # Batas aman satu argumen ~128 KB; pakai 24 KB base64 per batch.
    batches: list[list[dict]] = [[]]
    ukuran = 0
    for r in baris:
        perkiraan = len(str(r)) * 4 // 3 + 2
        if ukuran + perkiraan > 24_000 and batches[-1]:
            batches.append([])
            ukuran = 0
        batches[-1].append(r)
        ukuran += perkiraan

    total_baru = total_lewat = 0
    for b in batches:
        keluaran = _satu_batch(b, target)
        try:
            baru, lewat = (int(x) for x in keluaran.split()[:2])
            total_baru += baru
            total_lewat += lewat
        except (ValueError, IndexError):
            return f"gagal pada batch: {keluaran[:200]}"
    return f"push: {total_baru} baru, {total_lewat} dilewati ({len(batches)} batch) -> {target}"


def ringkas(deals: list[dict]) -> str:
    n = len(deals)
    if not n:
        return "tidak ada deal terbaca"
    net = sum(d["profit"] + d["swap"] + d["commission"] for d in deals)
    menang = [d["profit"] for d in deals if d["profit"] > 0]
    kalah = [d["profit"] for d in deals if d["profit"] < 0]
    pf = sum(menang) / abs(sum(kalah)) if kalah else float("inf")
    exp = net / n
    return (
        f"{n} deal | net ${net:,.2f} | PF {pf:.2f} | "
        f"ekspektasi ${exp:.2f}/trade | menang {len(menang)} / kalah {len(kalah)}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Impor deal EA ke jurnal paper")
    ap.add_argument("--statement", required=True, help="laporan/statement MT5 (.htm)")
    ap.add_argument("--strategi", required=True, help="label strategi, mis. galaxius")
    ap.add_argument("--akun", required=True, help="nomor akun MT5")
    ap.add_argument("--tulis", action="store_true", help="tambahkan ke CSV lokal")
    ap.add_argument("--push", action="store_true", help="kirim ke server (butuh sudo)")
    ap.add_argument("--target", default=SERVER_CSV, help="berkas tujuan di server")
    args = ap.parse_args()

    path = Path(args.statement)
    if not path.exists():
        raise SystemExit(f"tidak ada: {path}")

    deals = baca_statement(path, args.strategi, args.akun)
    print(f"{path.name}: {ringkas(deals)}")

    if args.tulis:
        baru, lewat = tulis_lokal(deals)
        print(f"lokal: {baru} baris baru, {lewat} sudah ada -> {DEFAULT_CSV}")
    if args.push:
        print("server:", push_server(deals, args.target))


if __name__ == "__main__":
    main()
