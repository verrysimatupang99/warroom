"""Agregat jam & hari terbaik trade — fungsi murni, tanpa I/O dan tanpa FastAPI.

Dipisah dari router supaya bisa diuji dengan data mock. Bentuk baris mengikuti
`lokal.journal_trades`: `iso` adalah waktu TUTUP trade, `pnl_usd` untuk forex dan
`r` (kelipatan risiko) untuk crypto paper.

Kenapa `pnl_usd`/`r`, bukan `pnl_pct`: MT5 tidak mengirim `pnl_pct` maupun
`close_price` untuk forex, jadi persentase akan selalu kosong. Uang (USD) dan R
adalah satu-satunya angka hasil yang benar-benar ada di sumber.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

HARI = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")

# Ambang minimal trade sebelum sebuah jam/hari boleh disebut "terbaik". Satu trade
# yang kebetulan profit bukan bukti pola; ambang ini menjaga label tetap jujur.
MIN_N = 2


def _angka(v: Any) -> float | None:
    """Konversi longgar ke float; kosong/None/teks aneh -> None (bukan 0)."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _waktu_utc(iso: Any) -> datetime | None:
    """Parse `iso` menjadi datetime UTC.

    Dua bentuk nyata di repo: `2026-11-10T19:17:00+00:00` (deals.csv) dan
    `2026-11-10 19:17:00` (hasil `jurnal_forex.dari_db`). Yang tanpa zona waktu
    diperlakukan UTC karena kedua sumber menyimpan UTC.
    """
    teks = str(iso or "").strip()
    if not teks:
        return None
    if teks.endswith("Z"):
        teks = teks[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(teks)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _kotak() -> dict[str, Any]:
    """Satu keranjang agregat. Angka yang tak punya dasar = None, bukan 0 palsu."""
    return {"n": 0, "menang": 0, "rugi": 0, "seri": 0, "winrate_pct": None, "pnl_usd_total": None}


def _tutup(k: dict[str, Any]) -> dict[str, Any]:
    """Hitung turunan keranjang setelah semua trade masuk."""
    diputuskan = k["menang"] + k["rugi"]
    k["winrate_pct"] = round(k["menang"] / diputuskan * 100, 2) if diputuskan else None
    if k["pnl_usd_total"] is not None:
        k["pnl_usd_total"] = round(k["pnl_usd_total"], 2)
    return k


def agregat_jam_hari(
    trades: list[dict[str, Any]] | None, *, market: str = "forex"
) -> dict[str, Any]:
    """Hitung win-rate & total PnL per jam (0-23 UTC) dan per hari (Senin-Minggu).

    `market` hanya memilih kolom penentu hasil: `pnl_usd` (forex) atau `r` (crypto).
    Baris tanpa `iso` valid atau tanpa angka hasil dilewati dan dihitung di
    `n_tanpa_waktu`, supaya `n_total` tetap bisa dibandingkan dengan sumbernya.
    """
    kunci = "r" if market == "crypto" else "pnl_usd"
    satuan = "r" if market == "crypto" else "pnl_usd"

    per_jam: dict[int, dict[str, Any]] = {j: _kotak() for j in range(24)}
    per_hari: dict[int, dict[str, Any]] = {i: _kotak() for i in range(7)}
    n_total = 0
    n_tanpa_waktu = 0
    n_tanpa_hasil = 0

    for t in trades or []:
        n_total += 1
        dt = _waktu_utc(t.get("iso"))
        if dt is None:
            n_tanpa_waktu += 1
            continue
        nilai = _angka(t.get(kunci))
        if nilai is None:
            n_tanpa_hasil += 1
            continue

        for k in (per_jam[dt.hour], per_hari[dt.weekday()]):
            k["n"] += 1
            if nilai > 0:
                k["menang"] += 1
            elif nilai < 0:
                k["rugi"] += 1
            else:
                k["seri"] += 1
            k["pnl_usd_total"] = (k["pnl_usd_total"] or 0.0) + nilai

    jam = [_tutup({"jam": j, **per_jam[j]}) for j in range(24)]
    hari = [_tutup({"hari": HARI[i], "index": i, **per_hari[i]}) for i in range(7)]

    def terbaik(baris: list[dict[str, Any]], label: str) -> dict[str, Any] | None:
        # Syarat sesuai spesifikasi: total PnL tertinggi dengan n >= MIN_N.
        layak = [
            b for b in baris
            if b["n"] >= MIN_N and b["pnl_usd_total"] is not None
        ]
        if not layak:
            return None
        # Urutan deterministik: PnL terbesar, lalu n terbesar, lalu label terkecil.
        pilih = sorted(
            layak, key=lambda b: (-b["pnl_usd_total"], -b["n"], b[label])
        )[0]
        return dict(pilih)

    return {
        "market": market,
        "satuan": satuan,
        "min_n": MIN_N,
        "n_total": n_total,
        "n_tanpa_waktu": n_tanpa_waktu,
        "n_tanpa_hasil": n_tanpa_hasil,
        "per_jam": jam,
        "per_hari": hari,
        "jam_terbaik": terbaik(jam, "jam"),
        "hari_terbaik": terbaik(hari, "hari"),
    }
