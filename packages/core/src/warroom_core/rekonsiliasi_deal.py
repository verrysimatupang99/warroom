"""Rekonsiliasi deal statement MT5 dengan `deals.csv` milik War Room.

Dua sumber yang harus cocok:

- **Statement/report MT5** — kebenaran broker. Hanya baris `Direction=out` yang
  merealisasi profit; baris `in` selalu 0,00 dan harus diabaikan.
- **`deals.csv`** — yang dilaporkan EA ke `POST /mt5/deal`. Satu baris per deal keluar.

Yang dibandingkan adalah **net** (profit + swap + commission), bukan profit saja.
Selisih di atas toleransi (default $0,01) dianggap temuan, bukan pembulatan.

Laporan MT5 adalah UTF-16LE dengan BOM; dibaca sebagai UTF-8 akan menghasilkan nol
baris dan mudah disalahartikan sebagai "EA tidak trading". Karena itu parser memilih
decoder dari BOM dan mengembalikan daftar kosong hanya bila memang tidak ada baris
`out` yang terbaca — pemanggil wajib membedakan "kosong" dari "cocok".
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

BARIS = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
SEL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
TAG = re.compile(r"<[^>]+>")

TOLERANSI_DEFAULT = 0.01


def bersih(sel: str) -> str:
    """Teks sel HTML tanpa tag/entitas yang mengganggu angka."""
    teks = (
        TAG.sub(" ", sel)
        .replace("&nbsp;", " ")
        .replace("&minus;", "-")
        .replace("&#8722;", "-")
        .replace("&#8209;", "-")
    )
    return " ".join(teks.split())


def ke_angka(nilai: Any) -> float | None:
    """Angka gaya MT5: `1 234,56` (EU) atau `1,234.56` (US). Bukan angka → None."""
    if isinstance(nilai, (int, float)):
        return float(nilai)
    if nilai is None:
        return None
    t = str(nilai).replace(" ", "").replace("\u00a0", "").strip()
    if not t:
        return None
    if "," in t and "." in t:
        t = t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _tanggal(teks: str) -> date | None:
    cocok = re.search(r"(\d{4})[.\-](\d{2})[.\-](\d{2})", str(teks or ""))
    if not cocok:
        return None
    try:
        return date(int(cocok.group(1)), int(cocok.group(2)), int(cocok.group(3)))
    except ValueError:
        return None


def baca_statement(path: Path) -> list[dict[str, Any]]:
    """Baca deal penutup (`out`) dari statement MT5. Tidak mengubah berkas."""
    mentah = path.read_bytes()
    html = (
        mentah.decode("utf-16", errors="ignore")
        if mentah[:2] in (b"\xff\xfe", b"\xfe\xff")
        else mentah.decode("utf-8", errors="ignore")
    )

    kolom: dict[str, int] | None = None
    deals: list[dict[str, Any]] = []
    for baris in BARIS.findall(html):
        sel = [bersih(s) for s in SEL.findall(baris)]
        if kolom is None:
            if "Profit" in sel and "Volume" in sel and "Time" in sel:
                kolom = {nama: i for i, nama in enumerate(sel)}
            continue
        if len(sel) < len(kolom):
            continue
        try:
            if sel[kolom["Direction"]].lower() != "out":
                continue
            ticket = sel[kolom["Deal"]].strip()
            if not ticket:
                continue
            profit = ke_angka(sel[kolom["Profit"]]) or 0.0
            swap = ke_angka(sel[kolom["Swap"]]) or 0.0
            commission = ke_angka(sel[kolom["Commission"]]) or 0.0
            deals.append(
                {
                    "iso": sel[kolom["Time"]].replace(".", "-", 2),
                    "ticket": ticket,
                    "symbol": sel[kolom["Symbol"]],
                    "side": sel[kolom["Type"]].upper(),
                    "volume": ke_angka(sel[kolom["Volume"]]) or 0.0,
                    "open_price": "",
                    "close_price": ke_angka(sel[kolom["Price"]]) or "",
                    "profit": round(profit, 2),
                    "swap": round(swap, 2),
                    "commission": round(commission, 2),
                    "net": round(profit + swap + commission, 2),
                    "sumber": "mt5_statement",
                }
            )
        except (KeyError, IndexError):
            continue
    return deals


def _net(baris: dict[str, Any], *, pakai_kolom_net: bool) -> float:
    if pakai_kolom_net and str(baris.get("net") or "").strip():
        return round(ke_angka(baris.get("net")) or 0.0, 2)
    return round(
        (ke_angka(baris.get("profit")) or 0.0)
        + (ke_angka(baris.get("swap")) or 0.0)
        + (ke_angka(baris.get("commission")) or 0.0),
        2,
    )


def _indeks(rows: list[dict[str, Any]], *, pakai_kolom_net: bool) -> tuple[dict[str, dict], list[str]]:
    idx: dict[str, dict] = {}
    duplikat: list[str] = []
    for r in rows:
        tiket = str(r.get("ticket") or "").strip()
        if not tiket:
            continue
        if tiket in idx:
            duplikat.append(tiket)
            continue
        idx[tiket] = r
    return idx, sorted(set(duplikat))


def _dalam_periode(baris: dict[str, Any], sejak: date | None, sampai: date | None) -> bool:
    if sejak is None and sampai is None:
        return True
    tgl = _tanggal(str(baris.get("close_time") or baris.get("iso") or ""))
    if tgl is None:
        # Tanggal tak terbaca jangan dibuang diam-diam; biar muncul sebagai temuan.
        return True
    if sejak is not None and tgl < sejak:
        return False
    return not (sampai is not None and tgl > sampai)


def bandingkan(
    statement: list[dict[str, Any]],
    deals: list[dict[str, Any]],
    *,
    toleransi: float = TOLERANSI_DEFAULT,
    sejak: date | None = None,
    sampai: date | None = None,
) -> dict[str, Any]:
    """Cocokkan statement vs deals.csv per tiket deal; selisih net di atas toleransi = temuan."""
    st_rows = [r for r in statement if _dalam_periode(r, sejak, sampai)]
    cs_rows = [r for r in deals if _dalam_periode(r, sejak, sampai)]
    st, dup_st = _indeks(st_rows, pakai_kolom_net=True)
    cs, dup_cs = _indeks(cs_rows, pakai_kolom_net=True)

    cocok: list[str] = []
    selisih: list[dict[str, Any]] = []
    for tiket in sorted(st.keys() & cs.keys()):
        net_st = _net(st[tiket], pakai_kolom_net=True)
        net_cs = _net(cs[tiket], pakai_kolom_net=True)
        diff = round(net_cs - net_st, 2)
        if abs(diff) > toleransi:
            selisih.append(
                {
                    "ticket": tiket,
                    "symbol": st[tiket].get("symbol") or cs[tiket].get("symbol") or "",
                    "net_statement": net_st,
                    "net_deals": net_cs,
                    "selisih": diff,
                }
            )
        else:
            cocok.append(tiket)

    def _ringkas(tiket: str, sumber: dict[str, dict], *, pakai_net: bool) -> dict[str, Any]:
        r = sumber[tiket]
        return {
            "ticket": tiket,
            "iso": r.get("close_time") or r.get("iso") or "",
            "symbol": r.get("symbol") or "",
            "net": _net(r, pakai_kolom_net=pakai_net),
        }

    hanya_st = [_ringkas(t, st, pakai_net=True) for t in sorted(st.keys() - cs.keys())]
    hanya_cs = [_ringkas(t, cs, pakai_net=True) for t in sorted(cs.keys() - st.keys())]

    # Hanya tiket yang lolos filter yang dijumlahkan; angka tidak mencampur periode lain.
    net_st_total = round(sum(_net(r, pakai_kolom_net=True) for r in st.values()), 2)
    net_cs_total = round(sum(_net(r, pakai_kolom_net=True) for r in cs.values()), 2)

    status = "cocok"
    if selisih or hanya_st or hanya_cs or dup_st or dup_cs:
        status = "selisih"

    return {
        "sumber": "statement MT5 vs deals.csv",
        "periode": {
            "sejak": sejak.isoformat() if sejak else None,
            "sampai": sampai.isoformat() if sampai else None,
        },
        "toleransi_usd": toleransi,
        "n_statement": len(st),
        "n_deals": len(cs),
        "net_statement_usd": net_st_total,
        "net_deals_usd": net_cs_total,
        "cocok": len(cocok),
        "selisih": selisih,
        "hanya_statement": hanya_st,
        "hanya_deals": hanya_cs,
        "duplikat_statement": dup_st,
        "duplikat_deals": dup_cs,
        "status": status,
    }


def teks(hasil: dict[str, Any]) -> str:
    baris = [
        "Rekonsiliasi statement MT5 vs deals.csv",
        f"Statement : {hasil['n_statement']} deal (net ${hasil['net_statement_usd']:.2f})",
        f"deals.csv : {hasil['n_deals']} deal (net ${hasil['net_deals_usd']:.2f})",
        f"Cocok     : {hasil['cocok']}",
        f"Selisih   : {len(hasil['selisih'])}",
        f"Hanya statement : {len(hasil['hanya_statement'])}",
        f"Hanya deals.csv : {len(hasil['hanya_deals'])}",
        f"Duplikat  : statement {len(hasil['duplikat_statement'])}, "
        f"deals {len(hasil['duplikat_deals'])}",
        f"Status    : {hasil['status'].upper()}",
    ]
    for s in hasil["selisih"][:10]:
        baris.append(
            f"  SELISIH ticket={s['ticket']} {s['symbol']} "
            f"statement={s['net_statement']:.2f} deals={s['net_deals']:.2f} "
            f"diff={s['selisih']:+.2f}"
        )
    for kunci, label in (("hanya_statement", "statement"), ("hanya_deals", "deals")):
        for r in hasil[kunci][:10]:
            baris.append(f"  HANYA {label} ticket={r['ticket']} {r['symbol']} net={r['net']:.2f}")
    if hasil["duplikat_statement"] or hasil["duplikat_deals"]:
        baris.append(
            "  DUPLIKAT: "
            f"statement={','.join(hasil['duplikat_statement'][:5])} "
            f"deals={','.join(hasil['duplikat_deals'][:5])}"
        )
    if hasil["hanya_statement"] or hasil["hanya_deals"]:
        baris.append("  Catatan: bila periode statement berbeda, pakai --sejak/--sampai.")
    return "\n".join(baris)
