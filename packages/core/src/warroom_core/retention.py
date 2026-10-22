"""Retensi data platform (P5 roadmap 5 Okt 2026).

Masalah: `facts` menyimpan SATU BARIS PER PENGAMATAN dan itu desain yang disengaja (ADR-005
— angka di UI/AI harus punya fact_id). Tapi tanpa retensi, tabelnya tumbuh selamanya: pada
5 Okt sudah 11.150 baris / 21 MB hanya dalam 3 hari, dengan 723 versi untuk satu kunci.

Prinsip yang dikodekan di sini:

- **Jangan hapus yang masih dipakai.** Setiap `(kind, key)` menyimpan ``keep_versi`` versi
  TERBARU apa pun yang terjadi. Baris yang punya ``fact_id`` yang dirujuk verdict/event
  tidak akan pernah jadi kandidat karena hanya versi lama berlebih yang dibuang.
- **`events` append-only tidak disentuh** kecuali retensi eksplisit yang diminta; tabel ini
  adalah jejak audit, jadi operator memutuskan, bukan kode.
- **Simulasi dulu.** ``rencana()`` menghitung apa yang AKAN dihapus tanpa menghapus apa pun.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select

from warroom_core.db import Alert, Event, Fact, LLMCall, Session

__all__ = ["prune_orphan_refs", "rencana", "jalankan"]

# Batas konservatif: simpan versi terbaru per kunci walau berapa pun umurnya.
KEEP_VERSI_DEFAULT = 3
# Untuk events: simpan N hari. Append-only tetap dihormati — ini retensi terencana,
# bukan alur yang menulis ulang riwayat.
EVENTS_HARI_DEFAULT = 90
# llm_calls: rekaman biaya; berguna lebih lama dari event rutin.
LLM_CALL_HARI_DEFAULT = 180
# alerts: notifikasi operasional. Yang SUDAH di-ack adalah arsip — simpan N hari lalu buang;
# yang BELUM di-ack TIDAK PERNAH dibuang oleh umur (itu tugas manusia, bukan retensi).
# Temuan 7 Okt: 100 alert menumpuk (75 belum di-ack sejak 2 Okt) karena retensi tidak
# pernah menyentuh tabel ini.
ALERTS_HARI_DEFAULT = 14


def prune_orphan_refs(s: Any, *, batas: int = 5000) -> int:
    """Kosongkan `events.fact_ids` yang menunjuk fakta sudah tidak ada.

    Ini BUKAN menghapus event (append-only dihormati): hanya daftar rujukannya yang
    dikosongkan karena fakta yang dirujuk sudah tidak ada. Terjadi sekali di produksi
    (5 Okt 2026) saat retensi pertama dijalankan TANPA penjaga "jangan hapus fakta yang
    dirujuk" — 935 event lama jadi menunjuk ke ketiadaan. Perbaikannya: penjaga di
    `rencana()`/`jalankan()`, plus pembersihan sekali untuk kerusakan yang sudah terjadi.
    """
    from sqlalchemy import text

    res = s.execute(
        text(
            """
            UPDATE events e SET fact_ids = '[]'::jsonb
             WHERE jsonb_array_length(e.fact_ids) > 0
               AND NOT EXISTS (
                   SELECT 1 FROM facts f WHERE e.fact_ids @> to_jsonb(f.id)
               )
               AND e.id IN (
                   SELECT e2.id FROM events e2
                    WHERE jsonb_array_length(e2.fact_ids) > 0
                      AND NOT EXISTS (
                          SELECT 1 FROM facts f2 WHERE e2.fact_ids @> to_jsonb(f2.id)
                      )
                    LIMIT :batas
               )
            """
        ),
        {"batas": batas},
    )
    s.flush()
    return res.rowcount or 0


def rencana(
    s: Any,
    *,
    keep_versi: int = KEEP_VERSI_DEFAULT,
    events_hari: int = EVENTS_HARI_DEFAULT,
    llm_call_hari: int = LLM_CALL_HARI_DEFAULT,
    alerts_hari: int = ALERTS_HARI_DEFAULT,
) -> dict[str, int]:
    """Hitung kandidat hapus TANPA menghapus apa pun (aman dijalankan di produksi)."""
    now = datetime.now(UTC)

    # facts: per (kind,key), buang versi lebih tua dari `keep_versi` terbaru — KECUALI
    # baris yang masih dirujuk `events.fact_ids`. Jejak audit append-only harus tetap bisa
    # ditelusuri; menghapus fakta yang dirujuk akan membuat event lama menunjuk ke ketiadaan
    # (terbukti terjadi: 935 event yatim saat retensi pertama tanpa penjaga ini).
    sub = (
        select(
            Fact.id,
            Fact.kind,
            Fact.key,
            func.row_number()
            .over(partition_by=(Fact.kind, Fact.key), order_by=Fact.observed_at.desc())
            .label("rn"),
        )
        .subquery()
    )
    # fact_ids berbentuk JSONB array angka; bandingkan lewat EXISTS agar tidak memuat semua
    # id ke memori.
    kandidat_facts = (
        select(sub.c.id)
        .where(sub.c.rn > keep_versi)
        .where(
            ~select(Event.id)
            .where(func.jsonb_array_length(Event.fact_ids) > 0)
            .where(Event.fact_ids.op("@>")(func.to_jsonb(sub.c.id)))
            .exists()
        )
        .where(
            ~select(Alert.id)
            .where(func.jsonb_array_length(Alert.fact_ids) > 0)
            .where(Alert.fact_ids.op("@>")(func.to_jsonb(sub.c.id)))
            .exists()
        )
    )
    n_facts = s.scalar(select(func.count()).select_from(kandidat_facts.subquery())) or 0

    batas_events = now - timedelta(days=events_hari)
    n_events = s.scalar(
        select(func.count()).select_from(Event).where(Event.created_at < batas_events)
    ) or 0

    batas_llm = now - timedelta(days=llm_call_hari)
    n_llm = s.scalar(
        select(func.count()).select_from(LLMCall).where(LLMCall.created_at < batas_llm)
    ) or 0

    batas_alert = now - timedelta(days=alerts_hari)
    n_alert = s.scalar(
        select(func.count())
        .select_from(Alert)
        .where(Alert.created_at < batas_alert, Alert.ack_at.is_not(None))
    ) or 0

    n_sessions = s.scalar(
        select(func.count())
        .select_from(Session)
        .where(Session.expires_at < now)
    ) or 0

    return {
        "facts": int(n_facts),
        "events": int(n_events),
        "llm_calls": int(n_llm),
        "alerts": int(n_alert),
        "sessions": int(n_sessions),
        "keep_versi": keep_versi,
        "events_hari": events_hari,
        "llm_call_hari": llm_call_hari,
        "alerts_hari": alerts_hari,
    }


def jalankan(
    s: Any,
    *,
    keep_versi: int = KEEP_VERSI_DEFAULT,
    events_hari: int = EVENTS_HARI_DEFAULT,
    llm_call_hari: int = LLM_CALL_HARI_DEFAULT,
    alerts_hari: int = ALERTS_HARI_DEFAULT,
    hapus_events: bool = True,
    hapus_llm_calls: bool = True,
) -> dict[str, Any]:
    """Jalankan retensi. Kembalikan jumlah yang benar-benar dihapus.

    ``hapus_events=False`` berguna kalau operator ingin menyimpan jejak audit penuh dan
    hanya membatasi pertumbuhan `facts` (yang paling cepat tumbuh).
    """
    r = rencana(
        s, keep_versi=keep_versi, events_hari=events_hari,
        llm_call_hari=llm_call_hari, alerts_hari=alerts_hari,
    )
    dihapus: dict[str, int] = {
        "facts": 0, "events": 0, "llm_calls": 0, "alerts": 0, "sessions": 0, "rujukan_yatim_dibersihkan": 0,
    }

    if r["facts"]:
        sub = (
            select(
                Fact.id,
                func.row_number()
                .over(partition_by=(Fact.kind, Fact.key), order_by=Fact.observed_at.desc())
                .label("rn"),
            )
            .subquery()
        )
        # Penjaga SAMA dengan rencana(): jangan hapus fakta yang masih dirujuk event atau alert.
        kandidat = (
            select(sub.c.id)
            .where(sub.c.rn > keep_versi)
            .where(
                ~select(Event.id)
                .where(func.jsonb_array_length(Event.fact_ids) > 0)
                .where(Event.fact_ids.op("@>")(func.to_jsonb(sub.c.id)))
                .exists()
            )
            .where(
                ~select(Alert.id)
                .where(func.jsonb_array_length(Alert.fact_ids) > 0)
                .where(Alert.fact_ids.op("@>")(func.to_jsonb(sub.c.id)))
                .exists()
            )
        )
        res = s.execute(delete(Fact).where(Fact.id.in_(kandidat)))
        dihapus["facts"] = res.rowcount or 0

    # Bersihkan rujukan fact_id yang sudah tidak ada (lihat prune_orphan_refs).
    dihapus["rujukan_yatim_dibersihkan"] = prune_orphan_refs(s)

    if hapus_events and r["events"]:
        batas = datetime.now(UTC) - timedelta(days=events_hari)
        res = s.execute(delete(Event).where(Event.created_at < batas))
        dihapus["events"] = res.rowcount or 0

    if hapus_llm_calls and r["llm_calls"]:
        batas = datetime.now(UTC) - timedelta(days=llm_call_hari)
        res = s.execute(delete(LLMCall).where(LLMCall.created_at < batas))
        dihapus["llm_calls"] = res.rowcount or 0

    # Alerts: hanya yang SUDAH di-ack dan lebih tua dari batas. Yang belum di-ack adalah
    # pekerjaan manusia — retensi tidak berhak membuangnya.
    if r["alerts"]:
        batas = datetime.now(UTC) - timedelta(days=alerts_hari)
        res = s.execute(
            delete(Alert).where(Alert.created_at < batas, Alert.ack_at.is_not(None))
        )
        dihapus["alerts"] = res.rowcount or 0

    # Sessions: bersihkan sesi kedaluwarsa (T-6 dead code purge_expired remediation)
    if r.get("sessions"):
        res = s.execute(
            delete(Session).where(Session.expires_at < datetime.now(UTC))
        )
        dihapus["sessions"] = res.rowcount or 0

    s.flush()
    return {"dihapus": dihapus, "rencana": r}
