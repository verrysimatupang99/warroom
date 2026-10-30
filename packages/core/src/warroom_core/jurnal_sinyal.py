"""Jurnal sinyal: gabungkan alert yang benar-benar dikirim dengan hasil pasar.

Sumber:
- alert `alerts` (subject ``sinyal/<PAIR>/<SIDE>``) — waktu kirim = `created_at`.
- verdict `allowed=true` — entry/SL/TP1 yang dipakai saat mengirim.
- hasil dihitung ulang dari candle sejak **jam setelah kirim**, bukan dari waktu verdict.

Modul ini hanya memuat data dan mencocokkan; pengambilan candle dan simulasi ada di
worker (`handler_jurnal_sinyal`) karena memakai `live_trading.measure.resolve_one`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TOLERANSI_S = 120
JENDELA_S = 6 * 3600


def muat_outcomes(path: Path) -> list[dict[str, Any]]:
    """Baca outcomes.jsonl; baris rusak dilewati, bukan menggagalkan seluruh jurnal."""
    if not path.exists():
        return []
    hasil = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict) or not row.get("ts"):
            continue
        try:
            row["_ts"] = datetime.fromisoformat(str(row["ts"]).replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        hasil.append(row)
    return hasil


def _pair_side(subject: str) -> tuple[str, str] | None:
    bagian = str(subject or "").split("/")
    if len(bagian) != 3 or bagian[0] != "sinyal":
        return None
    pair, side = bagian[1].strip().upper(), bagian[2].strip().upper()
    return (pair, side) if pair and side else None


def cocokkan(
    alerts: Iterable[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    *,
    toleransi_s: int = TOLERANSI_S,
    jendela_s: int = JENDELA_S,
) -> list[dict[str, Any]]:
    """Cocokkan alert ke verdict `allowed` terdekat; dedupe per verdict.

    ``alerts`` berisi dict minimal: ``id``, ``t`` (epoch detik), ``subject``.
    Alert duplikat untuk verdict yang sama dihitung sekali; itulah yang dikirim.
    """
    per_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in outcomes:
        if not r.get("allowed"):
            continue
        kunci = (str(r.get("pair") or "").upper(), str(r.get("direction") or "").upper())
        per_pair.setdefault(kunci, []).append(r)
    for daftar in per_pair.values():
        daftar.sort(key=lambda x: x["_ts"])

    hasil: dict[tuple[str, str, str], dict[str, Any]] = {}
    for a in alerts:
        ps = _pair_side(str(a.get("subject") or ""))
        if ps is None:
            continue
        pair, side = ps
        t = int(a["t"])
        kandidat = [
            r
            for r in per_pair.get((pair, side), [])
            if r["_ts"] <= t + toleransi_s and t - r["_ts"] <= jendela_s
        ]
        if not kandidat:
            continue
        v = max(kandidat, key=lambda x: x["_ts"])
        kunci = (v["ts"], pair, side)
        if kunci in hasil:
            continue
        hasil[kunci] = {
            "alert_id": a.get("id"),
            "dikirim": datetime.fromtimestamp(t, UTC).isoformat(timespec="seconds"),
            "pair": pair,
            "side": side,
            "verdict": v,
        }
    return sorted(hasil.values(), key=lambda x: x["dikirim"])


def biaya_r(entry: Any, sl: Any, fee_bps_per_sisi: float) -> float:
    """Biaya round-trip dalam satuan R: (2 × fee × harga) / jarak SL.

    Contoh: SL 1% dari harga, fee 0,05%/sisi → biaya 0,10R per trade. Itu cukup
    menghabiskan edge tier STANDAR yang gross-nya hanya +0,05R.
    """
    try:
        e, s = float(entry), float(sl)
    except (TypeError, ValueError):
        return 0.0
    risk = abs(e - s)
    if risk <= 0:
        return 0.0
    return (2 * (fee_bps_per_sisi / 10000.0) * e) / risk


def _final(row: dict[str, Any]) -> bool:
    return row.get("r") is not None and row.get("hasil") in (
        "tp1",
        "tp2",
        "sl",
        "kedaluwarsa",
        "terbuka",
    )


def ringkas(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Statistik dari baris hasil (field: hasil, r, r_net, tier)."""
    final = [r for r in rows if _final(r)]
    tp1 = sum(1 for r in final if r["hasil"] == "tp1")
    sl = sum(1 for r in final if r["hasil"] == "sl")
    total = round(sum(float(r["r"]) for r in final), 3)

    def _net(r: dict[str, Any]) -> float:
        nilai = r.get("r_net")
        return float(nilai) if nilai is not None else float(r["r"])

    total_net = round(sum(_net(r) for r in final), 3)
    biaya = [float(r["biaya_r"]) for r in final if r.get("biaya_r") is not None]
    kategori: dict[str, int] = {}
    for r in rows:
        kategori[str(r.get("hasil") or "?")] = kategori.get(str(r.get("hasil") or "?"), 0) + 1

    per_tier: dict[str, dict[str, Any]] = {}
    for tier in sorted({str(r.get("tier")) for r in rows}):
        f = [r for r in final if str(r.get("tier")) == tier]
        if not f:
            continue
        t_tp1 = sum(1 for r in f if r["hasil"] == "tp1")
        t_sl = sum(1 for r in f if r["hasil"] == "sl")
        t_total = round(sum(float(r["r"]) for r in f), 3)
        t_net = round(sum(_net(r) for r in f), 3)
        per_tier[tier] = {
            "n_terkirim": sum(1 for r in rows if str(r.get("tier")) == tier),
            "n_terisi": len(f),
            "tp1": t_tp1,
            "sl": t_sl,
            "winrate": round(t_tp1 / len(f) * 100, 1),
            "total_r": t_total,
            "expectancy_r": round(t_total / len(f), 4),
            "total_r_net": t_net,
            "expectancy_net_r": round(t_net / len(f), 4),
        }

    sama = sum(1 for r in rows if r.get("hasil") == r.get("hasil_cache"))
    return {
        "n_terkirim": len(rows),
        "n_terisi": len(final),
        "tp1": tp1,
        "sl": sl,
        "winrate": round(tp1 / len(final) * 100, 1) if final else None,
        "total_r": total,
        "expectancy_r": round(total / len(final), 4) if final else None,
        "expectancy_0r": round(total / len(rows), 4) if rows else None,
        "total_r_net": total_net,
        "expectancy_net_r": round(total_net / len(final), 4) if final else None,
        "expectancy_net_0r": round(total_net / len(rows), 4) if rows else None,
        "biaya_r_rata": round(sum(biaya) / len(biaya), 4) if biaya else None,
        "kategori": dict(sorted(kategori.items())),
        "per_tier": per_tier,
        "sama_cache": sama,
        "beda_cache": len(rows) - sama,
    }
