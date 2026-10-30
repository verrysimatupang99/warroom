"""Sumber data lokal untuk War Room — pengganti node upstream yang hilang.

Latar: seluruh data crypto/forex/IDX dulu diambil dari satu node di luar server
lewat Tailscale. Node itu sudah tidak ada. Modul ini mengambil data langsung
dari sumber publik, tanpa kredensial dan tanpa perantara:

  - Crypto  : MEXC public API (tanpa key). Dipakai juga oleh `lt scan`.
  - Forex   : Yahoo Finance chart API (butuh User-Agent; tanpa UA dibalas 429).
  - IDX     : Yahoo Finance untuk IHSG (^JKSE).

Prinsip: kalau sebuah data tidak bisa diambil, endpoint mengembalikan 503 dengan
alasan yang jelas. Tidak ada angka karangan, tidak ada nilai default palsu.
"""
from __future__ import annotations

import asyncio
import csv
import json
import time
from pathlib import Path
from typing import Any

import httpx

UA = "Mozilla/5.0 (X11; Linux x86_64) WarRoom/2.0"
MEXC = "https://api.mexc.com"
YAHOO = "https://query2.finance.yahoo.com"
TIMEOUT = 12.0

# Pemetaan interval yang dipakai UI ke format masing-masing penyedia.
_INTERVAL_MEXC = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
                  "1h": "60m", "60": "60m", "4h": "4h", "1d": "1d"}
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


async def crypto_universe(jumlah: int = 80) -> dict[str, Any]:
    """Pasangan USDT aktif di MEXC, diurutkan menurut volume 24 jam."""
    ticker = await _get_json(f"{MEXC}/api/v3/ticker/24hr")
    if not isinstance(ticker, list):
        raise SumberKosong("ticker MEXC bukan list")
    koin = [t for t in ticker if str(t.get("symbol", "")).endswith("USDT")]
    koin.sort(key=lambda t: float(t.get("quoteVolume") or 0), reverse=True)
    return {
        "symbols": [t["symbol"] for t in koin[:jumlah]],
        "total": len(koin),
        "sumber": "mexc-lokal",
        "diambil": int(time.time()),
    }


async def crypto_ticker(simbol: str) -> dict[str, Any]:
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
        "source": "mexc-lokal",
    }


async def crypto_klines(simbol: str, interval: str = "1h", limit: int = 15) -> dict[str, Any]:
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
        "sumber": "mexc-lokal",
    }


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

FILLS = Path("/var/lib/warroom/fills.csv")
DEALS = Path("/var/lib/warroom/deals.csv")
VERDICTS = Path("/home/admin/live-trading/state/verdicts.jsonl")
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
    """Trade paper crypto, dibentuk sama seperti baris fill forex."""
    hasil = []
    for r in _baca_csv(MOMENTUM_TRADES):
        aksi = str(r.get("aksi", "")).upper()
        hasil.append(
            {
                "iso": str(r.get("waktu", ""))[:19].replace("T", " "),
                "symbol": r.get("koin", ""),
                "side": "BUY" if aksi.startswith("BELI") else "SELL",
                "volume": r.get("qty", ""),
                "price_filled": r.get("harga", ""),
                "slippage_pts": "",
                "latency_ms": "",
                "pnl_pct": r.get("pnl_pct", ""),
                "market": "crypto",
            }
        )
    return hasil


def _trade_forex() -> list[dict[str, Any]]:
    """Trade forex tertutup dari deals.csv (bukan lagi dari fills entry)."""
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
    """Deal tertutup (satu baris per posisi) yang dilaporkan EA."""
    if not DEALS.exists():
        return []
    try:
        with DEALS.open(newline="") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


async def _snapshot_terakhir() -> dict[str, Any] | None:
    baris = await _db(
        "select value_json, observed_at from facts where kind='mt5_snapshot' "
        "order by observed_at desc limit 1"
    )
    if not baris:
        return None
    v = baris[0]["value_json"]
    if isinstance(v, str):
        v = json.loads(v)
    v = dict(v)
    v["_observed_at"] = str(baris[0]["observed_at"])
    return v


async def _deret_ekuitas(batas: int = 2000) -> list[dict[str, Any]]:
    baris = await _db(
        "select value_json, observed_at from facts where kind='mt5_snapshot' "
        "order by observed_at asc limit :n",
        {"n": batas},
    )
    hasil = []
    for r in baris:
        v = r["value_json"]
        if isinstance(v, str):
            v = json.loads(v)
        hasil.append({"t": str(r["observed_at"]), "equity": v.get("equity"),
                      "balance": v.get("balance"), "pnl_hari": v.get("net_pnl_today_usd")})
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
        "sumber": "lokal:deals.csv + fills.csv + momentum_trades.csv",
        "market": m,
        "closed": semua[:200],
        "open": [],
        "entries": entries[:200],
        "n": len(semua),
        "n_entry": len(entries),
        "catatan": "Forex tertutup dari deals.csv (laporan deal EA). Entri order dan "
                   "kualitas eksekusi dari fills.csv. Crypto dari catatan paper trader.",
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


async def journal_performance(market: str = "all") -> dict[str, Any]:
    if _cek_market(market) == "crypto":
        raise SumberKosong(
            "Riwayat ekuitas crypto belum direkam: paper trader menyimpan kondisi "
            "terakhir saja, bukan deret waktu. Riwayat mulai terkumpul setelah "
            "pencatatan per siklus ditambahkan."
        )
    deret = await _deret_ekuitas()
    if not deret:
        raise SumberKosong("Belum ada riwayat ekuitas. Rekaman dimulai saat EA mengirim telemetri.")
    akhir = deret[-1]
    awal = deret[0]
    puncak = max((d["equity"] or 0) for d in deret)
    return {
        "sumber": "lokal:mt5_snapshot",
        "n_titik": len(deret),
        "ekuitas_awal": awal["equity"],
        "ekuitas_akhir": akhir["equity"],
        "puncak": puncak,
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


async def journal_scanlog() -> dict[str, Any]:
    """Alasan sinyal ditolak, dari verdicts harian live-trading."""
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
    ekor = baris[-100:]
    keluar = []
    for ln in ekor:
        try:
            keluar.append(json.loads(ln))
        except ValueError:
            continue
    return {"sumber": "lokal:verdicts.jsonl", "n": len(baris), "terakhir": keluar[::-1]}


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
        # Lima endpoint menerima filter market: all | forex | crypto.
        if path in {
            "/forex/journal/stats",
            "/forex/journal/trades",
            "/forex/journal/edge",
            "/forex/journal/performance",
            "/forex/journal/multipair",
        }:
            return await jurnal[path](str(p.get("market", "all")))
        return await jurnal[path]()
    if path in ("/health", "/health/"):
        return {"ok": True, "mode": "lokal", "sumber": "mexc+yahoo"}
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
