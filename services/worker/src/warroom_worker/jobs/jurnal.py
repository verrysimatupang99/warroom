"""Jurnal sinyal: alert terkirim → hasil pasar sejak jam setelah kirim.

Ini bukan `lt measure` (yang mengukur dari waktu verdict). Tujuannya menjawab
pertanyaan yang berbeda: **penerima pesan mendapat hasil apa?** Karena itu candle
dimulai dari jam penuh setelah `alerts.created_at`, bukan dari `verdict.ts`.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session as SASession
from warroom_core.db import Alert, Job
from warroom_core.jurnal_sinyal import cocokkan, muat_outcomes, ringkas

from .base import _tulis_fakta, root_dir

log = logging.getLogger("warroom_worker.jobs")

JURNAL_PATH = Path("/var/lib/warroom/jurnal_sinyal.json")


def _ambil_klines(client: httpx.Client, base: str, pair: str, mulai_ms: int) -> list:
    r = client.get(
        f"{base}/fapi/v1/klines",
        params={"symbol": pair, "interval": "1h", "startTime": mulai_ms, "limit": 1000},
    )
    r.raise_for_status()
    return r.json()


def handler_jurnal_sinyal(s: SASession, job: Job) -> str:
    """Hitung ulang hasil tiap alert sinyal dari candle Binance setelah pesan dikirim."""
    from live_trading.config import get_settings
    from live_trading.measure import FILL_WINDOW_H, HOLD_MAX_H, resolve_one

    p = job.payload_json or {}
    max_alerts = int(p.get("max_alerts", 2000))
    keluaran = Path(p.get("output", str(JURNAL_PATH)))
    ttl_s = int(p.get("ttl_s", 86400))
    catatan = ""

    if bool(p.get("refresh_outcomes", True)):
        try:
            from .base import _jalankan_lt

            _jalankan_lt("measure", job, timeout_s=int(p.get("measure_timeout_s", 600)))
        except Exception as exc:  # noqa: BLE001 — cache lama masih bisa dipakai
            catatan = f"measure gagal: {type(exc).__name__}: {str(exc)[:100]}"
            log.warning("jurnal sinyal: %s", catatan)

    outcomes = muat_outcomes(root_dir() / "state" / "outcomes.jsonl")
    if not outcomes:
        return f"outcomes.jsonl belum ada; jurnal sinyal belum bisa dihitung. {catatan}".strip()

    baris = s.scalars(
        select(Alert)
        .where(Alert.subject.like("sinyal/%"))
        .order_by(Alert.created_at.desc())
        .limit(max_alerts)
    ).all()
    alerts = [
        {"id": a.id, "t": int(a.created_at.timestamp()), "subject": a.subject}
        for a in baris
    ]
    matched = cocokkan(alerts, outcomes)
    if not matched:
        return f"tidak ada alert sinyal yang cocok dengan {len(outcomes)} outcome"

    cfg = get_settings()
    now = datetime.now(UTC)
    klines_per_pair: dict[str, list] = {}
    gagal: list[str] = []
    with httpx.Client(timeout=30.0) as client:
        for pair in sorted({m["pair"] for m in matched}):
            awal = min(
                int(datetime.fromisoformat(m["dikirim"]).timestamp())
                for m in matched
                if m["pair"] == pair
            )
            mulai_ms = (awal // 3600) * 3600 * 1000
            try:
                klines_per_pair[pair] = _ambil_klines(
                    client, cfg.binance_fapi, pair, mulai_ms
                )
            except Exception as exc:  # noqa: BLE001 — satu pair gagal ≠ seluruh jurnal gagal
                gagal.append(pair)
                log.warning("jurnal sinyal: klines %s gagal: %s", pair, exc)

    hasil: list[dict[str, Any]] = []
    for m in matched:
        v = m["verdict"]
        dasar: dict[str, Any] = {
            "alert_id": m["alert_id"],
            "dikirim": m["dikirim"],
            "pair": m["pair"],
            "side": m["side"],
            "tier": v.get("tier"),
            "entry": v.get("entry"),
            "sl": v.get("sl"),
            "tp1": v.get("tp1"),
            "hasil_cache": v.get("hasil"),
            "r_cache": v.get("r"),
        }
        if m["pair"] in gagal:
            hasil.append({**dasar, "hasil": "gagal_ambil_data", "r": None})
            continue
        klines = klines_per_pair.get(m["pair"]) or []
        t_kirim = int(datetime.fromisoformat(m["dikirim"]).timestamp() * 1000)
        idx = next((i for i, k in enumerate(klines) if int(k[0]) >= t_kirim), None)
        if idx is None:
            hasil.append({**dasar, "hasil": "belum_ada_data", "r": None})
            continue
        jendela = klines[idx : idx + FILL_WINDOW_H + HOLD_MAX_H + 2]
        simulasi = resolve_one(
            {
                "ts": m["dikirim"],
                "pair": m["pair"],
                "direction": m["side"],
                "allowed": True,
                "tier": v.get("tier"),
                "entry": v.get("entry"),
                "sl": v.get("sl"),
                "tp1": v.get("tp1"),
            },
            jendela,
            now=now,
        )
        hasil.append(
            {
                **dasar,
                "hasil": simulasi["hasil"],
                "r": simulasi.get("r"),
                "jam_ke_isi": simulasi.get("jam_ke_isi"),
                "jam_ke_hasil": simulasi.get("jam_ke_hasil"),
            }
        )

    ringkasan = ringkas(hasil)
    data = {
        "dihitung_at": now.isoformat(),
        "sumber": "alerts + outcomes.jsonl + Binance 1H sejak jam setelah kirim",
        "n_rows": len(hasil),
        "gagal_pair": gagal,
        "catatan": catatan,
        "ringkas": ringkasan,
        "rows": hasil[-500:],
    }
    keluaran.parent.mkdir(parents=True, exist_ok=True)
    tmp = keluaran.with_suffix(keluaran.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, keluaran)

    _tulis_fakta(
        s,
        kind="jurnal.sinyal",
        key="ringkas",
        value={
            **ringkasan,
            "dihitung_at": now.isoformat(),
            "n_rows": len(hasil),
            "gagal_pair": gagal,
        },
        source="lokal:alerts+outcomes+binance",
        ttl_s=ttl_s,
    )
    return (
        f"alert={len(alerts)} cocok={len(matched)} final={ringkasan['n_terisi']} "
        f"wr={ringkasan['winrate']}% exp={ringkasan['expectancy_r']}R "
        f"beda_cache={ringkasan['beda_cache']} gagal_pair={len(gagal)}"
        + (f" catatan={catatan}" if catatan else "")
    )
