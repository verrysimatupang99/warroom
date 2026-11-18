#!/usr/bin/env python3
"""warroom-post-mortem (cyber1) — kirim post-mortem tiap trade MT5 tertutup.

Kenapa ada: operator ingin tahu langsung hasil tiap trade (net P/L, hold, arah)
tanpa membuka dashboard. Saat EA melaporkan deal tertutup ke API, watcher ini
mendeteksinya dan mengirim ringkasan post-mortem ke Telegram HQ.

Alur: poll GET /api/v1/tencent/mt5/deals (cookie owner) -> bandingkan ticket
dengan state tersimpan -> deal baru -> format post-mortem -> kirim via notify-hq.

Dijalankan systemd timer (cyber1) tiap beberapa menit.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

API = os.environ.get("WARROOM_API", "http://127.0.0.1:8800")
WIB = timedelta(hours=7)
SESSION_FILE = Path("/home/admin/.config/warroom/ringkasan-pagi-session.txt")
ACCOUNTS = Path("/home/admin/.config/warroom/accounts.env")
STATE_FILE = Path("/home/admin/.config/warroom/post-mortem-state.json")


def _login_cookie() -> str | None:
    if SESSION_FILE.exists():
        sid = SESSION_FILE.read_text().strip()
        if sid and _cek_sesi(sid):
            return sid
    user = password = ""
    if ACCOUNTS.exists():
        for line in ACCOUNTS.read_text().splitlines():
            if line.startswith("owner_user="):
                user = line.split("=", 1)[1].strip()
            elif line.startswith("owner_pass="):
                password = line.split("=", 1)[1].strip()
    if not user or not password:
        print("WARN kredensial owner tidak ditemukan")
        return None
    body = json.dumps({"username": user, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        f"{API}/api/v1/auth/login", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            for part in r.headers.get("Set-Cookie", "").split(";"):
                part = part.strip()
                if part.startswith("wr_session="):
                    sid = part.split("=", 1)[1]
                    try:
                        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
                        SESSION_FILE.write_text(sid)
                    except OSError:
                        pass
                    return sid
    except Exception as e:  # noqa: BLE001
        print(f"WARN login gagal: {e}")
    return None


def _cek_sesi(sid: str) -> bool:
    req = urllib.request.Request(f"{API}/api/v1/auth/me", headers={"Cookie": f"wr_session={sid}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def _ambil_deals() -> list[dict]:
    sid = _login_cookie()
    if not sid:
        return []
    req = urllib.request.Request(f"{API}/api/v1/tencent/mt5/deals?limit=25",
                                 headers={"Cookie": f"wr_session={sid}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8")).get("deals") or []
    except Exception as e:  # noqa: BLE001
        print(f"WARN gagal ambil deals: {e}")
        return []


def _muat_state() -> set[int]:
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text()))
        except Exception:  # noqa: BLE001
            pass
    return set()


def _simpan_state(tickets: set[int]) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Simpan maksimal 500 ticket terakhir agar file tak membengkak.
        STATE_FILE.write_text(json.dumps(sorted(tickets)[-500:]))
    except OSError as e:
        print(f"WARN gagal simpan state: {e}")


def _fmt_durasi(open_t: str, close_t: str) -> str:
    try:
        fmt = "%Y-%m-%d %H:%M:%S"
        o = datetime.strptime(open_t, fmt)
        c = datetime.strptime(close_t, fmt)
        d = c - o
        menit = int(d.total_seconds() // 60)
        if menit < 60:
            return f"{menit}m"
        return f"{menit // 60}j {menit % 60}m"
    except Exception:  # noqa: BLE001
        return "-"


def _post_mortem(d: dict) -> str:
    sym = d.get("symbol") or "?"
    side = (d.get("side") or "?").upper()
    net = d.get("net") or 0.0
    tanda = "+" if net >= 0 else ""
    emoji = "🟢" if net >= 0 else "🔴"
    hasil = "PROFIT" if net >= 0 else "RUGI"
    vol = d.get("volume") or "?"
    dur = _fmt_durasi(d.get("open_time") or "", d.get("close_time") or "")
    strat = d.get("strategy_version") or d.get("comment") or "-"
    baris = [
        f"{emoji} POST-MORTEM — {sym} {side}",
        f"• Hasil: {hasil} {tanda}${net:,.2f}",
        f"• Volume: {vol} | Hold: {dur}",
        f"• Entry→Exit: {d.get('open_price') or '?'} → {d.get('close_price') or '?'}",
        f"• Strategi: {strat}",
        f"• Ticket: {d.get('ticket')}",
    ]
    return "\n".join(baris)


def main() -> int:
    deals = _ambil_deals()
    if not deals:
        print("tidak ada deal / data kosong")
        return 0
    seen = _muat_state()
    baru = [d for d in deals if d.get("ticket") and d["ticket"] not in seen]
    if not seen and deals:
        # Pertama kali jalan: catat semua ticket yang ada TANPA mengirim (hindari spam riwayat lama).
        _simpan_state({d["ticket"] for d in deals})
        print(f"inisialisasi: {len(deals)} deal tercatat, tidak mengirim")
        return 0
    for d in baru:
        pesan = _post_mortem(d)
        r = subprocess.run(["/home/admin/warroom/scripts/notify-hq", pesan], capture_output=True, text=True, timeout=40)
        ok = r.returncode == 0
        print(f"POST-MORTEM ticket={d.get('ticket')} ok={ok} {'| ' + r.stderr.strip()[:100] if not ok else ''}")
        seen.add(d["ticket"])
    if baru:
        _simpan_state(seen)
    print(f"selesai: {len(baru)} post-mortem terkirim")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
