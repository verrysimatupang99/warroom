"""Implementasi job worker (P1-T4) + notifikasi alert (P1-T8).

Setiap handler menerima `(session, job)` dan mengembalikan string detail untuk `jobs.last_detail`.
Handler **tidak boleh** menelan kegagalan diam-diam: `schedule.run_one` yang menangkap dan mencatat.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as SASession
from warroom_core import autonomy
from warroom_core.db import Alert, Event, Fact, Heartbeat, Job, Service
from warroom_core.gate import DEFAULT_DEFF, GATE_DEFAULT_MIN_N, GATE_TOOL_CI
from warroom_notifier.dispatch import kirim_tertunda

from warroom_worker import schedule
from warroom_worker.facts_publish import canonical_hash, publish_snapshot

__all__ = [
    "handler_backup",
    "handler_collect",
    "handler_freshness",
    "handler_lp_mark",
    "handler_notify",
    "handler_publish_facts",
    "handler_radar_update",
    "handler_refresh_snapshot",
    "handler_signal_sync",
    "handler_source_health",
    "register_handlers",
    "root_dir",
]

# Alert dengan subjek yang sama tidak dibuat ulang SELAMA masih ada alert belum di-ack.
# (Dulu berbasis jendela waktu tetap: karena jeda nyata antar-run selalu sedikit lebih lama
# dari interval job, jendela yang setara interval selalu meleset → alert menumpuk tanpa batas
# untuk kondisi yang tidak berubah. Terbukti: 9 alert `learner/ringkas` + 13 `poly/klaim-uang`.)


def root_dir() -> Path:
    """Direktori domain (live-trading). Bisa ditimpa lewat env `WARROOM_DOMAIN_HOME`."""
    import os

    return Path(os.environ.get("WARROOM_DOMAIN_HOME", str(Path.home() / "live-trading")))


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
    skrip = root_dir() / "scripts" / "ops" / "backup-state.sh"
    if not skrip.exists():
        raise FileNotFoundError(f"skrip backup domain tidak ada: {skrip}")
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


def _lt_bin() -> Path:
    """Lokasi CLI `lt` yang benar — dari venv tempat worker ini berjalan.

    Kenapa tidak dari `root_dir()/.venv`: `root_dir()` adalah `WARROOM_DOMAIN_HOME`
    (`/home/admin/live-trading`), dan folder itu masih menyimpan **venv lama** yang meng-import
    dari source lama (`/home/admin/live-trading/src`). Akibatnya setiap job yang memanggil `lt`
    menjalankan kode sebelum merge: `lt snapshot` menghasilkan `bagian` yang lebih sedikit
    (macro/lp/overextended hilang) tanpa error apa pun — dan penjaga anti-snapshot-separuh pun
    tidak menangkapnya, karena kode lama itu melaporkan bagian yang sama dengan yang ia tulis.

    Venv worker sendiri (`sys.executable`) selalu menunjuk paket repo, jadi itu yang dipakai.
    """
    kandidat = Path(sys.executable).parent / "lt"
    if kandidat.exists():
        return kandidat
    return root_dir() / ".venv" / "bin" / "lt"


def _jalankan_lt(subperintah: str, job: Job, *, timeout_s: int) -> str:
    """Jalankan CLI domain (`lt <subperintah>`) sebagai subproses.

    Memakai entry point venv langsung (bukan `uv run`) supaya tidak membangun ulang
    lingkungan pada setiap job. Keluaran disimpan ringkas; yang penting jejaknya.
    """
    lt = _lt_bin()
    if not lt.exists():
        raise FileNotFoundError(f"CLI domain tidak ada: {lt}")
    hasil = subprocess.run(  # noqa: S603 — path tetap, dari repo domain yang tepercaya
        [str(lt), subperintah],
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
        cwd=str(root_dir()),
        env={**os.environ, "LT_HOME": str(root_dir())},
    )
    if hasil.returncode != 0:
        raise RuntimeError(
            f"lt {subperintah} gagal (kode {hasil.returncode}): {hasil.stderr.strip()[:200]}"
        )
    # Penjaga anti-snapshot-separuh. Snapshot ditulis dengan `write_text` (bukan atomik), jadi
    # satu-satunya cara sebuah bagian ("bagian") bisa HILANG sementara prosesnya keluar kode 0
    # adalah snapshot ditulis oleh **kode lama** — mis. satu layanan lain yang masih menjalankan
    # salinan lama dan menimpa berkas state yang sama. Menyimpan bagian-bagian yang sudah
    # dilaporkan ringkasan stdout lalu membandingkannya membuat keadaan itu **kelihatan**,
    # bukan lewat begitu saja dengan status "ok".
    ringkas = [b.strip() for b in hasil.stdout.splitlines() if b.strip()]
    dilaporkan = {b.split()[0] for b in ringkas if b.split() and b.split()[-1] == "ok"}
    ditulis = set()
    if subperintah == "snapshot":
        try:
            snap = json.loads((Path(root_dir()) / "state" / "snapshot.json").read_text("utf-8"))
            ditulis = set((snap.get("bagian") or {}).keys())
        except (OSError, json.JSONDecodeError):
            ditulis = set()
        hilang = sorted(dilaporkan - ditulis)
        if hilang:
            raise RuntimeError(
                f"snapshot tidak lengkap: {hilang} dilaporkan ok tetapi tidak ada di berkas — "
                "berkas kemungkinan ditimpa oleh kode lama (unit lain yang belum ikut diperbarui)"
            )
    return f"lt {subperintah} ok; " + " | ".join(ringkas[-3:])[:240]


def handler_poly_sync(s: SASession, job: Job) -> str:
    """Terbitkan fakta dari proyek Polymarket (arm, agen, dataset) — baca-saja (P4-T1)."""
    from warroom_worker.adapters import poly

    dasar = str(job.payload_json.get("base", "/var/lib"))
    ttl = int(job.payload_json.get("ttl_s", 1800))
    jumlah = 0

    arms = poly.arms(dasar)
    for nama, isi in arms.items():
        _tulis_fakta(s, kind="poly.arm", key=nama, value=isi,
                     source=f"{isi['dir']}/execution-paper-shadow-summary.json", ttl_s=ttl)
        jumlah += 1

    agen = poly.agent_ringkas()
    _tulis_fakta(s, kind="poly.agent", key="ringkas", value=agen,
                 source=f"{poly.AGENT_DIR}/agent-summary.json", ttl_s=ttl)
    jumlah += 1

    ds = poly.datasets_ringkas()
    _tulis_fakta(s, kind="poly.dataset", key="recorder", value=ds,
                 source=f"{poly.RESEARCH_DIR}", ttl_s=ttl * 6)
    jumlah += 1

    # Cakupan baca ditampilkan apa adanya: sebagian sumber milik user lain dan hanya bisa
    # dibaca lewat allowlist sudo yang sudah ada. Yang tidak terbaca BUKAN nol — ia "tidak-izin".
    ringkas_akses = {
        "arm_summary": arms["B-kandidat"]["summary"].get("status"),
        "arm_jsonl": arms["B-kandidat"]["jsonl_status"],
        "agen_summary": agen["summary_status"],
        "agen_lessons_n": agen["lessons"]["n"],
        "agen_upgrades_n": agen["upgrades"]["n"],
        "dataset_paired": ds["paired"].get("status"),
    }
    _tulis_fakta(s, kind="poly.akses", key="cakupan", value=ringkas_akses,
                 source="allowlist sudo + izin berkas", ttl_s=ttl)
    jumlah += 1

    return (
        f"fakta={jumlah} arm={len(arms)} arm_summary={ringkas_akses['arm_summary']} "
        f"agen_summary={agen['summary_status']} lessons={agen['lessons']['n']} "
        f"dataset={ds['paired'].get('status')}"
    )


def handler_verdict_sync(s: SASession, job: Job) -> str:
    """Terbitkan fakta `verdict` dari alat Poly — baca-saja, untuk GateMeter (W2).

    Nilai = keluaran apa adanya ``qa/favorite-live-verdict.py --json`` + kontrak yang
    dibaca UI (``n``, ``win``, ``be`` pecahan, ``ci``, ``deff``) supaya `/gate/evaluate`
    menilai dengan kebijakan yang SAMA seperti alat Poly (95% + koreksi klaster).
    ``split`` sengaja tidak diisi: tanpa split beku, gate jujur menjawab `insufficient`.
    """
    from warroom_worker.adapters import poly

    v = poly.verdict_favorit()
    ttl = int(job.payload_json.get("ttl_s", 1800))
    if v.get("status") != "ok":
        _tulis_fakta(
            s, kind="poly.verdict", key="verdict",
            value={"status": v.get("status"), "detail": v.get("detail")},
            source=str(v.get("sumber")), ttl_s=ttl,
        )
        return f"verdict={v.get('status')} detail={str(v.get('detail'))[:80]}"

    d = v["value"]
    nilai: dict[str, Any] = {
        # Kontrak GateBlok (apps/web …/GateBlok.svelte): n, win, be (pecahan 0..1) + opsional.
        "n": d.get("n"),
        "win": d.get("wins"),
        "be": (float(d.get("breakEven") or 0.0)) / 100.0,
        # Kebijakan alat Poly (Wilson 95% + koreksi klaster) — sumber tunggal di gate core.
        "ci": GATE_TOOL_CI,
        "deff": d.get("deff") or DEFAULT_DEFF,
        "min_n": GATE_DEFAULT_MIN_N,
        "split": None,
        "rule": "favorit btc/eth (band 0,70–0,95)",
        # Untuk tampilan + audit — nilai mentah alat, bukan hitungan ulang.
        "winRate": d.get("winRate"),
        "ask": d.get("ask"),
        "breakEven_pct": d.get("breakEven"),
        "evPerStake": d.get("evPerStake"),
        "ci95": d.get("ci95"),
        "nEff": d.get("nEff"),
        "rho": d.get("rho"),
        "nNeeded": d.get("nNeeded"),
        "verdict_alat": d.get("verdict"),
        "coins": d.get("coins"),
        "windows": d.get("windows"),
        "kebijakan_alat": "Wilson 95% dua sisi + koreksi klaster (deff)",
        "status": "ok",
    }
    _tulis_fakta(
        s, kind="poly.verdict", key="verdict", value=nilai,
        source=f"{v['sumber']} --json (baca-saja)", ttl_s=ttl,
    )
    return (
        f"n={nilai['n']} win={nilai['win']} be={nilai['be']:.4f} "
        f"deff={nilai['deff']} alat={nilai['verdict_alat']}"
    )


def handler_parity_drift(s: SASession, job: Job) -> str:
    """Bandingkan mirror vs eksekutor; drift > 0 → alert (P4-T2)."""
    from warroom_worker.adapters import poly

    d = poly.parity_drift(n=int(job.payload_json.get("n", 400)))
    _tulis_fakta(
        s, kind="poly.parity", key="drift",
        value={"status": d.status, "drift": d.drift, "mirror_n": d.mirror_n,
               "executor_n": d.executor_n, "contoh": d.contoh, "detail": d.detail},
        source="execution-paper-shadow.jsonl (mirror vs pilot)", ttl_s=1800,
    )
    if d.status == "ok" and d.drift > 0:
        _alert(s, subject="poly/parity-drift", message=f"drift keputusan mirror vs eksekutor: {d.drift}",
               aksi="periksa predikat/label alasan di kedua jalur sebelum mempercayai mirror",
               severity="warning")
    return f"status={d.status} drift={d.drift} mirror={d.mirror_n} eksekutor={d.executor_n}"


def handler_lpagent_sync(s: SASession, job: Job) -> str:
    """Terbitkan telemetri pool likuiditas Solana/Meteora dari LP Agent (baca-saja).

    Tanpa LPAGENT_API_KEY handler tetap jalan dan menerbitkan fakta jujur
    ``menunggu-kunci`` — halaman /sistem jadi benar sejak hari pertama, dan API pihak
    ketiga tidak pernah ditembak tanpa kunci. Gerbang live tidak disentuh (armed=false).
    """
    from warroom_worker.adapters import lpagent

    r = lpagent.lpagent_ringkas(top=int(job.payload_json.get("top", 5)))
    _tulis_fakta(
        s,
        kind="lpagent",
        key="pools",
        value=r,
        source=r.get("base_url", lpagent.BASE_URL),
        ttl_s=int(job.payload_json.get("ttl_s", 3600)),
    )
    return f"lpagent={r.get('status')} tersedia={r.get('tersedia')} n={r.get('n', 0)}"


def handler_reconcile(s: SASession, job: Job) -> str:
    """Verifikasi klaim uang ke sumber on-chain; tak terverifikasi → alert (P4-T5).

    Mode penarikan ``manual`` (default; env ``WARROOM_POLY_WITHDRAW`` atau
    ``payload.withdraw_mode``) berarti dana ditarik sendiri lewat dashboard Polymarket —
    tidak ada auto-claim on-chain untuk diverifikasi, sehingga status "belum terverifikasi"
    itu **wajar** dan tidak memunculkan alert. Fakta tetap jujur (``terverifikasi=False``);
    yang berubah hanya alarmnya, bukan angkanya.
    """
    from warroom_worker.adapters import poly

    alamat = job.payload_json.get("alamat")
    mode = str(job.payload_json.get("withdraw_mode") or "") or None
    r = poly.reconcile_klaim(alamat=alamat, withdraw_mode=mode)
    _tulis_fakta(s, kind="poly.money", key="klaim-pilot", value=r,
                 # Job ini berjalan tiap 3600 dtk: TTL harus LEBIH PANJANG dari interval,
                 # kalau tidak fakta selalu "basi" tepat sebelum run berikutnya dan alert
                 # freshness berbunyi tiap jam (pelajaran yang sama dengan fakta learner).
                 source=str(r.get("sumber", poly.PILOT_DIR)), ttl_s=7200)
    if r.get("status") == "ok" and not r.get("terverifikasi") and r.get("mode") != "manual":
        _alert(
            s,
            subject="poly/klaim-uang",
            message=f"klaim uang belum terverifikasi ke sumber: {r.get('klaim')!r}",
            aksi=(
                "jalankan verifikasi on-chain (WARROOM_POLYGON_RPC) sebelum menampilkan "
                "angka ini sebagai uang nyata"
            ),
            severity="warning",
        )
    return (
        f"status={r.get('status')} klaim={r.get('klaim')!r} "
        f"terverifikasi={r.get('terverifikasi')} mode={r.get('mode')}"
    )


def handler_rekonsiliasi_crypto(s: SASession, job: Job) -> str:
    """Tutup posisi menggantung yang tak pernah dicatat `watchlist-sync` (temuan 6 Okt).

    Bukti: OP_USDT & LIT_USDT "still_open" sejak 27 Sep padahal SL 27–28 Sep; ledger
    melaporkan +3,844R padahal +1,844R. Ledger kehilangan R selama tidak ada penutup.
    Modul `rekonsiliasi.py` memakai candle MEXC (SL dicek lebih dulu) dan TIDAK menebak
    saat jaringan gagal — barisnya masuk `gagal[]`.
    """
    from live_trading import rekonsiliasi
    from live_trading.config import get_settings

    rep = rekonsiliasi.rekonsiliasi_watchlist(get_settings().state_dir)
    baru = rep.get("baru") or []
    for baris in baru:
        s.add(
            Event(
                type="trade.rekonsiliasi",
                actor="rekonsiliasi",
                payload_json=baris,
                severity="warning" if float(baris.get("r") or 0) < 0 else "info",
            )
        )
    if baru:
        kirim_tertunda(s, limit=3)
    rincian = "; ".join(
        f"{b.get('signal_id')} {b.get('status')} {float(b.get('r') or 0):+.1f}R" for b in baru
    )
    return (
        f"diperiksa={rep.get('diperiksa')} baru={len(baru)} "
        f"gagal={len(rep.get('gagal') or [])} detail={rincian or 'nihil'}"
    )


def handler_gmgn_sync(s: SASession, job: Job) -> str:
    """Terbitkan fakta GMGN + radar lokal — baca-saja (P4-T4)."""
    from warroom_worker.adapters import gmgn

    g = gmgn.gmgn_ringkas()
    _tulis_fakta(s, kind="gmgn", key="paper", value=g, source=str(g.get("dir", "~/gmgn-paper/state")),
                 ttl_s=int(job.payload_json.get("ttl_s", 1800)))
    r = gmgn.radar_ringkas()
    _tulis_fakta(s, kind="gmgn", key="radar", value=r,
                 source=str(r.get("path", "state/radar_state.json")), ttl_s=1800)
    lm = gmgn.lp_mark_ringkas()
    _tulis_fakta(s, kind="snapshot", key="lp_mark", value=lm,
                 source=str(lm.get("path", "state/lp_mark_terakhir.json")), ttl_s=7200)
    # Arm LP paper: kinerja dari sim_ledger.jsonl (baca-saja). Halaman /lp butuh ini;
    # sebelumnya `lp_paper` selalu {"tersedia": false} sehingga halaman tak punya angka.
    lp = gmgn.lp_paper_ringkas()
    _tulis_fakta(s, kind="snapshot", key="lp_paper", value=lp,
                 source=str(lp.get("path", "state/sim_ledger.jsonl")), ttl_s=7200)
    return (
        f"gmgn={g.get('status')} berkas={g.get('files')} radar={r.get('status')} "
        f"sumber={r.get('sumber')} lp_mark={lm.get('status')} lp_paper={lp.get('status')} "
        f"lp_n={(lp.get('basis') or {}).get('n')}"
    )


def _pesan_sinyal(sg: dict[str, Any], label: str) -> str:
    """Format pesan sinyal untuk Telegram — angka apa adanya + label jujur wajib."""
    baris = [f"{sg['pair']} · {sg['arah']} · tier {sg.get('tier')}"]
    harga = f"entry {sg.get('entry')} · SL {sg.get('sl')} · TP1 {sg.get('tp1')}"
    # QA 7 Okt: yang ditulis mesin adalah JARAK STOP. Ukuran posisi dibuat agar risiko
    # akun tetap 1% ekuitas; menulis "risiko" di sini menyesatkan (dibaca sebagai pelanggaran).
    if sg.get("risk_pct") is not None:
        harga += f" · jarak stop {sg['risk_pct']}%"
    baris.append(harga)
    baris.append(label)
    if sg.get("aturan_gagal"):
        baris.append("aturan belum lulus: " + ", ".join(str(x) for x in sg["aturan_gagal"]))
    return "\n".join(baris)


def handler_signal_sync(s: SASession, job: Job) -> str:
    """Terbitkan fakta sinyal dari ledger verdict domain + kabarkan yang lolos (Aksi 2).

    Baca-saja dan tanpa jaringan: ledger ``verdicts.jsonl`` sudah ditulis job ``collect``
    (``lt scan``), jadi handler ini tidak menambah beban ke exchange mana pun.

    Setiap pesan WAJIB membawa label jujur — kandidat, bukan ajakan beli. Gate statistik
    proyek belum membuktikan edge (verdict ``NOT_PROVEN``); mengabarkan seolah terbukti
    adalah kesalahan yang justru jadi kelemahan kompetitor.
    """
    from warroom_worker.adapters import signals as sig

    jam = float(job.payload_json.get("jam_terakhir", 6))
    ttl = int(job.payload_json.get("ttl_s", 21600))
    kabari = bool(job.payload_json.get("kabari", True))
    d = sig.sinyal_terakhir(root_dir() / "state", jam_terakhir=jam)
    if d.get("status") != "ok":
        return f"ledger sinyal {d.get('status')}: {str(d.get('detail') or '')[:80]}"

    n_fakta = 0
    dikabarkan = 0
    for sg in d.get("sinyal") or []:
        nilai: dict[str, Any] = {
            "pair": sg["pair"],
            "arah": sg["arah"],
            "tier": sg.get("tier"),
            "entry": sg.get("entry"),
            "sl": sg.get("sl"),
            "tp1": sg.get("tp1"),
            "risk_pct": sg.get("risk_pct"),
            "r_r": sg.get("r_r"),
            "strategy": sg.get("strategy"),
            "mode": sg.get("mode", "PAPER"),
            "detail": sg.get("detail") or {},
            "aturan_gagal": sg.get("aturan_gagal") or [],
            "diambil": sg.get("ts"),
            "label": sig.LABEL_JUJUR,
        }
        fakta = Fact(
            kind="signal",
            key=str(sg["pair"]),
            value_json=nilai,
            source=f"{d.get('path')}#{sg.get('ts')}",
            observed_at=datetime.now(UTC),
            ttl_s=ttl,
            hash=canonical_hash(nilai),
        )
        s.add(fakta)
        s.flush()
        n_fakta += 1
        if kabari and _alert(
            s,
            subject=f"sinyal/{sg['pair']}/{sg['arah']}",
            message=_pesan_sinyal(sg, sig.LABEL_JUJUR),
            aksi="Tinjau manual — ini kandidat, bukan ajakan beli. Eksekusi tetap keputusan Anda.",
            severity="info",
            fact_ids=[fakta.id],
        ):
            dikabarkan += 1
    return (
        f"ledger={d.get('path')} jendela={jam:g}j sinyal={d.get('jumlah')} "
        f"fakta={n_fakta} dikabarkan={dikabarkan}"
    )


def _tulis_fakta(s: SASession, *, kind: str, key: str, value: Any, source: str, ttl_s: int) -> None:
    """Satu fakta berversi. `observed_at` = sekarang (kita yang baru membacanya)."""
    s.add(
        Fact(
            kind=kind,
            key=key,
            value_json=value,
            source=source,
            observed_at=datetime.now(UTC),
            ttl_s=ttl_s,
            hash=canonical_hash(value),
        )
    )
    s.flush()


def _alert(
    s: SASession,
    *,
    subject: str,
    message: str,
    aksi: str,
    severity: str = "warning",
    fact_ids: list[int] | None = None,
) -> bool:
    """Buat alert KECUALI sudah ada alert BELUM DI-ACK dengan subjek yang sama.

    Menahan diri selama alert lama masih terbuka (bukan hanya selama jendela waktu tetap)
    itu penting: jendela tetap yang lebih pendek dari interval job membuat alert menumpuk
    tanpa batas untuk kondisi yang tidak berubah — terbukti 9 alert `learner/ringkas` dan
    13 alert `poly/klaim-uang` terbuka hanya dari DUA kondisi. Selama satu alert masih
    terbuka, pengingat ditangani notifier; setelah di-ack, kondisi yang masih berjalan boleh
    memunculkan alert baru. Kembalikan True bila alert baru benar-benar dibuat.
    """
    sudah = s.scalar(
        select(Alert.id).where(Alert.subject == subject).where(Alert.ack_at.is_(None)).limit(1)
    )
    if sudah is not None:
        return False
    s.add(
        Alert(
            severity=severity,
            subject=subject,
            message=message,
            suggested_action=aksi,
            fact_ids=list(fact_ids or []),
        )
    )
    s.flush()
    return True


def handler_learner(s: SASession, job: Job) -> str:
    """Learner harian berbatas: baca bukti nyata, usulkan dalam batas, catat keputusan (P5-T2).

    Sumber bukti: log pelajaran agen Polymarket (baca-saja). Bukti dipetakan ke parameter
    registry; usulan di luar batas ditolak **dengan alasan**, dan yang menyentuh gate/live
    ditandai `prohibited`.

    Catatan jujur: sampel di log agen bukan *split beku* menurut kebijakan kita, jadi gate
    akan menolaknya sampai ada split beku. Itu memang perilaku yang diinginkan — lebih baik
    menolak daripada menerapkan perubahan pada bukti yang belum sah.
    """
    if autonomy.kill_switch_aktif(s):
        return "kill switch AI aktif — tidak ada usulan yang dibuat"

    dibuat = autonomy.seed_parameters(s)
    dipakai = 0
    ringkas_keputusan: dict[str, int] = {}

    # Pemetaan nama patch agen → nama parameter registry kita.
    peta = {
        "threshold": "agent.threshold",
        "weights.mom": "agent.weights.mom",
        "weights.book": "agent.weights.book",
        "weights.band": "agent.weights.band",
        "sizeUsd": "risk.sizeUsd",
        "maxOpen": "risk.maxOpen",
    }

    terbaru = _pelajaran_terakhir()
    if terbaru is not None:
        # Bila ada split beku TERVERIFIKASI untuk dataset ini, pasang ke bukti supaya gate
        # bisa lolos. Kalau tidak ada, biarkan kosong: gate akan menolak — dan itu benar.
        from warroom_core import splits as _splits

        split_beku = _splits.split_terverifikasi_terbaru(s, "poly-agent")
        ev = {
            "n": terbaru.get("rows"),
            "win": round(float(terbaru.get("winPct", 0)) / 100 * int(terbaru.get("rows", 0))),
            "be": float(terbaru.get("bePct", 0)) / 100,
            # Log agen adalah rentang bergulir, BUKAN split beku. Split hanya dipasang bila
            # benar-benar ada & terverifikasi; kalau tidak, gate menolak (lebih baik begitu).
            "sumber": "agent-lessons.jsonl",
            "split": split_beku,
            "label": terbaru.get("label"),
        }
        patch = terbaru.get("patch") or {}
        kandidat: list[tuple[str, Any]] = []
        for k, v in (patch.get("weights") or {}).items():
            if f"weights.{k}" in peta:
                kandidat.append((peta[f"weights.{k}"], v))
        if "threshold" in patch:
            kandidat.append((peta["threshold"], patch["threshold"]))
        for nama_param, nilai in kandidat:
            if ev["n"] is None:
                continue
            hasil = autonomy.usulkan(
                s,
                nama_param,
                nilai,
                alasan=f"learner: patch agen {terbaru.get('reason')} pada label {terbaru.get('label')}",
                evidence=ev,
                actor="learner",
            )
            dipakai += 1
            ringkas_keputusan[hasil["keputusan"]] = ringkas_keputusan.get(hasil["keputusan"], 0) + 1

    _tulis_fakta(
        s, kind="learner", key="ringkas",
        value={"diusulkan": dipakai, "keputusan": ringkas_keputusan, "seed_baru": dibuat,
               # Dibaca, bukan di-hardcode: kalau tidak, fakta ini menulis "saklar mati"
               # ke UI meski saklar nyala atau tak terbaca (temuan 5 Okt 2026).
               "kill_switch": autonomy.kill_switch_aktif(s)},
        # Job harian: TTL harus lebih panjang dari interval (86400 dtk) supaya fakta tidak
        # tampil "basi" permanen di antara dua jalan. Telat > 25 jam tetap terlihat.
        source="agent-lessons.jsonl + registry parameter", ttl_s=90_000,
    )
    return f"diusulkan={dipakai} keputusan={ringkas_keputusan} seed_baru={len(dibuat)}"


def _pelajaran_terakhir() -> dict[str, Any] | None:
    """Ambil pelajaran terakhir yang memuat n/win/be (yang lain tidak bisa dinilai)."""
    from warroom_worker.adapters import poly

    b = poly.baca_jsonl_ekor(f"{poly.AGENT_DIR}/agent-lessons.jsonl", n=50)
    if not b.ok or not isinstance(b.data, list):
        return None
    for baris in reversed(b.data):
        if isinstance(baris, dict) and baris.get("rows") and baris.get("winPct"):
            return baris
    return None


def handler_prompts_sync(s: SASession, job: Job) -> str:
    """Sinkronkan registry prompt dari berkas → tabel `prompts` (versi baru, bukan timpa)."""
    from warroom_core import prompts_dir
    from warroom_llm.prompts import load_prompts, sync_prompts

    direktori = str(job.payload_json.get("dir") or prompts_dir())
    prompts = load_prompts(direktori)
    jumlah = sync_prompts(s, prompts)
    versi = {r: p.version for r, p in prompts.items()}
    _tulis_fakta(
        s,
        kind="ai.prompt_registry",
        key="registry",
        value={"jumlah_disinkron": jumlah, "peran": versi, "sumber": direktori},
        source=direktori,
        ttl_s=int(job.payload_json.get("ttl_s", 86400)),
    )
    return f"prompts: {jumlah} baris disinkronkan dari {len(prompts)} berkas; versi={versi}"


def _ringkas_fakta(f: Any, kunci: str) -> str:
    """Ubah fakta besar jadi teks ANGKA-utuh untuk narator.

    Masalah nyata (6 Okt): narator hanya melihat 80 karakter pertama JSON, sehingga ia
    bercerita tentang metadata (sha256/checksum) alih-alih hasilnya. Di sini kita ambil
    bagian yang berisi angka, tanpa mengubah nilainya — LLM tidak boleh menghitung ulang.
    """
    v = f.value_json
    if not isinstance(v, dict):
        return str(v)[:400]
    if kunci.endswith("_sinyal"):
        entries = (v.get("entries") or [])[:5]
        baris = [
            {
                "pair": e.get("pair") or e.get("ticker"),
                "arah": e.get("arah"),
                "setup": e.get("setup"),
                "status": e.get("hasil") or e.get("status"),
                "skor_gate": e.get("skor"),
                "entry": e.get("entry"),
                "sl": e.get("sl"),
                "tp1": e.get("tp1"),
                "r": e.get("r") if e.get("r") is not None else e.get("net_r"),
            }
            for e in entries
        ]
        return f"n_entries={len(v.get('entries') or [])} | " + str(baris)[:1100]
    if kunci == "pasar_akurasi":
        pasar = v.get("pasar") or {}
        baris = []
        for nama, p in pasar.items():
            for setup, s in (p.get("per_setup") or {}).items():
                baris.append(
                    f"{nama}/{setup}: n={s.get('n')} hari={s.get('n_hari')} "
                    f"WR={s.get('winrate_pct')}% meanR={s.get('mean_r')} totalR={s.get('total_r')} "
                    f"pnl_usd={s.get('total_pnl_usd', s.get('pnl_usd'))} tingkat={s.get('tingkat')}"
                )
        return " || ".join(baris)[:1200]
    if kunci == "idx_akurasi":
        ringkas = v.get("per_setup") or {}
        baris = [
            f"{k}: n={s.get('n')} hari={s.get('n_hari')} WR={s.get('winrate_pct')}% "
            f"meanR={s.get('mean_r')} tingkat={s.get('pakem')}"
            for k, s in ringkas.items()
        ]
        return f"tuntas={v.get('tuntas')} belum={v.get('belum_tuntas')} | " + " || ".join(baris)[:1000]
    return str(v)[:600]


def handler_llm_brief(s: SASession, job: Job) -> str:
    """Narasi ringkas terjadwal dari fakta nyata (peran narrator). Gagal → dicatat, bukan dipaksa."""
    from warroom_core import prompts_dir
    from warroom_llm import CallRequest, FactRef, Gateway
    from warroom_llm.config import default_config
    from warroom_llm.prompts import PromptRegistry

    area = str(job.payload_json.get("area", "crypto"))
    # Nama baru memakai `_keys` (underscore = bukan milik skema gateway); `keys` lama tetap dibaca.
    kunci = job.payload_json.get("_keys") or job.payload_json.get("keys") or []
    terbaru = _fakta_terbaru(s, kunci or None, batas=int(job.payload_json.get("max_facts", 8)))
    fakta = tuple(
        FactRef(
            fact_id=f.id,
            label=f"F{i + 1}",
            text=f"[{f.key}] {_ringkas_fakta(f, f.key)} (sumber={f.source}, umur_s="
            f"{int((datetime.now(UTC) - f.observed_at).total_seconds())})",
        )
        for i, f in enumerate(terbaru)
    )
    if not fakta:
        return "lewati: belum ada fakta untuk dinarasikan"
    gw = Gateway(
        config=default_config(),
        prompts=PromptRegistry.from_dir(str(job.payload_json.get("prompts_dir") or prompts_dir())),
    )
    hasil = gw.call(
        CallRequest(
            role="narrator",
            user=f"Ringkas 2 kalimat untuk area {area} berdasarkan fakta.",
            facts=fakta,
            min_facts=1,
        )
    )
    _tulis_fakta(
        s,
        kind="ai.brief",
        key=area,
        value={
            "status": hasil.status,
            "provider": hasil.provider,
            "fallback_from": hasil.fallback_from,
            "prompt_version": hasil.prompt_version,
            "latency_ms": hasil.latency_ms,
            "fact_ids": list(hasil.fact_ids),
            "output": hasil.output,
            "error_code": hasil.error_code,
        },
        source=f"gateway:{hasil.provider or '-'}",
        ttl_s=int(job.payload_json.get("ttl_s", 21600)),
    )
    return f"narrator {hasil.status} via {hasil.provider} ({hasil.latency_ms} ms, {len(fakta)} fakta)"


def _fakta_terbaru(s: SASession, kunci: list[str] | None, *, batas: int) -> list[Any]:
    """Fakta terbaru per kunci (atau semua kunci bila `kunci` kosong)."""
    from warroom_core.db import Fact

    q = select(Fact).order_by(Fact.observed_at.desc()).limit(batas * 6 if kunci else batas)
    if kunci:
        q = q.where(Fact.key.in_(kunci))
    baris = list(s.scalars(q).all())
    unik: dict[str, Any] = {}
    for f in baris:
        unik.setdefault(f.key, f)
    return list(unik.values())[:batas]


def handler_paper_eval(s: SASession, job: Job) -> str:
    """Evaluasi posisi paper terhadap harga live bursa (MEXC, Binance, Forex, IDX, GMGN).

    Bila posisi kena SL/TP1/TP2:
    - Tutup atau update posisi
    - Buat Alert info untuk notifikasi instan Telegram
    - Buat Event stream untuk Web SSE
    """
    from live_trading.collectors.crypto import CryptoCollector
    from live_trading.config import get_settings
    from live_trading.execution.paper import PaperBroker

    stg = get_settings()
    total_eval = 0
    total_closed = 0
    hasil_detail: list[str] = []

    # 1. Evaluasi Crypto
    b_crypto = PaperBroker(stg, venue="crypto")
    positions = b_crypto.positions()
    if positions:
        pairs = {p.pair for p in positions}
        prices: dict[str, float] = {}
        c = CryptoCollector(stg)
        for pair in pairs:
            try:
                prices[pair] = c.pair_snapshot(pair, klines=2)["price"]
            except Exception:
                continue
        closed = b_crypto.evaluate(prices, net_be=True)
        total_eval += len(positions)
        total_closed += len(closed)
        for err in b_crypto.errors:
            hasil_detail.append(f"GAGAL {err}")
        for rec in closed:
            subjek = f"trade/{rec['signal_id']}"
            r_val = float(rec.get("r", 0))
            is_win = r_val > 0
            icon = "🎯" if is_win else "🛑"
            pesan = (
                f"{icon} [PAPER TRADE DITUTUP - CRYPTO]\n"
                f"Pair: {rec.get('pair')} ({rec.get('direction')})\n"
                f"Status: {rec.get('status')} @ {rec.get('note')}\n"
                f"Hasil R: {r_val:+.3f}R | Signal ID: {rec.get('signal_id')}"
            )
            _alert(
                s, subject=subjek, message=pesan,
                aksi="periksa buku kas di /crypto?sub=eksekusi", severity="info",
            )
            s.add(
                Event(
                    type="trade.closed",
                    actor="paper_eval",
                    payload_json=rec,
                    severity="info" if is_win else "warning",
                )
            )
            hasil_detail.append(f"{rec['signal_id']} {rec['pair']} {rec['status']} {r_val:+.2f}R")

        # Cek runner yang baru menyentuh TP1
        for p in b_crypto.positions():
            if p.status == "tp1_hit_runner":
                ev_subjek = f"tp1/{p.signal_id}"
                _msg = (
                    f"🎯 [TP1 TERCAPAI - RUNNER AKTIF]\nPair: {p.pair} ({p.direction})\n"
                    f"Stop loss digeser ke break-even (${p.stop}). Sisa posisi menuju TP2 (${p.tp2})."
                )
                if _alert(
                    s, subject=ev_subjek, message=_msg,
                    aksi="pantau posisi di Command Center", severity="info",
                ):
                    s.add(Event(
                        type="trade.tp1", actor="paper_eval",
                        payload_json=p.to_dict(), severity="info",
                    ))

    # Segera kirim alert bila ada perubahan posisi
    if total_closed > 0:
        kirim_tertunda(s, limit=5)

    return f"eval_posisi={total_eval} ditutup={total_closed} detail={', '.join(hasil_detail) or 'nihil'}"


def _pair_sudah_dipakai(stg: Any, *, jam: float = 12.0) -> set[str]:
    """Pair yang TIDAK boleh dibuka lagi: sedang terbuka, atau baru ditutup dalam `jam`.

    Temuan 7 Okt: AAVEUSDT punya 7 sinyal `allowed` berulang (3× dalam 1,5 jam pada 5 Okt)
    dan `paper-scan` membuka posisi SETIAP kali — hasilnya 4 posisi identik dengan 4 baris
    ledger. Dedup `_kandidat_terbaru_dari_ledger` hanya mencegah duplikat DALAM SATU
    pemindaian; ia tidak melihat posisi yang sudah ada. Akibatnya satu setup dihitung
    4× dan dompet/akurasi jadi salah.
    """
    import json as _json
    from datetime import UTC as _UTC
    from datetime import datetime as _dt

    dipakai: set[str] = set()
    # (a) posisi terbuka
    try:
        raw = _json.loads((stg.state_dir / "paper_positions.json").read_text(encoding="utf-8"))
        dipakai |= {str(p.get("pair")) for p in raw.get("positions", []) if p.get("pair")}
    except (OSError, ValueError, _json.JSONDecodeError):
        pass
    # (b) posisi yang baru ditutup → beri jeda supaya tidak langsung re-entry di pair sama
    batas = _dt.now(_UTC).timestamp() - jam * 3600
    try:
        for ln in (stg.state_dir / "crypto_equity.jsonl").read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                row = _json.loads(ln)
                ts = _dt.fromisoformat(str(row.get("closed_at") or "").replace("Z", "+00:00")).timestamp()
            except (ValueError, TypeError, _json.JSONDecodeError):
                continue
            if ts >= batas and row.get("pair"):
                dipakai.add(str(row["pair"]))
    except OSError:
        pass
    return dipakai


def _kandidat_terbaru_dari_ledger(stg: Any, *, jam_terakhir: float = 6.0) -> list[dict[str, Any]]:
    """Kandidat lolos TERBARU dari `verdicts.jsonl` — sumber yang sama dengan dashboard.

    Hanya baris `allowed` yang diambil; duplikat pair (entri berulang) diambil yang
    paling baru saja supaya satu pair tidak membuka dua posisi dalam satu pemindaian.
    """
    import json as _json
    from datetime import UTC as _UTC
    from datetime import datetime as _dt

    path = stg.state_dir / "verdicts.jsonl"
    if not path.is_file():
        return []
    batas = _dt.now(_UTC).timestamp() - jam_terakhir * 3600
    terbaru: dict[str, dict[str, Any]] = {}
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            row = _json.loads(ln)
        except _json.JSONDecodeError:
            continue
        if not row.get("allowed"):
            continue
        try:
            ts = _dt.fromisoformat(str(row["ts"]).replace("Z", "+00:00")).timestamp()
        except (KeyError, ValueError):
            continue
        if ts < batas:
            continue
        pair = str(row.get("pair") or "")
        if not pair:
            continue
        if pair not in terbaru or ts > terbaru[pair]["_ts"]:
            terbaru[pair] = {**row, "_ts": ts}
    return [v for v in terbaru.values()]

def handler_paper_scan(s: SASession, job: Job) -> str:
    """Pemindaian otomatis & pembukaan posisi paper bila ada sinyal lolos gerbang risiko."""
    from live_trading.config import get_settings
    from live_trading.execution.paper import PaperBroker
    from live_trading.risk import RiskGate

    stg = get_settings()
    b_crypto = PaperBroker(stg, venue="crypto")
    gate = RiskGate(stg, venue="crypto")
    curr_pos = b_crypto.positions()

    if len(curr_pos) >= stg.max_concurrent_positions:
        return f"slot posisi crypto penuh ({len(curr_pos)}/{stg.max_concurrent_positions})"

    # Sumber kandidat = `verdicts.jsonl` (ledger gate), BUKAN `engine.scan` lokal.
    #
    # Temuan 6 Okt: job ini memakai engine.scan(DEFAULT_PAIRS) — hanya 6 pair warisan —
    # sehingga kandidat lolos yang sudah dicatat ledger (AAVE/TIA/ARB, 192 izin dari 68
    # pair) tidak pernah dieksekusi. Akibatnya akurasi crypto mandek di 6 trade: mesin
    # tidak bisa membuktikan apa pun karena trade-nya tidak pernah dibuka.
    # Ledger adalah sumber yang sudah lolos gerbang & sudah ditampilkan UI — eksekusi
    # harus mengikuti sumber yang sama, bukan pemindaian kedua yang berbeda hasilnya.
    rows = _kandidat_terbaru_dari_ledger(stg, jam_terakhir=float(job.payload_json.get("jam_terakhir", 6)))
    # Satu pair = satu posisi pada satu waktu (dan jeda 12 jam setelah ditutup).
    # Tanpa ini, sinyal berulang membuat posisi identik bertumpuk (bukti: AAVE 4×, 7 Okt).
    sudah = _pair_sudah_dipakai(stg, jam=float(job.payload_json.get("jeda_pair_jam", 12)))
    dibuka: list[str] = []
    dilewati: list[str] = []

    for r in rows:
        if r.get("pair") in sudah:
            dilewati.append(str(r.get("pair")))
            continue
        if r.get("allowed") and len(b_crypto.positions()) < stg.max_concurrent_positions:
            pair = r["pair"]
            direction = r["direction"]
            entry = float(r["entry"])
            # Ledger menulis `sl`/`tp1`/`tp2`; engine.scan menulis `stop`. Keduanya diterima
            # supaya sumber kandidat bisa berganti tanpa kehilangan level — dan kalau
            # benar-benar tidak ada, kandidat dilewati (bukan ditebak).
            stop_raw = r.get("stop") or r.get("sl")
            tp1_raw = r.get("tp1")
            tp2_raw = r.get("tp2") or r.get("tp1")
            if stop_raw is None or tp1_raw is None:
                continue
            stop = float(stop_raw)
            tp1 = float(tp1_raw)
            tp2 = float(tp2_raw)
            atr = float(r.get("atr") or abs(entry - stop) / 1.5)

            dec = gate.check(
                pair=pair, price=entry, atr=atr, equity_usd=stg.equity_usd, fee_buffer_pct=0.0013
            )
            if dec.allowed:
                # Biaya TERUKUR dari buku nyata (P2) — bukan asumsi 0,1%. Sisi masuk = sisi
                # yang kita cross: LONG membeli di ask, SHORT menjual di bid; keluar di sisi
                # sebaliknya. Bila buku tak terbaca, biaya ditandai asumsi (bukan angka palsu).
                biaya: dict[str, Any] = {"asumsi": True, "total_bps": None, "sumber": "tak-diukur"}
                try:
                    from live_trading.collectors.depth import DepthCollector
                    from live_trading.execution import costs

                    rep = DepthCollector(stg).report(pair, limit=100, max_bps=costs.MAKS_BPS)
                    sisi_masuk = "ask" if direction.upper() == "LONG" else "bid"
                    sisi_keluar = "bid" if direction.upper() == "LONG" else "ask"
                    biaya = costs.biaya_dari_depth(
                        rep, sisi_masuk=sisi_masuk, size_usd=float(dec.size_usd or 0.0),
                        sisi_keluar=sisi_keluar,
                    )
                except Exception as exc:  # noqa: BLE001 — biaya gagal diukur jangan blokir order
                    biaya = {"asumsi": True, "total_bps": None, "sumber": "error",
                             "alasan": f"{type(exc).__name__}: {exc}"}

                # Jalur keputusan TUNGGAL (paper & live). Ukuran/SL/TP dari sini, bukan
                # dihitung ulang di eksekutor — itu yang membuat paper benar-benar 1:1.
                from live_trading.execution.keputusan import Konteks, jalur_untuk, putuskan_masuk

                kep = putuskan_masuk(
                    {**r, "atr": atr, "tp1": tp1, "tp2": tp2},
                    Konteks(
                        equity_usd=stg.equity_usd,
                        fee_bps=float(biaya["total_bps"]) if biaya.get("total_bps") is not None else None,
                        mode="paper",
                        slot_tersisa=max(0, stg.max_concurrent_positions - len(b_crypto.positions())),
                    ),
                )
                if not kep.masuk:
                    continue
                pos = b_crypto.open_position(
                    pair=kep.pair,
                    direction=kep.arah,
                    entry=float(kep.entry),
                    stop=float(kep.sl),
                    tp1=float(kep.tp1),
                    tp2=float(kep.tp2),
                    size_usd=float(kep.size_usd or 0.0),
                    note=f"jalur-tunggal ({kep.alasan}); biaya {biaya.get('sumber')}",
                    cost_bps=kep.cost_bps,
                )
                # Jejak keputusan disimpan supaya bisa dibandingkan baris-demi-baris dengan
                # mode live nanti — itu bukti 1:1 yang bisa diperiksa, bukan klaim.
                s.add(Event(type="keputusan.masuk", actor="paper_scan",
                            payload_json={**kep.to_dict(), "jalur": jalur_untuk(kep),
                                          "sumber_biaya": biaya.get("sumber")},
                            severity="info"))
                s.add(Event(type="cost.measured", actor="paper_scan",
                            payload_json={"pair": pair, "direction": direction,
                                          "size_usd": dec.size_usd, **biaya},
                            severity="info" if not biaya.get("asumsi") else "warning"))
                subjek = f"trade/{pos.signal_id}"
                pesan = (
                    f"🟢 [PAPER TRADE DIBUKA - CRYPTO]\n"
                    f"Pair: {pos.pair} ({pos.direction})\n"
                    f"Entry: ${pos.entry} | SL: ${pos.stop} | TP1: ${pos.tp1} | TP2: ${pos.tp2}\n"
                    f"Ukuran: ${pos.size_usd} | Risiko: ${dec.risk_usd} (1.0% equity)\n"
                    f"Biaya: {biaya.get('total_bps') or '?'} bps "
                    f"({'asumsi fee saja' if biaya.get('asumsi') else 'terukur dari buku'})\n"
                    f"Signal ID: {pos.signal_id}"
                )
                _alert(
                    s, subject=subjek, message=pesan,
                    aksi="lihat di /crypto?sub=eksekusi", severity="info",
                )
                s.add(Event(
                    type="trade.opened", actor="paper_scan",
                    payload_json=pos.to_dict(), severity="info",
                ))
                dibuka.append(f"{pos.signal_id} {pos.pair} {pos.direction}")

    if dibuka:
        kirim_tertunda(s, limit=5)

    detail = ", ".join(dibuka) or "tidak ada yang lolos gate"
    lewat = f" dilewati={','.join(sorted(set(dilewati)))}" if dilewati else ""
    return f"kandidat={len(rows)} dibuka={len(dibuka)}{lewat} detail={detail}"


def handler_retensi(s: SASession, job: Job) -> str:
    """Retensi data terjadwal (P5): batasi pertumbuhan `facts` tanpa menghapus yang dipakai.

    Simpan `keep_versi` versi terbaru per (kind,key). Default TIDAK menghapus `events`
    (jejak audit) — operator bisa menyalakannya lewat payload hapus_events=true.
    """
    from warroom_core import retention

    hasil = retention.jalankan(
        s,
        keep_versi=int(job.payload_json.get("keep_versi", retention.KEEP_VERSI_DEFAULT)),
        events_hari=int(job.payload_json.get("events_hari", retention.EVENTS_HARI_DEFAULT)),
        llm_call_hari=int(job.payload_json.get("llm_call_hari", retention.LLM_CALL_HARI_DEFAULT)),
        hapus_events=bool(job.payload_json.get("hapus_events", False)),
        hapus_llm_calls=bool(job.payload_json.get("hapus_llm_calls", True)),
    )
    d = hasil["dihapus"]
    return (
        f"facts_dihapus={d['facts']} events_dihapus={d['events']} llm_dihapus={d['llm_calls']} "
        f"(simpan {hasil['rencana']['keep_versi']} versi/kunci)"
    )


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
    s.flush()
    ringkas = " ".join(f"{u}={status_ringkas[u]}" for u in units)
    return f"host={host} unit={ditulis} {ringkas}"

def _unit_state(unit: str) -> str:
    """Status unit systemd (baca-saja). Gagal/tak ada → 'unknown'/'not-found', bukan tebakan."""
    import subprocess

    try:
        r = subprocess.run(  # noqa: S603
            ["systemctl", "show", unit, "-p", "LoadState", "-p", "ActiveState"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if r.returncode != 0:
        return "unknown"
    load = next((b.split("=", 1)[1] for b in r.stdout.splitlines() if b.startswith("LoadState=")), "")
    active = next((b.split("=", 1)[1] for b in r.stdout.splitlines() if b.startswith("ActiveState=")), "")
    if load in {"not-found", ""}:
        return "not-found"
    return active or "unknown"

def _upsert_service(
    s: SASession, *, host: str, unit: str, status: str, detail: dict[str, Any]
) -> None:
    """Satu baris per (host, unit) — pakai unique constraint, bukan tumpuk baris baru."""
    row = s.scalar(select(Service).where(Service.host == host, Service.unit == unit))
    if row is None:
        s.add(Service(host=host, unit=unit, status=status, detail_json=detail))
    else:
        row.status = status
        row.detail_json = detail
        row.updated_at = datetime.now(UTC)

def register_handlers() -> dict[str, Any]:
    """Daftarkan handler ke `schedule.HANDLERS` (dipanggil sekali saat worker start)."""
    schedule.HANDLERS.update(
        {
            "publish-facts": handler_publish_facts,
            "freshness": handler_freshness,
            "notify": handler_notify,
            "collect": handler_collect,
            "refresh-snapshot": handler_refresh_snapshot,
            "radar-update": handler_radar_update,
            "lp-mark": handler_lp_mark,
            "backup": handler_backup,
            "poly-sync": handler_poly_sync,
            "verdict-sync": handler_verdict_sync,
            "parity-drift": handler_parity_drift,
            "reconcile": handler_reconcile,
            "gmgn-sync": handler_gmgn_sync,
            "lpagent-sync": handler_lpagent_sync,
            "rekonsiliasi-crypto": handler_rekonsiliasi_crypto,
            "signal-sync": handler_signal_sync,
            "learner": handler_learner,
            "prompts-sync": handler_prompts_sync,
            "llm-brief": handler_llm_brief,
            "llm-brief-crypto": handler_llm_brief,
            "llm-brief-forex": handler_llm_brief,
            "llm-brief-idx": handler_llm_brief,
            "llm-brief-gmgn": handler_llm_brief,
            "llm-brief-polymarket": handler_llm_brief,
            "paper-eval": handler_paper_eval,
            "paper-scan": handler_paper_scan,
            "retensi": handler_retensi,
            "source-health": handler_source_health,
        }
    )
    return schedule.HANDLERS