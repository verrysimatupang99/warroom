"""Skema data platform War Room (Postgres 16) — `03-backend.md` §5.

Prinsip yang dikodekan di sini:

- **`facts`**: satu nilai = satu baris, berversi, wajib punya `source`, `observed_at`, `ttl_s`.
  Tidak ada angka di UI/AI tanpa `fact_id` (ADR-005).
- **`events`**: append-only. Tidak ada alur kode yang boleh UPDATE/DELETE tabel ini.
- **Uang nyata ≠ paper ≠ warisan**: dipisahkan lewat `trades.venue`/`trades.mode`
  (bukan lewat kolom boolean yang mudah lupa).
- Semua waktu `timestamptz` (UTC); batas zona tampilan urusan UI.

Uang disimpan sebagai `numeric(20,8)`, bukan float — pembulatan float pada saldo adalah
kelas bug yang tidak perlu.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

__all__ = ["Base", "Fact", "Event", "Verdict", "Trade", "Strategy", "Parameter", "Proposal",
           "LLMCall", "Prompt", "Alert", "Service", "Heartbeat", "User", "Session", "AuditLog",
           "Dataset", "ResearchRun", "ResearchRecord", "FrozenSplit", "Job", "Grant"]

Money = Numeric(20, 8)


class Base(DeclarativeBase):
    """Basis deklaratif. Semua tabel memakai skema publik."""


class Fact(Base):
    """Nilai tunggal berversi. Kunci: (kind, key, observed_at)."""

    __tablename__ = "facts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(160), nullable=False)
    value_json: Mapped[Any] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(String(160), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ttl_s: Mapped[int] = mapped_column(Integer, nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("kind", "key", "observed_at", name="uq_facts_kind_key_observed"),
        Index("ix_facts_kind_key_observed_at", "kind", "key", "observed_at"),
        Index("ix_facts_observed_at", "observed_at"),
    )


class Event(Base):
    """Log kejadian append-only. `fact_ids` menautkan bukti."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(80), nullable=False, default="system")
    payload_json: Mapped[Any] = mapped_column(JSONB, nullable=False, default=dict)
    fact_ids: Mapped[Any] = mapped_column(JSONB, nullable=False, default=list)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_events_type_created_at", "type", "created_at"),
        Index("ix_events_created_at", "created_at"),
    )


class Verdict(Base):
    """Hasil gate per subjek/aturan — keluaran `warroom_core.gate.evaluate`."""

    __tablename__ = "verdicts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String(160), nullable=False)
    rule: Mapped[str] = mapped_column(String(120), nullable=False)
    n: Mapped[int] = mapped_column(Integer, nullable=False)
    win: Mapped[int] = mapped_column(Integer, nullable=False)
    be: Mapped[float] = mapped_column(Float, nullable=False)
    ci_low: Mapped[float] = mapped_column(Float, nullable=False)
    ci_high: Mapped[float] = mapped_column(Float, nullable=False)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)  # lolos|gagal|insufficient
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    required_n: Mapped[int | None] = mapped_column(Integer)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False, default="gate/0.1.0")
    split: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    label: Mapped[str] = mapped_column(String(16), nullable=False, default="konfirmasi")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("subject", "rule", "policy_version", "created_at",
                         name="uq_verdicts_subject_rule_policy_created"),
        Index("ix_verdicts_subject_created", "subject", "created_at"),
    )


class Strategy(Base):
    """Definisi mesin/arm (A–D, agen, strategi lain) + status + ringkasan."""

    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    arm_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    area: Mapped[str] = mapped_column(String(32), nullable=False)  # poly|crypto|idx|forex|gmgn
    label: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="aktif")
    summary_json: Mapped[Any] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_strategies_area_status", "area", "status"),)


class Trade(Base):
    """Paper & live dibedakan tegas lewat (venue, mode) — bukan boolean.

    DEPRECATED untuk forex (ADR-009): jurnal forward test forex membaca
    `/var/lib/warroom/deals.csv`, dan tidak ada kode yang menulis tabel ini.
    Jangan menambah penulis forex di sini; bila DB dipakai, impor CSV → DB.
    Tabel dipertahankan untuk venue lain sampai ada penulis nyata.
    """

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    venue: Mapped[str] = mapped_column(String(40), nullable=False)  # polymarket|binance|paper|...
    mode: Mapped[str] = mapped_column(String(16), nullable=False)   # paper|live|warisan
    ext_id: Mapped[str] = mapped_column(String(120), nullable=False)
    strategy_id: Mapped[int | None] = mapped_column(ForeignKey("strategies.id"))
    side: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    qty: Mapped[Decimal | None] = mapped_column(Money)
    price: Mapped[Decimal | None] = mapped_column(Money)
    pnl_usd: Mapped[Decimal | None] = mapped_column(Money)
    pnl_r: Mapped[Decimal | None] = mapped_column(Money)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_json: Mapped[Any] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("venue", "mode", "ext_id", name="uq_trades_venue_mode_ext"),
        Index("ix_trades_closed_at", "closed_at"),
        Index("ix_trades_strategy_id", "strategy_id"),
        Index("ix_trades_mode_strategy_closed", "mode", "strategy_id", "closed_at"),
    )


class Parameter(Base):
    """Registry parameter + batas beku. Hanya nilai dalam `bounds` yang boleh diterapkan."""

    __tablename__ = "parameters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    scope: Mapped[str] = mapped_column(String(24), nullable=False, default="paper")  # paper|live
    value_json: Mapped[Any] = mapped_column(JSONB, nullable=False)
    bounds_json: Mapped[Any | None] = mapped_column(JSONB)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Proposal(Base):
    """Usulan perubahan parameter (bounded autonomy). Append-only."""

    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    parameter_name: Mapped[str] = mapped_column(ForeignKey("parameters.name"), nullable=False)
    from_json: Mapped[Any] = mapped_column(JSONB, nullable=False)
    to_json: Mapped[Any] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_json: Mapped[Any] = mapped_column(JSONB, nullable=False, default=dict)
    gate_verdict: Mapped[str] = mapped_column(String(24), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="diusulkan")
    decided_by: Mapped[str | None] = mapped_column(String(80))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    config_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Prompt(Base):
    """Registry prompt: perubahan = versi baru, tidak pernah menimpa."""

    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    schema_json: Mapped[Any] = mapped_column(JSONB, nullable=False, default=dict)
    contoh_json: Mapped[Any] = mapped_column(JSONB, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("role", "version", name="uq_prompts_role_version"),)


class LLMCall(Base):
    """Setiap panggilan LLM wajib meninggalkan jejak (ADR-004)."""

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Money)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fallback_from: Mapped[str | None] = mapped_column(String(40))
    error_code: Mapped[str | None] = mapped_column(String(60))
    result_hash: Mapped[str | None] = mapped_column(String(64))
    fact_ids: Mapped[Any] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_llm_calls_role_created", "role", "created_at"),)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    subject: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_action: Mapped[str] = mapped_column(Text, nullable=False, default="")
    fact_ids: Mapped[Any] = mapped_column(JSONB, nullable=False, default=list)
    ack_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snooze_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Berapa kali notifier mencoba mengirim (batas MAX_PERCOBAAN) + kesalahan terakhir.
    # Disimpan eksplisit supaya UI bisa menandai alert macet tanpa memindai event.
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Service(Base):
    """Unit lintas host (Webdock/Azure/Tencent) — status dibaca, bukan ditebak."""

    __tablename__ = "services"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    host: Mapped[str] = mapped_column(String(80), nullable=False)
    unit: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    detail_json: Mapped[Any] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("host", "unit", name="uq_services_host_unit"),)


class Heartbeat(Base):
    __tablename__ = "heartbeats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    host: Mapped[str] = mapped_column(String(80), nullable=False)
    unit: Mapped[str] = mapped_column(String(120), nullable=False)
    beat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload_json: Mapped[Any] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (Index("ix_heartbeats_host_unit_beat", "host", "unit", "beat_at"),)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="viewer")  # viewer|operator|owner
    pass_hash: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    totp_secret_enc: Mapped[str | None] = mapped_column(String(400))
    totp_last_counter: Mapped[int | None] = mapped_column(BigInteger)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    """Jejak aksi operator (siapa/apa/kapan/alasan)."""

    __tablename__ = "audit"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    detail_json: Mapped[Any] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Dataset(Base):
    """Katalog dataset (recorder Polymarket dll)."""

    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    path: Mapped[str] = mapped_column(String(400), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    range_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    range_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows: Mapped[int | None] = mapped_column(BigInteger)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    quality_json: Mapped[Any] = mapped_column(JSONB, nullable=False, default=dict)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ResearchRun(Base):
    """Versioned, research-only snapshot of both canonical contracts."""

    __tablename__ = "research_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    research_key: Mapped[str] = mapped_column(String(120), nullable=False)
    hypothesis_id: Mapped[str] = mapped_column(String(120), nullable=False)
    hypothesis_version: Mapped[str] = mapped_column(String(80), nullable=False)
    hypothesis_json: Mapped[Any] = mapped_column(JSONB, nullable=False)
    hypothesis_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_json: Mapped[Any] = mapped_column(JSONB, nullable=False)
    execution_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft", server_default="draft")
    provenance_json: Mapped[Any] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "research_key", "hypothesis_hash", "execution_hash", name="uq_research_runs_version"
        ),
        CheckConstraint(
            "status IN ('draft', 'running', 'completed', 'failed', 'invalid')",
            name="ck_research_runs_status",
        ),
        CheckConstraint(
            "execution_json ->> 'mode' IN ('paper', 'shadow')",
            name="ck_research_runs_research_only",
        ),
        Index("ix_research_runs_key_created", "research_key", "created_at"),
    )


class ResearchRecord(Base):
    """Immutable provenance record for an artifact attached to a research run."""

    __tablename__ = "research_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    research_run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    uri: Mapped[str] = mapped_column(String(400), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="observed", server_default="observed"
    )
    provenance_json: Mapped[Any] = mapped_column(JSONB, nullable=False, default=dict)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("research_run_id", "uri", "sha256", name="uq_research_records_artifact"),
        CheckConstraint("status IN ('observed', 'validated', 'rejected')", name="ck_research_records_status"),
        Index("ix_research_records_run_created", "research_run_id", "created_at"),
    )


class FrozenSplit(Base):
    """Split data yang DIBEKUKAN sebelum hasilnya dilihat (ADR-003, P1 roadmap 5 Okt 2026).

    Kenapa tabel, bukan sekadar string di payload: gate menerima ``split="frozen:<id>"``
    dan mempercayainya. Tanpa catatan yang tidak bisa diubah, "frozen:" hanyalah label —
    siapa pun bisa menuliskannya setelah melihat hasil. Baris di sini mengikat id itu ke
    daftar berkas + sha256 yang benar-benar dibaca, sehingga bisa diverifikasi ulang.

    Append-only: tidak ada alur yang boleh mengubah baris split setelah ditulis.
    """

    __tablename__ = "frozen_splits"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # dipakai sebagai frozen:<id>
    dataset: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    # Berkas yang termasuk split + sha256-nya: {"file": "...", "sha256": "...", "bytes": N}
    files_json: Mapped[Any] = mapped_column(JSONB, nullable=False, default=list)
    manifest_hash: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    partitions_json: Mapped[Any] = mapped_column(JSONB, nullable=False, default=dict)
    window_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows: Mapped[int | None] = mapped_column(BigInteger)
    created_by: Mapped[str] = mapped_column(String(80), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_frozen_splits_dataset", "dataset"),)


class Job(Base):
    """Jadwal deklaratif (P1-T4).

    Satu tempat untuk melihat "apa yang akan jalan, kapan terakhir jalan, hasilnya apa".
    Timer systemd lama tetap hidup sampai cutover diputuskan owner; menjalankan dua
    penulis untuk job yang sama akan menggandakan kuota (mis. Arjum) — itu sebabnya
    job `collect` sengaja didaftarkan **nonaktif** di P1, bukan dihapus.
    """

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    interval_s: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    payload_json: Mapped[Any] = mapped_column(JSONB, nullable=False, default=dict)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str] = mapped_column(String(24), nullable=False, default="")
    last_detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_jobs_enabled_next", "enabled", "next_run_at"),)
 

class Grant(Base):
    """Izin aksi live (P6-T1) — pola harness Polymarket: `grantedBy/messageId/scope/at`.

    Izin **wajib berasal dari pesan user** dan punya masa berlaku; satu scope = satu izin.
    Aksi live tanpa grant aktif → 409 dengan daftar grant yang kurang (bukan 403 kabur).
    """

    __tablename__ = "grants"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(80), nullable=False)
    granted_by: Mapped[str] = mapped_column(String(80), nullable=False)
    message_id: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_grants_scope_expires", "scope", "expires_at"),
        UniqueConstraint("scope", "message_id", name="uq_grants_scope_message"),
    )


class MT5Account(Base):
    """Vault kredensial MT5 — sandi terenkripsi, tidak pernah keluar via API metadata."""

    __tablename__ = "mt5_accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    login: Mapped[str] = mapped_column(String(32), nullable=False)
    server: Mapped[str] = mapped_column(String(160), nullable=False)
    password_enc: Mapped[str] = mapped_column(Text, nullable=False)
    # investor|master — investor disarankan (read-only)
    password_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="investor")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[int | None] = mapped_column(BigInteger)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("uq_mt5_accounts_login_server", "login", "server", unique=True),
    )


class VaultCredential(Base):
    """Gudang kredensial generik (endpoint + API key/secret platform manapun).

    Salin-tempel manual saja — BUKAN auto-login. Polymarket diblokir.
    """

    __tablename__ = "vault_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint: Mapped[str | None] = mapped_column(Text)
    api_key_enc: Mapped[str | None] = mapped_column(Text)
    api_secret_enc: Mapped[str | None] = mapped_column(Text)
    # pasangan ekstra bebas (JSON terenkripsi), mis. passphrase OKX
    extra_enc: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("uq_vault_platform_label", "platform", "label", unique=True),
        Index("ix_vault_credentials_platform", "platform"),
    )
