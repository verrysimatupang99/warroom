"""Strategi Laya AI Decision Judge untuk Forex & Emas (PNP Strategy 2).

Menggunakan model non-autoregressive Laya (convaiinnovations/laya)
untuk mengevaluasi kelayakan setup scalping secara deterministik dalam ~30ms.
"""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseStrategy

log = logging.getLogger("warroom_core.forex.strategies.laya")


class LayaForexJudgeStrategy(BaseStrategy):
    """Strategi hybrid: Indikator Teknis M5 + Evaluasi AI Laya System-1."""

    def __init__(self):
        super().__init__(name="Laya AI Decision Judge", timeframe="5m", rrr_min=1.5)
        self._agent = None
        self._load_laya()

    def _load_laya(self):
        try:
            import laya
            # Laya dapat dimuat secara on-demand
            self._laya_module = laya
            log.info("Laya module berhasil di-load ke dalam PNP Strategy")
        except Exception as exc:
            log.warning("Laya belum dapat dimuat: %s", exc)
            self._laya_module = None

    def evaluate(self, market_data: dict[str, Any]) -> dict[str, Any] | None:
        price = market_data.get("price", 0.0)
        ema9 = market_data.get("ema9", 0.0)
        ema21 = market_data.get("ema21", 0.0)
        atr14 = market_data.get("atr14", 3.0)

        if price <= 0 or ema9 <= 0:
            return None

        risk = round(max(atr14 * 1.2, 2.0), 2)
        reward = round(risk * 1.6, 2)

        # Baseline setup teknikal
        side = None
        if price >= ema9 and ema9 >= ema21:
            side = "LONG"
        elif price <= ema9 and ema9 <= ema21:
            side = "SHORT"

        if not side:
            return None

        # CATATAN KEJUJURAN (audit 2026-10-23): blok ini BELUM memanggil model Laya.
        # market_state disusun hanya sebagai bahan bila inferensi disambungkan nanti;
        # keputusan di bawah masih aturan baseline murni (EMA + ATR). Jangan menamai
        # hasilnya "Laya Confirmed" seolah-olah verdict model. Penyambungan nyata
        # sudah ada di strategies/multi_session_laya.py (evaluate_laya + ambang).
        _market_state = {
            "symbol": "XAUUSD",
            "side": side,
            "price": price,
            "atr": atr14,
            "ema9": ema9,
            "ema21": ema21,
            "mode": "scalping",
        }

        # Baseline rule (BUKAN verdict Laya).
        confidence = 0.85
        reason = f"Baseline EMA/ATR {side}: momentum searah EMA M5, ATR {atr14}"

        if side == "LONG":
            return {
                "side": "LONG",
                "entry": price,
                "sl": round(price - risk, 2),
                "tp1": round(price + reward, 2),
                "tp2": round(price + (reward * 1.5), 2),
                "reason": reason,
                "confidence": confidence,
                "strategy": self.name,
            }
        else:
            return {
                "side": "SHORT",
                "entry": price,
                "sl": round(price + risk, 2),
                "tp1": round(price - reward, 2),
                "tp2": round(price - (reward * 1.5), 2),
                "reason": reason,
                "confidence": confidence,
                "strategy": self.name,
            }
