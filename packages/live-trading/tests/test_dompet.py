"""Tes dompet paper Rp 10 juta per market — kejujuran angka di atas kenyamanan tampilan.

Prinsip yang ditegakkan:
1. Kurs wajib; tanpanya saldo TIDAK dikarang (`tersedia=False`).
2. Risiko per trade = % × saldo AWAL (tanpa compounding) — sampel kecil tidak dibungkus
   dengan efek majemuk.
3. Ledger kosong ≠ saldo nol: `tersedia=False` + alasan.
4. Saldo boleh MINUS (IDX: ARA_HUNTER menghabiskan dompet) — itu temuan, bukan bug.
5. Konsistensi aritmetika: pnl_pct = pnl/unit; saldo_akhir = unit + pnl.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from live_trading import dompet
from live_trading import dompet as dp


def _ledger(state: Path, nama: str, baris: list[dict]) -> None:
    (state / nama).write_text(
        "\n".join(json.dumps(b) for b in baris) + "\n", encoding="utf-8"
    )


def test_tanpa_kurs_tidak_mengarang(tmp_path: Path):
    _ledger(tmp_path, "crypto_equity.jsonl", [{"signal_id": "a", "r": 1.0, "closed_at": "2026-10-01"}])
    out = dp.ringkas_dompet(tmp_path, market="crypto", kurs=None, sumber="uji")
    assert out["tersedia"] is False
    assert "kurs" in out["alasan"].lower()


def test_ledger_kosong_bukan_nol(tmp_path: Path):
    out = dp.ringkas_dompet(tmp_path, market="crypto", kurs=17000.0, sumber="uji")
    assert out["tersedia"] is False
    assert out["alasan"]


def test_hitung_saldo_dan_tanpa_compounding(tmp_path: Path):
    # Dua trade: +1R dan -0.5R. Risiko 1% dari saldo awal 10jt/17000 = 588.24 USD → 5.8824 USD.
    _ledger(
        tmp_path,
        "crypto_equity.jsonl",
        [
            {"signal_id": "a", "r": 1.0, "closed_at": "2026-10-01T00:00:00+00:00"},
            {"signal_id": "b", "r": -0.5, "closed_at": "2026-10-02T00:00:00+00:00"},
        ],
    )
    out = dp.ringkas_dompet(tmp_path, market="crypto", kurs=17000.0, sumber="uji")
    assert out["tersedia"] is True
    unit = 10_000_000 / 17000
    assert abs(out["saldo_awal_unit"] - unit) < 0.01
    risiko = unit * 0.01
    assert abs(out["pnl_usd"] - (1.0 - 0.5) * risiko) < 0.01
    assert abs(out["saldo_akhir_usd"] - (unit + 0.5 * risiko)) < 0.01
    # trade kedua memakai risiko YANG SAMA (bukan risiko dari saldo yang sudah naik)
    assert abs(out["titik"][2]["pnl_usd"] - (-0.5 * risiko)) < 0.01


def test_saldo_boleh_minus(tmp_path: Path):
    """Dompet IDX bisa habis; itu yang harus terlihat, bukan dijepit ke nol."""
    _ledger(
        tmp_path,
        "idx_equity.jsonl",
        [{"signal_id": str(i), "r": -1.0, "closed_at": f"2026-10-0{i}T00:00:00+00:00"} for i in range(1, 6)],
    )
    out = dp.ringkas_dompet(tmp_path, market="idx", kurs=17000.0, risk_pct=30.0, sumber="uji")
    assert out["tersedia"] is True
    assert out["pnl_idr"] < 0
    assert out["pnl_pct"] < -100  # lebih rugi daripada modal → minus, dan itu ditampilkan


def test_pnL_idr_mengikuti_kurs(tmp_path: Path):
    _ledger(tmp_path, "crypto_equity.jsonl", [{"signal_id": "a", "r": 2.0, "closed_at": "2026-10-01"}])
    a = dp.ringkas_dompet(tmp_path, market="crypto", kurs=16000.0, sumber="uji")
    b = dp.ringkas_dompet(tmp_path, market="crypto", kurs=17000.0, sumber="uji")
    # saldo unit berbeda (kurs), tapi PnL rupiah = r × 1% × 10jt → sama
    assert abs(a["pnl_idr"] - b["pnl_idr"]) < 1.0


def test_biaya_tidak_tercatat_dinyatakan(tmp_path: Path):
    _ledger(tmp_path, "crypto_equity.jsonl", [{"signal_id": "a", "r": 1.0, "closed_at": "2026-10-01"}])
    out = dp.ringkas_dompet(tmp_path, market="crypto", kurs=17000.0, sumber="uji")
    assert out["biaya_tercatat"] is False
    assert any("bruto" in c for c in out["catatan"])


def test_gmgn_mark_terakhir_bukan_penjumlahan(tmp_path: Path):
    """Temuan audit 7 Okt: satu posisi LP punya 22 baris mark. Dompet tidak boleh
    menjumlahkan semuanya (dulu: modal $660 & PnL −3,17% dari 1 posisi $30).

    Kurs ditulis ke cache lebih dulu: tanpa itu tes ini memanggil jaringan
    (frankfurter.app) dan hasilnya berubah-ubah antar-run — pernah merah di suite
    penuh lalu hijau saat dijalankan sendiri (flaky, bukan bug dompet).
    """
    (tmp_path / "kurs_usd_idr.json").write_text(
        json.dumps({"kurs": 17_841.0, "diambil": dt.datetime.now(dt.UTC).isoformat(),
                    "sumber": "tes"}),
        encoding="utf-8",
    )
    baris = [
        {"symbol": "UBI", "status": "dinilai", "notional_usd": 30.0, "harga_masuk": 5.8e-06,
         "pnl_usd": -0.5, "ts": "2026-10-01T00:00:00+00:00"},
        {"symbol": "UBI", "status": "dinilai", "notional_usd": 30.0, "harga_masuk": 5.8e-06,
         "pnl_usd": -0.9, "ts": "2026-10-02T00:00:00+00:00"},
        {"symbol": "UBI", "status": "dinilai", "notional_usd": 30.0, "harga_masuk": 5.8e-06,
         "pnl_usd": -1.05, "ts": "2026-10-03T00:00:00+00:00"},
    ]
    _ledger(tmp_path, "lp_ledger.jsonl", baris)
    out = dompet.ringkas_semua_dompet(tmp_path)["pasar"]["gmgn"]
    assert out["tersedia"] is True
    assert out["trade"] == 1, "tiga mark = SATU posisi"
    assert out["mark_baris"] == 3
    # PnL = mark TERAKHIR saja (−1.05), bukan jumlah (−2.45)
    unit = 10_000_000 / out["kurs_usd_idr"]
    assert abs(out["pnl_usd"] - unit * (-1.05 / 30.0)) < 0.01
