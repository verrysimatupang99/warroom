#!/usr/bin/env python3
"""warroom-alert-push — kirim hasil AWAS/ALERT watchdog ke Telegram.

Kenapa ada: live-trading-watchdog hanya mencetak ke journal. Journal bukan kanal
notifikasi — operator baru tahu ada masalah saat membuka terminal. Skrip ini
membaca keluaran watchdog terakhir dan meneruskannya lewat transport resmi
warroom (TelegramTransport), yang kredensialnya hanya bisa dibaca root
(/etc/warroom/notifier.env).

Dedupe: tanda tangan isi alert disimpan di /var/lib. Alert yang sama tidak
dikirim ulang sampai REMIND_S (6 jam) lewat, supaya gangguan yang menetap tidak
menjadi spam tiap 10 menit.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

UNIT = "live-trading-watchdog.service"
STATE = Path("/var/lib/warroom-alert-push/state.json")
NOTIFIER_SRC = "/home/admin/warroom/services/notifier/src"
REMIND_S = 6 * 3600
JENDELA = "-45 min"

PREFIX = ("AWAS", "ALERT", "WARN")


def ambil_baris() -> list[str]:
    try:
        r = subprocess.run(
            ["journalctl", "-u", UNIT, "--since", JENDELA,
             "--no-pager", "-o", "cat"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as e:
        print(f"WARN journalctl gagal: {e}")
        return []
    if r.returncode != 0:
        print("WARN journalctl returncode", r.returncode)
        return []
    baris = []
    for ln in r.stdout.splitlines():
        s = ln.strip()
        if s.startswith(PREFIX) and s not in baris:
            baris.append(s)
    return baris


def main() -> int:
    baris = ambil_baris()
    if not baris:
        print("SEHAT tidak ada alert untuk dikirim")
        return 0

    sig = hashlib.sha256("\n".join(baris).encode()).hexdigest()[:16]
    prev: dict = {}
    try:
        prev = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prev = {}

    now = time.time()
    if prev.get("sig") == sig and (now - float(prev.get("ts") or 0)) < REMIND_S:
        sisa = int((REMIND_S - (now - float(prev.get("ts") or 0))) / 60)
        print(f"LEWATI alert sama masih berlaku (kirim ulang {sisa} mnt lagi)")
        return 0

    sys.path.insert(0, NOTIFIER_SRC)
    try:
        from warroom_notifier.transport import transport_from_env
    except Exception as e:  # noqa: BLE001
        print(f"WARN gagal impor transport: {e}")
        return 0

    t = transport_from_env()
    pesan = "\n".join(baris)
    res = t.send(
        "War Room infra",
        pesan,
        "warning",
        {"unit": UNIT, "n": len(baris)},
    )
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(
            json.dumps({"sig": sig, "ts": now, "ok": res.ok,
                        "detail": res.detail, "n": len(baris)}),
            encoding="utf-8",
        )
    except OSError as e:
        print(f"WARN state tak tersimpan: {e}")

    print(f"KIRIM ok={res.ok} transport={getattr(t, 'name', '?')} detail={res.detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
