from __future__ import annotations

import csv
import json
import logging
import os
import subprocess
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as SASession
from warroom_core.db import Alert, Event, Fact, Heartbeat, Job
from warroom_core.telemetry_policy import is_retired
from warroom_notifier.dispatch import kirim_tertunda

from .base import (
    _alert,
    _jalankan_lt,
    _tulis_fakta,
    _unit_state,
    _upsert_service,
    publish_snapshot,
    root_dir,
    root_dir_repo,
)

log = logging.getLogger("warroom_worker.jobs")


def audit_kesegaran(
    s: SASession,
    rows: list[Fact],
    basi: list[Fact],
    *,
    now: datetime,
    jendela_hari: int = 7,
) -> dict[str, Any]:
    """Rekap kesegaran per sumber + peringkat sumber paling sering basi.

    Bagian pertama dari fakta TERBARU per kunci (umur vs ttl masing-masing);
    bagian kedua dari riwayat alert `data basi` pada jendela tertentu — frekuensi
    kejadian, bukan satu momen. Tanpa riwayat, "paling sering basi" hanya bisa
    ditebak dari snapshot sesaat.
    """
    per_sumber: dict[str, dict[str, Any]] = {}

    def _entri(nama: str) -> dict[str, Any]:
        return per_sumber.setdefault(
            nama, {"fakta": 0, "basi": 0, "umur_maks_mnt": 0.0, "ttl_s": []}
        )

    for f in rows:
        e = _entri(f.source or "-")
        e["fakta"] += 1
        umur_mnt = round((now - f.observed_at).total_seconds() / 60, 1)
        e["umur_maks_mnt"] = max(e["umur_maks_mnt"], umur_mnt)
        if f.ttl_s not in e["ttl_s"]:
            e["ttl_s"].append(f.ttl_s)
    for f in basi:
        _entri(f.source or "-")["basi"] += 1

    sejak = now - timedelta(days=max(1, jendela_hari))
    riwayat = s.scalars(
        select(Alert).where(Alert.message.like("data basi%")).where(Alert.created_at >= sejak)
    ).all()
    kejadian: dict[str, int] = {}
    for a in riwayat:
        kejadian[a.subject] = kejadian.get(a.subject, 0) + 1
    return {
        "per_sumber": per_sumber,
        "kejadian_basi": dict(sorted(kejadian.items(), key=lambda kv: -kv[1])[:5]),
        "jendela_hari": jendela_hari,
    }


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
        if is_retired(f.kind, f.key):
            continue
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
        #
        # Batas yang penting: hanya alert yang BENAR-BENAR milik job ini (pesannya
        # berpola 'data basi:') yang boleh ditutup di sini. Sebelumnya filternya
        # hanya "subjek memuat /", sehingga alert domain lain yang kebetulan
        # bersubjek sama (mis. alert siklus hidup strategi) ikut ter-ack otomatis
        # lima menit setelah dibuat — alert keselamatan uang hilang tanpa jejak
        # keputusan siapa pun.
        buka = s.scalars(
            select(Alert)
            .where(Alert.ack_at.is_(None))
            .where(Alert.subject.like("%/%"))
            .where(Alert.message.like("data basi:%"))
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

    audit = audit_kesegaran(
        s,
        rows,
        basi,
        now=now,
        jendela_hari=int(job.payload_json.get("audit_jendela_hari", 7)),
    )
    s.add(
        Event(
            type="freshness.checked",
            actor="worker",
            payload_json={
                "diperiksa": len(rows),
                "basi": len(basi),
                "basi_wajar": basi_wajar,
                "alert_baru": dibuat,
                "audit_sumber": audit,
            },
            fact_ids=[f.id for f in basi],
            severity="warning" if (len(basi) - basi_wajar) else "info",
        )
    )
    paling = next(iter(audit["kejadian_basi"]), "-")
    return (
        f"diperiksa={len(rows)} basi={len(basi)} basi_wajar={basi_wajar} "
        f"alert_baru={dibuat} paling_sering_basi={paling}"
    )


def _tanggal_benched(subject: str) -> date | None:
    """Tanggal WIB di ekor subjek `strategi/benched:<strategi>:<YYYY-MM-DD>`."""
    ekor = subject.rsplit(":", 1)[-1]
    try:
        return datetime.strptime(ekor, "%Y-%m-%d").date()
    except ValueError:
        return None


def _tutup_benched_lampau(s: SASession, *, now: datetime) -> int:
    """Tutup alert 'benched' dari hari sebelumnya.

    Batas harian per strategi berakhir saat hari berganti; alert kemarin bukan
    kondisi yang masih berjalan. Tanpa ini, satu alert per hari menumpuk selamanya
    dan menenggelamkan alert sungguhan (10 alert terbuka pada 30 Okt, semuanya
    `strategi/benched:legacy-smc` dari hari-hari sebelumnya).
    """
    hari_ini = (now + timedelta(hours=7)).date()  # WIB, sama dengan pemilih `hari`
    buka = s.scalars(
        select(Alert)
        .where(Alert.subject.like("strategi/benched:%"))
        .where(Alert.ack_at.is_(None))
    ).all()
    ditutup = 0
    for a in buka:
        tanggal = _tanggal_benched(a.subject)
        # Subjek lama tanpa tanggal juga stale: format itu tidak dibuat lagi.
        if tanggal is not None and tanggal >= hari_ini:
            continue
        a.ack_at = now
        a.message = (a.message or "") + " | PULIH otomatis: hari berganti"
        ditutup += 1
    return ditutup


def handler_notify(s: SASession, job: Job) -> str:
    """Kirim alert terbuka lewat transport terkonfigurasi (P1-T8).

    Tanpa transport (default), alert tetap di DB dan dicatat `ok=false` — tidak pernah
    diklaim terkirim.
    """
    limit = int(job.payload_json.get("limit", 10))
    ditutup = _tutup_benched_lampau(s, now=datetime.now(UTC))
    hasil = kirim_tertunda(s, limit=limit)
    awalan = f"benched_lampau={ditutup} " if ditutup else ""
    if not hasil:
        return f"{awalan}tidak ada alert terbuka".strip()
    dilewati = sum(1 for h in hasil if h.get("alert_id") is None)
    dicoba = [h for h in hasil if h.get("alert_id") is not None]
    ok = sum(1 for h in dicoba if h["ok"])
    ekor = f" dilewati={dilewati}" if dilewati else ""
    return f"{awalan}dicoba={len(dicoba)} terkirim={ok} gagal={len(dicoba) - ok}{ekor}"


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


# --- watchdog forward test -------------------------------------------------------------
# Dua kegagalan yang membuat bukti forward test bohong tanpa suara:
#   1. EA berhenti mengirim telemetri di tengah sesi 08–09 → tidak ada trade yang dievaluasi,
#      dan tidak ada yang tahu sampai sesi habis.
#   2. EA melaporkan `total_trades_today` bertambah, tetapi tidak ada baris baru di
#      `deals.csv` → trade tertutup hilang dari jurnal.
# Keduanya dibandingkan dengan DATA, bukan tebakan: fakta `mt5_snapshot` dan berkas deal.

DEALS_DEFAULT = Path("/var/lib/warroom/deals.csv")
WATCHDOG_STATE_DEFAULT = Path("/var/lib/warroom/forwardtest_watchdog.json")


def _snapshot_mt5_terbaru(s: SASession) -> tuple[Fact | None, dict[str, Any]]:
    f = s.scalar(
        select(Fact).where(Fact.kind == "mt5_snapshot").order_by(Fact.observed_at.desc()).limit(1)
    )
    if f is None:
        return None, {}
    v = f.value_json
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            v = {}
    return f, dict(v) if isinstance(v, dict) else {}


def _tiket_deal(path: Path) -> set[str]:
    """Tiket unik dari deals.csv. Berkas tidak ada/rusak = kosong, bukan exception."""
    if not path.exists():
        return set()
    try:
        with path.open(newline="", encoding="utf-8", errors="replace") as f:
            return {str(r.get("ticket") or "").strip() for r in csv.DictReader(f)} - {""}
    except OSError:
        return set()


def _muat_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _simpan_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _tutup_alert(s: SASession, subject: str, alasan: str, *, now: datetime) -> bool:
    """Selesaikan alert yang masih terbuka untuk subjek ini (pemulihan otomatis)."""
    a = s.scalar(
        select(Alert).where(Alert.subject == subject).where(Alert.ack_at.is_(None)).limit(1)
    )
    if a is None:
        return False
    a.ack_at = now
    a.message = (a.message or "") + f" | PULIH otomatis: {alasan}"
    return True


def _jam_server(snapshot: dict[str, Any], umur_s: float) -> datetime | None:
    """Perkiraan jam server broker sekarang.

    `server_time` adalah epoch jam dinding server (TimeCurrent()), bukan UTC. Menambahkan
    umur fakta membuat perkiraan ini tetap jalan walau EA sudah berhenti — justru kasus
    yang ingin dideteksi.
    """
    st = snapshot.get("server_time")
    if not isinstance(st, (int, float)) or st <= 0:
        return None
    return datetime.fromtimestamp(float(st) + max(0.0, umur_s), UTC)


def handler_forwardtest_watchdog(s: SASession, job: Job) -> str:
    """Alert bila telemetri mati saat sesi, atau deal tertutup tidak masuk `deals.csv`."""
    now = datetime.now(UTC)
    p = job.payload_json or {}
    max_umur_s = float(p.get("max_umur_s", 120))
    grace_s = float(p.get("deal_grace_s", 300))
    jam_mulai = int(p.get("sesi_mulai", 8))
    jam_selesai = int(p.get("sesi_selesai", 9))
    deals_path = Path(p.get("deals_path", str(DEALS_DEFAULT)))
    state_path = Path(p.get("state_path", str(WATCHDOG_STATE_DEFAULT)))

    f, snap = _snapshot_mt5_terbaru(s)
    if f is None:
        return "tidak ada fakta mt5_snapshot; watchdog menunggu telemetri"

    umur_s = max(0.0, (now - f.observed_at).total_seconds())
    jam = _jam_server(snap, umur_s)
    dalam_sesi = bool(
        jam is not None
        and jam.weekday() < 5
        and jam_mulai <= jam.hour < jam_selesai
    )
    alert_baru = 0
    pulih = 0

    # 1) Telemetri mati di tengah sesi.
    if dalam_sesi and umur_s > max_umur_s:
        if _alert(
            s,
            subject="forwardtest/telemetri",
            severity="kritis",
            message=(
                f"telemetri MT5 berhenti {umur_s:.0f} s saat sesi Reaper "
                f"({jam:%H:%M} server) — melewati ambang {max_umur_s:.0f} s"
            ),
            aksi=(
                "periksa EA di VM Azure (terminal hidup, AutoTrading, koneksi broker), "
                "lalu cek /api/v1/tencent/mt5/status"
            ),
            fact_ids=[f.id],
        ):
            alert_baru += 1
    elif umur_s <= max_umur_s and _tutup_alert(
        s, "forwardtest/telemetri", f"telemetri segar lagi ({umur_s:.0f} s)", now=now
    ):
        pulih += 1

    # 2) Deal tertutup tidak tercatat. Dihitung dari selisih kumulatif: total deal hari ini
    #    yang dilaporkan EA vs baris baru di deals.csv. Selisih tidak hilang sampai ada
    #    baris deal yang menutupnya.
    total = snap.get("total_trades_today")
    total = int(total) if isinstance(total, (int, float)) else None
    jumlah_deal = len(_tiket_deal(deals_path))
    tanggal = (jam or now).date().isoformat()
    state = _muat_state(state_path)
    selisih = 0
    hilang_sejak: str | None = None

    if total is None:
        detail_deal = "total_trades_today tidak dikirim EA"
    else:
        if state.get("tanggal") != tanggal:
            # Hari server baru (atau run pertama): jadikan kondisi sekarang sebagai baseline.
            state = {"tanggal": tanggal, "total": total, "deal": jumlah_deal}
        selisih_lama = max(0, int(state.get("selisih", 0) or 0))
        sebelumnya_total = state.get("total")
        sebelumnya_deal = state.get("deal")
        prev_total = int(sebelumnya_total) if isinstance(sebelumnya_total, (int, float)) else total
        prev_deal = int(sebelumnya_deal) if isinstance(sebelumnya_deal, (int, float)) else jumlah_deal
        tambah_total = max(0, total - prev_total)
        tambah_deal = max(0, jumlah_deal - prev_deal)
        selisih = max(0, selisih_lama + tambah_total - tambah_deal)
        if selisih > 0:
            hilang_sejak = str(state.get("hilang_sejak") or now.isoformat())
        detail_deal = f"total_hari_ini={total} deal_csv={jumlah_deal} selisih={selisih}"

        if selisih > 0 and hilang_sejak:
            sejak = datetime.fromisoformat(hilang_sejak)
            if (now - sejak).total_seconds() >= grace_s:
                if _alert(
                    s,
                    subject="forwardtest/deal-hilang",
                    severity="kritis",
                    message=(
                        f"{selisih} deal tertutup belum masuk deals.csv "
                        f"(EA total hari ini {total}, tercatat {jumlah_deal}); "
                        f"menunggu {int((now - sejak).total_seconds())} s"
                    ),
                    aksi=(
                        "periksa log EA (OnTradeTransaction / POST /mt5/deal), "
                        "lalu cocokkan dengan statement MT5"
                    ),
                ):
                    alert_baru += 1
        elif selisih == 0 and _tutup_alert(
            s, "forwardtest/deal-hilang", "semua deal tertutup sudah tercatat", now=now
        ):
            pulih += 1

        state.update(
            {
                "tanggal": tanggal,
                "total": total,
                "deal": jumlah_deal,
                "selisih": selisih,
                "hilang_sejak": hilang_sejak if selisih > 0 else None,
                "diperiksa": now.isoformat(),
            }
        )
        _simpan_state(state_path, state)

    if alert_baru or pulih:
        s.add(
            Event(
                type="forwardtest.watchdog",
                actor="worker",
                payload_json={
                    "umur_telemetri_s": round(umur_s, 1),
                    "dalam_sesi": dalam_sesi,
                    "jam_server": jam.isoformat() if jam else None,
                    "total_trades_today": total,
                    "deal_csv": jumlah_deal,
                    "selisih": selisih,
                    "alert_baru": alert_baru,
                    "pulih": pulih,
                },
                severity="warning" if alert_baru else "info",
            )
        )

    return (
        f"umur={umur_s:.0f}s sesi={'ya' if dalam_sesi else 'tidak'} "
        f"{detail_deal} alert={alert_baru} pulih={pulih}"
    )




def handler_job_health(s: SASession, job: Job) -> str:
    """Alert bila job aktif gagal atau tidak jalan melewati 3x intervalnya.

    `freshness` hanya melihat umur fakta; job yang tidak menulis fakta (mis. backup,
    retention, source-health) bisa mati tanpa alarm. DeepSeek 2026 menunjukkan 90%
    respons cron gagal dan tidak ada yang tahu sampai dibaca manual.
    """
    now = datetime.now(UTC)
    p = job.payload_json or {}
    faktor = float(p.get("stale_factor", 3))
    min_stale = float(p.get("min_stale_s", 900))
    alert_baru = 0
    pulih = 0
    diperiksa = 0
    for j in s.scalars(select(Job).where(Job.enabled.is_(True))).all():
        if j.name == job.name or j.last_run_at is None:
            continue
        diperiksa += 1
        umur = max(0.0, (now - j.last_run_at).total_seconds())
        batas = max(faktor * j.interval_s, min_stale)
        stale = umur > batas
        gagal = str(j.last_status or "") == "gagal"
        subjek = f"job/{j.name}"
        if gagal or stale:
            alasan = []
            if gagal:
                alasan.append(f"status terakhir gagal: {j.last_detail[-120:] if j.last_detail else '-'}")
            if stale:
                alasan.append(f"tidak jalan {umur / 60:.1f} mnt (batas {batas / 60:.1f} mnt)")
            if _alert(
                s,
                subject=subjek,
                severity="warning",
                message=f"job {j.name}: " + "; ".join(alasan),
                aksi=(
                    f"periksa `journalctl -u warroom-worker` dan baris jobs '{j.name}'; "
                    "jalankan ulang setelah penyebabnya jelas"
                ),
            ):
                alert_baru += 1
        elif _tutup_alert(s, subjek, "job kembali ok dan tepat waktu", now=now):
            pulih += 1
    if alert_baru or pulih:
        s.add(
            Event(
                type="job.health",
                actor="worker",
                payload_json={"diperiksa": diperiksa, "alert_baru": alert_baru, "pulih": pulih},
                severity="warning" if alert_baru else "info",
            )
        )
    return f"diperiksa={diperiksa} alert={alert_baru} pulih={pulih}"


def handler_denyut(s: SASession, job: Job) -> str:
    """Denyut Telegram berkala: ringkasan kesehatan 6 jam terakhir sebagai alert `info`.

    Dikirim lewat `notify` seperti alert lain (auto-ack saat terkirim), jadi tiap
    siklus = 1 pesan Telegram. Isinya jujur dari DB: fakta baru, alert terbuka,
    job yang status terakhirnya gagal. Bila transport mati, alert menumpuk di DB
    dan tidak diklaim terkirim.
    """
    now = datetime.now(UTC)
    sejak = now - timedelta(hours=6)
    fakta_baru = s.scalar(
        select(func.count()).select_from(Fact).where(Fact.observed_at >= sejak)
    ) or 0
    terbuka = s.scalar(
        select(func.count()).select_from(Alert).where(Alert.ack_at.is_(None))
    ) or 0
    gagal = [
        j.name
        for j in s.scalars(select(Job).where(Job.enabled.is_(True))).all()
        if str(j.last_status or "") == "gagal"
    ]
    pesan = (
        f"denyut war-room 6 jam: fakta_baru={fakta_baru} alert_terbuka={terbuka} "
        f"job_gagal={','.join(sorted(gagal)) if gagal else '-'}"
    )
    dibuat = _alert(
        s,
        subject="denyut/war-room",
        severity="info",
        message=pesan,
        aksi="tidak perlu aksi bila angka wajar; selidiki bila job_gagal terisi",
    )
    return f"{pesan} alert_baru={int(dibuat)}"


def evaluate_slo(
    *,
    disk_pct: float,
    backup_age_h: float | None,
    drill_age_d: float | None,
    api_ok: bool,
    p95_ms: float = 0.0,
    requests_total: int = 0,
    error_rate: float = 0.0,
    disk_warn: float = 80.0,
    disk_crit: float = 90.0,
    backup_max_h: float = 26.0,
    drill_max_d: float = 35.0,
    p95_max_ms: float = 1000.0,
    error_rate_max: float = 0.01,
    min_requests: int = 20,
) -> list[dict[str, str]]:
    """Ambang SLO yang disetujui owner 1 Nov 2026. Murni, supaya bisa diuji."""
    temuan: list[dict[str, str]] = []
    if disk_pct >= disk_crit:
        temuan.append({"kode": "disk", "severity": "critical",
                       "pesan": f"disk {disk_pct:.1f}% (crit {disk_crit:.0f}%)"})
    elif disk_pct >= disk_warn:
        temuan.append({"kode": "disk", "severity": "warning",
                       "pesan": f"disk {disk_pct:.1f}% (warn {disk_warn:.0f}%)"})
    if backup_age_h is None or backup_age_h > backup_max_h:
        umur = "tidak ada dump" if backup_age_h is None else f"{backup_age_h:.1f} jam"
        temuan.append({"kode": "backup", "severity": "warning",
                       "pesan": f"backup Postgres {umur} (batas {backup_max_h:.0f} jam)"})
    if drill_age_d is None or drill_age_d > drill_max_d:
        umur = "belum pernah" if drill_age_d is None else f"{drill_age_d:.0f} hari"
        temuan.append({"kode": "drill", "severity": "warning",
                       "pesan": f"drill restore {umur} (batas {drill_max_d:.0f} hari)"})
    if not api_ok:
        temuan.append({"kode": "api", "severity": "warning",
                       "pesan": "probe /api/v1/build gagal"})
    if requests_total >= min_requests and p95_ms > p95_max_ms:
        temuan.append({"kode": "latency", "severity": "warning",
                       "pesan": f"p95 API {p95_ms:.0f} ms > {p95_max_ms:.0f} ms "
                                f"({requests_total} request)"})
    if requests_total >= min_requests and error_rate > error_rate_max:
        temuan.append({"kode": "error_rate", "severity": "warning",
                       "pesan": f"error 5xx {error_rate * 100:.2f}% > {error_rate_max * 100:.1f}% "
                                f"({requests_total} request)"})
    return temuan


def _umur_jam(path: Path, now: datetime) -> float | None:
    try:
        return (now - datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)).total_seconds() / 3600
    except OSError:
        return None


def handler_slo_check(s: SASession, job: Job) -> str:
    """Periksa ambang SLO yang bisa diukur dari host; alert ber-dedupe + auto-ack."""
    import shutil
    import urllib.request

    now = datetime.now(UTC)
    p = job.payload_json or {}
    disk = shutil.disk_usage("/")
    disk_pct = disk.used / disk.total * 100

    dumps = sorted(Path("/home/admin/backups/postgres").glob("warroom-*.dump"))
    backup_age_h = _umur_jam(dumps[-1], now) if dumps else None

    drill_age_d = None
    try:
        bukti = json.loads(Path("/var/lib/warroom/restore-drill/last.json").read_text("utf-8"))
        selesai = datetime.fromisoformat(bukti["selesai_at"])
        drill_age_d = (now - selesai).total_seconds() / 86400
    except (OSError, KeyError, ValueError, json.JSONDecodeError):
        drill_age_d = None

    api_ok = False
    try:
        with urllib.request.urlopen("http://127.0.0.1:8800/api/v1/build", timeout=5) as r:
            api_ok = r.status == 200
    except OSError:
        api_ok = False

    http: dict[str, float] = {}
    try:
        with urllib.request.urlopen("http://127.0.0.1:8800/metrics", timeout=5) as r:
            for baris in r.read().decode("utf-8", "replace").splitlines():
                if baris.startswith("warroom_http_") and " " in baris:
                    nama, nilai = baris.rsplit(" ", 1)
                    http[nama] = float(nilai)
    except (OSError, ValueError):
        http = {}

    temuan = evaluate_slo(
        disk_pct=disk_pct,
        p95_ms=float(http.get("warroom_http_latency_p95_ms", 0.0)),
        requests_total=int(http.get("warroom_http_requests_total", 0)),
        error_rate=float(http.get("warroom_http_error_rate", 0.0)),
        backup_age_h=backup_age_h,
        drill_age_d=drill_age_d,
        api_ok=api_ok,
        disk_warn=float(p.get("disk_warn", 80)),
        disk_crit=float(p.get("disk_crit", 90)),
        backup_max_h=float(p.get("backup_max_h", 26)),
        drill_max_d=float(p.get("drill_max_d", 35)),
    )
    kode_aktif = {t["kode"] for t in temuan}
    alert = 0
    pulih = 0
    for t in temuan:
        if _alert(s, subject=f"slo/{t['kode']}", severity=t["severity"],
                  message=t["pesan"], aksi="periksa dashboard /sistem dan log unit terkait"):
            alert += 1
    for kode in ("disk", "backup", "drill", "api", "latency", "error_rate"):
        if kode not in kode_aktif and _tutup_alert(s, f"slo/{kode}", "SLO kembali normal", now=now):
            pulih += 1

    _tulis_fakta(
        s, kind="slo", key="ringkas",
        value={
            "disk_pct": round(disk_pct, 1),
            "backup_age_h": round(backup_age_h, 1) if backup_age_h is not None else None,
            "drill_age_d": round(drill_age_d, 1) if drill_age_d is not None else None,
            "api_ok": api_ok,
            "temuan": temuan,
            "checked_at": now.isoformat(),
        },
        source="handler slo-check", ttl_s=int(p.get("ttl_s", 180)),
    )
    return (
        f"disk={disk_pct:.1f}% backup_h={backup_age_h} drill_d={drill_age_d} "
        f"api={api_ok} alert={alert} pulih={pulih}"
    )
