"""Handler formula-based: learner berbatas, evaluasi/scan paper (tanpa LLM).

Riwayat: modul ini dulu bernama ``llm.py`` — handler AI (narrator brief,
registry prompt) sudah dibuang; yang tersisa murni hitungan rumus."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session as SASession
from warroom_core import autonomy
from warroom_core.db import Event, Job
from warroom_notifier.dispatch import kirim_tertunda
from warroom_notifier.strategy_alert import (
    alert_benched,
    alert_entry,
    alert_exit,
    alert_tp1,
)

from .base import (
    _alert,
    _pelajaran_terakhir,
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
            r_val = float(rec.get("r", 0))
            is_win = r_val > 0
            # Pesan exit dibangun modul notifier (subjek trade/<id>/exit — dedup per aksi).
            kondisi = alert_exit(
                str(rec.get("strategi") or rec.get("source") or "paper"),
                signal_id=str(rec["signal_id"]),
                pair=str(rec.get("pair")),
                status=str(rec.get("status")),
                r=r_val,
                mode="paper",
            )
            _alert(
                s, subject=kondisi.subjek, message=kondisi.pesan,
                aksi=kondisi.subjek_aksi, severity=kondisi.severity,
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
                kondisi_tp1 = alert_tp1(
                    p.strategi or p.source or "crypto",
                    signal_id=p.signal_id,
                    pair=p.pair,
                    direction=p.direction,
                    stop=p.stop,
                    tp2=p.tp2,
                    mode="paper",
                )
                if _alert(
                    s,
                    subject=kondisi_tp1.subjek,
                    message=kondisi_tp1.pesan,
                    aksi=kondisi_tp1.subjek_aksi,
                    severity=kondisi_tp1.severity,
                ):
                    s.add(
                        Event(
                            type="trade.tp1",
                            actor="paper_eval",
                            payload_json=p.to_dict(),
                            severity="info",
                        )
                    )

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


def blokir_korelasi_rezim(
    arah: str, arah_terbuka: dict[str, int], rezim: str | None, maks_searah: int, pakai_filter: bool,
) -> str | None:
    """Alasan pemblokiran candidate berdasarkan korelasi & rezim BTC (#9, 15 Okt).

    Returns Skip-reason teks bila harus DIBLOKIR, None bila boleh lanjut.
    Murni (tanpa I/O) supaya bisa diuji tanpa DB — aturan tetap SATU tempat.
    """
    if pakai_filter and rezim in ("naik", "turun"):
        if arah == "SHORT" and rezim == "naik":
            return "(rezim BTC naik, short diblok)"
        if arah == "LONG" and rezim == "turun":
            return "(rezim BTC turun, long diblok)"
    if arah_terbuka.get(arah, 0) >= maks_searah:
        return f"(korelasi searah {arah} ≥ {maks_searah})"
    return None


def alert_bench_jika_transisi(
    s: SASession,
    bench: Any,
    nama: str,
    *,
    status_sebelum: str,
    entri: dict[str, Any],
) -> bool:
    """Kabarkan transisi aktif→benched — sekali, bukan tiap siklus.

    Keadaan SEBELUM dicatat `bench.catat` disuplai pemanggil (modul alert tidak
    menyimpan riwayat); strategi yang masih benched di siklus berikutnya tidak
    memicu apa pun karena tidak ada transisi baru.
    """
    if status_sebelum == "benched" or bench.status(nama) != "benched":
        return False
    b = bench.batas
    if int(entri.get("trade", 0)) >= b.maks_trade:
        alasan = f"batas {b.maks_trade} trade harian tercapai"
    elif float(entri.get("fee_usd", 0.0)) >= b.maks_fee_usd:
        alasan = f"batas fee ${b.maks_fee_usd:.2f}/hari tercapai"
    else:
        alasan = "batas harian terlampaui"
    kondisi = alert_benched(
        nama,
        alasan=alasan,
        trade=int(entri.get("trade", 0)),
        fee_usd=float(entri.get("fee_usd", 0.0)),
        hari=bench.hari() if hasattr(bench, "hari") else None,
    )
    return _alert(
        s, subject=kondisi.subjek, message=kondisi.pesan,
        aksi=kondisi.subjek_aksi, severity=kondisi.severity,
    )


def handler_paper_scan(s: SASession, job: Job) -> str:
    """Pemindaian otomatis & pembukaan posisi paper bila ada sinyal lolos gerbang risiko."""
    from live_trading.config import get_settings
    from live_trading.execution.paper import PaperBroker
    from live_trading.risk import RiskGate

    stg = get_settings()
    b_crypto = PaperBroker(stg, venue="crypto")
    gate = RiskGate(stg, venue="crypto")
    curr_pos = b_crypto.positions()

    # Batas harian per strategi (owner 16 Okt): melebihi trade/fee → 'benched' hari itu.
    from live_trading.bench import BatasStrategi, BenchHarian

    bench = BenchHarian(
        stg.state_dir / "bench_harian.json",
        batas=BatasStrategi(
            maks_trade=stg.bench_max_trade_harian, maks_fee_usd=stg.bench_max_fee_harian_usd
        ),
    )

    if len(curr_pos) >= stg.max_concurrent_positions:
        return f"slot posisi crypto penuh ({len(curr_pos)}/{stg.max_concurrent_positions})"

    # Batas korelasi (rekomendasi #9, 15 Okt): maks posisi SE-ARAH. Slot penuh =
    # semua posisi bisa buka arah yang sama; kartu resisten BTC berbalik →
    # semuanya rugi serentak. maks_searah 2 dari 3 slot: selalu tersisih satu
    # slot bagi arah berlawanan.
    arah_terbuka: dict[str, int] = {}
    for p in curr_pos:
        ar = str(getattr(p, "direction", "") or "").upper()
        if ar:
            arah_terbuka[ar] = arah_terbuka.get(ar, 0) + 1

    # Filter rezim BTC (rekomendasi #9): hitung TREN sekali per siklus, bukan per
    # kandidat. SHORT hanya saat BTC di bawah EMA50 4H, LONG hanya saat di atas.
    # Data gagal terbaca → sengaja SKIP kandidat (fail-closed, kultur rumah):
    # lebih baik tanpa entry daripada masuk tanpa tahu rezim.
    rezim: str | None = None
    if stg.btc_regime_filter:
        try:
            from live_trading.collectors.crypto import CryptoCollector
            from live_trading.indicators import ema as _ema

            c = CryptoCollector(stg)
            kl = c._get(stg.binance_fapi, "/fapi/v1/klines",
                        {"symbol": "BTCUSDT", "interval": "4h", "limit": 60})
            closes = [float(k[4]) for k in kl]
            if len(closes) >= 50:
                rata = _ema(closes, 50)
                if rata is not None:
                    rezim = "naik" if closes[-1] > rata else "turun"
        except Exception as exc:  # noqa: BLE001
            print(f"[paper-scan] rezim BTC gagal ({type(exc).__name__}) — kandidat diblok fail-closed")
            rezim = None
        if stg.btc_regime_filter and rezim is None:
            return "paper-scan: rezim BTC tidak terbaca — kandidat TIDAK dibuka (fail-closed)"
    else:
        rezim = "nonaktif"

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
            direction = r["direction"].upper()
            # Batas harian per strategi: melebihi trade/fee → 'benched', dilewati hari itu.
            nama_strategi = str(r.get("strategy") or "paper-crypto")
            boleh_bench, alasan_bench = bench.boleh_entry(nama_strategi)
            if not boleh_bench:
                dilewati.append(f"{pair} {alasan_bench}")
                continue
            blokir = blokir_korelasi_rezim(
                direction, arah_terbuka, rezim, stg.maks_posisi_searah, stg.btc_regime_filter,
            )
            if blokir:
                dilewati.append(f"{pair} {blokir}")
                continue
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
                # Biaya SERAGAM 0,1%/sisi (fee+slippage) — kebijakan owner 16 Okt 2026
                # supaya perbandingan antar-strategi paper ADIL. Buku order tidak lagi
                # diukur per pair: pair tipis tidak boleh "bayar" lebih mahal hanya karena
                # likuidasnya. `asumsi=True` tetap jujur — ini kebijakan datar, bukan terukur.
                from live_trading.execution import costs

                biaya: dict[str, Any] = costs.biaya_seragam()

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
                    strategi=nama_strategi,
                )
                # Cap korelasi: hitungan searah naik SETELAH sukses buka, supaya
                # kandidat searah berikutnya dalam siklus yang sama ikut terhitung.
                arah_k = kep.arah.upper()
                arah_terbuka[arah_k] = arah_terbuka.get(arah_k, 0) + 1
                # Jejak keputusan disimpan supaya bisa dibandingkan baris-demi-baris dengan
                # mode live nanti — itu bukti 1:1 yang bisa diperiksa, bukan klaim.
                s.add(Event(type="keputusan.masuk", actor="paper_scan",
                            payload_json={**kep.to_dict(), "jalur": jalur_untuk(kep),
                                          "sumber_biaya": biaya.get("sumber")},
                            severity="info"))
                s.add(Event(type="cost.measured", actor="paper_scan",
                            payload_json={"pair": pair, "direction": direction,
                                          "size_usd": dec.size_usd, **biaya},
                            severity="info"))
                kondisi = alert_entry(
                    nama_strategi,
                    signal_id=pos.signal_id,
                    pair=pos.pair,
                    direction=pos.direction,
                    entry=pos.entry,
                    stop=pos.stop,
                    tp1=pos.tp1,
                    tp2=pos.tp2,
                    mode="paper",
                    size_usd=pos.size_usd,
                    risk_usd=dec.risk_usd,
                    biaya_bps=biaya.get("total_bps"),
                )
                _alert(
                    s, subject=kondisi.subjek, message=kondisi.pesan,
                    aksi=kondisi.subjek_aksi, severity=kondisi.severity,
                )
                s.add(Event(
                    type="trade.opened", actor="paper_scan",
                    payload_json=pos.to_dict(), severity="info",
                ))
                dibuka.append(f"{pos.signal_id} {pos.pair} {pos.direction}")
                # Catat trade + fee ke batas harian strategi (bisa membuatnya 'benched').
                fee_usd = float(kep.size_usd or 0.0) * float(kep.cost_bps or 0.0) / 10_000.0
                status_sebelum = bench.status(nama_strategi)
                entri_bench = bench.catat(nama_strategi, fee_usd=fee_usd)
                alert_bench_jika_transisi(
                    s, bench, nama_strategi, status_sebelum=status_sebelum, entri=entri_bench,
                )

    if dibuka:
        kirim_tertunda(s, limit=5)

    detail = ", ".join(dibuka) or "tidak ada yang lolos gate"
    lewat = f" dilewati={','.join(sorted(set(dilewati)))}" if dilewati else ""
    return f"kandidat={len(rows)} dibuka={len(dibuka)}{lewat} detail={detail}"


