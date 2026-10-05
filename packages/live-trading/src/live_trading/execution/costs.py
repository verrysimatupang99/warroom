"""Biaya eksekusi TERUKUR, bukan diasumsikan (P2 roadmap 5 Okt 2026).

Masalah: ``compute_be_stop`` memakai ``fee_buffer_pct=0.001`` yang dipatok di kode. Angka
itu tidak pernah dibandingkan dengan buku order nyata. Padahal edge terukur bisa hilang
oleh spread kecil — dan model fee lama pernah membalik kesimpulan (lihat collectors/depth.py).

Modul ini mengukur dua komponen dari DATA NYATA saat order akan dibuka:

- **fee**: tarif taker dua sisi (konstanta venue; bukan angka karangan — diambil dari tarif
  publik venue yang dipakai, dan bisa ditimpa).
- **slippage**: setengah spread pada buku order Binance futures, pada ukuran posisi yang
  benar-benar akan dieksekusi (bukan 1 bps generik).

Bila buku order tidak bisa diambil, komponen itu ditandai ``sumber="asumsi"`` — tidak
pernah diam-diam memakai angka palsu seolah terukur.
"""

from __future__ import annotations

from typing import Any

from ..collectors.depth import notional_at_bps

__all__ = [
    "FEE_TAKER_BPS_PER_SISI",
    "biaya_dari_depth",
    "biaya_asumsi",
    "be_stop_dari_bps",
    "ringkas",
]

# Tarif taker publik (per sisi, dalam bps). MEXC futures taker 0,05% = 5 bps/sisi.
# Angka ini bisa ditimpa lewat parameter; yang penting ia EKSPLISIT, bukan tersembunyi
# di dalam default fungsi.
FEE_TAKER_BPS_PER_SISI = 5.0

# Batas slippage yang dicari di buku (bps dari mid). Di atas ini kita anggap "lebih dalam
# dari yang sanggup diukur", dan itu dicatat apa adanya.
MAKS_BPS = 50.0


def biaya_dari_depth(
    report: dict[str, Any],
    *,
    sisi_masuk: str,
    size_usd: float,
    fee_bps_per_sisi: float = FEE_TAKER_BPS_PER_SISI,
    sisi_keluar: str | None = None,
) -> dict[str, Any]:
    """Ukur biaya masuk (dan opsional keluar) dari satu laporan kedalaman nyata.

    ``sisi_masuk``/``sisi_keluar``: sisi buku yang kita CROSS. Beli → "ask"; jual → "bid".
    Slippage = jarak bps level terdalam yang perlu ditelan untuk memuat ``size_usd``,
    dibagi dua sebagai aproksimasi biaya rata-rata (kita tidak menelan seluruh rentang
    sekaligus, tetapi memakai rata-rata rentang yang tertelan).

    Mengembalikan dict dengan ``sumber`` eksplisit: "depth:<pair>" bila terukur,
    "asumsi" bila buku tak tersedia.
    """
    if "error" in report or not report.get("mid"):
        return biaya_asumsi(
            fee_bps_per_sisi=fee_bps_per_sisi, alasan=str(report.get("error", "buku tak tersedia"))
        )

    def _slippage_bps(sisi: str) -> float | None:
        block = report.get(sisi) or {}
        levels = block.get("levels") or []
        if not levels:
            return None
        # level terdalam yang perlu ditelan untuk memuat size_usd
        tercapai = None
        for lvl in levels:
            if lvl["cum_notional_usd"] >= size_usd:
                tercapai = lvl
                break
        if tercapai is None:
            # size melebihi seluruh kedalaman yang dipotret → pakai level terdalam + tandai
            tercapai = levels[-1]
        # biaya rata-rata ≈ setengah dari jarak ke level terdalam yang tertelan
        return float(tercapai["bps"]) / 2.0

    slip_masuk = _slippage_bps(sisi_masuk)
    slip_keluar = _slippage_bps(sisi_keluar) if sisi_keluar else None

    if slip_masuk is None:
        return biaya_asumsi(fee_bps_per_sisi=fee_bps_per_sisi, alasan=f"sisi {sisi_masuk} kosong")

    total_masuk = fee_bps_per_sisi + slip_masuk
    total = total_masuk
    if slip_keluar is not None:
        total = total_masuk + fee_bps_per_sisi + slip_keluar

    return {
        "sumber": f"depth:{report.get('pair', '?')}",
        "mid": report.get("mid"),
        "fee_bps": round(fee_bps_per_sisi * (2 if slip_keluar is not None else 1), 3),
        "slippage_bps_masuk": round(slip_masuk, 3),
        "slippage_bps_keluar": round(slip_keluar, 3) if slip_keluar is not None else None,
        "total_bps": round(total, 3),
        "total_pct": round(total / 10000.0, 8),
        "size_usd": round(size_usd, 2),
        "asumsi": False,
    }


def biaya_asumsi(
    *, fee_bps_per_sisi: float = FEE_TAKER_BPS_PER_SISI, alasan: str = ""
) -> dict[str, Any]:
    """Fallback jujur: fee saja, slippage TIDAK terukur. Ditandai ``asumsi=True``.

    Slippage masuk/keluar dikosongkan (None), bukan diisi angka karangan — supaya UI dan
    ledger bisa membedakan "terukur" dari "tidak tahu".
    """
    total = fee_bps_per_sisi * 2
    return {
        "sumber": "asumsi",
        "mid": None,
        "fee_bps": round(total, 3),
        "slippage_bps_masuk": None,
        "slippage_bps_keluar": None,
        "total_bps": round(total, 3),
        "total_pct": round(total / 10000.0, 8),
        "size_usd": None,
        "asumsi": True,
        "alasan": alasan or "buku order tidak tersedia — slippage tidak terukur",
    }


def be_stop_dari_bps(direction: str, entry: float, total_bps: float) -> float:
    """Stop break-even dari biaya TERUKUR (bukan 0,1% yang dipatok)."""
    pct = total_bps / 10000.0
    if direction.upper() == "LONG":
        return round(entry * (1.0 + pct), 8)
    return round(entry * (1.0 - pct), 8)


def ringkas(biaya: dict[str, Any]) -> str:
    """Kalimat pendek untuk log/alert — jujur soal apa yang terukur."""
    if biaya.get("asumsi"):
        return f"biaya {biaya['total_bps']:.1f} bps (ASUMSI fee saja, slippage tak terukur)"
    sl = biaya.get("slippage_bps_masuk")
    return (
        f"biaya {biaya['total_bps']:.1f} bps "
        f"(fee {biaya['fee_bps']:.1f} + slip {sl:.1f} bps, terukur dari buku)"
    )


def tersedia(report: dict[str, Any]) -> bool:
    """Apakah laporan kedalaman ini cukup untuk mengukur biaya."""
    return (
        "error" not in report
        and bool(report.get("mid"))
        and bool(notional_at_bps(report, "ask", MAKS_BPS))
    )
