#!/usr/bin/env python3
"""Sinkronisasi feed data pasar eksternal (brand AXYNODE, sumber publik).

Sumbernya semua publik (tanpa kunci — desain AXYNODE sendiri read-only):
  - Binance fapi premiumIndex  -> funding perpeti seluruh simbol
  - Binance fapi ticker/24hr   -> volume & harga perpeti
  - alternative.me FNG         -> Fear & Greed indeks + seri 8 hari
Diterbitkan sebagai fakta `axynode/ringkas` (ttl 1 jam) untuk panel /sistem.

Kredensial akun AXYNODE (terminal web) disimpan terpisah di
/etc/warroom/axynode.env (mode 600) — tidak pernah masuk repo/log.
"""

from __future__ import annotations

import datetime as dt
import os
import sys

import httpx

URL_FNG = "https://api.alternative.me/fng/?limit=8"
URL_FUNDING = "https://fapi.binance.com/fapi/v1/premiumIndex"
URL_TICKERS = "https://fapi.binance.com/fapi/v1/ticker/24hr"
STABLE = {"USDCUSDT", "FDUSDUSDT", "TUSDUSDT", "BUSDUSDT", "DAIUSDT", "EURUSDT"}


def _unduh() -> dict:
    out: dict = {}
    fng = httpx.get(URL_FNG, timeout=20.0).json().get("data") or []
    if fng:
        out["fng"] = {"nilai": int(fng[-1]["value"]), "label": fng[-1]["value_classification"],
                      "seri": [{"nilai": int(x["value"]), "ts": x["timestamp"]} for x in fng]}
    prem = httpx.get(URL_FUNDING, timeout=30.0).json()
    tick = httpx.get(URL_TICKERS, timeout=30.0).json()
    vol: dict[str, float] = {}
    for t in tick:
        s = t.get("symbol", "")
        if s.endswith("USDT"):
            vol[s] = float(t.get("quoteVolume") or 0.0)
    funding = []
    for p in prem:
        s = p.get("symbol", "")
        if not s.endswith("USDT") or s in STABLE:
            continue
        fr = float(p.get("lastFundingRate") or 0.0) * 100
        funding.append({"simbol": s, "funding_pct": round(fr, 4), "volume": vol.get(s, 0.0)})
    # hanya simbol likuid (volume dua sisi signifikan) supaya daftar tak dipenuhi dust
    likuid = [f for f in funding if f["volume"] >= 5_000_000]
    likuid.sort(key=lambda f: abs(f["funding_pct"]), reverse=True)
    out["funding"] = {
        "jumlah_simbol": len(funding),
        "ekstrem": likuid[:8],
        "rata_semua": round(sum(f["funding_pct"] for f in likuid) / len(likuid), 4) if likuid else None,
    }
    return out


def main() -> int:
    os.environ.setdefault("LT_HOME", "/home/admin/live-trading")
    try:
        data = _unduh()
    except httpx.HTTPError as exc:
        print(f"axynode-sinkron: galat jaringan {type(exc).__name__}: {exc}")
        return 1

    from warroom_core.db import session_scope
    from warroom_worker.jobs.base import _tulis_fakta

    value = {
        "sumber": ["fapi.binance.com (funding+perp)", "alternative.me (FNG)"],
        "data": data,
        "updated": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
    }
    with session_scope() as s:
        _tulis_fakta(s, kind="axynode", key="ringkas", value=value,
                     source="ops/axynode_sinkron.py", ttl_s=7200)
    f = value["data"].get("fng", {})
    print(f"axynode/ringkas terbit: FNG {f.get('nilai', '—')} ({f.get('label', '—')}), "
          f"simbol funding {value['data'].get('funding', {}).get('jumlah_simbol')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
