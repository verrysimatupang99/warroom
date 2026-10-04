"""CLI: ``lt doctor`` / ``lt paths`` / ``lt ledger``.

``doctor`` sengaja jadi perintah pertama: sebelum menyentuh uang, semua jalur
data harus terbukti hidup dari mesin ini.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from .config import get_settings


def _check(client: httpx.Client, name: str, url: str, *, headers: dict[str, str] | None = None) -> dict:
    t0 = time.perf_counter()
    try:
        r = client.get(url, headers=headers)
        ms = (time.perf_counter() - t0) * 1000
        ok = r.status_code == 200
        return {"name": name, "ok": ok, "detail": f"HTTP {r.status_code}", "ms": round(ms)}
    except Exception as exc:  # noqa: BLE001 — laporan diagnostik, bukan jalur kritis
        ms = (time.perf_counter() - t0) * 1000
        return {"name": name, "ok": False, "detail": type(exc).__name__, "ms": round(ms)}


def _arjum_key(path: Path) -> str | None:
    try:
        key = path.read_text(encoding="utf-8").strip()
        return key or None
    except OSError:
        return None


def cmd_doctor(args: argparse.Namespace) -> int:
    s = get_settings()
    checks: list[dict] = []

    with httpx.Client(timeout=15.0, follow_redirects=True) as c:
        checks.append(_check(c, "binance perp", f"{s.binance_fapi}/fapi/v1/ticker/price?symbol=BTCUSDT"))
        checks.append(
            _check(c, "binance coin-m", f"{s.binance_dapi}/dapi/v1/ticker/price?symbol=BTCUSD_PERP")
        )
        checks.append(_check(c, "mexc futures", f"{s.mexc_contract}/api/v1/contract/ticker?symbol=BTC_USDT"))
        checks.append(_check(c, "coingecko global", f"{s.coingecko}/global"))
        checks.append(_check(c, "fear & greed", f"{s.feargreed}/fng/?limit=1"))
        checks.append(
            _check(
                c,
                "tradingview",
                f"{s.tradingview_scanner}/symbol?symbol=OANDA%3AXAUUSD&fields=close,change&no_404=true",
            )
        )

        key = _arjum_key(s.arjum_key_path)
        if key:
            checks.append(_check(c, "arjum (IDX)", f"{s.arjum_base}/api/health", headers={"X-API-Key": key}))
        else:
            checks.append({"name": "arjum (IDX)", "ok": False, "detail": "key tidak ada", "ms": 0})

    width = max(len(c["name"]) for c in checks)
    failed = 0
    for c in checks:
        mark = "OK  " if c["ok"] else "GAGAL"
        if not c["ok"]:
            failed += 1
        print(f"  [{mark}] {c['name']:<{width}}  {c['detail']:<12} {c['ms']:>5} ms")

    print()
    print(f"  mode: {'PAPER' if s.paper else 'LIVE'}   |   rumah: {s.home}")
    print(f"  {'semua jalur data hidup' if not failed else f'{failed} jalur bermasalah'}")
    return 1 if failed else 0


def cmd_paths(args: argparse.Namespace) -> int:
    s = get_settings()
    out = {
        "home": str(s.home),
        "state_dir": str(s.state_dir),
        "secret_dir": str(s.secrets_dir),
        "journal_dir": str(s.journal_dir),
        "ledger": str(s.ledger_path),
        "watchlist": str(s.watchlist_path),
        "executor_lock": str(s.executor_lock_path),
        "mode": "paper" if s.paper else "live",
    }
    print(json.dumps(out, indent=2))
    return 0


def cmd_ledger(args: argparse.Namespace) -> int:
    s = get_settings()
    if not s.ledger_path.exists():
        print(f"  ledger belum ada: {s.ledger_path}")
        return 0
    rows = []
    for line in s.ledger_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    total_r = sum(float(r.get("r") or 0) for r in rows)
    wins = sum(1 for r in rows if float(r.get("r") or 0) > 0)
    print(f"  posisi penuh : {s.ledger_path}")
    print(f"  trade        : {len(rows)}")
    print(f"  total R      : {total_r:+.3f}")
    if rows:
        print(f"  winrate      : {wins / len(rows) * 100:.1f}%")
        print(f"  expectancy   : {total_r / len(rows):+.3f} R/trade")
    return 0


def cmd_equity(args: argparse.Namespace) -> int:
    """Kurva ekuitas kumulatif (R) + statistik ledger."""
    from . import equity

    _ = args
    s = get_settings()
    c = equity.curve(s)
    st = c["stats"]
    print(f"  ledger       : {s.ledger_path}")
    print(f"  trade        : {st['trades']}")
    if not st["trades"]:
        print("  belum ada trade tertutup")
        return 0
    print(f"  total R      : {st['total_r']:+.2f}")
    print(f"  winrate      : {st['winrate_pct']}% ({st['wins']}W/{st['losses']}L)")
    print(f"  expectancy   : {st['expectancy_r']:+.3f} R/trade")
    print(f"  max drawdown : {st['max_drawdown_r']:.2f}R")
    pf = st["profit_factor"]
    print(f"  profit factor: {pf if pf is not None else 'n/a'}")
    print("  kurva (5 titik terakhir):")
    for p in c["points"][-5:]:
        print(f"    #{p['i']:<3} {str(p.get('pair')):<12} {str(p.get('status')):<12} cum {p['cum']:+.2f}R")
    return 0


def _collect_idx() -> int:
    from .collectors.idx import ArjumCollector

    s = get_settings()
    c = ArjumCollector(s)
    data = c.screener(limit=5)
    q = c.quota()
    print(f"  IDX — Arjum screener ({data.get('source', '?')})")
    print(f"  kuota: {q.get('remaining', '?')}/{q.get('limit', s.arjum_daily_quota)}")
    for row in (data.get("rows") or [])[:5]:
        code = row.get("stock_code", "?")
        bucket = row.get("bucket", "")
        wr = row.get("wr_event")
        pot = row.get("potential")
        print(f"    {code:<6} {bucket:<22} WR {wr}%  potensi {pot}%")
    return 0


def _collect_forex() -> int:
    from .collectors.forex import ForexCollector

    c = ForexCollector(get_settings())
    st = c.structure("60", 120)
    print(f"  FOREX — {st['symbol']} ({st['resolution']}m, {st['bars']} candle)")
    print(
        f"    close {st['close']}  EMA20 {st['ema20']}  EMA50 {st['ema50']}  "
        f"ATR14 {st['atr14']} ({st['atr_pct']}%)  bias {st['bias']}"
    )
    return 0


def _collect_crypto() -> int:
    from .collectors.crypto import CryptoCollector

    c = CryptoCollector(get_settings())
    rows = c.digest()
    print("  CRYPTO — Binance perp (data publik)")
    print(f"    {'pair':<10} {'harga':>10} {'24j':>7} {'funding':>9} {'taker':>7} {'vol $M':>8}")
    for r in rows:
        if "error" in r:
            print(f"    {r['pair']:<10} GAGAL: {r['error']}")
            continue
        print(
            f"    {r['pair']:<10} {r['price']:>10,.2f} {r['chg24h']:>6.2f}% "
            f"{r['funding']:>8.4f}% {str(r['taker']):>7} {r['quote_vol']:>8,.1f}"
        )
    ex = c.mexc_check()
    print(f"    jalur eksekusi MEXC: {'hidup' if ex['ok'] else 'MATI'} ({ex['symbol']} @ {ex['last']})")
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    targets = {"idx": [_collect_idx], "forex": [_collect_forex], "crypto": [_collect_crypto]}
    if args.market == "all":
        fns = [_collect_crypto, _collect_idx, _collect_forex]
    else:
        fns = targets[args.market]

    failed = 0
    for i, fn in enumerate(fns):
        if i:
            print()
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 — satu market gagal jangan bunuh sisanya
            failed += 1
            print(f"  GAGAL: {type(exc).__name__}: {exc}")
    return 1 if failed else 0


def cmd_risk(args: argparse.Namespace) -> int:
    from .risk import RiskGate

    st = RiskGate(get_settings()).status()
    print("  mode              :", st["mode"])
    day_r = st["hari_ini_r"]
    print(
        f"  R hari ini        : {day_r:+.3f}  (batas -{st['batas_rugi_r']}, sisa ruang {st['sisa_ruang_r']})"
    )
    print(f"  posisi terbuka    : {st['posisi_terbuka']}/{st['maks_posisi']}")
    print(f"  risiko per trade  : {st['risiko_per_trade_pct']}% ekuitas")
    print(f"  total trade       : {st['total_trade']}")
    lock = st["kunci_executor"]
    print(
        f"  kunci executor    : {'DIPEGANG ' + str(lock['host']) if lock['held'] else 'bebas'}"
        + (f" ({lock['age_s']}s lalu)" if lock.get("age_s") is not None else "")
    )
    return 0


def cmd_paper(args: argparse.Namespace) -> int:
    from .execution.paper import PaperBroker

    s = get_settings()
    venue = (getattr(args, "venue", None) or "crypto").lower()
    b = PaperBroker(s, venue=venue)

    if args.aksi == "list":
        pos = b.positions()
        if not pos:
            print(f"  tidak ada posisi paper ({venue})")
            return 0
        for p in pos:
            print(
                f"  {p.signal_id}  {p.pair:<10} {p.direction:<5} entry {p.entry} stop {p.stop} "
                f"tp1 {p.tp1} tp2 {p.tp2} size ${p.size_usd} [{p.status}] ({venue})"
            )
        return 0

    if args.aksi == "open":
        from .risk import RiskGate

        gate = RiskGate(s, venue=venue)
        equity = args.equity or (s.venue_equity_usd if venue != "crypto" else s.equity_usd)
        atr_val = args.atr if args.atr else abs(args.entry - args.stop) / 1.5
        decision = gate.check(pair=args.pair, price=args.entry, atr=atr_val, equity_usd=equity)
        print(f"  risk gate [{venue}]: {'IZIN' if decision.allowed else 'TOLAK'} — {decision.reason}")
        if not decision.allowed:
            return 1
        pos = b.open_position(
            pair=args.pair,
            direction=args.direction,
            entry=args.entry,
            stop=args.stop,
            tp1=args.tp1,
            tp2=args.tp2,
            size_usd=decision.size_usd or 0.0,
            note=f"size dari risk gate ({decision.risk_usd} USD risiko, venue {venue})",
        )
        print(f"  dibuka: {pos.signal_id} {pos.pair} {pos.direction} size ${pos.size_usd} [{venue}]")
        return 0

    if args.aksi == "close":
        rec = b.close_position(args.signal_id, args.price, args.status, args.note)
        print(f"  ditutup: {rec['signal_id']} {rec['status']} R={rec['r']:+.3f} [{venue}]")
        return 0

    if args.aksi == "eval":
        prices: dict[str, float] = {}
        pairs = {p.pair for p in b.positions()}
        if pairs:
            if venue == "crypto":
                from .collectors.crypto import CryptoCollector

                c = CryptoCollector(s)
                for pair in pairs:
                    try:
                        prices[pair] = c.pair_snapshot(pair, klines=2)["price"]
                    except Exception:
                        continue
            elif venue == "forex":
                from .collectors.forex import ForexCollector

                fc = ForexCollector(s)
                st = fc.structure("60", 120)
                for p_info in (st.get("pairs") or []):
                    code = p_info.get("pair")
                    pr = p_info.get("price")
                    if code and pr:
                        prices[code] = float(pr)
            elif venue == "idx":
                from .collectors.idx_check import tv_snapshot

                snap = tv_snapshot(list(pairs))
                for item in snap:
                    pr = item.get("close")
                    ticker = item.get("ticker")
                    if ticker and pr:
                        prices[ticker] = float(pr)
            elif venue == "gmgn":
                from .collectors import dexscreen

                for pair in pairs:
                    try:
                        res = dexscreen.cari_pool(pair)
                        if res and res[0].get("priceUsd"):
                            prices[pair] = float(res[0]["priceUsd"])
                    except Exception:
                        continue
        closed = b.evaluate(prices)
        print(f"  [{venue}] harga diperiksa: {len(prices)} pair | ditutup: {len(closed)}")
        for rec in closed:
            print(f"    {rec['signal_id']} {rec['pair']} {rec['status']} R={rec['r']:+.3f}")
        return 0

    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    from .dashboard import build_snapshot

    s = get_settings()
    snap = build_snapshot(s, use_network=not args.offline)
    s.state_dir.mkdir(parents=True, exist_ok=True)
    p = s.state_dir / "snapshot.json"
    p.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    print(f"  snapshot ditulis: {p}")
    print(f"  dibuat {snap['dibuat']} | mode {snap['mode']}")
    for name, part in snap.get("bagian", {}).items():
        status = "error" if isinstance(part, dict) and part.get("error") else "ok"
        print(f"    {name:<8} {status}")
    print(f"  ledger: {snap['ledger']['trade']} trade, {snap['ledger']['total_r']:+}R")
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    from .dashboard import serve

    serve(get_settings())
    return 0


def cmd_agents(args: argparse.Namespace) -> int:
    """Tampilkan 6-agent untuk satu pair — hipotesis, bukan gate."""
    from .signals import agents as ag

    s = get_settings()
    out = ag.collect(s, args.pair.upper())
    print(f"  {out['pair']} · confluence {out['confluence']} (n={out['n_voting']}) — DICATAT, bukan gate")
    for name, a in out["agents"].items():
        b = a.get("bias")
        b_txt = f"{b:+.2f}" if b is not None else "n/a "
        note = a.get("note")
        if note == "n/a":
            note = "data " + ", ".join(f"{k}={v}" for k, v in (a.get("data") or {}).items())
        print(f"    {name:<10} bias {b_txt}  {note}")
    return 0


def cmd_smc(args: argparse.Namespace) -> int:
    """Struktur pasar + verdict gate — semua deterministik, tanpa LLM."""
    from .signals import engine

    s = get_settings()
    pair = args.pair.upper()

    ag_data = None
    if getattr(args, "agents", False):
        from .signals import agents as ag

        ag_data = ag.collect(s, pair)
        print(f"  agents: confluence {ag_data['confluence']} (n={ag_data['n_voting']}) — dicatat, bukan gate")

    if args.direction:
        st, prop, hasil = engine.evaluate(
            s,
            pair,
            args.direction,
            entry=args.entry,
            sl=args.sl,
            tp1=args.tp1,
            agents=ag_data,
        )
    else:
        st = engine.analyze(s, pair)
        prop, hasil = None, None

    print(f"  {st.pair} @ {st.price:,.6g}")
    atr_txt = f"{st.atr_pct:.2f}%" if st.atr_pct is not None else "n/a"
    bias_txt = f"1h {st.bias.get('1h')} / 4h {st.bias.get('4h')} / 1d {st.bias.get('1d')}"
    print(f"  ATR1H {atr_txt}  |  bias {bias_txt}")

    def show(label: str, poi: dict | None) -> None:
        if poi:
            print(
                f"  POI {label:<5}: {poi['kind']:<6} "
                f"[{poi['low']:,.6g} - {poi['high']:,.6g}] mid {poi['mid']:,.6g}"
            )
        else:
            print(f"  POI {label:<5}: tidak ada")

    show("long", st.poi_bullish)
    show("short", st.poi_bearish)
    sl_txt = f"{st.swing_low:,.6g}" if st.swing_low else "n/a"
    sh_txt = f"{st.swing_high:,.6g}" if st.swing_high else "n/a"
    print(f"  swing low {sl_txt} / swing high {sh_txt}  |  24j {st.low_24h:,.6g} - {st.high_24h:,.6g}")

    if prop:
        print()
        print(
            f"  USULAN {prop['direction']}: entry {prop['entry']:,.6g}  SL {prop['sl']:,.6g} "
            f"({prop['risk_pct']}%)  TP1 {prop['tp1']:,.6g}  TP2 {prop['tp2']:,.6g}"
        )

    if hasil:
        print()
        for v in hasil.verdicts:
            mark = "OK   " if v.ok else "GAGAL"
            keras = "" if v.hard else " (lunak)"
            print(f"    [{mark}] {v.rule}{keras}: {v.reason}")
        print(f"  VERDICT: {hasil.summary()}")
        if hasil.duplicate_of:
            print(f"  (duplikat dari kandidat {hasil.duplicate_of} — tidak dicatat ulang)")
        try:
            from .collectors.hyperliquid import context_for

            konteks = context_for(pair)
            if konteks:
                print(
                    f"  konteks HL   : OI ${konteks['oi_usd'] / 1e6:,.0f}M · "
                    f"funding {konteks['funding_hourly_pct']:+.4f}%/jam "
                    f"({konteks['funding_annual_pct']:+.0f}%/tahun) — konteks, BUKAN gate"
                )
        except Exception:  # noqa: BLE001 — konteks opsional, jangan gagalkan analisis
            pass
        return 0 if hasil.allowed else 2
    return 0


def cmd_verdicts(args: argparse.Namespace) -> int:
    """Ringkasan verdict: berapa kandidat lolos, dan aturan mana yang paling sering menolak."""
    from .signals.engine import summarize_verdicts

    s = get_settings()
    d = summarize_verdicts(s)
    if not d["total"]:
        print(f"  belum ada verdict di {s.state_dir / 'verdicts.jsonl'}")
        return 0
    lolos = d["allowed"]
    print(f"  total kandidat dinilai : {d['total']}")
    print(f"  lolos semua gate       : {lolos} ({lolos / d['total'] * 100:.1f}%)")
    print("  penolakan per aturan:")
    for rule, slot in sorted(d["per_rule"].items(), key=lambda kv: -kv[1]["gagal"]):
        total = slot["lolos"] + slot["gagal"]
        print(f"    {rule:<16} gagal {slot['gagal']:>4}/{total:<4} ({slot['gagal'] / total * 100:5.1f}%)")
    return 0


UNIVERSE_DEFAULT = [
    # mayor
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "SUIUSDT",
    "DOGEUSDT",
    "LINKUSDT",
    "AVAXUSDT",
    "ARBUSDT",
    "INJUSDT",
    "OPUSDT",
    # alt ber-ATR lebih tinggi — di sinilah aturan ATR>=1% masuk akal
    "ENAUSDT",
    "FILUSDT",
    "TIAUSDT",
    "SEIUSDT",
    "APTUSDT",
    "AAVEUSDT",
    "ORDIUSDT",
    "1000PEPEUSDT",
    "WIFUSDT",
    "CRVUSDT",
]


def cmd_scan(args: argparse.Namespace) -> int:
    """Pindai daftar pair — hanya arah yang didukung struktur (4H & 1H kompak)."""
    from .signals import engine

    s = get_settings()
    if args.top:
        from .signals.engine import top_pairs

        pairs = top_pairs(s, args.top)
        print(f"  memindai {len(pairs)} pair teratas menurut volume 24 jam nyata")
    else:
        pairs = [p.upper() for p in (args.pairs or UNIVERSE_DEFAULT)]
    rows = engine.scan(s, pairs)
    for r in rows:
        if r["direction"]:
            mark = "IZIN " if r.get("allowed") else "TOLAK"
            print(f"  {r['pair']:<10} {r['direction']:<5} {mark:<5} {r['tier']:<8} {r['note'][:96]}")
        else:
            print(f"  {r['pair']:<10} {'—':<5} {'—':<5} {r['tier']:<8} {r['note'][:96]}")
    lolos = sum(1 for r in rows if r.get("allowed"))
    dinilai = sum(1 for r in rows if r["direction"])
    dup = sum(1 for r in rows if r["tier"] == "DUPLIKAT")
    print(
        f"\n  {len(rows)} pair dipindai · {dinilai} punya arah jelas · "
        f"{dup} duplikat (tidak dicatat ulang) · {lolos} lolos semua gate"
    )
    return 0


def cmd_depth(args: argparse.Namespace) -> int:
    """Kedalaman buku order: berapa notional yang benar-benar tersedia di tiap level bps.

    Menjawab asumsi paling menentukan di uji maker: apakah limit order kita terisi pada
    kedalaman ≤5 bps. Tanpa pengukuran ini, "edge +0,030R" hanya berlaku di atas kertas.
    """
    from .collectors.depth import DepthCollector, notional_at_bps

    c = DepthCollector(get_settings())
    pairs = tuple(args.pairs) if args.pairs else (
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "ZECUSDT", "LINKUSDT", "SUIUSDT", "HYPEUSDT", "FETUSDT")
    # Hanya tampilkan kolom yang benar-benar dikumpulkan. Menampilkan kolom di atas
    # ambang akan memperlihatkan angka yang terpotong di ambang — menyesatkan.
    cols = tuple(b for b in (1, 5, 10, 20) if b <= args.max_bps) or (args.max_bps,)
    print(f"  kedalaman buku (Binance futures, {len(pairs)} pair, ambang {args.max_bps:g} bps)")
    print(f"  {'pair':<10}{'mid':>12}" + "".join(f"{'≤' + str(b) + 'bps':>12}" for b in cols))
    for p in pairs:
        r = c.report(p, limit=100, max_bps=args.max_bps)
        if "error" in r:
            print(f"  {p:<10}  error: {r['error'][:50]}")
            continue
        # sisi yang dipakai limit BUY adalah bid (kita menunggu di bawah mid)
        row = "".join(f"{notional_at_bps(r, 'bid', b):>12,.0f}" for b in cols)
        print(f"  {p:<10}{r['mid']:>12.6g}{row}")
    print()
    print("  Cara membaca: angka = notional yang TERLIHAT di buku pada kedalaman itu (sisi bid).")
    print("  BATAS: ini bukan jaminan terisi. Snapshot tidak memuat posisi antrean — kalau")
    print("  ada lot yang mengantre di depan kita, kita tidak dapat bagiannya.")
    print("  Ukuran posisi sistem ini kecil (ratusan dolar), jadi pair besar jelas cukup;")
    print("  yang perlu diperiksa adalah pair tipis (FET/LINK di atas).")
    return 0


def cmd_hl(args: argparse.Namespace) -> int:
    """Hyperliquid: OI + funding. Konteks positioning, bukan gate."""
    from .collectors import hyperliquid

    snap = hyperliquid.snapshot(get_settings(), top=args.top)
    print(f"  perp aktif: {snap['total_perp']}")
    print("  OI terbesar:")
    for r in snap["top_by_oi"]:
        print(
            f"    {r['coin']:<8} mark {r['mark']:>12,.4f}   "
            f"OI ${r['oi_usd'] / 1e6:>9,.1f}M   funding {r['funding_hourly_pct']:+.4f}%/jam"
        )
    print("  funding paling negatif (sisi short ramai):")
    for r in snap["funding_most_negative"]:
        print(
            f"    {r['coin']:<8} {r['funding_hourly_pct']:+.4f}%/jam  ({r['funding_annual_pct']:+.0f}%/tahun)"
        )
    print("  funding paling positif (sisi long ramai):")
    for r in snap["funding_most_positive"]:
        print(
            f"    {r['coin']:<8} {r['funding_hourly_pct']:+.4f}%/jam  ({r['funding_annual_pct']:+.0f}%/tahun)"
        )
    print("\n  catatan: ini konteks, BUKAN gate — tidak membatalkan/mengizinkan setup.")
    return 0


def cmd_idxtv(args: argparse.Namespace) -> int:
    """Screener IDX lewat TradingView (tanpa kunci)."""
    from .collectors import idx_tv

    rows = idx_tv.screen(
        min_volume=args.min_volume,
        limit=args.limit,
        uptrend_only=args.uptrend,
        rsi_below=args.rsi_below,
        sort_by=args.sort,
    )
    for r in rows:
        rsi = f"{r['rsi14']:.1f}" if r["rsi14"] is not None else " n/a"
        chg = f"{r['change_pct']:+.2f}%" if r["change_pct"] is not None else "   n/a"
        print(
            f"    {r['ticker']:<6} {r['close']:>9,.0f}  {chg:>8}  "
            f"vol {r['volume'] / 1e6:>8,.1f}jt  RSI {rsi:>5}  EMA {r['ema_state']}"
        )
    s = idx_tv.summary(rows)
    print(f"\n    {s['jumlah']} saham · EMA8>EMA21: {s['ema_naik']} · EMA8<EMA21: {s['ema_turun']}")
    print("    'EMA naik' = keadaan sekarang, BUKAN cross baru (scanner tidak memberi nilai EMA sebelumnya)")
    return 0


def cmd_bandar(args: argparse.Namespace) -> int:
    """Bandarmologi IDX lewat Stockbit — butuh token sesi."""
    from .collectors import idx_stockbit

    s = get_settings()
    tok = idx_stockbit.load_token(s)
    if not tok:
        info = idx_stockbit.broker_summary(args.symbol)
        print(f"  {info['error']}")
        print(f"  {info['petunjuk']}")
        print(f"  letak berkas: {idx_stockbit.secrets_dir(s) / idx_stockbit.TOKEN_FILENAME}")
        return 1

    view = idx_stockbit.bandar_view(args.symbol, args.period, tok)
    ring = view["ringkasan"]
    if "error" in ring:
        print(f"  gagal: {ring['error']}")
        return 1
    print(f"  {ring['symbol']} · jendela {ring['jendela'][0]} → {ring['jendela'][1]}")
    bandar = ring["bandar"]
    print(
        f"  bandar: {bandar.get('accdist')} "
        f"(pembeli {bandar.get('total_buyer')} / penjual {bandar.get('total_seller')})"
    )
    for label, key in (("pembeli", "pembeli"), ("penjual", "penjual")):
        for b in ring[key]:
            val = b["net_idr"] or 0
            print(
                f"    {label:<8} {b['broker']:<4} {b['type'] or '':<6} "
                f"{val / 1e9:>8,.1f} M  ({b['freq']} frek)"
            )
    dist = view["distribusi"]
    if "error" not in dist:
        print(f"  distribusi {dist['jendela'][0]} → {dist['jendela'][1]} ({dist['satuan']})")
        for b in dist.get("top_broker_buy", []):
            ke = ", ".join(f"{x['broker']} ({(x['amount'] or 0) / 1e9:,.1f}M)" for x in b["menyalur_ke"])
            print(f"    {b['broker']} → {ke}")
    return 0


def cmd_idx_check(args: argparse.Namespace) -> int:
    """Cross-check temuan Arjum dengan keadaan harga TradingView."""
    from .collectors.idx import ArjumCollector
    from .collectors.idx_check import gabungkan, tv_snapshot

    s = get_settings()
    rows = ArjumCollector(s).screener(limit=args.limit).get("rows") or []
    if not rows:
        print("  Arjum tidak mengembalikan baris")
        return 1
    tv = tv_snapshot([str(r.get("stock_code", "")) for r in rows])
    gab = gabungkan(rows, tv)

    for r in gab:
        harga = f"{r['harga']:,.0f}" if r["harga"] is not None else "  n/a"
        chg = f"{r['chg_pct']:+.2f}%" if r["chg_pct"] is not None else "   n/a"
        rsi = f"{r['rsi14']:.1f}" if r["rsi14"] is not None else "n/a"
        print(
            f"    {r['kode']:<6} {harga:>9} {chg:>8}  RSI {rsi:>5}  EMA {r['ema_state']:<5} "
            f"{r['maksud']:<9} → {r['putusan']}"
        )
        if r["putusan"] != "netral":
            print(f"           {r['alasan']}")
    sejalan = sum(1 for r in gab if r["putusan"] == "sejalan")
    bentrok = sum(1 for r in gab if r["putusan"] == "bertentangan")
    print(f"\n    {len(gab)} temuan Arjum · sejalan {sejalan} · bertentangan {bentrok}")
    print("    'keadaan' EMA = sekarang, bukan cross baru (batas TradingView).")
    return 0


def cmd_dedupe(args: argparse.Namespace) -> int:
    """Bersihkan catatan kandidat ganda yang sempat masuk sebelum dedupe dipasang."""
    from .signals.engine import purge_duplicates

    s = get_settings()
    hasil = purge_duplicates(s, apply=args.apply)
    print(f"  total baris    : {hasil['total']}")
    print(f"  duplikat       : {hasil['dibuang']}")
    print(f"  disimpan       : {hasil['disimpan']}")
    if not args.apply:
        print("  (belum diubah — jalankan dengan --apply untuk membersihkan)")
    else:
        print("  sudah dibersihkan")
    return 0


def _cetak_backtest(hasil: dict[str, Any]) -> None:
    bps = hasil.get("fee_per_sisi", 0) * 10000
    print(f"\n  kandidat           : {hasil['n_kandidat']}")
    print(f"  bisa dinilai        : {hasil['n_dinilai']}")
    print(f"  terisi              : {hasil['n_terisi']} ({hasil['fill_rate_pct']}% dari yang dinilai)")
    print(f"  biaya diperhitungkan: {bps:.1f} bps per sisi (dalam satuan R, bukan diabaikan)")
    for nama, kunci in (
        ("SEMUA (tanpa gate)", "semua"),
        ("MASUK DI HARGA PASAR", "masuk_pasar"),
        ("TARGET 2R (bukan 1R)", "target_2r"),
        ("LOLOS GATE", "lolos"),
        ("DITOLAK (bayangan)", "ditolak"),
    ):
        b = hasil[kunci]
        if not b["n"]:
            continue
        eks_isi = "n/a" if b["expectancy_terisi_r"] is None else f"{b['expectancy_terisi_r']:+.3f}R"
        bersih = "n/a" if b["expectancy_bersih_r"] is None else f"{b['expectancy_bersih_r']:+.3f}R"
        biaya = "n/a" if b["biaya_rata_r"] is None else f"{b['biaya_rata_r']:.3f}R"
        t = "-" if b["t_stat"] is None else f"{b['t_stat']:+.2f}"
        print(
            f"  {nama:<19}: n={b['n']:<4} TP1={b['tp1']:<4} SL={b['sl']:<4} "
            f"tak terisi={b['tak_terisi']:<4} terisi={b['terisi']}"
        )
        print(f"  {'':<19}  expectancy kotor  = {eks_isi:<9} total {b['total_r_terisi']:+.2f}R")
        print(
            f"  {'':<19}  biaya rata-rata   = {biaya:<9} "
            f"→ bersih {bersih} (total {b['total_bersih_r']:+.2f}R)  t={t} ({b['keyakinan']})"
        )
    if hasil["per_aturan"]:
        print("\n  per aturan (hanya kandidat yang ditolak SATU aturan):")
        for nama, b in hasil["per_aturan"].items():
            bersih = "n/a" if b["expectancy_bersih_r"] is None else f"{b['expectancy_bersih_r']:+.2f}R"
            t = "-" if b["t_stat"] is None else f"{b['t_stat']:+.2f}"
            print(
                f"    {nama:<15} n={b['n']:<4} terisi={b['terisi']:<3} TP1={b['tp1']:<3} "
                f"SL={b['sl']:<3} bersih={bersih:<8} t={t:<6} ({b['keyakinan']}) → {b['putusan']}"
            )
    print("\n  'berguna' = kandidat yang ditolak aturan itu memang cenderung rugi setelah biaya.")
    print("  Putusan hanya dikeluarkan kalau sudah >= 20 kandidat selesai; di bawah itu")
    print("  ditulis 'belum dapat disimpulkan' — t besar dari 3 pengamatan bukan bukti.")
    print("  'merugikan' = aturan itu membuang kandidat yang justru untung.")
    print("  'keyakinan' = |t| >= 2 DAN >= 20 trade dianggap kuat; selain itu bisa jadi derau.")


def _cetak_banding(
    b: dict[str, Any],
    klaster: dict[str, Any] | None = None,
    klaster_aturan: dict[str, dict[str, Any]] | None = None,
    nol: dict[str, Any] | None = None,
) -> None:
    print("\n  UJI BEDA (setelah biaya) — apakah kedua kelompok benar-benar berbeda?")
    utama = b["lolos_vs_ditolak"]
    beda = utama["beda_r"]
    print(
        f"    lolos vs ditolak : beda {beda:+.3f}R "
        f"(n={utama['n_lolos']} vs {utama['n_ditolak']}) · t={utama['t']} "
        f"· {utama['keterangan']}"
    )
    for nama, v in b["per_aturan"].items():
        if v["beda_r"] is None:
            continue
        print(
            f"    {nama:<16} : beda {v['beda_r']:+.3f}R (n_gagal={v['n_gagal']}) "
            f"· t={v['t']} · {v['keterangan']}"
        )
    print("    Catatan: kandidat satu pair saling berkorelasi, jadi t ini optimistis.")
    if klaster and klaster.get("beda_r") is not None:
        print(
            f"    UJI KLASTER (per pair, n={klaster['n_pair']}) : beda {klaster['beda_r']:+.3f}R "
            f"· t={klaster['t']} · {klaster['keterangan']}"
        )
        print("    Ini uji yang lebih keras — satu pair dihitung satu unit, bukan satu kandidat.")
    if klaster_aturan:
        print("    UJI KLASTER PER ATURAN (satu pair = satu unit):")
        for nama, v in sorted(klaster_aturan.items()):
            if v.get("beda_r") is None:
                continue
            print(
                f"      {nama:<15} beda {v['beda_r']:+.3f}R (n_pair={v['n_pair']}) "
                f"· t={v['t']} · {v['keterangan']}"
            )

    if nol and nol.get("rata_r") is not None:
        print(
            f"    EDGE ALIRAN KANDIDAT (per pair, n={nol['n_pair']}) : {nol['rata_r']:+.3f}R "
            f"· t={nol['t']} · {nol['keterangan']}"
        )
        print("    Pertanyaan paling dasar: kandidat sistem ini sendiri menghasilkan R atau tidak.")


def _cetak_sweep(rows: list[dict[str, Any]]) -> None:
    """Edge aliran kandidat pada beberapa tingkat biaya — pertanyaan sebenarnya.

    Bukan 'aturan mana yang berguna', tapi 'pada biaya berapa edge ini masih hidup'.
    Dengan R yang tipis, biaya menentukan hidup-mati, dan itu terlihat di sini.
    """
    from .backtest import aggregate, uji_klaster_nol

    print("\n  SENSITIVITAS BIAYA — edge aliran kandidat (uji klaster, satu pair = satu unit)")
    print(f"    {'biaya/sisi':<12} {'rata-rata':>10} {'t':>7}   putusan")
    for bps in (0.0, 1.0, 2.0, 3.0, 5.0, 7.0):
        nol = uji_klaster_nol(rows, fee_per_sisi=bps / 10000)
        if nol.get("rata_r") is None:
            continue
        print(f"    {bps:>6.1f} bps   {nol['rata_r']:>+9.4f}R {nol['t']:>+7.2f}   {nol['keterangan']}")
    kotor0 = aggregate(rows, fee_per_sisi=0.0)["semua"]["expectancy_bersih_r"]
    print(f"    (edge kotor tanpa biaya: {kotor0:+.3f}R — inilah yang dimakan biaya)")


def cmd_backtest(args: argparse.Namespace) -> int:
    """Uji aturan gate pada data historis — jawaban yang tidak perlu menunggu berminggu-minggu."""
    from .backtest import (
        aggregate,
        bandingkan,
        muat_rows,
        run,
        uji_klaster,
        uji_klaster_aturan,
        uji_klaster_nol,
    )
    from .signals.engine import top_pairs

    s = get_settings()
    fee = args.biaya_bps / 10000
    if args.dari_berkas:
        rows = muat_rows(s, args.days, args.offset, args.hold, args.penetrasi_bps or 0.0)
        if not rows:
            print(f"  tidak ada berkas backtest-{args.days}d.jsonl — jalankan tanpa --dari-berkas dulu")
            return 1
        print(f"  dihitung ulang dari berkas: {len(rows)} baris (tanpa menarik data baru)")
        _cetak_backtest(aggregate(rows, fee_per_sisi=fee))
        _cetak_banding(
            bandingkan(rows, fee_per_sisi=fee),
            uji_klaster(rows, fee_per_sisi=fee),
            uji_klaster_aturan(rows, fee_per_sisi=fee),
            uji_klaster_nol(rows, fee_per_sisi=fee),
        )
        if args.sweep_biaya:
            _cetak_sweep(rows)
        return 0

    pairs = [p.upper() for p in args.pairs] if args.pairs else top_pairs(s, args.top)
    geser = f" · digeser {args.offset} hari ke belakang" if args.offset else ""
    print(
        f"  backtest: {len(pairs)} pair · {args.days} hari{geser} · "
        f"keputusan tiap {args.step} jam · tahan {args.hold} jam"
    )
    print(
        f"  (biaya {args.biaya_bps:.1f} bps/sisi dihitung dalam satuan R · tanpa slippage/funding "
        f"· gate exposure tidak diuji · hanya candle tertutup)\n"
    )
    hasil = run(
        s,
        pairs,
        days=args.days,
        step_h=args.step,
        warmup_h=args.warmup,
        hold_h=args.hold,
        offset_days=args.offset,
        isi_penetrasi_bps=args.penetrasi_bps or 0.0,
        paksa_tag=args.penetrasi_bps is not None,
        fee_per_sisi=fee,
        lapor=print,
    )
    _cetak_backtest(hasil)
    _cetak_banding(
        bandingkan(hasil["rows"], fee_per_sisi=fee),
        uji_klaster(hasil["rows"], fee_per_sisi=fee),
        uji_klaster_aturan(hasil["rows"], fee_per_sisi=fee),
        uji_klaster_nol(hasil["rows"], fee_per_sisi=fee),
    )
    return 0


def cmd_measure(args: argparse.Namespace) -> int:
    """Apakah gate-nya berguna? Diukur dari hasil bayangan kandidat yang ditolak."""
    from . import measure

    rep = measure.report(get_settings())
    lolos, ditolak = rep["lolos"], rep["ditolak_bayangan"]
    print(f"  kandidat tercatat {rep['total_tercatat']} · sudah bisa dinilai {rep['dinilai']}")
    print()
    for label, s in (("LOLOS GATE", lolos), ("DITOLAK (bayangan)", ditolak)):
        if s["n"]:
            print(
                f"  {label:<19} n={s['n']:<3} TP1={s['tp1']:<3} SL={s['sl']:<3} "
                f"winrate {s['winrate']}%  expectancy {s['expectancy_r']:+.2f}R  total {s['total_r']:+.2f}R"
            )
        else:
            print(f"  {label:<19} belum ada yang selesai")
    mp = rep.get("masuk_pasar") or {}
    if mp.get("n"):
        print(
            f"  {'MASUK HARGA PASAR':<19} n={mp['n']:<3} TP1={mp['tp1']:<3} SL={mp['sl']:<3} "
            f"winrate {mp['winrate']}%  expectancy {mp['expectancy_r']:+.2f}R  total {mp['total_r']:+.2f}R"
        )
        print("    (pembanding: kandidat dimasuki di harga pasar, bukan menunggu POI)")
    aturan = rep["per_aturan"]
    if aturan:
        print()
        print("  per aturan (hanya kandidat yang ditolak SATU aturan):")
        for rule, s in sorted(aturan.items(), key=lambda kv: kv[1]["expectancy_r"]):
            t_txt = f"t={s['t']:+.2f}" if s.get("t") is not None else "t=n/a"
            print(
                f"    {rule:<16} n={s['n']:<3} expectancy {s['expectancy_r']:+.2f}R  "
                f"TP1={s['tp1']} SL={s['sl']}  {t_txt}  → {s['putusan']}"
            )
        print()
        print("    'berguna' = kandidat yang ditolak aturan itu memang cenderung rugi.")
        print("    'merugikan' = aturan itu membuang kandidat yang justru untung.")
        print("    Putusan butuh DUA syarat: n>=20 DAN |t|>=2. Selain itu = belum jelas.")
    pag = rep.get("per_agent") or {}
    if pag:
        print()
        print("  per agent (hipotesis — agent tidak menolak, hanya dicatat):")
        for nama, a in sorted(pag.items()):
            print(
                f"    {nama:<10} n={a['n']:<3} setuju {a['n_setuju']:<3} avg {a['avg_setuju_r']}R  "
                f"tak-setuju {a['n_tak_setuju']:<3} avg {a['avg_tak_setuju_r']}R  → {a['putusan']}"
            )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lt", description="War Room multi-market stack")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="cek semua jalur data").set_defaults(func=cmd_doctor)
    sub.add_parser("paths", help="tampilkan path efektif").set_defaults(func=cmd_paths)
    sub.add_parser("ledger", help="ringkas ledger R").set_defaults(func=cmd_ledger)
    sub.add_parser("equity", help="kurva ekuitas + statistik ledger").set_defaults(func=cmd_equity)
    col = sub.add_parser("collect", help="tarik data satu market (atau semua)")
    col.add_argument("market", choices=["crypto", "idx", "forex", "all"])
    col.set_defaults(func=cmd_collect)

    sub.add_parser("risk", help="status risk gate").set_defaults(func=cmd_risk)
    sub.add_parser("verdicts", help="ringkasan verdict gate").set_defaults(func=cmd_verdicts)
    scan = sub.add_parser("scan", help="pindai pair: hanya arah yang didukung struktur")
    scan.add_argument("pairs", nargs="*", help="daftar pair (default: 10 pair pantauan)")
    scan.add_argument(
        "--top",
        type=int,
        default=0,
        help="pakai N pair teratas menurut volume 24 jam nyata (mengabaikan daftar)",
    )
    scan.set_defaults(func=cmd_scan)
    sub.add_parser("hl", help="Hyperliquid: OI + funding (konteks)").set_defaults(func=cmd_hl)
    sub.choices["hl"].add_argument("--top", type=int, default=10)

    dep = sub.add_parser("depth", help="kedalaman buku order: notional pada tiap level bps")
    dep.add_argument("pairs", nargs="*", help="pair (kosong = daftar bawaan)")
    dep.add_argument("--max-bps", type=float, default=20.0)
    dep.set_defaults(func=cmd_depth)
    tvp = sub.add_parser("idx-tv", help="screener IDX via TradingView")
    tvp.add_argument("--min-volume", type=int, default=5_000_000)
    tvp.add_argument("--limit", type=int, default=15)
    tvp.add_argument("--sort", default="volume")
    tvp.add_argument("--uptrend", action="store_true", help="hanya EMA8 > EMA21")
    tvp.add_argument("--rsi-below", type=float)
    tvp.set_defaults(func=cmd_idxtv)
    bd = sub.add_parser("bandar", help="bandarmologi IDX via Stockbit (butuh token)")
    bd.add_argument("symbol")
    bd.add_argument("--period", choices=["latest", "7d", "3m"], default="7d")
    bd.set_defaults(func=cmd_bandar)
    sub.add_parser("measure", help="apakah gate berguna (hasil bayangan)").set_defaults(func=cmd_measure)
    dd = sub.add_parser("dedupe", help="bersihkan catatan kandidat ganda")
    dd.add_argument("--apply", action="store_true", help="tulis hasilnya (tanpa ini hanya laporan)")
    dd.set_defaults(func=cmd_dedupe)
    bt = sub.add_parser("backtest", help="uji aturan gate pada data historis")
    bt.add_argument("pairs", nargs="*", help="pair tertentu (default: teratas menurut volume)")
    bt.add_argument("--top", type=int, default=20)
    bt.add_argument("--days", type=int, default=60)
    bt.add_argument("--step", type=int, default=4, help="keputusan tiap N jam")
    bt.add_argument("--warmup", type=int, default=2880, help="candle 1H pemanasan sebelum menilai")
    bt.add_argument("--hold", type=int, default=33, help="jam pelacakan hasil (8 terisi + 24 tahan)")
    bt.add_argument("--dari-berkas", action="store_true", help="hitung ulang dari baris tersimpan")
    bt.add_argument(
        "--offset", type=int, default=0, help="geser jendela ke belakang N hari (uji di luar sampel)"
    )
    bt.add_argument(
        "--biaya-bps", type=float, default=5.0, help="biaya per sisi dalam bps (default 5 = 0,05%%)"
    )
    bt.add_argument("--sweep-biaya", action="store_true", help="edge pada beberapa tingkat biaya")
    bt.add_argument(
        "--penetrasi-bps",
        type=float,
        default=None,
        help="entry baru dianggap terisi kalau harga menembus level sejauh N bps (uji asumsi terisi)",
    )
    bt.set_defaults(func=cmd_backtest)
    ic = sub.add_parser("idx-check", help="cross-check Arjum vs TradingView")
    ic.add_argument("--limit", type=int, default=8)
    ic.set_defaults(func=cmd_idx_check)
    smc = sub.add_parser("smc", help="struktur pasar + verdict gate (deterministik)")
    smc.add_argument("pair")
    smc.add_argument("--direction", choices=["long", "short"])
    smc.add_argument("--entry", type=float)
    smc.add_argument("--sl", type=float)
    smc.add_argument("--tp1", type=float)
    smc.add_argument("--agents", action="store_true", help="hitung + catat 6-agent (hipotesis, bukan gate)")
    smc.set_defaults(func=cmd_smc)
    ag = sub.add_parser("agents", help="6-agent satu pair (hipotesis, bukan gate)")
    ag.add_argument("pair")
    ag.set_defaults(func=cmd_agents)
    sub.add_parser("snapshot", help="bangun snapshot dashboard").set_defaults(func=cmd_snapshot)
    sub.add_parser("dashboard", help="jalankan dashboard").set_defaults(func=cmd_dashboard)
    sub.choices["snapshot"].add_argument("--offline", action="store_true", help="tanpa jaringan")

    paper = sub.add_parser("paper", help="executor paper")
    paper.add_argument("aksi", choices=["list", "open", "close", "eval"])
    paper.add_argument("--venue", default="crypto", choices=["crypto", "polymarket", "gmgn", "idx", "forex"], help="venue pasar")
    paper.add_argument("--pair")
    paper.add_argument("--direction", default="LONG")
    paper.add_argument("--entry", type=float)
    paper.add_argument("--stop", type=float)
    paper.add_argument("--tp1", type=float)
    paper.add_argument("--tp2", type=float)
    paper.add_argument("--atr", type=float)
    paper.add_argument("--equity", type=float)
    paper.add_argument("--signal-id")
    paper.add_argument("--price", type=float)
    paper.add_argument("--status", default="closed_manual")
    paper.add_argument("--note", default="")
    paper.set_defaults(func=cmd_paper)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
