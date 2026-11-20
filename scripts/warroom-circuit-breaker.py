#!/usr/bin/env python3
"""warroom-circuit-breaker (cyber1) — alert saat ruang risiko harian hampir habis.

Kenapa ada: setiap pasar punya batas rugi harian (mis. 3R). Kalau operator over-trade
atau revenge trading, ruang risiko bisa habis tanpa disadari. Watcher ini memantau
sisa ruang risiko per pasar dan mengirim peringatan Telegram saat sisa < 1R —
sekali per hari per pasar, agar tidak spam.

Sumber: GET /api/v1/verdict (cookie owner). sisa_ruang_r = batas_rugi_r - hari_ini_r.

Dijalankan systemd timer (cyber1) tiap 10 menit.
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
STATE_FILE = Path("/home/admin/.config/warroom/circuit-breaker-state.json")
AMBATAS_SISA_R = 1.0  # alert saat sisa ruang < 1R


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


def _ambil_verdict() -> dict:
    sid = _login_cookie()
    if not sid:
        return {}
    req = urllib.request.Request(f"{API}/api/v1/verdict", headers={"Cookie": f"wr_session={sid}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"WARN gagal ambil verdict: {e}")
        return {}


def _muat_state() -> dict:
    """State: {hari: 'YYYY-MM-DD', sudah_alert: {pasar: true}}."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:  # noqa: BLE001
            pass
    return {}


def _simpan_state(st: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(st))
    except OSError as e:
        print(f"WARN gagal simpan state: {e}")


def _hari_ini() -> str:
    return (datetime.now(UTC) + WIB).strftime("%Y-%m-%d")


def main() -> int:
    data = _ambil_verdict()
    verdicts = data.get("verdict") or []
    if not verdicts:
        print("tidak ada data verdict")
        return 0

    hari = _hari_ini()
    st = _muat_state()
    if st.get("hari") != hari:
        st = {"hari": hari, "sudah_alert": {}}  # reset harian

    terkirim = 0
    for v in verdicts:
        pasar = v.get("pasar") or "?"
        detail = v.get("detail") or {}
        rk = detail.get("risiko") or v.get("risiko") or {}
        batas = rk.get("batas_rugi_r")
        terpakai = rk.get("hari_ini_r")
        if batas is None or terpakai is None:
            continue
        sisa = float(batas) - float(terpakai)
        if sisa >= AMBATAS_SISA_R:
            continue
        if st["sudah_alert"].get(pasar):
            continue  # sudah diperingatkan hari ini
        pesan = (
            f"⚠️ CIRCUIT BREAKER — {pasar.upper()}\n"
            f"• Sisa ruang risiko: {sisa:.1f}R (dari {batas:.0f}R)\n"
            f"• Terpakai hari ini: {terpakai:.1f}R\n"
            f"⚠️ Hampir menyentuh batas rugi harian. Hindari over-trade / revenge trading.\n"
            f"Sisa ruang < {AMBATAS_SISA_R:.0f}R — pertimbangkan berhenti untuk hari ini."
        )
        r = subprocess.run(["/home/admin/warroom/scripts/notify-hq", pesan], capture_output=True, text=True, timeout=40)
        ok = r.returncode == 0
        print(f"CIRCUIT-BREAKER {pasar} sisa={sisa:.1f}R ok={ok}")
        st["sudah_alert"][pasar] = True
        terkirim += 1

    _simpan_state(st)
    print(f"selesai: {terkirim} alert circuit-breaker")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
