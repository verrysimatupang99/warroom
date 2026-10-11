"""Rakit: data -> struktur -> usulan setup -> verdict.

Ini pengganti peran Agent 1/2/5 untuk bagian yang bisa dihitung. Yang dihasilkan bukan
"signal", tapi **usulan setup yang sudah dinilai** — lengkap dengan aturan mana yang
lolos dan mana yang gagal. Narasi dan pemilihan POI terbaik tetap pekerjaan manusia/LLM.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..collectors import make_client
from ..config import Settings
from . import gates, golden_pullback, smc

TIMEFRAMES = {"1h": 200, "4h": 200, "1d": 120}


@dataclass
class Structure:
    pair: str
    price: float
    atr_pct: float | None
    bias: dict[str, str]
    poi_bullish: dict[str, Any] | None
    poi_bearish: dict[str, Any] | None
    swing_low: float | None
    swing_high: float | None
    high_24h: float
    low_24h: float
    candles_1h: list[smc.Candle] = field(default_factory=list, repr=False)
    # Jendela freshness: 6 jam terakhir (aturan aslinya), bukan 24 jam
    high_6h: float = 0.0
    low_6h: float = 0.0
    ema_bias: dict[str, str] = field(default_factory=dict, repr=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "pair": self.pair,
            "price": self.price,
            "atr_pct": round(self.atr_pct, 3) if self.atr_pct else None,
            "bias": self.bias,
            "poi_bullish": self.poi_bullish,
            "poi_bearish": self.poi_bearish,
            "swing_low": self.swing_low,
            "swing_high": self.swing_high,
            "high_24h": self.high_24h,
            "low_24h": self.low_24h,
            "high_6h": self.high_6h,
            "low_6h": self.low_6h,
        }


def top_pairs(
    settings: Settings,
    n: int = 40,
    client: httpx.Client | None = None,
    exclude: tuple[str, ...] = ("USDC", "FDUSD", "TUSD", "BUSD", "BTCDOM", "DEFI"),
) -> list[str]:
    """Pair USDT perp teratas menurut volume 24 jam nyata.

    Daftar pair tetap buatan tangan punya bias: isinya koin yang kebetulan kita ingat.
    Volume nyata lebih jujur — dan kalau pasarnya ranging, yang muncul memang yang ramai.
    """
    own = client is None
    c = client or make_client(timeout=25.0)
    try:
        r = c.get(f"{settings.binance_fapi}/fapi/v1/ticker/24hr")
        r.raise_for_status()
        data = r.json()
    finally:
        if own:
            c.close()

    baris = [
        (str(d.get("symbol")), float(d.get("quoteVolume") or 0))
        for d in data
        if str(d.get("symbol", "")).endswith("USDT")
        and not any(x in str(d.get("symbol")) for x in exclude)
    ]
    baris.sort(key=lambda kv: kv[1], reverse=True)
    return [sim for sim, _ in baris[:n]]


def fetch_klines(
    settings: Settings, pair: str, interval: str, limit: int, client: httpx.Client
) -> list[list[Any]]:
    r = client.get(
        f"{settings.binance_fapi}/fapi/v1/klines",
        params={"symbol": pair, "interval": interval, "limit": limit},
    )
    r.raise_for_status()
    return r.json()


def build_structure(pair: str, candles: dict[str, list[smc.Candle]]) -> Structure:
    """Susun struktur dari candle yang sudah ada — tanpa jaringan.

    Dipisah dari ``analyze`` supaya backtest memakai jalur yang sama persis dengan
    perdagangan nyata. Kalau backtest punya salinan logika sendiri, ia akan menyimpang
    dan angkanya jadi tidak ada gunanya.
    """
    h1 = candles["1h"]
    price = h1[-1]["c"]
    highs = [x["h"] for x in h1]
    lows = [x["l"] for x in h1]
    closes = [x["c"] for x in h1]

    from ..indicators import atr_pct as atr_pct_fn

    a_pct = atr_pct_fn(highs, lows, closes, 14)

    def poi_dict(p: smc.Poi | None) -> dict[str, Any] | None:
        return (
            None
            if p is None
            else {
                "kind": p.kind,
                "direction": p.direction,
                "low": round(p.low, 8),
                "high": round(p.high, 8),
                "mid": round(p.mid, 8),
                "fresh": p.fresh,
            }
        )

    return Structure(
        pair=pair,
        price=price,
        atr_pct=a_pct,
        # Bias struktural (definisi sistem asalnya), bukan proksi EMA
        bias={tf: smc.structural_bias(rows) for tf, rows in candles.items()},
        ema_bias={tf: smc.bias(rows) for tf, rows in candles.items()},
        poi_bullish=poi_dict(smc.nearest_poi(h1, "long")),
        poi_bearish=poi_dict(smc.nearest_poi(h1, "short")),
        swing_low=smc.nearest_swing_low(h1, price),
        swing_high=smc.nearest_swing_high(h1, price),
        high_24h=max(highs[-24:]),
        low_24h=min(lows[-24:]),
        high_6h=max(highs[-6:]),
        low_6h=min(lows[-6:]),
        candles_1h=h1,
    )


def analyze(settings: Settings, pair: str, client: httpx.Client | None = None) -> Structure:
    """Bangun struktur pasar untuk satu pair dari Binance futures (data publik)."""
    own = client is None
    c = client or make_client(timeout=20.0)
    try:
        candles = {
            tf: smc.from_binance_klines(fetch_klines(settings, pair, tf, limit, c))
            for tf, limit in TIMEFRAMES.items()
        }
    finally:
        if own:
            c.close()

    return build_structure(pair, candles)


def _pick_anchor(
    candles: list[smc.Candle], entry: float, direction: str, buffer: float
) -> tuple[float | None, bool]:
    """Pilih anchor SL: swing terdekat yang **masih masuk akal**.

    Aturan lapangan: SL di balik swing terdekat, tapi kalau hasilnya <1% itu biasanya
    swing mikro — pakai swing SEBELUMNYA yang lebih valid. Implementasi naif (selalu
    swing terdekat) membuat hampir semua setup gagal aturan 1% — sudah terbukti saat
    dijalankan pada BTC/SUI/DOGE/SOL. Fungsi ini mengembalikan (level, apakah_masuk_akal).
    """
    long = direction.lower() == "long"
    sw = smc.swing_points(candles)
    levels = [p for _, p in (sw["lows"] if long else sw["highs"])]
    levels = [p for p in levels if (p < entry if long else p > entry)]
    if not levels:
        return None, False
    levels.sort(key=lambda p: abs(entry - p))  # terdekat lebih dulu

    for level in levels:
        sl = level - buffer if long else level + buffer
        pct = abs(entry - sl) / entry * 100.0 if entry else 0.0
        if gates.SL_MIN_PCT <= pct <= gates.SL_MAX_PCT:
            return level, True
    return levels[0], False  # tidak ada yang masuk akal → kembalikan terdekat, biar gate yang menolak


def propose(st: Structure, direction: str) -> dict[str, Any] | None:
    """Usulkan entry/SL/TP dari struktur — aturan lapangan, bukan tebakan.

    Entry = titik tengah POI searah. SL = swing yang masih masuk akal + buffer 0,5x ATR1H.
    TP1 = 1R, TP2 = 2R (aturan tetap dari prompt).
    ``None`` kalau tidak ada POI searah atau swing anchor tidak ditemukan.
    """
    long = direction.lower() == "long"
    poi = st.poi_bullish if long else st.poi_bearish
    if not poi:
        return None

    entry = float(poi["mid"])
    buffer = (st.atr_pct or 0) / 100.0 * entry * 0.5
    anchor, sane = _pick_anchor(st.candles_1h, entry, direction, buffer)
    if anchor is None:
        return None

    sl = anchor - buffer if long else anchor + buffer

    risk = abs(entry - sl)
    if risk <= 0:
        return None
    tp1 = entry + risk if long else entry - risk
    tp2 = entry + 2 * risk if long else entry - 2 * risk

    return {
        "pair": st.pair,
        "direction": direction.upper(),
        "entry": round(entry, 8),
        "sl": round(sl, 8),
        "tp1": round(tp1, 8),
        "tp2": round(tp2, 8),
        "poi": poi,
        "risk_pct": round(risk / entry * 100.0, 3),
        "sl_anchor_ok": sane,
        "rr": 2.0,
    }


def _propose_golden_smc_gated(st: Structure, direction: str) -> dict[str, Any] | None:
    """Deterministic SMC + Fibonacci Smart Golden Pullback proposal."""
    if direction.lower() not in {"long", "short"} or not st.candles_1h:
        return None
    sweeps = smc.liquidity_sweeps(st.candles_1h)
    kind = "sweep_low" if direction.lower() == "long" else "sweep_high"
    candidates = [row for row in sweeps if row["kind"] == kind]
    if not candidates:
        return None
    latest = candidates[-1]
    candle = st.candles_1h[-80:][latest["idx"]]
    confirmation = (
        candle["c"] > candle["o"] and candle["c"] > latest["level"]
        if direction.lower() == "long"
        else candle["c"] < candle["o"] and candle["c"] < latest["level"]
    )
    anchor_low = st.swing_low if direction.lower() == "long" else latest["level"]
    anchor_high = latest["level"] if direction.lower() == "long" else st.swing_high
    if anchor_low is None or anchor_high is None:
        return None
    d = "long" if direction.lower() == "long" else "short"
    setup = golden_pullback.build_pullback_setup(
        direction=d,
        swing_low=min(float(anchor_low), float(anchor_high)),
        swing_high=max(float(anchor_low), float(anchor_high)),
        current_price=st.price,
        structure_bias=st.bias.get("1h", "netral"),
        liquidity_swept=True,
        confirmation=confirmation,
    )
    if setup is None:
        return None
    return {
        "pair": st.pair,
        "direction": direction.upper(),
        "entry": round(float(setup["entry"]), 8),
        "sl": round(float(setup["stop"]), 8),
        "tp1": round(float(setup["target"]), 8),
        "tp2": round(float(setup["target"]), 8),
        "poi": {
            "kind": "golden_pullback",
            "low": setup["zone_low"],
            "high": setup["zone_high"],
            "mid": setup["entry"],
        },
        "risk_pct": round(abs(float(setup["entry"]) - float(setup["stop"])) / float(setup["entry"]) * 100, 3),
        "sl_anchor_ok": True,
        "rr": float(setup["risk_reward"]),
        "strategy": golden_pullback.GoldenPullbackStrategy.name,
        "mode": "PAPER",
    }


def _record_verdict(
    settings: Settings,
    pair: str,
    direction: str,
    prop: dict[str, Any] | None,
    assessment: gates.Assessment,
    *,
    harga_keputusan: float | None = None,
    atr_pct: float | None = None,
    agents: dict[str, Any] | None = None,
) -> None:
    """Simpan verdict ke `state/verdicts.jsonl`.

    Ini langkah yang paling sering dilewatkan: tanpa catatan, pertanyaan "aturan mana yang
    berguna" tidak bisa dijawab selamanya. Ditulis best-effort — gagal mencatat tidak boleh
    menggagalkan analisis.
    """
    import datetime as dt
    import json

    try:
        path = settings.state_dir / "verdicts.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "pair": pair,
            "direction": direction.upper(),
            "strategy": golden_pullback.GoldenPullbackStrategy.name
            if prop and prop.get("strategy")
            else "legacy-smc",
            "mode": (prop or {}).get("mode", "PAPER"),
            "allowed": assessment.allowed,
            "tier": assessment.tier,
            "entry": (prop or {}).get("entry"),
            "sl": (prop or {}).get("sl"),
            "tp1": (prop or {}).get("tp1"),
            "risk_pct": (prop or {}).get("risk_pct"),
            # Harga & ATR saat keputusan: dipakai untuk skenario "masuk di harga pasar"
            # dan untuk menguji mekanisme aturan (kenapa sebuah aturan berperilaku begitu).
            "harga_keputusan": harga_keputusan,
            "atr_pct": atr_pct,
            # zona POI disimpan supaya duplikat bisa dikenali di pemindaian berikutnya
            "poi_low": ((prop or {}).get("poi") or {}).get("low"),
            "poi_high": ((prop or {}).get("poi") or {}).get("high"),
            # instrumentasi 6-agent: dicatat, TIDAK dipakai gate. Atribusi R
            # per agent dihitung di measure dari field ini.
            "agents": agents,
            "rules": [
                {"rule": v.rule, "ok": v.ok, "hard": v.hard, "reason": v.reason} for v in assessment.verdicts
            ],
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass


def summarize_verdicts(settings: Settings) -> dict[str, Any]:
    """Ringkas verdicts.jsonl: berapa kandidat, berapa lolos, aturan mana yang paling sering menolak."""
    import json

    path = settings.state_dir / "verdicts.jsonl"
    if not path.is_file():
        return {"total": 0, "allowed": 0, "per_rule": {}}

    total = allowed = 0
    per_rule: dict[str, dict[str, int]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        allowed += 1 if row.get("allowed") else 0
        for r in row.get("rules") or []:
            if not isinstance(r, dict) or not r.get("rule"):
                continue
            slot = per_rule.setdefault(r["rule"], {"lolos": 0, "gagal": 0})
            slot["lolos" if r.get("ok") else "gagal"] += 1
    return {"total": total, "allowed": allowed, "per_rule": per_rule}


def supported_direction(st: Structure) -> str | None:
    """Arah yang didukung struktur: 4H dan 1H harus kompak.

    Ini memperbaiki kesalahan cara ukur saya: memindai **dua arah** untuk setiap pair
    memastikan satu arah selalu melawan struktur, sehingga `mtf_alignment` gagal ~80%
    bukan karena pasarnya buruk, tapi karena saya menilai setup yang memang tidak ada.
    Di sistem asalnya, arah datang dari order flow (Agent 1), bukan dari menembak dua arah.
    """
    b4, b1 = st.bias.get("4h"), st.bias.get("1h")
    if b4 == b1 == "bullish":
        return "long"
    if b4 == b1 == "bearish":
        return "short"
    return None


def zone_overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Seberapa besar dua zona bertumpuk, relatif terhadap zona tersempit (0..1)."""
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    if hi <= lo:
        return 0.0
    lebar = min(a[1] - a[0], b[1] - b[0])
    return 1.0 if lebar <= 0 else (hi - lo) / lebar


def duplicate_of_recent(
    settings: Settings,
    pair: str,
    direction: str,
    entry: float,
    zone: tuple[float, float] | None,
    *,
    window_h: float = 12.0,
    ambang: float = 0.7,
    now: dt.datetime | None = None,
) -> dict[str, Any] | None:
    """Kandidat berulang = sampel palsu.

    Pemindaian tiap 30 menit akan menemukan pair + arah + zona entry yang sama berkali-kali.
    Kalau semuanya dicatat, "200 kandidat" bisa jadi 20 setup yang dihitung 10 kali —
    dan setiap kesimpulan tentang gate-nya jadi tidak sah. Ini yang mencegahnya.
    """
    now = now or dt.datetime.now(dt.UTC)
    path = settings.state_dir / "verdicts.jsonl"
    if not path.is_file():
        return None

    z = zone or (entry * 0.999, entry * 1.001)
    for line in reversed(path.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("pair") != pair or str(row.get("direction", "")).upper() != direction.upper():
            continue
        try:
            ts = dt.datetime.fromisoformat(str(row["ts"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if (now - ts).total_seconds() / 3600 > window_h:
            break  # berkas ditulis urut waktu: yang lebih lama tidak perlu diperiksa
        if row.get("poi_low") and row.get("poi_high"):
            lama = (float(row["poi_low"]), float(row["poi_high"]))
        elif row.get("entry"):
            e = float(row["entry"])
            lama = (e * 0.999, e * 1.001)
        else:
            continue
        if zone_overlap(z, lama) >= ambang:
            return row
    return None


def purge_duplicates(
    settings: Settings, *, window_h: float = 12.0, ambang: float = 0.7, apply: bool = False
) -> dict[str, Any]:
    """Buang catatan kandidat yang sebenarnya duplikat dari baris sebelumnya.

    Dedupe baru dipasang setelah beberapa baris ganda sempat tercatat. Baris ganda itu
    menggelembungkan sampel (kandidat sama dihitung berkali-kali), jadi harus dibersihkan —
    dan jumlah yang dibuang dilaporkan, bukan dihapus diam-diam.
    """
    path = settings.state_dir / "verdicts.jsonl"
    if not path.is_file():
        return {"total": 0, "dibuang": 0, "disimpan": 0}

    baris: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            baris.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    disimpan: list[dict[str, Any]] = []
    dibuang: list[dict[str, Any]] = []
    for row in baris:
        try:
            ts = dt.datetime.fromisoformat(str(row["ts"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            disimpan.append(row)
            continue
        if row.get("poi_low") and row.get("poi_high"):
            zona = (float(row["poi_low"]), float(row["poi_high"]))
        elif row.get("entry"):
            e = float(row["entry"])
            zona = (e * 0.999, e * 1.001)
        else:
            disimpan.append(row)
            continue

        kembar = False
        for lama in disimpan:
            if lama.get("pair") != row.get("pair"):
                continue
            if str(lama.get("direction", "")).upper() != str(row.get("direction", "")).upper():
                continue
            try:
                ts_lama = dt.datetime.fromisoformat(str(lama["ts"]).replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            if abs((ts - ts_lama).total_seconds()) / 3600 > window_h:
                continue
            if lama.get("poi_low") and lama.get("poi_high"):
                zona_lama = (float(lama["poi_low"]), float(lama["poi_high"]))
            elif lama.get("entry"):
                e = float(lama["entry"])
                zona_lama = (e * 0.999, e * 1.001)
            else:
                continue
            if zone_overlap(zona, zona_lama) >= ambang:
                kembar = True
                break
        (dibuang if kembar else disimpan).append(row)

    if apply and dibuang:
        path.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in disimpan),
            encoding="utf-8",
        )
    return {"total": len(baris), "dibuang": len(dibuang), "disimpan": len(disimpan), "diterapkan": apply}


def scan(
    settings: Settings,
    pairs: list[str],
    *,
    client: httpx.Client | None = None,
    record: bool = True,
) -> list[dict[str, Any]]:
    """Pindai daftar pair: nilai HANYA arah yang didukung struktur."""
    own = client is None
    c = client or make_client(timeout=20.0)
    out: list[dict[str, Any]] = []
    try:
        for pair in pairs:
            try:
                st = analyze(settings, pair, c)
            except Exception as exc:  # noqa: BLE001
                out.append({"pair": pair, "direction": None, "tier": "ERROR", "note": str(exc)[:80]})
                continue
            direction = supported_direction(st)
            if direction is None:
                out.append(
                    {
                        "pair": pair,
                        "direction": None,
                        "tier": "TANPA ARAH",
                        "note": f"4H={st.bias.get('4h')} 1H={st.bias.get('1h')} tidak kompak",
                    }
                )
                continue

            # Usulan setup diperiksa SEBELUM evaluate. `propose` mengembalikan None kalau
            # struktur tidak memberi POI, dan `evaluate` melempar ValueError untuk itu.
            # Dulu tidak ada penjaga di sini: satu pair seperti itu membatalkan seluruh
            # `lt scan`, sehingga timer 30 menit gagal terus ~4 jam dan NOL kandidat tercatat.
            # Diperiksa langsung (bukan dengan menangkap ValueError) supaya kesalahan lain
            # tetap terlihat, bukan ikut tertelan.
            if propose(st, direction) is None:
                out.append(
                    {
                        "pair": pair,
                        "direction": direction,
                        "tier": "TANPA SETUP",
                        "allowed": False,
                        "note": (
                            f"tidak ada POI/usulan setup (4H={st.bias.get('4h')} "
                            f"1H={st.bias.get('1h')})"
                        ),
                    }
                )
                continue

            _st, prop, hasil = evaluate(settings, pair, direction, client=c, record=record)
            if hasil.duplicate_of:
                out.append(
                    {
                        "pair": pair,
                        "direction": direction,
                        "tier": "DUPLIKAT",
                        "allowed": False,
                        "note": f"sama dengan kandidat {hasil.duplicate_of} — tidak dicatat ulang",
                    }
                )
                continue
            out.append(
                {
                    "pair": pair,
                    "direction": direction,
                    "tier": hasil.tier,
                    "allowed": hasil.allowed,
                    "note": hasil.summary(),
                    "prop": prop,
                    "assessment": hasil,
                }
            )
    finally:
        if own:
            c.close()
    return out


def assess_setup(
    st: Structure,
    *,
    direction: str,
    entry: float,
    sl: float,
    tp1: float,
    poi: dict[str, Any] | None,
    open_positions: list[dict[str, Any]] | None = None,
    btc_change_24h: float | None = None,
) -> gates.Assessment:
    """Jalur gate tunggal — dipakai perdagangan nyata DAN backtest.

    Sengaja satu fungsi: kalau backtest menyalin aturan ini sendiri, salinannya akan
    menyimpang perlahan dan angkanya jadi tidak ada gunanya.
    """
    return gates.assess(
        direction=direction,
        entry=entry,
        sl=sl,
        tp1=tp1,
        price=st.price,
        atr_pct_value=st.atr_pct,
        bias_4h=st.bias.get("4h", "netral"),
        bias_1h=st.bias.get("1h", "netral"),
        bias_1d=st.bias.get("1d", "netral"),
        recent_high=st.high_6h,
        recent_low=st.low_6h,
        poi=poi,
        open_positions=open_positions,
        btc_change_24h=btc_change_24h,
    )


def evaluate(
    settings: Settings,
    pair: str,
    direction: str,
    *,
    entry: float | None = None,
    sl: float | None = None,
    tp1: float | None = None,
    open_positions: list[dict[str, Any]] | None = None,
    btc_change_24h: float | None = None,
    client: httpx.Client | None = None,
    record: bool = True,
    agents: dict[str, Any] | None = None,
) -> tuple[Structure, dict[str, Any] | None, gates.Assessment]:
    """Analisis + usulan + verdict. Entry/SL/TP bisa ditimpa kalau mau menguji setup sendiri."""
    st = analyze(settings, pair, client)
    prop = _propose_golden_smc_gated(st, direction) or propose(st, direction)
    base = prop or {}
    e = entry if entry is not None else base.get("entry")
    s = sl if sl is not None else base.get("sl")
    t1 = tp1 if tp1 is not None else base.get("tp1")
    if e is None or s is None or t1 is None:
        raise ValueError("tidak ada usulan setup dan entry/SL/TP tidak diberikan lengkap")

    poi = base.get("poi")
    assessment = assess_setup(
        st,
        direction=direction,
        entry=float(e),
        sl=float(s),
        tp1=float(t1),
        poi=poi,
        open_positions=open_positions,
        btc_change_24h=btc_change_24h,
    )
    if record:
        # Dedupe ada DI SINI, bukan di pemanggil: kalau hanya `scan` yang memeriksa,
        # pemanggilan `lt smc` langsung akan mencatat ulang kandidat yang sama dan
        # merusak sampel tanpa terlihat.
        poi_zona = None
        if poi and poi.get("low") is not None and poi.get("high") is not None:
            poi_zona = (float(poi["low"]), float(poi["high"]))
        dup = duplicate_of_recent(settings, pair, direction, float(e), poi_zona)
        if dup is not None:
            assessment = gates.Assessment(
                allowed=assessment.allowed,
                tier=assessment.tier,
                verdicts=assessment.verdicts,
                duplicate_of=str(dup.get("ts")),
            )
        else:
            _record_verdict(
                settings,
                pair,
                direction,
                prop,
                assessment,
                harga_keputusan=st.price,
                atr_pct=st.atr_pct,
                agents=agents,
            )
    return st, prop, assessment
