"""Pencatat posisi LP — satu-satunya cara `LP vs hold` bisa dihitung.

Masalah yang dijawab: setiap klaim LP di media sosial ("+122%!") tidak bisa diaudit karena
tidak menyebut **harga masuk**, **harga keluar**, **jendela waktu**, atau **pembanding hold**.
Modul ini menyimpan keempatnya, sehingga pertanyaan "LP saya lebih baik daripada cuma
memegang tokennya?" punya jawaban angka — bukan kesan.

Desain:
- Berkas, bukan DB: `state/lp_positions.json`, append-only supaya jejaknya bisa diaudit.
- **Il == hold** artinya kenaikan **proporsi** kedua kaki sama (tidak butuh harga absolut).
  Ini kebetulan menguntungkan: kita bisa menghitung IL dari kuantitas saja — persis data
  yang bahkan tidak dipublikasikan poster klaim itu.
- Nilai absolut butuh harga; kalau harga tidak ada, tulis `belum diketahui`, jangan ditebak.
- Nilai dalam USD kalau ada `harga_usd_sol`, kalau tidak pakai hitungan SOL sebagai unit.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

NAMA_BERKAS = "lp_positions.json"


def _akar(state_dir: Path) -> Path:
    d = Path(state_dir)
    return d if d.is_dir() else d.parent


def _baca(state_dir: Path) -> list[dict[str, Any]]:
    p = _akar(state_dir) / NAMA_BERKAS
    try:
        isi = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return isi if isinstance(isi, list) else list(isi.get("posisi") or [])


def _tulis(state_dir: Path, baris: list[dict[str, Any]]) -> None:
    p = _akar(state_dir) / NAMA_BERKAS
    p.write_text(json.dumps(baris, ensure_ascii=False, indent=1), encoding="utf-8")


def _angka(v: Any) -> float | None:
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def kunci_pool(rantai: str, alamat: str) -> str:
    return f"{rantai}:{alamat}".lower()


def catat_masuk(
    state_dir: Path,
    *,
    rantai: str,
    alamat_pool: str,
    pasangan: str,
    jumlah_base: float,
    jumlah_quote: float,
    harga_usd_base: float | None = None,
    harga_usd_quote: float | None = None,
    dex: str | None = None,
    label_pool: str | None = None,
    catatan: str | None = None,
    waktu: float | None = None,
) -> dict[str, Any]:
    """Catat pembukaan posisi LP. Wajib menyebut KEDUA kaki.

    Kalau salah satu kuantitas ≤ 0 → tolak. Bukan kegagalan teknis: LP tanpa kedua kaki
    tidak bisa dihitung, dan mencatatnya setengah-setengah justru menciptakan angka palsu.
    """
    jb, jq = _angka(jumlah_base), _angka(jumlah_quote)
    if jb is None or jq is None or jb <= 0 or jq <= 0:
        raise ValueError("kedua kaki posisi LP harus terisi dan > 0 (base & quote)")

    pos = {
        "pool": kunci_pool(rantai, alamat_pool),
        "rantai": rantai,
        "alamat_pool": alamat_pool,
        "pasangan": pasangan,
        "dex": dex,
        "label_pool": label_pool,
        "masuk_ts": time.time() if waktu is None else waktu,
        "masuk_base": jb,
        "masuk_quote": jq,
        "masuk_harga_base": _angka(harga_usd_base),
        "masuk_harga_quote": _angka(harga_usd_quote),
        "keluar_ts": None,
        "keluar_base": None,
        "keluar_quote": None,
        "keluar_harga_base": None,
        "keluar_harga_quote": None,
        "catatan": catatan,
    }
    baris = _baca(state_dir)
    baris.append(pos)
    _tulis(state_dir, baris)
    return pos


def _cari(baris: list[dict[str, Any]], pool: str) -> dict[str, Any] | None:
    for r in reversed(baris):
        if r.get("pool") == pool.lower() and r.get("keluar_ts") is None:
            return r
    return None


def catat_keluar(
    state_dir: Path,
    *,
    rantai: str,
    alamat_pool: str,
    jumlah_base: float,
    jumlah_quote: float,
    harga_usd_base: float | None = None,
    harga_usd_quote: float | None = None,
    waktu: float | None = None,
) -> dict[str, Any]:
    """Tutup posisi LP yang masih terbuka untuk pool ini."""
    pool = kunci_pool(rantai, alamat_pool)
    baris = _baca(state_dir)
    pos = _cari(baris, pool)
    if pos is None:
        raise ValueError(f"tidak ada posisi LP terbuka untuk pool {pool}")
    jb, jq = _angka(jumlah_base), _angka(jumlah_quote)
    if jb is None or jq is None:
        raise ValueError("kedua kaki keluar harus angka")
    pos.update(
        {
            "keluar_ts": time.time() if waktu is None else waktu,
            "keluar_base": jb,
            "keluar_quote": jq,
            "keluar_harga_base": _angka(harga_usd_base),
            "keluar_harga_quote": _angka(harga_usd_quote),
        }
    )
    _tulis(state_dir, baris)
    return pos


def _hitung(pos: dict[str, Any], harga_quote_usd: float | None = None) -> dict[str, Any]:
    """Inti perhitungan: rasio + IL == hold. Tidak pernah menebak yang tidak diketahui."""
    b0, q0 = _angka(pos.get("masuk_base")), _angka(pos.get("masuk_quote"))
    b1, q1 = _angka(pos.get("keluar_base")), _angka(pos.get("keluar_quote"))
    if b0 is None or q0 is None or b1 is None or q1 is None or b0 <= 0 or q0 <= 0:
        return {"status": "terbuka" if pos.get("keluar_ts") is None else "data-kurang"}

    # Kenaikan proporsi tiap kaki. IL == hold tepat ketika rasio kedua kaki sama —
    # jadi kenaikan proporsi sama artinya tidak ada rugi dibanding cuma memegang.
    kaki_base = b1 / b0
    kaki_quote = q1 / q0

    harga_masuk_b = _angka(pos.get("masuk_harga_base"))
    harga_masuk_q = _angka(pos.get("masuk_harga_quote"))
    harga_keluar_b = _angka(pos.get("keluar_harga_base"))
    harga_keluar_q = _angka(pos.get("keluar_harga_quote"))

    min_kaki = min(kaki_base, kaki_quote)
    imbalance = (
        round(max(kaki_base, kaki_quote) / min_kaki, 5)
        if min_kaki > 0
        else None
    )

    hasil: dict[str, Any] = {
        "status": "tertutup",
        "kenaikan_base_pct": round((kaki_base - 1) * 100, 3),
        "kenaikan_quote_pct": round((kaki_quote - 1) * 100, 3),
        "selisih_kaki_pp": round((kaki_base - kaki_quote) * 100, 3),
        # Kedua kaki naik = tanda kuat fee masuk (bukan cuma harga bergerak).
        "jumlah_kedua_kaki_naik": kaki_base > 1.0 and kaki_quote > 1.0,
        "imbalance": imbalance,
        "catatan": ["nilai absolut butuh harga; yang tidak diketahui tidak ditebak"],
    }

    punya = (harga_masuk_b, harga_masuk_q, harga_keluar_b, harga_keluar_q)
    if all(h is not None for h in punya):
        hmb, hmq, hkb, hkq = punya  # type: ignore[misc]
        v0 = b0 * hmb + q0 * hmq  # type: ignore[operator]
        v1 = b1 * hkb + q1 * hkq  # type: ignore[operator]
        hold = b0 * hkb + q0 * hkq  # type: ignore[operator]
        if v0 > 0:
            hasil.update(
                {
                    "unit": "USD",
                    "nilai_masuk_usd": round(v0, 4),
                    "nilai_keluar_usd": round(v1, 4),
                    "nilai_hold_usd": round(hold, 4),
                    "return_lp_pct": round((v1 / v0 - 1) * 100, 3),
                    "return_hold_pct": round((hold / v0 - 1) * 100, 3),
                    "lp_vs_hold_usd": round(v1 - hold, 4),
                    "lp_vs_hold_pp": round((v1 - hold) / v0 * 100, 3),
                    "menang": "LP" if v1 > hold else ("hold" if hold > v1 else "seri"),
                }
            )
            hasil["catatan"] = ["LP vs hold dihitung dari harga masuk & keluar yang dicatat"]
        else:
            hasil["catatan"] = ["nilai masuk non-positif, metrik relatif dilewati"]
    else:
        # Tanpa harga: tetap bisa menjawab IL vs hold lewat imbal hasil tertimbang
        # modal awal (bukan sekadar jumlah token, yang selalu terlihat naik).
        #   il_vs_hold = imbal hasil tertimbang − imbal hasil hold-murni
        w_b = (b0 / (b0 + q0)) if (b0 + q0) else 0.0
        w_q = 1.0 - w_b
        r_tertimbang = w_b * (kaki_base - 1) + w_q * (kaki_quote - 1)
        r_hold = 0.5 * (kaki_base - 1) + 0.5 * (kaki_quote - 1)
        hasil.update(
            {
                "unit": "rasio (tanpa harga)",
                "imbal_hasil_tertimbang_pct": round(r_tertimbang * 100, 3),
                "imbal_hasil_hold_pct": round(r_hold * 100, 3),
                "il_vs_hold_pct": round((r_tertimbang - r_hold) * 100, 3),
                "menang": "LP" if r_tertimbang > r_hold else ("hold" if r_hold > r_tertimbang else "seri"),
                "catatan": [
                    "komposisi masuk dipakai sebagai bobot (bukan 50/50) supaya tidak menebak",
                    "dinyatakan sebagai selisih imbal hasil, bukan USD (harga belum lengkap)",
                ],
            }
        )
        if harga_quote_usd:
            hasil["harga_quote_usd_dipakai"] = round(float(harga_quote_usd), 4)
    return hasil


def laporan(state_dir: Path, harga_quote_usd: float | None = None) -> dict[str, Any]:
    """Ringkas semua posisi + yang terbuka, untuk ditampilkan di panel."""
    baris = _baca(state_dir)
    kini = time.time()
    keluar_ = [dict(p, hitung=_hitung(p, harga_quote_usd)) for p in baris if p.get("keluar_ts")]
    buka = []
    for p in baris:
        if p.get("keluar_ts"):
            continue
        umur = (kini - float(p.get("masuk_ts") or kini)) / 3600
        buka.append({**p, "umur_jam": round(umur, 1)})

    return {
        "jumlah": len(baris),
        "terbuka": len(buka),
        "tertutup": len(keluar_),
        "posisi_terbuka": buka[-10:],
        "riwayat": keluar_[-10:],
    }


def dari_lp_cari(baris_ukur: dict[str, Any]) -> dict[str, Any]:
    """Ubah satu hasil `dexscreen.lp_cari` jadi rujukan posisi (untuk catat_masuk).

    Memisahkan dengan tegas: yang ini DISKUSI (potensi fee dari data pool), bukan posisi nyata.
    """
    return {
        "rantai": baris_ukur.get("rantai"),
        "alamat_pool": baris_ukur.get("alamat"),
        "pasangan": baris_ukur.get("pair"),
        "dex": baris_ukur.get("dex"),
        "label_pool": baris_ukur.get("label_pool"),
    }
