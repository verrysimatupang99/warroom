"""Pengukuran hasil maju — apakah gate-nya benar-benar berguna.

Masalah yang dijawab modul ini: gate kita menolak banyak kandidat dengan alasan yang terdengar
masuk akal. Tapi "terdengar masuk akal" bukan bukti. Selama kita tidak pernah melacak **apa
yang terjadi pada kandidat yang ditolak**, kita tidak akan pernah tahu apakah aturan itu
menyelamatkan kita atau justru membuang setup terbaik.

Caranya: untuk SETIAP kandidat (lolos maupun ditolak), jalankan simulasi yang sama persis —
entry di POI, TP1 = 1R, SL = swing — lalu lihat mana yang kena lebih dulu. Hasilnya disebut
**hasil bayangan** untuk kandidat yang ditolak.

Aturan waktu mengikuti aturan lapangan: expired 8 jam kalau tidak terisi, tahan maksimum 24 jam.
Kalau TP1 dan SL kena di candle yang sama, yang dihitung **SL** — pilihan konservatif, supaya
angka kita tidak dibaguskan oleh asumsi yang menguntungkan diri sendiri.
"""

from __future__ import annotations

import datetime as dt
import json
import statistics
from pathlib import Path
from typing import Any

import httpx

from .collectors import make_client
from .config import Settings

FILL_WINDOW_H = 8  # expired kalau tidak terisi dalam 8 jam (aturan lapangan)
HOLD_MAX_H = 24  # tahan maksimum 24 jam (aturan lapangan)
MIN_AGE_H = 1  # kandidat minimal berumur 1 jam baru bisa dinilai


def _t_stat(nilai: list[float]) -> float | None:
    """t sederhana untuk rata-rata sekumpulan R (None kalau tidak bisa dihitung).

    Dipakai untuk syarat kedua putusan aturan: selain sampel cukup (n>=20), bedanya juga harus
    nyata (|t|>=2). Tanpa itu, aturan berisi belasan hasil yang kebetulan bertanda tertentu
    akan dicap 'berguna'/'merugikan' padahal cuma derau.
    """
    if len(nilai) < 2:
        return None
    sd = statistics.stdev(nilai)
    if sd == 0:
        return None
    return statistics.fmean(nilai) / (sd / len(nilai) ** 0.5)


def load_verdicts(settings: Settings) -> list[dict[str, Any]]:
    path = settings.state_dir / "verdicts.jsonl"
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("entry") and row.get("sl") and row.get("tp1"):
            out.append(row)
    return out


def _fetch_1h(
    settings: Settings, pair: str, start_ms: int, limit: int, client: httpx.Client
) -> list[list[Any]]:
    r = client.get(
        f"{settings.binance_fapi}/fapi/v1/klines",
        params={"symbol": pair, "interval": "1h", "startTime": start_ms, "limit": limit},
    )
    r.raise_for_status()
    return r.json()


def masuk_pasar(
    row: dict[str, Any], klines: list[list[Any]], now: dt.datetime | None = None
) -> dict[str, Any]:
    """Skenario alternatif: masuk di harga pasar saat keputusan, bukan menunggu POI.

    SL dan TP1 tetap level yang sama, jadi (untuk long) risikonya lebih besar dan
    imbalannya lebih kecil. Yang diuji: apakah tambahan peluang terisi sebanding dengan
    R yang lebih buruk. Tanpa ``harga_keputusan`` di baris, skenario ini tidak bisa dinilai.
    """
    now = now or dt.datetime.now(dt.UTC)
    harga = row.get("harga_keputusan")
    if not harga:
        return {"hasil_pasar": "tanpa_harga_keputusan", "r_pasar": None}

    entry, sl, tp1 = float(harga), float(row["sl"]), float(row["tp1"])
    longgar = str(row["direction"]).lower() == "long"
    risk = abs(entry - sl)
    reward = (tp1 - entry) if longgar else (entry - tp1)
    if risk <= 0 or reward <= 0:
        return {"hasil_pasar": "tidak_valid", "r_pasar": None}

    candles = [{"h": float(k[2]), "l": float(k[3]), "c": float(k[4])} for k in klines[: HOLD_MAX_H + 1]]
    if not candles:
        return {"hasil_pasar": "belum_ada_data", "r_pasar": None}

    # Langsung terisi di candle pertama, lalu lacak seperti biasa (SL lebih dulu bila
    # keduanya tersentuh dalam satu candle — sama konservatifnya dengan resolve_one).
    for c in candles:
        if (longgar and c["l"] <= sl) or (not longgar and c["h"] >= sl):
            return {"hasil_pasar": "sl", "r_pasar": -1.0}
        if (longgar and c["h"] >= tp1) or (not longgar and c["l"] <= tp1):
            return {"hasil_pasar": "tp1", "r_pasar": round(reward / risk, 4)}

    terakhir = candles[-1]["c"]
    r_akhir = ((terakhir - entry) if longgar else (entry - terakhir)) / risk
    return {
        "hasil_pasar": "terbuka",
        "r_pasar": round(r_akhir, 4),
    }


def resolve_one(
    row: dict[str, Any],
    klines: list[list[Any]],
    now: dt.datetime | None = None,
    *,
    hold_max_h: int = HOLD_MAX_H,
    isi_penetrasi_bps: float = 0.0,
) -> dict[str, Any]:
    """Lacak satu kandidat: terisi? kena TP1 atau SL? dalam berapa jam?

    ``klines`` = candle 1H Binance (array), sudah dimulai dari waktu verdict.
    """
    now = now or dt.datetime.now(dt.UTC)
    ts = dt.datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))
    umur_jam = (now - ts).total_seconds() / 3600

    entry, sl, tp1 = float(row["entry"]), float(row["sl"]), float(row["tp1"])
    long = str(row["direction"]).lower() == "long"
    risk = abs(entry - sl)

    dasar: dict[str, Any] = {
        "ts": row["ts"],
        "pair": row["pair"],
        "direction": row["direction"],
        "allowed": bool(row.get("allowed")),
        "tier": row.get("tier"),
        "strategy_version": row.get("strategy_version"),
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        # Diteruskan apa adanya: tanpa ini, skenario "masuk di harga pasar" kehilangan
        # harga entry-nya dan biayanya tidak bisa dihitung. Field yang tidak terdaftar
        # di sini akan hilang tanpa suara dari hasil.
        "harga_keputusan": row.get("harga_keputusan"),
        "atr_pct": row.get("atr_pct"),
        "agents": row.get("agents"),
        "rules_gagal": [r["rule"] for r in (row.get("rules") or []) if not r.get("ok")],
        "umur_jam": round(umur_jam, 1),
    }
    if risk <= 0:
        return {**dasar, "hasil": "data_tidak_valid", "r": None}

    candles = [
        {"o": float(k[1]), "h": float(k[2]), "l": float(k[3]), "c": float(k[4]), "t": int(k[0])}
        for k in klines
    ]
    if not candles:
        return {**dasar, "hasil": "belum_ada_data", "r": None}

    # 1) kapan terisi — harga harus menyentuh zona entry
    # ``isi_penetrasi_bps`` membuat syaratnya lebih keras: harga harus menembus level entry
    # sejauh itu, bukan sekadar menyentuh. Dipakai untuk menguji asumsi yang paling lemah
    # di seluruh model ini — bahwa order limit kita benar-benar terisi saat harga menyentuh.
    if isi_penetrasi_bps:
        geser = entry * isi_penetrasi_bps / 10000.0
        entry_isi = entry - geser if long else entry + geser
    else:
        entry_isi = entry

    def _kena(c: dict[str, float]) -> bool:
        return c["l"] <= entry_isi if long else c["h"] >= entry_isi

    fill_idx = next((i for i, c in enumerate(candles[:FILL_WINDOW_H]) if _kena(c)), None)
    if fill_idx is None:
        if umur_jam <= FILL_WINDOW_H:
            return {**dasar, "hasil": "menunggu_terisi", "r": None}
        return {**dasar, "hasil": "tidak_terisi", "r": 0.0}

    # 2) dari titik terisi, mana yang kena lebih dulu
    for i, c in enumerate(candles[fill_idx : fill_idx + hold_max_h]):
        jam = i + 1
        if long:
            if c["l"] <= sl:
                return {**dasar, "hasil": "sl", "r": -1.0, "jam_ke_hasil": jam, "jam_ke_isi": fill_idx + 1}
            if c["h"] >= tp1:
                return {
                    **dasar,
                    "hasil": "tp1",
                    "r": round(abs(tp1 - entry) / risk, 3),
                    "jam_ke_hasil": jam,
                    "jam_ke_isi": fill_idx + 1,
                }
        else:
            if c["h"] >= sl:
                return {**dasar, "hasil": "sl", "r": -1.0, "jam_ke_hasil": jam, "jam_ke_isi": fill_idx + 1}
            if c["l"] <= tp1:
                return {
                    **dasar,
                    "hasil": "tp1",
                    "r": round(abs(entry - tp1) / risk, 3),
                    "jam_ke_hasil": jam,
                    "jam_ke_isi": fill_idx + 1,
                }

    # 3) belum kena apa-apa — nilai pada harga terakhir (mark), jangan dipaksa jadi 0
    last = candles[min(fill_idx + hold_max_h, len(candles)) - 1]["c"]
    r_now = (last - entry) / risk if long else (entry - last) / risk
    return {
        **dasar,
        "hasil": "terbuka" if umur_jam < hold_max_h else "kedaluwarsa",
        "r": round(r_now, 3),
        "jam_ke_isi": fill_idx + 1,
    }


def outcomes(
    settings: Settings, *, client: httpx.Client | None = None, now: dt.datetime | None = None
) -> list[dict[str, Any]]:
    """Lacak semua kandidat yang sudah cukup umur. Ini sumber kebenaran pengukuran."""
    now = now or dt.datetime.now(dt.UTC)
    rows = load_verdicts(settings)
    own = client is None
    c = client or make_client(timeout=25.0)
    out: list[dict[str, Any]] = []
    try:
        for row in rows:
            ts = dt.datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))
            if (now - ts).total_seconds() / 3600 < MIN_AGE_H:
                continue
            start_ms = int(ts.timestamp() * 1000)
            try:
                klines = _fetch_1h(settings, row["pair"], start_ms, FILL_WINDOW_H + HOLD_MAX_H + 2, c)
            except Exception as exc:  # noqa: BLE001
                out.append(
                    {
                        "ts": row["ts"],
                        "pair": row["pair"],
                        "hasil": "gagal_ambil_data",
                        "r": None,
                        "catatan": str(exc)[:80],
                    }
                )
                continue
            hasil = resolve_one(row, klines, now)
            # Skenario pembanding: masuk di harga pasar, dan target 2R.
            hasil.update(masuk_pasar(row, klines, now))
            hasil.update(resolve_tp2(row, klines, now))
            out.append(hasil)
    finally:
        if own:
            c.close()
    return out


def resolve_tp2(
    row: dict[str, Any], klines: list[list[Any]], now: dt.datetime | None = None
) -> dict[str, Any]:
    """Hasil kalau targetnya 2R (TP2), bukan 1R (TP1).

    Biaya per trade tetap sama dalam satuan R, sementara imbalannya dua kali. Kalau biaya
    yang memakan edge pada target 1R, target yang lebih jauh bisa lebih baik — tapi hanya
    kalau peluang kena 2R tidak turun terlalu banyak. Itu yang diukur, bukan diterka.
    """
    now = now or dt.datetime.now(dt.UTC)
    entry, sl = float(row["entry"]), float(row["sl"])
    long = str(row["direction"]).lower() == "long"
    risk = abs(entry - sl)
    if risk <= 0:
        return {"hasil_tp2": "data_tidak_valid", "r_tp2": None}
    target = entry + 2 * risk if long else entry - 2 * risk

    candles = [{"h": float(k[2]), "l": float(k[3]), "c": float(k[4])} for k in klines[: HOLD_MAX_H + 1]]
    if not candles:
        return {"hasil_tp2": "belum_ada_data", "r_tp2": None}

    fill_idx = next((i for i, c in enumerate(candles[:FILL_WINDOW_H]) if c["l"] <= entry <= c["h"]), None)
    if fill_idx is None:
        return {"hasil_tp2": "tidak_terisi", "r_tp2": None}

    for c in candles[fill_idx : fill_idx + HOLD_MAX_H]:
        if (long and c["l"] <= sl) or (not long and c["h"] >= sl):
            return {"hasil_tp2": "sl", "r_tp2": -1.0}
        if (long and c["h"] >= target) or (not long and c["l"] <= target):
            return {"hasil_tp2": "tp2", "r_tp2": 2.0}

    terakhir = candles[min(fill_idx + HOLD_MAX_H, len(candles)) - 1]["c"]
    r_akhir = ((terakhir - entry) if long else (entry - terakhir)) / risk
    return {"hasil_tp2": "terbuka", "r_tp2": round(r_akhir, 4)}


def ekskursi(row: dict[str, Any], klines: list[list[Any]], now: dt.datetime | None = None) -> dict[str, Any]:
    """Seberapa jauh trade bergerak menguntungkan (MFE) dan merugikan (MAE), dalam satuan R.

    Disimpan supaya pilihan target bisa diuji tanpa menjalankan backtest ulang: dari
    sebaran MFE, peluang kena target T pada R tertentu bisa dibaca langsung. Ini juga
    yang menunjukkan apakah target 1R terlalu dekat setelah biaya diperhitungkan.
    """
    _ = now
    entry, sl = float(row["entry"]), float(row["sl"])
    long = str(row["direction"]).lower() == "long"
    risk = abs(entry - sl)
    if risk <= 0:
        return {"r_mfe": None, "r_mae": None}

    candles = [{"h": float(k[2]), "l": float(k[3])} for k in klines[: HOLD_MAX_H + 1]]
    fill_idx = next((i for i, c in enumerate(candles[:FILL_WINDOW_H]) if c["l"] <= entry <= c["h"]), None)
    if fill_idx is None:
        return {"r_mfe": None, "r_mae": None}

    jendela = candles[fill_idx : fill_idx + HOLD_MAX_H]
    if not jendela:
        return {"r_mfe": None, "r_mae": None}
    if long:
        mfe = max(c["h"] for c in jendela)
        mae = min(c["l"] for c in jendela)
        return {"r_mfe": round((mfe - entry) / risk, 3), "r_mae": round((mae - entry) / risk, 3)}
    mfe = min(c["l"] for c in jendela)
    mae = max(c["h"] for c in jendela)
    return {"r_mfe": round((entry - mfe) / risk, 3), "r_mae": round((entry - mae) / risk, 3)}


def rows_entering_market(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Konversi baris ke skenario masuk di harga pasar.

    Dipakai bersama oleh pengukuran hidup dan backtest, supaya keduanya mengukur hal
    yang sama — kalau masing-masing punya konversi sendiri, keduanya akan menyimpang.
    """
    out = []
    for r in rows:
        if r.get("r_pasar") is None or not r.get("harga_keputusan"):
            continue
        q = dict(r)
        q["entry"] = float(r["harga_keputusan"])
        q["r"] = r["r_pasar"]
        q["hasil"] = r["hasil_pasar"]
        out.append(q)
    return out


def _ringkas(rows: list[dict[str, Any]]) -> dict[str, Any]:
    import statistics

    selesai = [
        r
        for r in rows
        if r.get("r") is not None and r["hasil"] in ("tp1", "tp2", "sl", "kedaluwarsa", "terbuka")
    ]
    tp1 = [r for r in selesai if r["hasil"] == "tp1"]
    sl = [r for r in selesai if r["hasil"] == "sl"]
    total_r = sum(r["r"] for r in selesai)
    n = len(selesai)
    return {
        "n": n,
        "tp1": len(tp1),
        "sl": len(sl),
        "winrate": round(len(tp1) / n * 100, 1) if selesai else None,
        "total_r": round(total_r, 3),
        "expectancy_r": round(total_r / n, 3) if selesai else None,
        "median_r": round(statistics.median([r["r"] for r in selesai]), 3) if selesai else None,
        "sampel_cukup": n >= 50,
    }


def atribusi_agent(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Rata-rata R per agent berdasarkan kesepakatan arah — HIPOTESIS, bukan putusan.

    Aturan main sama ketatnya dengan per_aturan: n<20 = belum dapat
    disimpulkan. Bedanya, agent tidak pernah menolak kandidat (tidak ada gate),
    jadi yang diukur hanya: ketika agent setuju arah, hasilnya lebih baik atau
    tidak dibanding ketika tidak setuju / tidak vote.
    """
    slot: dict[str, dict[str, Any]] = {}
    for r in rows:
        if r.get("r") is None or r.get("hasil") in (
            "menunggu_terisi", "belum_ada_data", "gagal_ambil_data",
        ):
            continue
        arah = str(r.get("direction", "")).lower()
        agents = r.get("agents") or {}
        for nama, a in (agents.get("agents") or {}).items():
            bias = (a or {}).get("bias")
            s = slot.setdefault(nama, {"n": 0, "setuju_r": [], "tak_setuju_r": []})
            s["n"] += 1
            if bias is None:
                continue
            setuju = (bias > 0 and arah == "long") or (bias < 0 and arah == "short")
            s["setuju_r" if setuju else "tak_setuju_r"].append(float(r["r"]))
    out: dict[str, Any] = {}
    for nama, s in slot.items():
        setuju, tak = s["setuju_r"], s["tak_setuju_r"]
        cukup = s["n"] >= 20
        out[nama] = {
            "n": s["n"],
            "n_setuju": len(setuju),
            "n_tak_setuju": len(tak),
            "avg_setuju_r": round(sum(setuju) / len(setuju), 3) if setuju else None,
            "avg_tak_setuju_r": round(sum(tak) / len(tak), 3) if tak else None,
            "putusan": "cukup sampel — bandingkan avg" if cukup else "belum dapat disimpulkan (sampel kecil)",
        }
    return out


FINAL = {
    "tp1",
    "tp2",
    "sl",
    "tidak_terisi",
    "kedaluwarsa",
    "data_tidak_valid",
    "gagal_ambil_data",
}


def _cache_path(settings: Settings) -> Path:
    return settings.state_dir / "outcomes.jsonl"


def _load_cache(settings: Settings) -> dict[tuple[str, str], dict[str, Any]]:
    path = _cache_path(settings)
    if not path.is_file():
        return {}
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        out[(row.get("ts", ""), row.get("pair", ""))] = row
    return out


def outcomes_cached(
    settings: Settings, *, client: httpx.Client | None = None, now: dt.datetime | None = None
) -> list[dict[str, Any]]:
    """Seperti :func:`outcomes`, tapi hasil akhir dipakai ulang.

    Tanpa cache, dashboard akan menarik ulang candle untuk setiap kandidat lama setiap kali
    snapshot dibangun. Dengan cache, hanya kandidat baru atau yang belum selesai yang
    diambil — hasil yang sudah final tidak pernah dihitung dua kali.
    """
    now = now or dt.datetime.now(dt.UTC)
    cache = _load_cache(settings)
    rows = load_verdicts(settings)
    own = client is None
    c = client or make_client(timeout=25.0)
    hasil: list[dict[str, Any]] = []
    berubah = False
    try:
        for row in rows:
            key = (row["ts"], row["pair"])
            lama = cache.get(key)
            if lama and lama.get("hasil") in FINAL:
                hasil.append(lama)
                continue
            ts = dt.datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))
            if (now - ts).total_seconds() / 3600 < MIN_AGE_H:
                continue
            try:
                klines = _fetch_1h(
                    settings, row["pair"], int(ts.timestamp() * 1000), FILL_WINDOW_H + HOLD_MAX_H + 2, c
                )
                baru = resolve_one(row, klines, now)
            except Exception as exc:  # noqa: BLE001
                baru = {
                    "ts": row["ts"],
                    "pair": row["pair"],
                    "hasil": "gagal_ambil_data",
                    "r": None,
                    "catatan": str(exc)[:80],
                }
            hasil.append(baru)
            berubah = True
    finally:
        if own:
            c.close()

    if berubah:
        try:
            _cache_path(settings).parent.mkdir(parents=True, exist_ok=True)
            # Atomik: dashboard membaca berkas ini tiap 15 menit dan tidak boleh
            # menemukannya separuh tertulis.
            tmp = _cache_path(settings).with_suffix(".jsonl.tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                for r in hasil:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            tmp.replace(_cache_path(settings))
        except OSError:
            pass
    return hasil


def report(
    settings: Settings, *, client: httpx.Client | None = None, now: dt.datetime | None = None
) -> dict[str, Any]:
    """Laporan lengkap: hasil kandidat lolos vs ditolak (bayangan), lalu lift per aturan.

    Perbandingannya begini:
    - Kalau kandidat yang DITOLAK punya rata-rata R negatif → gate menyaring dengan benar.
    - Kalau kandidat yang ditolak justru positif → aturan itu sedang membuang uang kita,
      dan itu harus terlihat, bukan disembunyikan.
    """
    rows = outcomes_cached(settings, client=client, now=now)
    lolos = [r for r in rows if r.get("allowed")]
    ditolak = [r for r in rows if r.get("allowed") is False]

    per_aturan: dict[str, dict[str, Any]] = {}
    for r in ditolak:
        gagal = r.get("rules_gagal") or []
        if len(gagal) != 1:
            continue  # hanya kandidat yang ditolak SATU aturan: mengukur aturan itu bersih
        slot = per_aturan.setdefault(gagal[0], {"n": 0, "total_r": 0.0, "tp1": 0, "sl": 0, "r": []})
        if r.get("r") is None or r["hasil"] in ("menunggu_terisi", "belum_ada_data", "gagal_ambil_data"):
            continue
        slot["n"] += 1
        slot["total_r"] += r["r"]
        slot["r"].append(r["r"])
        slot["tp1"] += 1 if r["hasil"] == "tp1" else 0
        slot["sl"] += 1 if r["hasil"] == "sl" else 0

    aturan: dict[str, Any] = {}
    for rule, s in per_aturan.items():
        if not s["n"]:
            continue
        # Putusan "berguna/merugikan" butuh DUA syarat, sama seperti di backtest:
        # sampel cukup (n>=20) DAN bedanya nyata (|t|>=2). Tanpa syarat kedua, aturan dengan
        # hasil persis di sekitar nol akan dicap "merugikan" hanya karena tandanya kebetulan.
        rerata = s["total_r"] / s["n"]
        t = _t_stat(s["r"]) if s["n"] >= 2 else None
        cukup = s["n"] >= 20
        if not cukup:
            putusan = "belum dapat disimpulkan (sampel kecil)"
        elif t is not None and abs(t) >= 2.0:
            putusan = "berguna" if rerata < 0 else "merugikan"
        else:
            putusan = "tidak bisa dibedakan dari derau"
        aturan[rule] = {
            "n": s["n"],
            "expectancy_r": round(rerata, 3),
            "t": round(t, 2) if t is not None else None,
            "tp1": s["tp1"],
            "sl": s["sl"],
            "sampel_cukup": cukup,
            "putusan": putusan,
        }

    return {
        "total_tercatat": len(load_verdicts(settings)),
        "dinilai": len(rows),
        "lolos": _ringkas(lolos),
        "ditolak_bayangan": _ringkas(ditolak),
        # Pembanding: kalau kandidat yang tidak pernah terisi kita masuki di harga pasar.
        "masuk_pasar": _ringkas(rows_entering_market(rows)),
        "per_aturan": aturan,
        "per_agent": atribusi_agent(rows),
        "rows": rows,
    }
