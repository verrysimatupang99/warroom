"""Struktur pasar & POI — deterministik, bisa diuji, tanpa LLM.

Ini pemindahan taksonomi yang sebelumnya hidup sebagai kalimat di dalam prompt 5-agen
(Dumbledore) menjadi fungsi. Yang dipindah **hanya** yang bisa dihitung: swing, order
block, FVG, sweep, bias MTF. Yang tetap butuh penilaian — POI mana yang paling relevan,
narasi, prioritas — tidak ada di sini.

Candle di modul ini berbentuk dict: ``{"t", "o", "h", "l", "c", "v"}``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..indicators import atr, ema

Candle = dict[str, float]


def from_binance_klines(rows: list[list[Any]]) -> list[Candle]:
    """Binance kline (array) -> candle dict. Format array mudah berubah; ini satu-satunya tempat konversi."""
    return [
        {
            "t": float(r[0]),
            "o": float(r[1]),
            "h": float(r[2]),
            "l": float(r[3]),
            "c": float(r[4]),
            "v": float(r[5]),
        }
        for r in rows
    ]


# --------------------------------------------------------------------- swing
def swing_points(candles: list[Candle], k: int = 2) -> dict[str, list[tuple[int, float]]]:
    """Swing high/low: titik yang lebih ekstrem dari ``k`` tetangga di kedua sisi.

    ``k=2`` = swing minor (1H), cukup untuk SL struktural intraday.
    """
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    for i in range(k, len(candles) - k):
        window = candles[i - k : i + k + 1]
        hi, lo = candles[i]["h"], candles[i]["l"]
        if hi == max(c["h"] for c in window) and hi > candles[i - 1]["h"]:
            highs.append((i, hi))
        if lo == min(c["l"] for c in window) and lo < candles[i - 1]["l"]:
            lows.append((i, lo))
    return {"highs": highs, "lows": lows}


def nearest_swing_low(candles: list[Candle], price: float, k: int = 2) -> float | None:
    """Swing low terdekat DI BAWAH harga — anchor SL standar untuk long."""
    lows = [p for _, p in swing_points(candles, k)["lows"] if p < price]
    return max(lows) if lows else None


def nearest_swing_high(candles: list[Candle], price: float, k: int = 2) -> float | None:
    """Swing high terdekat DI ATAS harga — anchor SL standar untuk short."""
    highs = [p for _, p in swing_points(candles, k)["highs"] if p > price]
    return min(highs) if highs else None


# ------------------------------------------------------------------ bias MTF
def bias(candles: list[Candle]) -> str:
    """Bias dari EMA20 vs EMA50 pada deret candle satu timeframe — proksi, bukan definisi."""
    if not candles:
        return "netral"
    closes = [c["c"] for c in candles]
    e20, e50 = ema(closes, 20), ema(closes, 50)
    if e20 is None or e50 is None:
        return "netral"
    last = closes[-1]
    if last > e20 > e50:
        return "bullish"
    if last < e20 < e50:
        return "bearish"
    return "netral"


def structural_bias(candles: list[Candle], k: int = 2) -> str:
    """Bias struktural: higher-high + higher-low = naik; lower-high + lower-low = turun.

    Ini definisi yang dipakai sistem asalnya (Agent 2 menilai bias secara struktural).
    Proksi EMA terlalu ketat: pada data nyata ia menolak 80% kandidat karena 1H "netral"
    hanya berarti EMA belum rapi, bukan bahwa strukturnya tidak searah.
    """
    sw = swing_points(candles, k)
    highs = [p for _, p in sw["highs"]][-2:]
    lows = [p for _, p in sw["lows"]][-2:]
    if len(highs) < 2 or len(lows) < 2:
        return "netral"
    hh, hl = highs[-1] > highs[-2], lows[-1] > lows[-2]
    lh, ll = highs[-1] < highs[-2], lows[-1] < lows[-2]
    if hh and hl:
        return "bullish"
    if lh and ll:
        return "bearish"
    return "netral"


# ---------------------------------------------------------------- order block
def order_blocks(candles: list[Candle], impulse_mult: float = 1.5) -> list[dict[str, Any]]:
    """Order block: candle terakhir berlawanan arah sebelum impuls.

    Bullish OB = candle down-close terakhir sebelum impuls naik; zona = [low, high] candle itu.
    ``fresh`` = harga belum kembali masuk zona setelah impuls (zona belum "dimakan").
    """
    rows = candles[-80:]  # jendela terbatas: OB lama tidak relevan untuk intraday
    a = atr([c["h"] for c in rows], [c["l"] for c in rows], [c["c"] for c in rows], 14)
    if not a or a <= 0:
        return []

    out: list[dict[str, Any]] = []
    for i in range(1, len(rows) - 1):
        cur, nxt = rows[i], rows[i + 1]
        body_next = abs(nxt["c"] - nxt["o"])
        if body_next < impulse_mult * a:
            continue

        bullish_impulse = nxt["c"] > nxt["o"] and nxt["c"] > cur["h"]
        bearish_impulse = nxt["c"] < nxt["o"] and nxt["c"] < cur["l"]

        if bullish_impulse and cur["c"] < cur["o"]:
            zone = (cur["l"], cur["h"])
            fresh = all(c["l"] > zone[1] for c in rows[i + 2 :])
            out.append({"kind": "bullish", "low": zone[0], "high": zone[1], "idx": i, "fresh": fresh})
        elif bearish_impulse and cur["c"] > cur["o"]:
            zone = (cur["l"], cur["h"])
            fresh = all(c["h"] < zone[0] for c in rows[i + 2 :])
            out.append({"kind": "bearish", "low": zone[0], "high": zone[1], "idx": i, "fresh": fresh})
    return out


# ------------------------------------------------------------------------ FVG
def fair_value_gaps(candles: list[Candle]) -> list[dict[str, Any]]:
    """FVG 3-candle: celah antara candle i-1 dan i+1 yang dilewati candle i.

    Bullish FVG: high(i-1) < low(i+1) -> zona [high(i-1), low(i+1)].
    ``filled`` = sudah ada candle yang kembali mengisi zona itu.
    """
    rows = candles[-80:]
    out: list[dict[str, Any]] = []
    for i in range(1, len(rows) - 1):
        prev, nxt = rows[i - 1], rows[i + 1]
        if prev["h"] < nxt["l"]:
            low, high = prev["h"], nxt["l"]
            filled = any(c["l"] <= low for c in rows[i + 2 :])
            out.append({"kind": "bullish", "low": low, "high": high, "idx": i, "filled": filled})
        elif prev["l"] > nxt["h"]:
            low, high = nxt["h"], prev["l"]
            filled = any(c["h"] >= high for c in rows[i + 2 :])
            out.append({"kind": "bearish", "low": low, "high": high, "idx": i, "filled": filled})
    return out


# ---------------------------------------------------------------------- sweep
def liquidity_sweeps(candles: list[Candle], k: int = 2) -> list[dict[str, Any]]:
    """Sweep: wick menembus swing tapi close kembali ke dalam range (= jebakan likuiditas).

    Bukan break. Arah: sweep low -> sinyal balik naik; sweep high -> sinyal balik turun.
    """
    rows = candles[-80:]
    sw = swing_points(rows, k)
    out: list[dict[str, Any]] = []
    for i, level in sw["lows"]:
        for j in range(i + 1, min(i + 6, len(rows))):
            if rows[j]["l"] < level and rows[j]["c"] > level:
                out.append({"kind": "sweep_low", "level": level, "idx": j})
                break
    for i, level in sw["highs"]:
        for j in range(i + 1, min(i + 6, len(rows))):
            if rows[j]["h"] > level and rows[j]["c"] < level:
                out.append({"kind": "sweep_high", "level": level, "idx": j})
                break
    return out


# ------------------------------------------------------------------------ POI
@dataclass(frozen=True)
class Poi:
    kind: str  # "ob" | "fvg" | "swing"
    direction: str  # "bullish" | "bearish"
    low: float
    high: float
    fresh: bool

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2


def candidate_pois(candles: list[Candle]) -> list[Poi]:
    """Kumpulkan POI yang sah dari ketiga sumber, urut dari yang paling dekat harga."""
    if not candles:
        return []
    price = candles[-1]["c"]
    out: list[Poi] = []
    for ob in order_blocks(candles):
        out.append(Poi("ob", ob["kind"], ob["low"], ob["high"], bool(ob["fresh"])))
    for fvg in fair_value_gaps(candles):
        # FVG yang sudah terisi tidak lagi jadi POI; iFVG (inversion) penilaiannya terpisah
        if not fvg["filled"]:
            out.append(Poi("fvg", fvg["kind"], fvg["low"], fvg["high"], True))
    sw = swing_points(candles)
    for _, level in sw["lows"][-3:]:
        if level < price:
            out.append(Poi("swing", "bullish", level * 0.999, level * 1.001, True))
    for _, level in sw["highs"][-3:]:
        if level > price:
            out.append(Poi("swing", "bearish", level * 0.999, level * 1.001, True))
    return sorted(out, key=lambda p: abs(p.mid - price))


def nearest_poi(candles: list[Candle], direction: str) -> Poi | None:
    """POI paling dekat yang searah dengan rencana entry."""
    want = "bullish" if direction.lower() == "long" else "bearish"
    for p in candidate_pois(candles):
        if p.direction == want:
            return p
    return None
