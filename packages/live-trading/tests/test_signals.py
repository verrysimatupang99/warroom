"""Kontrak mesin sinyal SMC — aturan lapangan harus berperilaku sama setiap kali dijalankan."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from live_trading.config import get_settings
from live_trading.signals import engine, gates, smc


def _c(o: float, hi: float, lo: float, c: float, t: int = 0) -> dict[str, float]:
    return {"t": float(t), "o": o, "h": hi, "l": lo, "c": c, "v": 1.0}


# ------------------------------------------------------------------- struktur
def test_swing_terdeteksi_pada_puncak_dan_dasar() -> None:
    # k=2 -> indeks yang bisa jadi swing adalah 2..len-3; sisipkan di dalam rentang itu
    candles = [_c(10, 11, 9, 10, i) for i in range(8)]
    candles[3] = _c(10, 15, 9.5, 12, 3)  # puncak
    candles[5] = _c(12, 12.5, 5, 11, 5)  # dasar

    sw = smc.swing_points(candles, k=2)

    assert 15 in [p for _, p in sw["highs"]]
    assert 5 in [p for _, p in sw["lows"]]


def test_swing_butuh_konteks_kiri_kanan() -> None:
    """Candle terakhir tidak boleh jadi swing — belum ada konfirmasi kanan."""
    candles = [_c(10, 10.5, 9.5, 10, i) for i in range(5)]
    candles[-1] = _c(10, 99, 9, 11, 4)

    sw = smc.swing_points(candles, k=2)

    assert 99 not in [p for _, p in sw["highs"]]


def test_bias_dari_ema() -> None:
    naik = [_c(100 + i, 101 + i, 99 + i, 100 + i, i) for i in range(60)]
    turun = [_c(160 - i, 161 - i, 159 - i, 160 - i, i) for i in range(60)]

    assert smc.bias(naik) == "bullish"
    assert smc.bias(turun) == "bearish"
    assert smc.bias(naik[:10]) == "netral"


def test_order_block_bullish_dan_fresh() -> None:
    """Candle down-close terakhir sebelum impuls naik = bullish OB."""
    flat = [_c(100, 100.5, 99.5, 100, i) for i in range(20)]
    ob = _c(100, 100.5, 97, 98, 20)  # down-close
    impulse = _c(98, 112, 97.9, 111, 21)  # impuls naik kuat
    after = [_c(111 - i * 0.1, 111.5 - i * 0.1, 110 - i * 0.1, 111 - i * 0.1, 22 + i) for i in range(10)]

    obs = smc.order_blocks(flat + [ob, impulse] + after)

    bullish = [x for x in obs if x["kind"] == "bullish"]
    assert bullish, "bullish OB tidak terdeteksi"
    assert bullish[-1]["low"] == pytest.approx(97)
    assert bullish[-1]["fresh"] is True


def test_fvg_bullish_terdeteksi_dan_terisi() -> None:
    a = _c(100, 101, 99, 100.5, 0)
    b = _c(100.5, 106, 100.5, 105, 1)  # lompat
    c = _c(105, 107, 103, 106, 2)  # low 103 > high(a) 101 -> gap 101-103
    kosong = smc.fair_value_gaps([a, b, c])

    assert any(g["kind"] == "bullish" and g["low"] == pytest.approx(101) for g in kosong)
    assert all(not g["filled"] for g in kosong)

    isi = smc.fair_value_gaps([a, b, c, _c(106, 106, 101, 102, 3)])
    assert any(g["filled"] for g in isi)


def test_sweep_low_butuh_close_kembali() -> None:
    """Wick menembus swing tapi close di atas level = sweep. Close di bawah = break, bukan sweep."""
    # low harus benar-benar menurun lalu naik, kalau sama semua tidak ada swing
    lows = [100, 99, 95, 97, 98, 99]
    base = [_c(100, 101, lo, 100, i) for i, lo in enumerate(lows)]
    sweep = base + [_c(100, 100.2, 93, 99, 6)]  # wick 93, close 99 (kembali di atas 95)
    brk = base + [_c(100, 100.2, 93, 94, 6)]  # close 94 < 95 -> break asli

    assert any(s["kind"] == "sweep_low" for s in smc.liquidity_sweeps(sweep, k=2))
    assert not any(s["kind"] == "sweep_low" for s in smc.liquidity_sweeps(brk, k=2))


# ---------------------------------------------------------------------- gate
def test_sl_di_luar_batas_ditolak() -> None:
    assert gates.sl_distance("long", 100.0, 94.0).ok is False  # 6%
    assert gates.sl_distance("long", 100.0, 99.5).ok is False  # 0,5% (swing mikro)
    assert gates.sl_distance("long", 100.0, 97.0).ok is True  # 3%


def test_sl_relatif_atr_dipertahankan_absolut() -> None:
    """29 Sep: eksperimen cap 2xATR DI-REVERT — validasi 180d penuh mengencerkan
    (+0,114R → +0,076R). Cap absolut 5% berlaku apa pun ATR-nya."""
    assert gates.sl_distance("long", 100.0, 94.0, atr_pct=4.0).ok is False
    assert gates.sl_distance("long", 100.0, 97.0, atr_pct=4.0).ok is True


def test_sl_di_sisi_salah_ditolak() -> None:
    assert gates.sl_distance("long", 100.0, 101.0).ok is False
    assert gates.sl_distance("short", 100.0, 99.0).ok is False


def test_atr_minimum() -> None:
    assert gates.atr_min(0.4).ok is False
    assert gates.atr_min(None).ok is False
    lunak = gates.atr_min(1.2)
    assert lunak.ok is True and lunak.hard is False  # lolos, di bawah ideal
    assert "ideal" in gates.atr_min(2.0).reason


def test_mtf_menentukan_tier() -> None:
    premium = gates.mtf_alignment("long", "bullish", "bullish", "bullish")
    standar = gates.mtf_alignment("long", "bullish", "bullish", "bearish")
    gagal = gates.mtf_alignment("long", "bearish", "bullish", "bearish")

    assert premium.ok and premium.detail["tier_cap"] == "PREMIUM"
    assert standar.ok and standar.detail["tier_cap"] == "STANDAR"
    assert gagal.ok is False


def test_freshness_tidak_lagi_menolak_tp1_yang_sudah_kena() -> None:
    """Dihapus 29 Sep: backtest 300d/180d/offset-300d konsisten — penolakan TP1-tersentuh
    membuang pemenang (+0,04R, t=+4,20, n=2627). TP1 tersentuh = konfirmasi momentum."""
    kena = gates.freshness("long", tp1=105.0, poi_mid=100.0, price=102.0, recent_high=106.0, recent_low=99.0)
    segar = gates.freshness("long", tp1=110.0, poi_mid=100.0, price=102.0, recent_high=106.0, recent_low=99.0)

    assert kena.ok is True
    assert segar.ok is True


def test_freshness_menolak_harga_yang_sudah_jauh_dari_poi() -> None:
    jauh = gates.freshness("long", tp1=200.0, poi_mid=100.0, price=105.0, recent_high=106.0, recent_low=99.0)

    assert jauh.ok is False
    assert "POI baru" in jauh.reason


def test_freshness_tp1_lewat_tetap_lolos_kalau_dekat_poi() -> None:
    """Pengganti jendela-6-jam: TP1 tersentuh kapan pun tidak lagi menolak.

    Kasus lama (TP1 tersentuh 8 jam lalu) dulu lolos lewat jendela; sekarang lolos
    karena pemeriksaannya memang dihapus — hanya jarak dari POI yang dinilai.
    """
    segar = gates.freshness("long", tp1=105.0, poi_mid=100.0, price=102.0, recent_high=104.0, recent_low=99.0)

    assert segar.ok is True, "TP1 belum tersentuh dalam 6 jam terakhir -> setup masih layak"


def _path_candles(pivots: list[tuple[int, float]], n: int) -> list[dict[str, float]]:
    """Candle dari garis patah-patah antar pivot — untuk menguji swing secara pasti."""

    def price_at(i: int) -> float:
        for (i0, p0), (i1, p1) in zip(pivots, pivots[1:], strict=False):
            if i0 <= i <= i1:
                t = 0.0 if i1 == i0 else (i - i0) / (i1 - i0)
                return p0 + (p1 - p0) * t
        return pivots[-1][1]

    return [_c(price_at(i) - 0.05, price_at(i) + 0.2, price_at(i) - 0.2, price_at(i), i) for i in range(n)]


def test_bias_struktural_higher_high_higher_low() -> None:
    candles = _path_candles(
        [(0, 100), (4, 102), (9, 100), (14, 104), (19, 101), (24, 105), (29, 102), (34, 106)], 40
    )

    assert smc.structural_bias(candles) == "bullish"


def test_bias_struktural_lower_high_lower_low() -> None:
    candles = _path_candles(
        [(0, 106), (4, 104), (9, 106), (14, 102), (19, 105), (24, 101), (29, 104), (34, 100)], 40
    )

    assert smc.structural_bias(candles) == "bearish"


def test_bias_struktural_netral_kalau_swing_kurang() -> None:
    assert smc.structural_bias([_c(100, 100.5, 99.5, 100, i) for i in range(10)]) == "netral"


def test_poi_valid_harus_memuat_entry() -> None:
    assert gates.poi_valid("long", 100.0, 99.0, 101.0, "ob").ok is True
    assert gates.poi_valid("long", 103.0, 99.0, 101.0, "ob").ok is False
    assert gates.poi_valid("long", 100.0, None, None, None).ok is False


def test_exposure_batas_posisi_dan_korelasi() -> None:
    penuh = gates.exposure(
        "long", [{"direction": "long"}, {"direction": "short"}, {"direction": "long"}], 0.0
    )
    searah = gates.exposure("long", [{"direction": "long"}, {"direction": "long"}], 0.0)
    korelasi = gates.exposure("long", [{"direction": "long"}], -4.0)
    aman = gates.exposure("long", [{"direction": "long"}], -1.0)

    assert penuh.ok is False and "penuh" in penuh.reason
    assert searah.ok is False and "searah" in searah.reason
    assert korelasi.ok is False and "korelasi" in korelasi.reason
    assert aman.ok is True

def test_exposure_menghormati_batas_dari_settings() -> None:
    dua = [{"direction": "long"}, {"direction": "short"}]
    assert gates.exposure("long", dua, 0.0, max_total=2).ok is False
    assert gates.exposure(
        "long", [{"direction": "long"}, {"direction": "long"}], 0.0, max_same_dir=3
    ).ok is True


def test_assess_menggabungkan_semua_gate() -> None:
    hasil = gates.assess(
        direction="long",
        entry=100.0,
        sl=97.0,
        tp1=103.0,
        price=100.5,
        atr_pct_value=1.8,
        bias_4h="bullish",
        bias_1h="bullish",
        bias_1d="bullish",
        recent_high=101.0,
        recent_low=98.0,
        poi={"kind": "ob", "low": 99.5, "high": 100.5, "mid": 100.0},
        open_positions=[],
        btc_change_24h=0.5,
    )

    assert hasil.allowed is True
    assert hasil.tier == "PREMIUM"
    assert hasil.failures == []


def test_assess_menolak_kalau_ada_aturan_keras_gagal() -> None:
    hasil = gates.assess(
        direction="long",
        entry=100.0,
        sl=97.0,
        tp1=103.0,
        price=100.0,
        atr_pct_value=0.3,
        bias_4h="bullish",
        bias_1h="bullish",
        bias_1d="bullish",
        recent_high=101.0,
        recent_low=98.0,
        poi={"kind": "ob", "low": 99.5, "high": 100.5, "mid": 100.0},
    )

    assert hasil.allowed is False
    assert hasil.tier == "SKIP"
    assert [v.rule for v in hasil.failures] == ["atr_min"]


# -------------------------------------------------------------------- engine
def _series_with_lows(levels: list[float], base: float = 101.0, n: int = 24) -> list[dict[str, float]]:
    """Deret candle dengan swing low buatan pada level yang diminta (k=2)."""
    candles = [_c(base, base + 0.5, base - 0.2, base, i) for i in range(n)]
    for j, lv in enumerate(levels):
        i = 3 + j * 3
        candles[i] = _c(base, base + 0.3, lv, base - 0.1, i)
    return candles


def test_anchor_sl_memakai_swing_terdekat_kalau_masuk_akal() -> None:
    """Buffer ATR besar (1,0) membuat swing terdekat sudah memenuhi batas 1%."""
    candles = _series_with_lows([99.7, 98.5])

    level, sane = engine._pick_anchor(candles, entry=100.0, direction="long", buffer=1.0)

    assert level == pytest.approx(99.7)
    assert sane is True


def test_anchor_sl_melompati_swing_mikro() -> None:
    """Aturan 'kalau <1%, pakai swing sebelumnya yang lebih valid'.

    Tanpa fallback ini hampir semua setup gagal aturan 1% — terbukti saat dijalankan
    pada data nyata BTC/SUI/DOGE/SOL (SL 0,17-0,99%).
    """
    candles = _series_with_lows([99.7, 98.5])

    level, sane = engine._pick_anchor(candles, entry=100.0, direction="long", buffer=0.2)

    assert level == pytest.approx(98.5), "harus pindah ke swing yang lebih valid"
    assert sane is True


def test_anchor_sl_jujur_kalau_tidak_ada_yang_masuk_akal() -> None:
    """Jangan diam-diam memakai angka tidak masuk akal — tandai gagal, biar gate menolak."""
    candles = _series_with_lows([99.9])

    level, sane = engine._pick_anchor(candles, entry=100.0, direction="long", buffer=0.2)

    assert level == pytest.approx(99.9)
    assert sane is False


def test_usulan_setup_memakai_aturan_sl_struktural() -> None:
    st = engine.Structure(
        pair="BTCUSDT",
        price=100.0,
        atr_pct=2.0,
        bias={"1h": "bullish", "4h": "bullish", "1d": "bullish"},
        poi_bullish={
            "kind": "ob",
            "direction": "bullish",
            "low": 99.0,
            "high": 101.0,
            "mid": 100.0,
            "fresh": True,
        },
        poi_bearish=None,
        swing_low=95.0,
        swing_high=110.0,
        high_24h=105.0,
        low_24h=95.0,
        candles_1h=_series_with_lows([95.0]),
    )

    p = engine.propose(st, "long")

    assert p is not None
    # SL = swing low 95 - buffer 0,5x ATR (2% dari 100 = 2 -> buffer 1) = 94
    assert p["sl"] == pytest.approx(94.0)
    assert p["tp1"] == pytest.approx(106.0)  # 1R dari entry 100
    assert p["tp2"] == pytest.approx(112.0)  # 2R
    assert p["risk_pct"] == pytest.approx(6.0)
    assert p["sl_anchor_ok"] is False  # 6% > batas 5% -> gate yang menolak


def test_usulan_tanpa_poi_menghasilkan_none() -> None:
    st = engine.Structure(
        pair="X",
        price=100.0,
        atr_pct=2.0,
        bias={},
        poi_bullish=None,
        poi_bearish=None,
        swing_low=None,
        swing_high=None,
        high_24h=105.0,
        low_24h=95.0,
    )

    assert engine.propose(st, "long") is None


def test_arah_didukung_struktur_butuh_4h_dan_1h_kompak() -> None:
    """Arah kandidat harus datang dari struktur, bukan dari menembak dua arah."""
    dasar = {
        "pair": "X",
        "price": 100.0,
        "atr_pct": 2.0,
        "poi_bullish": None,
        "poi_bearish": None,
        "swing_low": None,
        "swing_high": None,
        "high_24h": 105.0,
        "low_24h": 95.0,
    }
    naik = engine.Structure(bias={"1h": "bullish", "4h": "bullish", "1d": "bullish"}, **dasar)
    turun = engine.Structure(bias={"1h": "bearish", "4h": "bearish", "1d": "netral"}, **dasar)
    campur = engine.Structure(bias={"1h": "netral", "4h": "bullish", "1d": "bullish"}, **dasar)

    assert engine.supported_direction(naik) == "long"
    assert engine.supported_direction(turun) == "short"
    assert engine.supported_direction(campur) is None


def test_zone_overlap_hitung_tumpang_tindih() -> None:
    assert engine.zone_overlap((0.0, 10.0), (0.0, 10.0)) == pytest.approx(1.0)
    assert engine.zone_overlap((0.0, 10.0), (20.0, 30.0)) == pytest.approx(0.0)
    # bertumpuk 5 dari zona tersempit (lebar 10) = 0,5
    assert engine.zone_overlap((0.0, 10.0), (5.0, 25.0)) == pytest.approx(0.5)


def test_duplikat_terdeteksi_agar_sampel_tidak_digandakan(tmp_path) -> None:
    """Pemindaian 30 menit menemukan kandidat yang sama berulang — jangan dihitung berkali-kali."""
    import datetime as dt
    import json

    s = get_settings(home=tmp_path)
    s.state_dir.mkdir(parents=True, exist_ok=True)
    baru = dt.datetime.now(dt.UTC).isoformat()
    (s.state_dir / "verdicts.jsonl").write_text(
        json.dumps(
            {
                "ts": baru,
                "pair": "SUIUSDT",
                "direction": "LONG",
                "allowed": True,
                "tier": "PREMIUM",
                "entry": 1.24,
                "sl": 1.22,
                "tp1": 1.26,
                "poi_low": 1.238,
                "poi_high": 1.242,
                "rules": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    # zona hampir sama -> duplikat
    dup = engine.duplicate_of_recent(s, "SUIUSDT", "long", 1.2401, (1.2395, 1.2421))
    assert dup is not None and dup["pair"] == "SUIUSDT"

    # pair lain -> bukan duplikat
    assert engine.duplicate_of_recent(s, "ETHUSDT", "long", 1.2401, (1.2395, 1.2421)) is None
    # arah lain -> bukan duplikat
    assert engine.duplicate_of_recent(s, "SUIUSDT", "short", 1.2401, (1.2395, 1.2421)) is None
    # zona jauh -> bukan duplikat
    assert engine.duplicate_of_recent(s, "SUIUSDT", "long", 1.30, (1.299, 1.301)) is None


def test_duplikat_di_luar_jendela_waktu_diabaikan(tmp_path) -> None:
    import datetime as dt
    import json

    s = get_settings(home=tmp_path)
    s.state_dir.mkdir(parents=True, exist_ok=True)
    lama = (dt.datetime.now(dt.UTC) - dt.timedelta(hours=20)).isoformat()
    (s.state_dir / "verdicts.jsonl").write_text(
        json.dumps(
            {
                "ts": lama,
                "pair": "SUIUSDT",
                "direction": "LONG",
                "allowed": True,
                "tier": "PREMIUM",
                "entry": 1.24,
                "sl": 1.22,
                "tp1": 1.26,
                "poi_low": 1.238,
                "poi_high": 1.242,
                "rules": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert engine.duplicate_of_recent(s, "SUIUSDT", "long", 1.2401, (1.2395, 1.2421)) is None


def test_purge_duplicates_membuang_baris_kembar(tmp_path) -> None:
    """Baris ganda menggelembungkan sampel — harus dibersihkan, dan jumlahnya dilaporkan."""
    import json

    s = get_settings(home=tmp_path)
    s.state_dir.mkdir(parents=True, exist_ok=True)
    baris = [
        {
            "ts": "2026-09-27T10:00:00+00:00",
            "pair": "SUIUSDT",
            "direction": "LONG",
            "entry": 1.24,
            "sl": 1.22,
            "tp1": 1.26,
            "poi_low": 1.238,
            "poi_high": 1.242,
        },
        {
            "ts": "2026-09-27T10:30:00+00:00",
            "pair": "SUIUSDT",
            "direction": "LONG",
            "entry": 1.2401,
            "sl": 1.22,
            "tp1": 1.26,
            "poi_low": 1.2395,
            "poi_high": 1.2421,
        },
        {
            "ts": "2026-09-27T10:35:00+00:00",
            "pair": "ETHUSDT",
            "direction": "LONG",
            "entry": 2600.0,
            "sl": 2500.0,
            "tp1": 2700.0,
            "poi_low": 2599.0,
            "poi_high": 2601.0,
        },
    ]
    (s.state_dir / "verdicts.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in baris), encoding="utf-8"
    )

    laporan = engine.purge_duplicates(s, apply=False)
    assert laporan["total"] == 3
    assert laporan["dibuang"] == 1
    assert laporan["disimpan"] == 2
    assert len((s.state_dir / "verdicts.jsonl").read_text().splitlines()) == 3, "tanpa --apply tidak diubah"

    engine.purge_duplicates(s, apply=True)
    sisa = (s.state_dir / "verdicts.jsonl").read_text().strip().splitlines()
    assert len(sisa) == 2
    pair_tersisa = [json.loads(x)["pair"] for x in sisa]
    assert pair_tersisa == ["SUIUSDT", "ETHUSDT"], "yang dibuang harus baris kembar kedua"


def test_evaluate_menolak_mencatat_kandidat_yang_sama(tmp_path) -> None:
    """Dedupe harus ada di jalur pencatatan, bukan hanya di `scan`."""
    import json

    from live_trading.signals import engine as eng

    def candle(o: float, hi: float, lo: float, c: float, i: int) -> list[Any]:
        return [i, str(o), str(hi), str(lo), str(c), "10", 0, "0", 0, "5", "0", "0"]

    def series(start: float, step: float, n: int = 200, tiap: int = 10) -> list[list[Any]]:
        out: list[list[Any]] = []
        px = start
        for i in range(n):
            px += step
            if i % tiap == tiap - 1:
                o, c = px, px - step * 3
                out.append(candle(o, o + step, c - step, c, i))
            else:
                o, c = px - step, px + step / 2
                out.append(candle(o, c + step, o - step, c, i))
        return out

    h1, h4, d1 = series(100, 0.5), series(90, 1.0), series(80, 2.0)
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(200, json={"1h": h1, "4h": h4}.get(req.url.params.get("interval"), d1))
        )
    )
    s = get_settings(home=tmp_path)

    _st, _prop, pertama = eng.evaluate(s, "TESTUSDT", "long", client=client)
    _st2, _prop2, kedua = eng.evaluate(s, "TESTUSDT", "long", client=client)

    baris = (s.state_dir / "verdicts.jsonl").read_text().strip().splitlines()
    assert len(baris) == 1, "panggilan kedua tidak boleh menambah baris"
    assert pertama.duplicate_of is None
    assert kedua.duplicate_of is not None, "panggilan kedua harus ditandai duplikat"
    assert json.loads(baris[0])["pair"] == "TESTUSDT"


def test_verdict_direkam_dan_bisa_diringkas(tmp_path) -> None:
    """Langkah yang paling sering dilewatkan: tanpa rekaman, 'aturan mana yang berguna' tak terjawab."""
    s = get_settings(home=tmp_path)
    lolos = gates.assess(
        direction="long",
        entry=100.0,
        sl=97.0,
        tp1=103.0,
        price=100.5,
        atr_pct_value=1.8,
        bias_4h="bullish",
        bias_1h="bullish",
        bias_1d="bullish",
        recent_high=101.0,
        recent_low=98.0,
        poi={"kind": "ob", "low": 99.5, "high": 100.5, "mid": 100.0},
    )
    gagal = gates.assess(
        direction="long",
        entry=100.0,
        sl=97.0,
        tp1=103.0,
        price=100.0,
        atr_pct_value=0.3,
        bias_4h="bullish",
        bias_1h="bullish",
        bias_1d="bullish",
        recent_high=101.0,
        recent_low=98.0,
        poi={"kind": "ob", "low": 99.5, "high": 100.5, "mid": 100.0},
    )

    engine._record_verdict(s, "BTCUSDT", "long", {"entry": 100, "sl": 97, "tp1": 103, "risk_pct": 3}, lolos)
    engine._record_verdict(s, "ETHUSDT", "long", None, gagal)

    d = engine.summarize_verdicts(s)

    assert d["total"] == 2
    assert d["allowed"] == 1
    assert d["per_rule"]["atr_min"]["gagal"] == 1
    assert d["per_rule"]["atr_min"]["lolos"] == 1
    assert (s.state_dir / "verdicts.jsonl").is_file()


def test_top_pairs_urut_volume_dan_buang_stablecoin() -> None:
    """Daftar tetap buatan tangan punya bias; volume nyata lebih jujur."""
    data = [
        {"symbol": "BTCUSDT", "quoteVolume": "900"},
        {"symbol": "ETHUSDT", "quoteVolume": "800"},
        {"symbol": "USDCUSDT", "quoteVolume": "700"},  # stablecoin, harus dibuang
        {"symbol": "BTCDOMUSDT", "quoteVolume": "600"},  # indeks, harus dibuang
        {"symbol": "SUIUSDT", "quoteVolume": "500"},
        {"symbol": "BTCUSDC", "quoteVolume": "999"},  # bukan USDT
    ]
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=data)))

    hasil = engine.top_pairs(get_settings(), n=3, client=client)

    assert hasil == ["BTCUSDT", "ETHUSDT", "SUIUSDT"]


def test_evaluate_end_to_end_dengan_transport_palsu(tmp_path) -> None:
    """Semua jaringan dipalsukan: yang diuji rantai keputusannya, bukan koneksi.

    Deretnya sengaja zigzag (naik dengan pullback), bukan monoton: deret monoton tidak
    punya swing, dan tanpa swing tidak ada POI — persis seperti pasar yang tidak bergerak.
    """

    def candle(o: float, hi: float, lo: float, c: float, i: int) -> list[Any]:
        return [i, str(o), str(hi), str(lo), str(c), "10", 0, "0", 0, "5", "0", "0"]

    def series(start: float, step: float, n: int = 200, tiap: int = 10) -> list[list[Any]]:
        out: list[list[Any]] = []
        px = start
        for i in range(n):
            px += step
            if i % tiap == tiap - 1:  # candle pullback (down-close)
                o, c = px, px - step * 3
                out.append(candle(o, o + step, c - step, c, i))
            else:  # candle naik
                o, c = px - step, px + step / 2
                out.append(candle(o, c + step, o - step, c, i))
        return out

    h1, h4, d1 = series(100, 0.5), series(90, 1.0), series(80, 2.0)

    def handler(request: httpx.Request) -> httpx.Response:
        interval = request.url.params.get("interval")
        if interval == "1h":
            return httpx.Response(200, json=h1)
        if interval == "4h":
            return httpx.Response(200, json=h4)
        return httpx.Response(200, json=d1)

    s = get_settings(home=tmp_path)
    client = httpx.Client(transport=httpx.MockTransport(handler))

    st, prop, hasil = engine.evaluate(s, "TESTUSDT", "long", client=client)

    assert st.price == pytest.approx(float(h1[-1][4]))
    assert st.atr_pct is not None and st.atr_pct > 0
    assert prop is not None, "deret zigzag harus menghasilkan POI dan usulan setup"
    assert len(hasil.verdicts) == 6
    assert {v.rule for v in hasil.verdicts} == {
        "mtf_alignment",
        "poi_valid",
        "freshness",
        "sl_distance",
        "atr_min",
        "exposure",
    }
    assert prop["tp1"] is not None and prop["sl"] is not None


def test_scan_tidak_mati_karena_satu_pair_tanpa_setup(monkeypatch, tmp_path) -> None:
    """Satu pair tanpa POI tidak boleh membatalkan seluruh pemindaian.

    Bug nyata: `scan` memanggil `evaluate` tanpa penjaga, dan `evaluate` melempar ValueError
    ketika `propose` mengembalikan None (struktur tanpa POI). Akibatnya bukan sebagian baris
    hilang, tapi SEMUA: timer 30 menit gagal terus selama ~4 jam (kandidat terakhir 01:04 UTC,
    pemindaian berikutnya yang berhasil 05:26 UTC) dan nol kandidat tercatat.
    """
    from live_trading.config import get_settings

    s = get_settings(home=tmp_path)

    class _St:
        bias = {"4h": "bullish", "1h": "bullish"}

        def __init__(self) -> None:
            self.poi_bullish = None
            self.poi_bearish = None

    dipanggil: list[str] = []

    def fake_analyze(settings, pair, client=None):
        st = _St()
        if pair == "ADAUSDT":
            st.poi_bullish = {"mid": 1.0}  # pair ini punya POI → boleh masuk evaluate
        return st

    def fake_propose(st, direction):
        if st.poi_bullish is None and st.poi_bearish is None:
            return None
        return {"entry": 1.0, "sl": 0.9, "tp1": 1.1}

    monkeypatch.setattr(engine, "analyze", fake_analyze)
    monkeypatch.setattr(engine, "propose", fake_propose)
    monkeypatch.setattr(engine, "supported_direction", lambda st: "long")

    def fake_evaluate(settings, pair, direction, **kwargs):
        dipanggil.append(pair)

        class _Hasil:
            duplicate_of = None
            verdicts: list[Any] = []
            allowed = True
            tier = "IZIN"

            def summary(self) -> str:
                return "lolos semua gate"

        return _St(), {"entry": 1.0, "sl": 0.9, "tp1": 1.1}, _Hasil()

    monkeypatch.setattr(engine, "evaluate", fake_evaluate)

    rows = engine.scan(s, ["TANPAPOIUSDT", "ADAUSDT"], client=object(), record=False)

    assert [r["tier"] for r in rows] == ["TANPA SETUP", "IZIN"], (
        "pair tanpa POI harus dilewati sebagai TANPA SETUP, dan pair berikutnya tetap dinilai"
    )
    assert dipanggil == ["ADAUSDT"], "evaluate tidak boleh dipanggil untuk pair tanpa usulan"


def test_smc_empty_candles() -> None:
    """Empty candle lists must return neutral/empty without IndexError."""
    assert smc.bias([]) == "netral"
    assert smc.candidate_pois([]) == []
    assert smc.nearest_poi([], "long") is None

