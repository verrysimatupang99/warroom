from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as SASession
from warroom_core.db import Event, Fact, Job
from warroom_core.gate import DEFAULT_DEFF, GATE_DEFAULT_MIN_N, GATE_TOOL_CI
from warroom_notifier.dispatch import kirim_tertunda

from .base import (
    _alert,
    _pesan_sinyal,
    _tulis_fakta,
    canonical_hash,
    root_dir,
)

log = logging.getLogger("warroom_worker.jobs")


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
    # Hanya tier ini yang dikabarkan ke Telegram. Fakta untuk tier lain tetap ditulis
    # supaya jurnal/pengukuran tidak buta; yang dihentikan hanya notifikasinya.
    # Bukti 160 sinyal: STANDAR net expectancy -0,012R (fee 5 bps/sisi), PREMIUM +0,230R.
    kabar_tier = {
        str(t).strip().upper()
        for t in (job.payload_json.get("kabar_tier") or ["PREMIUM"])
        if str(t).strip()
    }
    d = sig.sinyal_terakhir(root_dir() / "state", jam_terakhir=jam)
    if d.get("status") != "ok":
        return f"ledger sinyal {d.get('status')}: {str(d.get('detail') or '')[:80]}"

    n_fakta = 0
    dilewati = 0
    dikabarkan = 0
    for sg in d.get("sinyal") or []:
        # Sinyal yang sudah pernah diterbitkan TIDAK ditulis/dikabarkan ulang. Sumber
        # (`path#ts`) sudah mengunci identitas sinyal; tanpa ini ledger yang sama
        # ditulis ulang tiap siklus (15 mnt) dan alert dikabarkan berulang setelah ack —
        # di produksi: 197 alert untuk 12 sinyal unik, dan umur sinyal ikut "disegarkan"
        # sehingga kandidat 6 jam bisa terlihat segar sampai ~12 jam.
        sumber = f"{d.get('path')}#{sg.get('ts')}"
        sudah = s.scalar(
            select(Fact.id)
            .where(Fact.kind == "signal", Fact.key == str(sg["pair"]), Fact.source == sumber)
            .limit(1)
        )
        if sudah is not None:
            dilewati += 1
            continue
        nilai: dict[str, Any] = {
            "pair": sg["pair"],
            "arah": sg["arah"],
            "tier": sg.get("tier"),
            "strategy_version": sg.get("strategy_version") or "legacy",
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
            source=sumber,
            observed_at=datetime.now(UTC),
            ttl_s=ttl,
            hash=canonical_hash(nilai),
        )
        s.add(fakta)
        s.flush()
        n_fakta += 1
        if (
            kabari
            and str(sg.get("tier") or "").strip().upper() in kabar_tier
            and _alert(
                s,
                subject=f"sinyal/{sg['pair']}/{sg['arah']}",
                message=_pesan_sinyal(sg, sig.LABEL_JUJUR),
                aksi="Tinjau manual — ini kandidat, bukan ajakan beli. Eksekusi tetap keputusan Anda.",
                severity="info",
                fact_ids=[fakta.id],
            )
        ):
            dikabarkan += 1
    return (
        f"ledger={d.get('path')} jendela={jam:g}j sinyal={d.get('jumlah')} "
        f"baru={n_fakta} sudah_ada={dilewati} dikabarkan={dikabarkan} "
        f"tier_kabar={','.join(sorted(kabar_tier)) or '-'}"
    )




def handler_polybtc_sync(s: SASession, job: Job) -> str:
    """Terbitkan fakta alternatif «PolyBTC Momentum» (BTC 5m) — baca-saja.

    Skill pihak ketiga (0xgetz/polymarket-btc-5m) berjalan mandiri; handler ini
    hanya membaca keluarannya dan menerbitkan fakta. Tidak ada order, tidak ada
    perubahan pada kode skill. Kegagalan dilaporkan sebagai data, bukan disembunyikan.
    """
    from warroom_worker.adapters import polybtc

    r = polybtc.polybtc_ringkas()
    _tulis_fakta(
        s,
        kind="poly.alt",
        key="btc-5m",
        value=r,
        source=str(r.get("skill_dir", "polymarket-btc-5m")),
        ttl_s=int(job.payload_json.get("ttl_s", 900)),
    )
    sesi = r.get("sesi") or {}
    obs = r.get("observasi") or {}
    return (
        f"tersedia={r.get('tersedia')} jalan={r.get('jalan')} "
        f"mode={sesi.get('mode')} profil={sesi.get('profil')} "
        f"snapshot={obs.get('n_snapshot')} preflight_go={obs.get('preflight_go')}"
    )

