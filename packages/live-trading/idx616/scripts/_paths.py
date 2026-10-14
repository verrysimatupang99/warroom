"""Path portabel untuk mesin IDX 616 versi lokal (War Room).

Dulu seluruh path di-hardcode ke /home/ubuntu (Tencent). Modul ini memusatkan
letak state/cache/log/data supaya skrip yang sama bisa jalan di sini tanpa
mengubah apa pun di Tencent. Semua bisa ditimpa lewat env (IDX616_ROOT).
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("IDX616_ROOT", "/home/admin/live-trading"))
STATE = Path(os.environ.get("IDX616_STATE", str(ROOT / "state")))
SCRIPTS = Path(__file__).resolve().parent
DATA = SCRIPTS.parent / "data"
CACHE_ARJUM = ROOT / "index-cache" / "arjum"
LOGS_ARJUM = ROOT / "logs" / "arjum"
LEDGER_DB = STATE / "idx616_signal_ledger.db"
DRIFT_JSON = STATE / "idx616_drift.json"
REGIME_JSON = STATE / "idx616_regime.json"
ARJUM_TRADES_DB = STATE / "arjum_trades.db"

for _d in (STATE, DATA, CACHE_ARJUM, LOGS_ARJUM):
    _d.mkdir(parents=True, exist_ok=True)
