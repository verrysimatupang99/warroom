"""Batas harian per strategi — status ``benched`` saat terlampaui (owner, 16 Okt 2026).

Dua batas per strategi: jumlah trade yang boleh dibuka per hari dan total fee yang boleh
dikeluarkan per hari. Saat salah satu terlampaui, strategi statusnya ``benched`` (duduk di
bangku) sampai hari berikutnya (reset harian WIB) — satu strategi yang kebablasan tidak
menghabiskan dompet sementara yang lain menunggu, dan perbandingan antar-strategi tetap
adil.

State ditulis ke ``state/bench_harian.json`` (berkas BARU — tidak menyentuh ledger/
positions yang sudah ada). Pembacaan gagal dianggap belum ada trade; ``boleh_entry`` tetap
menghormati batas begitu state terbaca. Tanpa I/O jaringan.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = ["BatasStrategi", "BenchHarian"]

# Batas default per strategi (kebijakan; owner bisa lewat Settings/env).
DEFAULT_MAKS_TRADE_HARIAN = 5
DEFAULT_MAKS_FEE_HARIAN_USD = 2.0


@dataclass(frozen=True)
class BatasStrategi:
    maks_trade: int = DEFAULT_MAKS_TRADE_HARIAN
    maks_fee_usd: float = DEFAULT_MAKS_FEE_HARIAN_USD


class BenchHarian:
    """Penjaga batas trade + fee harian per strategi, dengan reset harian WIB."""

    def __init__(
        self,
        state_path: Path,
        *,
        batas: BatasStrategi | None = None,
        now: Callable[[], dt.datetime] | None = None,
    ) -> None:
        self.path = state_path
        self.batas = batas or BatasStrategi()
        # Jam WIB (offset +07:00 jujur) — hari berubah saat WIB berganti hari.
        self._now = now or (lambda: dt.datetime.now(dt.UTC) + dt.timedelta(hours=7))

    def hari(self) -> str:
        """Tanggal WIB (YYYY-MM-DD) saat ini."""
        return self._hari()

    def _hari(self) -> str:
        return self._now().strftime("%Y-%m-%d")

    def _baca(self) -> dict[str, Any]:
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return d if isinstance(d, dict) else {}

    def _tulis(self, d: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def _entri(self, nama: str) -> dict[str, Any]:
        hari = self._baca().get(self._hari(), {})
        e = hari.get(nama)
        return e if isinstance(e, dict) else {"trade": 0, "fee_usd": 0.0}

    def status(self, nama: str) -> str:
        e = self._entri(nama)
        if int(e.get("trade", 0)) >= self.batas.maks_trade:
            return "benched"
        if float(e.get("fee_usd", 0.0)) >= self.batas.maks_fee_usd:
            return "benched"
        return "aktif"

    def boleh_entry(self, nama: str) -> tuple[bool, str]:
        """True bila strategi masih boleh buka trade hari ini; alasannya selalu jelas."""
        e = self._entri(nama)
        trade = int(e.get("trade", 0))
        fee = float(e.get("fee_usd", 0.0))
        if trade >= self.batas.maks_trade:
            return False, f"benched: {nama} {trade}/{self.batas.maks_trade} trade hari ini"
        if fee >= self.batas.maks_fee_usd:
            return False, f"benched: {nama} fee ${fee:.2f} ≥ ${self.batas.maks_fee_usd:.2f} hari ini"
        return True, "aktif"

    def catat(self, nama: str, *, fee_usd: float = 0.0) -> dict[str, Any]:
        """Catat satu trade terbuka; kembalikan entri terbaru (untuk log/observasi)."""
        d = self._baca()
        hari = d.setdefault(self._hari(), {})
        e = hari.get(nama) if isinstance(hari.get(nama), dict) else {"trade": 0, "fee_usd": 0.0}
        e["trade"] = int(e.get("trade", 0)) + 1
        e["fee_usd"] = round(float(e.get("fee_usd", 0.0)) + fee_usd, 6)
        hari[nama] = e
        self._tulis(d)
        return e

    def ringkas(self) -> dict[str, Any]:
        """Status semua strategi yang tercatat hari ini (untuk panel/CLI)."""
        hari = self._baca().get(self._hari(), {})
        return {
            nama: {
                "trade": int(e.get("trade", 0)) if isinstance(e, dict) else 0,
                "fee_usd": round(float(e.get("fee_usd", 0.0)), 6) if isinstance(e, dict) else 0.0,
                "status": self.status(nama),
            }
            for nama, e in hari.items()
            if isinstance(e, dict)
        }
