"""Konfigurasi terpusat — satu-satunya tempat path & konstanta boleh didefinisikan.

Kenapa ini ada: script legacy (diwarisi dari Hermes Tencent) meng-hardcode
``~/.hermes/...`` di dalam modul. Itu bikin kode tidak bisa dipindah mesin dan
tidak bisa dites. Semua path sekarang turunan dari :class:`Settings` dan bisa
di-override lewat env var ``LT_*``.

Nilai sensitif (API key) TIDAK pernah di sini — hanya *path* ke file-nya.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Setelan runtime, dibaca dari env (prefix ``LT_``) atau ``<home>/.env``."""

    model_config = SettingsConfigDict(
        env_prefix="LT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Lokasi proyek ---------------------------------------------------
    home: Path = Field(default=Path.home() / "live-trading")

    # --- Endpoint data (semua publik, tanpa key) -------------------------
    binance_fapi: str = "https://fapi.binance.com"
    binance_dapi: str = "https://dapi.binance.com"
    mexc_contract: str = "https://contract.mexc.com"
    coingecko: str = "https://api.coingecko.com/api/v3"
    feargreed: str = "https://api.alternative.me"
    tradingview_scanner: str = "https://scanner.tradingview.com"

    # --- IDX / Arjum (butuh key) -----------------------------------------
    arjum_base: str = "https://stock.arjum.com"
    arjum_daily_quota: int = 6000
    arjum_min_remaining: int = 500

    # --- Batas risiko (dipakai risk gate, bukan oleh strategi) -----------
    paper: bool = True
    equity_usd: float = 100.0
    daily_loss_limit_r: float = 3.0
    max_concurrent_positions: int = 3
    risk_per_trade_pct: float = 1.0
    # Batas notional terhadap ekuitas. 1.0 = tanpa leverage (paling aman).
    # Dinaikkan secara sadar lewat LT_MAX_LEVERAGE kalau memang mau pakai perp.
    max_leverage: float = 1.0

    # --- Dashboard --------------------------------------------------------
    dashboard_port: int = 8799
    snapshot_ttl_s: int = 600

    # --- Kompatibilitas script legacy ------------------------------------
    # Kalau True, path legacy (``~/.hermes/...``) dipakai apa adanya.
    # Dipakai HANYA untuk menjalankan script warisan sebelum dimigrasi.
    legacy_hermes: bool = False
    legacy_hermes_root: Path = Field(default=Path.home() / ".hermes")

    # --- Turunan path ----------------------------------------------------
    @computed_field
    @property
    def secrets_dir(self) -> Path:
        return self.home / "secrets"

    @computed_field
    @property
    def state_dir(self) -> Path:
        return self.home / "state"

    @computed_field
    @property
    def journal_dir(self) -> Path:
        return self.home / "journal"

    @computed_field
    @property
    def baselines_dir(self) -> Path:
        return self.home / "baselines"

    @computed_field
    @property
    def logs_dir(self) -> Path:
        return self.home / "logs"

    @computed_field
    @property
    def arjum_key_path(self) -> Path:
        """File berisi API key Arjum (mode 600). Nilainya tidak pernah dibaca di sini."""
        return self.secrets_dir / "arjum_api_key"

    @computed_field
    @property
    def watchlist_path(self) -> Path:
        return self.state_dir / "crypto-watchlist.json"

    @computed_field
    @property
    def ledger_path(self) -> Path:
        return self.state_dir / "crypto_equity.jsonl"

    @computed_field
    @property
    def executor_lock_path(self) -> Path:
        """Kunci 'satu executor per akun' — mencegah dua mesin mengeksekusi bersamaan."""
        return self.state_dir / "executor.lock"

    # --- Partisi Multi-Venue (5 Pasar) -----------------------------------
    venue_equity_usd: float = 200.0

    def venue_ledger_path(self, venue: str = "crypto") -> Path:
        v = (venue or "crypto").lower()
        if v == "crypto":
            return self.ledger_path
        return self.state_dir / f"{v}_equity.jsonl"

    def venue_positions_path(self, venue: str = "crypto") -> Path:
        v = (venue or "crypto").lower()
        if v == "crypto":
            return self.state_dir / "paper_positions.json"
        return self.state_dir / f"paper_positions_{v}.json"

    # --- Operasi ---------------------------------------------------------
    def ensure_dirs(self) -> None:
        for d in (self.secrets_dir, self.state_dir, self.journal_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)

    def legacy_path(self, *parts: str) -> Path:
        """Path relatif terhadap root legacy (``~/.hermes``) — jembatan migrasi."""
        return self.legacy_hermes_root.joinpath(*parts)


def get_settings(**overrides: object) -> Settings:
    """Muat setelan; overrides dipakai di test."""
    return Settings(**overrides)  # type: ignore[arg-type]
