"""Server HTTP dashboard + render halaman."""

from __future__ import annotations

import json
import logging
import re
import threading
import time as _t
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from ..config import Settings, get_settings
from .html_parts import _card, _e
from .page_parts import (
    _blok,
    _css,
    _grup_badge,
    _hero,
    _kepala,
    _rakit,
    _ringkas,
)
from .panels import _ASETS_DIR, _FRONTEND_DIR, load_snapshot

log = logging.getLogger("live_trading.dashboard")

def render(snap, page="semua"):
    return _SHELL.format(css=_css(), header=_kepala(snap, page), body=_rakit(snap, page))


_SHELL = """<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>War Room</title><meta http-equiv="refresh" content="60">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap">
<style>{css}</style></head><body>{header}<div class="wrap">{body}</div></body></html>"""


def serve(settings: Settings | None = None) -> None:
    s = settings or get_settings()
    build_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:  # senyap di journal
            return

        def do_GET(self) -> None:  # noqa: N802
            seg = self.path.split("?")[0]
            if seg.startswith("/refresh"):
                with build_lock:
                    load_snapshot(s, force=True)
                dest = self.headers.get("Referer", "/")
                path_only = "/" + dest.split("/", 3)[-1] if "://" in dest else dest.split("?")[0]
                if not path_only.startswith(("/terminal", "/uang", "/bukti", "/pasar", "/proyek")):
                    path_only = "/"
                self.send_response(302)
                self.send_header("Location", path_only)
                self.end_headers()
                return
            if seg.startswith("/api/snapshot"):
                try:
                    raw = (s.state_dir / "snapshot.json").read_bytes()
                except OSError:
                    raw = b"{}"
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if seg.startswith("/api/klines"):
                import urllib.parse as _up

                q = _up.urlparse(self.path).query
                arg = _up.parse_qs(q)
                try:
                    raw = _klines(arg.get("pair", [""])[0].upper(), arg.get("tf", [""])[0])
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Cache-Control", "public, max-age=60")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except ValueError:
                    self.send_response(400)
                    self.end_headers()
                except OSError:
                    self.send_response(502)
                    self.end_headers()
                return
            if seg.startswith("/frag/"):
                nama = seg[len("/frag/") :]
                try:
                    snap = load_snapshot(s)
                    semua = fragments(snap)
                except OSError:
                    semua = {}
                if nama not in semua:
                    self.send_response(404)
                    self.end_headers()
                    return
                data = semua[nama].encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if seg.startswith("/assets/"):
                import mimetypes

                f = _ASETS_DIR / seg[len("/assets/") :]
                try:
                    data = f.resolve().read_bytes()
                    if _FRONTEND_DIR not in f.resolve().parents:
                        raise OSError("di luar frontend")
                except OSError:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    mimetypes.guess_type(str(f))[0] or "application/octet-stream",
                )
                self.send_header("Cache-Control", "public, max-age=300")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            rute = {
                "/": "index.html",
                "/terminal": "terminal.html",
                "/uang": "uang.html",
                "/bukti": "bukti.html",
                "/pasar": "pasar.html",
                "/proyek": "proyek.html",
            }
            nama_file = rute.get(seg, "index.html")
            try:
                data = (_FRONTEND_DIR / nama_file).read_bytes()
            except OSError:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    srv = ThreadingHTTPServer(("127.0.0.1", s.dashboard_port), Handler)
    print(f"War Room dashboard: http://127.0.0.1:{s.dashboard_port}", flush=True)
    srv.serve_forever()


def render_shell(snap: dict[str, Any]) -> str:
    """Alias untuk tes."""
    return render(snap)


_KLINES_TTL = 60.0
# Cache singkat hasil _klines (dulu di dashboard.py, terlewat oleh pemecah karena
# memakai anotasi `AnnAssign`). Definisi TUNGGAL di sini.
_KLINES_CACHE: dict[str, tuple[float, bytes]] = {}


def _klines(pair: str, tf: str) -> bytes:
    """Ambil klines Binance lewat server (browser user kadang diblokir Binance).

    Mengembalikan body JSON mentah. Raise ValueError untuk input jelek,
    OSError kalau kedua host Binance gagal.
    """
    import urllib.request as _ur

    if not re.fullmatch(r"[A-Z0-9]{4,20}", pair or ""):
        raise ValueError("pair jelek")
    if tf not in ("15m", "1h", "4h", "1d"):
        raise ValueError("tf jelek")
    kunci = f"{pair}/{tf}"
    entri = _KLINES_CACHE.get(kunci)
    if entri and _t.time() - entri[0] < _KLINES_TTL:
        return entri[1]
    err: Exception | None = None
    for host in ("https://api.binance.com", "https://data-api.binance.vision"):
        try:
            req = _ur.Request(
                f"{host}/api/v3/klines?symbol={pair}&interval={tf}&limit=120",
                headers={"User-Agent": "war-room/1.0"},
            )
            with _ur.urlopen(req, timeout=10) as r:
                raw = r.read()
            json.loads(raw)
            _KLINES_CACHE[kunci] = (_t.time(), raw)
            return raw
        except Exception as exc:  # noqa: BLE001
            err = exc
    raise OSError(f"binance gagal: {err}")


def fragments(snap):
    """Backend API: semua fragmen HTML untuk frontend statis.

    Kunci = nama seksi blok + potongan rakitan (hero/tldr/grup/footer).
    Frontend mengambil yang dibutuhkannya per halaman via /frag/<nama>.
    """
    e = _e
    out = _blok(snap)
    tldr = "".join(f"<li>{e(teks)}</li>" for teks, _nada in _ringkas(snap))
    out["hero"] = _hero(snap)
    out["tldr"] = _card("Ringkasan 10 detik", f"<ul class='tldr'>{tldr}</ul>")
    out["g-uang"] = _grup_badge(snap, "uang", "Uang", "Ke mana perginya uang paper?")
    out["g-bukti"] = _grup_badge(snap, "bukti", "Bukti", "Apakah sistemnya terbukti? Jawaban jujur di sini.")
    out["g-pasar"] = _grup_badge(snap, "pasar", "Pasar", "Kondisi lapangan — konteks, bukan perintah entry.")
    out["g-proyek"] = _grup_badge(snap, "proyek", "Proyek", "Mesin lain yang jalan paper — semua baca-saja.")
    out["footer"] = (
        f"<footer><p class='sub'>snapshot {e(snap.get('dibuat', ''))} · "
        "data dibangun ulang tiap 15 mnt</p><details><summary>Kamus singkat</summary><p class='sub'>"
        "R = kelipatan risiko per trade · warisan = trade lama, bukan hasil gate · "
        "gate = 6 aturan saring sinyal · HP = print paus · V/L = volume/likuiditas · "
        "shadow = hasil bayangan tanpa modal · exp = expectancy (rata2 R per trade) · "
        "tier = SKIP/STANDAR/PREMIUM (boleh entry atau tidak)</p></details></footer>"
    )
    for daftar in FRAGMEN_HALAMAN.values():
        for nama in daftar:
            out.setdefault(nama, "")
    return out


FRAGMEN_HALAMAN = {
    "index": ["hero", "tldr", "g-uang", "ledger", "posisi", "risiko", "footer"],
    "terminal": ["terminal", "pod_kripto", "footer"],
    "uang": ["g-uang", "ledger", "posisi", "risiko", "footer"],
    "bukti": ["g-bukti", "ukur", "backtest", "footer"],
    "pasar": ["g-pasar", "crypto", "hl", "idx", "idx_tv", "idx616", "pod_idx", "forex", "footer"],
    "proyek": ["g-proyek", "radar", "lp", "poly", "pod_poly", "gmgn", "pod_gmgn", "footer"],
}


