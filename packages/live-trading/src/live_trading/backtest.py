"""Backtest walk-forward: uji aturan gate pada data historis.

Kenapa ini ada: pengumpulan kandidat secara hidup hanya menghasilkan beberapa kandidat per
jam, dan hanya sebagian kecil yang pernah selesai (TP1/SL kena). Menunggu sampel yang cukup
butuh berminggu-minggu. Padahal pertanyaannya sederhana: **aturan gate ini berguna atau
tidak?** Data historis bisa menjawabnya malam ini.

Aturan main supaya angkanya sah:

1. Keputusan diambil di penutupan candle. Data yang dipakai hanya candle yang SUDAH tertutup.
2. Candle yang belum penuh (4 jam / 1 hari) DIBUANG, bukan dipotong. Memotong berarti
   memasukkan harga masa depan ke dalam keputusan — dan semua hasilnya jadi omong kosong.
3. Hasil dilacak dengan fungsi yang sama dengan perdagangan hidup (``measure.resolve_one``),
   bukan salinan aturan.
4. Gate yang dipakai adalah fungsi yang sama (``engine.assess_setup``).

Keterbatasan yang wajib disebut saat melaporkan angka:
- Tanpa biaya transaksi, tanpa slippage, tanpa pendanaan (funding).
- Gate exposure tidak diuji: backtest menganggap tidak ada posisi bersamaan.
- Satu keputusan per ``step_h`` jam, jadi tidak setiap candle dinilai (biaya komputasi).
"""

from __future__ import annotations

import datetime as dt
import json
import math
import statistics
from pathlib import Path
from typing import Any

import httpx

from .collectors import make_client
from .config import Settings
from .measure import FILL_WINDOW_H, ekskursi, masuk_pasar, resolve_one, resolve_tp2
from .signals import engine, smc

MS_JAM = 3_600_000
TIMEFRAME_JAM = {"1h": 1, "4h": 4, "1d": 24}


# Hasil yang dianggap sudah selesai (terisi lalu keluar). 'tp2' wajib ada di sini:
# kemenangan target 2R pernah hilang dari perhitungan hanya karena namanya tidak
# terdaftar, dan itu membuat ringkasan melaporkan rugi besar yang tidak ada.
HASIL_TERISI = ("tp1", "tp2", "sl", "terbuka", "kedaluwarsa")


def fetch_history(
    settings: Settings, pair: str, days: int, client: httpx.Client, offset_days: int = 0
) -> list[list[Any]]:
    """Riwayat candle 1H, menaik, dijahit dari beberapa permintaan (batas 1000 per panggilan).

    ``offset_days`` menggeser jendela ke belakang. Dipakai untuk uji di luar sampel: kalau
    temuan hanya muncul di 300 hari terakhir, itu bukan temuan — itu kebetulan periode.
    """
    akhir = int((dt.datetime.now(dt.UTC) - dt.timedelta(days=offset_days)).timestamp() * 1000)
    kursor = akhir - days * 24 * MS_JAM
    out: list[list[Any]] = []
    while kursor < akhir:
        r = client.get(
            f"{settings.binance_fapi}/fapi/v1/klines",
            params={"symbol": pair, "interval": "1h", "startTime": kursor, "limit": 1000},
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        out.extend(batch)
        kursor = int(batch[-1][0]) + MS_JAM
        if len(batch) < 1000:
            break
    return out


def resample(raw: list[list[Any]], jam: int) -> list[list[Any]]:
    """Gabungkan candle 1H menjadi candle lebih besar; yang belum penuh dibuang.

    Membuang — bukan memotong — adalah inti anti-lookahead di sini.
    """
    span = jam * MS_JAM
    ember: dict[int, list[list[Any]]] = {}
    for k in raw:
        b = (int(k[0]) // span) * span
        ember.setdefault(b, []).append(k)

    out: list[list[Any]] = []
    for b in sorted(ember):
        g = ember[b]
        if len(g) < jam:
            continue  # candle belum penuh -> tidak boleh dipakai
        # float() wajib: Binance mengirim harga sebagai teks, dan min/max atas teks itu
        # urut abjad — min("9", "10") = "10". Ini pernah benar-benar salah.
        out.append(
            [
                b,
                float(g[0][1]),
                max(float(x[2]) for x in g),
                min(float(x[3]) for x in g),
                float(g[-1][4]),
                sum(float(x[5]) for x in g),
                g[-1][6],
            ]
        )
    return out


def _duplikat(
    riwayat: list[dict[str, Any]],
    ts: dt.datetime,
    arah: str,
    zona: tuple[float, float] | None,
    jendela_jam: float,
) -> bool:
    for r in reversed(riwayat):
        umur = (ts - r["ts"]).total_seconds() / 3600
        if umur > jendela_jam:
            break
        if r["arah"] != arah:
            continue
        if zona is None or r["zona"] is None:
            continue
        if engine.zone_overlap(zona, r["zona"]) > 0.7:
            return True
    return False


def jendela_h1() -> int:
    """Berapa candle 1H yang perlu disediakan agar tiap timeframe punya jatah penuh.

    Diambil dari batas milik perdagangan hidup (``engine.TIMEFRAMES``), bukan angka
    sendiri-sendiri. Kalau batas hidup berubah, backtest ikut — dan tetap melihat
    informasi yang sama persis dengan yang dilihat bot saat mengambil keputusan.
    """
    return max(engine.TIMEFRAMES[tf] * jam for tf, jam in TIMEFRAME_JAM.items())


def run_pair(
    settings: Settings,
    pair: str,
    raw: list[list[Any]],
    *,
    step_h: int = 4,
    warmup_h: int = 2880,
    hold_h: int = 33,
    jendela_dedupe_jam: float = 12.0,
    isi_penetrasi_bps: float = 0.0,
) -> list[dict[str, Any]]:
    """Satu pair, berjalan maju per ``step_h`` jam. Tidak ada data masa depan yang bocor."""
    rows: list[dict[str, Any]] = []
    riwayat: list[dict[str, Any]] = []
    butuh = jendela_h1()

    for t in range(warmup_h, len(raw) - hold_h - 1, step_h):
        # Jendela bergerak, bukan seluruh riwayat: sama dengan yang dilihat bot hidup,
        # dan membuat biaya tiap keputusan tetap (kalau tidak, backtest jadi O(n^2)).
        win = raw[max(0, t - butuh) : t]
        if len(win) < butuh:
            continue
        candles = {}
        for tf, jam in TIMEFRAME_JAM.items():
            seri = win if jam == 1 else resample(win, jam)
            seri = seri[-engine.TIMEFRAMES[tf] :]
            if not seri:
                break
            candles[tf] = smc.from_binance_klines(seri)
        if len(candles) < 3 or len(candles["1d"]) < 6 or len(candles["4h"]) < 12:
            continue

        st = engine.build_structure(pair, candles)
        arah = engine.supported_direction(st)
        if arah is None:
            continue

        prop = engine.propose(st, arah)
        if not prop or prop.get("entry") is None or prop.get("sl") is None or prop.get("tp1") is None:
            continue

        poi = prop.get("poi") or {}
        zona = None
        if poi.get("low") is not None and poi.get("high") is not None:
            zona = (float(poi["low"]), float(poi["high"]))

        ts = dt.datetime.fromtimestamp(int(raw[t - 1][6]) / 1000, dt.UTC)
        if _duplikat(riwayat, ts, arah, zona, jendela_dedupe_jam):
            continue

        penilaian = engine.assess_setup(
            st,
            direction=arah,
            entry=float(prop["entry"]),
            sl=float(prop["sl"]),
            tp1=float(prop["tp1"]),
            poi=prop.get("poi"),
            open_positions=None,  # backtest: tidak ada posisi bersamaan (lihat catatan modul)
        )
        row = {
            "ts": ts.isoformat(timespec="seconds"),
            "pair": pair,
            "direction": arah.upper(),
            "allowed": penilaian.allowed,
            "tier": penilaian.tier,
            "entry": float(prop["entry"]),
            "sl": float(prop["sl"]),
            "tp1": float(prop["tp1"]),
            # Disimpan supaya skenario "masuk di harga pasar" dan uji mekanisme
            # (mis. kenapa aturan freshness berperilaku begitu) bisa dihitung nanti.
            "harga_keputusan": float(st.price),
            "atr_pct": st.atr_pct,
            "rules": [
                {"rule": v.rule, "ok": v.ok, "hard": v.hard, "reason": v.reason} for v in penilaian.verdicts
            ],
        }
        maju = raw[t : t + hold_h + 1]
        tahan = max(1, hold_h - FILL_WINDOW_H - 1)
        hasil = resolve_one(
            row,
            maju,
            now=ts + dt.timedelta(hours=hold_h),
            hold_max_h=tahan,
            isi_penetrasi_bps=isi_penetrasi_bps,
        )
        hasil.update(masuk_pasar(row, maju, now=ts + dt.timedelta(hours=hold_h)))
        hasil.update(resolve_tp2(row, maju, now=ts + dt.timedelta(hours=hold_h)))
        hasil.update(ekskursi(row, maju))
        rows.append(hasil)
        riwayat.append({"ts": ts, "arah": arah, "zona": zona})

    return rows


FEE_PER_SISI_DEFAULT = 0.0005  # 0,05% per sisi (Binance USDⓈ-M taker tanpa VIP)


def _blok(sel: list[dict[str, Any]], *, fee_per_sisi: float = 0.0) -> dict[str, Any]:
    nilai = [r["r"] for r in sel if r.get("r") is not None]
    terisi = [r for r in sel if r.get("hasil") in HASIL_TERISI]
    nilai_terisi = [r["r"] for r in terisi if r.get("r") is not None]

    def biaya_r(r: dict[str, Any]) -> float:
        """Biaya dalam satuan R: (2 sisi × fee × harga) / jarak SL.

        Ini bukan detail kecil: dengan SL 1% dari harga, biaya round-trip 0,10% sudah
        memakan 0,10R per trade — cukup untuk menghabiskan 'edge' kecil.
        """
        entry, sl = r.get("entry"), r.get("sl")
        if not entry or not sl:
            return 0.0
        risk = abs(float(entry) - float(sl))
        if risk <= 0:
            return 0.0
        return (2 * fee_per_sisi * float(entry)) / risk

    biaya = [biaya_r(r) for r in terisi if r.get("r") is not None]
    nilai_bersih = [
        r["r"] - b for r, b in zip([r for r in terisi if r.get("r") is not None], biaya, strict=True)
    ]

    # Apakah bedanya nyata atau cuma derau? Selisih +0,07R dari belasan kandidat bisa
    # dengan mudah jadi kebetulan. Tanpa ini, angka kecil akan dilaporkan sebagai temuan.
    t_stat: float | None = None
    if len(nilai_terisi) >= 3:
        sd = statistics.stdev(nilai_terisi)
        if sd > 0:
            t_stat = round(statistics.fmean(nilai_terisi) / (sd / len(nilai_terisi) ** 0.5), 2)

    return {
        "n": len(sel),
        "tp1": sum(1 for r in sel if r.get("hasil") == "tp1"),
        "sl": sum(1 for r in sel if r.get("hasil") == "sl"),
        "tak_terisi": sum(1 for r in sel if r.get("hasil") == "tidak_terisi"),
        "terisi": len(terisi),
        # Dua ukuran, sengaja dipisah: kandidat yang tidak pernah terisi bukan "seri",
        # ia tidak pernah menjadi posisi. Mencampurnya menyamarkan sinyalnya.
        "expectancy_r": round(sum(nilai) / len(nilai), 3) if nilai else None,
        "expectancy_terisi_r": (round(sum(nilai_terisi) / len(nilai_terisi), 3) if nilai_terisi else None),
        "biaya_rata_r": round(statistics.fmean(biaya), 4) if biaya else None,
        "expectancy_bersih_r": (round(statistics.fmean(nilai_bersih), 3) if nilai_bersih else None),
        "total_r": round(sum(nilai), 2) if nilai else 0.0,
        "total_r_terisi": round(sum(nilai_terisi), 2) if nilai_terisi else 0.0,
        "total_bersih_r": round(sum(nilai_bersih), 2) if nilai_bersih else 0.0,
        "t_stat": t_stat,
        # Dua syarat, bukan satu: t besar dari 3 pengamatan itu tidak berarti apa-apa.
        "keyakinan": (
            "belum cukup bukti"
            if t_stat is None
            else "kuat"
            if abs(t_stat) >= 2 and len(nilai_terisi) >= 20
            else "lemah"
        ),
    }


def test_difference(a: list[float], b: list[float]) -> dict[str, Any]:
    """Uji Welch: apakah dua kelompok benar-benar berbeda, bukan cuma beda dari nol.

    t-statistik biasa hanya menjawab "apakah rata-ratanya di atas nol". Itu BUKAN
    pertanyaan yang kita punya. Yang kita punya: apakah kandidat yang lolos gate
    berbeda dari yang ditolak — dan itu butuh uji beda antar kelompok.
    """
    if len(a) < 3 or len(b) < 3:
        return {"beda_r": None, "t": None, "keterangan": "sampel kurang"}
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    va, vb = statistics.variance(a), statistics.variance(b)
    na, nb = len(a), len(b)
    se = (va / na + vb / nb) ** 0.5
    if se == 0:
        return {"beda_r": round(ma - mb, 4), "t": None, "keterangan": "ragam nol"}
    t = (ma - mb) / se
    # p dua sisi, pendekatan normal (df besar). Cukup untuk menyaring derau.
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2))))
    return {
        "beda_r": round(ma - mb, 4),
        "t": round(t, 2),
        "p_approx": round(p, 4),
        "keterangan": "beda nyata" if abs(t) >= 2 else "tidak bisa dibedakan dari derau",
    }


def bandingkan(rows: list[dict[str, Any]], *, fee_per_sisi: float = FEE_PER_SISI_DEFAULT) -> dict[str, Any]:
    """Bandingkan kelompok: lolos vs ditolak, dan tiap aturan vs sisanya (setelah biaya)."""
    dinilai = [r for r in rows if r.get("hasil") != "menunggu_terisi"]

    def bersih(sel: list[dict[str, Any]]) -> list[float]:
        out = []
        for r in sel:
            if r.get("r") is None or not r.get("entry") or not r.get("sl"):
                continue
            risk = abs(float(r["entry"]) - float(r["sl"]))
            if risk <= 0:
                continue
            out.append(r["r"] - (2 * fee_per_sisi * float(r["entry"])) / risk)
        return out

    lolos = bersih([r for r in dinilai if r.get("allowed")])
    ditolak = bersih([r for r in dinilai if not r.get("allowed")])
    hasil: dict[str, Any] = {"lolos_vs_ditolak": test_difference(lolos, ditolak)}
    hasil["lolos_vs_ditolak"]["n_lolos"] = len(lolos)
    hasil["lolos_vs_ditolak"]["n_ditolak"] = len(ditolak)

    per_aturan = {}
    for nama in sorted({r2 for r in dinilai for r2 in (r.get("rules_gagal") or [])}):
        gagal = bersih([r for r in dinilai if nama in (r.get("rules_gagal") or [])])
        lolos_saja = bersih([r for r in dinilai if not r.get("rules_gagal")])
        per_aturan[nama] = test_difference(gagal, lolos_saja)
        per_aturan[nama]["n_gagal"] = len(gagal)
    hasil["per_aturan"] = per_aturan
    return hasil


def rows_entering_market(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Baris sintetis untuk skenario masuk di harga pasar, supaya bisa dinilai _blok yang sama.

    Tinggal di ``measure`` (bukan di ``backtest``) supaya pengukuran hidup dan backtest
    memakai konversi yang sama persis.
    """
    from .measure import rows_entering_market as _impl

    return _impl(rows)


def test_cluster(rows: list[dict[str, Any]], *, fee_per_sisi: float = FEE_PER_SISI_DEFAULT) -> dict[str, Any]:
    """Uji beda yang tahan korelasi: satu pair = satu unit, bukan satu kandidat = satu unit.

    Kandidat dalam satu pair saling berkorelasi (rezim pasar yang sama, level yang sama),
    jadi menghitung t atas ribuan kandidat seperti pengamatan bebas itu terlalu percaya diri.
    Di sini tiap pair diringkas jadi satu angka, lalu 40 pair itu yang diuji — jauh lebih
    keras, dan lebih jujur soal berapa bukti yang sebenarnya kita punya.
    """
    dinilai = [r for r in rows if r.get("hasil") != "menunggu_terisi" and r.get("pair")]

    def bersih(r: dict[str, Any]) -> float | None:
        if r.get("r") is None or not r.get("entry") or not r.get("sl"):
            return None
        risk = abs(float(r["entry"]) - float(r["sl"]))
        if risk <= 0:
            return None
        return r["r"] - (2 * fee_per_sisi * float(r["entry"])) / risk

    per_pair: dict[str, dict[str, list[float]]] = {}
    for r in dinilai:
        b = bersih(r)
        if b is None:
            continue
        kunci = "lolos" if r.get("allowed") else "ditolak"
        per_pair.setdefault(r["pair"], {"lolos": [], "ditolak": []})[kunci].append(b)

    selisih = [
        statistics.fmean(v["lolos"]) - statistics.fmean(v["ditolak"])
        for v in per_pair.values()
        if v["lolos"] and v["ditolak"]
    ]
    if len(selisih) < 3:
        return {"n_pair": len(selisih), "beda_r": None, "t": None, "keterangan": "pair terlalu sedikit"}
    t = statistics.fmean(selisih) / (statistics.stdev(selisih) / len(selisih) ** 0.5)
    return {
        "n_pair": len(selisih),
        "beda_r": round(statistics.fmean(selisih), 4),
        "t": round(t, 2),
        "keterangan": "beda nyata" if abs(t) >= 2 else "tidak bisa dibedakan dari derau",
        "catatan": "satu pair = satu unit pengamatan (tahan korelasi dalam pair)",
    }


def test_cluster_rules(
    rows: list[dict[str, Any]], *, fee_per_sisi: float = FEE_PER_SISI_DEFAULT
) -> dict[str, dict[str, Any]]:
    """Uji klaster per aturan: kandidat yang gagal aturan itu vs yang lolos semua gate.

    Tanpa ini, temuan seperti "atr_min beda nyata (t=-2.97)" bisa jadi cuma efek korelasi
    dalam pair — persis yang terjadi pada perbandingan lolos vs ditolak.
    """
    dinilai = [r for r in rows if r.get("hasil") != "menunggu_terisi" and r.get("pair")]

    def bersih(r: dict[str, Any]) -> float | None:
        if r.get("r") is None or not r.get("entry") or not r.get("sl"):
            return None
        risk = abs(float(r["entry"]) - float(r["sl"]))
        if risk <= 0:
            return None
        return r["r"] - (2 * fee_per_sisi * float(r["entry"])) / risk

    aturan = sorted({a for r in dinilai for a in (r.get("rules_gagal") or [])})
    keluar: dict[str, dict[str, Any]] = {}
    for nama in aturan:
        per_pair: dict[str, dict[str, list[float]]] = {}
        for r in dinilai:
            b = bersih(r)
            if b is None:
                continue
            gagal = nama in (r.get("rules_gagal") or [])
            bersih_semua = not (r.get("rules_gagal") or [])
            if not gagal and not bersih_semua:
                continue
            slot = per_pair.setdefault(r["pair"], {"gagal": [], "bersih": []})
            slot["gagal" if gagal else "bersih"].append(b)
        selisih = [
            statistics.fmean(v["gagal"]) - statistics.fmean(v["bersih"])
            for v in per_pair.values()
            if v["gagal"] and v["bersih"]
        ]
        if len(selisih) < 3:
            keluar[nama] = {
                "n_pair": len(selisih),
                "beda_r": None,
                "t": None,
                "keterangan": "pair terlalu sedikit",
            }
            continue
        t = statistics.fmean(selisih) / (statistics.stdev(selisih) / len(selisih) ** 0.5)
        keluar[nama] = {
            "n_pair": len(selisih),
            "beda_r": round(statistics.fmean(selisih), 4),
            "t": round(t, 2),
            "keterangan": "beda nyata" if abs(t) >= 2 else "tidak bisa dibedakan dari derau",
        }
    return keluar


def test_cluster_null(
    rows: list[dict[str, Any]], *, fee_per_sisi: float = FEE_PER_SISI_DEFAULT
) -> dict[str, Any]:
    """Apakah aliran kandidat sendiri punya edge? Satu pair = satu unit, diuji terhadap nol.

    Ini pertanyaan paling dasar dari semuanya: sebelum membahas aturan mana yang berguna,
    apakah kandidat yang dihasilkan sistem ini menghasilkan R positif setelah biaya — dan
    apakah itu bertahan ketika korelasi dalam pair diperhitungkan?
    """
    dinilai = [r for r in rows if r.get("hasil") != "menunggu_terisi" and r.get("pair")]
    per_pair: dict[str, list[float]] = {}
    for r in dinilai:
        if r.get("r") is None or not r.get("entry") or not r.get("sl"):
            continue
        risk = abs(float(r["entry"]) - float(r["sl"]))
        if risk <= 0:
            continue
        bersih = r["r"] - (2 * fee_per_sisi * float(r["entry"])) / risk
        per_pair.setdefault(r["pair"], []).append(bersih)

    rerata = [statistics.fmean(v) for v in per_pair.values() if len(v) >= 5]
    if len(rerata) < 3:
        return {"n_pair": len(rerata), "rata_r": None, "t": None, "keterangan": "pair terlalu sedikit"}
    t = statistics.fmean(rerata) / (statistics.stdev(rerata) / len(rerata) ** 0.5)
    return {
        "n_pair": len(rerata),
        "rata_r": round(statistics.fmean(rerata), 4),
        "t": round(t, 2),
        "keterangan": (
            "edge nyata" if t >= 2 else "rugi nyata" if t <= -2 else "tidak bisa dibedakan dari derau"
        ),
        "catatan": "rata-rata per pair (min 5 kandidat), lalu diuji terhadap nol",
    }


def rows_target_2r(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Baris sintetis untuk skenario target 2R, supaya bisa dinilai _blok yang sama."""
    out = []
    for r in rows:
        if r.get("r_tp2") is None:
            continue
        q = dict(r)
        q["r"] = r["r_tp2"]
        q["hasil"] = r["hasil_tp2"]
        out.append(q)
    return out


def aggregate(rows: list[dict[str, Any]], *, fee_per_sisi: float = FEE_PER_SISI_DEFAULT) -> dict[str, Any]:
    """Susun angka: lolos vs ditolak (bayangan), plus penilaian per aturan.

    ``fee_per_sisi`` dihitung sebagai biaya nyata dalam satuan R, bukan diabaikan.
    """
    dinilai = [r for r in rows if r.get("hasil") != "menunggu_terisi"]
    terisi = [r for r in dinilai if r.get("hasil") in HASIL_TERISI]

    aturan: dict[str, list[dict[str, Any]]] = {}
    for r in dinilai:
        gagal = r.get("rules_gagal") or []
        if len(gagal) == 1:
            aturan.setdefault(gagal[0], []).append(r)

    per_aturan = {}
    for nama, sel in sorted(aturan.items()):
        b = _blok(sel, fee_per_sisi=fee_per_sisi)
        eks = b["expectancy_bersih_r"]  # setelah biaya: yang menentukan hidup-mati
        b["putusan"] = (
            "belum bisa dinilai"
            if eks is None
            else "berguna"
            if eks < 0
            else "merugikan"
            if eks > 0
            else "netral"
        )
        per_aturan[nama] = b

    return {
        "n_kandidat": len(rows),
        "n_dinilai": len(dinilai),
        "n_terisi": len(terisi),
        "fill_rate_pct": round(100 * len(terisi) / len(dinilai), 1) if dinilai else None,
        "fee_per_sisi": fee_per_sisi,
        # Garis dasar: apa yang terjadi kalau SEMUA kandidat berarah ditradingkan tanpa gate.
        # Tanpa pembanding ini, "lolos vs ditolak" tidak ada artinya.
        "semua": _blok(dinilai, fee_per_sisi=fee_per_sisi),
        # Pembanding yang lebih penting daripada gate: menunggu harga datang ke POI
        # membuang ~38% kandidat. Apakah penantian itu sepadan, diukur di sini.
        "masuk_pasar": _blok(rows_entering_market(dinilai), fee_per_sisi=fee_per_sisi),
        # Biaya per trade tetap dalam satuan R, imbalannya dua kali: apakah target 2R
        # lebih baik daripada 1R pada biaya yang sama?
        "target_2r": _blok(rows_target_2r(dinilai), fee_per_sisi=fee_per_sisi),
        "lolos": _blok([r for r in dinilai if r.get("allowed")], fee_per_sisi=fee_per_sisi),
        "ditolak": _blok([r for r in dinilai if not r.get("allowed")], fee_per_sisi=fee_per_sisi),
        "per_aturan": per_aturan,
    }


def _nama_berkas(
    days: int,
    offset_days: int = 0,
    hold_h: int = 33,
    isi_penetrasi_bps: float = 0.0,
    paksa_tag: bool = False,
) -> str:
    """Nama berkas memuat jendela, pergeseran, tahan, dan penetrasi — percobaan tidak saling menimpa.

    ``paksa_tag`` dipakai ketika sebuah percobaan kebetulan memakai nilai default semua
    (mis. ``--penetrasi-bps 0``): tanpa itu, hasilnya menimpa berkas kanonik dan dashboard
    diam-diam membaca sampel yang berbeda.
    """
    if paksa_tag or offset_days or hold_h != 33 or isi_penetrasi_bps:
        return f"backtest-{days}d-h{hold_h}-o{offset_days}-p{isi_penetrasi_bps:g}.jsonl"
    return f"backtest-{days}d.jsonl"


def save_rows(
    settings: Settings,
    rows: list[dict[str, Any]],
    days: int,
    offset_days: int = 0,
    hold_h: int = 33,
    isi_penetrasi_bps: float = 0.0,
    paksa_tag: bool = False,
) -> Path:
    """Simpan baris mentah supaya penghitungan bisa diulang tanpa menarik data lagi.

    Ditulis ke berkas sementara lalu dipindahkan: dashboard bisa membaca berkas ini kapan
    saja (timer 15 menit), dan berkas yang separuh tertulis akan terbaca sebagai rusak.
    """
    path = settings.state_dir / _nama_berkas(days, offset_days, hold_h, isi_penetrasi_bps, paksa_tag)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return path


def load_rows(
    settings: Settings,
    days: int,
    offset_days: int = 0,
    hold_h: int = 33,
    isi_penetrasi_bps: float = 0.0,
) -> list[dict[str, Any]]:
    path = settings.state_dir / _nama_berkas(days, offset_days, hold_h, isi_penetrasi_bps)
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def run(
    settings: Settings,
    pairs: list[str],
    *,
    days: int = 60,
    step_h: int = 4,
    warmup_h: int = 2880,
    hold_h: int = 33,
    offset_days: int = 0,
    isi_penetrasi_bps: float = 0.0,
    paksa_tag: bool = False,
    fee_per_sisi: float = FEE_PER_SISI_DEFAULT,
    client: httpx.Client | None = None,
    lapor: Any = None,
) -> dict[str, Any]:
    own = client is None
    c = client or make_client(timeout=30.0)
    semua: list[dict[str, Any]] = []
    # ``days`` = jendela KEPUTUSAN. Data yang ditarik harus lebih panjang dari itu, karena
    # tiap keputusan butuh masa pemanasan (batas timeframe hidup). Tanpa ini, jendela yang
    # digeser ke belakang akan menghasilkan nol kandidat tanpa penjelasan.
    hari_pemanasan = -(-warmup_h // 24)
    hari_tarik = days + hari_pemanasan
    try:
        for i, pair in enumerate(pairs, 1):
            try:
                raw = fetch_history(settings, pair, hari_tarik, c, offset_days=offset_days)
                rows = run_pair(
                    settings,
                    pair,
                    raw,
                    step_h=step_h,
                    warmup_h=warmup_h,
                    hold_h=hold_h,
                    isi_penetrasi_bps=isi_penetrasi_bps,
                )
            except Exception as exc:  # noqa: BLE001
                if lapor:
                    lapor(f"  [{i}/{len(pairs)}] {pair:<12} GAGAL: {type(exc).__name__}: {exc}")
                continue
            semua.extend(rows)
            if lapor:
                lolos = sum(1 for r in rows if r.get("allowed"))
                lapor(
                    f"  [{i}/{len(pairs)}] {pair:<12} {len(raw):>5} candle · "
                    f"{len(rows):>3} kandidat · {lolos} lolos"
                )
    finally:
        if own:
            c.close()

    hasil = aggregate(semua, fee_per_sisi=fee_per_sisi)
    hasil["rows"] = semua
    save_rows(settings, semua, days, offset_days, hold_h, isi_penetrasi_bps, paksa_tag)
    return hasil
