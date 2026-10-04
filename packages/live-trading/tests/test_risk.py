"""Kontrak risk gate — batas harus ditegakkan SEBELUM order, bukan sesudah."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from live_trading.config import get_settings
from live_trading.risk import RiskGate, r_closed_on, read_ledger


def _gate(tmp_path: Path, **over) -> RiskGate:
    s = get_settings(home=tmp_path, **over)
    s.ensure_dirs()
    return RiskGate(s)


def test_ukuran_posisi_dari_atr(tmp_path: Path) -> None:
    """Risiko per trade tetap: stop lebih lebar -> ukuran lebih kecil."""
    g = _gate(tmp_path, risk_per_trade_pct=1.0)

    lebar = g.check(pair="BTCUSDT", price=100.0, atr=4.0, equity_usd=1000.0)  # stop 6%
    sempit = g.check(pair="BTCUSDT", price=100.0, atr=1.0, equity_usd=1000.0)  # stop 1.5%

    assert lebar.allowed and sempit.allowed
    assert lebar.risk_usd == 10.0 and sempit.risk_usd == 10.0
    assert lebar.size_usd < sempit.size_usd
    assert lebar.size_usd == 166.67  # 10 / 0.06


def test_batas_rugi_harian_menolak(tmp_path: Path) -> None:
    g = _gate(tmp_path, daily_loss_limit_r=3.0)
    today = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=7)).strftime("%Y-%m-%d")
    g.s.ledger_path.write_text(
        json.dumps({"closed_at": f"{today}T10:00:00+07:00", "r": -3.5}) + "\n", encoding="utf-8"
    )

    d = g.check(pair="BTCUSDT", price=100.0, atr=1.0, equity_usd=1000.0)

    assert not d.allowed
    assert "rugi harian" in d.reason


def test_posisi_bersamaan_penuh_ditolak(tmp_path: Path) -> None:
    g = _gate(tmp_path, max_concurrent_positions=1)
    (g.s.state_dir / "paper_positions.json").write_text(
        json.dumps({"positions": [{"pair": "ETHUSDT"}]}), encoding="utf-8"
    )

    d = g.check(pair="BTCUSDT", price=100.0, atr=1.0, equity_usd=1000.0)

    assert not d.allowed
    assert "penuh" in d.reason


def test_pair_ganda_ditolak(tmp_path: Path) -> None:
    """Dua posisi di pair yang sama = menambah risiko tanpa keputusan baru."""
    g = _gate(tmp_path)
    (g.s.state_dir / "paper_positions.json").write_text(
        json.dumps({"positions": [{"pair": "BTCUSDT"}]}), encoding="utf-8"
    )

    d = g.check(pair="BTCUSDT", price=100.0, atr=1.0, equity_usd=1000.0)

    assert not d.allowed
    assert "sudah punya posisi" in d.reason


def test_atr_nol_ditolak_bukan_dibulatkan(tmp_path: Path) -> None:
    d = _gate(tmp_path).check(pair="BTCUSDT", price=100.0, atr=0.0, equity_usd=1000.0)

    assert not d.allowed


def test_ukuran_melebihi_ekuitas_ditolak(tmp_path: Path) -> None:
    """Stop sangat sempit butuh leverage besar — harus ditolak, bukan dieksekusi."""
    d = _gate(tmp_path, risk_per_trade_pct=50.0).check(
        pair="BTCUSDT", price=100.0, atr=0.01, equity_usd=100.0
    )

    assert not d.allowed
    assert "leverage" in d.reason


def test_leverage_dibuka_hanya_kalau_disengaja(tmp_path: Path) -> None:
    """Default 1x menolak; setelah LT_MAX_LEVERAGE dinaikkan, trade yang sama lolos."""
    args = {"pair": "BTCUSDT", "price": 84500.0, "atr": 466.0, "equity_usd": 500.0}

    tolak = _gate(tmp_path).check(**args)
    lolos = _gate(tmp_path, max_leverage=3.0).check(**args)

    assert not tolak.allowed
    assert "leverage" in tolak.reason
    assert lolos.allowed
    assert lolos.size_usd is not None and lolos.size_usd > 500.0


def test_r_harian_hanya_menghitung_hari_itu(tmp_path: Path) -> None:
    rows = [
        {"closed_at": "2026-09-26T10:00:00+07:00", "r": 5.0},
        {"closed_at": "2026-09-27T10:00:00+07:00", "r": -1.0},
        {"closed_at": "2026-09-27T12:00:00+07:00", "r": 0.5},
    ]

    assert r_closed_on(rows, "2026-09-27") == -0.5


def test_ledger_rusak_tidak_mematikan_pembacaan(tmp_path: Path) -> None:
    """Satu baris rusak jangan bikin seluruh ledger tak terbaca."""
    p = tmp_path / "l.jsonl"
    p.write_text('{"r": 1.0}\nbukan json\n{"r": 2.0}\n', encoding="utf-8")

    assert len(read_ledger(p)) == 2


def test_kunci_executor_menolak_host_lain(tmp_path: Path) -> None:
    """Ini yang mencegah dua mesin mengeksekusi akun yang sama."""
    s = get_settings(home=tmp_path)
    s.ensure_dirs()
    g = RiskGate(s)
    s.executor_lock_path.write_text(
        json.dumps({"host": "mesin-lain", "pid": 1, "ts": dt.datetime.now(dt.UTC).timestamp()}),
        encoding="utf-8",
    )

    res = g.acquire_executor_lock()

    assert res["ok"] is False
    assert "mesin-lain" in res["reason"]


def test_kunci_basi_bisa_diambil_alih(tmp_path: Path) -> None:
    """Kunci yang host-nya sudah mati tidak boleh memblokir selamanya."""
    s = get_settings(home=tmp_path)
    s.ensure_dirs()
    g = RiskGate(s)
    s.executor_lock_path.write_text(
        json.dumps({"host": "mesin-mati", "pid": 1, "ts": dt.datetime.now(dt.UTC).timestamp() - 9999}),
        encoding="utf-8",
    )

    assert g.acquire_executor_lock()["ok"] is True


def _tulis_ledger(path: Path, baris: list[str]) -> None:
    path.write_text("\n".join(baris) + "\n", encoding="utf-8")


def _hari_ini() -> str:
    from live_trading.risk import _today_wib

    return _today_wib()


def test_ledger_rusak_MENOLAK_entry(tmp_path: Path) -> None:
    """Gagal-tertutup: ledger yang tidak bisa dipastikan bukan 'tidak ada kerugian'.

    Regresi yang dijaga: `read_ledger` melewatkan baris rusak tanpa sepatah kata, dan
    `daily_r` membacanya sebagai 0. Satu baris terpotong (proses mati saat menulis)
    cukup untuk menghapus kerugian dari perhitungan dan MEMBUKA entry padahal batas
    rugi harian sudah terlampaui. Diverifikasi: dengan baris utuh gate menolak
    (-4R <= -3R), dengan baris rusak gate dulu mengizinkan.
    """
    g = _gate(tmp_path)
    hari = _hari_ini()
    # dua kerugian 2R; baris kedua terpotong
    _tulis_ledger(
        g.s.ledger_path,
        [json.dumps({"closed_at": hari + "T10:00:00+07:00", "r": -2.0}),
         '{"closed_at": "' + hari + 'T11:00:00+07:00", "r": -2.0'],
    )
    d = g.check(pair="BTCUSDT", price=100.0, atr=2.0, equity_usd=100.0)
    assert not d.allowed, "ledger rusak harus MENOLAK, bukan mengizinkan entry"
    assert "tidak bisa dipastikan" in d.reason


def test_ledger_utuh_dengan_batas_terlampaui_menolak(tmp_path: Path) -> None:
    g = _gate(tmp_path)
    hari = _hari_ini()
    _tulis_ledger(
        g.s.ledger_path,
        [json.dumps({"closed_at": hari + "T10:00:00+07:00", "r": -2.0}),
         json.dumps({"closed_at": hari + "T11:00:00+07:00", "r": -2.0})],
    )
    d = g.check(pair="BTCUSDT", price=100.0, atr=2.0, equity_usd=100.0)
    assert not d.allowed
    assert "batas rugi harian" in d.reason


def test_ledger_belum_ada_bukan_kerusakan(tmp_path: Path) -> None:
    """Sistem baru belum punya trade — itu keadaan sah, bukan alasan menolak."""
    g = _gate(tmp_path)
    assert not g.s.ledger_path.is_file()
    d = g.check(pair="BTCUSDT", price=100.0, atr=2.0, equity_usd=100.0)
    assert d.allowed, "ledger yang belum ada tidak boleh menolak entry"


def test_ledger_utuh_rugi_kecil_tetap_boleh(tmp_path: Path) -> None:
    g = _gate(tmp_path)
    hari = _hari_ini()
    _tulis_ledger(g.s.ledger_path, [json.dumps({"closed_at": hari + "T10:00:00+07:00", "r": -1.0})])
    d = g.check(pair="BTCUSDT", price=100.0, atr=2.0, equity_usd=100.0)
    assert d.allowed


def test_read_ledger_strict_melaporkan_integritas(tmp_path: Path) -> None:
    from live_trading.risk import read_ledger_strict

    p = tmp_path / "l.jsonl"
    _tulis_ledger(p, ['{"r": 1.0}', "bukan json", '{"r": 2.0}'])
    r = read_ledger_strict(p)
    assert r.exists and len(r.rows) == 2 and r.unreadable == 1

    p.unlink()
    r2 = read_ledger_strict(p)
    assert not r2.exists and r2.rows == [] and r2.unreadable == 0
