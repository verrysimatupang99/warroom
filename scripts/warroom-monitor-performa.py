#!/usr/bin/env python3
"""warroom-monitor-performa (cyber1) — pantau kesehatan performa trading MT5 nyata.

Kenapa ada: operator ingin tahu DINI kalau performa trading eksekusi nyata memburuk
(winrate anjlok, profit factor < 1, atau loss beruntun), bukan menunggu akhir bulan.
Monitor ini membaca deal tertutup nyata (deals.csv via endpoint GET /mt5/deals) dan
mengirim peringatan Telegram saat performa menurun.

Metrik (dihitung dari deal nyata, bukan angka karangan):
- Winrate, Profit Factor (PF = gross profit / gross loss), loss beruntun terpanjang.
Ambang alert:
- PF < 1.0 setelah >= MIN_TRADE deal  -> strategi rugi secara agregat.
- Loss beruntun >= STREAK_RUGI        -> kemungkinan strategi/param tidak cocok pasar.

Catatan: saat belum ada cukup deal nyata, monitor diam (dormant) dan tidak spam.
Dijalankan systemd timer (cyber1) tiap 30 menit.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from pathlib import Path

API = os.environ.get("WARROOM_API", "http://127.0.0.1:8800")
SESSION_FILE = Path("/home/admin/.config/warroom/ringkasan-pagi-session.txt")
ACCOUNTS = Path("/home/admin/.config/warroom/accounts.env")
STATE_FILE = Path("/home/admin/.config/warroom/monitor-performa-state.json")
JENDELA = 30  # evaluasi 30 deal terakhir
MIN_TRADE = 10  # minimal deal sebelum menilai PF
STREAK_RUGI = 4  # alert saat loss beruntun mencapai ini
PF_AMBANG = 1.0


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
    req = urllib.request.Request(f"{API}/api/v1/tencent/mt5/deals?limit={JENDELA}",
                                 headers={"Cookie": f"wr_session={sid}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8")).get("deals") or []
    except Exception as e:  # noqa: BLE001
        print(f"WARN gagal ambil deals: {e}")
        return []


def _muat_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:  # noqa: BLE001
            pass
    return {"pf_alert": False, "streak_alert": False}


def _simpan_state(st: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(st))
    except OSError as e:
        print(f"WARN gagal simpan state: {e}")


def _kirim(pesan: str) -> bool:
    r = subprocess.run(["/home/admin/warroom/scripts/notify-hq", pesan], capture_output=True, text=True, timeout=40)
    return r.returncode == 0


def _hitung(deals: list[dict]) -> dict:
    """Hitung winrate, PF, loss beruntun terpanjang dari daftar deal (net)."""
    nets = []
    for d in deals:
        try:
            nets.append(float(d.get("net") or 0.0))
        except (TypeError, ValueError):
            continue
    if not nets:
        return {}
    menang = [n for n in nets if n > 0]
    rugi = [n for n in nets if n < 0]
    winrate = len(menang) / len(nets) * 100
    gross_profit = sum(menang)
    gross_loss = abs(sum(rugi))
    pf = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)
    # loss beruntun terpanjang (urut dari terbaru ke terlama)
    streak = 0
    streak_max = 0
    for n in nets:
        if n < 0:
            streak += 1
            streak_max = max(streak_max, streak)
        else:
            streak = 0
    return {
        "total": len(nets), "winrate": winrate, "pf": pf,
        "gross_profit": gross_profit, "gross_loss": gross_loss,
        "streak_rugi": streak, "streak_max": streak_max,
    }


def main() -> int:
    deals = _ambil_deals()
    m = _hitung(deals)
    if not m or m["total"] < MIN_TRADE:
        print(f"deal {m.get('total', 0)}/{MIN_TRADE} — belum cukup untuk menilai, monitor diam")
        return 0

    st = _muat_state()
    terkirim = 0

    # Alert PF rendah (agregat rugi)
    if m["pf"] < PF_AMBANG:
        if not st.get("pf_alert"):
            pesan = (
                f"📉 MONITOR PERFORMA — Profit Factor rendah\n"
                f"• PF: {m['pf']:.2f} (ambang {PF_AMBANG:.1f})\n"
                f"• Winrate: {m['winrate']:.0f}% dari {m['total']} deal\n"
                f"• Gross profit: ${m['gross_profit']:,.2f} | Gross loss: ${m['gross_loss']:,.2f}\n"
                f"⚠️ Secara agregat strategi RUGI. Evaluasi parameter/strategi."
            )
            if _kirim(pesan):
                st["pf_alert"] = True
                terkirim += 1
    else:
        st["pf_alert"] = False  # pulih -> reset agar bisa alert lagi kalau memburuk

    # Alert loss beruntun
    if m["streak_rugi"] >= STREAK_RUGI:
        if not st.get("streak_alert"):
            pesan = (
                f"🔴 MONITOR PERFORMA — Loss beruntun\n"
                f"• {m['streak_rugi']} rugi beruntun (ambang {STREAK_RUGI})\n"
                f"• Winrate: {m['winrate']:.0f}% dari {m['total']} deal\n"
                f"⚠️ Kemungkinan strategi tidak cocok kondisi pasar. Pertimbangkan jeda."
            )
            if _kirim(pesan):
                st["streak_alert"] = True
                terkirim += 1
    else:
        st["streak_alert"] = False

    _simpan_state(st)
    print(f"PF={m['pf']:.2f} winrate={m['winrate']:.0f}% streak={m['streak_rugi']} -> {terkirim} alert")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
