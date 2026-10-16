"""Jadwal deklaratif (P1-T4).

Satu tabel `jobs`, satu fungsi `run_due()`. Tidak ada cron tersembunyi: apa yang akan jalan
bisa dibaca dari DB, lengkap dengan hasil terakhirnya.

Job yang **tidak** dinyalakan di P1 diberi alasan eksplisit di `note` — bukan didiamkan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as SASession
from warroom_core.db import Event, Job

__all__ = ["DEFAULT_JOBS", "JobSpec", "due_jobs", "ensure_jobs", "run_due", "run_one", "set_enabled"]


@dataclass(frozen=True)
class JobSpec:
    name: str
    interval_s: int
    enabled: bool = True
    payload: dict[str, Any] = field(default_factory=dict)
    note: str = ""


DEFAULT_JOBS: tuple[JobSpec, ...] = (
    JobSpec(
        name="publish-facts",
        interval_s=300,
        enabled=True,
        # TTL 1800 s = 2× jarak tulis snapshot (timer domain 15 mnt) dan sama dengan ambang
        # watchdog domain (`SNAPSHOT_MAX_AGE=1800`). Memakai 600 s (nilai badge dashboard)
        # membuat fakta "basi" di antara dua tulisan dan memunculkan alert palsu — sudah
        # terjadi sekali; lihat docs/p1-progress.md.
        payload={"path": "state/snapshot.json", "ttl_s": 1800},
        note="baca snapshot domain → facts + event (murah, tanpa kuota).",
    ),
    JobSpec(
        name="freshness",
        interval_s=300,
        enabled=True,
        payload={"alert_on_basi": True},
        note="hitung umur fakta vs ttl; basi → alert (dedupe per subjek).",
    ),
    JobSpec(
        name="notify",
        interval_s=300,
        enabled=True,
        payload={"limit": 10},
        note=(
            "kirim alert terbuka lewat transport; default tanpa transport → alert tetap di DB "
            "dan dicatat gagal (tidak pernah diklaim terkirim)."
        ),
    ),
    JobSpec(
        name="poly-sync",
        interval_s=300,
        enabled=True,
        payload={"base": "/var/lib", "ttl_s": 1800},
        note="baca-saja arm/agen/dataset Polymarket → fakta (P4-T1). Tidak menulis ke sumber.",
    ),
    JobSpec(
        name="verdict-sync",
        interval_s=900,
        enabled=True,
        payload={"ttl_s": 1800},
        note=(
            "jalankan alat verdict Poly (`qa/favorite-live-verdict.py --json`, baca-saja) → "
            "fakta `verdict` untuk GateMeter. Kebijakan alat = 95% + koreksi klaster; split "
            "tidak diisi agen, jadi gate tetap `insufficient` sampai manusia membekukannya."
        ),
    ),
    JobSpec(
        name="parity-drift",
        interval_s=900,
        enabled=True,
        payload={"n": 400},
        note="bandingkan keputusan mirror vs eksekutor; drift>0 → alert (P4-T2).",
    ),
    JobSpec(
        name="gmgn-sync",
        interval_s=600,
        enabled=True,
        payload={"ttl_s": 1800},
        note="baca-saja state GMGN + radar (dari cache) → fakta (P4-T4).",
    ),
    JobSpec(
        name="signal-sync",
        interval_s=900,
        enabled=True,
        # TTL 6 jam > interval 15 mnt (aturan rumah: fakta tidak boleh basi di antara dua tulis).
        # Ledger `verdicts.jsonl` tumbuh ~20 baris/hari, jadi jendela 6 jam cukup untuk
        # menangkap sinyal baru tanpa mengabarkan ulang yang lama.
        payload={"jam_terakhir": 6, "ttl_s": 21600, "kabari": True},
        note=(
            "baca-saja ledger verdict domain (`lt scan`) → fakta `signal.<pair>` + kabar Telegram "
            "lewat alert ber-dedupe subjek. Setiap pesan membawa label jujur: kandidat, bukan ajakan beli."
        ),
    ),
    JobSpec(
        name="polybtc-sync",
        interval_s=900,
        enabled=True,
        # TTL 30 mnt > interval 15 mnt (aturan rumah: fakta tidak boleh basi di antara
        # dua tulis). Sesi BTC 5m berganti tiap 5 menit, jadi 15 mnt cukup segar.
        payload={"ttl_s": 1800},
        note=(
            "baca-saja keluaran skill «PolyBTC Momentum» (0xgetz/polymarket-btc-5m) → "
            "fakta `poly.alt/btc-5m`. Skill berjalan mandiri; handler ini tidak pernah "
            "mengirim order dan tidak mengubah kode skill."
        ),
    ),
    JobSpec(
        name="lpagent-sync",
        interval_s=1800,
        # SENGAJA enabled=True walau kunci belum ada: handler mendeteksi kunci hilang dan
        # menerbitkan fakta jujur "menunggu-kunci" (bukan nol, bukan angka karangan),
        # sehingga halaman /sistem langsung jujur sejak hari pertama tanpa menembak API.
        enabled=True,
        payload={"top": 5, "ttl_s": 3600},
        note=(
            "snapshot pool likuiditas Solana/Meteora dari LP Agent Open API (baca-saja). "
            "Tanpa LPAGENT_API_KEY → fakta 'menunggu-kunci', bukan angka palsu. "
            "Tier Basic rate limit kecil: UI tak pernah memanggil API ini langsung."
        ),
    ),
    JobSpec(
        name="reconcile",
        interval_s=3600,
        enabled=True,
        payload={"alamat": None},
        note=(
            "verifikasi klaim uang ke on-chain (P4-T5). Tanpa WARROOM_POLYGON_RPC hasilnya "
            "'belum terverifikasi' + alert — angka uang tidak pernah ditampilkan sebagai nyata."
        ),
    ),
    JobSpec(
        name="prompts-sync",
        interval_s=3600,
        enabled=True,
        payload={"ttl_s": 86400},
        note="sinkronkan registry prompt berkas → tabel `prompts` (versi baru, tidak menimpa).",
    ),
    JobSpec(
        name="llm-brief-crypto",
        interval_s=21600,
        enabled=True,
        # 6 jam sekali: cukup untuk kartu agen, jauh di bawah batas biaya harian; cache gateway
        # 900 s membuat panggilan berulang tidak menambah biaya.
        # TTL fakta (8 jam) WAJIB lebih panjang dari interval (6 jam): kalau sama, fakta selalu
        # "basi" tepat sebelum run berikutnya dan alert freshness berbunyi tiap siklus.
        payload={
            "area": "crypto",
            "_keys": ["crypto_sinyal", "pasar_akurasi", "kandidat"],
            "max_facts": 8,
            "ttl_s": 28800,
        },
        note="narasi narrator dari fakta nyata; gagal → `status` dicatat di fakta ai.brief.",
    ),
    JobSpec(
        name="llm-brief-forex",
        interval_s=21600,
        enabled=True,
        payload={"area": "forex", "_keys": ["forex_sinyal", "pasar_akurasi"], "max_facts": 8, "ttl_s": 28800},
        note="narasi narrator forex dari jurnal mesin XAUUSD/multi-pair (angka apa adanya).",
    ),
    JobSpec(
        name="llm-brief-idx",
        interval_s=21600,
        enabled=True,
        payload={
            "area": "idx",
            "_keys": ["idx_sinyal", "idx_akurasi", "pasar_akurasi"],
            "max_facts": 8,
            "ttl_s": 28800,
        },
        note="narasi narrator IDX dari ledger mesin (ARA/BSJP/INTRADAY).",
    ),
    JobSpec(
        name="llm-brief-gmgn",
        interval_s=21600,
        enabled=True,
        payload={"area": "gmgn", "_keys": ["lp_mark", "pasar_akurasi"], "max_facts": 8, "ttl_s": 28800},
        note="narasi narrator GMGN/LP dari mark lokal (P&L USD, bukan R).",
    ),
    JobSpec(
        name="llm-brief-polymarket",
        interval_s=21600,
        enabled=True,
        payload={"area": "polymarket", "_keys": ["pasar_akurasi"], "max_facts": 8, "ttl_s": 28800},
        note="narasi narrator Polymarket dari akurasi per arm (win-rate entri, fees dibebankan).",
    ),
    JobSpec(
        name="reconcile-crypto",
        interval_s=3600,
        enabled=True,
        # Tiap jam: menutup posisi menggantung yang tertinggal dari `watchlist-sync`
        # (yang hidup di Tencent). Murah: hanya memanggil candle MEXC untuk posisi terbuka,
        # biasanya nol posisi. TTL tidak relevan — ia menulis fakta lewat ledger/event.
        payload={},
        note=(
            "tutup posisi crypto menggantung (SL dicek lebih dulu); gagal jaringan → "
            "dilaporkan, tidak menebak. Temuan 6 Okt: 2 posisi tertinggal, 2R hilang."
        ),
    ),
    JobSpec(
        name="learner",
        interval_s=86400,
        enabled=True,
        payload={},
        note=(
            "usulan parameter berbatas dari bukti nyata (P5-T2). Bukti tanpa split beku "
            "DITOLAK oleh gate — itu disengaja, bukan bug."
        ),
    ),
    JobSpec(
        name="refresh-snapshot",
        interval_s=900,
        enabled=True,
        payload={"timeout_s": 900},
        note=(
            "`lt snapshot` — pindahan dari `live-trading-snapshot.timer` (irama 15 mnt). "
            "Cutover 3 Okt: timer domain dimatikan supaya hanya ada SATU penulis snapshot. "
            "Anggaran 900s (bukan 300s): sejak `bagian` bertambah (macro, lp, …) satu siklus bisa "
            "menembus 5 menit saat jaringan lambat, dan proses yang dibunuh di tengah tulis "
            "meninggalkan snapshot separuh."
        ),
    ),
    JobSpec(
        name="radar-update",
        interval_s=1800,
        enabled=True,
        payload={"timeout_s": 900},
        note=(
            "`lt radar-update` — radar rantai dijalankan LOKAL (recreate 6 Okt dari VM Azure "
            "yang akan dimatikan). State: `state/radar_state.json`; sumbernya `gmgn-cli`, "
            "bukan Arjum (tidak menyentuh kuota). Irama 30 mnt menjaga rate-limit gmgn-cli."
        ),
    ),
    JobSpec(
        name="lp-mark",
        interval_s=3600,
        enabled=True,
        payload={"timeout_s": 300},
        note=(
            "`lt lp-mark` — mark posisi LP paper dari DexScreener (per alamat pool) → "
            "`state/lp_ledger.jsonl` + nilai pakem bukti (n = hari, bukan baris). "
            "Irama 1 jam: cukup rapat untuk jejak harian, cukup jauh agar tidak membebani API."
        ),
    ),
    JobSpec(
        name="collect",
        interval_s=1800,
        enabled=True,
        payload={"timeout_s": 900},
        note=(
            "`lt scan` — pindahan dari `live-trading-collect.timer` (irama 30 mnt). "
            "Tanpa kuota Arjum (kripto saja). Cutover 3 Okt: timer domain dimatikan."
        ),
    ),
    JobSpec(
        name="backup",
        interval_s=21600,
        enabled=True,
        payload={"timeout_s": 600},
        note=(
            "skrip backup domain (state + rotasi 14) — pindahan dari `live-trading-backup.timer` "
            "(6 jam). Cutover 3 Okt: timer domain dimatikan."
        ),
    ),
    JobSpec(
        name="paper-eval",
        interval_s=60,
        enabled=True,
        payload={"timeout_s": 30},
        note="evaluasi harga live bursa untuk posisi paper aktif; eksekusi TP/SL + alert Telegram instan.",
    ),
    JobSpec(
        name="paper-scan",
        interval_s=180,
        enabled=True,
        payload={"timeout_s": 60},
        note="pemindaian kuantitatif SMC & auto-open posisi paper saat lolos 5 risk gates + alert Telegram.",
    ),
    JobSpec(
        name="source-health",
        interval_s=60,
        enabled=True,
        payload={"host": None, "units": None},
        note=(
            "tulis `services` + `heartbeats` (R3): baca status unit systemd (baca-saja, tanpa "
            "restart) lalu catat denyut. Tanpa ini kedua tabel tetap kosong dan kesiapan "
            "(`collect_readiness`) selalu 'unknown'."
        ),
    ),
    JobSpec(
        name="retention",
        interval_s=86400,
        enabled=True,
        # Simpan 3 versi terbaru per kunci. `events` (jejak audit) TIDAK dihapus secara
        # bawaan — operator memutuskan lewat payload bila mau. facts adalah yang tumbuh
        # paling cepat (1 baris per pengamatan), jadi ini yang wajib dibatasi.
        payload={"keep_versi": 3, "hapus_events": False, "timeout_s": 120},
        note="retensi harian: batasi versi `facts` per kunci; `events` (audit) dibiarkan.",
    ),
)

# Nama job → fungsi. Diisi oleh `warroom_worker.jobs` saat impor untuk menghindari impor melingkar.
HANDLERS: dict[str, Any] = {}


def ensure_jobs(s: SASession, specs: tuple[JobSpec, ...] = DEFAULT_JOBS) -> list[str]:
    """Sinkronkan jadwal dengan spesifikasi kode.

    - Job yang belum ada → dibuat.
    - Job yang sudah ada → `interval_s`/`payload_json`/`note` **disinkronkan** dengan kode
      (supaya perubahan rumus/parameter tidak diam-diam tertinggal di DB).
    - `enabled` **tidak pernah** diubah di sini: mematikan/menyalakan job adalah keputusan
      manusia, dan kode tidak boleh membatalkannya diam-diam.
    """
    ada = {j.name: j for j in s.scalars(select(Job)).all()}
    dibuat: list[str] = []
    for spec in specs:
        baris = ada.get(spec.name)
        if baris is None:
            s.add(
                Job(
                    name=spec.name,
                    interval_s=spec.interval_s,
                    enabled=spec.enabled,
                    payload_json=spec.payload,
                    note=spec.note,
                    next_run_at=datetime.now(UTC),
                )
            )
            dibuat.append(spec.name)
            continue
        baris.interval_s = spec.interval_s
        baris.payload_json = spec.payload
        baris.note = spec.note
    s.flush()
    return dibuat


def set_enabled(s: SASession, name: str, enabled: bool) -> bool:
    """Nyalakan/matikan job secara eksplisit (dipakai cutover & manusia). True bila berubah."""
    job = s.scalar(select(Job).where(Job.name == name))
    if job is None:
        return False
    if job.enabled == enabled:
        return False
    job.enabled = enabled
    if enabled:
        job.next_run_at = datetime.now(UTC)
    s.flush()
    return True


def due_jobs(s: SASession, now: datetime | None = None) -> list[Job]:
    """Job aktif yang sudah waktunya. Urut paling telat lebih dulu."""
    t = now or datetime.now(UTC)
    rows = s.scalars(
        select(Job)
        .where(Job.enabled.is_(True))
        .where((Job.next_run_at.is_(None)) | (Job.next_run_at <= t))
        .order_by(Job.next_run_at.asc().nulls_first())
    ).all()
    return list(rows)


def run_one(s: SASession, job: Job, now: datetime | None = None) -> tuple[str, str]:
    """Jalankan satu job. Status: ok | dilewati | gagal. Tidak pernah melempar ke pemanggil."""
    t = now or datetime.now(UTC)
    handler = HANDLERS.get(job.name)
    if handler is None:
        status, detail = "dilewati", f"tidak ada handler untuk job '{job.name}'"
    else:
        try:
            detail = handler(s, job) or ""
            status = "ok"
        except Exception as exc:  # noqa: BLE001 — kegagalan job harus tercatat, bukan mematikan loop
            status, detail = "gagal", f"{type(exc).__name__}: {exc}"

    job.last_run_at = t
    job.last_status = status
    job.last_detail = detail[:500]
    job.next_run_at = t + timedelta(seconds=max(1, job.interval_s))
    s.add(
        Event(
            type="job.ran",
            actor="worker",
            payload_json={"job": job.name, "status": status, "detail": job.last_detail},
            fact_ids=[],
            severity="info" if status == "ok" else "warning",
        )
    )
    s.flush()
    return status, detail


def run_due(s: SASession, now: datetime | None = None, limit: int = 10) -> list[dict[str, str]]:
    """Jalankan semua job yang jatuh tempo (maks `limit` per siklus)."""
    hasil: list[dict[str, str]] = []
    for job in due_jobs(s, now)[:limit]:
        status, detail = run_one(s, job, now)
        hasil.append({"job": job.name, "status": status, "detail": detail})
    return hasil