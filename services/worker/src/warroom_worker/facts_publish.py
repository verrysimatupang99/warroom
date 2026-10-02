"""Penulis fakta: `state/snapshot.json` → tabel `facts` + satu `event` (P1-T5).

Kontrak:

- Satu kunci tingkat atas snapshot = satu fakta (kind ``snapshot``), nilainya **apa adanya**
  dari berkas — tidak ada perhitungan ulang di sini (ADR-005).
- ``observed_at`` diambil dari field ``dibuat`` bila ada dan bisa diurai; kalau tidak, dari
  mtime berkas. Tidak pernah "sekarang" — itu akan membuat data basi menyamar segar.
- ``hash`` = sha256 dari JSON kanonik nilainya, supaya perubahan sunyi bisa dideteksi.
- Berkas tidak ada → **tidak ada fakta yang ditulis** dan fungsi mengembalikan laporan
  ``status="tidak-ada"``. Bukan nol, bukan nilai lama.

Dipanggil worker (P1-T4) dan bisa dipanggil manual untuk uji parity.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session as SASession
from warroom_core.db import Event, Fact, Strategy

__all__ = ["DEFAULT_TTL_S", "PublishReport", "canonical_hash", "publish_snapshot"]

DEFAULT_TTL_S = 600  # snapshot dibangun tiap 15 menit (config.snapshot_ttl_s)
SOURCE = "state/snapshot.json"

# Kunci tingkat atas yang memang memuat angka; sisanya tetap dipublikasikan sebagai fakta
# supaya UI tidak perlu tahu struktur berkas.
_NUMERIC_KEYS = ("equity", "ledger", "risiko", "pengukuran", "backtest", "poly_paper", "lp_paper")


def canonical_hash(value: Any) -> str:
    """sha256 dari JSON kanonik (kunci terurut, tanpa spasi) — stabil antar-jalankan."""
    blob = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _observed_at(payload: dict[str, Any], path: Path) -> datetime:
    raw = payload.get("dibuat")
    if isinstance(raw, str) and raw:
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            dt = None
        if dt is not None:
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)


@dataclass
class PublishReport:
    status: str  # ok | tidak-ada | rusak
    facts: int = 0
    keys: list[str] = field(default_factory=list)
    observed_at: str | None = None
    detail: str = ""


def publish_snapshot(
    s: SASession,
    path: str | Path,
    *,
    ttl_s: int = DEFAULT_TTL_S,
    actor: str = "worker",
) -> PublishReport:
    """Tulis fakta snapshot + satu event. Idempoten per (kind,key,observed_at)."""
    p = Path(path)
    if not p.exists():
        return PublishReport(status="tidak-ada", detail=f"{p} tidak ada")
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return PublishReport(status="rusak", detail=f"{type(exc).__name__}: {exc}")
    if not isinstance(payload, dict):
        return PublishReport(status="rusak", detail="snapshot bukan objek JSON")

    observed = _observed_at(payload, p)
    rows = [
        {
            "kind": "snapshot",
            "key": str(key),
            "value_json": value,
            "source": SOURCE,
            "observed_at": observed,
            "ttl_s": ttl_s,
            "hash": canonical_hash(value),
        }
        for key, value in payload.items()
    ]

    # Idempoten: menerbitkan snapshot yang sama dua kali tidak boleh gagal —
    # konflik pada (kind,key,observed_at) diabaikan, bukan error.
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    stmt = pg_insert(Fact).values(rows).on_conflict_do_nothing(
        index_elements=["kind", "key", "observed_at"]
    )
    s.execute(stmt)
    s.flush()

    created = list(
        s.scalars(
            select(Fact).where(Fact.kind == "snapshot", Fact.observed_at == observed, Fact.source == SOURCE)
        ).all()
    )

    # Strategi/mesin yang terlihat di snapshot didaftarkan (idempoten) supaya `strategies`
    # tidak kosong saat UI mulai dibangun.
    for arm in ("poly_paper", "lp_paper", "gmgn", "radar"):
        if arm in payload:
            _ensure_strategy(s, arm_id=f"snapshot:{arm}", area=_area_of(arm), label=arm)

    ev = Event(
        type="snapshot.published",
        actor=actor,
        payload_json={
            "path": str(p),
            "keys": sorted(payload.keys()),
            "count": len(created),
            "numeric_keys": [k for k in _NUMERIC_KEYS if k in payload],
        },
        fact_ids=[f.id for f in created],
        severity="info",
    )
    s.add(ev)

    return PublishReport(
        status="ok",
        facts=len(created),
        keys=sorted(str(k) for k in payload),
        observed_at=observed.isoformat(),
    )


def _area_of(arm: str) -> str:
    if arm.startswith("poly"):
        return "poly"
    if arm.startswith("lp"):
        return "poly"
    return "gmgn"


def _ensure_strategy(s: SASession, *, arm_id: str, area: str, label: str) -> None:
    from sqlalchemy import select

    if s.scalar(select(Strategy).where(Strategy.arm_id == arm_id)) is None:
        s.add(Strategy(arm_id=arm_id, area=area, label=label, status="pemantauan"))