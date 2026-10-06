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
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session as SASession
from warroom_core.db import Event, Fact, Strategy

__all__ = [
    "BAGIAN_WAJIB",
    "DEFAULT_TTL_S",
    "PublishReport",
    "canonical_hash",
    "periksa_kelengkapan_bagian",
    "publish_snapshot",
]

DEFAULT_TTL_S = 600  # snapshot dibangun tiap 15 menit (config.snapshot_ttl_s)
SOURCE = "state/snapshot.json"

# Sub-bagian yang WAJIB ada di setiap snapshot. Bila salah satu hilang sementara proses
# melaporkan sukses, snapshot itu SEPARUH — kelas bug yang tak terlihat dari luar: nilai
# yang ADA tetap benar, yang HILANG tidak dilaporkan siapa pun. Daftar ini diverifikasi
# terhadap `bagian` nyata di state/snapshot.json (13 kunci, 5 Okt 2026 — `bsjp` ditambahkan).
BAGIAN_WAJIB: frozenset[str] = frozenset(
    {
        "bandarmologi",
        "bsjp",
        "crypto",
        "dex",
        "forex",
        "hyperliquid",
        "idx",
        "idx616",
        "idx_tv",
        "lp",
        "macro",
        "memecoin",
        "news",
        "overextended",
    }
)

# Kunci tingkat atas yang memang memuat angka; sisanya tetap dipublikasikan sebagai fakta
# supaya UI tidak perlu tahu struktur berkas.
_NUMERIC_KEYS = ("equity", "ledger", "risiko", "pengukuran", "backtest", "poly_paper", "lp_paper")


def canonical_hash(value: Any) -> str:
    """sha256 dari JSON kanonik (kunci terurut, tanpa spasi) — stabil antar-jalankan."""
    blob = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _observed_at(payload: dict[str, Any], path: Path) -> datetime:
    """Waktu observasi sebenarnya.

    Field `dibuat` dari domain berformat `"2026-10-05 01:15:52 WIB"` (UTC+7).
    Bila ada penanda 'WIB', waktu harus ditandai timezone(timedelta(hours=7))
    agar konversi ke UTC tepat dan tidak melompat 7 jam ke masa depan.

    Urutan kepercayaan: stempel waktu berzona (ISO, mis. `...+07:00`/`Z`) →
    `dibuat` berformat WIB (UTC+7) → `dibuat` lokal/UTC → mtime berkas.
    """
    raw = payload.get("dibuat")
    if isinstance(raw, str) and raw:
        is_wib = "WIB" in raw
        teks = raw.strip().replace(" WIB", "").replace("WIB", "").strip()
        # ISO dengan penanda zona eksplisit (Z atau ±HH:MM) = paling tepercaya.
        if re.search(r"(Z|[+-]\d{2}:?\d{2})$", teks):
            try:
                return datetime.fromisoformat(teks.replace("Z", "+00:00"))
            except ValueError:
                pass
        wib_tz = timezone(timedelta(hours=7))
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                if is_wib:
                    dt = datetime.strptime(teks, fmt).replace(tzinfo=wib_tz)
                else:
                    dt = datetime.strptime(teks, fmt).replace(tzinfo=UTC)
            except ValueError:
                continue
            # Penjaga masa depan: bila jam lokal keliru diset melompat ke depan
            now_utc = datetime.now(tz=UTC)
            if dt > now_utc + timedelta(minutes=5):
                try:
                    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
                    return min(mtime, now_utc)
                except OSError:
                    return now_utc
            return dt
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except OSError:
        return datetime.now(tz=UTC)


@dataclass
class PublishReport:
    status: str  # ok | tidak-ada | rusak
    facts: int = 0
    keys: list[str] = field(default_factory=list)
    observed_at: str | None = None
    detail: str = ""


def periksa_kelengkapan_bagian(
    payload: dict[str, Any], *, bagian_sebelumnya: set[str] | None = None
) -> list[str]:
    """Sub-bagian yang HILANG dari ``payload["bagian"]`` (kosong = lengkap).

    Acuan ganda supaya tahan perubahan kontrak:
    - ``BAGIAN_WAJIB`` (kontrak eksplisit kode);
    - ``bagian_sebelumnya`` (snapshot terbit terakhir) — menangkap kunci yang PERNAH ada
      lalu hilang, walau namanya belum masuk kontrak.

    Bila ``bagian`` bukan dict, SELURUH bagian wajib dianggap hilang — bukan "nol".
    """
    bagian = payload.get("bagian")
    wajib = BAGIAN_WAJIB | set(bagian_sebelumnya or ())
    if not isinstance(bagian, dict):
        return sorted(wajib)
    return sorted(wajib - set(bagian))


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

    # Penjaga snapshot separuh (temuan 5 Okt 2026): bandingkan `bagian` sekarang vs kontrak
    # + bagian terbit sebelumnya. Diambil SEBELUM menulis, supaya snapshot separuh tidak
    # pernah diterbitkan sebagai "ok". Fakta tetap ditulis agar bagian yang MASIH BENAR
    # tetap terbaca — yang diperbaiki adalah klaim implisit "snapshot lengkap".
    from sqlalchemy import select

    sebelum = s.scalars(
        select(Fact.value_json)
        .where(Fact.kind == "snapshot", Fact.key == "bagian")
        .order_by(Fact.observed_at.desc())
        .limit(1)
    ).first()
    bagian_sebelumnya = set(sebelum) if isinstance(sebelum, dict) else set()
    hilang = periksa_kelengkapan_bagian(payload, bagian_sebelumnya=bagian_sebelumnya)

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
            "bagian_hilang": hilang,
        },
        fact_ids=[f.id for f in created],
        severity="warning" if hilang else "info",
    )
    s.add(ev)
    s.flush()

    if hilang:
        # Alert ber-dedupe subjek: satu kondisi terbuka = satu alert (tidak menumpuk).
        from warroom_core.db import Alert

        sudah = s.scalar(
            select(Alert.id).where(Alert.subject == "snapshot/separuh").where(Alert.ack_at.is_(None)).limit(1)
        )
        if sudah is None:
            s.add(
                Alert(
                    severity="warning",
                    subject="snapshot/separuh",
                    message=f"snapshot separuh: bagian hilang {hilang} (sumber {p})",
                    suggested_action=(
                        "periksa penulis snapshot (job refresh-snapshot / unit live-trading-*); "
                        "bandingkan bagian yang dilaporkan `lt snapshot` vs isi berkas"
                    ),
                    fact_ids=[f.id for f in created],
                )
            )
        return PublishReport(
            status="separuh",
            facts=len(created),
            keys=sorted(str(k) for k in payload),
            observed_at=observed.isoformat(),
            detail=f"bagian hilang: {hilang}",
        )

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