#!/usr/bin/env python3
"""arjum_client.py — REST API client untuk stock.arjum.com (IDXEDGEPRO).

Key: env ARJUM_API_KEY (jangan hardcode di file lain). Kuota harian, reset
00:00 WIB. Endpoint DATA mengirim header X-RateLimit-* (limit 6000 diamati
5 Sep 2026 — docs bilang 1000, header menang); /api/health TIDAK mengirim.
State file .arjum_rate_state.json: di-sync dari header saat ada, +1 saat
tidak — jadi rate_status() akurat lintas proses (guard cron di proses baru).

Endpoints resmi (terverifikasi 4 Sep 2026):
  GET /api/health                      → status service
  GET /api/search?q=BBRI               → lookup emiten (kode/nama, last price)
  GET /api/screener/latest             → hasil screener V5.2 harian (rows + raw)
  GET /api/broker-summary/<CODE>       → broker top 20 + net flow per emiten
  GET /api/broker-accumulation/<CODE>  → series akumulasi broker (range)
  GET /api/analysis/<CODE>             → teks analisis harian per emiten
  GET /api/history/<CODE>?frame=daily|weekly|monthly  → OHLCV + foreign flow
                                          (daily 120 bar, weekly 120, monthly 81)
  GET /api/seasonal/<CODE>             → seasonality per bulan, multi-tahun

Catatan: /api/stocks, /api/ohlcv, /api/market-snapshot dsb 403 = memang
bukan endpoint publik (403 "tidak dibuka"), jangan ditebak-tebak lagi.
"""
import datetime
import json
import os
import time
import urllib.error
import urllib.request

BASE = "https://stock.arjum.com"
DEFAULT_KEY_PATH = "/home/admin/live-trading/state/.arjum_api_key"


def _load_key():
    key = os.environ.get("ARJUM_API_KEY")
    if key:
        return key.strip()
    try:
        with open(DEFAULT_KEY_PATH) as f:
            return f.read().strip()
    except FileNotFoundError:
        raise RuntimeError("ARJUM_API_KEY tidak diset dan " + DEFAULT_KEY_PATH + " tidak ada")


_last_rate = {"limit": None, "remaining": None}  # hanya untuk kompatibilitas import lama

DAILY_LIMIT = 6000
RATE_STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".arjum_rate_state.json")


def _wib_today():
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=7)).strftime("%Y-%m-%d")


def _load_state():
    """Kuota terpakai hari ini (per tanggal WIB). File kecil, race jarang (cron serial)."""
    try:
        with open(RATE_STATE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state):
    try:
        tmp = RATE_STATE_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f)
        os.replace(tmp, RATE_STATE_PATH)
    except Exception:
        pass  # state file gagal tulis ≠ gagal request


def _sync_quota(used_from_header, limit_from_header):
    """Sinkron state lokal dari header: dipercaya karena dari server langsung."""
    global DAILY_LIMIT
    if limit_from_header:
        DAILY_LIMIT = limit_from_header
    state = _load_state()
    today = _wib_today()
    if state.get("date") != today:
        state = {"date": today, "used": 0}
    state["used"] = used_from_header
    state["limit"] = DAILY_LIMIT
    _save_state(state)


def _bump_quota():
    """+1 request hari ini (dipakai kalau server tak kirim header, mis. /api/health)."""
    state = _load_state()
    today = _wib_today()
    if state.get("date") != today:
        state = {"date": today, "used": 0}
    state["used"] = state.get("used", 0) + 1
    state["limit"] = DAILY_LIMIT
    _save_state(state)


def quota_remaining():
    state = _load_state()
    limit = state.get("limit") or DAILY_LIMIT
    if state.get("date") != _wib_today():
        return limit
    return max(0, limit - state.get("used", 0))


def rate_status():
    """Sisa kuota hari ini, lintas proses. Source: header (server) / local (state file)."""
    state = _load_state()
    limit = state.get("limit") or DAILY_LIMIT
    used = state.get("used", 0) if state.get("date") == _wib_today() else 0
    return {"limit": limit, "remaining": max(0, limit - used), "source": "header-sync" if state.get("date") == _wib_today() and state.get("used") else "local"}


def get(path, params=None, timeout=20):
    key = _load_key()
    url = BASE + path
    if params:
        from urllib.parse import urlencode
        url += "?" + urlencode(params)
    req = urllib.request.Request(url, headers={"X-API-Key": key, "User-Agent": "hermes-idx/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            lim = r.headers.get("x-ratelimit-limit")
            rem = r.headers.get("x-ratelimit-remaining")
            data = json.loads(r.read().decode())
            if lim is not None and rem is not None:
                lim, rem = int(lim), int(rem)
                _last_rate.update(limit=lim, remaining=rem)
                _sync_quota(lim - rem, lim)
            else:
                _bump_quota()  # endpoint tanpa header (mis. /api/health) → +1 lokal
            return data
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:200]
        if e.code == 429:
            raise RuntimeError(f"arjum 429 (kuota habis): {body}") from None
        raise RuntimeError(f"arjum {e.code} {path}: {body}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"arjum unreachable: {e.reason}") from None


def health():
    return get("/api/health")


def search(q):
    return get("/api/search", {"q": q})


def screener_latest(limit=None, bucket=None):
    params = {}
    if limit: params["limit"] = limit
    if bucket: params["bucket"] = bucket
    return get("/api/screener/latest", params or None)


def broker_summary(code):
    return get(f"/api/broker-summary/{code.upper()}")


def broker_accumulation(code, days=None):
    params = {"days": days} if days else None
    return get(f"/api/broker-accumulation/{code.upper()}", params)


def analysis(code):
    return get(f"/api/analysis/{code.upper()}")


def history(code, frame="daily"):
    return get(f"/api/history/{code.upper()}", {"frame": frame})


def seasonal(code):
    return get(f"/api/seasonal/{code.upper()}")


def financial_statements_proxy(code):
    return get(f"/api/financial-statements/{code.upper()}")


def market_cap_proxy():
    return get("/api/market-cap")


if __name__ == "__main__":
    import sys
    print("health:", health())
    print("rate:", rate_status())
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        arg = sys.argv[2] if len(sys.argv) > 2 else None
        if cmd == "screener":
            d = screener_latest()
            print(d["date"], "| rows:", len(d["rows"]))
            for r in d["rows"][:5]:
                print(" ", r["stock_code"], r["bucket"], "|", r["summary"][:80])
        elif cmd == "summary":
            d = broker_summary(arg)
            print(arg, "| brokers:", len(d.get("brokers", [])), "| net:", d.get("broker_net"))
        elif cmd == "history":
            d = history(arg, sys.argv[3] if len(sys.argv) > 3 else "daily")
            print(arg, d["frame"], "| rows:", len(d["rows"]), "| last:", d["rows"][0]["close"])
        elif cmd == "search":
            print(search(arg))
        elif cmd == "seasonal":
            print(arg, "| years:", seasonal(arg).get("years"))
        print("rate:", rate_status())
