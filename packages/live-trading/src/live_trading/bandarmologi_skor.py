"""Skor Bandarmologi (adopsi pola produk acuan ihsgscreener, 6 Okt 2026).

Yang diadopsi dari ihsgscreener: satu ANGKA ringkas per emiten (Intelligence Score)
yang memaksa banyak sinyal kecil digabung dengan bobot yang bisa dijelaskan — bukan
tumpukan tabel yang harus dibaca manual.

Yang TIDAK diadopsi: skor "rekomendasi AI" tanpa jejak hitungan. Di sini setiap
komponen punya **kontribusi yang bisa diaudit** (`komponen[]`), dan semua angka masuk
apa adanya dari broker summary (ATS beli/jual, frekuensi, no-sell). Skor 0–100 ini
ALAT BACA, bukan ajakan beli — label itu ikut dikembalikan.

Catatan jujur yang melekat:
- ATS/frq adalah aliran BROKER hari itu; satu hari tidak membuktikan akumulasi.
  Nilai `n_hari` dan `peringatan` selalu ikut.
- Komponen dinormalisasi batas tetap (bukan persentil antar emiten) supaya skor
  TIDAK berubah hanya karena komposisi radar hari ini berubah.
"""

from __future__ import annotations

from typing import Any

__all__ = ["skor_bandarmologi", "skor_dari_hasil"]

# Bobot komponen (total 100). Angka dipilih dari yang paling langsung bermakna:
# rasio ATS beli/jual adalah sinyal agresivitas; frekuensi menunjukkan siapa yang ramai.
_BOBOT = {
    "rasio_ats": 40,      # ATS beli / (beli+jual) — pusat dari bandarmologi
    "rasio_frq": 30,      # frekuensi beli / (beli+jual) — seringnya sisi mana
    "no_sell": 20,        # tidak ada antrean jual besar (bonus, hanya bila benar)
    "ukuran_ats": 10,     # ukuran transaksi rata-rata (besar = institusional)
}

_PERINGATAN = (
    "Skor ini alat baca satu hari broker summary — bukan bukti akumulasi. "
    "Tidak ada track record yang melekat pada skor; jangan dijadikan ajakan beli."
)


def _bagian_rasio(beli: float, jual: float) -> float:
    """0..1 dari rasio beli vs jual; 0.5 = seimbang, tanpa memihak skala absolut."""
    total = beli + jual
    if total <= 0:
        return 0.5
    return beli / total


def skor_dari_hasil(hasil: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hitung skor per emiten dari `bagian.bandarmologi.hasil`.

    Bentuk keluaran sengaja datar supaya UI tidak perlu tahu apa-apa:
    ``{kode, skor, kelas, komponen[], peringatan}``.
    """
    if not hasil:
        return []
    # Skala ukuran ATS: pakai median lintas radar sebagai 'normal' — dihitung dari data
    # hari itu, tetapi hanya sebagai PEMBAGI; tiap baris mencatat pembaginya sendiri.
    ats_semua = sorted(
        float(h.get("ats_beli") or 0) for h in hasil if (h.get("ats_beli") or 0) > 0
    )
    median_ats = ats_semua[len(ats_semua) // 2] if ats_semua else 0.0

    keluaran: list[dict[str, Any]] = []
    for h in hasil:
        if str(h.get("status")) != "ok":
            continue
        kode = str(h.get("kode") or "?")
        ats_beli = float(h.get("ats_beli") or 0)
        ats_jual = float(h.get("ats_jual") or 0)
        frq_beli = float(h.get("frq_beli") or 0)
        frq_jual = float(h.get("frq_jual") or 0)

        rasio_ats = _bagian_rasio(ats_beli, ats_jual)
        rasio_frq = _bagian_rasio(frq_beli, frq_jual)
        no_sell = bool(h.get("no_sell"))
        # Ukuran ATS relatif radar: nilai penuh pada 1,5× median. Kalau radar terlalu
        # kecil (<3 emiten), komponen ini TIDAK informatif — dimatikan, bukan diberi
        # nilai penuh (temuan nyata 6 Okt: median-dari-satu membuat skor semua emiten
        # naik tanpa alasan).
        if median_ats > 0 and len(ats_semua) >= 3:
            ukuran = min(1.0, (ats_beli / median_ats) / 1.5)
            kontrib_ukuran = round(_BOBOT["ukuran_ats"] * ukuran, 3)
            catatan_ukuran = None
        else:
            ukuran = 0.0
            kontrib_ukuran = 0.0
            catatan_ukuran = "radar terlalu kecil — komponen ukuran ATS dimatikan"

        kontribusi = {
            "rasio_ats": round(_BOBOT["rasio_ats"] * (rasio_ats - 0.5) * 2, 3),
            "rasio_frq": round(_BOBOT["rasio_frq"] * (rasio_frq - 0.5) * 2, 3),
            "no_sell": _BOBOT["no_sell"] if no_sell else 0.0,
            "ukuran_ats": kontrib_ukuran,
        }
        # Basis 50 + kontribusi (positif/negatif), dijepit 0..100.
        mentah = 50.0 + sum(kontribusi.values())
        skor = int(round(max(0.0, min(100.0, mentah))))

        if skor >= 70:
            kelas = "AKUMULASI"
        elif skor >= 55:
            kelas = "CENDERUNG-BELI"
        elif skor > 45:
            kelas = "SEIMBANG"
        elif skor > 30:
            kelas = "CENDERUNG-JUAL"
        else:
            kelas = "DISTRIBUSI"

        keluaran.append(
            {
                "kode": kode,
                "skor": skor,
                "kelas": kelas,
                "rasio_ats_pct": round(rasio_ats * 100, 1),
                "rasio_frq_pct": round(rasio_frq * 100, 1),
                "no_sell": no_sell,
                "ukuran_relatif": round(ukuran, 2),
                "komponen": [
                    {"nama": k, "bobot": _BOBOT[k], "kontribusi": v}
                    for k, v in kontribusi.items()
                ],
                "catatan": [c for c in (catatan_ukuran,) if c],
                "peringatan": _PERINGATAN,
            }
        )

    keluaran.sort(key=lambda x: x["skor"], reverse=True)
    return keluaran


def skor_bandarmologi(bagian: dict[str, Any]) -> dict[str, Any]:
    """Skor untuk seluruh radar hari ini, dari ``bagian.bandarmologi`` snapshot."""
    bandar = (bagian or {}).get("bandarmologi") or {}
    hasil = bandar.get("hasil") or []
    skor = skor_dari_hasil(hasil)
    return {
        "tersedia": bool(skor),
        "alasan": None if skor else (bandar.get("error") or "belum ada broker summary pada snapshot"),
        "hari": bandar.get("hari"),
        "n_emiten": len(skor),
        "emiten": skor,
        "sumber": "bagian.bandarmologi (Arjum broker summary) — dihitung lokal, tanpa kuota tambahan",
        "metode": (
            "Skor 0–100 = basis 50 + kontribusi berbobot: rasio ATS beli (40), rasio "
            "frekuensi beli (30), bonus no-sell (20), ukuran ATS relatif median radar (10). "
            "Semua komponen diaudit di `komponen[]`."
        ),
    }
