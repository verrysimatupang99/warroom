"""Listener Telegram (Telethon) - menangkap sinyal trading dari channel/grup.

Kredensial (`TG_API_ID`, `TG_API_HASH`) WAJIB dari environment; unit gagal
start dengan pesan jelas bila kosong - lebih baik daripada diam-diam memakai
kredensial yang tidak ada. Sesi Telethon (`trading_session.session`) tetap
state runtime lokal dan tidak pernah di-commit.
"""

import asyncio
import logging
import os
import re

from db import init_db, insert_signal
from telethon import TelegramClient, events

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("tg_engine")


def _wajib_env(nama: str) -> str:
    """Rahasia Telegram hanya boleh datang dari environment, tidak pernah dari kode."""
    nilai = os.environ.get(nama, "").strip()
    if not nilai:
        raise RuntimeError(
            f"{nama} kosong. Isi /etc/warroom/tg-engine.env (mode 600) lalu restart unit; "
            "lihat services/tg-engine/README.md."
        )
    return nilai


def _wajib_int(nama: str) -> int:
    try:
        return int(_wajib_env(nama))
    except ValueError as exc:
        raise RuntimeError(f"{nama} harus angka (API_ID Telegram)") from exc


API_ID = _wajib_int("TG_API_ID")
API_HASH = _wajib_env("TG_API_HASH")
SESSION_NAME = "trading_session"

# Keyword matching rules
FOREX_KEYWORDS = [
    r"\bxauusd\b",
    r"\bgold\b",
    r"\bforex\b",
    r"\beurusd\b",
    r"\bgbpusd\b",
    r"\busdjpy\b",
    r"\bpips\b",
    r"\blot\b",
    r"\bcallisto\b",
    r"\border block\b",
    r"\bfvg\b",
    r"\bchoch\b",
    r"\bbreakeven\b",
    r"\bbep\b",
    r"\bsl plus\b",
    r"\btake profit\b",
    r"\bstop loss\b",
    r"\bscalping\b",
    r"\bbuy limit\b",
    r"\bsell limit\b",
    r"\bbuy now\b",
    r"\bsell now\b",
    r"\bustec\b",
    r"\bnas100\b",
    r"\bnasdaq\b",
    r"\bus100\b",
    r"\bndx\b",
    r"\bus30\b",
    r"\bdow\b",
]

SAHAM_KEYWORDS = [
    r"\bihsg\b",
    r"\bsaham\b",
    r"\bidx\b",
    r"\bbek\b",
    r"\bstockbit\b",
    r"\bbandarmologi\b",
    r"\bforeign flow\b",
    r"\bipo\b",
    r"\barb\b",
    r"\bara\b",
    r"\bbkpm\b",
    r"\blq45\b",
    r"\bidx30\b",
    r"\bbca\b",
    r"\bbbca\b",
    r"\bbbri\b",
    r"\bbmri\b",
    r"\bbdni\b",
    r"\btlkm\b",
    r"\basii\b",
    r"\bgoto\b",
    r"\bbren\b",
    r"\bcuang\b",
    r"\bdividen\b",
    r"\bbroker summary\b",
]

CRYPTO_KEYWORDS = [
    r"\bbtc\b",
    r"\bbitcoin\b",
    r"\beth\b",
    r"\bethereum\b",
    r"\bsol\b",
    r"\bsolana\b",
    r"\bcrypto\b",
    r"\bkripto\b",
    r"\baltcoin\b",
    r"\bbinance\b",
    r"\bbybit\b",
    r"\bfutures\b",
    r"\blong\b",
    r"\bshort\b",
    r"\bleverage\b",
    r"\bliquidation\b",
    r"\bairdrop\b",
    r"\bmemecoin\b",
    r"\bdex\b",
    r"\bpump\.fun\b",
    r"\btoken\b",
    r"\bfunding rate\b",
]

# Blacklist grup spam / obrolan random / bokep / judi yang ada di akun
BLACKLIST_CHATS = [
    "kaum hasrat",
    "anonymeet",
    "anonymous",
    "cari teman",
    "random chat",
    "viral",
    "boc1l",
    "bantuan jasa",
    "sexolah",
    "jual beli vps",
    "tiki4d",
    "dewacasino",
    "gaskeunbet",
    "game bocor",
    "starboy",
    "gudang138",
    "slot",
    "pemersatu",
    "gerbangwin",
    "racun shopee",
    "fjb kavling",
]

# Whitelist channel/grup trading resmi & channel prioritas user
WHITELIST_TRADING_CHATS = [
    "callisto",
    "fxm",
    "gold",
    "forex",
    "trader ndeso",
    "dio gold",
    "stockbit",
    "creative trader",
    "bandarsub",
    "saham",
    "akademikripto",
    "timothy ronald",
    "insider crypto",
    "nasahind",
    "yuk nabung",
    "mifx",
    "astra investasi",
    "malong",
    "saham sukses berkah",
    "sahamtalk",
    "ruangdegen",
    "formula_dsi",
    "dsi",
]

# Explicit channel category routing
CHANNEL_CATEGORY_MAP = {
    "malong": "FOREX",  # Malong Freemium / VIP Forex & Gold
    "saham sukses berkah": "SAHAM",  # Saham Sukses Berkah (IDX)
    "sahamtalk": "SAHAM",  # SahamTalk (IDX)
    "ruangdegen": "CRYPTO",  # RuangDegen (Crypto / Memecoins / Airdrops)
    "formula_dsi": "SAHAM",  # Formula DSI / Saham IDX
}


def is_blacklisted(channel_title: str) -> bool:
    t = channel_title.lower()
    return any(b in t for b in BLACKLIST_CHATS)


# Default: DM & bot dibuang. Sumber sinyal adalah channel/grup; memproses DM
# berarti pesan pribadi ikut diklasifikasi dan berpotensi tersimpan ke DB.
# Set TG_IZINKAN_DM=1 untuk memulihkan perilaku lama.
IZINKAN_DM = os.environ.get("TG_IZINKAN_DM", "").strip().lower() in {"1", "true", "ya"}


def boleh_diproses(*, is_private: bool, is_bot: bool) -> bool:
    """Gerbang pertama: apakah chat ini sumber sinyal yang sah?

    Dipanggil sebelum query database atau klasifikasi, supaya pesan DM tidak
    pernah menyentuh jalur penyimpanan.
    """
    if is_bot:
        return False
    if is_private and not IZINKAN_DM:
        return False
    return True


def classify_message(text: str, channel_title: str = "") -> str:
    combined = f"{channel_title} {text}".lower()

    # Priority 1: Direct channel match
    for ch_name, cat in CHANNEL_CATEGORY_MAP.items():
        if ch_name in channel_title.lower():
            # If text has specific keywords, allow overriding to more accurate sub-type
            if cat == "SAHAM" and any(re.search(kw, combined) for kw in FOREX_KEYWORDS):
                return "FOREX"
            if cat == "FOREX" and any(re.search(kw, combined) for kw in CRYPTO_KEYWORDS):
                return "CRYPTO"
            return cat

    score_forex = sum(1 for kw in FOREX_KEYWORDS if re.search(kw, combined))
    score_saham = sum(1 for kw in SAHAM_KEYWORDS if re.search(kw, combined))
    score_crypto = sum(1 for kw in CRYPTO_KEYWORDS if re.search(kw, combined))

    scores = [("FOREX", score_forex), ("SAHAM", score_saham), ("CRYPTO", score_crypto)]
    scores.sort(key=lambda x: x[1], reverse=True)

    if scores[0][1] > 0:
        return scores[0][0]

    # Check channel title hints
    if any(k in channel_title.lower() for k in ["fx", "gold", "xau", "callisto", "trader ndeso", "malong"]):
        return "FOREX"
    if any(
        k in channel_title.lower()
        for k in ["saham", "stock", "ihsg", "invest", "bandar", "rakyat", "berkah", "dsi"]
    ):
        return "SAHAM"
    if any(k in channel_title.lower() for k in ["crypto", "kripto", "airdrop", "ronald", "coin", "degen"]):
        return "CRYPTO"

    return "GENERAL"


async def main():
    init_db()
    log.info("Memulai Telegram Trading Listener 24/7 (Strict Trading Filter)...")

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        log.error("Sesi Telegram TIDAK terotorisasi! Harap verifikasi file session.")
        return

    me = await client.get_me()
    log.info("Telegram Client Berhasil Terhubung: %s (@%s) [ID: %s]", me.first_name, me.username, me.id)

    # Cache dialogs & entitas channel baru saat startup
    try:
        dialogs = await client.get_dialogs(limit=100)
        trading_channels = [d.title for d in dialogs if d.is_channel or d.is_group]
        log.info("Total %d dialog dimuat. Channel terdeteksi: %d", len(dialogs), len(trading_channels))
        for d in dialogs[:15]:
            log.info("  -> Terkoneksi ke dialog: [%s] (ID: %s)", getattr(d, "title", d.name), d.id)
    except Exception as e:
        log.warning("Gagal fetch initial dialogs: %s", e)

    @client.on(events.NewMessage)
    async def handler(event):
        try:
            # FILTER 0: hanya channel/grup. DM & bot dibuang sebelum I/O apa pun,
            # supaya pesan pribadi tidak pernah masuk klasifikasi/DB.
            # `get_sender()` hanya dipanggil untuk DM — di channel/grup tidak perlu.
            is_private = bool(getattr(event, "is_private", False))
            is_bot = is_private and bool(getattr(await event.get_sender(), "bot", False))
            if not boleh_diproses(is_private=is_private, is_bot=is_bot):
                return

            chat = await event.get_chat()
            channel_id = str(event.chat_id)
            channel_name = (
                getattr(chat, "title", None) or getattr(chat, "username", None) or f"User_{channel_id}"
            )

            message_text = event.message.message or ""
            if not message_text.strip():
                return

            # FILTER 1: Jangan simpan chat dari grup blacklist (bokep, slot, cari jodoh, random chat)
            if is_blacklisted(channel_name):
                return

            views = getattr(event.message, "views", 0) or 0
            forwards = getattr(event.message, "forwards", 0) or 0

            # Klasifikasi otomatis kategori
            category = classify_message(message_text, channel_name)

            # FILTER 2: HANYA SIMPAN JIKA TERBUKTI SINYAL TRADING (FOREX, SAHAM, CRYPTO)
            # Buang pesan GENERAL yang tidak ada hubungannya dengan trading
            is_whitelisted = any(w in channel_name.lower() for w in WHITELIST_TRADING_CHATS)
            if category == "GENERAL" and not is_whitelisted:
                return

            metadata = {
                "sender_id": getattr(event.message, "sender_id", None),
                "date": str(event.message.date),
                "is_channel": getattr(event, "is_channel", False),
                "is_group": getattr(event, "is_group", False),
                "post_author": getattr(event.message, "post_author", None),
            }

            sig_id = insert_signal(
                channel_id=channel_id,
                channel_name=channel_name,
                category=category,
                message_text=message_text,
                views=views,
                forwards=forwards,
                metadata=metadata,
            )
            log.info(
                "📥 [%s] Sinyal Valid #%d dari [%s]: %s...",
                category,
                sig_id,
                channel_name,
                message_text[:60].replace("\n", " "),
            )
        except Exception as e:
            log.error("Error processing incoming message: %s", e)

    log.info("Listening to incoming trading signals 24/7...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
