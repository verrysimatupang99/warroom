from __future__ import annotations

import logging
import subprocess
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session as SASession
from warroom_core.db import Alert, Event, Fact, Heartbeat, Job
from warroom_notifier.dispatch import kirim_tertunda

from .base import (
    _alert,
    _jalankan_lt,
    _unit_state,
    _upsert_service,
    publish_snapshot,
    root_dir,
    root_dir_repo,
)

log = logging.getLogger("warroom_worker.jobs")


def handler_publish_facts(s: SASession, job: Job) -> str:
    """Terbitkan `state/snapshot.json` → facts + event."""
    rel = str(job.payload_json.get("path", "state/snapshot.json"))
    ttl = int(job.payload_json.get("ttl_s", 600))
    path = root_dir() / rel
    rep = publish_snapshot(s, path, ttl_s=ttl, actor="worker")
    return f"status={rep.status} fakta={rep.facts} observed_at={rep.observed_at or '-'}"


def handler_freshness(s: SASession, job: Job) -> str:
    """Hitung umur fakta terbaru vs TTL; yang basi → Alert (dedupe) + event."""
    now = datetime.now(UTC)
    sub = (
        select(Fact.kind, Fact.key, func.max(Fact.observed_at).label("obs"))
        .group_by(Fact.kind, Fact.key)
        .subquery()
    )
    rows = s.scalars(
        select(Fact).join(
            sub,
            (Fact.kind == sub.c.kind) & (Fact.key == sub.c.key) & (Fact.observed_at == sub.c.obs),
        )
    ).all()

    # Toleransi GRACE (temuan audit 7 Okt): tanpa ini, setiap fakta snapshot WAJIB
    # melewati TTL-nya tepat sebelum penulisan berikutnya, karena penulisnya (refresh-snapshot
    # 15 mnt) hanya boleh TIDAK lebih cepat dari TTL. Akibatnya "data basi 13,3 mnt > ttl 600 s"
    # muncul untuk SEMUA kunci sekaligus — derau, bukan temuan; 32 alert palsu menumpuk.
    # Aturan: fakta dianggap basi hanya bila umurnya melewati 1,5× TTL (jadwal benar-benar
    # terlewat), dan toleransi minimum 15 menit supaya TTL pendek tidak berkedip.
    grace_min_s = float(job.payload_json.get("grace_min_s", 900))
    grace_faktor = float(job.payload_json.get("grace_faktor", 1.5))
    basi: list[Fact] = []
    for f in rows:
        umur = (now - f.observed_at).total_seconds()
        ambang = max(f.ttl_s * grace_faktor, f.ttl_s + grace_min_s)
        if umur > ambang:
            basi.append(f)

    # --- Pisahkan "basi karena pasar kering" (bukan masalah) dari "basi karena job gagal" ---
    # Temuan 9 Okt: subjek alert per-pair (`signal/ETHUSDT`, ...) membuat dedupe TIDAK menolong
    # saat banyak pair tua sekaligus — 12 alert serentak. Padahal `signal-sync` status `ok`,
    # hanya `sinyal=0` (pasar kering). Pair lama memang tak diperbarui bila tak ada sinyal baru:
    # itu WAJAR, bukan kegagalan. Alert untuk kondisi wajar = derau yang menenggelamkan alert
    # sungguhan. Aturan: fakta `signal` HANYA dianggap masalah bila job penulisnya (`signal-sync`)
    # sedang gagal; kalau tidak, ia dihitung sebagai `basi_wajar` (dicatat di event, tanpa alert).
    sinyal_penulis_gagal = False
    js = s.scalar(select(Job).where(Job.name == "signal-sync").limit(1))
    if js is not None and js.last_status not in ("ok", None):
        sinyal_penulis_gagal = True

    dibuat = 0
    basi_wajar = 0
    if job.payload_json.get("alert_on_basi", True):
        # Kelompokkan per (kind, sumber): satu alert mewakili BANYAK pair, bukan per-pair.
        # Dedupe `_alert` per-subjek lalu efektif untuk seluruh kelompok — tanpa mengubah
        # perilaku untuk fakta non-kelompok (mis. snapshot).
        grup: dict[tuple[str, str], list] = {}
        for f in basi:
            if f.kind == "signal" and not sinyal_penulis_gagal:
                basi_wajar += 1
                continue
            grup.setdefault((f.kind, f.source or "-"), []).append(f)

        for (kind, sumber), anggota in grup.items():
            anggota.sort(key=lambda x: x.observed_at)
            paling_baru = anggota[-1]
            umur_mnt = round((now - paling_baru.observed_at).total_seconds() / 60, 1)
            ambang_mnt = round(
                max(paling_baru.ttl_s * grace_faktor, paling_baru.ttl_s + grace_min_s) / 60
            )
            if len(anggota) == 1:
                subjek = f"{kind}/{paling_baru.key}"
                pesan = (
                    f"data basi: {subjek} umur {umur_mnt} mnt — melewati ambang "
                    f"{ambang_mnt} mnt (ttl {paling_baru.ttl_s} s + grace)"
                )
            else:
                contoh = ", ".join(x.key for x in anggota[:3])
                sisa = f" +{len(anggota) - 3} lain" if len(anggota) > 3 else ""
                subjek = f"{kind}/{sumber}" if sumber != "-" else f"{kind}/banyak"
                pesan = (
                    f"data basi: {len(anggota)} {kind} dari sumber '{sumber}' "
                    f"({contoh}{sisa}) — paling baru umur {umur_mnt} mnt, melewati ambang {ambang_mnt} mnt"
                )
            if _alert(
                s,
                subject=subjek,
                message=pesan,
                aksi=(
                    f"periksa sumber '{paling_baru.source}' (job yang menulisnya), "
                    f"lalu jalankan ulang job terkait"
                ),
                fact_ids=[f.id for f in anggota[:10]],
            ):
                dibuat += 1

        # Auto-pulih (rekomendasi #6: "selesaikan otomatis begitu pulih") — alert
        # 'data basi' ber-subjek {kind}/{sumber|key} diclose saat fakta yang
        # dimaksud SUDAH segar lagi. Tanpa ini, alert basi menggantung selamanya
        # walau sumber sudah pulih (kasus snapshot & lp_mark, 15 Okt).
        buka = s.scalars(
            select(Alert).where(Alert.ack_at.is_(None)).where(Alert.subject.like("%/%"))
        ).all()
        for a in buka:
            potongan = a.subject.split("/", 1)
            if len(potongan) != 2:
                continue
            kind_a, ident_a = potongan
            masih_basi = any(
                f.kind == kind_a and (f.key == ident_a or (f.source or "-") == ident_a)
                for f in basi
            )
            if not masih_basi:
                a.ack_at = now
                a.message = (a.message or "") + " | PULIH otomatis: fakta segar kembali"

    s.add(
        Event(
            type="freshness.checked",
            actor="worker",
            payload_json={
                "diperiksa": len(rows),
                "basi": len(basi),
                "basi_wajar": basi_wajar,
                "alert_baru": dibuat,
            },
            fact_ids=[f.id for f in basi],
            severity="warning" if (len(basi) - basi_wajar) else "info",
        )
    )
    return f"diperiksa={len(rows)} basi={len(basi)} basi_wajar={basi_wajar} alert_baru={dibuat}"


def handler_notify(s: SASession, job: Job) -> str:
    """Kirim alert terbuka lewat transport terkonfigurasi (P1-T8).

    Tanpa transport (default), alert tetap di DB dan dicatat `ok=false` — tidak pernah
    diklaim terkirim.
    """
    limit = int(job.payload_json.get("limit", 10))
    hasil = kirim_tertunda(s, limit=limit)
    if not hasil:
        return "tidak ada alert terbuka"
    dilewati = sum(1 for h in hasil if h.get("alert_id") is None)
    dicoba = [h for h in hasil if h.get("alert_id") is not None]
    ok = sum(1 for h in dicoba if h["ok"])
    ekor = f" dilewati={dilewati}" if dilewati else ""
    return f"dicoba={len(dicoba)} terkirim={ok} gagal={len(dicoba) - ok}{ekor}"


def handler_collect(s: SASession, job: Job) -> str:
    """`lt scan` (kandidat crypto, tanpa kuota Arjum) — dipindahkan dari timer domain."""
    return _jalankan_lt("scan", job, timeout_s=int(job.payload_json.get("timeout_s", 900)))


def handler_refresh_snapshot(s: SASession, job: Job) -> str:
    """`lt snapshot` — dipindahkan dari timer domain (irama 15 menit).

    `timeout_s` bawaan 300 detik terlalu ketat: begitu `bagian` bertambah (macro, lp, dst.)
    satu siklus bisa menembus 5 menit saat jaringan lambat — dan prosesnya dibunuh **di tengah
    tulis**, sehingga `state/snapshot.json` tinggal separuh (gejala: `bagian` kehilangan `lp`
    dan `macro` tanpa error apa pun). 900 detik = sama dengan anggaran job `collect`.
    """
    bawaan = int(job.payload_json.get("timeout_s", 900) or 900)
    return _jalankan_lt("snapshot", job, timeout_s=max(bawaan, 900))


def handler_radar_update(s: SASession, job: Job) -> str:
    """`lt radar-update` — radar rantai dijalankan **lokal** (recreate dari VM Azure).

    Sejak 6 Okt 2026 server Azure dimatikan; radar tidak lagi di-SSH dari sini, melainkan
    dijalankan di host ini dan hasilnya ditulis ke `state/radar_state.json`. Job terpisah
    (bukan menumpang `refresh-snapshot`) karena panggilan gmgn-cli bisa lambat: satu chain
    bisa menunggu rate-limit hingga puluhan detik.
    """
    bawaan = int(job.payload_json.get("timeout_s", 600) or 600)
    return _jalankan_lt("radar-update", job, timeout_s=max(bawaan, 600))


def handler_lp_mark(s: SASession, job: Job) -> str:
    """`lt lp-mark` — mark posisi LP paper dari pasar nyata → ledger + pakem.

    Read-only pasar (DexScreener per alamat pool). Tidak menyentuh wallet/venue.
    TTL fakta 2x interval: kalau sama, fakta selalu "basi" tepat sebelum run berikutnya.
    """
    return _jalankan_lt("lp-mark", job, timeout_s=int(job.payload_json.get("timeout_s", 300) or 300))


def handler_backup(s: SASession, job: Job) -> str:
    """Skrip backup domain (state + rotasi 14) — dipindahkan dari timer domain."""
    # 15 Okt: skrip pindah ke repo (packages/live-trading/scripts/ops) setelah
    # kode di luar repo diarsipkan — cari repo dulu, domain-home hanya fallback.
    kandidat = [
        root_dir_repo() / "packages" / "live-trading" / "scripts" / "ops" / "backup-state.sh",
        root_dir() / "scripts" / "ops" / "backup-state.sh",
    ]
    skrip = next((p for p in kandidat if p.exists()), kandidat[0])
    if not skrip.exists():
        raise FileNotFoundError(f"skrip backup domain tidak ada: {', '.join(str(p) for p in kandidat)}")
    hasil = subprocess.run(  # noqa: S603 — path tetap, dari repo domain yang tepercaya
        ["/bin/bash", str(skrip)],
        capture_output=True,
        text=True,
        timeout=int(job.payload_json.get("timeout_s", 600)),
        check=False,
        cwd=str(root_dir()),
    )
    baris = [b for b in hasil.stdout.splitlines() if "arsip:" in b or "GAGAL" in b]
    detail = baris[0] if baris else hasil.stdout.strip().splitlines()[-1:] or [""]
    detail = detail if isinstance(detail, str) else " ".join(detail)
    if hasil.returncode not in (0, 2):  # 2 = snapshot basi (peringatan), bukan kegagalan
        raise RuntimeError(f"backup keluar dengan kode {hasil.returncode}: {detail[:200]}")
    return f"kode={hasil.returncode} {detail[:180]}"


def handler_source_health(s: SASession, job: Job) -> str:
    """Tulis `services` + `heartbeats` dari status unit systemd (baca-saja, R3).

    Sebelum ini kedua tabel kosong sama sekali: pembacanya (`metrics.collect_readiness`,
    `stream`) sudah ada, tapi tak ada penulis → kesiapan selalu 'unknown'.

    Baca-saja mutlak: `systemctl show` tidak mengubah apa pun, tidak me-restart unit.
    Unit yang dipantau dibatasi daftar tetap di bawah supaya tidak menyapu seluruh host.
    """
    import socket

    host = str(job.payload_json.get("host") or socket.gethostname())
    units = job.payload_json.get("units") or [
        "warroom-api",
        "warroom-worker",
        "warroom-web",
        "nginx",
    ]

    now = datetime.now(UTC)
    ditulis = 0
    status_ringkas: dict[str, str] = {}
    for unit in units:
        aktif = _unit_state(unit)
        status_ringkas[unit] = aktif
        _upsert_service(s, host=host, unit=unit, status=aktif, detail={"sumber": "systemctl show"})
        # Denyut ditulis apa pun statusnya: yang penting "kapan terakhir dilihat", bukan tebakan.
        s.add(Heartbeat(host=host, unit=unit, beat_at=now, payload_json={"status": aktif}))
        ditulis += 1

    # Disk host — insiden 15 Okt (89%, sempat >95%): pemakaian > 80% = peringatan
    # ber-dedupe (_alert menahan duplikat selama alert lama terbuka). Baca-saja: `df`.
    import subprocess as _sp

    try:
        out = _sp.run(["df", "-P", "/"], capture_output=True, text=True, timeout=15).stdout
        pakai_pct = int(out.strip().splitlines()[-1].split()[4].rstrip("%"))
    except Exception as e:  # noqa: BLE001
        _alert(
            s, subject="ops/disk-baca",
            severity="warning",
            message=f"gagal membaca pemakaian disk: {type(e).__name__} {str(e)[:80]}",
            aksi="periksa df / dan unit host",
        )
    else:
        if pakai_pct >= 80:
            _alert(
                s, subject="ops/disk-80",
                severity="warning" if pakai_pct < 90 else "kritis",
                message=f"pemakaian disk / {pakai_pct}% (ambang 80%)",
                aksi=(
                    "rotasi log/journal, VACUUM/bersihkan snapshot lama, "
                    "periksa /root/warroom-archive sebelum menambah data"
                ),
            )
        elif pakai_pct < 78:
            # Pemulihan: kondisi pulih → alert disk yang masih terbuka diselesaikan
            # otomatis (rekomendasi #6 "selesai otomatis begitu pulih"), bukan
            # menunggu ack manual selamanya.
            pulih = s.scalar(
                select(Alert.id).where(Alert.subject == "ops/disk-80").where(Alert.ack_at.is_(None)).limit(1)
            )
            if pulih is not None:
                row = s.get(Alert, pulih)
                row.ack_at = now
                row.message = (row.message or "") + " | PULIH otomatis: pemakaian kembali < 78%"
        status_ringkas["disk_pct"] = str(pakai_pct)

    s.flush()
    ringkas = " ".join(f"{u}={status_ringkas[u]}" for u in units)
    return f"host={host} unit={ditulis} {ringkas} disk={status_ringkas.get('disk_pct', '?')}%"


