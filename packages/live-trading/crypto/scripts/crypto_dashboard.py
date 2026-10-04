#!/usr/bin/env python3
"""Crypto trading dashboard — pipeline status, watchlist, MEXC live, Agent 6.

Stdlib only (http.server + json + sqlite-free). Port 8771.
Data sources:
  ~/.hermes/cron/jobs.json              -> status job pipeline (5309ec6950c8)
  ~/.hermes/cron/output/<job>/          -> file output terakhir (umur laporan)
  ~/.hermes/crypto-watchlist.json       -> signal + status + P/L
  ~/.hermes/mexc_futures.json + mexc_client -> balance & posisi live MEXC
  ~/.hermes/state/onchain_enrich.jsonl  -> Agent 6 (makro DefiLlama + positioning)

Dijalankan sebagai systemd user service (crypto-dashboard.service) supaya tahan restart gateway.
"""
import json
import os
import re
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Daftar koin yang di-scan diambil LANGSUNG dari sumbernya supaya angka di
# dashboard tidak pernah beda dari yang beneran dipakai pipeline.
try:
    from crypto_signal_collect import WATCHLIST as SCAN_UNIVERSE
except Exception:
    SCAN_UNIVERSE = []

HERE = os.path.expanduser("~/.hermes")
CRON_JOBS = os.path.join(HERE, "cron", "jobs.json")
CRON_OUT = os.path.join(HERE, "cron", "output", "5309ec6950c8")
WATCHLIST = os.path.join(HERE, "crypto-watchlist.json")
A6_LOG = os.path.join(HERE, "state", "onchain_enrich.jsonl")
JOB_ID = "5309ec6950c8"
PORT = 8771
WIB = timezone(timedelta(hours=7))

_cache = {"mexc": (0.0, None), "mexc_lock": threading.Lock()}


# ------------------------------------------------------------------ helpers
def _load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _latest_output_age():
    try:
        files = [os.path.join(CRON_OUT, f) for f in os.listdir(CRON_OUT)]
        if not files:
            return None, None
        newest = max(files, key=os.path.getmtime)
        ts = datetime.fromtimestamp(os.path.getmtime(newest), WIB)
        age_min = (datetime.now(WIB) - ts).total_seconds() / 60
        return ts.strftime("%d %b %H:%M WIB"), round(age_min)
    except Exception:
        return None, None


def pipeline_status():
    jobs = _load_json(CRON_JOBS, {})
    arr = jobs if isinstance(jobs, list) else jobs.get("jobs", [])
    job = next((j for j in arr if j.get("id") == JOB_ID), {}) or {}
    out_ts, out_age = _latest_output_age()
    return {
        "name": job.get("name"),
        "enabled": job.get("enabled", True),
        "schedule": job.get("schedule"),
        "model": job.get("model"),
        "provider": job.get("provider"),
        "last_status": job.get("last_status"),
        "last_run_at": job.get("last_run_at"),
        "next_run_at": job.get("next_run_at"),
        "failure_streak": job.get("failure_streak", 0),
        "last_output": out_ts,
        "last_output_age_min": out_age,
        "universe": len(SCAN_UNIVERSE),
        "universe_pairs": SCAN_UNIVERSE,
    }


def mexc_state():
    """Balance + posisi live MEXC, cache 60 detik biar tidak spam API."""
    with _cache["mexc_lock"]:
        ts, val = _cache["mexc"]
        if val is not None and time.time() - ts < 60:
            return val
        data = {"ok": False, "balance": None, "positions": [], "error": None}
        try:
            import mexc_client as mx
            data["balance"] = mx.balance_usdt()
            pos = mx.positions() or []
            clean = []
            for p in pos:
                clean.append({
                    "symbol": p.get("symbol"),
                    "side": "LONG" if str(p.get("positionType")) == "1" else "SHORT",
                    "vol": p.get("holdVol"),
                    "open_price": p.get("holdAvgPrice") or p.get("openAvgPrice"),
                    "leverage": p.get("leverage"),
                    "pnl": p.get("realised") or p.get("imRate"),
                    "im": p.get("im"),
                })
            data["positions"] = clean
            data["ok"] = True
        except Exception as exc:
            data["error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
        _cache["mexc"] = (time.time(), data)
        return data


def _latest_output_file():
    try:
        files = [os.path.join(CRON_OUT, f) for f in os.listdir(CRON_OUT)]
        return max(files, key=os.path.getmtime) if files else None
    except Exception:
        return None


# ------------------------------------------------- status A1-A6 (dari digest)
# (kode, nama, fungsi 1 baris) — diambil dari prompt pipeline, bukan karangan.
AGENT_FUNCS = [
    ("A1", "Market Scan", "Order flow (buy pressure, volume Δ6h, funding) + struktur SMC "
                          "1D/4H/1H → tentukan kandidat"),
    ("A2", "Setup Creator", "Bangun setup SMC dari kandidat (POI 1H + MTF) → yang bikin signal"),
    ("A3", "News & Sentiment", "Fear & Greed, dominasi BTC, kalender event → filter event 60 menit"),
    ("A4", "Whale & Positioning", "Taker B/S, OI, funding, whale print >$100k → buang kandidat "
                                  "yang kontradiksi"),
    ("A5", "Risk Gate", "SL ≤5%, ATR ≥1%, korelasi BTC, maks 2 posisi → gerbang terakhir"),
    ("A6", "Confluence", "Makro DefiLlama (stablecoin/DEX/TVL) + positioning Binance → bobot "
                         "keyakinan, BUKAN gate"),
]
_CLS_RE = re.compile(r"^ {2}([A-Z0-9]+USDT)\s+\| bp\s+([+-]?[\d.]+)%\s+\| volΔ6h\s+([+-]?[\d.]+)%"
                     r"\s+\| fund\s+([+-]?[\d.]+)%\s+\| L=\s*([\d.]+)%\s+\|\s*(\S+)\s+(.+)$", re.M)


def _digest_text():
    f = _latest_output_file()
    if not f:
        return None, ""
    try:
        with open(f, encoding="utf-8", errors="replace") as fh:
            return f, fh.read()
    except Exception:
        return None, ""


def _section(text, start, stops):
    """Ambil potongan teks digest dari header `start` sampai salah satu `stops`."""
    i = text.find(start)
    if i < 0:
        return ""
    i += len(start)
    j = len(text)
    for s in stops:
        k = text.find(s, i)
        if 0 <= k < j:
            j = k
    return text[i:j]


def agent_status():
    """Kondisi tiap agent A1-A6 dari digest run terakhir — diparse, bukan dikarang."""
    f, text = _digest_text()
    out = {"run": None, "response": None, "agents": []}
    if not text:
        for code, name, func in AGENT_FUNCS:
            out["agents"].append({"code": code, "name": name, "func": func,
                                  "status": "n/a", "state": "neutral"})
        return out

    ts = ""
    m = re.search(r"^Collected:\s*(.+)$", text, re.M)
    if m:
        ts = m.group(1).strip()
    out["run"] = ts
    out["file_age_min"] = None
    try:
        out["file_age_min"] = round((time.time() - os.path.getmtime(f)) / 60)
    except Exception:
        pass

    flow = _section(text, "=== AGENT 1 — MARKET SCAN: ORDER FLOW ===",
                    ["=== AGENT 1 — MARKET SCAN: SMC", "=== AGENT 4"])
    pairs = _CLS_RE.findall(flow)
    tally = {}
    for row in pairs:
        tally[row[6].strip()] = tally.get(row[6].strip(), 0) + 1
    n_neutral = sum(v for k, v in tally.items() if "neutral" in k.lower())
    n_cand = len(pairs) - n_neutral
    lowvol = sum(1 for r in pairs if r[2] and float(r[2]) < -70)

    resp = _section(text, "## Response", ["\n=== "]).strip()
    silent = resp.startswith("[SILENT]")
    n_sig = len(set(re.findall(r"#SIG[0-9A-F]{6,}", resp)))

    a4 = _section(text, "=== AGENT 4 — WHALES & POSITIONING", ["=== AGENT 3"])
    a4_none = "tidak ada pair Mild/Aggressive" in a4
    a4_pairs = len(set(re.findall(r"^ {2}([A-Z0-9]+USDT)\s+\| taker", a4, re.M)))

    a3 = _section(text, "=== AGENT 3 — SENTIMENT DATA ===", ["=== AGENT 5"])
    fg = re.search(r"Fear & Greed:\s*(\d+)/100\s*—\s*([A-Za-z ]+?)(?:\s*\(|\n|$)", a3)
    dom = re.search(r"BTC dominance:\s*([\d.]+)%", a3)

    a5 = _section(text, "=== AGENT 5 — RISK & EXPOSURE ===", ["=== AGENT 6"])
    npos = re.search(r"Posisi open user:\s*(\d+)", a5)

    a6 = _section(text, "=== AGENT 6", ["## Response", "\n[IMPORTANT"])
    score6 = re.search(r"SKOR MAKRO:\s*([+-]?\d)/3\s*\(([^)]+)\)", a6)

    def add(code, status, state):
        nm, fn = next((n, g) for c, n, g in AGENT_FUNCS if c == code)
        out["agents"].append({"code": code, "name": nm, "func": fn,
                              "status": status, "state": state})

    cls_txt = ", ".join(f"{v} {k}" for k, v in sorted(tally.items())) or "n/a"
    # Guard: kalau section A1 ada isinya tapi regex tidak nangkap satu baris pun,
    # itu tanda format digest berubah. Jangan lapor "0 pair di-scan" — angka itu
    # salah tapi kelihatan benar.
    if pairs:
        a1_status = (f"{len(pairs)} pair di-scan → {n_cand} kandidat ({cls_txt})"
                     + (f" · {lowvol} pair volume tipis (<-70%)" if lowvol else ""))
        a1_state = "ok" if n_cand else "idle"
    else:
        a1_status = ("GAGAL PARSE digest A1 — format berubah? (bukan 0 pair)"
                     if flow.strip() else "digest A1 kosong")
        a1_state = "warn"
    add("A1", a1_status, a1_state)
    add("A2", (f"{n_sig} setup di-posting" if n_sig else
               "tidak ada setup (0 kandidat)" if silent else "run selesai tanpa signal"),
        "ok" if n_sig else "idle")
    add("A3", (f"F&G {fg.group(1)}/100 ({fg.group(2).strip()})" if fg else "sentiment n/a")
              + (f" · dominasi BTC {dom.group(1)}%" if dom else ""),
        "warn" if fg and int(fg.group(1)) >= 75 else "ok")
    add("A4", (f"whale scan skip — {a4_pairs} pair (BTC-only, tanpa kandidat)" if a4_none
               else f"whale scan {a4_pairs} pair (kandidat + BTC)"),
        "idle" if a4_none else "ok")
    add("A5", f"{npos.group(1) if npos else '?'} posisi open · "
              + ("tidak ada setup masuk gate" if not n_cand else f"{n_cand} kandidat masuk gate"),
        "ok")
    add("A6", (f"skor makro {score6.group(1)}/3 ({score6.group(2)})" if score6
               else "snapshot n/a") + " · confluence only",
        "ok" if score6 else "neutral")
    return out


def watchlist():
    wl = _load_json(WATCHLIST, {}) or {}
    items = list(wl.get("items") or [])
    items.sort(key=lambda x: x.get("date_added") or "", reverse=True)
    meta = wl.get("meta", {}) or {}
    # Catatan evaluasi mentah dari pipeline = satu paragraf panjang; pecah jadi
    # bullet terkelompok supaya bisa dibaca sekilas di dashboard.
    meta["eval_note_bullets"] = eval_bullets(meta.get("last_eval_note"))
    return {"meta": meta, "items": items}


# ------------------------------------------- catatan evaluasi -> bullet
# Urutan tampil grup (bukan urutan pencocokan). Grup terakhir = default.
_EVAL_DISPLAY = ["Ringkasan", "Kandidat & setup", "Penyebab / konteks",
                 "Posisi & trigger", "Verifikasi MEXC", "Event & risiko", "Aksi"]
_EVAL_MATCH = [
    ("Aksi", ("no action", "silent", "hold,", "crypto-auto-eval")),
    ("Verifikasi MEXC", ("positionid", "holdvol", "stoporder", "verified live", "liq ")),
    ("Posisi & trigger", ("still_open", "#sig", "tersentuh", "fill ", "px now",
                          "trigger", "tp1", "sl ")),
    ("Penyebab / konteks", ("penyebab", "vold", "low_vol")),
    ("Kandidat & setup", ("kandidat", "a1:", "neutral", "setup")),
    ("Event & risiko", ("event", "likuiditas", "weekend")),
    ("Ringkasan", ()),  # default
]


def eval_bullets(note):
    """Ubah catatan evaluasi jadi [{'label':.., 'items':[..]}] terkelompok.

    Menerima dua bentuk: (1) sudah multi-baris bertanda '-' (format baru dari
    prompt pipeline) -> dipakai apa adanya sebagai satu grup; (2) satu paragraf
    panjang (format lama) -> dipecah per kalimat lalu dikelompokkan per topik.
    """
    if not note or not str(note).strip():
        return []
    lines = [l.strip() for l in str(note).splitlines() if l.strip()]
    marked = [l for l in lines if l.lstrip().startswith(("-", "•", "*"))]
    if len(marked) >= 2:
        return [{"label": None, "items": [l.lstrip("-•* ").strip() for l in marked]}]

    text = " ".join(lines)
    # Pecah per kalimat. Titik desimal aman karena char sebelum spasi adalah
    # digit, bukan titik; yang dipecah hanya ". " yang diikuti huruf kapital.
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z(\[])", text) if s.strip()]

    buckets = {}
    for s in sentences:
        low = s.lower()
        label = "Ringkasan"
        for name, kws in _EVAL_MATCH:
            if any(k in low for k in kws):
                label = name
                break
        buckets.setdefault(label, []).append(s)
    return [{"label": g, "items": buckets[g]} for g in _EVAL_DISPLAY if g in buckets]


# ---------------------------------------------- positioning on-demand (Blok 2)
POS_CACHE = {"ts": 0.0, "data": {}, "lock": threading.Lock()}
POS_TTL = 300  # detik


def _binance_sym(symbol):
    """MEXC 'LINK_USDT' / watchlist pair -> Binance 'LINKUSDT'."""
    if not symbol:
        return None
    s = str(symbol).upper().replace("_", "").strip()
    return s if s.endswith("USDT") else None


def live_positioning(symbols):
    """Ambil positioning Binance untuk koin yang TIDAK ada di snapshot A6.

    Alasan: snapshot A6 mengikuti daftar kandidat, dan saat tidak ada kandidat
    pipeline jatuh ke fallback BTC/ETH/SOL — jadi koin yang justru sedang
    ditradingkan (posisi open / signal aktif) bisa hilang dari tabel. Baris
    seperti itu diambil live di sini, cache 5 menit biar API tidak dispam.
    """
    if not symbols:
        return {}
    now = time.time()
    with POS_CACHE["lock"]:
        fresh = (now - POS_CACHE["ts"]) < POS_TTL
        have = POS_CACHE["data"] if fresh else {}
        want = [s for s in symbols if s not in have]
        out = dict(have)
        if want:
            try:
                from onchain_enrich import positioning, crowding
                for sym, row in (positioning(want) or {}).items():
                    row["crowd"] = crowding(row)
                    out[sym] = row
            except Exception:
                pass
            POS_CACHE["data"] = out
            POS_CACHE["ts"] = now
        return {s: out[s] for s in symbols if s in out}


def _must_show():
    """Koin yang wajib tampil di Blok 2 + alasannya (prioritas tertinggi)."""
    need = {}
    try:
        for p in (mexc_state().get("positions") or []):
            s = _binance_sym(p.get("symbol"))
            if s:
                need[s] = "posisi open"
    except Exception:
        pass
    try:
        for it in (watchlist().get("items") or []):
            if (it.get("status") or "") in ("still_open", "tp1_hit_runner"):
                s = _binance_sym(it.get("pair"))
                if s:
                    need.setdefault(s, "signal aktif")
    except Exception:
        pass
    return need


R_BY_STATUS = {"closed_TP2": 1.5, "closed_TP1": 0.5, "closed_timeout": 0.0,
               "expired": 0.0, "closed_SL": -1.0}
_R_RE = re.compile(r"([+-]\d+(?:\.\d+)?)\s*R\b")


def _r_from_notes(notes):
    """Ambil angka R yang ditulis di notes (mis. 'Net ~+1R', 'Blended ~+1.5R')."""
    if not notes:
        return None
    m = _R_RE.search(notes)
    return float(m.group(1)) if m else None


def stats():
    items = watchlist()["items"]
    by, rows = {}, []
    est_r = 0.0
    counted = 0
    for it in items:
        st = it.get("status") or "?"
        by[st] = by.get(st, 0) + 1
        if st in ("still_open", "tp1_hit_runner"):
            continue
        r = _r_from_notes(it.get("notes"))
        if r is None:
            r = R_BY_STATUS.get(st, 0.0)
        est_r += r
        counted += 1
        rows.append({"signal_id": it.get("signal_id"), "pair": it.get("pair"),
                     "status": st, "r": round(r, 2)})
    closed = sum(v for k, v in by.items() if k.startswith("closed") or k == "expired")
    wins = sum(1 for r in rows if r["r"] > 0)
    return {
        "by_status": by,
        "closed": closed,
        "wins": wins,
        "winrate_pct": round(100 * wins / closed, 1) if closed else None,
        "est_r": round(est_r, 2),
        "counted": counted,
        "open": by.get("still_open", 0) + by.get("tp1_hit_runner", 0),
        "rows": rows,
    }


def agent6(limit=40):
    rows = []
    try:
        with open(A6_LOG, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return {"latest": None, "history": []}

    # Label crowding dihitung di sini pakai fungsi yang SAMA dengan pipeline
    # (onchain_enrich.crowding) supaya angka di dashboard tidak pernah beda
    # dari yang dipakai Agent 6 waktu bikin keputusan.
    latest = rows[-1] if rows else None
    if latest:
        pos = latest.get("positioning") or {}
        try:
            from onchain_enrich import crowding
            for row in pos.values():
                row["crowd"] = crowding(row)
                row.setdefault("tag", "kandidat")
        except Exception:
            pass

        # Koin yang wajib tampil: posisi open + signal aktif. Snapshot A6 hanya
        # berisi kandidat (atau fallback BTC/ETH/SOL saat tidak ada kandidat),
        # jadi tanpa langkah ini koin yang sedang ditradingkan bisa hilang dari
        # tabel padahal posisinya terbuka.
        need = _must_show()
        missing = [s for s in need if s not in pos]
        if missing:
            for s, row in live_positioning(missing).items():
                row["tag"] = need.get(s, "live")
                row["live"] = True
                pos[s] = row
        _order = {"posisi open": 0, "signal aktif": 1, "kandidat": 2}
        latest["positioning"] = dict(
            sorted(pos.items(), key=lambda kv: _order.get(kv[1].get("tag"), 3)))
        latest["must_show"] = need
    return {"latest": latest, "history": rows[-limit:]}


def summary():
    try:
        import crypto_equity
        eq = crypto_equity.curve()
    except Exception as exc:
        eq = {"points": [], "trades": [], "stats": {"error": str(exc)}}
    return {
        "now": datetime.now(WIB).strftime("%d %b %Y %H:%M:%S WIB"),
        "pipeline": pipeline_status(),
        "mexc": mexc_state(),
        "watchlist": watchlist(),
        "stats": stats(),
        "agent6": agent6(),
        "agents": agent_status(),
        "equity": eq,
    }


# ------------------------------------------------------------------- HTML
PAGE = """<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>₿ Crypto Trading Desk — Pipeline · MEXC · Agent 6</title>
<style>
:root{--bg:#080d13;--card:#111a24;--card2:#0e161f;--border:#1e2c3a;--accent:#38bdf8;
--green:#22c55e;--red:#ef4444;--yellow:#eab308;--text:#e6f0f7;--muted:#7c93a6;--purple:#a78bfa;}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);line-height:1.55}
header{background:linear-gradient(135deg,#0b1c2c 0%,#080d13 100%);border-bottom:1px solid var(--border);padding:16px 0;position:sticky;top:0;z-index:50}
.container{max-width:1240px;margin:0 auto;padding:0 16px}
h1{font-size:20px;display:flex;align-items:center;gap:8px}
.sub{color:var(--muted);font-size:12px;margin-top:2px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:16px 0}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px}
.kpi-label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.5px}
.kpi-value{font-size:22px;font-weight:700;margin-top:4px}
.kpi-note{color:var(--muted);font-size:11px;margin-top:2px}
section{margin:22px 0}
h2{font-size:14px;text-transform:uppercase;letter-spacing:.6px;color:var(--accent);margin-bottom:10px;display:flex;align-items:center;gap:8px}
table{width:100%;border-collapse:collapse;font-size:13px;background:var(--card);border-radius:10px;overflow:hidden}
th{background:var(--card2);color:var(--muted);text-align:left;padding:9px 10px;font-size:11px;text-transform:uppercase;letter-spacing:.4px;font-weight:600}
td{padding:9px 10px;border-top:1px solid var(--border);vertical-align:top}
tr:hover td{background:#0f1a24}
.badge{display:inline-block;padding:2px 8px;border-radius:99px;font-size:11px;font-weight:600}
.sub-h{font-size:11px;letter-spacing:1.6px;text-transform:uppercase;color:var(--muted);font-weight:700;margin:0 0 8px}
.sub-h.mt{margin-top:16px}
.ev-g{margin:0 0 13px}
.ev-g:last-child{margin-bottom:0}
.ev-l{font-size:10.5px;letter-spacing:1.4px;text-transform:uppercase;color:var(--accent);font-weight:700;margin-bottom:5px}
.ev-ul{margin:0;padding-left:17px}
.ev-ul li{margin:4px 0;line-height:1.55;font-size:12.5px;color:#cbd8e4}
.ev-ul li::marker{color:var(--accent)}
.panel{border:1px solid var(--border);border-radius:10px;background:var(--card);overflow:hidden}
.ag{display:flex;gap:10px;align-items:flex-start;padding:10px 13px;border-top:1px solid var(--border)}
.ag:first-child{border-top:0}
.ag-code{font-weight:700;font-size:11px;background:rgba(56,189,248,.13);color:var(--accent);border-radius:6px;padding:3px 8px;flex:0 0 auto}
.ag-name{font-weight:600;font-size:12.5px;margin-bottom:2px}
.ag-func{color:var(--muted);font-size:11px;line-height:1.5}
.ag-status{font-size:12px;color:#cbd8e4;margin-top:5px;line-height:1.5}
.ok{background:rgba(34,197,94,.15);color:var(--green)}
.bad{background:rgba(239,68,68,.15);color:var(--red)}
.warn{background:rgba(234,179,8,.15);color:var(--yellow)}
.neutral{background:rgba(124,147,166,.15);color:var(--muted)}
.info{background:rgba(56,189,248,.15);color:var(--accent)}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
.muted{color:var(--muted)}
.bar{height:8px;background:#16222e;border-radius:99px;overflow:hidden;margin-top:6px}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,#38bdf8,#a78bfa)}
.flex{display:flex;gap:12px;flex-wrap:wrap}
pre{background:var(--card2);border:1px solid var(--border);border-radius:8px;padding:10px;font-size:11px;white-space:pre-wrap;color:var(--muted);max-height:220px;overflow:auto}
.scroll-box{max-height:430px;overflow-y:auto;border:1px solid var(--border);border-radius:10px;background:var(--card);overscroll-behavior:contain}
.scroll-box table{border-radius:0}
.scroll-box thead th{position:sticky;top:0;z-index:3;background:var(--card2);box-shadow:inset 0 -1px 0 var(--border)}
.scroll-box::-webkit-scrollbar{width:10px}
.scroll-box::-webkit-scrollbar-track{background:#0b131b;border-radius:99px}
.scroll-box::-webkit-scrollbar-thumb{background:#26384a;border-radius:99px}
.scroll-box::-webkit-scrollbar-thumb:hover{background:#33506b}
.scroll-box{scrollbar-width:thin;scrollbar-color:#26384a #0b131b}
.sec-head{display:flex;align-items:baseline;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:10px}
.sec-head h2{margin-bottom:0}
.sec-head .count{color:var(--muted);font-size:11px;text-transform:none;letter-spacing:0}
footer{color:var(--muted);font-size:11px;text-align:center;padding:24px 0}
</style>
</head>
<body>
<header>
  <div class="container">
    <h1>₿ Crypto Trading Desk <span class="badge neutral" id="hdr-status">loading…</span></h1>
    <div class="sub">Pipeline 5-agent + Agent 6 confluence · eksekusi MEXC Futures · <span id="hdr-time">—</span></div>
  </div>
</header>
<div class="container">
  <div class="grid" id="kpis"></div>

  <section>
    <h2>📈 Equity Curve <span class="muted" style="text-transform:none;letter-spacing:0;font-size:11px" id="eq-sub"></span></h2>
    <div class="card" style="padding:14px">
      <div id="eq-kpis" class="flex" style="gap:18px;margin-bottom:10px;font-size:12px"></div>
      <div id="eq-chart"></div>
    </div>
  </section>

  <section id="agents-sec">
    <div class="sec-head">
      <h2>🎛️ Status Agent (A1–A6)</h2>
      <span class="count" id="agents-run"></span>
    </div>
    <div id="agents"></div>
  </section>

  <section>
    <div class="sec-head">
      <h2>🎯 Signal &amp; Watchlist</h2>
      <span class="count" id="wl-count"></span>
    </div>
    <div id="watchlist"></div>
  </section>

  <section>
    <h2>💼 MEXC Live</h2>
    <div id="mexc"></div>
  </section>

  <section>
    <h2>🌐 Agent 6 — Confluence (makro &amp; positioning)</h2>
    <div id="a6"></div>
  </section>

  <section>
    <div class="sec-head">
      <h2>📋 Catatan Evaluasi Terakhir</h2>
      <span class="count" id="eval-ts"></span>
    </div>
    <div id="evalnote" class="scroll-box" style="max-height:340px;padding:14px 16px">—</div>
  </section>
</div>
<footer>Auto-refresh 60 detik · crypto-only dashboard · bukan nasihat keuangan</footer>
<script>
const fmt = n => (n===null||n===undefined) ? '—' : n;
const esc = s => String(s==null?'':s).replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const pct = n => (n===null||n===undefined) ? '—' : n + '%';
const usd = n => (n===null||n===undefined) ? '—' : '$' + Number(n).toFixed(2);

function statusBadge(s){
  if(!s) return '<span class="badge neutral">unknown</span>';
  const k = String(s).toLowerCase();
  if(k.includes('ok')||k.includes('completed')||k.includes('tp2')||k.includes('tp1')) return `<span class="badge ok">${s}</span>`;
  if(k.includes('error')||k.includes('fail')||k.includes('sl')) return `<span class="badge bad">${s}</span>`;
  if(k.includes('expired')||k.includes('running')||k.includes('timeout')) return `<span class="badge warn">${s}</span>`;
  return `<span class="badge neutral">${s}</span>`;
}

function renderEquity(eq){
  const st = eq.stats || {};
  const pts = eq.points || [];
  document.getElementById('eq-sub').textContent = eq.since ? ('sejak ' + String(eq.since).slice(0,10)) : '';
  const g = v => v>0 ? 'var(--green)' : (v<0 ? 'var(--red)' : 'var(--muted)');
  document.getElementById('eq-kpis').innerHTML = `
    <span><span class="muted">Total</span> <b style="color:${g(st.total_r)}">${st.total_r>0?'+':''}${fmt(st.total_r)}R</b></span>
    <span><span class="muted">Trade</span> <b>${fmt(st.trades)}</b></span>
    <span><span class="muted">Winrate</span> <b>${st.winrate_pct===null||st.winrate_pct===undefined?'—':st.winrate_pct+'%'}</b></span>
    <span><span class="muted">Expectancy</span> <b style="color:${g(st.expectancy_r)}">${st.expectancy_r===null||st.expectancy_r===undefined?'—':(st.expectancy_r>0?'+':'')+st.expectancy_r+'R'}</b></span>
    <span><span class="muted">Max DD</span> <b style="color:var(--red)">${fmt(st.max_drawdown_r)}R</b></span>
    <span><span class="muted">Profit factor</span> <b>${fmt(st.profit_factor)}</b></span>`;

  const box = document.getElementById('eq-chart');
  if(!pts.length || pts.length < 2){
    box.innerHTML = '<div class="muted" style="font-size:12px">Belum ada trade tertutup untuk digambar.</div>';
    return;
  }
  const W = 900, H = 220, PAD = 34;
  const xs = pts.map(p=>p.i);
  const ys = pts.map(p=>p.cum);
  const xmin = Math.min(...xs), xmax = Math.max(...xs);
  const ymin = Math.min(0, ...ys), ymax = Math.max(0, ...ys);
  const spanY = (ymax - ymin) || 1;
  const px = i => PAD + (xmax===xmin ? 0 : (i - xmin) / (xmax - xmin)) * (W - 2*PAD);
  const py = v => H - PAD - ((v - ymin) / spanY) * (H - 2*PAD);
  const line = pts.map((p,k)=>`${k?'L':'M'}${px(p.i).toFixed(1)},${py(p.cum).toFixed(1)}`).join(' ');
  const area = `${line} L${px(xmax).toFixed(1)},${py(0).toFixed(1)} L${px(xmin).toFixed(1)},${py(0).toFixed(1)} Z`;
  const zero = py(0);
  const dots = pts.filter(p=>p.signal_id).map(p=>{
    const c = p.r > 0 ? '#22c55e' : (p.r < 0 ? '#ef4444' : '#7f8fa1');
    return `<circle cx="${px(p.i).toFixed(1)}" cy="${py(p.cum).toFixed(1)}" r="3.5" fill="${c}"><title>${p.signal_id} ${p.pair||''} ${p.status||''} r=${p.r>0?'+':''}${p.r} cum=${p.cum>0?'+':''}${p.cum}</title></circle>`;
  }).join('');
  const yTicks = 5;
  let grid = '';
  for(let t=0;t<=yTicks;t++){
    const v = ymin + (spanY*t/yTicks);
    const y = py(v);
    grid += `<line x1="${PAD}" y1="${y.toFixed(1)}" x2="${W-PAD}" y2="${y.toFixed(1)}" stroke="#1d2733" stroke-width="1"/>`;
    grid += `<text x="${PAD-6}" y="${(y+3).toFixed(1)}" fill="#7f8fa1" font-size="10" text-anchor="end">${v>0?'+':''}${v.toFixed(1)}</text>`;
  }
  const last = pts[pts.length-1];
  const lastColor = last.cum >= 0 ? '#22c55e' : '#ef4444';
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto;display:block">
    <defs><linearGradient id="eqg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.35"/>
      <stop offset="100%" stop-color="#38bdf8" stop-opacity="0.02"/>
    </linearGradient></defs>
    ${grid}
    <line x1="${PAD}" y1="${zero.toFixed(1)}" x2="${W-PAD}" y2="${zero.toFixed(1)}" stroke="#3a4b5c" stroke-width="1" stroke-dasharray="4 3"/>
    <path d="${area}" fill="url(#eqg)"/>
    <path d="${line}" fill="none" stroke="#38bdf8" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>
    ${dots}
    <text x="${W-PAD}" y="${(py(last.cum)-8).toFixed(1)}" fill="${lastColor}" font-size="12" font-weight="700" text-anchor="end">${last.cum>0?'+':''}${last.cum.toFixed(2)}R</text>
  </svg>
  <div class="muted" style="font-size:10px;margin-top:4px">Titik hijau = win, merah = loss, abu = BE/expired. Kumulatif dalam R (1R = risiko per trade).</div>`;
}

async function load(){
  let d;
  try { d = await (await fetch('api/summary', {cache:'no-store'})).json(); }
  catch(e){ document.getElementById('hdr-status').textContent = 'API error'; return; }
  const p = d.pipeline, s = d.stats, m = d.mexc;

  document.getElementById('hdr-time').textContent = d.now;
  const hs = document.getElementById('hdr-status');
  hs.textContent = fmt(p.last_status);
  hs.className = 'badge ' + ((p.last_status==='ok'||p.last_status==='completed') ? 'ok'
      : (p.last_status ? 'bad' : 'neutral'));

  renderEquity(d.equity || {});

  document.getElementById('kpis').innerHTML = `
    <div class="card"><div class="kpi-label">Balance MEXC</div>
      <div class="kpi-value">${usd(m.balance)}</div>
      <div class="kpi-note">${m.ok ? 'live' : 'gagal ambil: ' + (m.error||'—')}</div></div>
    <div class="card"><div class="kpi-label">Posisi Open</div>
      <div class="kpi-value">${(m.positions||[]).length}</div>
      <div class="kpi-note">max 2 · risk ~$1.5/trade</div></div>
    <div class="card"><div class="kpi-label">Estimasi R (equity ledger)</div>
      <div class="kpi-value" style="color:${(d.equity&&d.equity.stats&&d.equity.stats.total_r>=0)?'var(--green)':'var(--red)'}">${(d.equity&&d.equity.stats&&d.equity.stats.total_r>0)?'+':''}${(d.equity&&d.equity.stats)?fmt(d.equity.stats.total_r):'—'}R</div>
      <div class="kpi-note">${(d.equity&&d.equity.stats)?(d.equity.stats.trades+' trade tertutup · expectancy '+(d.equity.stats.expectancy_r>0?'+':'')+d.equity.stats.expectancy_r+'R'):'—'}</div></div>
    <div class="card"><div class="kpi-label">Winrate</div>
      <div class="kpi-value">${s.winrate_pct===null?'—':s.winrate_pct+'%'}</div>
      <div class="kpi-note">${s.wins} win / ${s.closed} closed</div></div>
    <div class="card"><div class="kpi-label">Laporan terakhir</div>
      <div class="kpi-value" style="font-size:16px">${fmt(p.last_output)}</div>
      <div class="kpi-note">${p.last_output_age_min===null?'—':p.last_output_age_min+' menit lalu'}</div></div>
    <div class="card"><div class="kpi-label">Scan berikutnya</div>
      <div class="kpi-value" style="font-size:16px">${fmt((p.next_run_at||'').slice(11,16))}</div>
      <div class="kpi-note">${fmt((p.schedule||{}).display || p.schedule)} · streak fail ${p.failure_streak}</div></div>
    <div class="card" title="${(p.universe_pairs||[]).join(', ')}">
      <div class="kpi-label">Koin di-scan</div>
      <div class="kpi-value">${p.universe||'—'}</div>
      <div class="kpi-note">pair Binance USDT-perp tiap scan · hover untuk daftar</div></div>`;

  const ag = d.agents || {}, ags = ag.agents || [];
  document.getElementById('agents-run').textContent = ag.run
    ? `digest ${ag.run}` + (ag.file_age_min != null ? ` · ${ag.file_age_min} menit lalu` : '') : '';
  // 6 baris tetap -> JANGAN dikasih max-height/scroll, semua harus kelihatan.
  document.getElementById('agents').innerHTML = ags.length ? `
    <div class="panel">
    ${ags.map(a=>{
      const st = a.state || 'neutral';
      const cls = st==='ok' ? 'ok' : st==='warn' ? 'warn' : st==='bad' ? 'bad' : 'neutral';
      const lbl = st==='ok' ? 'aktif' : st==='idle' ? 'idle' : st==='warn' ? 'perhatian' : 'n/a';
      return `<div class="ag">
        <span class="ag-code">${esc(a.code)}</span>
        <div style="flex:1;min-width:0">
          <div class="ag-name">${esc(a.name)} <span class="badge ${cls}">${lbl}</span></div>
          <div class="ag-func">${esc(a.func)}</div>
          <div class="ag-status">${esc(a.status)}</div>
        </div></div>`;
    }).join('')}
    </div>`
    : '<div class="card muted">Belum ada data agent — akan terisi setelah run pipeline.</div>';

  const items = d.watchlist.items || [];
  document.getElementById('wl-count').textContent =
    items.length ? `${items.length} signal (baru di atas) · scroll untuk riwayat ↓` : '';
  document.getElementById('watchlist').innerHTML = items.length ? `
    <div class="scroll-box">
    <table><thead><tr><th>Signal</th><th>Pair</th><th>Arah</th><th>Entry zone</th><th>SL</th><th>TP1</th><th>TP2</th><th>Status</th><th>Order</th></tr></thead>
    <tbody>${items.map(i=>`<tr>
      <td class="mono">${i.signal_id||'—'}</td><td><b>${i.pair||'—'}</b></td>
      <td>${i.direction||'—'}</td><td class="mono">${i.entry_zone||'—'}</td>
      <td class="mono">${fmt(i.sl)}</td><td class="mono">${fmt(i.tp1)}</td><td class="mono">${fmt(i.tp2)}</td>
      <td>${statusBadge(i.status)}</td>
      <td class="muted">${i.exec_skip ? '<span style="color:#f0b429;font-weight:600" title="' + (i.exec_skip_reason||'') + '">📄 PAPER — tanpa eksekusi</span>' : (i.auto_order_note||'—')}</td></tr>`).join('')}</tbody></table>
    </div>`
    : '<div class="card muted">Belum ada signal di watchlist.</div>';

  const pos = m.positions || [];
  document.getElementById('mexc').innerHTML = pos.length ? `
    <table><thead><tr><th>Symbol</th><th>Arah</th><th>Vol</th><th>Entry</th><th>Leverage</th><th>IM</th></tr></thead>
    <tbody>${pos.map(x=>`<tr><td><b>${x.symbol}</b></td><td>${statusBadge(x.side)}</td>
      <td class="mono">${fmt(x.vol)}</td><td class="mono">${fmt(x.open_price)}</td>
      <td class="mono">${fmt(x.leverage)}x</td><td class="mono">${fmt(x.im)}</td></tr>`).join('')}</tbody></table>`
    : `<div class="card"><span class="badge neutral">FLAT</span> <span class="muted">tidak ada posisi open · balance ${usd(m.balance)}</span></div>`;

  const a6 = d.agent6 && d.agent6.latest;
  if(a6){
    const mac = a6.macro || {}, pos6 = a6.positioning || {};
    const pctChange = v => (v===null||v===undefined)?'—':(v>0?'+':'')+Number(v).toFixed(2)+'%';
    const crowdBadge = c => {
      if(!c) return '<span class="badge neutral">n/a</span>';
      const k = c.toLowerCase();
      const cls = k.includes('smart money long') ? 'ok'
                : k.includes('divergensi') ? 'bad'
                : k.includes('crowded') ? 'warn'
                : 'neutral';
      return `<span class="badge ${cls}">${c}</span>`;
    };
    const tagBadge = t => {
      if(!t) return '<span class="badge neutral">—</span>';
      const cls = t === 'posisi open' ? 'ok' : t === 'signal aktif' ? 'warn' : 'neutral';
      const lbl = t === 'kandidat' ? 'kandidat' : '● ' + t;
      return `<span class="badge ${cls}">${lbl}</span>`;
    };
    const rows = Object.entries(pos6).map(([sym,r])=>{
      const top=r.top_ls, ret=r.retail_ls;
      return `<tr><td><b>${sym}</b></td>
        <td>${tagBadge(r.tag)}</td>
        <td class="mono">${top??'—'}${r.top_long_pct?` (${r.top_long_pct.toFixed(1)}% long)`:''}</td>
        <td class="mono">${ret??'—'}${r.retail_long_pct?` (${r.retail_long_pct.toFixed(1)}% long)`:''}</td>
        <td>${crowdBadge(r.crowd)}</td></tr>`;
    }).join('');
    document.getElementById('a6').innerHTML = `
      <div class="sub-h">Blok 1 — Makro on-chain (DefiLlama) · 3 metrik &rarr; skor makro</div>
      <div class="grid" style="margin-top:0">
        <div class="card"><div class="kpi-label">Skor Makro</div>
          <div class="kpi-value" style="color:${mac.score>=0?'var(--green)':'var(--red)'}">${mac.score>0?'+':''}${mac.score}/3</div>
          <div class="kpi-note">${mac.label||'—'} · confluence only, bukan gate</div></div>
        <div class="card"><div class="kpi-label">Stablecoin supply</div>
          <div class="kpi-value" style="font-size:16px">${mac.stablecoin_usd?('$'+(mac.stablecoin_usd/1e9).toFixed(1)+'B'):'—'}</div>
          <div class="kpi-note">${pctChange(mac.stablecoin_chg1d)} 24j</div></div>
        <div class="card"><div class="kpi-label">DEX volume 24j</div>
          <div class="kpi-value" style="font-size:16px">${mac.dex_vol_24h?('$'+(mac.dex_vol_24h/1e9).toFixed(2)+'B'):'—'}</div>
          <div class="kpi-note">${pctChange(mac.dex_vol_chg1d)}</div></div>
        <div class="card"><div class="kpi-label">Total chain TVL</div>
          <div class="kpi-value" style="font-size:16px">${mac.tvl_usd?('$'+(mac.tvl_usd/1e9).toFixed(2)+'B'):'—'}</div>
          <div class="kpi-note">${pctChange(mac.tvl_chg1d)} 24j</div></div>
      </div>
      <div class="sub-h mt">Blok 2 — Positioning Binance Futures · top trader (smart money) vs crowd</div>
      ${rows?`<div class="scroll-box" style="max-height:280px"><table><thead><tr><th>Koin</th><th>Konteks</th><th>Top trader L/S</th><th>Crowd L/S</th><th>Klasifikasi</th></tr></thead><tbody>${rows}</tbody></table></div>`
             :'<div class="card muted">Data positioning tidak tersedia untuk snapshot ini.</div>'}
      <div class="muted" style="font-size:11px;margin-top:8px">Baris <b>● posisi open</b> &amp; <b>● signal aktif</b> diambil live dari Binance (bukan dari snapshot) supaya koin yang sedang ditradingkan selalu kelihatan. Sisanya = <b>kandidat</b> dari snapshot ${a6.ts||'—'} · datanya lagging, dipakai hanya sebagai konteks</div>`;
  } else {
    document.getElementById('a6').innerHTML = '<div class="card muted">Belum ada data Agent 6 (akan terisi setelah run pipeline berikutnya).</div>';
  }

  const meta = (d.watchlist.meta)||{};
  const evb = meta.eval_note_bullets || [];
  document.getElementById('eval-ts').textContent =
    meta.last_eval ? 'update terakhir ' + String(meta.last_eval).replace('T',' ').slice(0,16) + ' WIB' : '';
  if(evb.length){
    document.getElementById('evalnote').innerHTML = evb.map(g => `
      <div class="ev-g">
        ${g.label ? `<div class="ev-l">${esc(g.label)}</div>` : ''}
        <ul class="ev-ul">${g.items.map(t=>`<li>${esc(t)}</li>`).join('')}</ul>
      </div>`).join('');
  } else {
    document.getElementById('evalnote').textContent = meta.last_eval_note || '—';
  }
}
load();
setInterval(load, 60000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        try:
            if path in ("/", "/status", "/crypto", "/crypto/", "/index.html", "/crypto/index.html"):
                self._send(200, PAGE, "text/html; charset=utf-8")
            elif path in ("/api/summary", "/crypto/api/summary"):
                self._send(200, json.dumps(summary(), ensure_ascii=False, default=str))
            elif path in ("/api/pipeline", "/crypto/api/pipeline"):
                self._send(200, json.dumps(pipeline_status(), ensure_ascii=False))
            elif path in ("/api/watchlist", "/crypto/api/watchlist"):
                self._send(200, json.dumps(watchlist(), ensure_ascii=False))
            elif path in ("/api/agent6", "/crypto/api/agent6"):
                self._send(200, json.dumps(agent6(), ensure_ascii=False))
            elif path in ("/api/equity", "/crypto/api/equity"):
                import crypto_equity
                self._send(200, json.dumps(crypto_equity.curve(), ensure_ascii=False, default=str))
            else:
                self._send(404, json.dumps({"error": "not found", "path": path}))
        except Exception as exc:
            self._send(500, json.dumps({"error": f"{type(exc).__name__}: {exc}"}))


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"₿ Crypto dashboard on http://127.0.0.1:{PORT}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
