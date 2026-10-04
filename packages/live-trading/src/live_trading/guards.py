"""Penjaga otoritas uang: batas belanja + circuit breaker (fail-closed)."""

from __future__ import annotations

import time


class SpendLimitError(Exception):
    pass


class SpendLimitGuard:
    """Batas per-tx dan harian. Independen dari model/strategi."""

    def __init__(self, max_single: float = 500.0, max_daily: float = 2000.0) -> None:
        self.max_single = max_single
        self.max_daily = max_daily
        self._belanja: list[tuple[float, float]] = []

    def check_and_record(self, usd: float, sekarang: float | None = None) -> None:
        if usd > self.max_single:
            raise SpendLimitError(f"1 tx ${usd} > batas ${self.max_single}")
        now = time.time() if sekarang is None else sekarang
        sehari = [v for t, v in self._belanja if now - t < 86400]
        if sum(sehari) + usd > self.max_daily:
            raise SpendLimitError(f"harian ${sum(sehari) + usd} > batas ${self.max_daily}")
        self._belanja = [(t, v) for t, v in self._belanja if now - t < 86400]
        self._belanja.append((now, usd))


class TradingCircuitBreaker:
    """Halt setelah 3 rugi beruntun atau rugi harian >5% ekuitas acuan."""

    def __init__(self, max_beruntun: int = 3, max_rugi_harian_pct: float = 0.05) -> None:
        self.max_beruntun = max_beruntun
        self.max_rugi_harian_pct = max_rugi_harian_pct
        self.beruntun = 0
        self._halt_alasan = ""

    def catat_hasil(self, pnl: float) -> None:
        if pnl < 0:
            self.beruntun += 1
        else:
            self.beruntun = 0
        if self.beruntun >= self.max_beruntun:
            self._halt_alasan = f"halt: {self.beruntun} rugi beruntun"

    def cek_ekuitas(self, nilai: float, acuan: float) -> None:
        if acuan > 0 and (nilai - acuan) / acuan < -self.max_rugi_harian_pct:
            self._halt_alasan = f"halt: rugi harian {(nilai - acuan) / acuan:.1%}"

    def boleh_jalan(self) -> bool:
        return not self._halt_alasan

    def alasan(self) -> str:
        return self._halt_alasan
