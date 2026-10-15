#!/usr/bin/env python3
"""Backtest Strategi A (SMA harian) 4 tahun OOS — spec agent-2 §3.4.

Output: laporan teks + JSON di docs/blueprint/ (dipakai bukti fase 1 rollout).
Perbandingan wajib: buy-and-hold & DCA bulanan, sama modal.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "live-trading" / "src"))

from live_trading import harian  # noqa: E402

from ops.harian_cycle import _klines  # noqa: E402

ASSETS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
FEE_BPS = harian.FEE_BPS_SPOT + harian.SLIP_BPS_ASUMSI
EQUITY0 = 10.0


def jika_bnh(kl: dict[str, list[list]], fee_bps: float) -> dict[str, float]:
    hasil = {}
    for pair, rows in kl.items():
        closes = [float(k[4]) for k in rows]
        len(closes) // 3   # tiled: bandingkan pada jendela sama dgn OOS? — pakai full
        awal, akhir = closes[0], closes[-1]
        fee = 2 * fee_bps / 10_000
        hasil[pair] = (akhir / awal) * (1 - fee) - 1
    return hasil


def main() -> int:
    import datetime as dt

    kl = {p: _klines(p) for p in ASSETS}
    panjang = min(len(v) for v in kl.values())   # sejajarkan
    closes = {p: [float(k[4]) for k in v[-panjang:]] for p, v in kl.items()}

    hasil_semua = {}
    for sma_n in (50, 100):
        for confirm in (1, 2, 3):
            per_aset = {p: harian.jalankan_backtest(c, sma_n=sma_n, confirm_closes=confirm,
                                                    equity0=EQUITY0, fee_bps=FEE_BPS)
                        for p, c in closes.items()}
            daftar = list(per_aset.values())

            def _avg(attr: str, _daftar=daftar) -> float:
                return sum(getattr(b, attr) for b in _daftar) / len(_daftar)
            hasil_semua[f"SMA{sma_n}/c{confirm}"] = {
                "per_aset": {p: {"ret": round(b.total_return * 100, 2),
                                 "dd": round(b.max_drawdown * 100, 2)} for p, b in per_aset.items()},
                "avg_ret_pct": round(_avg("total_return") * 100, 2),
                "avg_dd_pct": round(_avg("max_drawdown") * 100, 2),
                "oos_ret_pct": round(_avg("total_return_oos") * 100, 2),
                "oos_dd_pct": round(_avg("max_drawdown_oos") * 100, 2),
                "n_trade": round(sum(b.n_trade for b in daftar) / 3, 1),
            }

    bnh = jika_bnh(kl, FEE_BPS)
    hasil_semua["UNIVERSE_BUY_HOLD"] = {p: round(v * 100, 2) for p, v in bnh.items()}

    import json
    out = json.dumps(hasil_semua, indent=2)
    tulis = Path("docs/blueprint/strategi-harian-backtest-20261016.json")
    tulis.write_text(out, encoding="utf-8")
    print(out)
    mulai = dt.datetime.fromtimestamp(min(min(k[0] for k in v) for v in kl.values()) / 1000, dt.UTC)
    akhir = dt.datetime.fromtimestamp(max(max(k[6] for k in v) for v in kl.values()) / 1000, dt.UTC)
    print(f"rentang data: {mulai.date()} → {akhir.date()} ({panjang} hari), fee+slip {FEE_BPS} bps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
