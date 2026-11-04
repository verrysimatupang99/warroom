"""
Risk Gate & Position Sizing - War Room / Laya Sentinel
=====================================================
Menolak sinyal dengan ekspektasi negatif SEBELUM masuk antrean eksekusi.

Aturan (fail-closed):
  1. RR minimum   : jarak TP1 / jarak SL >= 1.5  (selaras backtest Model C RRR 1:2)
  2. Freshness    : umur sinyal <= MAX_AGE_HOURS (default 12 jam)
  3. Data lengkap : SL, entry, TP1 wajib ada & koheren (SL != entry)
  4. Sizing       : lot dihitung dari saldo, bukan hardcode 0.10

Kenapa RR minimum 1.5:
  Backtest 1 tahun modal $100 -> 6/6 margin call, dengan banyak sinyal RR 1:0.3.
  RR 1:0.30 butuh win rate ~77% untuk impas. RR 1:0.93 butuh ~52%.
  RR 1:1.5 hanya butuh 40% -> realistis untuk WR backtest Model C (38.9%-52.9%).
"""

from __future__ import annotations

import datetime
import os
from typing import Any, Dict, Optional

# --- Konstanta kebijakan (bisa dioverride lewat environment) ---
MIN_RR = float(os.getenv("WARROOM_MIN_RR", "1.5"))
MAX_AGE_HOURS = float(os.getenv("WARROOM_MAX_SIGNAL_AGE_HOURS", "12"))
LOT_STEP = 0.01
MIN_LOT = 0.01
MAX_LOT = 0.10


def _num(v: Any) -> Optional[float]:
    """Konversi aman ke float; None bila bukan angka valid."""
    try:
        if v is None or isinstance(v, bool):
            return None
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None


def compute_rr(signal: Dict[str, Any]) -> Optional[float]:
    """
    Hitung risk-reward ratio terhadap TP1.
    Pakai sisi entry yang paling konservatif (terjauh dari SL) agar tidak optimistis.
    """
    action = (signal.get("action") or "").upper()
    sl = _num(signal.get("sl"))
    tp1 = _num(signal.get("tp1"))
    e_low = _num(signal.get("entry_low"))
    e_high = _num(signal.get("entry_high"))

    if sl is None or tp1 is None:
        return None

    entries = [e for e in (e_low, e_high) if e is not None]
    if not entries:
        return None

    is_buy = action.startswith("BUY")

    # Pilih entry yang menghasilkan RR terkecil (paling jujur)
    best: Optional[float] = None
    for entry in entries:
        if is_buy:
            risk = entry - sl
            reward = tp1 - entry
        else:
            risk = sl - entry
            reward = entry - tp1

        if risk <= 0 or reward <= 0:
            continue
        rr = reward / risk
        if best is None or rr < best:
            best = rr

    return best


def signal_age_hours(timestamp: Any) -> Optional[float]:
    """Umur sinyal dalam jam. Menerima string SQLite datetime atau objek datetime."""
    if not timestamp:
        return None
    try:
        if isinstance(timestamp, datetime.datetime):
            ts = timestamp
        else:
            raw = str(timestamp).replace("T", " ").replace("Z", "").strip()
            ts = datetime.datetime.fromisoformat(raw.split("+")[0].split(".")[0])
        if ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        now = datetime.datetime.utcnow()
        return max(0.0, (now - ts).total_seconds() / 3600.0)
    except (ValueError, TypeError, AttributeError):
        return None


def size_lot(balance: float, sl_points_from_entry: Optional[float], symbol: str = "XAUUSD") -> float:
    """
    Hitung lot dari saldo. Risk per trade = RISK_PCT dari saldo (default 1%),
    dibatasi oleh jarak SL aktual (bukan angka bulat 0.10).

    XAUUSD: 1.00 lot = $100 per $1 pergerakan harga -> 0.01 lot = $1 per $1.
    Jadi risk_usd_max = jarak_sl * 1.0 * lot / 0.01  -->  lot = risk_max / (jarak_sl * 100)
    """
    risk_pct = float(os.getenv("WARROOM_RISK_PCT", "1.0"))
    bal = _num(balance) or 0.0
    dist = _num(sl_points_from_entry)

    if bal <= 0 or dist is None or dist <= 0:
        return MIN_LOT

    risk_max_usd = bal * (risk_pct / 100.0)

    if symbol.upper() == "XAUUSD":
        value_per_1usd_move_per_001lot = 1.0  # $1 per $1 harga per 0.01 lot
        raw_lot = risk_max_usd / (dist * 100.0)
    else:
        # USTEC/indeks: pendekatan konservatif, gunakan 0.01 lot minimum
        raw_lot = MIN_LOT

    stepped = round(raw_lot / LOT_STEP) * LOT_STEP
    return max(MIN_LOT, min(MAX_LOT, round(stepped, 2)))


def evaluate(signal: Dict[str, Any], balance: Optional[float] = None) -> Dict[str, Any]:
    """
    Evaluasi satu sinyal. Mengembalikan dict:
      decision : 'APPROVED' | 'REJECTED'
      reasons  : list[str] alasan penolakan
      rr       : float | None
      lot      : float (sudah disesuaikan saldo)
      age_h   : float | None
    """
    reasons: list[str] = []
    action = (signal.get("action") or "").upper()
    symbol = (signal.get("symbol") or "").upper()
    sl = _num(signal.get("sl"))
    tp1 = _num(signal.get("tp1"))
    e_low = _num(signal.get("entry_low"))
    e_high = _num(signal.get("entry_high"))

    # --- 1. Kelengkapan data (fail-closed) ---
    if sl is None:
        reasons.append("SL tidak terbaca")
    if tp1 is None:
        reasons.append("TP1 tidak terbaca")
    if e_low is None and e_high is None:
        reasons.append("Entry tidak terbaca")

    entry_ref = e_low if e_low is not None else e_high
    if sl is not None and entry_ref is not None and abs(sl - entry_ref) < 1e-9:
        reasons.append("SL sama dengan entry")

    # --- 2. Arah harga koheren ---
    if sl is not None and tp1 is not None and entry_ref is not None:
        if action.startswith("BUY"):
            if not (tp1 > entry_ref > sl):
                reasons.append(f"Arah BUY tidak koheren (TP1={tp1} Entry={entry_ref} SL={sl})")
        elif action.startswith("SELL"):
            if not (tp1 < entry_ref < sl):
                reasons.append(f"Arah SELL tidak koheren (TP1={tp1} Entry={entry_ref} SL={sl})")
        else:
            reasons.append(f"Aksi tidak dikenali: {action!r}")

    # --- 3. RR minimum ---
    rr = compute_rr(signal)
    if rr is None:
        reasons.append("RR tidak dapat dihitung")
    elif rr < MIN_RR:
        reasons.append(f"RR {rr:.2f} di bawah minimum {MIN_RR:.2f}")

    # --- 4. Freshness ---
    age = signal_age_hours(signal.get("timestamp"))
    if age is None:
        reasons.append("Timestamp tidak valid")
    elif age > MAX_AGE_HOURS:
        reasons.append(f"Sinyal basi: {age:.1f} jam > {MAX_AGE_HOURS:.0f} jam")

    # --- 5. Sizing dari saldo ---
    dist = None
    if entry_ref is not None and sl is not None:
        dist = abs(entry_ref - sl)
    lot = size_lot(balance or 0.0, dist, symbol)

    return {
        "decision": "REJECTED" if reasons else "APPROVED",
        "reasons": reasons,
        "rr": round(rr, 3) if rr is not None else None,
        "lot": lot,
        "age_h": round(age, 2) if age is not None else None,
        "policy": {
            "min_rr": MIN_RR,
            "max_age_hours": MAX_AGE_HOURS,
        },
    }



# ============================================================================
# Aturan portofolio: sesi Nasdaq + korelasi Gold-Nasdaq
# ============================================================================

# Sesi likuiditas USTEC/NAS100 (waktu UTC). Cash session AS 13:30-20:00 UTC;
# diambil jendela lebih longgar 12:00-18:00 UTC = 19:00-01:00 WIB.
NASDAQ_SESSION_UTC = (12, 18)


def asian_or_late_session(now_utc=None):
    """True bila jam UTC di luar sesi Nasdaq yang wajar."""
    if now_utc is None:
        now_utc = datetime.datetime.utcnow()
    jam = now_utc.hour
    mulai, selesai = NASDAQ_SESSION_UTC
    return not (mulai <= jam < selesai)


def apply_portfolio_rules(approved):
    """Aturan lintas-sinyal pada daftar keputusan APPROVED (in-place).

    Korelasi: XAUUSD dan USTEC bergerak searah pada regime risk-on. Membuka
    BUY keduanya (atau SELL keduanya) menggandakan eksposur arah yang sama,
    bukan diversifikasi. Yang RR-nya lebih lemah ditolak.
    """
    for arah in ("BUY", "SELL"):
        grup = [x for x in approved
                if (x["signal"].get("action") or "").upper().startswith(arah)]
        gold = [x for x in grup if x["signal"].get("symbol") == "XAUUSD"]
        nas  = [x for x in grup if x["signal"].get("symbol") == "USTEC"]
        if gold and nas:
            kandidat = gold + nas
            kandidat.sort(key=lambda x: (x["verdict"]["rr"] or 0), reverse=True)
            pemenang = kandidat[0]
            for x in kandidat[1:]:
                x["verdict"]["decision"] = "REJECTED"
                x["verdict"]["reasons"].append(
                    "Korelasi: sudah ada " + pemenang["signal"].get("symbol", "?")
                    + " " + arah + " dengan RR lebih baik"
                )
    return approved


def check_market_session(signal):
    """Validasi sesi untuk USTEC. Mengembalikan alasan atau None."""
    if (signal.get("symbol") or "").upper() != "USTEC":
        return None
    if asian_or_late_session():
        return "Di luar sesi Nasdaq (12:00-18:00 UTC / 19:00-01:00 WIB)"
    return None
