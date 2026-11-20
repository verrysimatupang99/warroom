#!/usr/bin/env python3
"""warroom-ringkasan-pagi — kirim ringkasan pagi ke Telegram HQ.

Kenapa ada: operator memantau 4-5 pasar (crypto, forex, IDX, polymarket, memecoin).
Membuka dashboard tiap pagi untuk cek semuanya memakan waktu dan setup bisa terlewat.
Skrip ini menggabungkan: posisi MT5 + equity, sinyal per pasar, dan kalender makro
hari ini menjadi SATU pesan ringkas, dikirim otomatis tiap pagi.

Sumber data: API War Room sendiri (localhost:8800) memakai service token — pola sama
dengan pantau-tick. Kirim lewat transport resmi (TelegramTransport) seperti alert-push.

Dijalankan systemd timer warroom-ringkasan-pagi.timer tiap pagi.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

API = os.environ.get("WARROOM_API", "http://127.0.0.1:8800")
NOTIFIER_SRC = "/home/admin/warroom/services/notifier/src"
SERVICE_TOKEN_FILE = Path("/etc/warroom/service_token.env")
WIB = timedelta(hours=7)


def _service_token() -> str:
    tok = os.environ.get("WARROOM_SERVICE_TOKEN", "")
    if tok:
        return tok
    if SERVICE_TOKEN_FILE.exists():
        for line in SERVICE_TOKEN_FILE.read_text().splitlines():
            if line.startswith("WARROOM_SERVICE_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


SESSION_FILE = Path("/var/lib/warroom-ringkasan-pagi/session.txt")
ACCOUNTS = Path("/home/admin/.config/warroom/accounts.env")


def _login_cookie() -> str | None:
    """Login sebagai owner (kredensial di accounts.env) -> cookie sesi.

    Endpoint sinyal/kalender memakai auth.current_user (cookie sesi), bukan
    service token. Jadi skrip login dulu; sesi disimpan agar tak login tiap kali.
    """
    if SESSION_FILE.exists():
        sid = SESSION_FILE.read_text().strip()
        if sid:
            # verifikasi sesi masih hidup
            req = urllib.request.Request(
                f"{API}/api/v1/auth/me",
                headers={"Cookie": f"wr_session={sid}"},
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    if r.status == 200:
                        return sid
            except Exception:  # noqa: BLE001
                pass
    # login ulang
    user = password = ""
    if ACCOUNTS.exists():
        for line in ACCOUNTS.read_text().splitlines():
            if line.startswith("owner_user="):
                user = line.split("=", 1)[1].strip()
            elif line.startswith("owner_pass="):
                password = line.split("=", 1)[1].strip()
    if not user or not password:
        print("WARN kredensial owner tidak ditemukan di accounts.env")
        return None
    body = json.dumps({"username": user, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        f"{API}/api/v1/auth/login",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            set_cookie = r.headers.get("Set-Cookie", "")
            sid = None
            for part in set_cookie.split(";"):
                part = part.strip()
                if part.startswith("wr_session="):
                    sid = part.split("=", 1)[1]
                    break
            if sid:
                # Simpan sesi (cache) — bila gagal tulis, tetap kembalikan sid.
                try:
                    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
                    SESSION_FILE.write_text(sid)
                except OSError:
                    pass
                return sid
    except Exception as e:  # noqa: BLE001
        print(f"WARN login gagal: {e}")
    return None


def _ambil(path: str) -> dict | None:
    """GET ke API War Room dengan cookie sesi owner. None bila gagal."""
    sid = _login_cookie()
    if not sid:
        return None
    req = urllib.request.Request(
        f"{API}{path}", headers={"Cookie": f"wr_session={sid}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"WARN gagal ambil {path}: {e}")
        return None


def _mt5_blok() -> list[str]:
    d = _ambil("/api/v1/tencent/mt5/status")
    if not d:
        return ["• MT5: status tidak tersedia"]
    baris = []
    eq = d.get("equity")
    bal = d.get("balance")
    pos = d.get("positions") or []
    pnl = d.get("floating_pnl")
    is_cent = d.get("currency") == "USC" or str(d.get("account")) in ("452009427", "36525553")
    factor = 100.0 if is_cent else 1.0
    if eq is not None:
        eq_usd = eq / factor
        bal_usd = bal / factor if bal is not None else None
        bal_txt = f" (balance ${bal_usd:,.2f})" if bal_usd else ""
        usc_txt = " (USC)" if is_cent else ""
        baris.append(f"• Equity: ${eq_usd:,.2f}" + bal_txt + usc_txt)
    if pnl is not None:
        pnl_usd = pnl / factor
        tanda = "+" if pnl_usd >= 0 else ""
        baris.append(f"• Floating P/L: {tanda}${pnl_usd:,.2f}")
    baris.append(f"• Posisi terbuka: {len(pos)}")
    trade = d.get("total_trades_today")
    wr = d.get("win_rate_pct")
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
    hari = now.strftime("%A, %d %b %Y")
    jam = now.strftime("%H:%M WIB")

    baris = [f"🌅 RINGKASAN PAGI — {hari} ({jam})", ""]
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
    baris.append("Buka dashboard: https://polywarroom.vps.webdock.cloud")
    return "\n".join(baris)


def main() -> int:
    pesan = _bangun_pesan()
    sys.path.insert(0, NOTIFIER_SRC)
    try:
        from warroom_notifier.transport import transport_from_env
    except Exception as e:  # noqa: BLE001
        print(f"WARN gagal impor transport: {e}")
        print(pesan)  # fallback: cetak ke stdout agar tetap terlihat di journal
        return 0

    t = transport_from_env()
    res = t.send(
        "War Room ringkasan pagi",
        pesan,
        "info",
        {"jenis": "ringkasan-pagi"},
    )
    if not res.ok:
        # Bila kirim gagal (mis. transport belum terkonfigurasi), cetak pesan ke
        # journal supaya ringkasan tetap tercatat dan bisa diaudit.
        print(pesan)
    print(f"KIRIM ok={res.ok} transport={getattr(t, 'name', '?')} detail={res.detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
