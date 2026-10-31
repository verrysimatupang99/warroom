"""Status forward test: berapa trade tertutup, hari berjalan, dan jejak yang hilang.

Sumber kebenaran tetap berkas yang ditulis proses nyata:

- `deals.csv`  — deal tertutup yang dilaporkan EA (`POST /mt5/deal`), satu baris per posisi.
- `fills.csv`  — order masuk yang dicatat War Room, lengkap dengan slippage/latensi.

Modul ini hanya MEMBACA. Tidak ada angka yang dikarang: berkas tidak ada → nol dengan
alasan `ada_berkas: false`, bukan tebakan. Trade dihitung dari `ticket` unik supaya
pengiriman ulang EA (idempoten di API) tidak menggandakan hitungan.
"""

from __future__ import annotations

import csv
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from warroom_core.deal_koreksi import baca_koreksi, terapkan

DEALS_DEFAULT = Path("/var/lib/warroom/deals.csv")
FILLS_DEFAULT = Path("/var/lib/warroom/fills.csv")

# DoD yang disepakati owner: 20 trade tertutup ATAU 30 hari, mana yang lebih dulu.
TARGET_TRADE = 20
JENDELA_HARI = 30
MULAI_DEFAULT = date(2026, 10, 30)

_TANGGAL = re.compile(r"(\d{4})[.\-](\d{2})[.\-](\d{2})")


def baca_csv_detail(path: Path) -> tuple[list[dict[str, str]], str]:
    """Baca CSV dan kembalikan status jujur: ada | tidak-ada | tidak-izin | rusak.

    `tidak-izin` berbeda dari `tidak-ada`: berkas ada tetapi proses tidak boleh
    membacanya. Pemanggil tidak boleh melaporkan nol untuk kasus itu.
    """
    try:
        path.stat()
    except FileNotFoundError:
        return [], "tidak-ada"
    except PermissionError:
        return [], "tidak-izin"
    except OSError:
        return [], "rusak"
    try:
        with path.open(newline="", encoding="utf-8", errors="replace") as f:
            return list(csv.DictReader(f)), "ada"
    except PermissionError:
        return [], "tidak-izin"
    except OSError:
        return [], "rusak"

def baca_csv(path: Path) -> tuple[list[dict[str, str]], bool]:
    """Kompatibilitas: (baris, apakah berkas terbaca). Gunakan baca_csv_detail untuk status."""
    baris, status = baca_csv_detail(path)
    return baris, status == "ada"


def _angka(nilai: Any, bawaan: float = 0.0) -> float:
    try:
        return float(str(nilai).replace(",", "."))
    except (TypeError, ValueError):
        return bawaan


def _net(deal: dict[str, str]) -> float:
    """Net = profit + swap + commission. Kolom `net` dipakai bila ada."""
    if deal.get("net") not in (None, ""):
        return round(_angka(deal.get("net")), 2)
    return round(
        _angka(deal.get("profit")) + _angka(deal.get("swap")) + _angka(deal.get("commission")),
        2,
    )


def tanggal_deal(deal: dict[str, str]) -> date | None:
    """Tanggal tutup deal. `close_time` EA berbentuk `2026.10.30 08:15:00`; fallback `iso`/`ts`."""
    for kolom in ("close_time", "iso", "open_time"):
        cocok = _TANGGAL.search(str(deal.get(kolom) or ""))
        if cocok:
            try:
                return date(int(cocok.group(1)), int(cocok.group(2)), int(cocok.group(3)))
            except ValueError:
                continue
    return None


def _identitas_deal(deal: dict[str, str]) -> str:
    """Kunci deal: `position` (id posisi) lebih stabil daripada tiket deal keluar.

    Fills mencatat tiket order masuk; di MT5 tiket posisi umumnya sama dengan tiket
    order pembuka. Memakai `position` membuat pencocokan fill↔deal masuk akal; bila
    kosong, pakai tiket deal itu sendiri.
    """
    posisi = str(deal.get("position") or "").strip()
    return posisi or str(deal.get("ticket") or "").strip()


def ringkas(
    *,
    deals_path: Path = DEALS_DEFAULT,
    fills_path: Path = FILLS_DEFAULT,
    koreksi_path: Path | None = None,
    mulai: date = MULAI_DEFAULT,
    hari_ini: date | None = None,
    target: int = TARGET_TRADE,
    jendela_hari: int = JENDELA_HARI,
) -> dict[str, Any]:
    """Hitung status DoD forward test. Semua angka berasal dari berkas yang dibaca."""
    hari_ini = hari_ini or datetime.now(UTC).date()
    deals, deals_status = baca_csv_detail(deals_path)
    if koreksi_path is not None and deals_status == "ada":
        deals = terapkan(deals, baca_koreksi(koreksi_path))
    fills, fills_status = baca_csv_detail(fills_path)
    deals_ada = deals_status == "ada"
    fills_ada = fills_status == "ada"
    deals_tidak_izin = deals_status == "tidak-izin"
    fills_tidak_izin = fills_status == "tidak-izin"

    unik: dict[str, dict[str, str]] = {}
    for d in deals:
        tiket = str(d.get("ticket") or "").strip()
        if tiket:
            unik[tiket] = d
    deal_rows = list(unik.values())

    net = None if deals_tidak_izin else round(sum(_net(d) for d in deal_rows), 2)
    menang = None if deals_tidak_izin else sum(1 for d in deal_rows if _net(d) > 0)
    kalah = None if deals_tidak_izin else sum(1 for d in deal_rows if _net(d) < 0)

    hari_berjalan = max(0, (hari_ini - mulai).days + 1)
    batas = mulai + timedelta(days=max(0, jendela_hari - 1))
    sisa_hari = max(0, (batas - hari_ini).days + (1 if hari_ini <= batas else 0))

    deal_hari_ini = [] if deals_tidak_izin else [d for d in deal_rows if tanggal_deal(d) == hari_ini]

    fill_tiket = {str(f.get("ticket") or "").strip() for f in fills if str(f.get("ticket") or "").strip()}
    deal_ident = {_identitas_deal(d) for d in deal_rows if _identitas_deal(d)}
    deal_tiket = {str(d.get("ticket") or "").strip() for d in deal_rows if str(d.get("ticket") or "").strip()}

    # Fill yang belum punya deal = posisi masih terbuka ATAU deal tidak pernah dilaporkan.
    # Dua kemungkinan itu TIDAK dibedakan di sini — statusnya "belum ada deal", bukan "hilang".
    if deals_tidak_izin or fills_tidak_izin:
        fill_belum_deal = None
        deal_tanpa_fill = None
    else:
        fill_belum_deal = sorted(fill_tiket - deal_ident - deal_tiket)
        # Deal tanpa fill = dibuka di luar War Room (manual/EA lain) atau fill tidak tercatat.
        deal_tanpa_fill = sorted(deal_ident - fill_tiket)

    jumlah_trade: int | None = None if deals_tidak_izin else len(deal_rows)
    if jumlah_trade is None:
        status = "tidak-izin"
        catatan = (
            f"{deals_path} ada tetapi tidak bisa dibaca proses ini; jalankan sebagai "
            "root atau lewat unit yang berhak. Angka trade sengaja n/a, bukan nol."
        )
        laju = None
    elif jumlah_trade >= target:
        status = "selesai"
    elif hari_berjalan > jendela_hari:
        status = "lewat-batas"
    else:
        status = "berjalan"

    laju = (
        None
        if jumlah_trade is None
        else (round(jumlah_trade / hari_berjalan, 3) if hari_berjalan else 0.0)
    )
    if status == "berjalan":
        perlu = max(0, target - jumlah_trade)
        if perlu == 0:
            catatan = "target trade tercapai"
        elif laju > 0:
            butuh_hari = int(-(-perlu // laju))  # ceil
            catatan = f"kurang {perlu} trade; laju {laju}/hari → sekitar {butuh_hari} hari lagi"
        else:
            catatan = f"kurang {perlu} trade; belum ada trade tertutup untuk mengukur laju"
    elif status == "selesai":
        catatan = f"target {target} trade tercapai pada hari ke-{hari_berjalan}"
    else:
        catatan = f"jendela {jendela_hari} hari habis dengan {jumlah_trade}/{target} trade"

    return {
        "sumber": {
            "deals": str(deals_path),
            "deals_ada": deals_ada,
            "deals_status": deals_status,
            "fills": str(fills_path),
            "fills_ada": fills_ada,
            "fills_status": fills_status,
        },
        "mulai": mulai.isoformat(),
        "batas": batas.isoformat(),
        "hari_ini": hari_ini.isoformat(),
        "hari_berjalan": hari_berjalan,
        "sisa_hari": sisa_hari,
        "target_trade": target,
        "jendela_hari": jendela_hari,
        "trade_tertutup": jumlah_trade,
        "deal_hari_ini": len(deal_hari_ini),
        "net_usd": net,
        "menang": menang,
        "kalah": kalah,
        "seri": None if jumlah_trade is None else jumlah_trade - (menang or 0) - (kalah or 0),
        "laju_trade_per_hari": laju,
        "fill_belum_deal": None if fill_belum_deal is None else len(fill_belum_deal),
        "fill_belum_deal_tiket": [] if fill_belum_deal is None else fill_belum_deal[:20],
        "deal_tanpa_fill": None if deal_tanpa_fill is None else len(deal_tanpa_fill),
        "deal_tanpa_fill_tiket": [] if deal_tanpa_fill is None else deal_tanpa_fill[:20],
        "status": status,
        "catatan": catatan,
    }


def teks(hasil: dict[str, Any]) -> str:
    """Format CLI yang bisa ditempel ke laporan sprint."""
    sumber = hasil["sumber"]
    baris = [
        f"Forward test — hari {hasil['hari_berjalan']}/{hasil['jendela_hari']} "
        f"(mulai {hasil['mulai']}, batas {hasil['batas']})",
        f"Trade tertutup : {_n(hasil['trade_tertutup'])}/{hasil['target_trade']}"
        f"  (hari ini {_n(hasil['deal_hari_ini'])})",
        f"Net tertutup   : {_usd(hasil['net_usd'])}"
        f"  (menang {_n(hasil['menang'])}, kalah {_n(hasil['kalah'])}, seri {_n(hasil['seri'])})",
        f"Fill belum deal: {_n(hasil['fill_belum_deal'])}",
        f"Deal tanpa fill: {_n(hasil['deal_tanpa_fill'])}",
        f"Status         : {hasil['status']} — {hasil['catatan']}",
    ]
    if sumber.get("deals_status") == "tidak-izin":
        baris.append(f"Catatan        : {sumber['deals']} tidak izin dibaca (jalankan sebagai root)")
    elif not sumber["deals_ada"]:
        baris.append(f"Catatan        : {sumber['deals']} belum ada (belum ada deal tertutup)")
    if sumber.get("fills_status") == "tidak-izin":
        baris.append(f"Catatan        : {sumber['fills']} tidak izin dibaca (jalankan sebagai root)")
    elif not sumber["fills_ada"]:
        baris.append(f"Catatan        : {sumber['fills']} belum ada (belum ada order masuk)")
    return "\n".join(baris)

def _n(nilai: Any) -> str:
    return "n/a" if nilai is None else str(nilai)

def _usd(nilai: Any) -> str:
    return "n/a" if nilai is None else f"${nilai:.2f}"
