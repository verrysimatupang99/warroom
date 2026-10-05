"""BSJP — Beli Sore Jual Pagi: peringkat kandidat tahan semalam IDX (5 Okt 2026).

Lini masa singkat, supaya jelas kenapa berkas ini berbentuk begini:

- Versi pertama berkas ini hanya bisa memberi PERINGKAT PROKSI. Alasannya jujur: data yang
  tersedia saat itu (snapshot TradingView + screener Arjum) tidak memuat harga buka/tutup
  harian, jadi edge overnight tidak bisa dihitung.
- Ternyata filter BSJP yang SUDAH diuji walk-forward memang ada — tapi di `idx_bsjp_watch.py`
  (Hermes Tencent), bukan di repo ini. Port ini memindahkannya ke War Room.

ANGKA DI SINI BUKAN KARANGAN. Disalin apa adanya dari sumbernya:

    # EDGE filter — ARA raw resep Kingdom (walk-forward 10 Sep: net +1.05/+0.80/+1.18 per fold)
    # STRONG tier = subset dgn SMA10 extension + chg band (BSJP edge, net +0.86%)
    CHG_MIN, CHG_MAX = 2.0, 25.0
    VOL_VS_AVG = 1.5
    PRICE_MIN = 100.0
    VALUE_MIN = 1e9
    EXT_SMA10 = 1.03
    STRONG_CHG = (6.0, 12.0)
    COST_PCT = 0.40   # round-trip fee+levy

Dua tingkatan:
- **ARA**  — chg 2..25%, harga > Rp100, nilai ≥ Rp1 M, rel-vol ≥ 1,5× rata-rata. Estimasi net
  walk-forward ARA: **+1,06%/trade**.
- **STRONG** — subset ARA + close ≥ 1,03×SMA10 + chg 6..12%. Inilah edge BSJP: **+0,86%/trade**.

BATAS JUJUR yang dikodekan di sini (jangan dihapus tanpa menggantinya dengan yang lebih baik):

1. **Edge berasal dari FILTER, bukan dari dataset yang dihitung ulang di sini.** Itulah sebabnya
   ia bisa dipindah tanpa membawa 24 juta tick: yang perlu dibawa cuma definisi filternya.
2. `net_est_pct` adalah **hasil walk-forward di sumbernya**, BUKAN hasil verifikasi baru di War
   Room. Karena itu diberi label `sumber_angka` + `terverifikasi_di_warroom=False` supaya tidak
   ada yang menyangka ini hasil ukur ulang di sini.
3. `COST_PCT` 0,40% sudah dikurangkan di angka sumbernya. Di sini **tidak** dikurangkan lagi —
   mengurangkan dua kali membuat angkanya tampak lebih buruk daripada aslinya.
4. Kandidat yang SMA10-nya tidak diketahui **ditolak dengan alasan**, bukan diloloskan. Tier
   STRONG bergantung pada SMA10; meloloskan tanpa itu berarti mengarang dasar klasifikasi.
5. Data pasar diambil dari sumber GRATIS (TradingView scanner + riwayat harian), **tanpa kuota
   Arjum** — `history`/`history_yf` Arjum memang pemakan kuota terbesar, jadi mengaitkan BSJP
   ke sana akan mengulang masalah yang sedang dibereskan.

Mode keluaran:
- ``terukur``  — bila ada rangkaian harga buka/tutup harian nyata (edge dihitung di sini).
- ``bersumber`` — data sekarang: filter teruji diterapkan, angka dari walk-forward sumbernya.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from live_trading.collectors.idx import _kode_bersih  # normalisasi .JK (satu implementasi)

__all__ = ["PARAM", "KandidatBSJP", "PeringkatBSJP", "susun_peringkat"]

# Parameter filter — disalin apa adanya dari idx_bsjp_watch.py (Tencent). Jangan diubah tanpa
# mencatat ulang hasil walk-forward-nya di sumber.
PARAM: dict[str, Any] = {
    "chg_min": 2.0,
    "chg_max": 25.0,
    "vol_vs_avg": 1.5,
    "price_min": 100.0,
    "value_min": 1e9,
    "ext_sma10": 1.03,
    "strong_chg": (6.0, 12.0),
    "cost_pct": 0.40,
    "net_ara_pct": 1.06,      # estimasi net walk-forward, tier ARA
    "net_strong_pct": 0.86,   # estimasi net walk-forward, subset STRONG (edge BSJP)
    "sumber_angka": (
        "walk-forward idx_bsjp_watch.py (Tencent): ARA resep Kingdom +1,05/+0,80/+1,18 per fold; "
        "BSJP STRONG subset net +0,86%/trade"
    ),
}


def _angka(v: Any) -> float | None:
    """float() yang menolak NaN — NaN bukan angka untuk ditampilkan."""
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


@dataclass
class KandidatBSJP:
    """Satu kandidat BSJP. `net_est_pct` = estimasi dari SUMBER, bukan hitungan War Room.

    Field lama (nama/bucket/skor/wr_event/potensi/drawdown) tetap dipertahankan supaya UI dan
    tes yang sudah ada tidak pecah; field baru mengisi angka filter BSJP yang sebenarnya.
    """

    ticker: str
    tier: str = "ARA"                 # "STRONG" (edge BSJP) | "ARA"
    nama: str = ""
    bucket: str = ""
    skor: int | None = None           # None = tidak ada angka (bukan 0)
    close: float | None = None
    chg_pct: float | None = None
    sma10: float | None = None
    rel_vol: float | None = None
    ext_sma10: float | None = None    # close / sma10
    net_est_pct: float | None = None  # dari sumber, lihat catatan #2
    sumber_sma: str = ""
    wr_event: float | None = None     # win-rate event Arjum (BUKAN edge BSJP)
    potensi: float | None = None
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
    mode: str                          # "terukur" (dihitung di sini) | "bersumber" | "proksi"
    ada: bool
    kandidat: list[KandidatBSJP] = field(default_factory=list)
    edge_rata_pct: float | None = None  # HANYA terisi di mode "terukur"
    n_sampel: int = 0
    strong: int = 0
    ara: int = 0
    net_est_pct: float | None = None   # rata-rata estimasi bersumber
    terverifikasi_di_warroom: bool = False
    dipindai: int = 0
    ditolak_filter: int = 0
    alasan: str = ""
    catatan_kejujuran: str = ""
    sumber_angka: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "ada": self.ada,
            "kandidat": [k.to_dict() for k in self.kandidat],
            "edge_rata_pct": self.edge_rata_pct,
            "n_sampel": self.n_sampel,
            "strong": self.strong,
            "ara": self.ara,
            "net_est_pct": self.net_est_pct,
            "terverifikasi_di_warroom": self.terverifikasi_di_warroom,
            "dipindai": self.dipindai,
            "ditolak_filter": self.ditolak_filter,
            "alasan": self.alasan,
            "catatan_kejujuran": self.catatan_kejujuran,
            "sumber_angka": self.sumber_angka,
        }


def _baris_ke_kandidat_tera(
    r: dict[str, Any], riwayat: dict[str, dict[str, Any]], p: dict[str, Any]
) -> tuple[KandidatBSJP | None, str]:
    """Terapkan filter BSJP teruji ke satu baris pemindai.

    Mengembalikan ``(kandidat, "")`` bila lolos, atau ``(None, alasan_tolak)`` bila tidak.
    """
    ticker = str(r.get("ticker") or r.get("symbol") or r.get("stock_code") or "").upper()
    if not ticker:
        return None, "tanpa ticker"
    # Buang sufiks .JK (universe Tencent menulis 'CAMP.JK'). Tanpa ini, `riwayat.get(ticker)`
    # tidak menemukan kunci 'CAMP' dari ambil_riwayat — SMA10 hilang, kandidat ditolak
    # tanpa sebab yang terlihat.
    ticker = _kode_bersih(ticker)
    close = _angka(r.get("close") or r.get("last") or r.get("price"))
    chg = _angka(r.get("chg") if r.get("chg") is not None else r.get("change_pct"))
    vol = _angka(r.get("volume"))
    if close is None or chg is None:
        return None, "harga/perubahan tidak diketahui"

    if not (p["chg_min"] <= chg <= p["chg_max"]):
        return None, f"chg {chg:.1f}% di luar band {p['chg_min']}–{p['chg_max']}%"
    if close <= p["price_min"]:
        return None, f"harga {close:.0f} ≤ {p['price_min']:.0f}"
    if vol is not None and close * vol < p["value_min"]:
        return None, f"nilai transaksi {close * vol:,.0f} < {p['value_min']:.0f}"

    hist = riwayat.get(ticker) or {}
    sma10 = _angka(hist.get("sma10"))
    vavg10 = _angka(hist.get("vavg10"))
    sumber_sma = str(hist.get("sumber") or "")
    if sma10 is None:
        sma10 = _angka(r.get("sma10"))
        if sma10 is not None:
            sumber_sma = sumber_sma or "baris pemindai"
    if vavg10 is None:
        vavg10 = _angka(r.get("vavg10"))

    if sma10 is None or sma10 <= 0:
        # Aturan #4: tanpa SMA10, tier STRONG tidak punya dasar. Tolak, jangan karang.
        return None, "SMA10 tidak diketahui — tidak bisa dinilai sebagai BSJP"

    rel_vol = (vol / vavg10) if (vol is not None and vavg10) else _angka(r.get("rel_vol"))
    catatan: list[str] = []
    if rel_vol is not None:
        if rel_vol < p["vol_vs_avg"]:
            return None, f"rel-vol {rel_vol:.2f}× < {p['vol_vs_avg']}×"
    else:
        catatan.append("rel-vol tidak diketahui — tidak diklaim lolos filter volume")

    ext = close / sma10
    kuat = ext >= p["ext_sma10"] and (p["strong_chg"][0] <= chg <= p["strong_chg"][1])
    tier = "STRONG" if kuat else "ARA"
    if kuat:
        catatan.append(
            f"STRONG: close {ext:.3f}× SMA10 (≥{p['ext_sma10']}) dan chg {chg:.1f}% "
            f"di band {p['strong_chg'][0]}–{p['strong_chg'][1]}%"
        )
    else:
        catatan.append(f"ARA: chg {chg:.1f}% lolos band ARA, tapi bukan subset STRONG")
    catatan.append(f"SMA10 dari {sumber_sma or 'tidak dicatat'}")

    return (
        KandidatBSJP(
            ticker=ticker,
            tier=tier,
            nama=str(r.get("nama") or r.get("stock_name") or ""),
            bucket=str(r.get("bucket") or ""),
            close=round(close, 2),
            chg_pct=round(chg, 2),
            sma10=round(sma10, 2),
            rel_vol=round(rel_vol, 2) if rel_vol is not None else None,
            ext_sma10=round(ext, 4),
            net_est_pct=p["net_strong_pct"] if kuat else p["net_ara_pct"],
            sumber_sma=sumber_sma or "tidak dicatat",
            wr_event=r.get("wr_event") if isinstance(r.get("wr_event"), (int, float)) else None,
            potensi=r.get("potensi") if isinstance(r.get("potensi"), (int, float))
            else (r.get("potential") if isinstance(r.get("potential"), (int, float)) else None),
            drawdown=r.get("drawdown") if isinstance(r.get("drawdown"), (int, float)) else None,
            volume=vol,
            catatan=catatan,
        ),
        "",
    )


def susun_peringkat(
    screener_rows: list[dict[str, Any]] | None,
    tv_rows: list[dict[str, Any]] | None,
    *,
    riwayat: dict[str, dict[str, Any]] | None = None,
    edge_jendela_pct: float | None = None,
    n_jendela: int = 0,
) -> PeringkatBSJP:
    """Susun peringkat kandidat BSJP memakai filter yang sudah diuji walk-forward.

    Empat masukan, semuanya dari data yang sudah ada di War Room:

    - ``screener_rows`` — kandidat dari screener (mis. Arjum/idx). Dipakai sebagai daftar calon.
    - ``tv_rows`` — snapshot TradingView (harga live, RSI, EMA, ATR, volume). Sumber harga
      utama, karena Arjum tidak menyediakan harga live intraday.
    - ``riwayat`` — opsional ``{ticker: {"sma10", "vavg10", "sumber"}}``. Bila tidak ada, SMA10
      dicari di baris itu sendiri; bila tetap tidak ada, kandidat ditolak (aturan #4).
    - ``edge_jendela_pct`` — HANYA boleh diisi bila ada perhitungan harga buka/tutup per tanggal
      nyata. Selama ``None``, mode bukan ``terukur`` dan itu dinyatakan terang-terangan.
    """
    p = PARAM
    # Kunci riwayat dinormalkan juga: pemanggil bisa mengirim {'CAMP.JK': ...} atau
    # {'CAMP': ...} — dengan ini keduanya menemukan nilai yang sama.
    riwayat_pakai = {_kode_bersih(k): v for k, v in (riwayat or {}).items()}

    # Gabung kandidat: screener + TradingView. TradingView yang menang untuk field harga,
    # karena ia live dan screener tidak memuatnya.
    gabung: dict[str, dict[str, Any]] = {}
    for r in screener_rows or []:
        if not isinstance(r, dict):
            continue
        t = _kode_bersih(str(r.get("stock_code") or r.get("ticker") or ""))
        if t:
            gabung[t] = dict(r)
    for r in tv_rows or []:
        if not isinstance(r, dict):
            continue
        t = _kode_bersih(str(r.get("ticker") or r.get("symbol") or ""))
        if not t:
            continue
        dasar = gabung.get(t, {})
        dasar.update({k: v for k, v in r.items() if v is not None})
        dasar["ticker"] = t
        gabung[t] = dasar
        # SMA10 dari TradingView bisa dipakai bila riwayat tidak menyediakannya.
        if _angka(r.get("sma10")) is not None and t not in riwayat_pakai:
            riwayat_pakai[t] = {
                "sma10": _angka(r.get("sma10")),
                "vavg10": _angka(r.get("vavg10")),
                "sumber": str(r.get("sumber_sma") or "TradingView"),
            }

    kandidat: list[KandidatBSJP] = []
    ditolak = 0
    for r in gabung.values():
        k, _alasan = _baris_ke_kandidat_tera(r, riwayat_pakai, p)
        if k is None:
            ditolak += 1
            continue
        kandidat.append(k)

    # STRONG dulu, lalu rel-vol terbesar (urutan sama dengan sumbernya).
    kandidat.sort(key=lambda k: (k.tier != "STRONG", -(k.rel_vol or 0)))

    n_strong = sum(1 for k in kandidat if k.tier == "STRONG")
    n_ara = len(kandidat) - n_strong
    ada = bool(kandidat)

    net = None
    if kandidat:
        net = round(sum(k.net_est_pct or 0 for k in kandidat) / len(kandidat), 2)

    if edge_jendela_pct is not None:
        # Jalur "terukur": edge benar-benar dihitung di sini dari harga buka/tutup nyata.
        mode = "terukur"
        catatan = (
            f"Edge dihitung dari {n_jendela} jendela buka→tutup nyata di War Room. "
            "Ini angka terukur, bukan estimasi bersumber."
        )
        alasan = (
            f"{len(kandidat)} kandidat ({n_strong} STRONG, {n_ara} ARA); "
            f"edge rata-rata {edge_jendela_pct:+.2f}% per jendela"
        )
        terverifikasi = True
    elif ada:
        mode = "bersumber"
        catatan = (
            "Filter BSJP di sini sudah diuji walk-forward DI SUMBERNYA (Tencent) — ARA "
            f"+{p['net_ara_pct']:.2f}% dan subset STRONG +{p['net_strong_pct']:.2f}% per trade "
            "setelah biaya 0,40%. Angka itu BELUM dihitung ulang di War Room karena rangkaian "
            "harga buka/tutup harian belum tersedia. Perlakukan sebagai estimasi bersumber, "
            "bukan hasil terukur di sini."
        )
        alasan = (
            f"{len(kandidat)} lolos ({n_strong} STRONG, {n_ara} ARA) dari {len(gabung)} "
            f"diperiksa; {ditolak} ditolak filter"
        )
        terverifikasi = False
    else:
        mode = "bersumber"
        catatan = (
            "Tidak ada kandidat yang lolos filter BSJP pada pemindaian ini. Itu hasil wajar: "
            "filter sengaja ketat (band chg, nilai transaksi ≥ Rp1 M, rel-vol ≥ 1,5×, ekstensi "
            "SMA10). Kosong bukan berarti rusak."
        )
        alasan = f"{len(gabung)} kandidat diperiksa, {ditolak} ditolak filter"
        terverifikasi = False

    return PeringkatBSJP(
        mode=mode,
        ada=ada,
        kandidat=kandidat,
        edge_rata_pct=edge_jendela_pct,
        n_sampel=n_jendela,
        strong=n_strong,
        ara=n_ara,
        net_est_pct=net,
        terverifikasi_di_warroom=terverifikasi,
        dipindai=len(gabung),
        ditolak_filter=ditolak,
        alasan=alasan,
        catatan_kejujuran=catatan,
        sumber_angka=p["sumber_angka"],
    )
