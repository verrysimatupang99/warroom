"""Uji collector radar lokal (recreate dari VM Azure) — tanpa jaringan.

`scan_chain` diuji dengan `_run` yang dipalsukan; tidak ada panggilan `gmgn-cli` nyata.
Yang dijaga di sini: klasifikasi jendela, gerbang keamanan/kedalaman, dan aturan
"gagal ≠ kosong" (state lama tidak boleh ditimpa oleh hasil kosong).
"""

from __future__ import annotations

import json

from live_trading.collectors import radar as r


def _tmp_berisi(rows: list[dict], gas: float = 1.0):
    """Palasukan `_run`: market trending → rows, gas-price → native_usd."""

    def fake(args: list[str], *, retries: int = 3):  # noqa: ARG001
        if args[:2] == ["market", "trending"]:
            return {"data": {"rank": rows}}
        if args[:1] == ["gas-price"]:
            return {"native_token_usd_price": gas}
        return None

    return fake


def _row(liq=100_000, vol=300_000, mc=1_000_000, rug=0.05, bund=0.05, ins=0.05,
         top10=0.1, hold=500):
    return {
        "liquidity": str(liq),
        "volume_24h": str(vol),
        "market_cap": str(mc),
        "rug_ratio": str(rug),
        "bundler_rate": str(bund),
        "rat_trader_amount_rate": str(ins),
        "top_10_holder_rate": str(top10),
        "holder_count": str(hold),
    }


def test_scan_chain_klasifikasi_prima(monkeypatch):
    """Chain muda (<=14 hari) + avg V/L >= 0.5 → PRIME."""
    monkeypatch.setattr(
        r, "_run", _tmp_berisi([_row(liq=100_000, vol=1_000_000, hold=500)], gas=1.23)
    )
    # 'arc' launch 2026-09-16; paksa usia = 10 hari lewat patch tanggal?
    # Lebih stabil: uji klasifikasi langsung, scan cukup memastikan bentuk data.
    s = r.scan_chain("arc", 60)
    assert s.chain == "arc" and s.pools == 1
    assert s.native_usd == 1.23
    assert s.avg_vl == 10.0
    assert s.hp_count == 1, "V/L 10 + liq 100k + aman → high-potential"
    assert s.window in {"PRIME", "OPEN", "CLOSING", "CLOSED", "DRY"}


def test_klasifikasi_window_langsung():
    assert r._klasifikasi(10, 1.0)[0] == "PRIME"
    assert r._klasifikasi(20, 1.0)[0] == "OPEN"
    assert r._klasifikasi(50, 0.3)[0] == "CLOSING"
    assert r._klasifikasi(100, 5.0)[0] == "CLOSED"
    assert r._klasifikasi(10, 0.0)[0] == "DRY"
    assert r._klasifikasi(None, 9.9)[0] == "UNKNOWN"


def test_scan_chain_gerbang_keamanan(monkeypatch):
    """Rug/bundler/insider/top10 di atas ambang → tidak viable, tidak HP."""
    monkeypatch.setattr(
        r, "_run", _tmp_berisi([_row(rug=0.9, bund=0.9, ins=0.9, top10=0.9)], gas=1.0)
    )
    s = r.scan_chain("eth", 60)
    assert s.viable == 0 and s.hp_count == 0
    assert s.avg_vl == 3.0, "V/L tetap dihitung; yang digagalkan adalah gerbang aman"


def test_volume_fallback_dari_volume_kali_24(monkeypatch):
    """`volume_24h` kosong → pakai `volume` × 24 (perilaku lama dipertahankan)."""
    row = _row(liq=100_000)
    row.pop("volume_24h")
    row["volume"] = "10_000".replace("_", "")
    monkeypatch.setattr(r, "_run", _tmp_berisi([row], gas=1.0))
    s = r.scan_chain("base", 60)
    assert s.total_vol_24h == 240_000


def test_jalankan_radar_gagal_tidak_menimpa_state(tmp_path, monkeypatch):
    """Semua chain gagal → hasil kosong; state lama TIDAK boleh tertimpa."""
    state = tmp_path / "radar_state.json"
    state.write_text(json.dumps({"diambil_epoch": 1.0, "chains": [{"chain": "arc"}]}), "utf-8")
    monkeypatch.setattr(r, "scan_chain", lambda ch, limit: (_ for _ in ()).throw(RuntimeError("mati")))
    monkeypatch.setattr(r.time, "sleep", lambda *_: None)
    out = r.jalankan_radar(chains="arc", state_path=state)
    assert out["chains"] == []
    isi = json.loads(state.read_text("utf-8"))
    assert isi["chains"] == [{"chain": "arc"}], "state lama harus utuh (gagal ≠ kosong)"


def test_jalankan_radar_sukses_menulis_state(tmp_path, monkeypatch):
    """Sukses → state ditulis dengan sumber lokal + diambil_epoch."""
    monkeypatch.setattr(
        r, "scan_chain",
        lambda ch, limit: r.ChainStat(
            chain=ch, age_days=20, pools=5, total_liq=1.0, total_vol_24h=2.0, total_mcap=3.0,
            avg_vl=0.6, best_vl=1.0, viable=1, hp_count=0, native_usd=1.0,
            window="OPEN", note="ok",
        ),
    )
    monkeypatch.setattr(r.time, "sleep", lambda *_: None)
    state = tmp_path / "radar_state.json"
    out = r.jalankan_radar(chains="arc", state_path=state)
    isi = json.loads(state.read_text("utf-8"))
    assert isi["sumber"] == "lokal"
    assert isinstance(isi["diambil_epoch"], float)
    assert isi["chains"][0]["chain"] == "arc"
    assert out["alerts"] and out["alerts"][0].startswith("NEW")
    assert "arc" in out["alerts"][0]


def test_diff_deteksi_turun_dan_spike():
    prev = {"arc": {"chain": "arc", "window": "OPEN", "age_days": 20, "avg_vl": 0.6, "hp_count": 0}}
    now = [
        r.ChainStat(
            chain="arc", age_days=20, pools=5, total_liq=1.0, total_vol_24h=2.0, total_mcap=3.0,
            avg_vl=3.0, best_vl=5.0, viable=1, hp_count=3, native_usd=1.0,
            window="CLOSING", note="x",
        )
    ]
    alerts = r.diff_and_alert(prev, now)
    assert any(a.startswith("DOWN arc") for a in alerts)
    assert any(a.startswith("SPIKE arc") for a in alerts)
    assert any(a.startswith("HP") for a in alerts)
