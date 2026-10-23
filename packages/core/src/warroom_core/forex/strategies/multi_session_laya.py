"""Strategi Multi-Session Precision Scalper XAUUSD + Laya AI Decision Judge (PNP Strategy 3).

Fitur Utama:
1. Multi-Session Logic: Asia (Mean Reversion), London (Judas Sweep), New York (Trend Momentum).
2. Tight Stop-Loss (~$1.80 - $2.50) dengan Asymmetric RRR minimal 1:1.6 s/d 1:3.0.
3. Evaluasi Laya AI Decision Judge (convaiinnovations/laya) sebelum sinyal dikirim ke MT5 Exness.
4. Mendukung Lot 0.10, Buffered Breakeven (+1.2R), Partial TP (+1.0R), dan Dynamic Trailing Stop.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from .base import BaseStrategy

log = logging.getLogger("warroom_core.forex.strategies.multi_session_laya")


class MultiSessionLayaScalperStrategy(BaseStrategy):
    """Strategi Scalping Presisi Multi-Sesi dengan Hakim Keputusan Laya AI."""

    def __init__(
        self,
        lot_size: float = 0.10,
        enable_laya: bool = True,
        min_rrr: float = 1.6,
        max_sl_points: float = 3.0,
        laya_min_confidence: float = 0.60,
    ):
        super().__init__(name="Multi-Session Laya Precision Scalper", timeframe="5m", rrr_min=min_rrr)
        self.lot_size = lot_size
        self.enable_laya = enable_laya
        self.max_sl_points = max_sl_points
        self.laya_min_confidence = laya_min_confidence
        self._laya_loaded = False
        self._init_laya()

    def _init_laya(self):
        try:
            import laya
            self._laya = laya
            # Evaluator dibangun sekali di init (bukan per sinyal): memuat model
            # butuh ~10-20 detik pada panggilan pertama, jadi tidak boleh masuk
            # jalur panas. Bila model tidak tersedia, Laya ditandai nonaktif dan
            # strategi tetap jalan memakai baseline.
            self._evaluator = laya.LayaEvaluator(
                questions={
                    "verdict": {
                        "type": "choice",
                        "instructions": (
                            "Apakah kondisi pasar saat ini aman untuk eksekusi "
                            "scalping XAUUSD?"
                        ),
                        "criteria": {
                            "EXECUTE": (
                                "Momentum jelas, spread wajar, bukan zona fakeout "
                                "/ sideways mati"
                            ),
                            "SKIP": (
                                "Pasar rawan sweep lanjutan, choppy tanpa volume, "
                                "atau ada spike ekstrim"
                            ),
                        },
                    }
                }
            )
            self._laya_loaded = True
            log.info("Laya AI Decision Judge aktif di MultiSessionLayaScalperStrategy")
        except Exception as exc:
            log.warning("Laya belum dapat diinisialisasi: %s", exc)
            self._evaluator = None
            self._laya_loaded = False

    def get_current_session(self) -> str:
        """Tentukan sesi pasar aktif berdasarkan jam UTC saat ini.
        - Asia: 00:00 - 06:00 UTC (07:00 - 13:00 WIB)
        - London: 07:00 - 12:00 UTC (14:00 - 19:00 WIB)
        - New York: 12:00 - 20:00 UTC (19:00 - 03:00 WIB)
        """
        now_utc = datetime.now(UTC)
        hour = now_utc.hour
        if 0 <= hour < 7:
            return "ASIA"
        elif 7 <= hour < 12:
            return "LONDON"
        else:
            return "NEW_YORK"

    def evaluate_laya(self, market_state: dict[str, Any]) -> tuple[bool, float, str]:
        """Evaluasi kondisi setup scalping via Laya Model.

        Mengembalikan (layak_eksekusi, keyakinan, alasan). Bila Laya tidak aktif
        atau inferensi gagal, keputusan jatuh ke baseline dan ditandai di alasan
        supaya tidak pernah terlihat seperti verdict model.
        """
        if not self.enable_laya or not self._laya_loaded or self._evaluator is None:
            # Fallback jika Laya dinonaktifkan: loloskan dengan baseline rule
            return True, 0.85, "Laya AI Passthrough (Offline/Bypass)"

        try:
            hasil = self._evaluator.invoke(market_state)
            verdict = (hasil or {}).get("verdict") or {}
            pilihan = str(verdict.get("choice") or "").upper()
            prob = verdict.get("probabilities") or {}
            peluang = prob.get("EXECUTE")
            if peluang is None:
                peluang = verdict.get("answer_confidence")

            if pilihan not in ("EXECUTE", "SKIP"):
                return True, 0.0, f"Laya tanpa verdict dikenali ({pilihan or 'kosong'})"

            # min_confidence sengaja konservatif: Laya nyata bisa mengembalikan
            # EXECUTE dengan peluang ~0.57 (nyaris tebakan). Di bawah ambang ini
            # sinyal diperlakukan tidak aman, bukan diloloskan diam-diam.
            keyakinan = float(peluang) if peluang is not None else 0.0
            aman = pilihan == "EXECUTE" and keyakinan >= self.laya_min_confidence
            alasan = (
                f"Laya {pilihan} p={keyakinan:.3f} "
                f"(ambang {self.laya_min_confidence:.2f}) side={market_state.get('side')} "
                f"sesi={market_state.get('session')}"
            )
            return aman, keyakinan, alasan
        except Exception as exc:
            log.warning("Laya evaluation error: %s", exc)
            # Fail-open ke baseline: Laya adalah penyaring tambahan, bukan satu-satunya
            # gerbang. Kegagalan model tidak boleh membekukan strategi, tetapi alasannya
            # harus jujur menyebut bahwa Laya tidak dipakai.
            return True, 0.0, f"Laya error, jatuh ke baseline: {exc}"

    def evaluate(self, market_data: dict[str, Any]) -> dict[str, Any] | None:
        price = market_data.get("price", 0.0)
        ema9 = market_data.get("ema9", 0.0)
        ema21 = market_data.get("ema21", 0.0)
        atr14 = market_data.get("atr14", 3.0)
        candles = market_data.get("candles", [])

        if price <= 0 or ema9 <= 0 or len(candles) < 15:
            return None

        session = self.get_current_session()

        # Dynamic Stop Loss ketat: 1.2x ATR, dibatasi maksimal self.max_sl_points ($2.50 - $3.00)
        risk = round(min(max(atr14 * 1.1, 1.8), self.max_sl_points), 2)
        reward = round(risk * self.rrr_min, 2)  # RRR Asimetris tebal (min 1.8R)

        side = None
        setup_name = ""

        # Hitung High & Low dari 12 candle M5 terakhir (1 jam terakhir) untuk deteksi Liquidity Sweep
        recent_high = max([c.get("high", price) for c in candles[-12:]]) if candles else price + atr14
        recent_low = min([c.get("low", price) for c in candles[-12:]]) if candles else price - atr14

        # Skenario 1: Sesi Asia (Mean Reversion M5)
        if session == "ASIA":
            if price > ema9 and (price - ema9) > (atr14 * 0.8):
                side = "SHORT"
                setup_name = "Asia Range Top Reversal"
            elif price < ema9 and (ema9 - price) > (atr14 * 0.8):
                side = "LONG"
                setup_name = "Asia Range Bottom Rebound"

        # Skenario 2: Sesi London (Judas Sweep & Liquidity Reversal)
        elif session == "LONDON":
            # Jika harga sempat sweep recent_high lalu ditutup kembali di bawah EMA9 -> Bearish Judas Sweep
            if price < ema9 and (recent_high - price) >= (atr14 * 0.6):
                side = "SHORT"
                setup_name = "London Judas Liquidity Sweep (Bearish Rejection)"
            # Jika harga sempat sweep recent_low lalu mantul kembali ke atas EMA9 -> Bullish Judas Sweep
            elif price > ema9 and (price - recent_low) >= (atr14 * 0.6):
                side = "LONG"
                setup_name = "London Judas Liquidity Sweep (Bullish Spring)"
            elif ema9 >= ema21 and price >= ema9:
                side = "LONG"
                setup_name = "London Open Bullish Momentum"
            elif ema9 <= ema21 and price <= ema9:
                side = "SHORT"
                setup_name = "London Open Bearish Breakdown"

        # Skenario 3: Sesi New York (FVG Retest & Momentum Expansion)
        else:
            if price >= ema9 and ema9 >= ema21:
                side = "LONG"
                setup_name = "New York Trend Continuation (M5 Breakout)"
            elif price <= ema9 and ema9 <= ema21:
                side = "SHORT"
                setup_name = "New York Trend Continuation (M5 Breakdown)"

        if not side:
            return None

        # Evaluasi Laya AI
        market_state = {
            "symbol": "XAUUSD",
            "side": side,
            "session": session,
            "price": price,
            "atr": atr14,
            "setup": setup_name,
        }
        is_safe, confidence, laya_reason = self.evaluate_laya(market_state)

        if not is_safe:
            log.info("Sinyal ditolak oleh Laya: %s", laya_reason)
            return None

        if side == "LONG":
            entry = price
            sl = round(entry - risk, 2)
            tp1 = round(entry + reward, 2)
            tp2 = round(entry + (reward * 1.8), 2)
        else:
            entry = price
            sl = round(entry + risk, 2)
            tp1 = round(entry - reward, 2)
            tp2 = round(entry - (reward * 1.8), 2)

        return {
            "side": side,
            "entry": entry,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "risk": risk,
            "reward": reward,
            "lot": self.lot_size,
            "session": session,
            "reason": f"[{session}] {setup_name} | {laya_reason}",
            "confidence": confidence,
            "strategy": self.name,
        }
