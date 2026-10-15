"""Tes pengiriman live crypto — semua jalur REFUSAL harus terbukti (15 Okt 2026).

Prinsip: order nyata tidak boleh bisa keluar lewat jalan pintas. Tes ini membuktikan
setiap penyumbatan: tanpa file izin owner, tanpa kunci, mode salah, keputusan ditolak,
dan venue tanpa bazir() langsung betulan. Hanya SATU jalur lolos = ketiga syarat penuh
+ transport disuntik (mock) — dan tanda HMAC diverifikasi vektor deterministik.
"""

from __future__ import annotations

import hashlib
import hmac
from urllib.parse import parse_qs

import pytest

from live_trading.execution.keputusan import Keputusan, kirim_ke_live
from live_trading.execution.live_venue import (
    FILE_IZIN_OWNER,
    LiveTerblokir,
    LiveVenueCrypto,
    MexcSpotTransport,
    status_gerbang_live,
)


def keputusan_live(masuk: bool = True) -> Keputusan:
    return Keputusan(
        masuk=masuk, alasan="tes", pair="BTCUSDT", arah="LONG",
        entry=67000.0, sl=66000.0, size_usd=5.0, risk_usd=0.5, mode="live",
    )


# -- gerbang ------------------------------------------------------------------

def test_status_gerbang_default_tertutup(monkeypatch):
    monkeypatch.delenv("MEXC_API_KEY", raising=False)
    monkeypatch.delenv("MEXC_API_SECRET", raising=False)
    st = status_gerbang_live()
    assert st["siap"] is False
    assert "MEXC_API_KEY" in [k for k, v in st["kunci_ada"].items() if not v]


def test_kirim_ke_live_tanpa_izin_menolak(monkeypatch):
    """Tanpa file izin owner atau kunci → LiveTerblokir (analog 409)."""
    monkeypatch.delenv("MEXC_API_KEY", raising=False)
    monkeypatch.delenv("MEXC_API_SECRET", raising=False)
    with pytest.raises(LiveTerblokir, match="terblokir"):
        kirim_ke_live(keputusan_live())


def test_kirim_ke_live_mode_paper_menolak():
    with pytest.raises(ValueError, match="mode=live"):
        kirim_ke_live(Keputusan(True, "tes", mode="paper"))


def test_transport_kunci_rabili(monkeypatch):
    """Nilai kunci tidak boleh bocor ke pesan galat."""
    monkeypatch.setenv("MEXC_API_KEY", "KUNCI-RAHASIA-XYZ")
    monkeypatch.setenv("MEXC_API_SECRET", "SANGATRAHASIA")
    # file izin tidak dibuat → LiveTerblokir YA DI LEVEL BANGUN (sebelum kunci dipakai)
    with pytest.raises(LiveTerblokir) as exc:
        LiveVenueCrypto.bangun()
    assert "SANGATRAHASIA" not in str(exc.value)
    assert "KUNCI-RAHASIA-XYZ" not in str(exc.value)


# -- venue lengkap (izin disimulasikan via stub path) --------------------------

def test_venue_lengkap_lolos_dan_keputusan_diteruskan(monkeypatch, tmp_path):
    import live_trading.execution.live_venue as lv

    izin = tmp_path / "crypto-live-approved"
    izin.write_text("tes\n", encoding="utf-8")
    monkeypatch.setattr(lv, "FILE_IZIN_OWNER", str(izin))
    monkeypatch.setenv("MEXC_API_KEY", "k")
    monkeypatch.setenv("MEXC_API_SECRET", "s")

    terlihat: dict = {}
    kena: list = []

    def transport(order: dict) -> dict:
        terlihat.update(order)
        kena.append(1)
        return {"status": "NEW"}

    venue = LiveVenueCrypto(transport=transport, gerbang=True)
    r = venue.kirim_order(keputusan_live())
    assert kena == [1]
    assert terlihat["symbol"] == "BTCUSDT"
    assert terlihat["side"] == "BUY"
    assert terlihat["quote_order_qty"] == pytest.approx(5.0)
    # SL tidak dihitung ulang: persis nilai dari keputusan
    assert r["sl"]["stop_price"] == pytest.approx(66000.0)


def test_venue_menolak_keputusan_ditolak(monkeypatch, tmp_path):
    import live_trading.execution.live_venue as lv

    izin = tmp_path / "crypto-live-approved"
    izin.write_text("tes\n", encoding="utf-8")
    monkeypatch.setattr(lv, "FILE_IZIN_OWNER", str(izin))
    monkeypatch.setenv("MEXC_API_KEY", "k")
    monkeypatch.setenv("MEXC_API_SECRET", "s")
    venue = LiveVenueCrypto(transport=lambda o: {"status": "NEW"}, gerbang=True)
    with pytest.raises(LiveTerblokir, match="DITOLAK"):
        venue.kirim_order(keputusan_live(masuk=False))


def test_venue_tanpa_gabungan_menolak():
    venue = LiveVenueCrypto(transport=lambda o: {"status": "NEW"}, gerbang=False)
    with pytest.raises(LiveTerblokir, match="bangun"):
        venue.kirim_order(keputusan_live())


# -- tanda tangan HMAC ---------------------------------------------------------

def test_tanda_hmac_vektor(monkeypatch):
    monkeypatch.setenv("MEXC_API_KEY", "k")
    monkeypatch.setenv("MEXC_API_SECRET", "RAHASIA")

    terkirim: list = []

    def fake_send(url: str, query: str, apa: str, kunci: str) -> dict:
        terkirim.append((url, query, apa, kunci))
        return {"status": "NEW"}

    t = MexcSpotTransport(send=fake_send)
    r = t({"symbol": "BTCUSDT", "side": "BUY", "type": "MARKET", "quote_order_qty": 2.0})
    assert r["tanda_ok"] is True
    url, query, _apa, _kunci = terkirim[0]
    tid = parse_qs(query)
    tanda = tid["signature"][0]
    payload = query.split("&signature=")[0].encode()
    assert tanda == hmac.new(b"RAHASIA", payload, hashlib.sha256).hexdigest()
    # timestamp tercantum, kunci tidak dikirim dalam body
    assert "timestamp" in tid
    assert all("RAHASIA" != v for v in tid.values())


def test_file_izin_owner_nama_tetap():
    """Nama file & env adalah KONTRAK dengan owner — berubah tanpa koordinasi = bug."""
    assert FILE_IZIN_OWNER.endswith("crypto-live-approved")
