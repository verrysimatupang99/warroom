"""Adapter sinyal (baca-saja) — ledger verdict mesin sinyal domain.

Sumber: ``<domain>/state/verdicts.jsonl`` yang ditulis ``lt scan`` (job ``collect``).
**Tidak ada panggilan jaringan** dan tidak ada tulis ke sumber — jadi membaca sinyal tidak
menambah kuota atau beban ke exchange mana pun.

Kejujuran (wajib): yang keluar dari sini adalah **kandidat**, bukan rekomendasi. Gate statistik
proyek belum membuktikan edge di atas break-even, jadi setiap pesan membawa label itu apa adanya.
Mengabarkan kandidat seolah sudah terbukti adalah tepat kesalahan yang dilakukan kompetitor.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from warroom_worker.adapters.io import baca_jsonl_ekor

__all__ = ["LABEL_JUJUR", "EKOR", "sinyal_terakhir"]

#: Label yang WAJIB ikut pada setiap pesan sinyal.
LABEL_JUJUR = (
    "kandidat belum-terbukti — gate statistik belum lolos "
    "(interval kepercayaan bawah belum jelas di atas break-even)"
)

#: Berapa baris ekor yang dibaca (ledger tumbuh ~20 baris/hari; 600 ≈ sebulan).
EKOR = 600


def _ts(row: dict[str, Any]) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(row.get("ts")))
    except (ValueError, TypeError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _r_r(entry: Any, sl: Any, tp1: Any) -> float | None:
    try:
        e, s, t = float(entry), float(sl), float(tp1)
        risiko = abs(e - s)
        if risiko <= 0:
            return None
        return round(abs(t - e) / risiko, 2)
    except (TypeError, ValueError):
        return None


def sinyal_terakhir(
    state_dir: str | Path,
    *,
    jam_terakhir: float = 6.0,
    max_n: int = 12,
    sekarang: datetime | None = None,
) -> dict[str, Any]:
    """Sinyal yang **lolos gate** dalam jendela terakhir — terbaru dulu, unik per pair+arah.

    Gagal baca → status + alasan (bukan daftar kosong yang menyamar jadi "tidak ada sinyal").
    """
    b = baca_jsonl_ekor(Path(state_dir) / "verdicts.jsonl", EKOR)
    if not b.ok:
        return {"status": b.status, "path": b.path, "detail": b.detail, "sinyal": []}

    kini = sekarang or datetime.now(UTC)
    batas = kini - timedelta(hours=jam_terakhir)
    per_kunci: dict[tuple[str, str], dict[str, Any]] = {}
    for r in b.data or []:
        if not r.get("allowed"):
            continue
        ts = _ts(r)
        if ts is None or ts < batas:
            continue
        pair = str(r.get("pair") or "").upper()
        arah = str(r.get("direction") or "").upper()
        if not pair or not arah:
            continue
        rules = r.get("rules") or []
        per_kunci[(pair, arah)] = {
            "ts": ts.isoformat(timespec="seconds"),
            "pair": pair,
            "arah": arah,
            "tier": r.get("tier"),
            "entry": r.get("entry"),
            "sl": r.get("sl"),
            "tp1": r.get("tp1"),
            "risk_pct": r.get("risk_pct"),
            "r_r": _r_r(r.get("entry"), r.get("sl"), r.get("tp1")),
            "strategy": r.get("strategy"),
            "mode": r.get("mode", "PAPER"),
            "detail": r.get("detail") or {},
            "aturan_gagal": [str(v.get("rule")) for v in rules if isinstance(v, dict) and not v.get("ok")],
        }
    sinyal = sorted(per_kunci.values(), key=lambda x: x["ts"], reverse=True)[:max_n]
    return {
        "status": "ok",
        "path": b.path,
        "sha256": b.sha256,
        "rusak": (b.meta or {}).get("rusak", 0),
        "jendela_jam": jam_terakhir,
        "jumlah": len(sinyal),
        "label": LABEL_JUJUR,
        "sinyal": sinyal,
    }
