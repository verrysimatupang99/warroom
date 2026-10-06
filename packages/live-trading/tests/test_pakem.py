"""Uji pakem bukti — ambang, koreksi klaster hari, kejujuran sampel nol.

Pakem disepakati owner 6 Okt: INSUFFICIENT <10 · DIRECTIONAL 10–29 ·
PRELIMINARY 30+ · TUNING 100+; win rate tinggi tidak pernah cukup.
"""

from __future__ import annotations

from live_trading import pakem as p


def _seri(
    n: int,
    *,
    menang_rasio: float = 0.6,
    r_win: float = 1.0,
    r_loss: float = -1.0,
    hari_berbeda: int | None = None,
    mulai: str = "2026-09-01",
):
    """Bangun seri trade tuntas; `hari_berbeda` memaksa koreksi klaster."""
    rows = []
    for i in range(n):
        menang = (i / max(1, n)) < menang_rasio
        hari = i if hari_berbeda is None else (i % hari_berbeda)
        from datetime import date, timedelta

        d = date.fromisoformat(mulai) + timedelta(days=hari)
        rows.append({"r": r_win if menang else r_loss, "closed_at": d.isoformat() + "T10:00:00+07:00"})
    return rows


def test_ambang_sampel():
    assert p.nilai_pakem([]).tingkat == "INSUFFICIENT"
    # 5 trade di 5 hari berbeda → tetap insufficient
    h = p.nilai_pakem(_seri(5, hari_berbeda=5))
    assert h.tingkat == "INSUFFICIENT" and h.n_hari == 5
    # 12 trade di 12 hari → DIRECTIONAL
    h = p.nilai_pakem(_seri(12, hari_berbeda=12))
    assert h.tingkat == "DIRECTIONAL"
    # 40 trade di 40 hari → PRELIMINARY
    h = p.nilai_pakem(_seri(40, hari_berbeda=40))
    assert h.tingkat == "PRELIMINARY"
    # 120 trade di 120 hari → TUNING
    h = p.nilai_pakem(_seri(120, hari_berbeda=120))
    assert h.tingkat == "TUNING"


def test_koreksi_klaster_hari():
    """35 trade tapi hanya 11 hari → tetap DIRECTIONAL (bukan PRELIMINARY)."""
    h = p.nilai_pakem(_seri(35, hari_berbeda=11))
    assert h.n == 35 and h.n_hari == 11
    assert h.tingkat == "DIRECTIONAL", "koreksi klaster hari harus menahan tingkat"


def test_win_rate_tinggi_tidak_cukup():
    """WR 100% tapi expectancy negatif (banyak -2R) → tetap ditolak di alasan."""
    rows = []
    for i in range(40):
        from datetime import date, timedelta

        d = date.fromisoformat("2026-09-01") + timedelta(days=i)
        # 25 menang +1R, 15 kalah -2R → net -5R, WR 62,5%
        rows.append({"r": 1.0 if i < 25 else -2.0, "closed_at": d.isoformat()})
    h = p.nilai_pakem(rows)
    assert h.ringkas["winrate_pct"] == 62.5
    assert h.ringkas["mean_r"] is not None and h.ringkas["mean_r"] < 0
    assert any("expectancy" in a for a in h.alasan)


def test_nol_bukan_persen():
    h = p.nilai_pakem([])
    assert h.ringkas["winrate_pct"] is None, "n=0 tidak boleh jadi 0%"
    assert h.ci_winrate == (0.0, 0.0)
    assert any("n=0" in a for a in h.alasan)


def test_tanpa_tanggal_dicatat_jujur():
    rows = [{"r": 1.0}, {"r": -1.0}]
    h = p.nilai_pakem(rows)
    assert h.n_hari == 0
    assert any("tanggal" in a for a in h.alasan)


def test_profit_factor_dan_drawdown():
    rows = [
        {"r": 2.0, "closed_at": "2026-09-01"},
        {"r": -1.0, "closed_at": "2026-09-02"},
        {"r": -1.0, "closed_at": "2026-09-03"},
        {"r": 3.0, "closed_at": "2026-09-04"},
    ]
    r = p.ringkas_r([x["r"] for x in rows])
    assert r["profit_factor"] == 2.5
    assert r["max_drawdown_r"] == 2.0  # 2 → 1 → 0
    assert r["total_r"] == 3.0


def test_biaya_belum_tercatat_dicatat():
    h = p.nilai_pakem(_seri(40, hari_berbeda=40), biaya_tercatat=False)
    assert any("biaya" in a for a in h.alasan)
    h2 = p.nilai_pakem(_seri(40, hari_berbeda=40), biaya_tercatat=None)
    assert any("tidak diketahui" in a for a in h2.alasan)
