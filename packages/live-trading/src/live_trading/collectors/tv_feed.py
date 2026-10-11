#!/usr/bin/env python3
"""Fetch real OHLC history for a TradingView symbol via its chart websocket.

Used to source TVC:GOLD (spot gold CFD, US$/oz) candles — the same series a
prop-firm / CFD trader sees, rather than COMEX futures which carry a 50-60 point
contango premium.

Public/unauthorized token gives access to delayed-but-complete history for
TVC:GOLD, which is sufficient for structural analysis.
"""

import asyncio
import json
import random
import re
import string
import sys

import websockets

WS_URL = "wss://data.tradingview.com/socket.io/websocket?from=chart%2F"
ORIGIN = "https://www.tradingview.com"


def _session(prefix):
    return prefix + "".join(random.choices(string.ascii_lowercase, k=12))


def _msg(func, args):
    body = json.dumps({"m": func, "p": args}, separators=(",", ":"))
    return f"~m~{len(body)}~m~{body}"


def _parse(raw):
    """Split the ~m~<len>~m~<payload> frames TradingView multiplexes."""
    out = []
    for part in re.split(r"~m~\d+~m~", raw):
        if not part:
            continue
        if part.startswith("~h~"):
            out.append({"_heartbeat": part})
            continue
        try:
            out.append(json.loads(part))
        except json.JSONDecodeError:
            pass
    return out


async def fetch(symbol="TVC:GOLD", resolution="60", bars=500, timeout=25):
    """Return a list of {t,o,h,l,c,v} dicts, oldest first."""
    chart = _session("cs_")
    series = "s1"
    candles = {}

    async with websockets.connect(
        WS_URL,
        origin=ORIGIN,
        additional_headers={"User-Agent": "Mozilla/5.0"},
        max_size=None,
        open_timeout=15,
        ping_interval=None,
    ) as ws:
        for func, args in [
            ("set_auth_token", ["unauthorized_user_token"]),
            ("chart_create_session", [chart, ""]),
            ("resolve_symbol", [chart, "sds_sym_1",
                                f'={{"symbol":"{symbol}","adjustment":"splits"}}']),
            ("create_series", [chart, "sds_1", series, "sds_sym_1", resolution, bars, ""]),
        ]:
            await ws.send(_msg(func, args))

        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        done = False

        while not done and loop.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=max(1, deadline - loop.time()))
            except (TimeoutError, websockets.exceptions.ConnectionClosed):
                break

            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", "replace")

            for packet in _parse(raw):
                if "_heartbeat" in packet:
                    # echo the heartbeat frame back verbatim to keep the socket open
                    hb = packet["_heartbeat"]
                    try:
                        await ws.send(f"~m~{len(hb)}~m~{hb}")
                    except websockets.exceptions.ConnectionClosed:
                        done = True
                    continue

                name = packet.get("m")

                if name in ("symbol_error", "series_error", "critical_error"):
                    raise RuntimeError(f"TradingView rejected {symbol}: {packet.get('p')}")

                if name == "timescale_update":
                    for blob in packet.get("p", []):
                        if not isinstance(blob, dict):
                            continue
                        node = blob.get("sds_1") or blob.get(series)
                        if not isinstance(node, dict):
                            continue
                        for row in node.get("s", []):
                            v = row.get("v") or []
                            if len(v) >= 5:
                                candles[int(v[0])] = {
                                    "t": int(v[0]), "o": v[1], "h": v[2],
                                    "l": v[3], "c": v[4],
                                    "v": v[5] if len(v) > 5 else 0,
                                }

                if name == "series_completed":
                    done = True

    return [candles[k] for k in sorted(candles)]


async def _main():
    symbol = sys.argv[1] if len(sys.argv) > 1 else "TVC:GOLD"
    resolution = sys.argv[2] if len(sys.argv) > 2 else "60"
    bars = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    rows = await fetch(symbol, resolution, bars)
    print(json.dumps(rows))


if __name__ == "__main__":
    asyncio.run(_main())
