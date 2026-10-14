from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session as SASession
from warroom_core import autonomy
from warroom_core.db import Event, Job
from warroom_notifier.dispatch import kirim_tertunda

from .base import (
    _alert,
    _fakta_terbaru,
    _pelajaran_terakhir,
    _ringkas_fakta,
    _tulis_fakta,
)

log = logging.getLogger("warroom_worker.jobs")


def handler_learner(s: SASession, job: Job) -> str:
    """Learner harian berbatas: baca bukti nyata, propose dalam batas, catat keputusan (P5-T2).

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
            hasil = autonomy.propose(
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
                from live_trading.execution.keputusan import Konteks, decide_entry, jalur_untuk

                kep = decide_entry(
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


