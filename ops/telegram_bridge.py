"""Jembatan feed Telegram → War Room (jalan di webdock via cron).

Menarik pesan terbaru dari channel terverifikasi milik pemilik (sesi Telethon
milik akun pemilik, read-only), mem-parsing sinyal dengan REGEX KETAT,
dan mengirim yang cocok sebagai fakta `signal` status `kandidat` lewat
`POST /api/v1/sinyal/telegram`.

Tanpa AI, tanpa tebakan: pesan yang tidak cocok pola dilewati diam-diam.
Tidak ada sinyal → tidak ada fakta → tidak ada klaim palsu.

Env yang dibaca dari /etc/warroom/tg-feed/ (600):
  trading_session.session  sesi Telethon (disalin dari instabox testing)
  cookie                   sid sesi user layanan `feed-telegram` (operator)

State: $LT_HOME/state/tg_feed_seen.json  {channel_id: last_msg_id}
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

RUMAH = Path("/etc/warroom/tg-feed")
SESI = str(RUMAH / "trading_session")
COOKIE = (RUMAH / "cookie").read_text().strip()
_ENV: dict[str, str] = {}
for baris in (RUMAH / "env").read_text().splitlines():
    if "=" in baris and not baris.startswith("#"):
        k, v = baris.split("=", 1)
        _ENV[k.strip()] = v.strip()
API_ID = int(_ENV.get("TG_API_ID", "0"))
API_HASH = _ENV.get("TG_API_HASH", "")
API = "https://0xgunsl1ng3r.xyz/api/v1/sinyal/telegram"
KANALS = Path(__file__).with_name("tg_channels.json")
STATE = Path(os.environ.get("LT_HOME", "/home/admin/live-trading")) / "state" / "tg_feed_seen.json"

# Pola sinyal klasik: ARAH SIMBOL ... ENTRY/SL/TP (angka wajib min. 1 dari entry/sl)
POLA_KERAS = re.compile(
    r"(?i)\b(buy|sell|long|short|beli|jual)\b[\s\S]{0,60}?\b"
    r"(XAUUSD|GOLD|EURUSD|GBPUSD|USDJPY|BTCUSD|BTCUSDT|ETHUSDT|SOLUSDT|[A-Z]{4}\b)"
    r"[\s\S]{0,200}?\b(entry|@|open|sl|stop\s*loss|tp|take\s*profit)\b"
    r"[\s\S]{0,200}?(\d[\d.,]*)"
)
ANGKA = re.compile(r"(\d[\d.,]*)")


def angka(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def parse(teks: str, kategori: list[str]) -> dict | None:
    """Kembalikan dict sinyal atau None. Konservatif: tidak cocok → None."""
    t = (teks or "").strip()
    if len(t) < 15 or len(t) > 2000:
        return None
    m = POLA_KERAS.search(t)
    if not m:
        return None
    arah_kata = m.group(1).upper()
    arah = "LONG" if arah_kata in ("BUY", "LONG", "BELI") else "SHORT"
    simbol = m.group(2).upper()
    if simbol == "GOLD":
        simbol = "XAUUSD"
    ekor = t[m.end(3):m.end(3) + 200]
    # cari entry/sl/tp di sekitar kata kunci
    def ambil(kunci: str) -> float | None:
        mm = re.search(r"(?i)\b" + kunci + r"\b[^\d]{0,10}(\d[\d.,]*)", t)
        return angka(mm.group(1)) if mm else None
    entry = ambil(r"(?:entry|@|open)")
    sl = ambil(r"(?:sl|stop\s*loss)")
    tp1 = ambil(r"(?:tp1?|take\s*profit)")
    if entry is None and sl is None:
        return None
    if "saham" in [k.lower() for k in kategori] or (
        len(simbol) == 4 and simbol.isalpha()
    ):
        pasar = "idx"
    elif simbol in ("XAUUSD", "EURUSD", "GBPUSD", "USDJPY"):
        pasar = "forex"
    else:
        pasar = "crypto"
    return {"pasar": pasar, "simbol": simbol, "arah": arah,
            "entry": entry, "sl": sl, "tp1": tp1,
            "catatan": t[:300]}


def kirim(sinyal: dict, channel: str) -> bool:
    req = urllib.request.Request(
        API,
        data=json.dumps(sinyal).encode(),
        headers={"content-type": "application/json",
                 "Cookie": f"wr_session={COOKIE}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200
    except Exception as ex:  # noqa: BLE001 - dicatat pemanggil
        print(f"KIRIM-GAGAL {sinyal['simbol']}: {ex}", flush=True)
        return False


async def main() -> int:
    from telethon import TelegramClient

    if not API_ID or not API_HASH:
        print("TG_API_ID/HASH kosong di /etc/warroom/tg-feed/env")
        return 2

    try:
        semua = json.loads(KANALS.read_text())
    except FileNotFoundError:
        print("kanal belum ada");
        return 2
    kanals = [k for k in semua
              if k.get("terverifikasi") and k.get("id")]
    try:
        seen = json.loads(STATE.read_text()) if STATE.exists() else {}
    except json.JSONDecodeError:
        seen = {}
    sejak = datetime.now(UTC) - timedelta(hours=24)
    c = TelegramClient(SESI, API_ID, API_HASH)
    await c.connect()
    if not await c.is_user_authorized():
        print("SESI-TIDAK-VALID — perlu login ulang di testing")
        return 2
    cocok = terkirim = dilewati = 0
    for k in kanals:
        gid = k["id"]
        terakhir = seen.get(str(gid), 0)
        try:
            e = await c.get_entity(gid)
        except Exception as ex:
            print(f"LEWATI {k.get('title')}: {str(ex)[:80]}")
            continue
        maks = terakhir
        async for m in c.iter_messages(e, limit=40):
            if m.id <= terakhir or (m.date and m.date < sejak):
                continue
            maks = max(maks, m.id)
            s = parse(m.text or "", k.get("kategori", []))
            if not s:
                dilewati += 1
                continue
            cocok += 1
            s["catatan"] = f"[{k.get('title')}] {s['catatan']}"
            if kirim(s, str(k.get("title"))):
                terkirim += 1
        seen[str(gid)] = maks
    await c.disconnect()
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(seen))
    print(f"selesai: cocok={cocok} terkirim={terkirim} dilewati={dilewati}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
