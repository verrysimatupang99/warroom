#!/usr/bin/env python3
"""Watcher alert paper bot (webdock) — kirim Telegram saat bot buka/tutup posisi.

Co-located dengan paper bot (webdock). Membaca events.jsonl yang ditulis paper
bot, mengirim event BARU ke Telegram HQ via Bot API langsung (token di
telegram.env). State posisi terakhir terkirim disimpan agar tidak spam.

Dijalankan systemd user timer (webdock) tiap 5 menit.
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

EVENTS = Path("/var/lib/warroom/paper-config/events.jsonl")
STATE = Path("/home/admin/.config/warroom/paper-alert-state.json")
TG_ENV = Path("/home/admin/.config/warroom/telegram.env")


def _muat_tg() -> tuple[str, str, str | None]:
    token = chat = thread = ""
    if TG_ENV.exists():
        for line in TG_ENV.read_text().splitlines():
            if line.startswith("TG_BOT_TOKEN="):
                token = line.split("=", 1)[1].strip()
            elif line.startswith("TG_CHAT_ID="):
                chat = line.split("=", 1)[1].strip()
            elif line.startswith("TG_THREAD_ID="):
                thread = line.split("=", 1)[1].strip()
    return token, chat, thread or None


def _muat_state() -> int:
    if STATE.exists():
        try:
            return int(json.loads(STATE.read_text()).get("terakhir", 0))
        except (json.JSONDecodeError, ValueError, OSError):
            pass
    return 0


def _simpan_state(n: int) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"terakhir": n}))


def _kirim(token: str, chat: str, thread: str | None, teks: str) -> bool:
    payload: dict[str, object] = {"chat_id": chat, "text": teks, "parse_mode": "HTML"}
    if thread:
        payload["message_thread_id"] = int(thread)
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception as e:  # noqa: BLE001
        print(f"kirim gagal: {e}")
        return False


def _format(ev: dict) -> str:
    if ev.get("tipe") == "buka":
        return (
            f"🟢 PAPER BOT — BUKA {ev.get('arah', '').upper()} {ev.get('simbol')}\n"
            f"• Entry: {ev.get('entry')}\n"
            f"• SL: {ev.get('sl')} | TP: {ev.get('tp')}\n"
            f"• Strategi: {ev.get('config')}"
        )
    emoji = "🟢" if (ev.get("hasil_r") or 0) > 0 else "🔴"
    return (
        f"{emoji} PAPER BOT — TUTUP {ev.get('arah', '').upper()} {ev.get('simbol')}\n"
        f"• Exit: {ev.get('exit')} ({ev.get('alasan')})\n"
        f"• Hasil: {ev.get('hasil_r'):+.2f}R (${ev.get('pnl_usd'):+.2f})\n"
        f"• Entry: {ev.get('entry')} | Strategi: {ev.get('config')}"
    )


def main() -> int:
    token, chat, thread = _muat_tg()
    if not token or not chat:
        print("kredensial telegram tidak lengkap")
        return 0
    if not EVENTS.exists():
        print("belum ada events")
        return 0

    baris = EVENTS.read_text().strip().splitlines()
    terakhir = _muat_state()
    terkirim = 0
    for i in range(terakhir, len(baris)):
        if not baris[i].strip():
            continue
        try:
            ev = json.loads(baris[i])
        except json.JSONDecodeError:
            continue
        if _kirim(token, chat, thread, _format(ev)):
            terkirim += 1
            terakhir = i + 1
    _simpan_state(terakhir)
    print(f"{terkirim} alert terkirim (posisi state: {terakhir}/{len(baris)})")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
