"""Alert transisi status strategi dari fakta — kill-switch/HALTED (per strategi).

Modul alert (`warroom_notifier.strategy_alert`) membangkitkan kill HANYA pada
transisi aktif→kill; keadaan sebelumnya disuplai pemanggil. Di sini riwayat itu
adalah fakta-fakta terbaru `harian/status`: transisi terbaca dari pasangan
(belum HALTED → HALTED), dan penanda eksplisit (alert yang menautkan `baru.id`)
menahan pasangan lama supaya transisi yang faktanya masih tersimpan tidak berkabar ulang.

Kontrak transport tidak berubah: alert selalu masuk DB lebih dulu; pengiriman
(termasuk percobaan ulang) tetap urusan tabel `alerts` + job notify.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as SASession
from warroom_core.db import Alert, Fact, Job
from warroom_notifier.dispatch import kirim_tertunda
from warroom_notifier.strategy_alert import alert_kill_switch

from .base import _alert

__all__ = ["handler_strategi_alert"]


def handler_strategi_alert(s: SASession, job: Job) -> str:
    """Kabarkan transisi HALTED per strategi dari pasangan fakta terbaru."""
    kind = str(job.payload_json.get("kind", "harian"))
    key = str(job.payload_json.get("key", "status"))
    nama = str(job.payload_json.get("strategi", "Strategi A"))

    riwayat = list(
        s.scalars(
            select(Fact)
            .where(Fact.kind == kind, Fact.key == key)
            .order_by(Fact.observed_at.desc())
            .limit(5)
        ).all()
    )
    if len(riwayat) < 2:
        return f"{kind}/{key}: riwayat fakta < 2 — transisi belum bisa dinilai"

    obs = riwayat[0].observed_at
    if obs.tzinfo is None:
        obs = obs.replace(tzinfo=UTC)
    if datetime.now(UTC) - obs > timedelta(hours=26):
        raise RuntimeError(
            f"{kind}/{key}: fakta terbaru ({obs.isoformat()}) sudah stale > 26 jam"
        )

    for baru, lama in zip(riwayat, riwayat[1:], strict=False):
        v_baru = baru.value_json if isinstance(baru.value_json, dict) else {}
        v_lama = lama.value_json if isinstance(lama.value_json, dict) else {}
        if not v_baru.get("halted") or v_lama.get("halted"):
            continue
        alasan = str(v_baru.get("alasan_halted") or "kondisi risk engine (alasan tidak tercatat)")
        kondisi = alert_kill_switch(nama, alasan=alasan)
        # Penanda eksplisit: alert yang fact_ids-nya memuat baru.id sudah pernah dibuat.
        # Menghindari hilangnya alert bila siklus sebelumnya gagal saat run_one.
        sudah_ada = any(
            isinstance(a.fact_ids, list) and baru.id in a.fact_ids
            for a in s.scalars(select(Alert).where(Alert.subject == kondisi.subjek)).all()
        )
        if sudah_ada:
            break
        # Jika siklus sebelumnya sukses ('ok') dan lebih baru dari fakta ini, fakta sudah diproses.
        # Bila siklus sebelumnya gagal (last_status != 'ok'), jangan lewati fakta transisi.
        if (
            job.last_status == "ok"
            and job.last_run_at is not None
            and baru.observed_at < job.last_run_at
        ):
            break
        dibuat = _alert(
            s, subject=kondisi.subjek, message=kondisi.pesan,
            aksi=kondisi.subjek_aksi, severity=kondisi.severity,
            fact_ids=[baru.id],
        )
        if dibuat:
            kirim_tertunda(s, limit=5)
        return (
            f"{nama}: transisi HALTED {'dikabarkan' if dibuat else 'sudah ada alert terbuka'}"
            f" — {alasan}"
        )
    return f"{kind}/{key}: {len(riwayat)} fakta diperiksa — tidak ada transisi HALTED baru"
