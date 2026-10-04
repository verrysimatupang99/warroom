"""Skema 6-agent sebagai HIPOTESIS paper — bukan gate.

Diadaptasi dari pipeline crypto Tencent (order flow, whale/positioning,
sentiment, risk, makro on-chain). Perbedaan yang disengaja:

- TIDAK ADA LLM di jalur ini (Agent 2/komposer di Tencent). Semua yang bisa
  dihitung, dihitung; narasi tetap pekerjaan manusia.
- TIDAK ADA confluence gate. Pelajaran dari studi 6-agent (omp, 28 Sep):
  confluence tidak menambah nilai. Tiap agent dicatat terpisah per verdict
  supaya data yang menilai tiap agent — via atribusi R di ``measure`` —
  bukan keyakinan kita.
- Semua ambang di bawah ini bertanda HIPOTESIS: angka awal yang masuk akal,
  belum validasi. Kalau atribusi menunjukkan agent tidak membantu, ambangnya
  diubah atau agentnya dibuang — bukan dipertahankan.

Keluaran ``collect`` dicatat ke baris verdict (field ``agents``) dan diteruskan
``measure`` apa adanya untuk atribusi per-agent.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..collectors import make_client
from ..config import Settings

# Ambang HIPOTESIS — lihat docstring modul sebelum mengubah.
TAKER_PANAS = 1.1
TAKER_DINGIN = 0.9
LS_RAMAI_LONG = 65.0
LS_RAMAI_SHORT = 35.0
FUNDING_EKSTREM_PCT = 0.05
OI_LONJAKAN_PCT = 10.0
FG_RAKUS = 75
FG_TAKUT = 25
BTC_REZIM_PCT = 3.0


def _hasil(client: httpx.Client, url: str, params: dict[str, Any] | None = None) -> Any | None:
    try:
        r = client.get(url, params=params or {})
        r.raise_for_status()
        return r.json()
    except Exception:  # noqa: BLE001 — satu agent gagal tidak boleh mematikan yang lain
        return None


def _senarai(d: Any | None) -> list[Any]:
    return d if isinstance(d, list) else []


def _peta(d: Any | None) -> dict[str, Any]:
    return d if isinstance(d, dict) else {}


def _angka(v: Any | None) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _bias_terbatas(nilai: float) -> float:
    return round(max(-1.0, min(1.0, nilai)), 2)


def agent_orderflow(settings: Settings, pair: str, client: httpx.Client) -> dict[str, Any]:
    """Agen 1 — agresi taker + posisi crowd + funding."""
    out: dict[str, Any] = {"agent": "orderflow", "bias": None, "note": "n/a", "data": {}}
    base = settings.binance_fapi
    taker = _hasil(client, f"{base}/futures/data/takerlongshortRatio",
                   {"symbol": pair, "period": "1h", "limit": 2})
    ls = _hasil(client, f"{base}/futures/data/topLongShortAccountRatio",
                {"symbol": pair, "period": "1h", "limit": 1})
    fund = _hasil(client, f"{base}/fapi/v1/fundingRate", {"symbol": pair, "limit": 1})
    try:
        baris = _senarai(taker)
        rasio = float(baris[-1].get("buySellRatio")) if baris else None
    except (TypeError, ValueError, IndexError, AttributeError):
        rasio = None
    try:
        baris_ls = _senarai(ls)
        lsr = float(baris_ls[-1].get("longShortRatio")) if baris_ls else None
        long_pct = 100 * lsr / (1 + lsr) if lsr and lsr > 0 else None
    except (TypeError, ValueError, IndexError, AttributeError):
        long_pct = None
    try:
        baris_f = _senarai(fund)
        funding = float(baris_f[-1].get("fundingRate", 0)) * 100 if baris_f else None
    except (TypeError, ValueError, IndexError, AttributeError):
        funding = None
    out["data"] = {"taker_ratio": rasio, "top_long_pct": long_pct, "funding_pct": funding}
    suara: list[float] = []
    if rasio is not None:
        if rasio >= TAKER_PANAS:
            suara.append(0.5)
        elif rasio <= TAKER_DINGIN:
            suara.append(-0.5)
    if long_pct is not None:  # crowd berdesakan = kontrarian
        if long_pct >= LS_RAMAI_LONG:
            suara.append(-0.5)
        elif long_pct <= LS_RAMAI_SHORT:
            suara.append(0.5)
    if funding is not None:  # funding mahal = long membayar = hati-hati long
        if funding >= FUNDING_EKSTREM_PCT:
            suara.append(-0.5)
        elif funding <= -FUNDING_EKSTREM_PCT:
            suara.append(0.5)
    if suara:
        out["bias"] = _bias_terbatas(sum(suara) / len(suara))
        out["note"] = f"taker {rasio} · long {long_pct}% · fund {funding}%"
    return out


def agent_whale(settings: Settings, pair: str, client: httpx.Client) -> dict[str, Any]:
    """Agen 4 — delta open interest 24 jam + funding ekstrem (positioning).

    Sengaja TIDAK memakai print aggTrades mentah: paginasi 1000-trade pertama
    per window bias ke awal jam (pelajaran Tencent, fetch_whale_trades
    deprecated). OI history coverage-nya penuh dan jujur.
    """
    out: dict[str, Any] = {"agent": "whale", "bias": None, "note": "n/a", "data": {}}
    base = settings.binance_fapi
    hist = _hasil(client, f"{base}/futures/data/openInterestHist",
                  {"symbol": pair, "period": "1h", "limit": 25})
    delta = None
    baris = _senarai(hist)
    try:
        if len(baris) >= 20:
            awal = float(baris[0]["sumOpenInterest"])
            akhir = float(baris[-1]["sumOpenInterest"])
            delta = (akhir - awal) / awal * 100 if awal > 0 else None
    except (TypeError, ValueError, KeyError, IndexError):
        delta = None
    out["data"] = {"oi_delta_24h_pct": delta}
    if delta is not None:
        if delta >= OI_LONJAKAN_PCT:
            out["bias"] = 0.5
            out["note"] = f"OI +{delta:.1f}% — uang baru masuk"
        elif delta <= -OI_LONJAKAN_PCT:
            out["bias"] = -0.5
            out["note"] = f"OI {delta:.1f}% — deleveraging"
    return out


def agent_sentiment(settings: Settings, client: httpx.Client) -> dict[str, Any]:
    """Agen 3 — Fear & Greed (pasar-wide, bukan per pair)."""
    out: dict[str, Any] = {"agent": "sentiment", "bias": None, "note": "n/a", "data": {}}
    d = _hasil(client, f"{settings.feargreed}/fng/", {"limit": 2})
    try:
        cur = (d or {}).get("data", [])[0]
        nilai = int(cur["value"])
        label = cur.get("value_classification", "")
    except (TypeError, ValueError, IndexError, KeyError, AttributeError):
        return out
    out["data"] = {"fear_greed": nilai, "label": label}
    if nilai >= FG_RAKUS:
        out["bias"] = -0.5
        out["note"] = f"rakus {nilai} ({label}) — hati-hati long"
    elif nilai <= FG_TAKUT:
        out["bias"] = 0.5
        out["note"] = f"takut {nilai} ({label}) — kontraproduktif chase short"
    return out


def agent_risk(settings: Settings, pair: str, client: httpx.Client) -> dict[str, Any]:
    """Agen 5 — konteks risiko: ATR% + rezim BTC. Tidak mem-vote arah.

    Agen ini menjawab "seberapa besar boleh ambil", bukan "long/short".
    Bias selalu None — kehadirannya sebagai data, bukan suara.
    """
    out: dict[str, Any] = {"agent": "risk", "bias": None, "note": "n/a", "data": {}}
    base = settings.binance_fapi
    kl = _hasil(client, f"{base}/fapi/v1/klines", {"symbol": pair, "interval": "1h", "limit": 20})
    btc = _hasil(client, f"{base}/fapi/v1/ticker/24hr", {"symbol": "BTCUSDT"})
    atr = None
    baris = _senarai(kl)
    try:
        from ..indicators import atr_pct as atr_fn

        if len(baris) >= 15:
            highs = [float(k[2]) for k in baris]
            lows = [float(k[3]) for k in baris]
            closes = [float(k[4]) for k in baris]
            atr = atr_fn(highs, lows, closes, 14)
    except Exception:  # noqa: BLE001
        atr = None
    btc_chg = _angka(_peta(btc).get("priceChangePercent"))
    out["data"] = {"atr_pct_1h": atr, "btc_chg_24h_pct": btc_chg}
    out["note"] = f"ATR {atr}% · BTC {btc_chg}%/24j"
    return out


def agent_macro(settings: Settings, client: httpx.Client) -> dict[str, Any]:
    """Agen 6 — rezim makro: momentum BTC sebagai proksi risk-on/off."""
    out: dict[str, Any] = {"agent": "macro", "bias": None, "note": "n/a", "data": {}}
    btc = _hasil(client, f"{settings.binance_fapi}/fapi/v1/ticker/24hr", {"symbol": "BTCUSDT"})
    chg = _angka(_peta(btc).get("priceChangePercent"))
    if chg is None:
        return out
    out["data"] = {"btc_chg_24h_pct": chg}
    if chg >= BTC_REZIM_PCT:
        out["bias"] = 0.5
        out["note"] = f"rezim risk-on (BTC {chg:+.1f}%)"
    elif chg <= -BTC_REZIM_PCT:
        out["bias"] = -0.5
        out["note"] = f"rezim risk-off (BTC {chg:+.1f}%)"
    return out


def collect(
    settings: Settings, pair: str, client: httpx.Client | None = None
) -> dict[str, Any]:
    """Jalankan semua agent data untuk satu pair. Gagal sebagian = bias None."""
    own = client is None
    c = client or make_client(timeout=15.0)
    try:
        hasil = {
            "orderflow": agent_orderflow(settings, pair, c),
            "whale": agent_whale(settings, pair, c),
            "sentiment": agent_sentiment(settings, c),
            "risk": agent_risk(settings, pair, c),
            "macro": agent_macro(settings, c),
        }
    finally:
        if own:
            c.close()
    suara = [a["bias"] for a in hasil.values() if a.get("bias") is not None]
    return {
        "pair": pair,
        "agents": hasil,
        # Dicatat, TIDAK dipakai sebagai gate (pelajaran studi 6-agent).
        "confluence": round(sum(suara) / len(suara), 2) if suara else None,
        "n_voting": len(suara),
    }
