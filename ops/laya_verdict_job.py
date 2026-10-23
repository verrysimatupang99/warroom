"""Job terjadwal: hitung verdict Laya di PROSES TERPISAH, tulis ke cache.

Dijalankan oleh systemd timer (mis. tiap 60 detik). Tujuannya mengeluarkan
inferensi model 421M dari proses API:

- cold start model ~30 detik, warm ~1,5-2,2 detik
- RSS ~1 GB

Di dalam proses API, biaya itu membekukan endpoint lain dan melewati timeout
WebRequest EA (3 detik). Dengan job ini, endpoint `/forex/levels` hanya membaca
berkas JSON (mikrodetik), dan bila verdict basi/tidak ada maka gerbang menolak
(fail-closed).

Pemakaian:
    .venv/bin/python ops/laya_verdict_job.py
    .venv/bin/python ops/laya_verdict_job.py --ttl 180
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/core/src"))

from warroom_core.forex import laya_verdict  # noqa: E402
from warroom_core.forex.engine import (  # noqa: E402
    calculate_indicators,
    fetch_klines_direct,
)

log = logging.getLogger("laya_verdict_job")

PERTANYAAN = {
    "verdict": {
        "type": "choice",
        "instructions": (
            "Apakah kondisi pasar saat ini aman untuk eksekusi scalping XAUUSD "
            "dengan arah {side} pada sesi {session}?"
        ),
        "criteria": {
            "EXECUTE": (
                "Momentum jelas searah, spread wajar, bukan zona fakeout atau "
                "sideways mati"
            ),
            "SKIP": (
                "Pasar rawan sweep lanjutan, choppy tanpa volume, mengarah melawan "
                "posisi, atau ada spike ekstrem"
            ),
        },
    }
}


def sesi_sekarang() -> str:
    """Sama dengan logika MultiSessionLayaScalperStrategy.get_current_session()."""
    jam = datetime.now(UTC).hour
    if 0 <= jam < 7:
        return "ASIA"
    if 7 <= jam < 12:
        return "LONDON"
    return "NEW_YORK"


def nilai_satu_arah(evaluator: Any, state: dict[str, Any]) -> dict[str, Any]:
    """Jalankan satu inferensi, kembalikan ringkasan yang aman disimpan."""
    try:
        hasil = evaluator.invoke(state)
    except Exception as exc:  # noqa: BLE001
        log.warning("inferensi gagal untuk %s: %s", state.get("side"), exc)
        return {"choice": "", "confidence": 0.0, "error": f"{type(exc).__name__}: {exc}"}

    verdict = (hasil or {}).get("verdict") or {}
    pilihan = str(verdict.get("choice") or "").upper()
    prob = verdict.get("probabilities") or {}
    peluang = prob.get("EXECUTE")
    if peluang is None:
        peluang = verdict.get("answer_confidence")
    try:
        keyakinan = float(peluang) if peluang is not None else 0.0
    except (TypeError, ValueError):
        keyakinan = 0.0
    return {"choice": pilihan, "confidence": round(keyakinan, 4)}


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--ttl", type=int, default=laya_verdict.DEFAULT_TTL_SEC)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    candles = await fetch_klines_direct(args.symbol, interval="5m", range_period="1d")
    if not candles or len(candles) < 15:
        log.error("data candle tidak cukup (%s) — verdict TIDAK ditulis", len(candles or []))
        return 2

    ind = calculate_indicators(candles)
    sesi = sesi_sekarang()
    harga = ind["price"]

    try:
        import laya
    except Exception as exc:  # noqa: BLE001
        log.error("paket laya tidak tersedia: %s — verdict TIDAK ditulis", exc)
        return 3

    evaluator = laya.LayaEvaluator(questions=PERTANYAAN)
    verdicts: dict[str, Any] = {}
    for side in ("LONG", "SHORT"):
        state = {
            "symbol": args.symbol.upper(),
            "side": side,
            "session": sesi,
            "price": harga,
            "atr": ind["atr14"],
            "setup": f"{sesi} regime check",
        }
        verdicts[side] = nilai_satu_arah(evaluator, state)
        log.info("%s -> %s", side, verdicts[side])

    jalur = laya_verdict.write_verdict(
        {
            "session": sesi,
            "symbol": args.symbol.upper(),
            "price": harga,
            "atr": ind["atr14"],
            "trend": ind["trend_m5"],
            "ttl_sec": args.ttl,
            "engine": "convaiinnovations/laya",
            "verdicts": verdicts,
        }
    )
    log.info("verdict ditulis ke %s", jalur)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
