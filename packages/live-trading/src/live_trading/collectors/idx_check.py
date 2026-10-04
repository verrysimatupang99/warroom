"""Cross-check IDX: temuan Arjum (bandarmologi) vs keadaan harga di TradingView.

Kenapa ini ada: Arjum memberi sinyal berbasis aliran dana (akumulasi, distribusi), sementara
TradingView memberi keadaan harga. Dua sumber yang setuju jauh lebih berharga daripada satu
sumber yang yakin — dan yang bertentangan justru temuan, bukan gangguan. Ini cara yang sama
dipakai pada catatan RE sebelumnya (validasi silang movers harian, 46/47 cocok).

Batasnya diakui: TradingView tidak memberi riwayat, jadi yang dibandingkan adalah **keadaan**
(EMA8 di atas/bawah EMA21), bukan "cross baru".
"""

from __future__ import annotations

from typing import Any

from .idx_tv import _post  # pemakaian ulang: transport + header sudah benar di sana

TV_COLUMNS = ["name", "close", "change", "volume", "RSI", "EMA8", "EMA21", "market_cap_basic"]

AKUMULASI = ("SINYAL BERSIH", "AKUMULASI SENYAP", "SINYAL SENYAP")
WASPADA = ("RISIKO PANTULAN", "KONFLIK DISTRIBUSI")


def klasifikasi_bucket(bucket: str) -> str:
    """Terjemahkan label bucket Arjum menjadi maksudnya, tanpa bergantung pada emoji."""
    teks = (bucket or "").upper()
    if any(k in teks for k in AKUMULASI):
        return "akumulasi"
    if any(k in teks for k in WASPADA):
        return "waspada"
    return "netral"


def tv_snapshot(tickers: list[str]) -> dict[str, dict[str, Any]]:
    """Ambil keadaan harga untuk ticker tertentu saja."""
    if not tickers:
        return {}
    body = {
        "options": {"lang": "id"},
        "markets": ["indonesia"],
        "symbols": {"tickers": [f"IDX:{t.upper()}" for t in tickers], "query": {"types": []}},
        "columns": TV_COLUMNS,
    }
    data = _post(body)
    out: dict[str, dict[str, Any]] = {}
    for row in data.get("data", []):
        d = dict(zip(TV_COLUMNS, row["d"], strict=False))
        ema8, ema21 = d.get("EMA8"), d.get("EMA21")
        if ema8 and ema21:
            ema_state = "naik" if ema8 > ema21 else "turun"
        else:
            ema_state = "n/a"
        out[str(d.get("name", "")).upper()] = {
            "close": d.get("close"),
            "change_pct": d.get("change"),
            "volume": d.get("volume"),
            "rsi14": d.get("RSI"),
            "ema_state": ema_state,
            "market_cap": d.get("market_cap_basic"),
        }
    return out


def gabungkan(arjum_rows: list[dict[str, Any]], tv: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Gabungkan temuan Arjum dengan keadaan harga, lalu nilai apakah keduanya sejalan."""
    hasil: list[dict[str, Any]] = []
    for row in arjum_rows:
        kode = str(row.get("stock_code", "")).upper()
        harga = tv.get(kode) or {}
        maksud = klasifikasi_bucket(str(row.get("bucket", "")))
        ema = harga.get("ema_state", "n/a")

        if maksud == "akumulasi" and ema == "naik":
            putusan, alasan = "sejalan", "sinyal akumulasi dan harga di atas EMA"
        elif maksud == "akumulasi" and ema == "turun":
            putusan, alasan = "bertentangan", "screener bilang akumulasi, harga masih di bawah EMA"
        elif maksud == "waspada" and ema == "turun":
            putusan, alasan = "sejalan", "peringatan risiko dan harga memang lemah"
        elif maksud == "waspada" and ema == "naik":
            putusan, alasan = "bertentangan", "screener minta hati-hati, harga justru di atas EMA"
        else:
            putusan, alasan = "netral", "tidak ada data pembanding yang cukup"

        hasil.append({
            "kode": kode,
            "nama": row.get("stock_name"),
            "bucket": row.get("bucket"),
            "maksud": maksud,
            "wr_event": row.get("wr_event"),
            "potensi": row.get("potential"),
            "harga": harga.get("close"),
            "chg_pct": harga.get("change_pct"),
            "rsi14": harga.get("rsi14"),
            "ema_state": ema,
            "putusan": putusan,
            "alasan": alasan,
        })
    return hasil
