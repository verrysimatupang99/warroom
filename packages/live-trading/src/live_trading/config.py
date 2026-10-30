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
    okx_api: str = "https://www.okx.com"
    coingecko: str = "https://api.coingecko.com/api/v3"
    feargreed: str = "https://api.alternative.me"
    tradingview_scanner: str = "https://scanner.tradingview.com"

    # --- IDX / Arjum (butuh key) -----------------------------------------
    arjum_base: str = "https://stock.arjum.com"
    # Kuota akun SUPPORTER: 1.000 gratis + 5.003 dari plan = 6.003 req/hari (dashboard
    # Arjum, 5 Okt 2026). Nilai ini hanya dipakai sebagai DEFAULT saat header API tidak ada;
    # angka sebenarnya selalu diambil dari `x-ratelimit-limit` (dulu tertulis 1000 di berkas
    # state dan itu salah — terbaca sebagai "limit 1000" padahal akunnya 6.003).
    arjum_daily_quota: int = 6003
    # Ambang berhenti = margin keamanan, BUKAN target konsumsi. 150 dari 6.003 ≈ 2,5%:
    # cukup untuk menghentikan sweep yang kebablasan tanpa mematikan IDX selama seharian.
    # Nilai lama 500 pernah mengunci IDX padahal sisa 370 (37% kuota) masih banyak.
    arjum_min_remaining: int = 150

    # --- Batas risiko (dipakai risk gate, bukan oleh strategi) -----------
    paper: bool = True
    equity_usd: float = 100.0
    daily_loss_limit_r: float = 3.0
    max_concurrent_positions: int = 3
    risk_per_trade_pct: float = 1.0
    # Batas notional terhadap ekuitas. 1.0 = tanpa leverage (paling aman).
    # Dinaikkan secara sadar lewat LT_MAX_LEVERAGE kalau memang mau pakai perp.
    max_leverage: float = 1.0
    # Rekomendasi agent-2 #9 (15 Okt, disetujui owner "gass semua"):
    # 1) batas korelasi — maks posisi SE-ARAH supaya tidak full-short saat BTC berbalik;
    # 2) filter rezim BTC — candidate berlawanan arah tren BTC 4h (EMA50) dilewati.
    maks_posisi_searah: int = 2
    btc_regime_filter: bool = True

    # --- Batas harian per strategi (status 'benched', 16 Okt 2026) -------------
    # Kebijakan owner: batasi jumlah trade dan total fee per strategi tiap hari supaya
    # satu strategi kebablasan tidak menghabiskan dompet. Melebihi → 'benched' sampai
    # hari berikutnya. Angka = titik mulai; owner bisa lewat env LT_BENCH_*.
    bench_max_trade_harian: int = 5
    bench_max_fee_harian_usd: float = 2.0

    # --- Strategi A: SMA harian (spec agent-2 §3, disetujui owner 16 Okt) -----
    # Semua angka = hipotesis awal; wajib lulus backtest 4 tahun + OOS (sudah,
    # lihat docs/blueprint/strategi-harian-backtest-20261016.md).
    harian_universe: str = "BTCUSDT,ETHUSDT,SOLUSDT"
    # Pemilihan parameter sesuai hasil backtest 4-tahun OOS 30% (16 Okt, docs/blueprint/
    # strategi-harian-backtest-20261016.json): SMA50+confirm1 OOS +21,3% (DD 40%)
    # vs SMA100 semua VARIAN OOS negatif — data menang atas default spec.
    harian_sma_n: int = 50
    harian_confirm_closes: int = 1
    harian_maks_bucket: float = 0.40      # maks 40% bucket per aset
    harian_min_trade_usd: float = 5.0
    # Batas mingguan & kill-switch drawdown (spec §2):
    harian_mingguan_loss_pct: float = 8.0
    harian_kill_dd_pct: float = 20.0
    harian_capat_stop_pct: float = 20.0   # catastrophic stop per posisi (opsional)

    # --- Dashboard --------------------------------------------------------
    dashboard_port: int = 8799
    snapshot_ttl_s: int = 600

    # --- Kompatibilitas script legacy ------------------------------------
    # Kalau True, path legacy (``~/.hermes/...``) dipakai apa adanya.
    # Dipakai HANYA untuk menjalankan script warisan sebelum dimigrasi.
    legacy_hermes: bool = False
    legacy_hermes_root: Path = Field(default=Path.home() / ".hermes")

    def config_fingerprint(self) -> str:
        """Versi konfigurasi strategi/risiko: berubah bila parameter yang relevan berubah.

        Bukan versi kode (itu dari build/commit); ini sidik parameter yang membuat
        satu rangkaian sinyal berbeda dari yang lain. Jurnal memakainya untuk
        memisahkan performa antar versi, bukan mencampur semuanya.
        """
        import hashlib
        import json

        kunci = (
            "daily_loss_limit_r",
            "max_concurrent_positions",
            "risk_per_trade_pct",
            "max_leverage",
            "maks_posisi_searah",
            "btc_regime_filter",
            "bench_max_trade_harian",
            "bench_max_fee_harian_usd",
            "harian_sma_n",
            "harian_confirm_closes",
            "harian_maks_bucket",
            "harian_mingguan_loss_pct",
            "harian_kill_dd_pct",
            "harian_capat_stop_pct",
        )
        data = {k: getattr(self, k) for k in kunci}
        return hashlib.sha256(
            json.dumps(data, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:12]

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
