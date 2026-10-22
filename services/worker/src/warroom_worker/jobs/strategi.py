"""Alert transisi status strategi & Multi-Asset Break-Retest Scanner Engine."""

from __future__ import annotations

import csv
import json
import logging
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as SASession
from warroom_core.db import Alert, Fact, Job
from warroom_notifier.dispatch import kirim_tertunda
from warroom_notifier.strategy_alert import alert_kill_switch

from warroom_worker.facts_publish import canonical_hash

from .base import _alert

log = logging.getLogger("warroom_worker.strategi")

__all__ = ["handler_strategi_alert", "handler_break_retest_scanner"]


CONFIG_TUNED = {
    "XAUUSD": {
        "lookback": 35, "sl_atr": 1.6, "rrr": 3.0, "tol": 0.0020, "req_rej": True,
        "category": "forex",
    },
    "BTCUSDT": {
        "lookback": 20, "sl_atr": 1.2, "rrr": 2.0, "tol": 0.0030, "req_rej": False,
        "category": "crypto",
    },
    "SOLUSDT": {
        "lookback": 15, "sl_atr": 1.8, "rrr": 3.0, "tol": 0.0040, "req_rej": True,
        "category": "crypto",
    },
    "EURUSD": {
        "lookback": 30, "sl_atr": 2.0, "rrr": 3.0, "tol": 0.0015, "req_rej": True,
        "category": "forex",
    },
    "GBPUSD": {
        "lookback": 15, "sl_atr": 2.0, "rrr": 3.0, "tol": 0.0015, "req_rej": True,
        "category": "forex",
    },
}


def _hitung_atr(candles: list[dict[str, float]], period: int = 14) -> list[float]:
    trs = []
    for i in range(len(candles)):
        if i == 0:
            trs.append(candles[i]["high"] - candles[i]["low"])
        else:
            prev_close = candles[i - 1]["close"]
            tr = max(
                candles[i]["high"] - candles[i]["low"],
                abs(candles[i]["high"] - prev_close),
                abs(candles[i]["low"] - prev_close),
            )
            trs.append(tr)

    atrs = [0.0] * len(candles)
    if len(trs) < period:
        return atrs

    atrs[period - 1] = sum(trs[:period]) / period
    for i in range(period, len(candles)):
        atrs[i] = (atrs[i - 1] * (period - 1) + trs[i]) / period
    return atrs


def _baca_candles(csv_path: Path) -> list[dict[str, float]]:
    candles = []
    if not csv_path.exists():
        return []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            next(reader)
        except StopIteration:
            return []
        for row in reader:
            if not row or len(row) < 5:
                continue
            try:
                candles.append({
                    "time": float(row[0]),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                })
            except (ValueError, TypeError):
                continue
    return candles


def _scan_pair_break_retest(pair: str, cfg: dict[str, Any]) -> dict[str, Any] | None:
    csv_file = Path("/home/admin/warroom/data/hist") / f"{pair}_15m.csv"
    candles = _baca_candles(csv_file)
    if len(candles) < cfg["lookback"] + 20:
        return None

    atrs = _hitung_atr(candles, period=14)
    lookback = cfg["lookback"]
    c_curr = candles[-1]
    c_prev = candles[-2]
    atr_curr = atrs[-1]
    if atr_curr <= 0:
        return None

    highs = [c["high"] for c in candles[-lookback - 1:-1]]
    lows = [c["low"] for c in candles[-lookback - 1:-1]]
    res_level = max(highs)
    sup_level = min(lows)

    # Long setup
    tol = cfg["tol"]
    sl_atr = cfg["sl_atr"]
    rrr = cfg["rrr"]

    if (
        c_prev["close"] > res_level
        and c_curr["low"] <= res_level * (1 + tol)
        and c_curr["close"] >= res_level * (1 - tol)
    ):
        if not cfg["req_rej"] or c_curr["close"] > c_curr["open"]:
            entry = c_curr["close"]
            sl = entry - (atr_curr * sl_atr)
            risk = entry - sl
            tp = entry + (risk * rrr)
            risk_pct = round((risk / entry) * 100, 2)
            
            # Freqtrade & Hummingbot Guards:
            # 1. Breakeven Trigger: jika harga capai +1.0R, geser SL ke entry
            # 2. Trailing Stop Trigger: jika harga capai +1.5R, trail SL 1.0x ATR di bawah harga
            be_trigger = entry + risk
            trail_trigger = entry + (risk * 1.5)
            trail_distance = round(atr_curr * 1.0, 4 if "USD" in pair and pair != "XAUUSD" else 2)

            return {
                "pair": pair,
                "arah": "LONG",
                "entry": round(entry, 4 if "USD" in pair and pair != "XAUUSD" else 2),
                "sl": round(sl, 4 if "USD" in pair and pair != "XAUUSD" else 2),
                "tp1": round(tp, 4 if "USD" in pair and pair != "XAUUSD" else 2),
                "risk_pct": risk_pct,
                "r_r": rrr,
                "be_trigger": round(be_trigger, 4 if "USD" in pair and pair != "XAUUSD" else 2),
                "trail_trigger": round(trail_trigger, 4 if "USD" in pair and pair != "XAUUSD" else 2),
                "trail_step": trail_distance,
                "spread_max_allowed_pct": 0.08,
                "tier": "PREMIUM",
                "strategy": "break_retest_15m_tuned",
                "category": cfg["category"],
                "aturan_gagal": [],
            }

    # Short setup
    if (
        c_prev["close"] < sup_level
        and c_curr["high"] >= sup_level * (1 - tol)
        and c_curr["close"] <= sup_level * (1 + tol)
    ):
        if not cfg["req_rej"] or c_curr["close"] < c_curr["open"]:
            entry = c_curr["close"]
            sl = entry + (atr_curr * sl_atr)
            risk = sl - entry
            tp = entry - (risk * rrr)
            risk_pct = round((risk / entry) * 100, 2)
            
            be_trigger = entry - risk
            trail_trigger = entry - (risk * 1.5)
            trail_distance = round(atr_curr * 1.0, 4 if "USD" in pair and pair != "XAUUSD" else 2)

            return {
                "pair": pair,
                "arah": "SHORT",
                "entry": round(entry, 4 if "USD" in pair and pair != "XAUUSD" else 2),
                "sl": round(sl, 4 if "USD" in pair and pair != "XAUUSD" else 2),
                "tp1": round(tp, 4 if "USD" in pair and pair != "XAUUSD" else 2),
                "risk_pct": risk_pct,
                "r_r": rrr,
                "be_trigger": round(be_trigger, 4 if "USD" in pair and pair != "XAUUSD" else 2),
                "trail_trigger": round(trail_trigger, 4 if "USD" in pair and pair != "XAUUSD" else 2),
                "trail_step": trail_distance,
                "spread_max_allowed_pct": 0.08,
                "tier": "PREMIUM",
                "strategy": "break_retest_15m_tuned",
                "category": cfg["category"],
                "aturan_gagal": [],
            }
    return None


def handler_break_retest_scanner(s: SASession, job: Job) -> str:
    """Scan multi-asset (Gold, BTC, SOL, EUR, GBP) dengan konfigurasi presisi hasil tuning."""
    now = datetime.now(UTC)
    wib_hour = (now.hour + 7) % 24
    wib_minute = now.minute

    # Macro Stand-Down Guard check (contoh jendela rilis data AS 19:15 - 19:45 WIB)
    stand_down = False
    alasan_guard = ""
    if (wib_hour == 19 and 15 <= wib_minute <= 45) or (wib_hour == 1 and 0 <= wib_minute <= 30):
        stand_down = True
        alasan_guard = "Macro Stand-Down Window (High Impact US Release / FOMC)"

    ditemukan = 0
    dipublikasikan = 0
    kandidat_list = []

    # 1. Integrasi Sensor Level Presisi dari Tencent Node (XAUUSD & BTC) via Tailscale
    try:
        req_tc = urllib.request.Request(
            "http://100.126.10.74:8790/forex/levels?symbol=XAUUSD",
            headers={"User-Agent": "WarRoomWorker/2.0"},
        )
        with urllib.request.urlopen(req_tc, timeout=4) as resp:
            if resp.status == 200:
                tc_data = json.loads(resp.read().decode("utf-8"))
                if tc_data.get("status") == "OK" and tc_data.get("levels"):
                    lv = tc_data["levels"]
                    sig_tc = {
                        "pair": "XAUUSD",
                        "arah": tc_data.get("side", "LONG"),
                        "entry": round(float(lv["entry"]), 2),
                        "sl": round(float(lv["sl"]), 2),
                        "tp1": round(float(lv["tp1"]), 2),
                        "risk_pct": round(float(lv.get("risk_pct", 0.09)), 3),
                        "r_r": 2.0,
                        "be_trigger": round(
                            float(lv["entry"]) + abs(float(lv["entry"]) - float(lv["sl"])), 2
                        ),
                        "trail_trigger": round(
                            float(lv["entry"]) + (abs(float(lv["entry"]) - float(lv["sl"])) * 1.5), 2
                        ),
                        "trail_step": round(float(tc_data.get("atr", 3.8)) * 1.0, 2),
                        "tier": "PREMIUM",
                        "strategy": "tencent_sensor_sr_scalping",
                        "category": "forex",
                        "zone": lv.get("zone"),
                        "aturan_gagal": [],
                    }
                    if stand_down:
                        sig_tc["tier"] = "STAND_DOWN"
                        sig_tc["aturan_gagal"] = [alasan_guard]

                    sumber_tc = f"tencent_node#{now.strftime('%Y%m%d%H%M')}"
                    val_tc = {
                        **sig_tc,
                        "ts": now.isoformat(),
                        "diambil": now.isoformat(),
                        "label": "Tencent Node S/R Scalping Sensor (WireGuard)",
                    }
                    fakta_tc = Fact(
                        kind="signal",
                        key="XAUUSD_TENCENT_SENSOR",
                        value_json=val_tc,
                        source=sumber_tc,
                        observed_at=now,
                        ttl_s=1800,
                        hash=canonical_hash(val_tc),
                    )
                    s.add(fakta_tc)
                    kandidat_list.append(f"XAUUSD_TC:{sig_tc['arah']}")
                    ditemukan += 1
                    dipublikasikan += 1
    except Exception as e:
        log.warning("Gagal query level Tencent node di worker: %s", e)

    # 2. Scanning Tuned Break & Retest Multi-Asset
    for pair, cfg in CONFIG_TUNED.items():
        sig = _scan_pair_break_retest(pair, cfg)
        if not sig:
            continue
        ditemukan += 1
        if stand_down and cfg["category"] == "forex":
            sig["tier"] = "STAND_DOWN"
            sig["aturan_gagal"] = [alasan_guard]

        sumber = f"break_retest_engine#{now.strftime('%Y%m%d%H%M')}"
        nilai = {
            **sig,
            "ts": now.isoformat(),
            "diambil": now.isoformat(),
            "label": "Tuned Break & Retest (Backtest Profitable Multi-Asset)",
        }
        fakta = Fact(
            kind="signal",
            key=f"{sig['pair']}_TUNED",
            value_json=nilai,
            source=sumber,
            observed_at=now,
            ttl_s=1800,
            hash=canonical_hash(nilai),
        )
        s.add(fakta)
        kandidat_list.append(f"{sig['pair']}:{sig['arah']}")
        dipublikasikan += 1

        # Kirim notifikasi jika bukan stand down
        if sig["tier"] != "STAND_DOWN":
            _alert(
                s,
                subject=f"sinyal/{sig['pair']}/{sig['arah']}",
                message=(
                    f"🎯 WAR ROOM TUNED SIGNAL — {sig['pair']} ({sig['arah']})\n"
                    f"Entry: {sig['entry']} | SL: {sig['sl']} | TP: {sig['tp1']}\n"
                    f"R:R 1:{sig['r_r']} | Stop: {sig['risk_pct']}%\n"
                    f"Strategi: Break & Retest 15m (Grid Tuned)"
                ),
                aksi="Tinjau setup di Cockpit / Alat. Keputusan eksekusi manual ada di tangan Anda.",
                severity="info",
                fact_ids=[fakta.id],
            )

    s.flush()
    return f"scan=5_pairs ditemukan={ditemukan} terbit={dipublikasikan} {' '.join(kandidat_list)}"


def handler_strategi_alert(s: SASession, job: Job) -> str:
    """Kabarkan transisi HALTED per strategi dari pasangan fakta terbaru."""
    kind = str(job.payload_json.get("kind", "harian"))
    key = str(job.payload_json.get("key", "status"))
    nama = str(job.payload_json.get("strategi", "Strategi A"))

    riwayat = list(
        s.scalars(
            select(Fact)
            .where(Fact.kind == kind, Fact.key == key)
            .order_by(Fact.observed_at.desc())
            .limit(5)
        ).all()
    )
    if len(riwayat) < 2:
        return f"{kind}/{key}: riwayat fakta < 2 — transisi belum bisa dinilai"

    obs = riwayat[0].observed_at
    if obs.tzinfo is None:
        obs = obs.replace(tzinfo=UTC)
    if datetime.now(UTC) - obs > timedelta(hours=26):
        raise RuntimeError(
            f"{kind}/{key}: fakta terbaru ({obs.isoformat()}) sudah stale > 26 jam"
        )

    for baru, lama in zip(riwayat, riwayat[1:], strict=False):
        v_baru = baru.value_json if isinstance(baru.value_json, dict) else {}
        v_lama = lama.value_json if isinstance(lama.value_json, dict) else {}
        if not v_baru.get("halted") or v_lama.get("halted"):
            continue
        alasan = str(v_baru.get("alasan_halted") or "kondisi risk engine (alasan tidak tercatat)")
        kondisi = alert_kill_switch(nama, alasan=alasan)
        sudah_ada = any(
            isinstance(a.fact_ids, list) and baru.id in a.fact_ids
            for a in s.scalars(select(Alert).where(Alert.subject == kondisi.subjek)).all()
        )
        if sudah_ada:
            break
        if (
            job.last_status == "ok"
            and job.last_run_at is not None
            and baru.observed_at < job.last_run_at
        ):
            break
        dibuat = _alert(
            s, subject=kondisi.subjek, message=kondisi.pesan,
            aksi=kondisi.subjek_aksi, severity=kondisi.severity,
            fact_ids=[baru.id],
        )
        if dibuat:
            kirim_tertunda(s, limit=5)
        return (
            f"{nama}: transisi HALTED {'dikabarkan' if dibuat else 'sudah ada alert terbuka'}"
            f" — {alasan}"
        )
    return f"{kind}/{key}: {len(riwayat)} fakta diperiksa — tidak ada transisi HALTED baru"

