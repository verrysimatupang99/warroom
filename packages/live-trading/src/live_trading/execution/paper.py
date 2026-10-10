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


def compute_be_stop(
    direction: str, entry: float, fee_buffer_pct: float = 0.001, total_bps: float | None = None
) -> float:
    """True Net Break-Even stop yang menutup biaya round-trip.

    ``total_bps`` (bila diberi) = biaya TERUKUR dari buku order (P2) — dipakai apa adanya.
    Tanpa itu, jatuh ke ``fee_buffer_pct`` lama (0,1% = asumsi fee taker OKX 0,05%×2).
    """
    pct = (total_bps / 10000.0) if total_bps is not None else fee_buffer_pct
    if direction.upper() == "LONG":
        return round(entry * (1.0 + pct), 8)
    return round(entry * (1.0 - pct), 8)


def _risk_init(direction: str, entry: float, stop_init: float) -> float:
    """Risiko awal posisi dari stop yang belum pernah digeser."""
    return (entry - stop_init) if direction.upper() == "LONG" else (stop_init - entry)


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
    stop_init: float = 0.0  # stop asli saat open; `stop` boleh digeser ke break-even
    # Biaya round-trip TERUKUR saat open (bps), dari buku order nyata (P2). None = tidak
    # terukur; evaluate() akan jatuh ke asumsi 0,1% lama.
    cost_bps: float | None = None
    opened_at: str = field(default_factory=_now_wib)
    status: str = "open"
    source: str = "paper"
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_r_exit(pos: PaperPosition, exit_price: float) -> float:
    """R untuk PENUTUPAN, tahan terhadap stop yang sudah digeser ke break-even.

    ``compute_r`` menolak stop di sisi yang salah — benar untuk validasi saat
    open, tapi salah untuk runner: setelah TP1 stop digeser ke entry / net
    break-even sehingga risikonya 0 atau negatif. Kondisi itu dulu membuat
    ``close_position`` melempar ValueError dan ``evaluate`` berhenti di tengah,
    sehingga runner tidak pernah bisa ditutup sama sekali.
    """
    risk = _risk_init(pos.direction, pos.entry, pos.stop_init or pos.stop)
    if risk <= 0:
        # Posisi lama tanpa stop_init yang sudah di-BE: exit break-even ≈ 0R.
        return 0.0
    move = (exit_price - pos.entry) if pos.direction == "LONG" else (pos.entry - exit_price)
    return round(move / risk, 3)


class PaperBroker:
    def __init__(self, settings: Settings, venue: str = "crypto") -> None:
        from live_trading.guards import SpendLimitGuard, TradingCircuitBreaker

        self.belanja = SpendLimitGuard()
        self.pemutus = TradingCircuitBreaker()
        self.s = settings
        self.venue = (venue or "crypto").lower()
        self.errors: list[str] = []

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
        tmp = self.positions_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.positions_path)

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
        cost_bps: float | None = None,
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
            stop_init=stop,
            cost_bps=cost_bps,
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

        r = compute_r_exit(target, exit_price)
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

    def evaluate(self, prices: dict[str, float], net_be: bool = False) -> list[dict[str, Any]]:
        """Periksa SL/TP terhadap harga sekarang; tutup yang kena.

        TP1 kena → stop digeser ke entry (atau True Net Break-Even bila net_be=True)
        dan status jadi ``tp1_hit_runner``; sisa posisi dibiarkan jalan ke TP2.

        Error pada SATU posisi dicatat ke ``self.errors`` dan posisinya tetap
        disimpan — evaluasi posisi lain tetap jalan.
        """
        closed: list[dict[str, Any]] = []
        self.errors = []
        positions = self.positions()
        keep: list[PaperPosition] = []

        for p in positions:
            price = prices.get(p.pair)
            if price is None:
                keep.append(p)
                continue
            try:
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
                    p.stop = (
                        compute_be_stop(p.direction, p.entry, total_bps=p.cost_bps)
                        if net_be
                        else p.entry
                    )
                    keep.append(p)
                else:
                    keep.append(p)
            except Exception as exc:  # noqa: BLE001 — satu posisi rusak tidak boleh mematikan evaluasi
                self.errors.append(f"{p.signal_id} {p.pair}: {type(exc).__name__}: {exc}")
                keep.append(p)
                continue

        if len(keep) != len(positions):
            self._save(keep)
        elif any(p.status == "tp1_hit_runner" for p in keep):
            self._save(keep)
        return closed
