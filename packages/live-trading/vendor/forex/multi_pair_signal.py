#!/usr/bin/env python3
"""multi_pair_signal.py — SMC signal scanner utk 3 pair: XAUUSD, NAS100, EURUSD.

Req Dumbledore (22 Sep 2026): signal "kayak biasanya" utk 3 pair, tanpa
integrasi broker. Engine sama dgn xauusd_reactive.py (OB/FVG/iFVG/TL +
confluence_score + build_signal), MIN_CONFLUENCE diimport dr sana agar
gate selalu sinkron dgn rule yg aktif.

- XAUUSD TIDAK discan di sini (sudah dicover reactive watcher + daily 14:30).
  Pair ini disertakan sbg no-op supaya state/cron seragam — skip cepat.
- NAS100 : CAPITALCOM:NAS100 (Capital.com CFD) | sesi 21:30-03:00 WIB (NY)
- EURUSD : OANDA:EURUSD                      | sesi 14:00-21:00 WIB (London+NY overlap)

Dedup: 1 zone (tf+kind+low+high) max 1 signal per hari per pair
(state ~/.hermes/state/multi_pair_signals.json).

Output: kirim pesan Telegram ke topic 144 (HQ, label pair di header).
Tanpa chart (plot_signal.py masih XAU-specific) — level lengkap di teks.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import xauusd_reactive as rx  # reuse: tv_fetch-like via tv_feed, engine funcs

WIB = timezone(timedelta(hours=7))
STATE_PATH = os.path.expanduser("~/.hermes/state/multi_pair_signals.json")

PAIRS = {
    "XAUUSD": {"sym": "TVC:GOLD", "win": (13, 19), "send": False},   # existing pipeline covers
    "NAS100": {"sym": "CAPITALCOM:NAS100", "win": (21, 3), "send": True},  # 21:00-03:59 WIB
    "EURUSD": {"sym": "OANDA:EURUSD", "win": (14, 21), "send": True},
}

PRICE_DP = {"XAUUSD": 2, "NAS100": 1, "EURUSD": 5}


def fmt_sig(sig, pair):
    """Round level sesuai presisi pair (build_signal default 2dp — EURUSD 5dp)."""
    dp = PRICE_DP[pair]
    out = dict(sig)
    for k in ("entry", "sl", "tp1", "tp2", "be"):
        out[k] = round(sig[k], dp)
    return out


def build_signal_dp(zone, atr_val, pair, px=None, max_risk_mult=1.5):
    """Sama dgn rx.build_signal (POLICY LIMIT-ONLY, rule user 25 Sep 2026)
    tapi round sesuai presisi pair.

    Harga di atas zona BUY -> entry zone high (retest) = LIMIT.
    Harga di dalam zona    -> entry harga sekarang   = LIMIT.
    Harga di bawah zona    -> entry zone low, tapi itu di atas pasar (buy
    stop) -> order_type "WATCH": jangan dipasang stop, tunggu harga masuk zona.
    SELL mirror. SL selalu di balik sisi jauh zona + 1xATR.
    Risk > max_risk_mult x ATR -> tolak (zona kelebaran)."""
    side = zone["side"]
    dp = PRICE_DP[pair]
    r_ = lambda x: round(x, dp)
    zl, zh = zone["low"], zone["high"]
    st = rx.zone_state(zone, px) if px is not None else "in_zone"
    if st == "mitigated":
        return None  # harga tembus sisi jauh zona -> demand/supply sudah gagal
    in_zone = st == "in_zone"
    if side == "BUY":
        sl = r_(zl - atr_val)
        entry = r_(px) if in_zone else r_(zh)
        risk = entry - sl
        if risk > atr_val * max_risk_mult or risk <= 0:
            return None
        return {"side": side, "entry": entry, "sl": sl, "tp1": r_(entry + risk),
                "tp2": r_(entry + 2 * risk), "be": entry, "risk": risk,
                "atr": atr_val, "order_type": "LIMIT", "in_zone": in_zone}
    sl = r_(zh + atr_val)
    entry = r_(px) if in_zone else r_(zl)
    risk = sl - entry
    if risk > atr_val * max_risk_mult or risk <= 0:
        return None
    return {"side": side, "entry": entry, "sl": sl, "tp1": r_(entry - risk),
            "tp2": r_(entry - 2 * risk), "be": entry, "risk": risk,
            "atr": atr_val, "order_type": "LIMIT", "in_zone": in_zone}


def tv_fetch2(sym, tf, bars):
    r = rx.subprocess.run([rx.PY, rx.TV_FEED, sym, tf, str(bars)],
                          capture_output=True, text=True, timeout=60)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return json.loads(r.stdout)


def in_session(win, now):
    a, b = win
    if a <= b:
        return a <= now.hour < b
    return now.hour >= a or now.hour < b  # window crosses midnight (NAS100)


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return json.load(f)
    return {}


def save_state(st):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(st, f, indent=2)


def candidate_zones(h1):
    """Auto-POI zona di sekitar harga: OB, FVG, iFVG, trendline."""
    zones = []
    px = h1[-1]["c"]
    obs = rx.order_blocks(h1, lookback=80)
    fvgs = rx.find_fvg(h1, lookback=80)
    ifvgs = rx.find_ifvgs(h1, lookback=80)
    tls = []  # trendline zones skip: band harga→garis terlalu lebar utk risk cap 1.5xATR
    for b in obs:
        kind = b.get("kind", "")
        side = "BUY" if kind.startswith("bullish") else "SELL"
        zones.append({"tf": "1H", "kind": kind, "low": b["lo"], "high": b["hi"],
                      "side": side, "trigger": "OB retest", "note": "auto-scan"})
    for f in fvgs:
        kind = f.get("kind", "")
        side = "BUY" if kind.startswith("bullish") else "SELL"
        zones.append({"tf": "1H", "kind": kind + " FVG", "low": f["lo"], "high": f["hi"],
                      "side": side, "trigger": "FVG retest", "note": "auto-scan"})
    for b in ifvgs:
        side = "BUY" if b["kind"].startswith("bullish") else "SELL"
        zones.append({"tf": "1H", "kind": b["kind"], "low": b["lo"], "high": b["hi"],
                      "side": side, "trigger": "iFVG retest", "note": "auto-scan"})
    for t in tls:
        side = "BUY" if t["kind"] == "trendline support" else "SELL"
        zones.append({"tf": "1H", "kind": t["kind"], "low": min(t["lo"], px), "high": max(t["hi"], px),
                      "side": side, "trigger": "trendline retest",
                      "note": f"{t['touches']} touches", "touches": t["touches"]})
    # hanya zona yang relevan: price di dalam / dekat zona (<= 1.5 ATR via filter width di build_signal)
    near = []
    for z in zones:
        if z["low"] <= px <= z["high"]:
            near.append(z)
        elif rx.zone_state(z, px) == "mitigated":
            # harga tembus sisi jauh -> catat sebagai zona gagal; kalau nanti
            # harga balik masuk, itu retest (dibalik arahnya), bukan POI searah.
            rx.mark_zone_broken(z, px)
    return [rx.flip_zone(z) for z in near]


def send_text(pair, sig, zone, score, h1_close, atr_val):
    tok = ""
    for line in open(os.path.expanduser("~/.hermes/.env")):
        line = line.strip()
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            tok = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
    if not tok:
        print("no TELEGRAM_BOT_TOKEN", file=sys.stderr)
        return False
    dp = PRICE_DP[pair]
    risk_txt = f"{sig['risk']:.{dp}f}"
    msg = (
        f"⚡ MULTI-PAIR SIGNAL — {pair} | {datetime.now(WIB):%d %b %H:%M} WIB\n"
        f"🕐 1H close: {h1_close:.{dp}f} | confluence {score}/6 (gate {rx.MIN_CONFLUENCE})\n\n"
        f"Setup: harga di {zone['kind']} {zone['tf']} "
        f"{zone['low']:.{dp}f}-{zone['high']:.{dp}f}\n"
        f"Trigger: {zone.get('trigger', '')}\n\n"
        f"**{sig['side']} {sig.get('order_type', 'LIMIT')}**\n"
        f"Entry : {sig['entry']}\n"
        f"SL    : {sig['sl']} (-{risk_txt}, 1xATR buffer)\n"
        f"TP1   : {sig['tp1']} (+1R)  → partial 50%, BE arm\n"
        f"TP2   : {sig['tp2']} (+2R)\n\n"
        f"Risk: 0.5% modal | konfirmasi manual wajib | TTL 24j tanpa fill = cancel"
    )
    if sig.get("order_type") == "WATCH":
        msg += (
            "\n\n⚠️ **WATCH — JANGAN pakai buy/sell stop.**\n"
            "Harga sekarang di LUAR zona. Stop-entry keisi di ujung breakout; "
            "kalau breakout palsu, harga round-trip langsung ke SL.\n"
            f"Tunggu harga MASUK zona, baru pasang limit di {sig['entry']} "
            "setelah ada konfirmasi close."
        )
    elif sig.get("in_zone"):
        msg += (
            "\n\nℹ️ Harga **sudah di dalam zona** — order ini terisi begitu "
            "dipasang (entry sekarang), bukan nunggu harga datang."
        )
    import urllib.request
    data = json.dumps({"chat_id": "-1004383844873", "message_thread_id": "144",
                       "text": msg, "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage",
                                 data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("ok", False)


def scan_pair(pair, cfg, now, dry=False):
    if not cfg["send"]:
        return f"{pair}: skip (dicover pipeline XAU existing)"
    if not in_session(cfg["win"], now):
        return f"{pair}: di luar sesi {cfg['win']}"
    h1 = tv_fetch2(cfg["sym"], "60", 120)
    m15 = tv_fetch2(cfg["sym"], "15", 60)
    if not h1 or not m15:
        return f"{pair}: FEED FAILED"
    atr_val = rx.atr(h1)
    px = h1[-1]["c"]
    zones = candidate_zones(h1)
    if not zones:
        return f"{pair}: {px:.2f} — tidak ada zona auto-POI aktif"
    st = load_state()
    today = now.strftime("%Y-%m-%d")
    # Kumpulkan semua kandidat yang lolos gate DULU, lalu kirim HANYA yang
    # terbaik. Rule user (23 Sep): kalau ada 2 signal berlawanan arah di pair
    # yang sama, kirim yang probability-nya tertinggi saja — bukan dua-duanya
    # (straddle = bukan setup). Satu pair = maksimal SATU signal per run.
    cands = []
    for z in zones[:8]:
        score, reasons = rx.confluence_score(z, h1, m15, atr_val)
        if score < rx.MIN_CONFLUENCE:
            continue
        sig = build_signal_dp(z, atr_val, pair, px=px)
        if sig is None:
            continue
        cands.append((score, z, sig))
    if not cands:
        save_state(st)
        return f"{pair}: {px:.2f} — {len(zones)} zona, 0 lolos gate {rx.MIN_CONFLUENCE}/6"
    # ranking: skor tertinggi dulu; tie-break = entry paling dekat harga
    # (fill paling cepat, risk drift paling kecil)
    cands.sort(key=lambda c: (-c[0], abs(c[2]["entry"] - px)))
    score, z, sig = cands[0]
    skipped = [f"{c[2]['side']}@{c[2]['entry']}({c[0]}/6)" for c in cands[1:]]
    sent = []
    dp = PRICE_DP[pair]
    key = f"{today}|{pair}|{z['tf']}|{z['kind']}|{z['low']:.4f}|{z['high']:.4f}"
    prev = st.get(key, "")
    is_watch = sig.get("order_type") == "WATCH"
    # Dedupe: signal executable sudah dikirim hari ini -> jangan ulang.
    # WATCH yang sudah dikirim -> jangan ulang juga, TAPI kalau harga akhirnya
    # datang ke zona (signal jadi executable/LIMIT), kirim yang baru — kalau
    # tidak, WATCH pagi memblokir entry yang seharusnya bisa dieksekusi siang.
    if prev and not (prev.startswith("WATCH") and not is_watch):
        save_state(st)
        return f"{pair}: {px:.2f} — kandidat sudah pernah dikirim hari ini ({prev[:5]})"
    line = (f"{pair} {z['side']} @ {sig['entry']:.{dp}f} (SL {sig['sl']:.{dp}f}, "
            f"TP1 {sig['tp1']:.{dp}f}, TP2 {sig['tp2']:.{dp}f}) "
            f"confluence {score}/6 [{z['kind']}]"
            + (" [WATCH]" if is_watch else ""))
    if dry:
        sent.append("[DRY] " + line)
    elif send_text(pair, sig, z, score, px, atr_val):
        st[key] = ("WATCH " if is_watch else "") + now.isoformat(timespec="seconds")
        sent.append(line)
        try:
            import multipair_journal as mj
            mj.journal_signal(pair, sig, z, score)
        except Exception as e:
            print(f"JOURNAL FAILED: {e}", file=sys.stderr)
    else:
        sent.append(line + " — SEND FAILED")
    if skipped:
        print(f"{pair}: {len(skipped)} kandidat lain dilewati "
              f"(1-setup-per-pair rule): {', '.join(skipped)}", file=sys.stderr)
    save_state(st)
    return f"{pair}: {px:.2f} — " + ("; ".join(sent) if sent else
                                     "kandidat terbaik sudah pernah dikirim hari ini")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    now = datetime.now(WIB)
    out = [scan_pair(p, c, now, args.dry_run) for p, c in PAIRS.items()]
    print(f"=== multi_pair_signal {now:%Y-%m-%d %H:%M} WIB ===")
    for line in out:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
