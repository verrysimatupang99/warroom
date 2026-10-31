"""Analisis sensitivitas hasil backtest terhadap biaya eksekusi.

Membaca laporan HTML MetaTrader 5 apa adanya (tanpa mengubahnya), mengambil
baris deal yang punya kolom profit, lalu menghitung ulang hasil bersih di
beberapa skenario biaya tambahan:

  A. slippage 0,05 harga per fill (0,10 per trade bolak-balik)
  B. komisi 7 dolar per lot per trade
  C. keduanya

Untuk emas (XAUUSD), 1 lot = 100 oz, jadi slippage 0,05 harga = 5 dolar per lot
per fill. Angka ini bukan ramalan; ini batas bawah disiplin.

Biaya dibagi: separuh mengurangi kemenangan, separuh menambah kerugian. Itu
pilihan konservatif supaya PF tidak terlihat lebih baik dari kenyataan.
"""

import re
import sys
from pathlib import Path

BARIS = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
SEL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
TAG = re.compile(r"<[^>]+>")
ANGKA = re.compile(r"-?\d[\d\s.,]*\d|-?\d")


def bersih(sel: str) -> str:
    teks = TAG.sub(" ", sel)
    teks = teks.replace("&nbsp;", " ").replace("&minus;", "-").replace("&#8722;", "-")
    return " ".join(teks.split())


def ke_angka(teks: str) -> float | None:
    """'7 409.37' / '1 234,56' / '-16.12' -> float. None kalau bukan angka."""
    if not teks:
        return None
    t = teks.replace(" ", "").replace("\u00a0", "")
    if "," in t and "." in t:
        t = t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".")
    if not re.fullmatch(r"-?\d+(\.\d+)?", t):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def baca(path: Path):
    """Baca deal dari laporan MT5. Kolom diambil dari baris header, bukan ditebak."""
    mentah = path.read_bytes()
    if mentah[:2] in (b"\xff\xfe", b"\xfe\xff"):
        html = mentah.decode("utf-16", errors="ignore")
    else:
        html = mentah.decode("utf-8", errors="ignore")

    baris = BARIS.findall(html)
    kolom: dict[str, int] | None = None
    deals = []

    for r in baris:
        sel = [bersih(s) for s in SEL.findall(r)]
        if kolom is None:
            if "Profit" in sel and "Volume" in sel and "Time" in sel:
                kolom = {nama: i for i, nama in enumerate(sel)}
            continue
        if len(sel) < len(kolom):
            continue
        try:
            arah = sel[kolom["Direction"]].lower()
            profit = ke_angka(sel[kolom["Profit"]]) or 0.0
        except (KeyError, IndexError):
            continue
        # Hanya deal penutup yang merealisasi profit. Deal 'in' selalu 0.00.
        if arah != "out":
            continue
        volume = ke_angka(sel[kolom["Volume"]]) or 0.0
        deals.append(
            {
                "profit": profit,
                "volume": volume,
                "komisi": abs(ke_angka(sel[kolom["Commission"]]) or 0.0),
                "swap": ke_angka(sel[kolom["Swap"]]) or 0.0,
            }
        )
    return deals


def ringkas(deals, slippage_fill=0.0, komisi_lot=0.0, kontrak=100):
    menang, kalah = [], []
    biaya_total = 0.0
    for d in deals:
        lot = d["volume"] or 0.0
        biaya = slippage_fill * 2 * kontrak * lot + komisi_lot * lot
        biaya_total += biaya
        hasil = d["profit"] - biaya / 2
        (menang if d["profit"] > 0 else kalah).append(hasil)
    bruto_menang = sum(menang)
    bruto_kalah = abs(sum(kalah))
    pf = bruto_menang / bruto_kalah if bruto_kalah else float("inf")
    net = sum(menang) + sum(kalah)
    return {
        "trade": len(deals),
        "net": net,
        "pf": pf,
        "biaya": biaya_total,
        "menang": len(menang),
        "kalah": len(kalah),
    }


def main(paths):
    for path in paths:
        p = Path(path)
        if not p.exists():
            print(f"  {p.name}: tidak ada")
            continue
        deals = baca(p)
        if not deals:
            print(f"  {p.name}: tidak ada baris deal terbaca")
            continue
        lot_rata = [d["volume"] for d in deals if d["volume"]]
        rata_lot = sum(lot_rata) / len(lot_rata) if lot_rata else 0
        print(f"\n{p.name} — {len(deals)} deal, lot rata-rata {rata_lot:.2f}")
        # Rekonsiliasi: net MT5 = profit + komisi + swap. Kalau tidak cocok, parser salah
        # memilih baris (biasanya ikut menghitung deal 'in' yang selalu 0,00).
        profit = sum(d["profit"] for d in deals)
        komisi = sum(d["komisi"] for d in deals)
        swap = sum(d["swap"] for d in deals)
        print(
            f"  rekonsiliasi: profit {profit:,.2f} + komisi {komisi:,.2f} "
            f"+ swap {swap:,.2f} = {profit + komisi + swap:,.2f} (net yang dilaporkan MT5)"
        )
        skenario = [
            ("apa adanya", 0.0, 0.0),
            ("slippage 0,05/fill", 0.05, 0.0),
            ("komisi 7/lot", 0.0, 7.0),
            ("keduanya", 0.05, 7.0),
        ]
        for nama, slip, kom in skenario:
            r = ringkas(deals, slip, kom)
            print(
                f"   {nama:22s} net ${r['net']:>10,.2f}  PF {r['pf']:.2f}  "
                f"biaya ${r['biaya']:>8,.2f}  ({r['menang']} menang / {r['kalah']} kalah)"
            )


if __name__ == "__main__":
    main(sys.argv[1:])
