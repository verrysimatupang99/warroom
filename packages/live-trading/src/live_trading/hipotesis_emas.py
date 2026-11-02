"""Tiga hipotesis trading emas, diuji dengan aturan eksekusi yang sama.

Semua hipotesis sengaja dibuat **sederhana dan bisa dijelaskan**. Strategi rumit
dengan 8 parameter gampang menghasilkan angka bagus yang tidak bertahan di luar
sampel. Kalau ide sederhana tidak jalan, ide rumit hampir pasti cuma menambal
derau.

Hipotesis:
    A. Cross-session momentum — arah sesi Asia yang diteruskan sesi London.
    B. Opening range breakout NY 13:30 UTC — pecah range pertama 60 menit.
    C. Trend harian + filter sesi — ikut arah harian, hanya masuk saat volatil.
"""

from __future__ import annotations

from typing import Any

from live_trading.lab_emas import atr, ema, jam_utc, tanggal_utc


def _balik(s: dict[str, Any], acuan: float) -> dict[str, Any]:
    """Cerminkan sinyal: arah ditukar, jarak stop & target dipertahankan.

    Dipakai untuk menguji apakah hasil negatif berasal dari **arah sinyal yang
    salah** atau dari **biaya transaksi**. Kalau versi cermin tetap negatif,
    yang membunuh adalah biaya, bukan arah.
    """
    arah = "short" if s["arah"] == "long" else "long"
    jarak_stop = abs(acuan - s["stop"])
    jarak_target = abs(s["target"] - acuan)
    if arah == "long":
        return {"arah": "long", "stop": acuan - jarak_stop, "target": acuan + jarak_target}
    return {"arah": "short", "stop": acuan + jarak_stop, "target": acuan - jarak_target}


# --------------------------------------------------------------------------
# A. Cross-session momentum
# --------------------------------------------------------------------------


def sinyal_momentum_sesi(
    data: dict[str, list[Any]],
    *,
    sesi_awal: int = 0,
    sesi_akhir: int = 8,
    min_gerak_atr: float = 0.5,
    rr: float = 2.0,
    balik: bool = False,
) -> Any:
    """Sesi Asia (00–07 UTC) bergerak satu arah; London (08 UTC) melanjutkan.

    Dasar: emas dipengaruhi aliran Asia yang kemudian dihadapi order Eropa.
    Syarat: gerak Asia harus melebihi ``min_gerak_atr`` ATR, kalau tidak itu
    cuma derau dan arahnya tidak punya arti.
    """

    def sinyal(i: int) -> dict[str, Any] | None:
        t = data["waktu"][i]
        if jam_utc(t) != sesi_akhir - 1:
            return None  # hanya putuskan di candle penutup terakhir sesi Asia
        hari = tanggal_utc(t)
        # Kumpulkan candle sesi Asia pada hari yang sama.
        j = i
        while j >= 0 and tanggal_utc(data["waktu"][j]) == hari and jam_utc(data["waktu"][j]) >= sesi_awal:
            j -= 1
        awal, akhir = j + 1, i
        if akhir - awal < 4:
            return None
        hi = max(data["high"][awal : akhir + 1])
        lo = min(data["low"][awal : akhir + 1])
        buka = data["open"][awal]
        tutup = data["close"][akhir]
        gerak = hi - lo
        a = atr_ref[i]
        if a <= 0 or gerak < min_gerak_atr * a:
            return None

        arah = "long" if tutup > buka else "short"
        risiko = gerak  # stop di seberang range sesi: definisi struktural, bukan selera
        if risiko <= 0:
            return None
        if arah == "long":
            out = {"arah": "long", "stop": lo, "target": tutup + rr * risiko}
        else:
            out = {"arah": "short", "stop": hi, "target": tutup - rr * risiko}
        return _balik(out, tutup) if balik else out

    a = atr(data["high"], data["low"], data["close"], 14)
    atr_ref = a
    return sinyal


# --------------------------------------------------------------------------
# B. Opening range breakout 13:30 UTC
# --------------------------------------------------------------------------

OR_MULAI_JAM = 13  # 13:00 UTC; 13:30 data NY ditangkap di paruh kedua jam ini
OR_BARS = 4  # 4 x 15m = 60 menit


def sinyal_opening_range(
    data: dict[str, list[Any]],
    *,
    rr: float = 1.5,
    rasio_range_maks: float = 3.0,
    min_bars: int = 3,
    jendela_bars: int = 24,
    balik: bool = False,
) -> Any:
    """Pecah high/low range 60 menit pertama sesi NY, target ``rr`` x range.

    Alurnya dua tahap, dan itu bukan kerumitan yang dibuat-buat:

    1. Saat range 13:00–14:00 UTC selesai, level high/low disimpan.
    2. Pada ``jendela_bars`` candle berikutnya, dipakai **close** pertama yang
       menembus salah satu level. Close candle terakhir range selalu berada di
       dalam [low, high] miliknya sendiri, jadi mengecek breakout pada candle
       itu sendiri tidak akan pernah memicu sinyal.

    ``rasio_range_maks`` membatasi range pembukaan terhadap ATR harian. Jam
    13:00 UTC adalah jam paling volatil emas, jadi range 1 jam di sana wajar
    bernilai 1,4–2,2x ATR harian. Ambang 0,7x yang sempat dipakai sebelum
    melihat data membunuh hampir semua hari; itu kesalahan asumsi, bukan
    temuan pasar.
    """
    a = atr(data["high"], data["low"], data["close"], 96)  # ATR harian kasar (96 x 15m)
    waktu = data["waktu"]
    high = data["high"]
    low = data["low"]
    close = data["close"]

    return _sinyal_or(
        waktu=waktu,
        high=high,
        low=low,
        close=close,
        atr_ref=a,
        or_jam=OR_MULAI_JAM,
        or_bars=OR_BARS,
        min_bars=min_bars,
        rr=rr,
        rasio_range_maks=rasio_range_maks,
        jendela_bars=jendela_bars,
        balik=balik,
    )


def _sinyal_or(
    *,
    waktu: list[int],
    high: list[float],
    low: list[float],
    close: list[float],
    atr_ref: list[float],
    or_jam: int,
    or_bars: int,
    min_bars: int,
    rr: float,
    rasio_range_maks: float,
    jendela_bars: int,
    balik: bool,
) -> Any:
    state: dict[str, Any] = {}

    def sinyal(i: int) -> dict[str, Any] | None:
        t = waktu[i]

        # Tahap 1: akhir range pembukaan -> simpan level.
        if jam_utc(t) == or_jam and (t // 900000) % 4 == or_bars - 1:
            awal = i - (or_bars - 1)
            if awal < 1:
                return None
            if any(jam_utc(waktu[k]) != or_jam for k in range(awal, i + 1)):
                return None
            if i - awal + 1 < min_bars:
                return None
            hi = max(high[awal : i + 1])
            lo = min(low[awal : i + 1])
            rentang = hi - lo
            if rentang <= 0:
                return None
            if atr_ref[i] > 0 and rentang > rasio_range_maks * atr_ref[i]:
                state.clear()
                return None
            state["level"] = (hi, lo, rentang, i)
            return None

        # Tahap 2: cari penembusan lewat close, dalam jendela waktu terbatas.
        if "level" not in state:
            return None
        hi, lo, rentang, idx_or = state["level"]
        if i <= idx_or:
            return None
        if i - idx_or > jendela_bars or tanggal_utc(waktu[i]) != tanggal_utc(waktu[idx_or]):
            state.clear()
            return None

        if close[i] > hi:
            state.clear()
            out = {"arah": "long", "stop": lo, "target": hi + rr * rentang}
            return _balik(out, close[i]) if balik else out
        if close[i] < lo:
            state.clear()
            out = {"arah": "short", "stop": hi, "target": lo - rr * rentang}
            return _balik(out, close[i]) if balik else out
        return None

    return sinyal


# --------------------------------------------------------------------------
# C. Trend harian + filter sesi
# --------------------------------------------------------------------------


def sinyal_trend_sesi(
    data: dict[str, list[Any]],
    *,
    ema_cepat: int = 50,
    ema_lambat: int = 200,
    rr: float = 2.0,
    min_atr_pct: float = 0.0,
    balik: bool = False,
) -> Any:
    """Ikut arah EMA 50/200, masuk hanya di jam London/NY saat ATR cukup besar.

    ``min_atr_pct``: ATR(14) 15m minimum dalam persen harga. Menyaring pasar
    tidur di mana stop ikut sempit dan biaya memakan seluruh edge.
    """
    close = data["close"]
    ec = ema(close, ema_cepat)
    el = ema(close, ema_lambat)
    a = atr(data["high"], data["low"], close, 14)

    def sinyal(i: int) -> dict[str, Any] | None:
        if i < ema_lambat + 2:
            return None
        jam = jam_utc(data["waktu"][i])
        if not (8 <= jam <= 20):
            return None
        if ec[i] == 0 or el[i] == 0:
            return None
        if min_atr_pct > 0 and close[i] > 0 and a[i] / close[i] < min_atr_pct:
            return None

        risiko = 1.5 * a[i]
        if risiko <= 0:
            return None

        # Butuh pemisahan jelas antara kedua EMA, bukan cuma menyentuh.
        pisah = abs(ec[i] - el[i])
        if pisah < 0.25 * a[i]:
            return None

        if ec[i] > el[i] and close[i] > ec[i]:
            out = {"arah": "long", "stop": close[i] - risiko, "target": close[i] + rr * risiko}
            return _balik(out, close[i]) if balik else out
        if ec[i] < el[i] and close[i] < ec[i]:
            out = {"arah": "short", "stop": close[i] + risiko, "target": close[i] - rr * risiko}
            return _balik(out, close[i]) if balik else out
        return None

    return sinyal
