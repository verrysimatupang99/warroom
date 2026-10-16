"""Alert transisi status strategi dari fakta — kill-switch/HALTED (per strategi).

Modul alert (`warroom_notifier.strategy_alert`) membangkitkan kill HANYA pada
transisi aktif→kill; keadaan sebelumnya disuplai pemanggil. Di sini riwayat itu
adalah fakta-fakta terbaru `harian/status`: transisi terbaca dari pasangan
(belum HALTED → HALTED), dan `job.last_run_at` menahan pasangan lama supaya
transisi yang faktanya masih tersimpan tidak berkabar ulang tiap siklus.

Kontrak transport tidak berubah: alert selalu masuk DB lebih dulu; pengiriman
(termasuk percobaan ulang) tetap urusan tabel `alerts` + job notify.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as SASession
from warroom_core.db import Fact, Job
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

    for baru, lama in zip(riwayat, riwayat[1:], strict=False):
        v_baru = baru.value_json if isinstance(baru.value_json, dict) else {}
        v_lama = lama.value_json if isinstance(lama.value_json, dict) else {}
        if not v_baru.get("halted") or v_lama.get("halted"):
            continue
        if job.last_run_at is not None and baru.observed_at < job.last_run_at:
            # Pasangan ini sudah diproses di siklus sebelumnya; yang lebih tua tak mungkin lebih baru.
            break
        alasan = str(v_baru.get("alasan_halted") or "kondisi risk engine (alasan tidak tercatat)")
        kondisi = alert_kill_switch(nama, alasan=alasan)
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
