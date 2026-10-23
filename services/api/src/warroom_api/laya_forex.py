"""Middleware keputusan forex berbasis Laya AI (server-side).

Peran modul ini: menggantikan `laya_sentinel.py` yang selama ini hanya menyetel
string tetap ("HEALTHY", confidence 0.92) tanpa memanggil model apa pun.

Input yang diolah:
1. **Data mentah MT5** — dari telemetri EA (`/api/v1/tencent/mt5/telemetry`):
   balance, equity, floating PnL, posisi terbuka, spread.
2. **Sinyal level War Room** — dari `/api/v1/tencent/forex/levels`: side, entry, sl,
   tp1, atr, trend.

Keduanya dirangkum menjadi satu dokumen pendek lalu dinilai Laya dengan pertanyaan
terstruktur. Keluaran: verdict EXECUTE / SKIP beserta probabilitasnya.

Prinsip kejujuran yang dikodekan di sini:
- Bila model tidak tersedia, kembalikan `tersedia: False` dengan alasan — JANGAN
  mengarang "HEALTHY" atau confidence.
- Bila verdict tidak dikenali, jangan dianggap lolos.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

log = logging.getLogger(__name__)

# Ambang keyakinan: di bawah ini sinyal diperlakukan tidak aman (SKIP).
MIN_CONFIDENCE_DEFAULT = 0.60

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


class LayaForexMiddleware:
    """Pembungkus tipis di atas laya.LayaEvaluator dengan pola lazy-load.

    Evaluator dibangun sekali (memuat model 421M butuh waktu), lalu dipakai ulang.
    Thread-safe karena endpoint FastAPI bisa memanggil bersamaan.
    """

    def __init__(
        self, *, min_confidence: float = MIN_CONFIDENCE_DEFAULT, timeout_s: float = 120.0
    ) -> None:
        self.min_confidence = min_confidence
        self.timeout_s = timeout_s
        self._evaluator: Any = None
        self._tersedia = False
        self._alasan = "belum diinisialisasi"
        self._lock = threading.Lock()
        self._terakhir: dict[str, Any] = {}

    # -- inisialisasi -------------------------------------------------------
    def _pastikan_evaluator(self) -> bool:
        if self._evaluator is not None:
            return True
        with self._lock:
            if self._evaluator is not None:
                return True
            try:
                import laya

                self._evaluator = laya.LayaEvaluator(questions=PERTANYAAN)
                self._tersedia = True
                self._alasan = "model termuat"
                log.info("Laya forex middleware aktif (model termuat)")
                return True
            except Exception as exc:  # noqa: BLE001
                self._tersedia = False
                self._alasan = f"laya tidak tersedia: {type(exc).__name__}: {exc}"
                log.warning("Laya middleware gagal init: %s", exc)
                return False

    # -- penyusunan konteks -------------------------------------------------
    @staticmethod
    def susun_konteks(sinyal: dict[str, Any], telemetri: dict[str, Any]) -> dict[str, Any]:
        """Rangkum sinyal + telemetri jadi satu objek untuk model.

        Hanya memuat angka yang benar-benar ada; field yang tidak diketahui
        dibiarkan None supaya model tidak membaca nol palsu.
        """
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

    # -- penilaian ----------------------------------------------------------
    def nilai(self, sinyal: dict[str, Any], telemetri: dict[str, Any]) -> dict[str, Any]:
        """Kembalikan verdict atas satu sinyal. Tidak pernah mengarang hasil.

        CATATAN PENTING (insiden 23 Okt 2026): memanggil model langsung di dalam
        endpoint async membuat SELURUH API membeku - `/api/v1/build` pun balas 000
        selama inferensi berjalan (muat model 421M + torch memblokir event loop).
        Karena itu pemanggil async WAJIB memakai `nilai_async()` yang menjalankannya
        di thread terpisah. Fungsi ini tetap sinkron untuk dipakai dari thread/CLI.
        """
        konteks = self.susun_konteks(sinyal, telemetri)
        dasar = {
            "tersedia": False,
            "engine": "convaiinnovations/laya",
            "min_confidence": self.min_confidence,
            "konteks": konteks,
            "ts": int(time.time()),
        }

        if not self._pastikan_evaluator():
            return {**dasar, "alasan": self._alasan, "verdict": "TAK_DIKETAHUI"}

        try:
            hasil = self._evaluator.invoke(konteks)
        except Exception as exc:  # noqa: BLE001
            return {
                **dasar,
                "alasan": f"inferensi gagal: {type(exc).__name__}: {exc}",
                "verdict": "TAK_DIKETAHUI",
            }

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
            layak = pilihan == "EXECUTE" and keyakinan_f >= self.min_confidence
            keluaran = {
                **dasar,
                "tersedia": True,
                "verdict": pilihan,
                "layak_eksekusi": layak,
                "keyakinan": round(keyakinan_f, 4),
                "probabilitas": prob,
                "alasan": (
                    f"Laya {pilihan} p={keyakinan_f:.3f} "
                    f"(ambang {self.min_confidence:.2f})"
                ),
            }
        self._terakhir = keluaran
        return keluaran

    async def nilai_async(
        self, sinyal: dict[str, Any], telemetri: dict[str, Any]
    ) -> dict[str, Any]:
        """Versi async AMAN: inferensi dijalankan di proses TERPISAH (subprocess).

        Riwayat (23 Okt 2026): menjalankan model di dalam proses API terbukti
        membekukan seluruh layanan — `/api/v1/build` balas 000, listen backlog penuh,
        RSS melonjak ke 1,1 GB. `asyncio.to_thread` TIDAK menolong karena bebannya
        CPU+memori, bukan I/O.

        Karena itu inferensi dipanggil sebagai subprocess dengan batas waktu. Bila
        model lambat/gagal, API tetap hidup dan endpoint menjawab "tidak tersedia"
        alih-alih menggantung.
        """
        import asyncio
        import json
        import sys
        from pathlib import Path

        skrip = Path(__file__).with_name("laya_cli.py")
        muatan = json.dumps({"sinyal": sinyal, "telemetri": telemetri})
        py = sys.executable
        try:
            proc = await asyncio.create_subprocess_exec(
                py,
                str(skrip),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(
                proc.communicate(muatan.encode("utf-8")), timeout=self.timeout_s
            )
        except (TimeoutError, asyncio.TimeoutError):
            return {
                "tersedia": False,
                "verdict": "TAK_DIKETAHUI",
                "engine": "convaiinnovations/laya",
                "alasan": f"inferensi melebihi {self.timeout_s}s (dibatalkan agar API tetap hidup)",
                "konteks": self.susun_konteks(sinyal, telemetri),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "tersedia": False,
                "verdict": "TAK_DIKETAHUI",
                "engine": "convaiinnovations/laya",
                "alasan": f"gagal menjalankan inferensi: {type(exc).__name__}: {exc}",
                "konteks": self.susun_konteks(sinyal, telemetri),
            }

        if proc.returncode != 0:
            return {
                "tersedia": False,
                "verdict": "TAK_DIKETAHUI",
                "engine": "convaiinnovations/laya",
                "alasan": f"proses inferensi gagal (kode {proc.returncode}): "
                f"{err.decode('utf-8', 'replace')[-300:]}",
                "konteks": self.susun_konteks(sinyal, telemetri),
            }

        try:
            hasil = json.loads(out.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            return {
                "tersedia": False,
                "verdict": "TAK_DIKETAHUI",
                "alasan": f"keluaran inferensi tidak valid: {exc}",
                "konteks": self.susun_konteks(sinyal, telemetri),
            }
        self._terakhir = hasil
        return hasil

    def status(self) -> dict[str, Any]:
        return {
            "tersedia": self._tersedia,
            "alasan": self._alasan,
            "min_confidence": self.min_confidence,
            "terakhir": self._terakhir or None,
            "engine": "convaiinnovations/laya",
        }


middleware = LayaForexMiddleware()
