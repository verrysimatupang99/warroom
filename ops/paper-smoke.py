#!/usr/bin/env python3
"""Smoke end-to-end jalur paper: order paper, kill switch, laporan PnL.

Kenapa ada: TODO 2 November menuntut bukti otomatis — bukan klaim manual —
bahwa jalur paper (order → risk gate → kill switch → PnL) masih utuh. Skrip ini
dijalankan job CI harian dan menulis laporan JSON sebagai artefak.

Sifat:
- deterministik: waktu disuntik (``now=``), tidak ada jam dinding;
- tanpa efek samping: tidak ada DB, jaringan, berkas, atau order nyata;
- gagal keras (exit 1) kalau satu skenario menyimpang, supaya artefak tidak
  pernah berisi laporan "hijau" dari pipeline yang rusak.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from warroom_core.paper import PaperExecutor
from warroom_core.signal import MarketData, RiskPolicy, Signal

T0 = datetime(2026, 11, 3, 0, 0, 0, tzinfo=UTC)


def _signal(signal_id: str = "s1", *, direction: str = "long") -> Signal:
    return Signal(
        signal_id=signal_id,
        market="crypto",
        venue="okx",
        instrument="BTCUSDT",
        strategy="smoke",
        direction=direction,  # type: ignore[arg-type]
        entry=100.0,
        stop=98.0,
        target=104.0,
        risk_reward=2.0,
        confidence=0.8,
        created_at=T0,
        expires_at=T0 + timedelta(minutes=5),
        freshness_s=1.0,
        reason="paper-smoke",
    )


def _data(*, spread_bps: float = 2.0, price: float = 100.0) -> MarketData:
    return MarketData("crypto", "okx", "BTCUSDT", T0, price, spread_bps, 100_000.0, {})


def _policy(**kw: object) -> RiskPolicy:
    dasar: dict[str, object] = {
        "max_age_s": 120.0,
        "max_spread_bps": 10.0,
        "risk_usd": 50.0,
        "fee_bps": 5.0,
        "slippage_bps": 5.0,
        "max_daily_loss_usd": 150.0,
        "max_open_exposure_usd": 200.0,
    }
    dasar.update(kw)
    return RiskPolicy(**dasar)  # type: ignore[arg-type]


def _cek(nama: str, syarat: bool, detail: str, galat: dict[str, str]) -> None:
    if not syarat:
        galat[nama] = detail


def jalankan() -> dict[str, object]:
    """Jalankan semua skenario; kembalikan laporan. Tidak pernah melempar."""
    galat: dict[str, str] = {}
    skenario: list[dict[str, object]] = []

    # 1. Jalur bahagia: order paper terisi, fee & slippage eksplisit.
    ex = PaperExecutor(_policy())
    fill = ex.submit(_signal("fill-1"), _data(), now=T0)
    _cek("fill_status", fill.status == "filled", f"status={fill.status}", galat)
    _cek("fill_price", fill.price == 100.05, f"price={fill.price}", galat)
    _cek("fill_fee", fill.fee_usd == 0.025, f"fee={fill.fee_usd}", galat)
    skenario.append({"nama": "order_paper_terisi", "hasil": asdict(fill)})

    # 2. Deduplikasi: id sama tidak boleh tercatat dua kali.
    dup = ex.submit(_signal("fill-1"), _data(), now=T0)
    _cek("dup_status", dup.status == "duplicate", f"status={dup.status}", galat)
    _cek("dup_total", len(ex.records) == 1, f"records={len(ex.records)}", galat)
    skenario.append({"nama": "dedup_signal_id", "hasil": asdict(dup)})

    # 3. Kill switch: saklar menyala -> SEMUA ditolak, tak ada fill.
    ex_kill = PaperExecutor(_policy(kill_switch=True))
    kill = ex_kill.submit(_signal("kill-1"), _data(), now=T0)
    _cek("kill_status", kill.status == "rejected", f"status={kill.status}", galat)
    _cek("kill_reason", kill.reason == "kill_switch", f"reason={kill.reason}", galat)
    _cek("kill_tanpa_fill", all(r.status != "filled" for r in ex_kill.records), "ada fill", galat)
    skenario.append({"nama": "kill_switch_menolak", "hasil": asdict(kill)})

    # 4. Rem harian: rugi menyentuh batas -> ditolak.
    ex_dd = PaperExecutor(_policy(daily_loss_usd=150.0))
    dd = ex_dd.submit(_signal("dd-1"), _data(), now=T0)
    _cek("dd_status", dd.status == "rejected", f"status={dd.status}", galat)
    _cek("dd_reason", dd.reason == "daily_loss_limit", f"reason={dd.reason}", galat)
    skenario.append({"nama": "rem_rugi_harian", "hasil": asdict(dd)})

    # 5. Data basi: gate harus menolak, bukan meloloskan.
    data_basi = MarketData("crypto", "okx", "BTCUSDT", T0 - timedelta(seconds=600),
                           100.0, 2.0, 100_000.0, {})
    ex_basi = PaperExecutor(_policy())
    basi = ex_basi.submit(_signal("stale-1"), data_basi, now=T0)
    _cek("stale_status", basi.status == "rejected", f"status={basi.status}", galat)
    _cek("stale_reason", basi.reason == "stale_data", f"reason={basi.reason}", galat)
    skenario.append({"nama": "tolak_data_basi", "hasil": asdict(basi)})

    # 6. Fail-closed: policy kosong (None) wajib ditolak saat konstruksi.
    try:
        PaperExecutor(None)  # type: ignore[arg-type]
    except ValueError:
        skenario.append({"nama": "fail_closed_policy_kosong", "hasil": "ditolak(benar)"})
    else:
        galat["fail_closed"] = "PaperExecutor(None) tidak melempar ValueError"
        skenario.append({"nama": "fail_closed_policy_kosong", "hasil": "LOLOS(salah)"})

    # 7. Ringkasan PnL dari sesi bahagia (biaya = fee, bukan PnL pasar).
    total_fee = sum(r.fee_usd or 0.0 for r in ex.records)
    total_risk = sum(r.risk_usd or 0.0 for r in ex.records)
    pnl = {
        "jumlah_order": len(ex.records),
        "terisi": sum(1 for r in ex.records if r.status == "filled"),
        "ditolak": sum(1 for r in ex.records if r.status == "rejected"),
        "duplikat": sum(1 for r in ex.records if r.status == "duplicate"),
        "risiko_terpakai_usd": round(total_risk, 6),
        "biaya_usd": round(total_fee, 6),
        "pnl_realisasi_usd": 0.0,
    }

    return {
        "skrip": "paper-smoke",
        "dibuat": datetime.now(UTC).isoformat(),
        "lulus": not galat,
        "jumlah_skenario": len(skenario),
        "skenario": skenario,
        "pnl": pnl,
        "galat": galat,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Smoke end-to-end jalur paper War Room.")
    p.add_argument("-o", "--out", type=Path, default=Path("paper-smoke-report.json"),
                   help="berkas laporan JSON (default: paper-smoke-report.json)")
    a = p.parse_args()

    laporan = jalankan()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(
        json.dumps(laporan, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    galat: dict[str, str] = laporan["galat"]  # type: ignore[assignment]
    if not galat:
        print(f"LULUS: {laporan['jumlah_skenario']} skenario -> {a.out}")
        return 0
    print(f"GAGAL: {sorted(galat)} -> {a.out}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
