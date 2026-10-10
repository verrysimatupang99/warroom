#!/usr/bin/env python3
"""Ara Hunter — replikasi resep screener (Kingdom Saham, V1) via TradingView.

Resep asli (screener "ARA" di Stockbit/DSI/NeoBDM):
  Price  >= 1.02 x prev close   -> change_pct >= 2
  Volume >= 2 x prev volume     -> relative volume >= 2 (proxy Volume/MA10)
  Volume >= 2 x Volume MA20     -> (sama, dijadikan satu dgn di atas)
  ADX(14) > 15
  Value  >= Rp10,000,000,000    -> close * volume >= 10e9

Upgrade 7 Sep 2026 (user request "intensif + model gratisan terbaik"):
  - LLM garnish: analisa 1 kalimat/saham via oc/mimo-v2.5-free
    (OpenCode Free via 9router localhost:20128; same route as topic-616 jobs).
    Model ini reasoning: max_tokens 2000 + parser strip blok thinking.
    Fallback diam ke format deterministik kalau LLM gagal.

Usage: ara_hunter.py [--min-chg 2] [--min-rvol 2] [--min-adx 15] [--min-value 10e9] [--top 15] [--post]
"""
import argparse
import datetime
from idx_clock import now_wib
import json
import re
import sys

TV_URL = "https://scanner.tradingview.com/indonesia/scan"
TV_HEADERS = {"origin": "https://www.tradingview.com", "referer": "https://www.tradingview.com/"}
LLM_MODEL = "oc/mimo-v2.5-free"


def _num(v):
    try:
        return round(float(v), 3) if v is not None else None
    except (TypeError, ValueError):
        return None


def scan():
    from curl_cffi import requests as cr
    s = cr.Session(impersonate="chrome")
    body = {
        "filter": [{"left": "type", "operation": "equal", "right": "stock"}],
        "columns": ["name", "close", "change", "volume", "ADX", "average_volume_10d_calc",
                    "market_cap_basic", "Pre Market Change"],
        "sort": {"sortBy": "volume", "sortOrder": "desc"},
        "range": [0, 900],
    }
    r = s.post(TV_URL, json=body, timeout=30, headers=TV_HEADERS)
    r.raise_for_status()
    out = []
    for d in r.json().get("data", []):
        v = d.get("d") or []
        if len(v) < 7:
            continue
        avg10 = _num(v[5])
        out.append({"symbol": d["s"].replace("IDX:", ""), "close": _num(v[1]),
                    "change_pct": _num(v[2]), "volume": _num(v[3]), "adx": _num(v[4]),
                    "avg10": avg10,
                    "rel_vol": round(v[3] / avg10, 2) if avg10 and v[3] else None,
                    "market_cap": _num(v[6])})
    return out


def llm_commentary(hits):
    """Analisa 1 kalimat/saham via model gratis terbaik (9router opencode free).
    Return dict sym->kalimat; {} kalau gagal (fallback deterministik). Never raises."""
    try:
        import urllib.request
        data = [{"sym": h["symbol"], "harga": h["close"], "chg_pct": h["change_pct"],
                 "rel_vol": h["rel_vol"], "adx": h["adx"]} for h in hits]
        body = json.dumps({
            "model": LLM_MODEL,
            "max_tokens": 2000,
            "messages": [{"role": "user", "content":
                "Kamu analis scalping saham IDX. Untuk tiap saham berikut (sym, harga, chg%, rel_vol, ADX), "
                "tulis SATU kalimat singkat dan spesifik soal momentum/risk scalping-nya dalam Bahasa Indonesia. "
                "JANGAN menulis proses berpikir. Format ketat: 'SYM: kalimat' satu per baris, "
                "tanpa header, tanpa disclaimer, tanpa pemanis.\n"
                + json.dumps(data)}],
        }).encode()
        # Versi lokal War Room: tidak pakai LLM komentar Tencent. Bila endpoint lokal
        # tak diset, kembalikan tanpa komentar — data tetap utuh tanpa mengarang teks.
        import os as _os
        base = _os.environ.get("ARA_LLM_BASE", "")
        key = _os.environ.get("ARA_LLM_KEY", "")
        if not base:
            return {}
        req = urllib.request.Request(base, data=body,
                                     headers={"Authorization": "Bearer " + key,
                                              "Content-Type": "application/json"})
        raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", errors="ignore")
        d = json.JSONDecoder().raw_decode(raw)[0]  # 9router kadang concat JSON — ambil pertama
        content = d["choices"][0]["message"].get("content") or ""
        out = {}
        # model reasoning kadang tetap ngeluarin thinking — cari baris SYM valid pertama
        first = re.search(r"^\**\s*([A-Z]{4})\s*:\s*\S", content, flags=re.M)
        if first:
            content = content[first.start():]
        for ln in content.splitlines():
            mm = re.match(r"^\**\s*([A-Z]{4})\s*:\s*(\S.*?)\s*$", ln.strip())
            if mm:
                sym, txt = mm.group(1).upper(), mm.group(2).strip().strip("*")
                if len(txt) > 10:
                    out[sym] = txt
        return out
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-chg", type=float, default=5.0)
    ap.add_argument("--min-rvol", type=float, default=3.0)
    ap.add_argument("--min-adx", type=float, default=15.0)
    ap.add_argument("--min-value", type=float, default=1e9)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--post", action="store_true")
    args = ap.parse_args()

    try:
        rows = scan()
    except Exception as e:
        print(f"[ara_hunter] FAIL: {e}", file=sys.stderr)
        return 1

    hits = [x for x in rows
            if (x["change_pct"] or 0) >= args.min_chg
            and (x["rel_vol"] or 0) >= args.min_rvol
            and (x["adx"] or 0) > args.min_adx
            and (x["close"] or 0) * (x["volume"] or 0) >= args.min_value]
    hits.sort(key=lambda x: -(x["rel_vol"] or 0))
    hits = hits[:args.top]

    # archive untuk dashboard (versi lokal War Room)
    try:
        import os as _os
        _dir = _os.path.dirname(_os.path.abspath(__file__)) + "/../data"
        _os.makedirs(_dir, exist_ok=True)
        with open(_dir + "/ara_hunter_latest.json", "w") as f:
            json.dump({"time": now_wib().strftime("%Y-%m-%d %H:%M:%S"),
                       "scanned": len(rows), "hits": hits}, f, default=str)
    except Exception:
        pass

    if not args.post:
        print(json.dumps({"time": now_wib().strftime("%F %T"),
                          "scanned": len(rows), "hits": hits}, default=str)[:4000])
        return 0

    now = now_wib().strftime("%H:%M")
    if not hits:
        print("[SILENT] tidak ada kandidat ara hari ini", file=sys.stderr)
        return 0
    comments = llm_commentary(hits)
    lines = [f"🏹 *ARA HUNTER* — {now} WIB",
             "Resep: chg >=5% · rel vol >=3x · ADX>15 · value >=Rp1B — walk-forward verified 11 Sep (+1.00% net/trade, exit open T+1)",
             "─────────────────────"]
    for x in hits:
        e = "🟢" if (x["change_pct"] or 0) >= 5 else "⚪"
        lines.append(f"• {e} *{x['symbol']}* {x['close']:,.0f} (+{x['change_pct']:.1f}%) | "
                     f"rel vol {x['rel_vol']:.1f}x | ADX {x['adx']:.0f}")
        if x["symbol"] in comments:
            lines.append(f"   ↳ {comments[x['symbol']]}")
    lines += ["", "⚠️ Ara/ATS berisiko: jangan kejar gain >15%, waspada lock price atas. "
              "Bukan rekomendasi jual/beli.",
              f"— Hermes Ara Hunter + {LLM_MODEL} (opencode free)"]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
