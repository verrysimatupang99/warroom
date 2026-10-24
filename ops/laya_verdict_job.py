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
import os
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
            "Apakah kondisi pasar DAN kondisi akun saat ini aman untuk eksekusi "
            "scalping XAUUSD dengan arah {side} pada sesi {session}? "
            "Pertimbangkan juga balance, equity, floating PnL, dan jumlah posisi "
            "yang sudah terbuka."
        ),
        "criteria": {
            "EXECUTE": (
                "Momentum jelas searah, spread wajar, bukan zona fakeout atau "
                "sideways mati, DAN risiko terhadap ukuran balance masih wajar "
                "dengan tidak ada posisi terbuka yang menahan risiko"
            ),
            "SKIP": (
                "Pasar rawan sweep lanjutan, choppy tanpa volume, mengarah melawan "
                "posisi, ada spike ekstrem, ATAU kondisi akun menunjukkan tekanan "
                "(floating loss besar dibanding balance, margin tipis, sudah ada "
                "posisi terbuka)"
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


async def ambil_akun(timeout_s: float = 5.0) -> dict[str, Any]:
    """Ambil telemetri akun dari API War Room. Kegagalan tidak fatal."""
    url = os.environ.get(
        "WARROOM_MT5_STATUS_URL", "http://127.0.0.1:8800/api/v1/tencent/mt5/status"
    )
    try:
        import httpx

        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            log.warning("telemetri akun HTTP %s", resp.status_code)
            return {}
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except Exception as exc:  # noqa: BLE001
        log.warning("gagal ambil telemetri akun: %s", exc)
        return {}


def susun_konteks_akun(akun: dict[str, Any]) -> dict[str, Any]:
    """Ringkas telemetri menjadi konteks risiko yang bisa dibaca model.

    Sengaja hanya meneruskan angka yang benar-benar ada. Field yang tidak diketahui
    dibiarkan None agar model tidak membaca nol palsu sebagai "akun kosong".
    """
    terhubung = bool(akun.get("connected"))
    balance = akun.get("balance")
    equity = akun.get("equity")
    floating = akun.get("floating_pnl")
    posisi = akun.get("positions")
    n_posisi = len(posisi) if isinstance(posisi, list) else None

    # Risiko mengambang relatif terhadap balance: bila floating loss besar
    # dibanding balance, menambah posisi baru memperburuk tekanan margin.
    floating_pct: float | None = None
    if isinstance(floating, (int, float)) and isinstance(balance, (int, float)) and balance:
        floating_pct = round(floating / balance * 100.0, 2)

    return {
        "akun_tersedia": terhubung,
        "balance_usd": balance,
        "equity_usd": equity,
        "floating_pnl_usd": floating,
        "floating_pct_balance": floating_pct,
        "posisi_terbuka": n_posisi,
        "free_margin_usd": akun.get("free_margin"),
        "win_rate_pct": akun.get("win_rate_pct"),
        "net_pnl_usd": akun.get("net_pnl_usd"),
    }


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

    # R5: konteks akun. Tanpa ini Laya hanya menilai "pasar aman", bukan
    # "trade ini pantas untuk ukuran akun". Risiko relatif terhadap balance adalah
    # bagian dari keputusan, dan EA tidak mengirimkannya ke model mana pun.
    akun = await ambil_akun()
    konteks_akun = susun_konteks_akun(akun)
    if konteks_akun["akun_tersedia"]:
        log.info("konteks akun: %s", konteks_akun)
    else:
        log.warning(
            "telemetri akun tidak tersedia — Laya menilai pasar saja (tanpa konteks akun)"
        )

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
            **konteks_akun,
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
            "akun": konteks_akun,
            "verdicts": verdicts,
        }
    )
    log.info("verdict ditulis ke %s", jalur)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
