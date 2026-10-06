"""Rekonsiliasi posisi crypto yang menggantung — "posisi hantu" (6 Okt 2026).

MASALAH NYATA YANG MEMICU MODUL INI
-----------------------------------
Watchlist crypto menyimpan posisi berstatus ``still_open``; posisi itu ditutup oleh
`watchlist-sync` (di Tencent) yang menulis baris ledger. Ketika posisi lenyap dari
daftar "terbuka" **tanpa** baris ledger, tidak ada yang menutupnya di sini: posisi
menggantung selamanya, dan ledger kehilangan R-nya.

Bukti 6 Okt: OP_USDT & LIT_USDT masih ``still_open`` sejak 27 Sep, padahal candle
MEXC menunjukkan keduanya terisi 26/27 Sep dan kena SL pada 28/27 Sep. Akibatnya
ledger melaporkan +3,844R padahal seharusnya +1,844R — selisih 2R yang terlalu
besar untuk dibiarkan.

ATURAN (bukan sekadar tebakan)
------------------------------
1. Hanya posisi berstatus terbuka yang diperiksa; yang sudah ada baris ledger-nya
   TIDAK disentuh (satu posisi = satu baris hasil).
2. Fill dianggap terjadi hanya bila harga benar-benar menyentuh zona entry.
   Tidak menyentuh → hasil ``no_fill`` dengan R 0 (bukan dihitung sebagai kalah).
3. Urutan di dalam satu candle: **SL dicek lebih dulu** (konservatif). Bila candle
   menyentuh SL dan TP sekaligus, kita menganggap kalah — bias ke arah tidak
   menyenangkan diri sendiri.
4. Hasil ditulis dengan ``source="rekonsiliasi"`` + ``note`` berisi bukti candle
   (waktu, harga) supaya setiap R bisa ditelusuri; bukan angka telanjang.
5. Tanpa data candle (jaringan gagal) → **tidak menulis apa pun**; dilempar ke
   ``gagal[]`` dan dilaporkan, bukan ditebak.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = ["rekonstruksi_posisi", "rekonsiliasi_watchlist"]

_KLINE = "https://contract.mexc.com/api/v1/contract/kline/{pair}?interval=Min60&start={start}"
_STATUS_TERBUKA = {"still_open", "open", "pending"}


def _pair_mexc(pair: str) -> str:
    p = str(pair).upper()
    return p if "_" in p else f"{p[:-4]}_USDT" if p.endswith("USDT") else p


def _klines(pair: str, sejak_iso: str, timeout: float = 20.0) -> dict[str, list[float]]:
    t0 = int(datetime.fromisoformat(sejak_iso).timestamp()) - 3600
    req = urllib.request.Request(
        _KLINE.format(pair=_pair_mexc(pair), start=t0),
        headers={"User-Agent": "war-room/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    data = d.get("data") or {}
    return {
        "t": [int(x) for x in (data.get("time") or [])],
        "h": [float(x) for x in (data.get("high") or [])],
        "l": [float(x) for x in (data.get("low") or [])],
    }


def _zona(entry_zone: Any) -> tuple[float, float] | None:
    """Zona entry dari teks '0.1469-0.1476' (juga menerima en-dash)."""
    if entry_zone is None:
        return None
    teks = str(entry_zone).replace("–", "-").replace("—", "-").strip()
    bagian = [b for b in teks.split("-") if b.strip()]
    if len(bagian) != 2:
        return None
    try:
        a, b = float(bagian[0]), float(bagian[1])
    except ValueError:
        return None
    return (min(a, b), max(a, b))


def rekonstruksi_posisi(pos: dict[str, Any], *, ambil_klines=_klines) -> dict[str, Any] | None:
    """Rekonstruksi satu posisi terbuka; ``None`` bila bukan kandidat/tak bisa dinilai."""
    zona = _zona(pos.get("entry_zone"))
    if zona is None or pos.get("date_added") is None:
        return None
    try:
        sl = float(pos["sl"])
        tp1 = float(pos["tp1"])
        tp2 = float(pos.get("tp2") or pos["tp1"])
    except (KeyError, TypeError, ValueError):
        return None

    zl, zh = zona
    is_long = str(pos.get("direction", "LONG")).upper() == "LONG"
    k = ambil_klines(str(pos.get("pair")), str(pos["date_added"]))
    terisi_pada: str | None = None
    for i, ts in enumerate(k["t"]):
        waktu = datetime.fromtimestamp(ts, tz=UTC).isoformat()
        if terisi_pada is None:
            if k["l"][i] <= zh and k["h"][i] >= zl:
                terisi_pada = waktu
            continue
        # SL lebih dulu di candle yang sama (konservatif).
        if is_long and k["l"][i] <= sl:
            return _hasil(pos, "closed_SL", sl, terisi_pada, waktu, "SL", -1.0)
        if not is_long and k["h"][i] >= sl:
            return _hasil(pos, "closed_SL", sl, terisi_pada, waktu, "SL", -1.0)
        if is_long and k["h"][i] >= tp2:
            return _hasil(pos, "closed_TP2", tp2, terisi_pada, waktu, "TP2", 2.0)
        if not is_long and k["l"][i] <= tp2:
            return _hasil(pos, "closed_TP2", tp2, terisi_pada, waktu, "TP2", 2.0)
        if is_long and k["h"][i] >= tp1:
            return _hasil(pos, "closed_TP1", tp1, terisi_pada, waktu, "TP1", 1.0)
        if not is_long and k["l"][i] <= tp1:
            return _hasil(pos, "closed_TP1", tp1, terisi_pada, waktu, "TP1", 1.0)

    if terisi_pada is None:
        # Harga tak pernah masuk zona → order kedaluwarsa, R 0 (bukan kerugian).
        akhir = (
            datetime.fromtimestamp(k["t"][-1], tz=UTC).isoformat() if k["t"] else None
        )
        return _hasil(pos, "expired", None, None, akhir, "TIDAK_FILL", 0.0)
    return None  # sudah terisi tapi belum kena apa-apa → masih jalan, jangan dipaksa


def _hasil(
    pos: dict[str, Any],
    status: str,
    harga: float | None,
    terisi_pada: str | None,
    waktu: str | None,
    label: str,
    r: float,
) -> dict[str, Any]:
    return {
        "signal_id": pos.get("signal_id"),
        "pair": pos.get("pair"),
        "direction": str(pos.get("direction", "")).upper(),
        "closed_at": waktu or datetime.now(UTC).isoformat(),
        "status": status,
        "r": r,
        "note": (
            f"REKONSILIASI candle MEXC 1H: terisi {terisi_pada or '—'} → {label} "
            f"{f'@ {harga}' if harga is not None else ''} pada {waktu or '—'} "
            f"(SL dicek lebih dulu bila satu candle menyentuh dua level)."
        ),
        "source": "rekonsiliasi",
    }


def rekonsiliasi_watchlist(state_dir: Path, *, ambil_klines=_klines) -> dict[str, Any]:
    """Periksa semua posisi terbuka; tulis baris hasil ke ledger crypto.

    Tidak pernah menulis untuk posisi yang sudah punya baris ledger. Gagal mengambil
    candle → masuk ``gagal[]`` (tidak ada tulisan, tidak ada tebakan).
    """
    watch_p = state_dir / "crypto-watchlist.json"
    ledger_p = state_dir / "crypto_equity.jsonl"
    try:
        watch = json.loads(watch_p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "lewati", "alasan": "watchlist tidak terbaca", "baru": [], "gagal": []}

    sudah = set()
    if ledger_p.is_file():
        for ln in ledger_p.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if d.get("signal_id"):
                sudah.add(str(d["signal_id"]))

    terbuka = [
        it for it in (watch.get("items") or [])
        if str(it.get("status")) in _STATUS_TERBUKA and str(it.get("signal_id")) not in sudah
    ]

    baru: list[dict[str, Any]] = []
    gagal: list[dict[str, str]] = []
    for it in terbuka:
        try:
            hasil = rekonstruksi_posisi(it, ambil_klines=ambil_klines)
        except Exception as exc:  # noqa: BLE001 — jaringan gagal bukan alasan mengarang
            gagal.append({"signal_id": str(it.get("signal_id")), "alasan": f"{type(exc).__name__}: {exc}"})
            continue
        if hasil is not None:
            baru.append(hasil)

    if baru:
        with ledger_p.open("a", encoding="utf-8") as fh:
            for baris in baru:
                fh.write(json.dumps(baris, ensure_ascii=False) + "\n")

    return {
        "status": "ok",
        "diperiksa": len(terbuka),
        "baru": baru,
        "gagal": gagal,
        "ledger": str(ledger_p),
    }
