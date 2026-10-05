"""BSJP — Beli Sore Jual Pagi: uji edge overnight IDX (5 Okt 2026).

Apa ini: strategi menahan posisi semalam — beli di sore (menjelang tutup) dan jual di pagi
(awal sesi berikutnya), menangkap lompatan harga antar-sesi. Di IDX, ini menarik karena
banyak aksi harga terjadi di pembukaan.

Batas jujur yang dikodekan di sini (jangan dihapus tanpa menggantinya dengan yang lebih baik):

1. **Data yang ada BUKAN bar harian.** Yang tersedia: `idx_tv` (snapshot TradingView — RSI,
   EMA, ATR, perubahan hari ini) dan `arjum/screener` (bucket + win-rate event + potensi).
   Keduanya **tidak** memuat harga buka/tutup harian per tanggal. Karena itu edge overnight
   tidak bisa dihitung dari data ini — hanya bisa **diperkirakan**, dan perkiraan ditandai
   sebagai perkiraan.
2. **Win-rate Arjum adalah win-rate EVENT mereka**, bukan hasil BSJP. Menamainya "edge BSJP"
   akan mengklaim sesuatu yang tidak diukur. Karena itu dipakai sebagai proksi dan diberi
   label eksplisit.
3. **Dua mode.** ``jendela`` (data cukup: harga buka/tutup per tanggal) menghitung edge
   nyata; ``proksi`` (data sekarang) memberi peringkat kandidat + menyebut batasnya.
   Mode dilaporkan di keluaran supaya UI tidak bisa menampilkannya tanpa konteks.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

__all__ = ["KandidatBSJP", "PeringkatBSJP", "susun_peringkat"]


@dataclass
class KandidatBSJP:
    """Satu kandidat BSJP dengan alasan yang bisa diperiksa."""

    ticker: str
    nama: str = ""
    bucket: str = ""
    skor: int | None = None          # 0-100 terukur; None = tidak ada angka
    wr_event: float | None = None    # win-rate event Arjum (BUKAN edge BSJP)
    potensi: float | None = None     # potensi % dari screener
    drawdown: float | None = None
    rsi14: float | None = None
    ema_state: str | None = None
    atr: float | None = None
    volume: float | None = None
    catatan: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PeringkatBSJP:
    mode: str                        # "jendela" (edge nyata) | "proksi" (data belum cukup)
    ada: bool
    kandidat: list[KandidatBSJP] = field(default_factory=list)
    edge_rata_pct: float | None = None   # HANYA terisi di mode "jendela"
    n_sampel: int = 0
    alasan: str = ""
    catatan_kejujuran: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "ada": self.ada,
            "kandidat": [k.to_dict() for k in self.kandidat],
            "edge_rata_pct": self.edge_rata_pct,
            "n_sampel": self.n_sampel,
            "alasan": self.alasan,
            "catatan_kejujuran": self.catatan_kejujuran,
        }


# Ambang skor: RSI terlalu tinggi = risiko beli di puncak (BSJP beli sore, jadi RSI tinggi
# justru bahaya); EMA naik = tren mendukung tahan semalam.
_RSI_IDEAL_MAKS = 70.0
_RSI_BAHAYA = 80.0


def _skor_kandidat(baris: dict[str, Any], tv: dict[str, Any] | None) -> tuple[int | None, list[str]]:
    """Skor 0-100 dari komponen yang BENAR-BENAR ada. Tidak mengarang komponen."""
    catatan: list[str] = []
    bagian: list[float] = []

    potensi = baris.get("potensi") if "potensi" in baris else baris.get("potential")
    if isinstance(potensi, (int, float)):
        # potensi 0-20% dipetakan 0-40 poin (di atas 20% tidak menambah kepercayaan)
        bagian.append(min(40.0, max(0.0, float(potensi) / 20.0 * 40.0)))

    wr = baris.get("wr_event")
    if isinstance(wr, (int, float)):
        # WR 50-75% dipetakan 0-30 poin
        bagian.append(min(30.0, max(0.0, (float(wr) - 50.0) / 25.0 * 30.0)))

    dd = baris.get("drawdown")
    if isinstance(dd, (int, float)):
        # drawdown -5% ke atas (kecil) = 30 poin; -20% = 0 poin
        bagian.append(min(30.0, max(0.0, (float(dd) + 20.0) / 15.0 * 30.0)))

    if not bagian:
        return None, catatan

    skor = round(sum(bagian))

    if tv:
        rsi = tv.get("rsi14")
        if isinstance(rsi, (int, float)):
            if rsi >= _RSI_BAHAYA:
                skor = max(0, skor - 25)
                catatan.append(f"RSI {rsi:.1f} ≥ {_RSI_BAHAYA:.0f} — risiko beli di puncak")
            elif rsi > _RSI_IDEAL_MAKS:
                skor = max(0, skor - 10)
                catatan.append(f"RSI {rsi:.1f} di atas {_RSI_IDEAL_MAKS:.0f} — kurang ideal untuk tahan semalam")
        if tv.get("ema_state") == "naik":
            catatan.append("EMA naik — tren mendukung tahan semalam")
        elif tv.get("ema_state"):
            skor = max(0, skor - 10)
            catatan.append("EMA turun — melawan arah tahan semalam")
    else:
        catatan.append("belum ada data TradingView untuk ticker ini (skor dari screener saja)")

    return skor, catatan


def susun_peringkat(
    screener_rows: list[dict[str, Any]] | None,
    tv_rows: list[dict[str, Any]] | None,
    *,
    edge_jendela_pct: float | None = None,
    n_jendela: int = 0,
) -> PeringkatBSJP:
    """Susun peringkat kandidat BSJP.

    ``edge_jendela_pct`` hanya boleh diisi bila ada perhitungan harga buka/tutup per tanggal.
    Selama ``None``, mode = "proksi" dan itu dinyatakan terang-terangan.
    """
    tv_per_ticker = {str(r.get("ticker")): r for r in (tv_rows or []) if isinstance(r, dict)}
    kandidat: list[KandidatBSJP] = []

    for r in screener_rows or []:
        if not isinstance(r, dict):
            continue
        ticker = str(r.get("stock_code") or r.get("ticker") or "")
        if not ticker:
            continue
        tv = tv_per_ticker.get(ticker)
        skor, catatan = _skor_kandidat(r, tv)
        kandidat.append(
            KandidatBSJP(
                ticker=ticker,
                nama=str(r.get("stock_name") or ""),
                bucket=str(r.get("bucket") or ""),
                skor=skor,
                wr_event=r.get("wr_event") if isinstance(r.get("wr_event"), (int, float)) else None,
                potensi=r.get("potensi") if isinstance(r.get("potensi"), (int, float))
                else (r.get("potential") if isinstance(r.get("potential"), (int, float)) else None),
                drawdown=r.get("drawdown") if isinstance(r.get("drawdown"), (int, float)) else None,
                rsi14=(tv or {}).get("rsi14"),
                ema_state=(tv or {}).get("ema_state"),
                atr=(tv or {}).get("atr"),
                volume=(tv or {}).get("volume"),
                catatan=catatan,
            )
        )

    # Ticker yang ada di TradingView tapi belum masuk screener tetap ditampilkan: itu
    # kandidat yang belum dinilai Arjum, bukan kandidat yang tidak ada.
    sudah = {k.ticker for k in kandidat}
    for ticker, tv in tv_per_ticker.items():
        if ticker in sudah:
            continue
        kandidat.append(
            KandidatBSJP(
                ticker=ticker,
                skor=None,
                rsi14=tv.get("rsi14"),
                ema_state=tv.get("ema_state"),
                atr=tv.get("atr"),
                volume=tv.get("volume"),
                catatan=["belum masuk screener Arjum — belum dinilai; ditampilkan apa adanya"],
            )
        )

    kandidat.sort(key=lambda k: (k.skor is not None, k.skor or 0), reverse=True)
    ada = bool(kandidat)

    if edge_jendela_pct is not None:
        mode = "jendela"
        catatan = (
            f"Edge dihitung dari {n_jendela} jendela buka→tutup nyata. "
            "Ini angka terukur, bukan proksi."
        )
        alasan = f"{len(kandidat)} kandidat; edge rata-rata {edge_jendela_pct:+.2f}% per jendela"
    else:
        mode = "proksi"
        catatan = (
            "BELUM TERUKUR: data yang ada (snapshot TradingView + screener Arjum) tidak "
            "memuat harga buka/tutup harian, jadi edge overnight BSJP tidak bisa dihitung. "
            "Peringkat di bawah adalah PROKSI dari win-rate event Arjum + kondisi teknikal — "
            "bukan hasil BSJP. Jangan diperlakukan sebagai edge."
        )
        alasan = f"{len(kandidat)} kandidat (peringkat proksi, bukan edge terukur)"

    return PeringkatBSJP(
        mode=mode, ada=ada, kandidat=kandidat,
        edge_rata_pct=edge_jendela_pct, n_sampel=n_jendela,
        alasan=alasan, catatan_kejujuran=catatan,
    )
