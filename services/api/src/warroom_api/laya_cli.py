"""Jalankan inferensi Laya di PROSES TERPISAH, lalu kembalikan verdict sebagai JSON.

Dipakai `laya_forex.LayaForexMiddleware.nilai_async()`.

Kenapa subprocess: memuat model 421M + torch menaikkan RSS ke ~1,1 GB dan membekukan
event loop FastAPI bila dijalankan di dalam proses API (terbukti 23 Okt 2026:
`/api/v1/build` balas 000, listen backlog penuh). Dengan proses terpisah, API tetap
hidup dan kegagalan model tidak menjatuhkan layanan.

Masukan (stdin): {"sinyal": {...}, "telemetri": {...}}
Keluaran (stdout): JSON verdict, atau JSON {"tersedia": false, "alasan": ...}
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

MIN_CONFIDENCE = 0.60

PERTANYAAN = {
    "verdict": {
        "type": "choice",
        "instructions": (
            "Berdasarkan ringkasan kondisi akun MT5 dan sinyal trading di atas, "
            "apakah sinyal ini layak dieksekusi sekarang?"
        ),
        "criteria": {
            "EXECUTE": (
                "Arah sinyal selaras dengan tren, risiko terhadap stop loss wajar "
                "untuk ukuran akun, dan tidak ada tanda bahaya pada posisi terbuka "
                "atau floating loss"
            ),
            "SKIP": (
                "Sinyal melawan tren, risiko terlalu besar untuk ukuran akun, "
                "ada posisi terbuka yang menahan risiko, atau kondisi akun "
                "menunjukkan tekanan (floating loss besar / margin tipis)"
            ),
        },
    }
}


def susun_konteks(sinyal: dict[str, Any], telemetri: dict[str, Any]) -> dict[str, Any]:
    levels = sinyal.get("levels") or {}
    return {
        "symbol": sinyal.get("symbol"),
        "sinyal_arah": sinyal.get("side") or levels.get("order_type"),
        "tren": sinyal.get("trend"),
        "entry": levels.get("entry"),
        "stop_loss": levels.get("sl"),
        "take_profit": levels.get("tp1"),
        "jarak_sl": levels.get("risk"),
        "atr": sinyal.get("atr"),
        "atr_pct": sinyal.get("atr_pct"),
        "akun_balance": telemetri.get("balance"),
        "akun_equity": telemetri.get("equity"),
        "floating_pnl": telemetri.get("floating_pnl"),
        "margin": telemetri.get("margin"),
        "free_margin": telemetri.get("free_margin"),
        "posisi_terbuka": len(telemetri.get("positions") or []),
        "menit_sejak_ea": telemetri.get("seconds_ago"),
    }


def main() -> int:
    mentah = sys.stdin.read()
    try:
        muatan = json.loads(mentah)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"tersedia": False, "alasan": f"masukan tidak valid: {exc}"}))
        return 0

    konteks = susun_konteks(muatan.get("sinyal") or {}, muatan.get("telemetri") or {})
    dasar = {
        "engine": "convaiinnovations/laya",
        "min_confidence": MIN_CONFIDENCE,
        "konteks": konteks,
        "ts": int(time.time()),
        "tersedia": False,
    }

    try:
        import laya
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {
                    **dasar,
                    "verdict": "TAK_DIKETAHUI",
                    "alasan": f"paket laya tidak tersedia: {type(exc).__name__}: {exc}",
                }
            )
        )
        return 0

    try:
        ev = laya.LayaEvaluator(questions=PERTANYAAN)
        hasil = ev.invoke(konteks)
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {
                    **dasar,
                    "verdict": "TAK_DIKETAHUI",
                    "alasan": f"inferensi gagal: {type(exc).__name__}: {exc}",
                }
            )
        )
        return 0

    verdict = (hasil or {}).get("verdict") or {}
    pilihan = str(verdict.get("choice") or "").upper()
    prob = verdict.get("probabilities") or {}
    keyakinan = prob.get("EXECUTE")
    if keyakinan is None:
        keyakinan = verdict.get("answer_confidence")
    try:
        keyakinan_f = float(keyakinan) if keyakinan is not None else 0.0
    except (TypeError, ValueError):
        keyakinan_f = 0.0

    if pilihan not in ("EXECUTE", "SKIP"):
        keluaran = {
            **dasar,
            "verdict": "TAK_DIKETAHUI",
            "alasan": f"verdict tidak dikenali: {pilihan or 'kosong'}",
            "probabilitas": prob,
        }
    else:
        layak = pilihan == "EXECUTE" and keyakinan_f >= MIN_CONFIDENCE
        keluaran = {
            **dasar,
            "tersedia": True,
            "verdict": pilihan,
            "layak_eksekusi": layak,
            "keyakinan": round(keyakinan_f, 4),
            "probabilitas": prob,
            "alasan": f"Laya {pilihan} p={keyakinan_f:.3f} (ambang {MIN_CONFIDENCE:.2f})",
        }

    print(json.dumps(keluaran))
    return 0


if __name__ == "__main__":
    sys.exit(main())
