"""SSE `/api/v1/stream` (P1-T7).

Sumber: tabel `events` (append-only). Klien boleh mengirim `Last-Event-ID` untuk melanjutkan
tanpa kehilangan kejadian. Implementasi **polling** DB (bukan bus di memori) supaya:
- event dari proses lain (worker, notifier) tetap terkirim,
- tidak ada state yang bisa hilang saat proses API restart,
- tidak ada kebocoran memori dari daftar subscriber yang tak dibersihkan.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import or_, select
from warroom_core.db import Event, session_scope

__all__ = ["event_stream", "parse_last_event_id", "topic_matches"]

# Topik → prefiks tipe event. Topik tak dikenal → tidak ada yang cocok (jujur, bukan kirim semua).
TOPICS: dict[str, tuple[str, ...]] = {
    "signals": ("signal.",),
    "verdicts": ("verdict.", "gate."),
    "trades": ("trade.", "order."),
    "alerts": ("alert.",),
    "llm": ("llm.",),
    "services": ("service.", "job.", "heartbeat.", "freshness."),
    "params": ("param.", "proposal.", "policy."),
    "facts": ("snapshot.", "fact."),
}

POLL_S = 1.5
HEARTBEAT_S = 15.0


def parse_last_event_id(raw: str | None) -> int | None:
    """`Last-Event-ID` boleh kosong/aneh — yang tidak bisa diurai diabaikan, bukan error 500."""
    if not raw:
        return None
    try:
        nilai = int(raw.strip())
    except (TypeError, ValueError):
        return None
    return nilai if nilai >= 0 else None


def topic_matches(tipe: str, topics: list[str] | None) -> bool:
    if not topics:
        return True
    for t in topics:
        if tipe.startswith(TOPICS.get(t, ("\0tidak-ada-topik-ini",))):
            return True
    return False


def _sse(id_: int | None, event: str, data: dict) -> str:
    baris = []
    if id_ is not None:
        baris.append(f"id: {id_}")
    baris.append(f"event: {event}")
    baris.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    return "\n".join(baris) + "\n\n"


def _fetch(after_id: int, topics: list[str] | None, limit: int = 200) -> tuple[list[Event], int]:
    """Ambil event setelah ``after_id`` yang COCOK topik.

    Mengembalikan ``(baris_cocok, id_tertinggi_yang_dibaca)``.

    Temuan QA putaran 2 (isolasi SSE) yang sekaligus menemukan BUG NYATA di sini:
    versi lama mengambil 200 baris TERAKHIR tanpa peduli topik, menyaring di Python,
    dan hanya memajukan ``after`` untuk baris yang cocok. Dengan tabel events yang
    didominasi ``job.ran`` (12.000+ baris), klien bertopik "trades" terus membaca
    200 baris ``job.ran`` yang sama, tidak pernah ada yang cocok, dan ``after`` tak
    pernah maju → **stream kelaparan selamanya** (panel Kejadian Area kosong).
    Sekarang: filter topik diterapkan di SQL, dan ``after`` SELALU maju ke id tertinggi
    yang dibaca — baris yang tidak cocok dilewati sekali, bukan dibaca berulang.
    """
    with session_scope() as s:
        q = select(Event).where(Event.id > after_id).order_by(Event.id.asc()).limit(limit)
        if topics:
            pola: list[str] = []
            for t in topics:
                pola.extend(TOPICS.get(t, ("\0tidak-ada-topik-ini",)))
            q = q.where(or_(*[Event.type.startswith(p.rstrip(".")) for p in pola]))
        rows = s.scalars(q).all()
        id_tertinggi = after_id
        if rows:
            id_tertinggi = max(id_tertinggi, rows[-1].id)
        # Salin ke objek sederhana supaya sesi boleh ditutup (tidak ada lazy-load setelah commit).
        return (
            [
                Event(
                    id=e.id,
                    type=e.type,
                    actor=e.actor,
                    payload_json=e.payload_json,
                    fact_ids=e.fact_ids,
                    severity=e.severity,
                    created_at=e.created_at,
                )
                for e in rows
            ],
            id_tertinggi,
        )


def _last_id() -> int:
    with session_scope() as s:
        return s.scalar(select(Event.id).order_by(Event.id.desc()).limit(1)) or 0


async def event_stream(
    topics: list[str] | None = None,
    last_event_id: str | None = None,
    *,
    poll_s: float = POLL_S,
    heartbeat_s: float = HEARTBEAT_S,
    max_iterations: int | None = None,
    disconnect: object | None = None,
) -> AsyncIterator[str]:
    """Generator SSE. `max_iterations`/`disconnect` dipakai tes supaya bisa berhenti sendiri."""
    after = parse_last_event_id(last_event_id)
    if after is None:
        # Tanpa Last-Event-ID: mulai dari sekarang (jangan banjiri klien dengan seluruh riwayat).
        after = await asyncio.to_thread(_last_id)

    yield f"retry: 3000\ndata: {json.dumps({'ok': True, 'topik': topics or ['semua'], 'dari_id': after})}\n\n"

    iterasi = 0
    terakhir_denyut = 0.0
    while True:
        iterasi += 1
        if max_iterations is not None and iterasi > max_iterations:
            return
        if disconnect is not None and callable(disconnect) and disconnect():  # type: ignore[operator]
            return

        rows, id_terbaca = await asyncio.to_thread(_fetch, after, topics)
        # `after` maju mengikuti apa yang DIBACA (bukan hanya yang dikirim) — kalau tidak,
        # baris di luar topik akan dibaca ulang selamanya dan stream tak pernah sampai
        # ke kejadian yang cocok (bug kelaparan di atas).
        after = max(after, id_terbaca)
        for e in rows:
            yield _sse(
                e.id,
                e.type,
                {
                    "id": e.id,
                    "type": e.type,
                    "actor": e.actor,
                    "severity": e.severity,
                    "payload": e.payload_json,
                    "fact_ids": e.fact_ids,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                },
            )
        if rows:
            terakhir_denyut = 0.0
            continue

        terakhir_denyut += poll_s
        if terakhir_denyut >= heartbeat_s:
            terakhir_denyut = 0.0
            yield f": denyut {datetime.now(UTC).isoformat()}\n\n"
        await asyncio.sleep(poll_s)