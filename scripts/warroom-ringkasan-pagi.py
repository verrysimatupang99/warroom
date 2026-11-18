#!/usr/bin/env python3
"""warroom-ringkasan-pagi (cyber1) — kirim ringkasan pagi ke Telegram HQ.

Kenapa di cyber1: notify-hq (token Telegram HQ) ada di cyber1, dan cyber1 bisa
menjangkau API publik War Room. Jadi ringkasan dirangkai di sini tanpa perlu root.

Alur: login ke API publik War Room sebagai owner (kredensial di accounts.env
lokal cyber1) -> ambil MT5 status + sinyal per pasar + kalender makro ->
format ringkas -> kirim via notify-hq.

Dijalankan systemd timer (user) tiap pagi 07:00 WIB.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

API = os.environ.get("WARROOM_API", "http://127.0.0.1:8800")
WIB = timedelta(hours=7)
SESSION_FILE = Path("/home/admin/.config/warroom/ringkasan-pagi-session.txt")
ACCOUNTS = Path("/home/admin/.config/warroom/accounts.env")


def _login_cookie() -> str | None:
    """Login sebagai owner -> cookie sesi. Cache di file; verifikasi dulu bila ada."""
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
        f"{API}/api/v1/auth/login",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
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
    req = urllib.request.Request(
        f"{API}/api/v1/auth/me", headers={"Cookie": f"wr_session={sid}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def _ambil(path: str) -> dict | None:
    sid = _login_cookie()
    if not sid:
        return None
    req = urllib.request.Request(f"{API}{path}", headers={"Cookie": f"wr_session={sid}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"WARN gagal ambil {path}: {e}")
        return None


def _mt5_blok() -> list[str]:
    d = _ambil("/api/v1/tencent/mt5/status")
    if not d:
        return ["• MT5: status tidak tersedia"]
    baris = []
    eq, bal = d.get("equity"), d.get("balance")
    pnl, pos = d.get("floating_pnl"), d.get("positions") or []
    if eq is not None:
        baris.append(f"• Equity: ${eq:,.2f}" + (f" (balance ${bal:,.2f})" if bal else ""))
    if pnl is not None:
        baris.append(f"• Floating P/L: {'+' if pnl >= 0 else ''}${pnl:,.2f}")
    baris.append(f"• Posisi terbuka: {len(pos)}")
    trade, wr = d.get("total_trades_today"), d.get("win_rate_pct")
    if trade is not None:
        baris.append(f"• Trade hari ini: {trade}" + (f" (win {wr:.0f}%)" if wr else ""))
    return baris or ["• MT5: tidak ada data"]


def _sinyal_blok() -> list[str]:
    d = _ambil("/api/v1/sinyal/per-pasar")
    if not d:
        return ["• Sinyal: tidak tersedia"]
    baris = []
    for p in d.get("pasar", []):
        label = p.get("label") or p.get("pasar")
        status = p.get("status_data")
        if status == "ada":
            n = p.get("jumlah") or len(p.get("sinyal") or [])
            baris.append(f"• {label}: {n} sinyal aktif")
        elif status == "kosong":
            baris.append(f"• {label}: tidak ada setup cocok")
        elif status == "gagal":
            baris.append(f"• {label}: PEMINDAIAN MATI (periksa)")
    return baris or ["• Sinyal: tidak ada data"]


def _makro_blok() -> list[str]:
    d = _ambil("/api/v1/kalender/makro?dampak=tinggi&batas=5")
    if not d:
        return []
    baris = []
    for ev in (d.get("acara") or d.get("events") or [])[:5]:
        waktu = ev.get("waktu") or ev.get("time") or ""
        nama = ev.get("nama") or ev.get("event") or ev.get("judul") or ""
        mata = ev.get("mata_uang") or ev.get("currency") or ""
        if nama:
            baris.append(f"• {waktu} {mata} {nama}".strip())
    return baris


def _bangun_pesan() -> str:
    now = datetime.now(UTC) + WIB
    baris = [f"🌅 RINGKASAN PAGI — {now.strftime('%A, %d %b %Y')} ({now.strftime('%H:%M WIB')})", ""]
    baris.append("💰 MT5 / EKSEKUSI")
    baris.extend(_mt5_blok())
    baris.append("")
    baris.append("📡 SINYAL PER PASAR")
    baris.extend(_sinyal_blok())
    makro = _makro_blok()
    if makro:
        baris.append("")
        baris.append("📅 BERITA EKONOMI HARI INI (dampak tinggi)")
        baris.extend(makro)
    baris.append("")
    baris.append("Buka dashboard: http://127.0.0.1:8800")
    return "\n".join(baris)


def main() -> int:
    pesan = _bangun_pesan()
    # Kirim via notify-hq (token Telegram HQ di /etc/warroom-notify.env, cyber1).
    r = subprocess.run(["/home/admin/warroom/scripts/notify-hq", pesan], capture_output=True, text=True, timeout=40)
    ok = r.returncode == 0
    print(f"KIRIM ok={ok} {'| ' + r.stderr.strip()[:120] if not ok else ''}")
    if not ok:
        print(pesan)
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
