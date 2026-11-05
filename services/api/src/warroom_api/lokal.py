"""Sumber data lokal untuk War Room — pengganti node upstream yang hilang.

Latar: seluruh data crypto/forex/IDX dulu diambil dari satu node di luar server
lewat Tailscale. Node itu sudah tidak ada. Modul ini mengambil data langsung
dari sumber publik, tanpa kredensial dan tanpa perantara:

  - Crypto  : OKX public API (tanpa key), fallback MEXC bila OKX gagal.
              Field `sumber`/`source` selalu menyebut siapa yang benar-benar
              menjawab — tidak pernah mengklaim OKX saat yang dipakai fallback.
  - Forex   : Yahoo Finance chart API (butuh User-Agent; tanpa UA dibalas 429).
  - IDX     : Yahoo Finance untuk IHSG (^JKSE).

Prinsip: kalau sebuah data tidak bisa diambil, endpoint mengembalikan 503 dengan
alasan yang jelas. Tidak ada angka karangan, tidak ada nilai default palsu.
"""
from __future__ import annotations

import asyncio
import csv
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
from warroom_core.deal_koreksi import KOREKSI_DEFAULT, baca_koreksi, terapkan
from warroom_core.mt5_accounts import snapshot_key

from warroom_api import jurnal_crypto, jurnal_forex

UA = "Mozilla/5.0 (X11; Linux x86_64) WarRoom/2.0"
MEXC = "https://api.mexc.com"
OKX = "https://www.okx.com"
YAHOO = "https://query2.finance.yahoo.com"
TIMEOUT = 12.0

# Pemetaan interval yang dipakai UI ke format masing-masing penyedia.
_INTERVAL_MEXC = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
                  "1h": "60m", "60": "60m", "4h": "4h", "1d": "1d"}
_INTERVAL_OKX = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
                 "1h": "1H", "60": "1H", "4h": "4H", "1d": "1D"}
# Yahoo memakai 60m untuk per jam, dan rentang harus cocok dengan intervalnya.
_INTERVAL_YAHOO = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
                   "1h": "60m", "60": "60m", "1d": "1d"}
_RANGE_YAHOO = {"1m": "1d", "5m": "5d", "15m": "1mo", "30m": "1mo",
                "60m": "1mo", "60": "1mo", "1d": "6mo"}

_SIMBOL_YAHOO = {
    # XAUUSD spot tidak tersedia di Yahoo (404). Yang ada kontrak futures
    # COMEX (GC=F); harganya bergerak bersama spot dengan selisih basis kecil.
    # Untuk level dan candle jangka pendek selisih ini dapat diterima, tetapi
    # jangan dipakai sebagai harga eksekusi.
    "XAUUSD": "GC=F",
    "DXY": "DX-Y.NYB",
    "IHSG": "^JKSE",
}


class SumberKosong(RuntimeError):
    """Data tidak tersedia dari sumber mana pun."""


async def _get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": UA}) as c:
        r = await c.get(url, params=params)
        if r.status_code != 200:
            raise SumberKosong(f"{url} -> HTTP {r.status_code}")
        return r.json()


# ---------------------------------------------------------------- crypto ---


def _simbol_ke_okx(simbol: str) -> str:
    """`BTCUSDT` (gaya UI/MEXC) -> `BTC-USDT` (gaya OKX spot)."""
    s = simbol.upper().strip()
    if "-" in s:
        return s
    if s.endswith("USDT") and len(s) > 4:
        return s[:-4] + "-USDT"
    return s


def _simbol_dari_okx(inst_id: str) -> str:
    """`BTC-USDT` -> `BTCUSDT` (bentuk yang dipakai UI)."""
    return inst_id.upper().replace("-", "")


# ---------------------------------------------------------------- crypto ---


async def _okx_universe(jumlah: int) -> dict[str, Any]:
    data = await _get_json(f"{OKX}/api/v5/market/tickers", {"instType": "SPOT"})
    if str(data.get("code")) != "0":
        raise SumberKosong(f"OKX tickers code={data.get('code')}")
    rows = [t for t in (data.get("data") or []) if str(t.get("instId", "")).endswith("-USDT")]
    rows.sort(key=lambda t: float(t.get("volCcy24h") or 0), reverse=True)
    return {
        "symbols": [_simbol_dari_okx(t["instId"]) for t in rows[:jumlah]],
        "total": len(rows),
        "sumber": "okx-lokal",
        "diambil": int(time.time()),
    }


async def _mexc_universe(jumlah: int) -> dict[str, Any]:
    """Fallback lama bila OKX tidak bisa dihubungi."""
    ticker = await _get_json(f"{MEXC}/api/v3/ticker/24hr")
    if not isinstance(ticker, list):
        raise SumberKosong("ticker MEXC bukan list")
    koin = [t for t in ticker if str(t.get("symbol", "")).endswith("USDT")]
    koin.sort(key=lambda t: float(t.get("quoteVolume") or 0), reverse=True)
    return {
        "symbols": [t["symbol"] for t in koin[:jumlah]],
        "total": len(koin),
        "sumber": "mexc-lokal (fallback)",
        "diambil": int(time.time()),
    }


async def crypto_universe(jumlah: int = 80) -> dict[str, Any]:
    """Pasangan USDT aktif, diurutkan menurut volume 24 jam. OKX dulu, MEXC cadangan."""
    try:
        return await _okx_universe(jumlah)
    except SumberKosong:
        return await _mexc_universe(jumlah)


async def _okx_ticker(simbol: str) -> dict[str, Any]:
    inst = _simbol_ke_okx(simbol)
    data = await _get_json(f"{OKX}/api/v5/market/ticker", {"instId": inst})
    rows = data.get("data") or []
    if str(data.get("code")) != "0" or not rows:
        raise SumberKosong(f"ticker OKX {inst} kosong (code={data.get('code')})")
    d = rows[0]
    last = float(d.get("last") or 0)
    high = float(d.get("high24h") or 0)
    low = float(d.get("low24h") or 0)
    buka = float(d.get("open24h") or 0)
    ubah = ((last - buka) / buka * 100) if buka else 0.0
    return {
        "symbol": _simbol_dari_okx(inst),
        "last_price": last,
        "high_": high,
        "low_": low,
        "change_pct_": ubah,
        "volume_": float(d.get("volCcy24h") or 0),
        "source": "okx-lokal",
    }


async def _mexc_ticker(simbol: str) -> dict[str, Any]:
    d = await _get_json(f"{MEXC}/api/v3/ticker/24hr", {"symbol": simbol.upper()})
    if isinstance(d, list):
        d = d[0] if d else {}
    if not d:
        raise SumberKosong(f"ticker {simbol} kosong")
    return {
        "symbol": d.get("symbol"),
        "last_price": float(d.get("lastPrice") or 0),
        "high_": float(d.get("highPrice") or 0),
        "low_": float(d.get("lowPrice") or 0),
        "change_pct_": float(d.get("priceChangePercent") or 0),
        "volume_": float(d.get("quoteVolume") or 0),
        "source": "mexc-lokal (fallback)",
    }


async def crypto_ticker(simbol: str) -> dict[str, Any]:
    try:
        return await _okx_ticker(simbol)
    except SumberKosong:
        return await _mexc_ticker(simbol)


async def _okx_klines(simbol: str, interval: str = "1h", limit: int = 15) -> dict[str, Any]:
    bar = _INTERVAL_OKX.get(interval)
    if not bar:
        raise SumberKosong(f"interval {interval} tidak didukung OKX")
    inst = _simbol_ke_okx(simbol)
    data = await _get_json(
        f"{OKX}/api/v5/market/candles",
        {"instId": inst, "bar": bar, "limit": str(max(2, min(int(limit), 300)))},
    )
    if str(data.get("code")) != "0":
        raise SumberKosong(f"OKX candles {inst} code={data.get('code')}")
    mentah = data.get("data") or []
    # OKX mengembalikan terbaru dulu; grafik butuh menaik.
    mentah = sorted(mentah, key=lambda r: int(r[0]))
    return {
        "candles": [
            {"t": int(r[0]), "o": float(r[1]), "h": float(r[2]),
             "l": float(r[3]), "c": float(r[4]), "v": float(r[5])}
            for r in mentah
        ],
        "sumber": "okx-lokal",
    }


async def _mexc_klines(simbol: str, interval: str = "1h", limit: int = 15) -> dict[str, Any]:
    iv = _INTERVAL_MEXC.get(interval)
    if not iv:
        raise SumberKosong(f"interval {interval} tidak didukung MEXC")
    mentah = await _get_json(
        f"{MEXC}/api/v3/klines",
        {"symbol": simbol.upper(), "interval": iv, "limit": max(2, min(int(limit), 500))},
    )
    return {
        "candles": [
            {"t": r[0], "o": float(r[1]), "h": float(r[2]),
             "l": float(r[3]), "c": float(r[4]), "v": float(r[5])}
            for r in mentah
        ],
        "sumber": "mexc-lokal (fallback)",
    }


async def crypto_klines(simbol: str, interval: str = "1h", limit: int = 15) -> dict[str, Any]:
    try:
        return await _okx_klines(simbol, interval, limit)
    except SumberKosong:
        return await _mexc_klines(simbol, interval, limit)


# ------------------------------------------------------- forex & indeks ---


async def yahoo_candles(simbol_yahoo: str, interval: str, limit: int) -> dict[str, Any]:
    iv = _INTERVAL_YAHOO.get(interval)
    if not iv:
        raise SumberKosong(f"interval {interval} tidak didukung Yahoo")
    rentang = _RANGE_YAHOO.get(interval, "1mo")
    d = await _get_json(
        f"{YAHOO}/v8/finance/chart/{simbol_yahoo}",
        {"range": rentang, "interval": iv},
    )
    hasil = (d.get("chart") or {}).get("result") or []
    if not hasil:
        raise SumberKosong(f"Yahoo tidak mengembalikan data untuk {simbol_yahoo}")
    r0 = hasil[0]
    ts = r0.get("timestamp") or []
    q = ((r0.get("indicators") or {}).get("quote") or [{}])[0]
    o, h, lo, c, v = (q.get(k) or [] for k in ("open", "high", "low", "close", "volume"))
    candles = []
    for i, t in enumerate(ts):
        try:
            if c[i] is None:
                continue
            candles.append({
                "t": t * 1000,
                "o": round(float(o[i]), 5),
                "h": round(float(h[i]), 5),
                "l": round(float(lo[i]), 5),
                "c": round(float(c[i]), 5),
                "v": float(v[i] or 0) if i < len(v) else 0.0,
            })
        except (IndexError, TypeError, ValueError):
            continue
    return {"candles": candles[-int(limit):], "sumber": f"yahoo:{simbol_yahoo}"}


async def forex_klines(simbol: str, interval: str = "60", limit: int = 15) -> dict[str, Any]:
    nama = _SIMBOL_YAHOO.get(simbol.upper(), f"{simbol.upper()}=X")
    return await yahoo_candles(nama, str(interval), limit)


async def forex_dxy() -> dict[str, Any]:
    d = await yahoo_candles("DX-Y.NYB", "1d", 2)
    c = d["candles"]
    if len(c) < 1:
        raise SumberKosong("DXY kosong")
    akhir, sebelum = c[-1]["c"], (c[-2]["c"] if len(c) > 1 else c[-1]["o"])
    return {
        "price": akhir,
        "value": akhir,
        "change_pct": round((akhir - sebelum) / sebelum * 100, 3) if sebelum else 0.0,
        "source": "yahoo:dx-y",
    }


async def idx_market() -> dict[str, Any]:
    """Ringkas IHSG dari candle harian. Bukan scanner IDX, hanya kondisi pasar."""
    d = await yahoo_candles("^JKSE", "1d", 30)
    c = d["candles"]
    if len(c) < 2:
        raise SumberKosong("IHSG kosong")
    akhir, sebelum = c[-1], c[-2]
    return {
        "symbol": "IHSG",
        "last": akhir["c"],
        "open": akhir["o"],
        "high": akhir["h"],
        "low": akhir["l"],
        "change_pct": round((akhir["c"] - sebelum["c"]) / sebelum["c"] * 100, 3),
        "volume": akhir["v"],
        "sumber": "yahoo:jkse",
        "candles": c[-20:],
    }


async def idx_stats() -> dict[str, Any]:
    m = await idx_market()
    return {
        "market": "IDX",
        "ihsg": m["last"],
        "change_pct": m["change_pct"],
        "high": m["high"],
        "low": m["low"],
        "volume": m["volume"],
        "sumber": m["sumber"],
        "catatan": "Ringkasan IHSG dari sumber publik. Scanner, ledger sinyal, "
                   "dan aliran dana IDX belum tersedia secara lokal.",
    }


# ------------------------------------------------------------- jurnal ---


def _jalur_env(nama: str, bawaan: str) -> Path:
    v = os.environ.get(nama)
    return Path(v) if v else Path(bawaan)


FILLS = Path("/var/lib/warroom/fills.csv")
DEALS = Path("/var/lib/warroom/deals.csv")
VERDICTS = Path("/home/admin/live-trading/state/verdicts.jsonl")
# Bisa dioverride (CI/e2e menunjuk ke berkas sintetis; produksi tetap /var/lib).
JURNAL_SINYAL = _jalur_env("WARROOM_JURNAL_SINYAL", "/var/lib/warroom/jurnal_sinyal.json")
MOMENTUM_STATE = Path("/var/lib/warroom/momentum_paper.json")
MOMENTUM_TRADES = Path("/var/lib/warroom/momentum_trades.csv")

MARKET_SAH = ("all", "forex", "crypto")


def _cek_market(market: str) -> str:
    m = (market or "all").lower()
    return m if m in MARKET_SAH else "all"


def _baca_momentum() -> dict[str, Any] | None:
    if not MOMENTUM_STATE.exists():
        return None
    try:
        st = json.loads(MOMENTUM_STATE.read_text())
    except (OSError, ValueError):
        return None
    return st if isinstance(st, dict) else None


def _ringkas_momentum() -> dict[str, Any]:
    """Ringkas dompet paper crypto. State disimpan per koin, bukan sebagai total."""
    st = _baca_momentum()
    if not st:
        return {"aktif": False}
    ekuitas = 0.0
    posisi = 0
    for p in st.values():
        harga = p.get("harga") or p.get("entry") or 0.0
        ekuitas += float(p.get("kas") or 0.0) + float(p.get("qty") or 0.0) * float(harga)
        if float(p.get("qty") or 0.0) > 0:
            posisi += 1
    modal = 500.0 * len(st)
    return {
        "aktif": True,
        "koin": len(st),
        "modal": round(modal, 2),
        "ekuitas": round(ekuitas, 2),
        "return_pct": round((ekuitas / modal - 1) * 100, 2) if modal else 0.0,
        "posisi": posisi,
    }


def _baca_csv(p: Path) -> list[dict[str, Any]]:
    if not p.exists():
        return []
    try:
        with p.open(newline="") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def _trade_crypto() -> list[dict[str, Any]]:
    """Trade paper crypto: ledger `crypto_equity.jsonl`, cadangan momentum lama.

    Ledger diutamakan karena itu yang benar-benar dijalankan `paper-scan`.
    Cadangan hanya dipakai bila ledger tidak ada/kosong, supaya jurnal crypto
    tidak tiba-tiba kosong saat ledger sedang ditulis ulang.
    """
    hasil = jurnal_crypto.dari_db()
    if hasil:
        return hasil
    # DB belum terisi (job sync belum jalan) → baca ledger langsung, jangan kosong.
    hasil = jurnal_crypto.dari_ledger()
    if hasil:
        return hasil
    for r in _baca_csv(MOMENTUM_TRADES):
        aksi = str(r.get("aksi", "")).upper()
        hasil.append(
            {
                "iso": str(r.get("waktu", ""))[:19].replace("T", " "),
                "symbol": r.get("koin", ""),
                "side": "BUY" if aksi.startswith("BELI") else "SELL",
                "direction": "",
                "volume": r.get("qty", ""),
                "price_filled": r.get("harga", ""),
                "slippage_pts": "",
                "latency_ms": "",
                "pnl_pct": r.get("pnl_pct", ""),
                "r": "",
                "status": "",
                "strategi": r.get("alasan", ""),
                "fee_usd": "",
                "keterangan": "",
                "market": "crypto",
                "sumber": "momentum_trades",
            }
        )
    return hasil


def _trade_forex() -> list[dict[str, Any]]:
    """Trade forex tertutup: DB `trades` dulu, cadangan `deals.csv`.

    DB diisi `trades-forex-sync` dari `deals.csv`. Bila DB kosong (EA belum
    pernah melapor atau job belum jalan), baca berkasnya langsung supaya jurnal
    tidak tiba-tiba kosong saat sinkronisasi tertunda.
    """
    hasil = jurnal_forex.dari_db()
    if hasil:
        return hasil
    hasil = []
    for r in _baca_deals():
        hasil.append(
            {
                "iso": r.get("iso", ""),
                "symbol": r.get("symbol", ""),
                "side": r.get("side", ""),
                "volume": r.get("volume", ""),
                "price_filled": r.get("close_price", ""),
                "open_price": r.get("open_price", ""),
                "slippage_pts": "",
                "latency_ms": "",
                "pnl_usd": r.get("net", ""),
                "pnl_pct": "",
                "ticket": r.get("ticket", ""),
                "account": r.get("account") or "unknown",
                "strategy_version": r.get("strategy_version") or "unknown",
                "market": "forex",
            }
        )
    return hasil


def _baca(kueri: str, param: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Baca DB secara sinkron. Dipanggil lewat thread supaya loop tetap jalan."""
    from sqlalchemy import text
    from warroom_core.db import session_scope

    with session_scope() as s:
        hasil = s.execute(text(kueri), param or {}).fetchall()
        return [dict(r._mapping) for r in hasil]


async def _db(kueri: str, param: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_baca, kueri, param)


def _baca_fills() -> list[dict[str, Any]]:
    if not FILLS.exists():
        return []
    try:
        with FILLS.open(newline="") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []

def _baca_deals() -> list[dict[str, Any]]:
    """Deal tertutup (satu baris per posisi) yang dilaporkan EA, sudah dikoreksi."""
    if not DEALS.exists():
        return []
    try:
        with DEALS.open(newline="") as f:
            return terapkan(list(csv.DictReader(f)), baca_koreksi(KOREKSI_DEFAULT))
    except OSError:
        return []


async def _snapshot_terakhir(account: str | None = None) -> dict[str, Any] | None:
    baris = await _db(
        "select value_json, observed_at from facts where kind='mt5_snapshot' "
        "and key=:key order by observed_at desc limit 1",
        {"key": snapshot_key(account)},
    )
    if not baris:
        return None
    v = baris[0]["value_json"]
    if isinstance(v, str):
        v = json.loads(v)
    v = dict(v)
    v["_observed_at"] = str(baris[0]["observed_at"])
    return v


async def _deret_ekuitas(batas: int = 2000, account: str | None = None) -> list[dict[str, Any]]:
    baris = await _db(
        "select value_json, observed_at from facts where kind='mt5_snapshot' "
        "and key=:key order by observed_at desc limit :n",
        {"n": batas, "key": snapshot_key(account)},
    )
    hasil = []
    for r in baris:
        v = r["value_json"]
        if isinstance(v, str):
            v = json.loads(v)
        hasil.append({"t": str(r["observed_at"]), "equity": v.get("equity"),
                      "balance": v.get("balance"), "pnl_hari": v.get("net_pnl_today_usd")})
    # Query mengambil N TERBARU (desc) supaya deret tidak membeku di 2000 titik pertama;
    # grafik butuh urutan waktu naik.
    hasil.reverse()
    return hasil


async def journal_stats(market: str = "all") -> dict[str, Any]:
    m = _cek_market(market)
    pakai_forex = m in ("all", "forex")
    pakai_crypto = m in ("all", "crypto")
    snap = await _snapshot_terakhir() if pakai_forex else None
    forex = await asyncio.to_thread(_trade_forex) if pakai_forex else []
    fills = await asyncio.to_thread(_baca_fills) if pakai_forex else []
    crypto = await asyncio.to_thread(_trade_crypto) if pakai_crypto else []
    mom = await asyncio.to_thread(_ringkas_momentum) if pakai_crypto else None
    if not snap and not forex and not crypto and not (mom or {}).get("aktif"):
        raise SumberKosong(
            "Jurnal belum punya data untuk market ini. Telemetri MT5 direkam tiap menit, "
            "dan trade paper crypto dicatat saat strategi membuka posisi."
        )
    snap = snap or {}
    mom = mom or {}
    return {
        "sumber": "lokal:mt5+momentum",
        "market": m,
        "akun": snap.get("account"),
        "saldo": snap.get("balance"),
        "ekuitas": snap.get("equity"),
        "pnl_hari_ini_usd": snap.get("net_pnl_today_usd"),
        "trade_hari_ini": snap.get("total_trades_today"),
        "menang": snap.get("wins_today"),
        "kalah": snap.get("losses_today"),
        "win_rate_hari_ini_pct": snap.get("win_rate_today_pct"),
        "posisi_terbuka": snap.get("posisi"),
        "pending": snap.get("pending"),
        "crypto": {
            "aktif": bool(mom.get("aktif")),
            "koin": mom.get("koin"),
            "modal": mom.get("modal"),
            "ekuitas": mom.get("ekuitas"),
            "return_pct": mom.get("return_pct"),
            "posisi": mom.get("posisi"),
            "trade": len(crypto),
            # Ringkasan dari ledger paper (R, bukan persen). Momentum di atas hanya
            # mencakup 8 koin strategi lama; angka di bawah ini mencakup seluruh
            # trade paper yang dijalankan `paper-scan`.
            "trade_paper": len(crypto),
            "menang_paper": sum(1 for t in crypto if jurnal_crypto.r_dari(t) > 0),
            "kalah_paper": sum(1 for t in crypto if jurnal_crypto.r_dari(t) < 0),
            "r_total_paper": round(sum(jurnal_crypto.r_dari(t) for t in crypto), 2),
        },
        "n_fill_tercatat": len(fills) + len(crypto),
        "n_fill_forex": len(fills),
        "n_fill_crypto": len(crypto),
        "n_deal_forex": len(forex),
        "terakhir_terlihat": snap.get("_observed_at"),
    }


async def journal_trades(market: str = "all") -> dict[str, Any]:
    m = _cek_market(market)
    forex = await asyncio.to_thread(_trade_forex) if m in ("all", "forex") else []
    crypto = await asyncio.to_thread(_trade_crypto) if m in ("all", "crypto") else []
    entries: list[dict[str, Any]] = []
    if m in ("all", "forex"):
        for r in await asyncio.to_thread(_baca_fills):
            d = dict(r)
            d["status"] = "entry"
            d["market"] = "forex"
            entries.append(d)
    semua = sorted(forex + crypto, key=lambda r: str(r.get("iso", "")), reverse=True)
    return {
        "sumber": "lokal:deals.csv + fills.csv + crypto_equity.jsonl",
        "market": m,
        "closed": semua[:200],
        "open": [],
        "entries": entries[:200],
        "n": len(semua),
        "n_entry": len(entries),
        "catatan": "Forex tertutup dari deals.csv (laporan deal EA). Entri order dan "
                   "kualitas eksekusi dari fills.csv. Crypto dari ledger paper "
                   "crypto_equity.jsonl; hasilnya dalam R (kelipatan risiko), bukan persen.",
    }


async def journal_edge(market: str = "all") -> dict[str, Any]:
    """Slippage dan latensi per jam, dari fill nyata forex."""
    m = _cek_market(market)
    if m == "crypto":
        raise SumberKosong(
            "Paper crypto tidak punya slippage nyata: entry dicatat di harga candle, "
            "tanpa antrean order. Edge eksekusi hanya bermakna untuk forex."
        )
    fills = await asyncio.to_thread(_baca_fills)
    if not fills:
        raise SumberKosong("Belum ada fill forex. Edge eksekusi belum bisa dihitung.")
    per_jam: dict[str, list[float]] = {}
    per_simbol: dict[str, list[float]] = {}
    latensi: list[float] = []
    for f in fills:
        try:
            slip = float(f.get("slippage_pts") or 0)
            jam = str(f.get("iso", ""))[11:13] or "??"
        except (TypeError, ValueError):
            continue
        per_jam.setdefault(jam, []).append(slip)
        per_simbol.setdefault(str(f.get("symbol") or "?"), []).append(slip)
        if f.get("latency_ms"):
            try:
                latensi.append(float(f["latency_ms"]))
            except ValueError:
                pass

    def ringkas(d: dict[str, list[float]]) -> dict[str, Any]:
        return {
            k: {
                "n": len(v),
                "slip_rata_pts": round(sum(v) / len(v), 2),
                "slip_terburuk_pts": round(min(v), 2),
            }
            for k, v in sorted(d.items())
        }

    return {
        "sumber": "lokal:fills.csv",
        "per_jam": ringkas(per_jam),
        "per_simbol": ringkas(per_simbol),
        "latensi_rata_ms": round(sum(latensi) / len(latensi), 1) if latensi else None,
        "n": len(fills),
    }


def _drawdown_maks(deret: list[dict[str, Any]]) -> float:
    """Drawdown maksimum (%) dari puncak berjalan, bukan dari titik awal."""
    puncak: float | None = None
    maks = 0.0
    for d in deret:
        eq = d.get("equity")
        if eq is None:
            continue
        puncak = float(eq) if puncak is None else max(puncak, float(eq))
        if puncak > 0:
            maks = max(maks, (puncak - float(eq)) / puncak * 100)
    return round(maks, 3)


def _marker_forex() -> list[dict[str, Any]]:
    """Deal tertutup sebagai penanda di kurva ekuitas (terbaru di akhir)."""
    hasil = []
    for d in _trade_forex():
        net = d.get("pnl_usd")
        try:
            net_f = round(float(net), 2) if str(net).strip() not in ("", "None") else None
        except (TypeError, ValueError):
            net_f = None
        hasil.append(
            {
                "t": d.get("iso", ""),
                "ticket": d.get("ticket", ""),
                "symbol": d.get("symbol", ""),
                "side": d.get("side", ""),
                "net_usd": net_f,
            }
        )
    hasil.sort(key=lambda x: str(x["t"]))
    return hasil[-200:]


async def journal_performance(market: str = "all", account: str | None = None) -> dict[str, Any]:
    m = _cek_market(market)
    if m == "crypto":
        raise SumberKosong(
            "Riwayat ekuitas crypto belum direkam: paper trader menyimpan kondisi "
            "terakhir saja, bukan deret waktu. Riwayat mulai terkumpul setelah "
            "pencatatan per siklus ditambahkan."
        )
    deret = await _deret_ekuitas(account=account)
    if not deret:
        raise SumberKosong("Belum ada riwayat ekuitas. Rekaman dimulai saat EA mengirim telemetri.")
    akhir = deret[-1]
    awal = deret[0]
    puncak = max((d["equity"] or 0) for d in deret)
    markers = await asyncio.to_thread(_marker_forex) if m in ("all", "forex") else []
    return {
        "sumber": "lokal:mt5_snapshot",
        "market": m,
        "n_titik": len(deret),
        "ekuitas_awal": awal["equity"],
        "ekuitas_akhir": akhir["equity"],
        "puncak": puncak,
        "drawdown_max_pct": _drawdown_maks(deret),
        "markers": markers,
        "perubahan_pct": round((akhir["equity"] - awal["equity"]) / awal["equity"] * 100, 3)
        if awal["equity"] else None,
        "deret": deret[-500:],
    }


async def journal_session() -> dict[str, Any]:
    snap = await _snapshot_terakhir()
    if not snap:
        raise SumberKosong("Belum ada telemetri MT5 yang terekam.")
    return {
        "sumber": "lokal:mt5",
        "sesi": "live-demo",
        "akun": snap.get("account"),
        "ekuitas": snap.get("equity"),
        "spread_pts": snap.get("spread_pts"),
        "bid": snap.get("bid"),
        "ask": snap.get("ask"),
        "posisi_terbuka": snap.get("posisi"),
        "pnl_hari_ini_usd": snap.get("net_pnl_today_usd"),
        "terakhir_terlihat": snap.get("_observed_at"),
    }


async def journal_watchlist() -> dict[str, Any]:
    snap = await _snapshot_terakhir()
    if not snap:
        raise SumberKosong("Belum ada telemetri MT5 yang terekam.")
    return {
        "sumber": "lokal:mt5",
        "posisi": snap.get("positions") or [],
        "pending": snap.get("pending_orders") or [],
        "n_posisi": snap.get("posisi"),
        "terakhir_terlihat": snap.get("_observed_at"),
    }


def _baca_verdicts() -> tuple[list[dict[str, Any]], int]:
    """Verdict crypto terbaru (100 terakhir) + total baris. Berkas tidak ada → SumberKosong."""
    if not VERDICTS.exists():
        raise SumberKosong("Berkas verdicts belum ada di server ini.")
    baris: list[str] = []
    try:
        with VERDICTS.open(encoding="utf-8", errors="replace") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    baris.append(ln)
    except OSError as exc:
        raise SumberKosong(f"Gagal baca verdicts: {exc}") from exc
    keluar = []
    for ln in baris[-100:]:
        try:
            keluar.append(json.loads(ln))
        except ValueError:
            continue
    return keluar[::-1], len(baris)

async def _scanlog_crypto() -> dict[str, Any]:
    keluar, total = await asyncio.to_thread(_baca_verdicts)
    if not keluar:
        raise SumberKosong("Berkas verdicts ada tetapi tidak memuat baris JSON yang sah.")
    return {
        "sumber": "lokal:verdicts.jsonl",
        "market": "crypto",
        "n": total,
        "terakhir": keluar,
    }

async def _scanlog_forex() -> dict[str, Any]:
    """Riwayat evaluasi EA (bukan verdict crypto), dari fakta `mt5_snapshot`.

    Snapshot ditulis maksimal sekali per menit. Baris dengan isi evaluasi identik
    digabung supaya tabel tidak penuh salinan yang sama; yang ditampilkan adalah
    perubahan keputusan, bukan irama telemetri.
    """
    baris = await _db(
        "select value_json, observed_at from facts where kind='mt5_snapshot' "
        "and key='ringkas' order by observed_at desc limit :n",
        {"n": 500},
    )
    if not baris:
        raise SumberKosong(
            "Belum ada telemetri MT5 yang terekam. Riwayat evaluasi EA muncul setelah "
            "EA mengirim snapshot pertama."
        )
    unik: list[dict[str, Any]] = []
    sudah: set[tuple] = set()
    for r in baris:
        v = r.get("value_json")
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except ValueError:
                continue
        if not isinstance(v, dict):
            continue
        kunci = (
            v.get("eval_at"),
            v.get("eval_alasan"),
            v.get("eval_sesi"),
            v.get("eval_atr"),
            v.get("eval_rsi"),
            v.get("eval_ema_fast"),
            v.get("eval_ema_slow"),
            v.get("eval_tren"),
        )
        if kunci in sudah:
            continue
        sudah.add(kunci)
        ts = r.get("observed_at")
        unik.append(
            {
                "ts": ts.isoformat() if hasattr(ts, "isoformat") else str(ts or ""),
                "pair": "XAUUSD",
                "eval_at": v.get("eval_at"),
                "sesi": bool(v.get("eval_sesi")),
                "alasan": v.get("eval_alasan") or "(EA belum mengirim alasan evaluasi)",
                "atr": v.get("eval_atr"),
                "spread": v.get("eval_spread"),
                "rsi": v.get("eval_rsi"),
                "ema_fast": v.get("eval_ema_fast"),
                "ema_slow": v.get("eval_ema_slow"),
                "tren": v.get("eval_tren"),
            }
        )
        if len(unik) >= 50:
            break
    return {
        "sumber": "lokal:mt5_snapshot",
        "market": "forex",
        "n": len(unik),
        "n_snapshot": len(baris),
        "terakhir": unik,
    }

async def journal_scanlog(market: str = "all") -> dict[str, Any]:
    """Alasan keputusan per market. Forex = evaluasi EA; crypto = verdicts.jsonl.

    `all` mengembalikan dua bagian terpisah — tidak pernah mencampur pair crypto ke
    riwayat forex atau sebaliknya.
    """
    m = _cek_market(market)
    if m == "forex":
        return await _scanlog_forex()
    if m == "crypto":
        return await _scanlog_crypto()
    hasil: dict[str, Any] = {"market": "all"}
    for nama, fn in (("forex", _scanlog_forex), ("crypto", _scanlog_crypto)):
        try:
            hasil[nama] = await fn()
        except SumberKosong as exc:
            hasil[nama] = {"market": nama, "n": 0, "terakhir": [], "catatan": str(exc)}
    return hasil


async def journal_signals() -> dict[str, Any]:
    """Jurnal sinyal terkirim + hasil dari candle sejak jam setelah kirim (dihitung worker)."""
    if not JURNAL_SINYAL.exists():
        raise SumberKosong(
            "Jurnal sinyal belum dihitung. Job `jurnal-sinyal` menulis berkas ini "
            "setiap 6 jam setelah ada alert sinyal."
        )
    try:
        data = json.loads(JURNAL_SINYAL.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SumberKosong(f"Jurnal sinyal tidak terbaca: {exc}") from exc
    if not isinstance(data, dict):
        raise SumberKosong("Jurnal sinyal tidak berisi objek yang sah.")
    return data


async def journal_charts() -> dict[str, Any]:
    deret = await _deret_ekuitas()
    return {
        "sumber": "lokal:mt5_snapshot",
        "charts": [
            {"nama": "ekuitas", "n": len(deret), "data": deret[-300:]},
        ],
    }


async def journal_multipair(market: str = "all") -> dict[str, Any]:
    m = _cek_market(market)
    fills = []
    if m in ("all", "forex"):
        fills += await asyncio.to_thread(_trade_forex)
    if m in ("all", "crypto"):
        fills += await asyncio.to_thread(_trade_crypto)
    per: dict[str, dict[str, Any]] = {}
    for f in fills:
        s = str(f.get("symbol") or "?")
        d = per.setdefault(s, {"n": 0, "volume": 0.0, "slip": [], "market": f.get("market")})
        d["n"] += 1
        try:
            d["volume"] += float(f.get("volume") or 0)
            if f.get("slippage_pts"):
                d["slip"].append(float(f["slippage_pts"]))
        except ValueError:
            pass
    return {
        "sumber": "lokal:fills.csv + momentum_trades.csv",
        "market": m,
        "per_simbol": {
            k: {
                "n": v["n"],
                "market": v["market"],
                "volume": round(v["volume"], 2),
                "slip_rata_pts": round(sum(v["slip"]) / len(v["slip"]), 2) if v["slip"] else None,
            }
            for k, v in per.items()
        },
    }


async def sebar(path: str, params: dict[str, Any] | None = None) -> Any:
    """Dispatch path gaya node lama ke implementasi lokal."""
    p = params or {}
    jurnal = {
        "/forex/journal/stats": journal_stats,
        "/forex/journal/trades": journal_trades,
        "/forex/journal/edge": journal_edge,
        "/forex/journal/performance": journal_performance,
        "/forex/journal/session": journal_session,
        "/forex/journal/watchlist": journal_watchlist,
        "/forex/journal/scanlog": journal_scanlog,
        "/forex/journal/charts": journal_charts,
        "/forex/journal/multipair": journal_multipair,
    }
    if path in jurnal:
        if path == "/forex/journal/performance":
            return await jurnal[path](str(p.get("market", "all")), p.get("account"))
        # Enam endpoint menerima filter market: all | forex | crypto.
        if path in {
            "/forex/journal/stats",
            "/forex/journal/trades",
            "/forex/journal/edge",
            "/forex/journal/performance",
            "/forex/journal/multipair",
            "/forex/journal/scanlog",
        }:
            return await jurnal[path](str(p.get("market", "all")))
        return await jurnal[path]()
    if path in ("/health", "/health/"):
        return {"ok": True, "mode": "lokal", "sumber": "okx+yahoo"}
    if path in ("/crypto/universe", "/universe"):
        return await crypto_universe()
    if path in ("/crypto/ticker", "/ticker"):
        return await crypto_ticker(str(p.get("symbol", "BTCUSDT")))
    if path in ("/crypto/klines", "/klines"):
        return await crypto_klines(str(p.get("symbol", "BTCUSDT")),
                                   str(p.get("interval", "1h")),
                                   int(p.get("limit", 15) or 15))
    if path == "/forex/klines":
        return await forex_klines(str(p.get("symbol", "XAUUSD")),
                                  str(p.get("interval", "60")),
                                  int(p.get("limit", 15) or 15))
    if path == "/forex/dxy":
        return await forex_dxy()
    if path == "/idx/market":
        return await idx_market()
    if path == "/idx/stats":
        return await idx_stats()
    raise SumberKosong(
        f"{path} belum punya padanan lokal. Data ini dulu dihitung oleh node "
        "scanner yang sudah tidak ada."
    )


def jalankan(coro: Any) -> Any:
    """Jalankan coroutine dari konteks sinkron (dipakai skrip CLI/uji)."""
    return asyncio.run(coro)
