"""Bandarmologi IDX — replikasi parameter broker-flow dari data Arjum yang sudah kita punya.

Asal-usul: sebuah alat screener IDX publik (IHSG Screener) mempromosikan sistem
"KRAKEN FLOW / ORCA" dengan parameter: High Bid/Offer, High ATS, No Sell, Close High,
High Non-Regular, Top Volume, Frequency, Foreign. Pertanyaannya: mana yang bisa dihitung
dari data yang SUDAH kita punya (Arjum + TradingView), dan mana yang tidak?

Jawaban jujur (diuji 4 Okt, lihat CATATAN_REPLIKASI):

    bisa   : Top Volume, Frequency, Foreign, High ATS, No Sell, Close High
    tidak  : High Bid/Offer (butuh antrean order book), High Non-Regular (butuh data
             transaksi negosiasi/non-reguler) — keduanya TIDAK ada di Arjum maupun TradingView

ATURAN KEJUJURAN modul ini: parameter yang berhasil direplikasi BUKAN bukti bahwa strateginya
menguntungkan. Kita hanya meniru cara MENGUKUR, bukan mengklaim edge. Karena itu setiap keluaran
membawa `LABEL_JUJUR`, dan skor di sini disebut `skor_heuristik` — bukan "win rate" atau "akurasi".

Kuota: Arjum 6000 panggilan/hari. Setiap ticker = 1 panggilan. Karena itu `skrining()` WAJIB
dipakai dengan daftar terbatas + cache harian, dan menaikkan `maks_ticker` harus disengaja.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path
from typing import Any

LABEL_JUJUR = (
    "parameter broker-flow (ATS, no-sell, frekuensi) = replikasi CARA UKUR, "
    "bukan bukti menguntungkan. Skor di sini heuristik; edge-nya belum diuji."
)

CATATAN_REPLIKASI = [
    "bisa dihitung: Top Volume, Frequency, Foreign, High ATS, No Sell, Close High",
    "tidak bisa: High Bid/Offer (antrean order book) dan High Non-Regular (transaksi "
    "negosiasi) — tidak tersedia di Arjum maupun TradingView",
]

CACHE_NAME = "bandarmologi.json"
TTL_S = 6 * 3600  # 6 jam — data broker IDX berubah harian, bukan per menit


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x else None


def _total(brokers: list[dict[str, Any]], kunci: str) -> float:
    """Jumlahkan satu field numerik dari daftar broker; field rusak/hilang dilewati."""
    t = 0.0
    for b in brokers:
        v = _f(b.get(kunci))
        if v is not None:
            t += v
    return t


def _total_berpasangan(
    brokers: list[dict[str, Any]], kunci_nilai: str, kunci_frq: str
) -> tuple[float, float]:
    """Jumlahkan pasangan (nilai, frekuensi) HANYA untuk broker yang keduanya terbaca.

    Kenapa penting: ATS = nilai ÷ frekuensi. Kalau satu broker nilainya rusak/hilang tetapi
    frekuensinya ikut dijumlahkan, penyebutnya membengkak dan ATS jadi terlalu rendah —
    angka yang salah tanpa error. Karena itu pasangannya harus koheren.
    """
    nilai = frq = 0.0
    for b in brokers:
        a, c = _f(b.get(kunci_nilai)), _f(b.get(kunci_frq))
        if a is None or c is None:
            continue
        nilai += a
        frq += c
    return nilai, frq


def ringkas_broker(payload: dict[str, Any]) -> dict[str, Any]:
    """Ubah satu `broker_summary` Arjum jadi ukuran yang bisa dibandingkan antar-emiten.

    Rumus yang dipakai (semuanya dari field Arjum, tidak ada tebakan):

    - ``ats_beli``   = Σ nilai beli ÷ Σ frekuensi beli   → rata-rata nilai per transaksi beli
                       ("Average Trade Size" milik alat itu)
    - ``porsi_frq_beli`` = Σ frq beli ÷ (Σ frq beli + Σ frq jual) → siapa yang lebih sering
                       bertransaksi; >0,5 = sisi beli lebih aktif
    - ``net_nilai``  = Σ nilai net antar broker → net buy agregat
    - ``no_sell``    = broker akumulator teratas punya frekuensi jual sangat kecil dibanding
                       beli (< 20%) → gejala "tidak ada tekanan jual"
    - ``pembeli_teratas`` / ``penjual_teratas`` = broker dengan net beli / net jual terbesar
    """
    brokers = [b for b in (payload.get("brokers") or []) if isinstance(b, dict)]
    if not brokers:
        return {"status": "belum-cukup-data"}

    bfrq = _total(brokers, "bfrq")
    sfrq = _total(brokers, "sfrq")
    nval = _total(brokers, "nval")

    # Untuk rasio ATS dipakai pasangan yang koheren (lihat `_total_berpasangan`).
    bval_p, bfrq_p = _total_berpasangan(brokers, "bval", "bfrq")
    sval_p, sfrq_p = _total_berpasangan(brokers, "sval", "sfrq")

    ats = round(bval_p / bfrq_p, 1) if bfrq_p else None
    ats_jual = round(sval_p / sfrq_p, 1) if sfrq_p else None
    porsi = round(bfrq / (bfrq + sfrq), 4) if (bfrq + sfrq) else None

    bersih = sorted(
        (
            {
                "broker": b.get("broker_code"),
                "nama": b.get("broker_name"),
                "net_nilai": _f(b.get("nval")) or 0.0,
                "frq_beli": _f(b.get("bfrq")) or 0.0,
                "frq_jual": _f(b.get("sfrq")) or 0.0,
            }
            for b in brokers
        ),
        key=lambda x: x["net_nilai"],
        reverse=True,
    )
    atas = bersih[0] if bersih else None
    bawah = bersih[-1] if bersih else None

    no_sell = False
    if atas and atas["frq_beli"]:
        rasio = atas["frq_jual"] / atas["frq_beli"]
        no_sell = rasio < 0.20

    return {
        "status": "ok",
        "kode": payload.get("stock_code"),
        "tanggal": payload.get("broker_end_date"),
        "ats_beli": ats,
        "ats_jual": ats_jual,
        "porsi_frq_beli": porsi,
        "net_nilai": round(nval, 2),
        "net_juta": round(nval / 1e6, 1),
        "frq_beli": bfrq,
        "frq_jual": sfrq,
        "no_sell": no_sell,
        "pembeli_teratas": atas,
        "penjual_teratas": bawah,
        "jumlah_broker": len(brokers),
    }


def skor_heuristik(r: dict[str, Any]) -> float:
    """Skor gabungan 0..100 dari ukuran di atas — HEURISTIK, bukan hasil uji.

    Dibuat transparan supaya bisa dibantah: setiap komponen disebut bobotnya.

    - porsi frekuensi beli     : bobot 40 (sisi beli lebih aktif)
    - net beli positif         : bobot 30
    - ATS beli > ATS jual      : bobot 20 (transaksi besar di sisi beli)
    - no_sell                  : bobot 10
    """
    if r.get("status") != "ok":
        return 0.0
    skor = 0.0
    porsi = r.get("porsi_frq_beli") or 0.0
    skor += min(max(porsi, 0.0), 1.0) * 40
    if (r.get("net_nilai") or 0.0) > 0:
        skor += 30
    a_b, a_j = r.get("ats_beli"), r.get("ats_jual")
    if a_b and a_j and a_b > a_j:
        skor += 20
    if r.get("no_sell"):
        skor += 10
    return round(skor, 1)


def skrining(
    kode: list[str],
    state_dir: Path | str,
    *,
    maks_ticker: int = 8,
    sekarang: float | None = None,
    ambil=None,
) -> dict[str, Any]:
    """Ambil `broker_summary` untuk kode terpilih, ukur, urutkan. Cache 6 jam.

    `maks_ticker` dibatasi keras: setiap ticker = 1 panggilan Arjum, dan kuotanya 6000/hari
    dibagi seluruh pemakaian lain. Menaikkan angka ini harus keputusan sadar, bukan default.

    `ambil` bisa diisi fungsi pengambil (untuk tes tanpa jaringan).
    """
    from pathlib import Path as _P

    if ambil is None:
        raise ValueError("`ambil` wajib: fungsi yang menerima kode dan mengembalikan payload")

    d = _P(state_dir) / "cache"
    p = d / CACHE_NAME
    kini = time.time() if sekarang is None else sekarang
    hari = dt.datetime.fromtimestamp(kini, dt.UTC).strftime("%Y-%m-%d")
    try:
        isi = json.loads(p.read_text(encoding="utf-8"))
        if isi.get("hari") == hari and (kini - float(isi.get("diambil_epoch") or 0)) < TTL_S:
            return isi
    except (OSError, json.JSONDecodeError):
        pass

    kode = list(dict.fromkeys(kode))[:maks_ticker]
    baris: list[dict[str, Any]] = []
    galat: list[str] = []
    for k in kode:
        try:
            payload = ambil(k)
        except Exception as exc:  # noqa: BLE001 — satu kode gagal jangan menjatuhkan sisanya
            galat.append(f"{k}: {type(exc).__name__}")
            continue
        r = ringkas_broker(payload or {})
        if r.get("status") != "ok":
            galat.append(f"{k}: data kurang")
            continue
        r["skor_heuristik"] = skor_heuristik(r)
        baris.append(r)

    baris.sort(key=lambda b: b["skor_heuristik"], reverse=True)
    out = {
        "hari": hari,
        "diambil_epoch": kini,
        "ttl_s": TTL_S,
        "jumlah": len(baris),
        "diperiksa": kode,
        "maks_ticker": maks_ticker,
        "hasil": baris,
        "galat": galat,
        "catatan": [LABEL_JUJUR, *CATATAN_REPLIKASI],
    }
    try:
        d.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return out
