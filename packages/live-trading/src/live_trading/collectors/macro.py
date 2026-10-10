"""Kolektor kalender makro — bahan gerbang *stand-down*.

Kenapa ada: setup yang bersih tetap trade yang salah kalau jatuh persis di depan
CPI/NFP/FOMC. Layanan sejenis di industri ini memakai stand-down yang sama, dan
biayanya nyaris nol dibanding nilainya.

Sumber: kalender mingguan ForexFactory (JSON publik, tanpa API key).
    https://nfs.faireconomy.media/ff_calendar_thisweek.json
Field: ``title``, ``country``, ``date`` (ISO 8601 + offset), ``impact``, ``forecast``, ``previous``.

Disiplin yang sama dengan kolektor lain: cache lokal, dan saat sumber tak terjangkau
pakai cache terakhir **beserta umurnya** — bukan ``n/a`` tanpa jejak, dan bukan angka karangan.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import Settings, get_settings
from . import make_client

CAL_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
CACHE_NAME = "macro_calendar.json"
#: Kalender ini mingguan; 6 jam sudah cukup segar dan hemat.
TTL_S = 6 * 3600

#: Mata uang yang pergerakannya relevan untuk pasar kita.
MATA_UANG_DIPANTAU: tuple[str, ...] = ("USD", "EUR", "JPY", "GBP", "AUD", "CHF", "CAD", "CNY")

#: Hanya event berdampak tinggi yang memblokir entri.
IMPACT_BLOKIR: tuple[str, ...] = ("High",)


def _ts(nilai: Any) -> float | None:
    """ISO 8601 (dengan offset) → epoch detik. Gagal = None (event dibuang, bukan ditebak)."""
    try:
        return datetime.fromisoformat(str(nilai)).timestamp()
    except (ValueError, TypeError):
        return None


def normalisasi(events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Payload mentah → bentuk tetap, urut waktu. Event tanpa waktu sah dibuang."""
    out: list[dict[str, Any]] = []
    for e in events or []:
        if not isinstance(e, dict):
            continue
        ts = _ts(e.get("date"))
        if ts is None:
            continue
        out.append(
            {
                "ts": ts,
                "title": str(e.get("title") or "?").strip(),
                "mata_uang": str(e.get("country") or "?").upper(),
                "impact": str(e.get("impact") or "?"),
                "forecast": str(e.get("forecast") or ""),
                "previous": str(e.get("previous") or ""),
            }
        )
    return sorted(out, key=lambda x: x["ts"])


def stand_down(
    events: list[dict[str, Any]] | None,
    *,
    sekarang: float | None = None,
    jendela_menit: int = 60,
    mata_uang: tuple[str, ...] = MATA_UANG_DIPANTAU,
) -> list[dict[str, Any]]:
    """Event berdampak tinggi di dalam jendela **ke depan** → alasan menahan diri.

    Sengaja hanya melihat ke depan: tujuannya mencegah entri buta tepat sebelum rilis,
    bukan melarang trading setelah volatilitasnya lewat.
    """
    kini = time.time() if sekarang is None else sekarang
    batas = kini + jendela_menit * 60
    blokir: list[dict[str, Any]] = []
    for e in events or []:
        if e.get("impact") not in IMPACT_BLOKIR:
            continue
        if mata_uang and e.get("mata_uang") not in mata_uang:
            continue
        ts = e.get("ts")
        if isinstance(ts, (int, float)) and kini <= ts <= batas:
            blokir.append({**e, "menit_lagi": round((ts - kini) / 60, 1)})
    return sorted(blokir, key=lambda x: x["ts"])


def ringkas(
    events: list[dict[str, Any]],
    *,
    jendela_menit: int = 60,
    dari_cache_mnt: float | None = None,
    error: str | None = None,
    sekarang: float | None = None,
) -> dict[str, Any]:
    """Bentuk siap-tampil untuk dashboard/API."""
    kini = time.time() if sekarang is None else sekarang
    blokir = stand_down(events, sekarang=kini, jendela_menit=jendela_menit)
    depan = [e for e in events if e.get("ts", 0) >= kini][:6]
    # Rentang tanggal data (informatif). Sumber "thisweek" hanya memuat minggu berjalan;
    # saat minggu itu habis (mis. Sabtu), `berikutnya` kosong walaupun `jumlah` besar.
    # Tanpa rentang, UI tak bisa membedakan "tak ada agenda" dari "data minggu lalu" —
    # pembaca bisa salah paham bahwa benar-benar tak ada agenda. Murni keterangan, bukan gate.
    ts_sah = [e["ts"] for e in events if isinstance(e.get("ts"), (int, float))]
    return {
        "tersedia": True,
        "jumlah": len(events),
        "jendela_menit": jendela_menit,
        "stand_down": bool(blokir),
        "alasan": blokir,
        "berikutnya": depan,
        "dari_cache_mnt": dari_cache_mnt,
        "tanggal_min": min(ts_sah) if ts_sah else None,
        "tanggal_max": max(ts_sah) if ts_sah else None,
        "error": error,
    }


class MacroCollector:
    """Ambil kalender makro; cache lokal + fallback ke cache basi (ditandai umurnya)."""

    def __init__(self, settings: Settings | None = None, client: Any | None = None) -> None:
        self.s = settings or get_settings()
        self.client = client

    def fetch(self) -> list[dict[str, Any]]:
        c = self.client or make_client(timeout=20.0)
        r = c.get(CAL_URL)
        r.raise_for_status()
        return normalisasi(r.json())

    def snapshot(
        self, state_dir: Path | str, *, jendela_menit: int = 60, sekarang: float | None = None
    ) -> dict[str, Any]:
        p = Path(state_dir) / "cache" / CACHE_NAME
        kini = time.time() if sekarang is None else sekarang
        basi: dict[str, Any] | None = None
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            umur_s = kini - float(d.get("diambil_epoch") or 0)
            if umur_s < TTL_S:
                return ringkas(
                    d.get("events") or [],
                    jendela_menit=jendela_menit,
                    error=d.get("error"),
                    sekarang=kini,
                )
            basi = d
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

        try:
            events = self.fetch()
        except Exception as exc:  # noqa: BLE001 — dashboard jangan mati karena satu panel
            pesan = f"{type(exc).__name__}: {exc}"
            if basi is not None:
                umur_mnt = round((kini - float(basi.get("diambil_epoch") or 0)) / 60, 1)
                return ringkas(
                    basi.get("events") or [],
                    jendela_menit=jendela_menit,
                    dari_cache_mnt=umur_mnt,
                    error=pesan,
                    sekarang=kini,
                )
            return {"tersedia": False, "error": pesan}

        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps({"diambil_epoch": kini, "events": events}), encoding="utf-8")
            tmp.replace(p)
        except OSError:
            pass
        return ringkas(events, jendela_menit=jendela_menit, sekarang=kini)
