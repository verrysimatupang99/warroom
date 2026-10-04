"""Paper executor — order virtual dengan harga nyata.

Tujuannya bukan "pura-pura trading", tapi **menguji jalur keputusan yang sama**
dengan yang nanti dipakai live: sizing dari risk gate, SL/TP yang sama, ledger
yang sama. Yang berbeda hanya satu baris: order tidak dikirim ke bursa.

Ledger memakai skema yang sama dengan warisan Tencent
(``signal_id, pair, direction, closed_at, status, r, note, source``) supaya angka
lama dan baru bisa dibandingkan langsung.
"""

from __future__ import annotations

import datetime as dt
import json
import secrets
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..config import Settings


def _now_wib() -> str:
    return (dt.datetime.now(dt.UTC) + dt.timedelta(hours=7)).isoformat(timespec="seconds")


def new_signal_id() -> str:
    return f"#SIG{secrets.token_hex(4).upper()}"


def compute_r(direction: str, entry: float, stop: float, exit_price: float) -> float:
    """R = jarak tempuh dibagi jarak risiko awal. Arah short dicerminkan."""
    risk = (entry - stop) if direction.upper() == "LONG" else (stop - entry)
    if risk <= 0:
        raise ValueError("stop harus di sisi yang benar (long: stop < entry, short: stop > entry)")
    move = (exit_price - entry) if direction.upper() == "LONG" else (entry - exit_price)
    return round(move / risk, 3)


@dataclass
class PaperPosition:
    signal_id: str
    pair: str
    direction: str
    entry: float
    stop: float
    tp1: float
    tp2: float
    size_usd: float
    opened_at: str = field(default_factory=_now_wib)
    status: str = "open"
    source: str = "paper"
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PaperBroker:
    def __init__(self, settings: Settings, venue: str = "crypto") -> None:
        from live_trading.guards import SpendLimitGuard, TradingCircuitBreaker

        self.belanja = SpendLimitGuard()
        self.pemutus = TradingCircuitBreaker()
        self.s = settings
        self.venue = (venue or "crypto").lower()

    # ------------------------------------------------------------------ berkas
    @property
    def positions_path(self) -> Path:
        return self.s.venue_positions_path(self.venue)

    @property
    def ledger_path(self) -> Path:
        return self.s.venue_ledger_path(self.venue)

    def positions(self) -> list[PaperPosition]:
        if not self.positions_path.is_file():
            return []
        try:
            raw = json.loads(self.positions_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return [PaperPosition(**p) for p in raw.get("positions", [])]

    def _save(self, positions: list[PaperPosition]) -> None:
        self.s.state_dir.mkdir(parents=True, exist_ok=True)
        payload = {"updated_at": _now_wib(), "positions": [p.to_dict() for p in positions]}
        self.positions_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _append_ledger(self, record: dict[str, Any]) -> None:
        self.s.state_dir.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------ aksi
    def open_position(
        self,
        *,
        pair: str,
        direction: str,
        entry: float,
        stop: float,
        tp1: float,
        tp2: float,
        size_usd: float,
        source: str = "paper",
        note: str = "",
    ) -> PaperPosition:
        pos = PaperPosition(
            signal_id=new_signal_id(),
            pair=pair,
            direction=direction.upper(),
            entry=entry,
            stop=stop,
            tp1=tp1,
            tp2=tp2,
            size_usd=size_usd,
            source=f"paper-{self.venue}" if source == "paper" else source,
            note=note,
        )
        compute_r(pos.direction, entry, stop, entry)  # validasi sisi stop
        if not self.pemutus.boleh_jalan():
            raise RuntimeError(f"paper halt: {self.pemutus.alasan()}")
        self.belanja.check_and_record(float(size_usd))
        positions = self.positions()
        positions.append(pos)
        self._save(positions)
        return pos

    def close_position(
        self, signal_id: str, exit_price: float, status: str, note: str = ""
    ) -> dict[str, Any]:
        positions = self.positions()
        target = next((p for p in positions if p.signal_id == signal_id), None)
        if target is None:
            raise KeyError(f"posisi {signal_id} tidak ditemukan")

        r = compute_r(target.direction, target.entry, target.stop, exit_price)
        record = {
            "signal_id": target.signal_id,
            "pair": target.pair,
            "direction": target.direction,
            "closed_at": _now_wib(),
            "status": status,
            "r": r,
            "note": note or f"{status} @ {exit_price}",
            "source": target.source,
        }
        self._append_ledger(record)
        self._save([p for p in positions if p.signal_id != signal_id])
        return record

    def evaluate(self, prices: dict[str, float]) -> list[dict[str, Any]]:
        """Periksa SL/TP terhadap harga sekarang; tutup yang kena.

        TP1 kena → stop digeser ke entry (break-even) dan status jadi
        ``tp1_hit_runner``; sisa posisi dibiarkan jalan ke TP2.
        """
        closed: list[dict[str, Any]] = []
        positions = self.positions()
        keep: list[PaperPosition] = []

        for p in positions:
            price = prices.get(p.pair)
            if price is None:
                keep.append(p)
                continue
            long = p.direction == "LONG"

            hit_sl = price <= p.stop if long else price >= p.stop
            hit_tp2 = price >= p.tp2 if long else price <= p.tp2
            hit_tp1 = price >= p.tp1 if long else price <= p.tp1

            if hit_sl:
                closed.append(self.close_position(p.signal_id, p.stop, "closed_SL"))
            elif hit_tp2:
                closed.append(self.close_position(p.signal_id, p.tp2, "closed_TP2"))
            elif hit_tp1 and p.status == "open":
                p.status = "tp1_hit_runner"
                p.stop = p.entry  # break-even, bukan trailing agresif
                keep.append(p)
            else:
                keep.append(p)

        if len(keep) != len(positions):
            self._save(keep)
        elif any(p.status == "tp1_hit_runner" for p in keep):
            self._save(keep)
        return closed
