"""Unified paper-signal contract and shared risk gate.

This is intentionally market-neutral and paper-only. Market adapters and
strategies can depend on the shape without gaining execution authority.

Batas peran (jangan tertukar dengan `market_signal.py`):
- `signal.py` (INI)      : kontrak *generik* untuk satu sinyal paper — `MarketData`,
  `Signal`, `RiskPolicy`, `evaluate_risk`. Dipakai paper-engine, strategy,
  adapters, notifier. Market-neutral, tak tahu pasar apa pun.
- `market_signal.py`     : "sinyal terbaik PER PASAR" untuk Home/UI (`SinyalPasar`,
  `best_signal_per_market`) — lapisan di ATAS kontrak ini.
- `verdict.py`           : verdict kanonik per pasar (`market_verdict`), lapisan
  di atas `market_signal.py`.

Jadi ketiganya BUKAN duplikasi: tiga lapisan berbeda (kontrak → sinyal-UI →
verdict). Lihat docs/adr/penamaan-kode-bahasa-inggris.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

__all__ = ["Decision", "MarketData", "RiskPolicy", "Signal", "evaluate_risk"]
Direction = Literal["long", "short", "yes", "no", "monitor"]
Mode = Literal["paper", "live"]


@dataclass(frozen=True, slots=True)
class Signal:
    signal_id: str
    market: str
    venue: str
    instrument: str
    strategy: str
    direction: Direction
    entry: float
    stop: float | None
    target: float | None
    risk_reward: float | None
    confidence: float | None
    created_at: datetime
    expires_at: datetime
    freshness_s: float
    reason: str
    mode: Mode = "paper"

    def __post_init__(self) -> None:
        if not self.signal_id.strip() or not self.market.strip() or not self.instrument.strip():
            raise ValueError("signal identity wajib diisi")
        if self.mode != "paper":
            raise ValueError("unified signal hanya boleh paper; live memakai gate terpisah")
        if self.direction not in {"long", "short", "yes", "no", "monitor"}:
            raise ValueError("direction tidak valid")
        if self.entry <= 0 or self.freshness_s < 0 or self.expires_at <= self.created_at:
            raise ValueError("signal timing/price tidak valid")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence harus 0..1")


@dataclass(frozen=True, slots=True)
class MarketData:
    market: str
    venue: str
    instrument: str
    observed_at: datetime
    price: float
    spread_bps: float | None
    liquidity_usd: float | None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RiskPolicy:
    """Batas risiko konservatif untuk gate paper.

    Alasan nilai default (relatif terhadap ``risk_usd=50``):
    - ``max_position_usd=50`` (1x risiko): satu posisi tak boleh melebihi
      risiko satu trade — book paper default datar, tanpa scaling.
    - ``max_open_exposure_usd=200`` (4x risiko): maksimal ~4 posisi
      full-risk yang terbuka bersamaan.
    - ``max_daily_loss_usd=150`` (3x risiko): rem harian setelah kira-kira
      tiga kali loss penuh.
    - ``max_correlated_exposure_usd=100`` (2x risiko): keranjang berkorelasi
      dibatasi lebih ketat daripada total eksposur terbuka.

    ``None`` tidak lagi diterima: batas ``None`` dulu berarti "tanpa batas"
    (unlimited) dan itu berbahaya — konfigurasi kosong/lolos-diam-diam harus
    gagal eksplisit di konstruksi, bukan di evaluasi.
    """
    max_age_s: float = 120.0
    max_spread_bps: float = 50.0
    min_liquidity_usd: float = 0.0
    risk_usd: float = 50.0
    kill_switch: bool = False
    max_daily_loss_usd: float = 150.0
    daily_loss_usd: float = 0.0
    max_open_exposure_usd: float = 200.0
    open_exposure_usd: float = 0.0
    max_correlated_exposure_usd: float = 100.0
    correlated_exposure_usd: float = 0.0
    max_position_usd: float = 50.0
    fee_bps: float = 5.0
    slippage_bps: float = 5.0
    def __post_init__(self) -> None:
        for name in (
            "risk_usd",
            "max_daily_loss_usd",
            "max_open_exposure_usd",
            "max_correlated_exposure_usd",
            "max_position_usd",
        ):
            value = getattr(self, name)
            if value is None:
                raise ValueError(f"{name} wajib eksplisit (None berarti unlimited — ditolak)")
            if value <= 0:
                raise ValueError(f"{name} harus > 0, dapat {value!r}")


@dataclass(frozen=True, slots=True)
class Decision:
    allowed: bool
    reason: str
    size_usd: float | None = None


def evaluate_risk(
    signal: Signal,
    data: MarketData,
    policy: RiskPolicy,
    *,
    now: datetime | None = None,
) -> Decision:
    """Pure shared paper risk gate. No order, file, or network side effect."""
    t = now or datetime.now(UTC)
    if policy.kill_switch:
        return Decision(False, "kill_switch")
    if policy.daily_loss_usd >= policy.max_daily_loss_usd:
        return Decision(False, "daily_loss_limit")
    if signal.mode != "paper":
        return Decision(False, "live_mode_blocked")
    if data.market != signal.market or data.instrument != signal.instrument:
        return Decision(False, "market_data_mismatch")
    if (t - data.observed_at).total_seconds() > policy.max_age_s:
        return Decision(False, "stale_data")
    if signal.expires_at <= t:
        return Decision(False, "signal_expired")
    if data.spread_bps is not None and data.spread_bps > policy.max_spread_bps:
        return Decision(False, "spread_too_wide")
    if data.liquidity_usd is not None and data.liquidity_usd < policy.min_liquidity_usd:
        return Decision(False, "liquidity_too_low")
    if policy.open_exposure_usd + policy.risk_usd > policy.max_open_exposure_usd:
        return Decision(False, "open_exposure_limit")
    if policy.correlated_exposure_usd + policy.risk_usd > policy.max_correlated_exposure_usd:
        return Decision(False, "correlated_exposure_limit")
    if policy.risk_usd > policy.max_position_usd:
        return Decision(False, "position_size_limit")
    return Decision(True, "allowed", policy.risk_usd)
