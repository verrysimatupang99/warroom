import asyncio
import logging
import threading

import uvicorn
from api import app
from engine import main as run_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("main_runner")


def start_api():
    log.info("Memulai REST API & Web Dashboard di http://127.0.0.1:8088...")
    uvicorn.run(app, host="127.0.0.1", port=8088, log_level="warning")


if __name__ == "__main__":
    # Jalankan API di thread background
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()

    # Jalankan listener Telethon di main thread asyncio event loop
    log.info("Memulai Telethon Telegram Listener...")
    asyncio.run(run_engine())
