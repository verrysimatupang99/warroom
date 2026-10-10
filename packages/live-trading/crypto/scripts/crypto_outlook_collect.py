#!/usr/bin/env python3
"""Morning outlook collector for thread 648.
OKX swap digest (BTC/ETH focus) + CoinGecko global & OTHERS proxy.
Printed to stdout for the cron agent to compose a two-scenario outlook.
"""
import json
import subprocess
import sys

from crypto_signal_collect import analyze, WATCHLIST


def curl(url):
    try:
        return json.loads(subprocess.run(
            ["curl", "-s", "--max-time", "12", url],
            capture_output=True, text=True, timeout=18,
        ).stdout)
    except Exception:
        return None


def main():
    lines = ["=== MORNING OUTLOOK COLLECTOR ==="]

    g = curl("https://api.coingecko.com/api/v3/global")
    top = curl(
        "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd"
        "&order=market_cap_desc&per_page=10&page=1"
    )
    if g and "data" in g:
        d = g["data"]
        total = d["total_market_cap"]["usd"]
        dom = d["market_cap_percentage"]
        lines.append(
            f"GLOBAL: mcap ${total/1e12:.3f}T "
            f"({d.get('market_cap_change_percentage_24h_usd', 0):+.2f}% 24h) | "
            f"BTC dom {dom.get('btc', 0):.2f}% | ETH dom {dom.get('eth', 0):.2f}%"
        )
        if isinstance(top, list) and len(top) >= 10:
            top10 = sum(c["market_cap"] for c in top[:10])
            others = total - top10
            lines.append(f"OTHERS proxy (total - top10): ${others/1e9:.1f}B")
            alts = [
                f"{c['symbol'].upper()} {c.get('price_change_percentage_24h', 0):+.1f}%"
                for c in top[1:] if c["symbol"] and len(c["symbol"]) <= 5
            ]
            lines.append("Top10 24h: BTC "
                         f"{top[0].get('price_change_percentage_24h',0):+.1f}%, "
                         + ", ".join(alts))
    else:
        lines.append("GLOBAL: data gagal")

    focus = ["BTC_USDT", "ETH_USDT", "SOL_USDT"]
    rest = [s for s in WATCHLIST if s not in focus]
    for sym in focus + rest:
        r = analyze(sym)
        if not r:
            lines.append(f"\n--- {sym}: DATA GAGAL ---")
            continue
        tag = "FOCUS" if sym in focus else "watch"
        lines.append(
            f"\n--- {sym} [{tag}] | perp ${r['price']:,.4g} | 24h {r['chg24h']:+.2f}% "
            f"| funding {r['funding']} ---"
        )
        label = {"Week1": "1W", "Day1": "1D", "Hour4": "4H", "Min60": "1H"}
        for tf, lab in label.items():
            lines.append(f"  [{lab}] {r.get(tf, 'n/a')}")

    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
