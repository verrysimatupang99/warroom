#!/usr/bin/env python3
"""arjum_pool.py — singleton wrapper di atas arjum_client (REST).

Tujuan (SoW IDX 616, 6 Sep 2026):
1. Cache lintas cron: screener TTL 30m, broker_summary 1h, history 4h, analysis 1d, seasonal 7d.
2. Quota guard: auto-skip kalau remaining < MIN_REMAINING (degraded → caller tangani).
3. Audit JSONL harian: ~/.hermes/cron/logs/arjum_audit_<YYYY-MM-DD>.jsonl
4. Tidak mengubah arjum_client.py — layer additive, drop-in.

Cara pakai:
    from arjum_pool import pool_screener, pool_history, pool_broker_summary, pool_analysis, pool_seasonal
    d = pool_screener()           # cached 30m
    d = pool_history("BBRI","daily")  # cached 4h per code+frame
    d = pool_broker_summary("BBRI")   # cached 1h

Constraint: dipakai HANYA oleh script cron 616, tidak disentuh dari MaxiCorp UI.
"""
import datetime
import json
import os
import sys
import time
from pathlib import Path

import arjum_client as _c

# ── TTL config (detik) ──────────────────────────────────────────────────────
TTL = {
    "screener":       30 * 60,   # 30m   (V5.2 update harian, refresh intraday 30m OK)
    "broker_summary": 60 * 60,   # 1h    (broker netflow refresh intraday 1-2x)
    "history":        4 * 60 * 60,   # 4h (OHLCV daily 1x/hari cukup; weekly/monthly even lebih)
    "analysis":       24 * 60 * 60,  # 1d   (recap harian)
    "seasonal":       7 * 24 * 60 * 60,  # 7d (pola musiman tahunan stabil)
    "search":         24 * 60 * 60,  # 1d  (autocomplete cache)
    "financial_statements": 7 * 24 * 60 * 60,  # 7d (quarterly, 4x setahun)
    "insiders":       6 * 60 * 60,   # 6h (cukup utk daily watch, insider jarang)
    "market_cap":     6 * 60 * 60,   # 6h (update 1-2x/hari pas bursa)
    "history_yf":     4 * 60 * 60,   # 4h — cermin "history", namespace terpisah
}
MIN_REMAINING = 500  # guard: skip kalau sisa < 500

# ── Sumber history: Arjum atau yfinance ─────────────────────────────────────
# Job yang hanya butuh OHLCV (close/open/high/low/volume/date) bisa dilayani
# yfinance tanpa menyentuh kuota Arjum sama sekali. Job yang butuh data khas
# IDX (foreign flow, broker summary/akumulasi, insider, laporan keuangan,
# screener analitik) memanggil endpoint LAIN, jadi tidak terpengaruh saklar ini.
#
# Set ARJUM_HISTORY_SOURCE=arjum untuk kembali ke jalur lama seketika.
HISTORY_SOURCE = os.environ.get("ARJUM_HISTORY_SOURCE", "yfinance").strip().lower()

# ── Cache file (persist antar proses; in-memory tetap utama) ────────────────
CACHE_DIR = Path("/home/ubuntu/.hermes/cron/cache/arjum")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR = Path("/home/ubuntu/.hermes/cron/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# in-memory cache (per process)
_mem_cache: dict = {}


def _cache_key(endpoint, *args, **kwargs):
    """Identifier deterministik (untuk TTL+key file)."""
    if args and kwargs:
        return f"{endpoint}|{args}|{sorted(kwargs.items())}"
    if args:
        return f"{endpoint}|{args}"
    if kwargs:
        return f"{endpoint}|{sorted(kwargs.items())}"
    return endpoint


def _log_audit(endpoint, code, status, source):
    """JSONL append per-call — transparansi per cron job."""
    today = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=7)).strftime("%Y-%m-%d")
    path = LOG_DIR / f"arjum_audit_{today}.jsonl"
    rec = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "endpoint": endpoint,
        "code": code,
        "status": status,        # "hit" | "fetch" | "skip_low_quota" | "err"
        "source": source,        # "mem" | "disk" | "live" | "guard"
        "remaining": _c.quota_remaining(),
    }
    try:
        with path.open("a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass


def _cache_path(key):
    safe = key.replace("/", "_").replace("|", "_").replace(" ", "_")
    return CACHE_DIR / f"{safe}.json"


def _cache_load(key):
    """Cek disk cache; return data kalau masih dalam TTL endpoint."""
    cp = _cache_path(key)
    if not cp.exists():
        return None
    try:
        meta = json.loads(cp.read_text())
    except Exception:
        return None
    ttl = TTL.get(meta.get("endpoint", ""), 0)
    if ttl <= 0 or (time.time() - meta.get("saved_at", 0)) > ttl:
        return None
    return meta.get("data")


def _cache_save(key, endpoint, data):
    """Simpan ke disk + memory."""
    _mem_cache[key] = (endpoint, data, time.time())
    try:
        _cache_path(key).write_text(json.dumps({
            "endpoint": endpoint, "data": data, "saved_at": time.time()
        }))
    except Exception:
        pass


def _cached_or_fetch(endpoint_name, fn, *args, ttl_override=None, quota_free=False, **kwargs):
    """Core helper: cache → quota check → fetch → audit.

    quota_free=True melewati guard kuota Arjum. Dipakai sumber yang tidak
    memanggil Arjum sama sekali (mis. yfinance), supaya mereka justru tetap
    bisa bekerja saat kuota Arjum sedang habis.
    """
    key = _cache_key(endpoint_name, *args, **kwargs)

    # 1. memory
    if key in _mem_cache:
        ep, data, saved = _mem_cache[key]
        ttl = ttl_override or TTL.get(ep, 0)
        if ttl > 0 and (time.time() - saved) <= ttl:
            _log_audit(endpoint_name, args[0] if args else None, "hit", "mem")
            return data

    # 2. disk
    disk = _cache_load(key)
    if disk is not None:
        _mem_cache[key] = (endpoint_name, disk, time.time())
        _log_audit(endpoint_name, args[0] if args else None, "hit", "disk")
        return disk

    # 3. quota guard
    if not quota_free and _c.quota_remaining() < MIN_REMAINING:
        _log_audit(endpoint_name, args[0] if args else None, "skip_low_quota", "guard")
        raise RuntimeError(
            f"arjum_pool: quota rendah ({_c.quota_remaining()}/{MIN_REMAINING} min), "
            f"skip fetch {endpoint_name}. Caller fallback ke sumber lain."
        )

    # 4. live fetch
    try:
        data = fn(*args, **kwargs)
        _cache_save(key, endpoint_name, data)
        _log_audit(endpoint_name, args[0] if args else None, "fetch", "live")
        return data
    except Exception as e:
        _log_audit(endpoint_name, args[0] if args else None, "err", str(e)[:50])
        raise


# ── Adapter yfinance (bentuk respons disamakan dgn arjum_client) ─────────────
_yf_state = {"loaded": False, "mod": None}

# yfinance sudah tersedia di venv milik Hermes (di sanalah job cron dijalankan),
# jadi import biasa hampir selalu berhasil. Kalau gagal — misal skrip dijalankan
# dengan python sistem — cari site-packages venv itu lalu coba lagi.
YF_VENV = os.environ.get("ARJUM_YF_VENV", "/home/ubuntu/hermes-agent/venv")


def _yf_paths():
    return sorted(Path(YF_VENV).glob("lib/python3*/site-packages"), reverse=True)


def _yf_load():
    """Import yfinance malas — supaya tidak jadi dependensi keras.

    Gagal total → None, dan pool_history jatuh kembali ke jalur Arjum.
    """
    if not _yf_state["loaded"]:
        _yf_state["loaded"] = True
        try:
            import yfinance as _yf
            _yf_state["mod"] = _yf
            return _yf_state["mod"]
        except Exception:
            pass
        for sp in _yf_paths():
            if not sp.is_dir():
                continue
            sys.path.insert(0, str(sp))
            try:
                import yfinance as _yf
                _yf_state["mod"] = _yf
                break
            except Exception:
                sys.path.pop(0)
    return _yf_state["mod"]


_YF_INTERVAL = {"daily": ("1d", "2y"), "weekly": ("1wk", "5y"), "monthly": ("1mo", "10y")}


def _yf_num(v):
    try:
        f = float(v)
        return f if f == f else None      # NaN → None
    except Exception:
        return None


def _yf_history(code, frame="daily"):
    """history() versi yfinance; bentuk balikan identik dgn arjum_client.history().

    Field yang tidak tersedia di Yahoo (avg, freq, f_buy, f_sell, n_foreign)
    diisi None — tidak ada konsumen pada jalur history yang membacanya.
    """
    yf = _yf_load()
    if yf is None:
        raise RuntimeError("yfinance tidak tersedia")
    interval, period = _YF_INTERVAL.get(str(frame).lower(), ("1d", "2y"))
    ticker = f"{str(code).upper()}.JK"
    df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
    if df is None or getattr(df, "empty", True):
        raise RuntimeError(f"yfinance kosong: {ticker}")

    rows = []
    prev = None
    for ts, r in df.iterrows():
        close = _yf_num(r.get("Close"))
        if not close:
            continue
        change = (close - prev) if prev else 0.0
        pct = (change / prev * 100.0) if prev else 0.0
        vol = _yf_num(r.get("Volume")) or 0.0
        rows.append({
            "date": ts.strftime("%Y-%m-%d"),
            "open": _yf_num(r.get("Open")),
            "high": _yf_num(r.get("High")),
            "low": _yf_num(r.get("Low")),
            "close": close,
            "change": round(change, 2),
            "change_pct": round(pct, 2),
            "volume": vol,
            "value": round(close * vol, 2),
            "avg": None,
            "freq": None,
            "f_buy": None,
            "f_sell": None,
            "n_foreign": None,
        })
        prev = close
    rows.reverse()   # Arjum mengembalikan terbaru dulu
    return {"stock_code": str(code).upper(), "frame": frame, "rows": rows}


# ── Public API (signature sama dgn arjum_client, + caching) ─────────────────
def pool_screener(limit=None, bucket=None):
    return _cached_or_fetch("screener", _c.screener_latest, limit=limit, bucket=bucket)


def pool_broker_summary(code):
    return _cached_or_fetch("broker_summary", _c.broker_summary, code)


def pool_broker_accumulation(code, days=None):
    return _cached_or_fetch("broker_accumulation", _c.broker_accumulation, code, days=days)


def pool_analysis(code):
    return _cached_or_fetch("analysis", _c.analysis, code)


def pool_history(code, frame="daily"):
    if HISTORY_SOURCE != "arjum" and _yf_load() is not None:
        try:
            # Namespace cache terpisah dari "history" supaya data dua sumber
            # tidak tercampur saat saklar diganti.
            return _cached_or_fetch("history_yf", _yf_history, code, frame=frame, quota_free=True)
        except Exception:
            # Meja sinyal tidak boleh kehilangan data: kalau yfinance gagal,
            # jatuh kembali ke jalur Arjum seperti sebelumnya.
            pass
    return _cached_or_fetch("history", _c.history, code, frame=frame)


def pool_seasonal(code):
    return _cached_or_fetch("seasonal", _c.seasonal, code)


def pool_search(q):
    return _cached_or_fetch("search", _c.search, q)


def pool_financial_statements(code, statement=None, limit=None):
    """statement diabaikan server (hardcoded INCOME_STATEMENT). limit honored."""
    if statement is not None or limit is not None:
        # tidak lewat cache (param variasi) — bypass
        from arjum_client import get as _get
        params = {}
        if statement: params["statement"] = statement
        if limit: params["limit"] = limit
        return _get(f"/api/financial-statements/{code.upper()}", params)
    return _cached_or_fetch("financial_statements", _c.financial_statements_proxy, code)


def pool_insiders(code, page=1, page_size=10, action_type=None, start_date=None, sort=None, badges=None):
    """Paged + filter insider trading. Tidak di-cache (variasi param banyak)."""
    from arjum_client import get as _get
    params = {"page": page, "page_size": page_size}
    if action_type: params["action_type"] = action_type
    if start_date: params["start_date"] = start_date
    if sort: params["sort"] = sort
    if badges: params["badges"] = badges
    return _get(f"/api/insiders/{code.upper()}", params)


def pool_market_cap(page=1, per_page=25, sort=None, sector=None):
    """Cached only untuk default (no param); param variasi bypass cache."""
    if any([page != 1, per_page != 25, sort, sector]):
        from arjum_client import get as _get
        params = {"page": page, "per_page": per_page}
        if sort: params["sort"] = sort
        if sector: params["sector"] = sector
        return _get("/api/market-cap", params)
    return _cached_or_fetch("market_cap", _c.market_cap_proxy)


# ── Admin helpers ───────────────────────────────────────────────────────────
def audit_summary(date=None):
    """Summary audit per tanggal (default hari ini WIB)."""
    if date is None:
        date = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=7)).strftime("%Y-%m-%d")
    path = LOG_DIR / f"arjum_audit_{date}.jsonl"
    if not path.exists():
        return {"date": date, "calls": 0, "by_endpoint": {}, "hits": 0, "fetches": 0, "skips": 0, "errs": 0}
    summary = {"date": date, "calls": 0, "by_endpoint": {}, "hits": 0, "fetches": 0, "skips": 0, "errs": 0}
    for line in path.read_text().splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        summary["calls"] += 1
        ep = r.get("endpoint", "?")
        st = r.get("status", "?")
        summary["by_endpoint"].setdefault(ep, {"hit": 0, "fetch": 0, "skip_low_quota": 0, "err": 0})
        summary["by_endpoint"][ep][st] = summary["by_endpoint"][ep].get(st, 0) + 1
        if st == "hit":
            summary["hits"] += 1
        elif st == "fetch":
            summary["fetches"] += 1
        elif st == "skip_low_quota":
            summary["skips"] += 1
        elif st == "err":
            summary["errs"] += 1
    return summary


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "audit":
        print(json.dumps(audit_summary(), indent=1))
    else:
        print("quota:", _c.rate_status())
        print("audit:", audit_summary())
