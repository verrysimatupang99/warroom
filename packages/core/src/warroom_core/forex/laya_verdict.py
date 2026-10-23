"""Cache verdict Laya AI — memisahkan inferensi dari jalur permintaan.

Latar belakang (insiden 23 Okt 2026): model Laya 421M dimuat di DALAM proses API.
Biaya terukur: 30 detik saat cold start dan 1,5-2,2 detik saat warm, sementara
timeout WebRequest EA hanya 3 detik. Model itu juga menambah ~1 GB RSS ke proses
yang melayani dashboard dan EA sekaligus, dan pernah membekukan seluruh API.

Pola yang dipakai sekarang:
    job terjadwal (proses terpisah)  ->  tulis verdict ke berkas state
    API/strategi                     ->  baca berkas itu (instan, tanpa model)

Semantik gerbang tetap FAIL-CLOSED: verdict tidak ada, basi, atau tidak cocok
dengan sesi berjalan berarti sinyal DIBLOKIR — bukan diloloskan.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

DEFAULT_PATH = "/var/lib/warroom/laya_verdict.json"
DEFAULT_TTL_SEC = 180
DEFAULT_MIN_CONFIDENCE = 0.60


def _path() -> Path:
    return Path(os.environ.get("WARROOM_LAYA_VERDICT_PATH", DEFAULT_PATH))


def _ttl() -> int:
    try:
        return int(os.environ.get("WARROOM_LAYA_VERDICT_TTL_SEC", DEFAULT_TTL_SEC))
    except ValueError:
        return DEFAULT_TTL_SEC


def write_verdict(payload: dict[str, Any]) -> Path:
    """Tulis verdict secara atomik agar pembaca tidak pernah melihat berkas separuh."""
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    isi = dict(payload)
    isi.setdefault("ts", int(time.time()))
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".laya-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(isi, fh, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return path


def read_verdict() -> dict[str, Any] | None:
    """Baca verdict terakhir. Mengembalikan None bila tidak ada / rusak."""
    path = _path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    ts = data.get("ts")
    if isinstance(ts, (int, float)):
        data["age_sec"] = max(0, int(time.time() - ts))
    else:
        data["age_sec"] = None
    return data


def ambil(
    side: str,
    session: str,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> tuple[bool, float, str]:
    """Ambil keputusan gerbang dari cache. SELALU fail-closed.

    Mengembalikan (layak_eksekusi, keyakinan, alasan). Setiap jalur yang tidak
    bisa membuktikan keamanan mengembalikan False beserta alasan eksplisit.
    """
    data = read_verdict()
    if data is None:
        return (
            False,
            0.0,
            "Verdict Laya belum tersedia (job terjadwal belum menulis) — sinyal DIBLOKIR",
        )

    umur = data.get("age_sec")
    ttl = _ttl()
    if umur is None:
        return False, 0.0, "Verdict Laya tanpa stempel waktu — sinyal DIBLOKIR"
    if umur > ttl:
        return (
            False,
            0.0,
            f"Verdict Laya BASI ({umur}s > TTL {ttl}s) — sinyal DIBLOKIR",
        )

    sesi_cache = str(data.get("session") or "").upper()
    if sesi_cache != str(session or "").upper():
        return (
            False,
            0.0,
            f"Verdict Laya untuk sesi {sesi_cache or '?'} bukan {session} — sinyal DIBLOKIR",
        )

    per_side = (data.get("verdicts") or {}).get(str(side or "").upper())
    if not isinstance(per_side, dict):
        return False, 0.0, f"Verdict Laya tidak memuat arah {side} — sinyal DIBLOKIR"

    pilihan = str(per_side.get("choice") or "").upper()
    if pilihan not in ("EXECUTE", "SKIP"):
        return (
            False,
            0.0,
            f"Verdict Laya tidak dikenali ({pilihan or 'kosong'}) — sinyal DIBLOKIR",
        )

    try:
        keyakinan = float(per_side.get("confidence") or 0.0)
    except (TypeError, ValueError):
        keyakinan = 0.0

    layak = pilihan == "EXECUTE" and keyakinan >= min_confidence
    alasan = (
        f"Laya {pilihan} p={keyakinan:.3f} (ambang {min_confidence:.2f}, "
        f"umur {umur}s/{ttl}s) side={side} sesi={session}"
    )
    return layak, keyakinan, alasan
