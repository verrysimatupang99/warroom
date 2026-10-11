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
from collections.abc import Callable
from pathlib import Path
from statistics import mean, median
from typing import Any

# Indeks kolom kline Binance: [0] open time, [1] open, [2] high, [3] low, [4] close.
_I_OPEN, _I_HIGH, _I_LOW, _I_CLOSE = 1, 2, 3, 4

LABEL_JUJUR = (
    "overextended = fakta harga, BUKAN sinyal short. Puncak hanya diketahui setelahnya; "
    "uji_edge_short() yang menentukan apakah pola ini pernah membayar."
)

FR_NETRAL_PCT = 0.05  # di atas ini funding dianggap ramai (long crowded)

# Indeks kolom kline Binance USDⓈ-M futures:
# [0] open time [1] open [2] high [3] low [4] close [5] volume (base)
# [9] takerBuyBaseAssetVolume [10] takerBuyQuoteAssetVolume
_I_TAKER_BUY = 9
_I_VOLUME = 5


def cvd_seri(klines: list[list[Any]]) -> list[float]:
    """CVD (Cumulative Volume Delta) dari klines — agresi beli dikurangi agresi jual.

    Delta tiap bar = taker_buy_base − taker_sell_base, dan taker_sell_base = volume − taker_buy_base,
    jadi delta = 2·taker_buy_base − volume. Dijumlahkan kumulatif sepanjang window.

    Kenapa dari klines dan bukan aggTrade: `aggTrades` hanya mengembalikan trade terakhir
    (beberapa menit), sedangkan klines memberi riwayat panjang yang sama-sama berasal dari data
    taker sungguhan — bukan tebakan.
    """
    kum = 0.0
    out: list[float] = []
    for k in klines:
        try:
            vol = float(k[_I_VOLUME])
            tb = float(k[_I_TAKER_BUY])
        except (IndexError, TypeError, ValueError):
            out.append(kum)
            continue
        kum += 2 * tb - vol
        out.append(kum)
    return out


def uji_kehabisan_pembeli(klines: list[list[Any]], jendela: int = 24) -> dict[str, Any]:
    """Uji klaim 'buyer exhaustion' lewat divergensi CVD — sinyal KETIGA yang disebut postingan.

    Divergensi bearish klasik: harga mencetak puncak **lebih tinggi**, tetapi CVD (agresi beli
    kumulatif) pada puncak itu **lebih rendah** daripada puncak sebelumnya. Artinya: harga naik
    bukan karena pembeli makin agresif — tenaga pendorongnya habis.

    Kejujuran yang dipegang: divergensi **bukan** izin short. Ia hanya gejala; apakah ia pernah
    membayar tetap harus diuji lewat `uji_edge_short(tanda_tangan=tanda_divergensi_cvd)`.
    """
    if len(klines) < jendela * 2:
        return {"status": "belum-cukup-data", "jendela": jendela}
    potong = klines[-jendela * 2 :]
    cvd = cvd_seri(potong)
    tengah = jendela

    def puncak(a: int, b: int) -> tuple[int, float, float]:
        i = max(range(a, b), key=lambda x: float(potong[x][_I_HIGH]))
        return i, float(potong[i][_I_HIGH]), cvd[i]

    i1, h1, c1 = puncak(0, tengah)
    i2, h2, c2 = puncak(tengah, len(potong))
    divergensi = h2 > h1 and c2 < c1

    return {
        "status": "ok",
        "jendela": jendela,
        "puncak_lama": {"jam": _wib(potong[i1][0]), "harga": h1, "cvd": round(c1, 2)},
        "puncak_baru": {"jam": _wib(potong[i2][0]), "harga": h2, "cvd": round(c2, 2)},
        "harga_lebih_tinggi": h2 > h1,
        "cvd_lebih_rendah": c2 < c1,
        "divergensi": divergensi,
        "cvd_sekarang": round(cvd[-1], 2),
        "catatan": [
            "divergensi CVD = gejala 'buyer exhaustion', BUKAN izin short — puncak hanya "
            "diketahui setelahnya",
            "harga membuat puncak lebih tinggi sementara agresi beli lebih rendah"
            if divergensi
            else "tidak ada divergensi pada window ini (harga dan agresi beli sejalan)",
        ],
    }


def tanda_divergensi_cvd(klines: list[list[Any]], jendela: int = 24) -> set[int]:
    """Indeks bar yang saat itu menunjukkan divergensi CVD (dihitung mundur, bukan menyontek).

    Untuk setiap bar i, hanya data sampai bar i yang dipakai — supaya uji edge-nya tidak
    memakai informasi masa depan.
    """
    out: set[int] = set()
    for i in range(len(klines)):
        if i + 1 < jendela * 2:
            continue
        h = uji_kehabisan_pembeli(klines[: i + 1], jendela=jendela)
        if h.get("divergensi"):
            out.add(i)
    return out


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

    # Sinyal ketiga yang biasa diklaim: 'buyer exhaustion' lewat divergensi CVD.
    kehabisan = uji_kehabisan_pembeli(klines)
    if kehabisan.get("status") == "ok" and kehabisan.get("divergensi"):
        catatan.append(
            "divergensi CVD terdeteksi: harga bikin puncak lebih tinggi, agresi beli justru "
            "lebih rendah (gejala 'buyer exhaustion')"
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
        "kehabisan_pembeli": kehabisan,
        "overextended": bool(pump_pct is not None and pump_pct >= 50),
        "catatan": catatan,
    }


def _http(path: str, timeout: float = 20.0) -> Any:
    import json
    import urllib.request

    req = urllib.request.Request(
        "https://fapi.binance.com" + path, headers={"User-Agent": "war-room/1.0"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


CACHE_NAME = "overextended.json"
TTL_S = 3600  # 1 jam — 3 panggilan API per simbol, jadi tidak perlu tiap 15 menit


def snapshot(
    pairs: tuple[str, ...] | list[str],
    state_dir: Path | str,
    *,
    sekarang: float | None = None,
    jendela_jam: int = 168,
) -> dict[str, Any]:
    """Ukur kelebihan + uji edge untuk beberapa simbol, dengan cache 1 jam.

    Sengaja TIDAK menamai ini "sinyal short": keluaran selalu membawa hasil uji edge, sehingga
    pembaca melihat apakah pola itu pernah membayar — bukan hanya label "overextended".
    """
    import json
    import time
    from pathlib import Path as _P

    d = _P(state_dir) / "cache"
    p = d / CACHE_NAME
    kini = time.time() if sekarang is None else sekarang
    try:
        isi = json.loads(p.read_text(encoding="utf-8"))
        if (kini - float(isi.get("diambil_epoch") or 0)) < TTL_S:
            return isi
    except (OSError, json.JSONDecodeError):
        pass

    baris: list[dict[str, Any]] = []
    galat: list[str] = []
    for s in pairs:
        try:
            kl = _http(f"/fapi/v1/klines?symbol={s}&interval=1h&limit={jendela_jam}")
            oi = _http(f"/futures/data/openInterestHist?symbol={s}&period=1h&limit={jendela_jam}")
            fr = _http(f"/fapi/v1/fundingRate?symbol={s}&limit=60")
        except Exception as exc:  # noqa: BLE001 — satu simbol gagal jangan menjatuhkan sisanya
            galat.append(f"{s}: {type(exc).__name__}")
            continue
        ukur = ukur_kelebihan(kl, oi, fr)
        if ukur.get("status") != "ok":
            galat.append(f"{s}: data kurang")
            continue
        edge = uji_edge_short(kl, oi, fr)
        edge_cvd = uji_edge_divergensi_cvd(kl)
        baris.append(
            {
                "symbol": s,
                "pump_pct": ukur["pump_pct"],
                "turun_dari_puncak_pct": ukur["turun_dari_puncak_pct"],
                "oi_mereda_pct": ukur["oi_mereda_pct"],
                "fr_pernah_ramai": ukur["fr_pernah_ramai"],
                "fr_maks_pct": ukur["fr_maks_pct"],
                "overextended": ukur["overextended"],
                "divergensi_cvd": (ukur.get("kehabisan_pembeli") or {}).get("divergensi"),
                "edge_oi_fr": edge.get("verdict"),
                "edge_oi_fr_detail": edge.get("uji"),
                "edge_cvd": edge_cvd.get("verdict"),
                "edge_cvd_detail": edge_cvd.get("uji"),
                "catatan": ukur["catatan"],
            }
        )

    baris.sort(key=lambda b: (b["pump_pct"] or 0), reverse=True)
    out = {
        "diambil_epoch": kini,
        "ttl_s": TTL_S,
        "jumlah": len(baris),
        "paling_overextended": baris[0]["symbol"] if baris else None,
        "simbol": baris,
        "galat": galat,
        "catatan": [
            LABEL_JUJUR,
            "uji edge memakai dasar pembanding: 'tidak-terbukti' berarti pola itu TIDAK lebih "
            "baik daripada short asal-asalan, bukan sekadar 'kurang yakin'",
        ],
    }
    try:
        d.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return out


def uji_edge_divergensi_cvd(
    klines: list[list[Any]],
    horizon_jam: tuple[int, ...] = (6, 12, 24),
    jendela: int = 24,
) -> dict[str, Any]:
    """Uji apakah sinyal 'buyer exhaustion' (divergensi CVD) pernah membayar kalau di-short.

    Ini menguji sinyal ketiga yang diklaim postingan dengan mesin yang sama seperti sinyal OI/FR —
    supaya tidak ada dua standar pembuktian.
    """
    if not klines:
        return {"status": "belum-cukup-data"}
    return uji_edge_short(
        klines,
        horizon_jam=horizon_jam,
        tanda=lambda kl: tanda_divergensi_cvd(kl, jendela=jendela),
        nama_tanda=f"divergensi-CVD (jendela {jendela} jam)",
    )


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
    *,
    tanda: Callable[[list[list[Any]]], set[int]] | None = None,
    nama_tanda: str = "harga-naik + OI-naik + FR-netral",
) -> dict[str, Any]:
    """Terapkan aturan itu ke SEMUA jam, lalu bandingkan dengan short asal-asalan (dasar).

    Inti kejujurannya: satu trade yang dipamerkan tidak membuktikan apa-apa. Yang membuktikan
    adalah menjalankan aturannya ke seluruh data lalu membandingkan dengan dasar pembanding.
    Kalau tidak lebih baik dari dasar, tulis `tidak-terbukti`.

    `tanda` memungkinkan menguji tanda tangan lain (mis. divergensi CVD) dengan mesin yang sama,
    supaya tidak ada dua cara berbeda menghitung hal yang sama.
    """
    if not klines:
        return {"status": "belum-cukup-data"}
    if tanda is not None:
        idx_sinyal = set(tanda(klines))
        jumlah_sinyal = len(idx_sinyal)
    else:
        peta = _peta_oi(oi_hist or [])
        fr_titik = sorted(
            (int(r["fundingTime"]), (_f(r.get("fundingRate")) or 0.0) * 100)
            for r in (funding or [])
            if r.get("fundingTime")
        )
        sinyal = _tanda_tangan(klines, peta, fr_titik)
        idx_sinyal = {s["i"] for s in sinyal}
        jumlah_sinyal = len(sinyal)

    hasil: dict[str, Any] = {
        "status": "ok",
        "nama_tanda": nama_tanda,
        "jumlah_jam": len(klines),
        "jumlah_sinyal": jumlah_sinyal,
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
            r = (masuk - keluar) / masuk * 100  # PnL short
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
    # Dasar pembanding positif = pasar memang sedang turun. Short menang bukan karena sinyalnya,
    # tapi karena arah pasar — jadi itu BUKAN keunggulan sinyal. Harus dinyatakan, bukan dipuji.
    dasar_positif = [u for u in lengkap if u.get("rata_dasar_pct", 0) > 0]
    ada_keunggulan = bool(bermanfaat) and jumlah_lebih_baik >= 2

    if not lengkap:
        hasil["verdict"] = "tidak-ada-sinyal"
    elif ada_keunggulan and len(dasar_positif) == len(lengkap):
        # Semua dasar positif: kemungkinan besar ini cuma efek pasar turun.
        hasil["verdict"] = "perlu-uji-tambahan"
    elif ada_keunggulan:
        hasil["verdict"] = "ada-keunggulan"
    else:
        hasil["verdict"] = "tidak-terbukti"

    hasil["jumlah_horizon"] = len(lengkap)
    hasil["jumlah_lebih_baik"] = jumlah_lebih_baik
    hasil["dasar_positif_semua"] = bool(lengkap) and len(dasar_positif) == len(lengkap)
    hasil["jendela_jam"] = len(klines)
    hasil["catatan"] = [
        f"diuji pada {len(klines)} jam — satu rezim pasar; ini bukti lemah, bukan kepastian",
        "'lebih baik daripada dasar' = lebih baik daripada short asal-asalan pada window yang sama",
    ]
    alasan = {
        "tidak-ada-sinyal": (
            "aturan ini tidak pernah menyala pada window ini — tidak ada yang bisa disimpulkan"
        ),
        "perlu-uji-tambahan": (
            f"{jumlah_lebih_baik}/{len(lengkap)} horizon lebih baik, TAPI dasar pembanding "
            "positif di semua horizon — pasar sedang turun, jadi short menang apa pun sinyalnya. "
            "Bukan bukti keunggulan; perlu window yang arahnya berbeda"
        ),
        "ada-keunggulan": (
            f"menang di {jumlah_lebih_baik}/{len(lengkap)} horizon dan ada horizon yang positif"
        ),
        "tidak-terbukti": (
            f"hanya {jumlah_lebih_baik}/{len(lengkap)} horizon lebih baik (perlu ≥2) — "
            "pola ini belum terbukti"
        ),
    }[hasil["verdict"]]
    hasil["ringkas"] = alasan
    return hasil
