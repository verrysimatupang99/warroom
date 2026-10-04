"""Ukur koin yang "overextended" — dan sekaligus uji apakah men-short-nya pernah membayar.

Asal-usul: sebuah postingan media sosial memamerkan short $VELVET yang untung, dengan alasan
"derivatif mulai mereda (OI, FR, CVD)". Diuji ke data Binance sungguhan, alasannya **tidak
didukung data saat itu**: OI justru sedang di puncaknya dan naik +10,7% pada jam masuk.

Modul ini memisahkan dua hal yang sering dicampur:
  1. `ukur_kelebihan()` — apakah harga memang sudah lari jauh? (fakta yang bisa dilihat)
  2. `uji_edge_short()` — apakah men-short pola itu pernah membayar? (bukti, bukan kesan)

Aturan kejujuran yang dipegang modul ini: "harga sudah naik banyak" BUKAN alasan untuk short.
Puncak hanya bisa dipastikan SETELAH kejadian. Karena itu hasil ukur selalu disertai uji edge,
dan kalau uji edge tidak menunjukkan keunggulan, itu ditulis apa adanya.
"""

from __future__ import annotations

import datetime as dt
from statistics import mean, median
from typing import Any

# Indeks kolom kline Binance: [0] open time, [1] open, [2] high, [3] low, [4] close.
_I_OPEN, _I_HIGH, _I_LOW, _I_CLOSE = 1, 2, 3, 4

LABEL_JUJUR = (
    "overextended = fakta harga, BUKAN sinyal short. Puncak hanya diketahui setelahnya; "
    "uji_edge_short() yang menentukan apakah pola ini pernah membayar."
)

FR_NETRAL_PCT = 0.05  # di atas ini funding dianggap ramai (long crowded)


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x else None


def _wib(ms: int) -> str:
    return (dt.datetime.fromtimestamp(ms / 1000, dt.UTC) + dt.timedelta(hours=7)).strftime(
        "%d/%m %H:%M"
    )


def _peta_oi(oi_hist: list[dict[str, Any]]) -> dict[int, float]:
    out: dict[int, float] = {}
    for r in oi_hist or []:
        t = r.get("timestamp")
        v = _f(r.get("sumOpenInterestValue")) or _f(r.get("sumOpenInterest"))
        if isinstance(t, int) and v is not None:
            out[t] = v
    return out


def _fr_pada(fr_titik: list[tuple[int, float]], ts: int) -> float | None:
    kandidat = [v for t, v in fr_titik if t <= ts]
    return kandidat[-1] if kandidat else None


def ukur_kelebihan(
    klines: list[list[Any]],
    oi_hist: list[dict[str, Any]] | None = None,
    funding: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Seberapa jauh harga sudah lari, dan bagaimana kondisi derivatifnya SEKARANG.

    Mengembalikan fakta yang bisa dilihat sekarang — tanpa berpura-pura tahu ini puncak.
    """
    if not klines:
        return {"status": "belum-cukup-data"}

    peta = _peta_oi(oi_hist or [])
    fr_titik = sorted(
        (int(r["fundingTime"]), (_f(r.get("fundingRate")) or 0.0) * 100)
        for r in (funding or [])
        if r.get("fundingTime")
    )

    tinggi = max(float(k[_I_HIGH]) for k in klines)
    rendah = min(float(k[_I_LOW]) for k in klines)
    jam_puncak = max(klines, key=lambda k: float(k[_I_HIGH]))[0]
    kini = float(klines[-1][_I_CLOSE])
    pump_pct = round((tinggi / rendah - 1) * 100, 2) if rendah else None
    dari_puncak_pct = round((kini / tinggi - 1) * 100, 2) if tinggi else None

    # OI: puncak vs sekarang
    oi_puncak = oi_kini = None
    jam_oi_puncak = None
    if peta:
        t_puncak = max(peta, key=lambda t: peta[t])
        oi_puncak = peta[t_puncak]
        jam_oi_puncak = t_puncak
        oi_kini = peta[max(peta)]
    oi_mereda_pct = (
        round((oi_kini / oi_puncak - 1) * 100, 2) if (oi_puncak and oi_kini) else None
    )

    fr_persen = [v for _, v in fr_titik]
    fr_maks = round(max(fr_persen), 4) if fr_persen else None
    fr_median = round(median(fr_persen), 4) if fr_persen else None
    fr_pernah_ramai = bool(fr_persen) and max(fr_persen) > FR_NETRAL_PCT

    catatan: list[str] = [LABEL_JUJUR]
    if fr_maks is not None and not fr_pernah_ramai:
        catatan.append(
            f"funding tidak pernah ramai (maks {fr_maks:+.4f}% per 8 jam, ambang {FR_NETRAL_PCT}%) "
            "— jadi 'long crowded' tidak terlihat di sini"
        )
    if oi_mereda_pct is not None and oi_mereda_pct >= -5:
        catatan.append(
            f"OI masih di dekat puncak ({oi_mereda_pct:+.1f}% dari puncak) — derivatif BELUM mereda"
        )

    return {
        "status": "ok",
        "harga_sekarang": kini,
        "harga_tertinggi": tinggi,
        "harga_terendah": rendah,
        "jam_puncak": _wib(jam_puncak),
        "pump_pct": pump_pct,
        "turun_dari_puncak_pct": dari_puncak_pct,
        "oi_puncak_usd": oi_puncak,
        "oi_sekarang_usd": oi_kini,
        "oi_puncak_wib": _wib(jam_oi_puncak) if jam_oi_puncak else None,
        "oi_mereda_pct": oi_mereda_pct,
        "fr_maks_pct": fr_maks,
        "fr_median_pct": fr_median,
        "fr_pernah_ramai": fr_pernah_ramai,
        "overextended": bool(pump_pct is not None and pump_pct >= 50),
        "catatan": catatan,
    }


def _tanda_tangan(
    klines: list[list[Any]], peta: dict[int, float], fr_titik: list[tuple[int, float]]
) -> list[dict[str, Any]]:
    """Jam yang MEMENUHI syarat seperti yang bisa diamati saat itu (bukan setelah tahu hasil).

    Syarat: harga naik jam itu, OI naik jam itu, funding netral.
    """
    out: list[dict[str, Any]] = []
    for i, k in enumerate(klines):
        if i == 0:
            continue
        ts = k[0]
        prev_ts = klines[i - 1][0]
        oi, oi_prev = peta.get(ts), peta.get(prev_ts)
        fr = _fr_pada(fr_titik, ts)
        if oi is None or oi_prev is None or fr is None:
            continue
        if float(k[_I_CLOSE]) > float(klines[i - 1][_I_CLOSE]) and oi > oi_prev and abs(fr) < FR_NETRAL_PCT:
            out.append({"ts": ts, "wib": _wib(ts), "close": float(k[_I_CLOSE]), "i": i})
    return out


def uji_edge_short(
    klines: list[list[Any]],
    oi_hist: list[dict[str, Any]] | None = None,
    funding: list[dict[str, Any]] | None = None,
    horizon_jam: tuple[int, ...] = (6, 12, 24),
) -> dict[str, Any]:
    """Terapkan aturan itu ke SEMUA jam, lalu bandingkan dengan short asal-asalan (dasar).

    Inti kejujurannya: satu trade yang dipamerkan tidak membuktikan apa-apa. Yang membuktikan
    adalah menjalankan aturannya ke seluruh data lalu membandingkan dengan dasar pembanding.
    Kalau tidak lebih baik dari dasar, tulis `tidak-terbukti`.
    """
    if not klines:
        return {"status": "belum-cukup-data"}
    peta = _peta_oi(oi_hist or [])
    fr_titik = sorted(
        (int(r["fundingTime"]), (_f(r.get("fundingRate")) or 0.0) * 100)
        for r in (funding or [])
        if r.get("fundingTime")
    )
    sinyal = _tanda_tangan(klines, peta, fr_titik)
    idx_sinyal = {s["i"] for s in sinyal}

    hasil: dict[str, Any] = {
        "status": "ok",
        "jumlah_jam": len(klines),
        "jumlah_sinyal": len(sinyal),
        "uji": [],
    }
    for h in horizon_jam:
        sig, dasar = [], []
        for i, k in enumerate(klines):
            if i + h >= len(klines):
                continue
            masuk, keluar = float(k[_I_CLOSE]), float(klines[i + h][_I_CLOSE])
            if not masuk:
                continue
            r = (masuk / keluar - 1) * 100  # PnL short
            dasar.append(r)
            if i in idx_sinyal:
                sig.append(r)
        if not dasar:
            continue
        # Dasar pembanding SELALU dilaporkan — kalau tidak ada sinyal, itu tetap informasi
        # ("aturan ini tidak pernah menyala di window ini, dan ini yang dilakukan asal-short").
        baris_uji: dict[str, Any] = {
            "tahan_jam": h,
            "n_sinyal": len(sig),
            "n_dasar": len(dasar),
            "rata_dasar_pct": round(mean(dasar), 2),
            "tengah_dasar_pct": round(median(dasar), 2),
        }
        if sig:
            menang = sum(1 for r in sig if r > 0)
            baris_uji.update(
                {
                    "rata_sinyal_pct": round(mean(sig), 2),
                    "tengah_sinyal_pct": round(median(sig), 2),
                    "menang_sinyal": menang,
                    "winrate_sinyal_pct": round(menang / len(sig) * 100, 1),
                    "selisih_poin": round(mean(sig) - mean(dasar), 2),
                }
            )
        hasil["uji"].append(baris_uji)

    lengkap = [u for u in hasil["uji"] if "rata_sinyal_pct" in u]
    bermanfaat = [
        u for u in lengkap if u["rata_sinyal_pct"] > 0 and u.get("selisih_poin", 0) > 0
    ]
    jumlah_lebih_baik = sum(1 for u in lengkap if u.get("selisih_poin", 0) > 0)
    if not lengkap:
        hasil["verdict"] = "tidak-ada-sinyal"
    else:
        hasil["verdict"] = "ada-keunggulan" if bermanfaat else "tidak-terbukti"
    hasil["ringkas"] = (
        f"{jumlah_lebih_baik} dari {len(lengkap)} horizon lebih baik daripada asal-short; "
        + (
            "ada horizon yang positif DAN lebih baik"
            if bermanfaat
            else "TIDAK ada horizon yang sekaligus positif dan lebih baik — pola ini belum terbukti"
        )
        if lengkap
        else "aturan ini tidak pernah menyala pada window ini — tidak ada yang bisa disimpulkan"
    )
    return hasil
