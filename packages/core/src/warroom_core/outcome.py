"""Ekstraksi hasil pasar dari dataset recorder Poly (P1 lanjutan, 5 Okt 2026).

**Koreksi penting.** Sebelumnya dilaporkan "recorder tidak menulis outcome" — itu KELIRU.
Recorder memang memanggil Gamma (``gamma-api.polymarket.com/events?slug=<coin>-updown-5m-<wts>``)
dan merekam body-nya. Resolusinya ADA, tetapi terkubur di dalam body HTTP mentah:

    event.closed == true
    event.markets[].umaResolutionStatus == "resolved"
    event.markets[].outcomes == ["Up","Down"]
    event.markets[].outcomePrices == ["0","1"]   # harga 1 = hasil yang menang

Yang belum ada hanyalah **yang mengekstrak**-nya jadi label menang/kalah per keputusan.
Modul ini melakukan itu: baca `http` (gamma) + `decision` dari satu run paired, gabungkan
lewat kunci (coin, wts), dan hasilkan baris ber-label.

Tanpa langkah ini, gate tidak punya n/menang untuk dihitung — itulah yang menahan learner.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "REASON_LAYAK",
    "HasilPasar",
    "baca_hasil",
    "hanya_layak_dagang",
    "label_keputusan",
    "ringkas_dataset",
]

# Alasan keputusan yang berarti "strategi MEMANG mau masuk". Selain ini adalah keputusan
# yang DITOLAK strategi (di luar jendela, momentum kurang, buku kosong, …). Menghitung
# menang/kalah dari keputusan yang ditolak menghasilkan edge palsu yang besar: pada satu run
# produksi, keputusan yang ditolak menang 61-100%, sedangkan yang benar-benar layak
# (`quote_eligible`) hanya menang 14,8%. Gate yang memakai angka campuran itu akan
# meloloskan strategi yang sebenarnya rugi.
REASON_LAYAK = ("quote_eligible",)


@dataclass
class HasilPasar:
    """Satu resolusi pasar 5 menit."""

    slug: str
    coin: str
    wts: int
    menang: str          # "Up" | "Down"
    status: str          # "resolved" | lain
    teresolusi: bool


def _slug_ke_kunci(slug: str) -> tuple[str, int] | None:
    """`btc-updown-5m-1791158400` → ("btc", 1791158400)."""
    bagian = slug.split("-")
    if len(bagian) < 4 or bagian[1] != "updown" or bagian[2] != "5m":
        return None
    try:
        return bagian[0], int(bagian[3])
    except ValueError:
        return None


def _menang_dari_market(m: dict[str, Any]) -> str | None:
    """Ambil pemenang dari outcomes/outcomePrices (harga 1 = menang).

    Gamma mengirim kedua field ini sebagai STRING JSON (``'["Up", "Down"]'``), bukan array —
    jadi harus di-``json.loads`` dulu. Mengiterasi string mentah akan membaca per karakter
    dan selalu gagal (bug yang ditemukan saat menguji modul ini).
    """
    outcomes = m.get("outcomes")
    harga = m.get("outcomePrices")
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except json.JSONDecodeError:
            return None
    if isinstance(harga, str):
        try:
            harga = json.loads(harga)
        except json.JSONDecodeError:
            return None
    if not isinstance(outcomes, list) or not isinstance(harga, list) or not outcomes or not harga:
        return None
    try:
        angka = [float(x) for x in harga]
    except (TypeError, ValueError):
        return None
    if not angka:
        return None
    idx = angka.index(max(angka))
    # Wajib tegas: pemenang ~1, sisanya ~0. Pasar yang masih jalan (mis. 0.505/0.495) TIDAK
    # boleh dilabeli — itu akan mengarang hasil dan merusak gate.
    if angka[idx] < 0.95:
        return None
    return str(outcomes[idx])


def baca_hasil(path: str | Path, *, maks_baris: int | None = None) -> dict[tuple[str, int], HasilPasar]:
    """Pindai satu berkas events-*.jsonl(.gz); kembalikan hasil per (coin, wts).

    Hanya event ``kind == "http"`` yang URL-nya Gamma dan body-nya memuat market tertutup
    yang dipakai. Resolusi TERAKHIR untuk satu slug yang menang (data bisa berubah dari
    "belum" jadi "sudah" seiring waktu).
    """
    p = Path(path)
    pembuka = gzip.open if p.suffix == ".gz" else open
    hasil: dict[tuple[str, int], HasilPasar] = {}
    with pembuka(p, "rt", encoding="utf-8", errors="replace") as fh:  # type: ignore[operator]
        for i, baris in enumerate(fh):
            if maks_baris is not None and i >= maks_baris:
                break
            if "gamma-api" not in baris:
                continue
            try:
                e = json.loads(baris)
            except json.JSONDecodeError:
                continue
            if e.get("kind") != "http" or "gamma" not in str(e.get("url", "")):
                continue
            body = e.get("body")
            if not isinstance(body, list):
                continue
            for ev in body:
                if not isinstance(ev, dict):
                    continue
                slug = str(ev.get("slug") or "")
                kunci = _slug_ke_kunci(slug)
                if kunci is None:
                    continue
                for m in ev.get("markets") or []:
                    if not isinstance(m, dict):
                        continue
                    status = str(m.get("umaResolutionStatus") or "")
                    # Hanya pasar yang SUDAH selesai. Ini penjaga terpenting: label hasil
                    # dari pasar yang masih berjalan = mengarang data.
                    if not (m.get("closed") or status == "resolved"):
                        continue
                    menang = _menang_dari_market(m)
                    if menang is None:
                        continue
                    coin, wts = kunci
                    hasil[(coin, wts)] = HasilPasar(
                        slug=slug, coin=coin, wts=wts, menang=menang,
                        status=status, teresolusi=bool(m.get("closed")) or status == "resolved",
                    )
    return hasil


def label_keputusan(path: str | Path, hasil: dict[tuple[str, int], HasilPasar]) -> list[dict[str, Any]]:
    """Gabungkan keputusan (yang punya side+token) dengan hasil → baris ber-label.

    Satu keputusan dihitung MENANG bila `side`-nya sama dengan hasil pasar. Keputusan tanpa
    hasil (pasar belum selesai) DIBUANG, bukan dihitung seri — menebak di sini akan merusak
    gate.
    """
    p = Path(path)
    pembuka = gzip.open if p.suffix == ".gz" else open
    baris_keluar: list[dict[str, Any]] = []
    with pembuka(p, "rt", encoding="utf-8", errors="replace") as fh:  # type: ignore[operator]
        for baris in fh:
            if '"decision"' not in baris:
                continue
            try:
                e = json.loads(baris)
            except json.JSONDecodeError:
                continue
            if e.get("kind") != "decision":
                continue
            side = e.get("side")
            coin = str(e.get("coin") or "")
            wts = e.get("wts")
            if not side or not coin or not isinstance(wts, int):
                continue
            h = hasil.get((coin, wts))
            if h is None or not h.teresolusi:
                continue
            baris_keluar.append({
                "coin": coin,
                "wts": wts,
                "side": side,
                "menang": h.menang,
                "hasil": "menang" if side == h.menang else "kalah",
                "partition": e.get("partition"),
                "reason": e.get("reason"),
                "token": e.get("token"),
                "cadences": e.get("cadences"),
            })
    return baris_keluar


def hanya_layak_dagang(baris: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Saring ke keputusan yang strategi MEMANG mau masuk (lihat REASON_LAYAK).

    Ini penjaga terpenting modul ini. Tanpa saringan ini, keputusan yang sengaja ditolak
    strategi ikut terhitung dan menghasilkan win-rate palsu yang tinggi.
    """
    return [r for r in baris if str(r.get("reason")) in REASON_LAYAK]


def ringkas_dataset(root: str | Path, *, layak_saja: bool = True) -> dict[str, Any]:
    """Ringkas satu direktori run: berapa hasil terbaca, berapa keputusan bisa dilabeli.

    DUA LINTASAN — penting: resolusi datang SETELAH keputusannya, dan berkas dirotasi
    (411 berkas di satu run), jadi resolusi satu keputusan sering ada di berkas LAIN.
    Melabeli per-berkas (lintasan tunggal) menemukan nol pasangan.
    """
    d = Path(root)
    berkas = sorted(d.glob("events-*.jsonl*"))
    if not berkas:
        return {"error": f"tidak ada events-*.jsonl di {d}"}

    # Lintasan 1: kumpulkan SEMUA resolusi dulu.
    semua_hasil: dict[tuple[str, int], HasilPasar] = {}
    for b in berkas:
        semua_hasil.update(baca_hasil(b))

    # Lintasan 2: labeli keputusan dengan peta resolusi yang lengkap.
    semua_label: list[dict[str, Any]] = []
    for b in berkas:
        semua_label.extend(label_keputusan(b, semua_hasil))

    layak = hanya_layak_dagang(semua_label)
    dipakai = layak if layak_saja else semua_label

    per_partisi: dict[str, int] = {}
    per_hasil: dict[str, int] = {}
    per_reason: dict[str, dict[str, int]] = {}
    for r in semua_label:
        pr = per_reason.setdefault(str(r.get("reason")), {"menang": 0, "kalah": 0})
        pr[str(r.get("hasil"))] = pr.get(str(r.get("hasil")), 0) + 1
    for r in dipakai:
        per_partisi[str(r.get("partition"))] = per_partisi.get(str(r.get("partition")), 0) + 1
        per_hasil[str(r.get("hasil"))] = per_hasil.get(str(r.get("hasil")), 0) + 1
    _semua_menang = sum(v.get("menang", 0) for v in per_reason.values())
    _semua_total = sum(v.get("menang", 0) + v.get("kalah", 0) for v in per_reason.values())
    return {
        "root": str(d),
        "berkas": len(berkas),
        "hasil_pasar": len(semua_hasil),
        "keputusan_berlabel": len(dipakai),
        "keputusan_semua_alasan": len(semua_label),
        "layak_saja": layak_saja,
        "per_partisi": per_partisi,
        "per_hasil": per_hasil,
        "per_reason": per_reason,
        "menang": per_hasil.get("menang", 0),
        "kalah": per_hasil.get("kalah", 0),
        # win-rate mentah untuk SEMUA alasan — JANGAN dipakai gate (lihat REASON_LAYAK).
        "win_rate_palsu_semua_alasan": round(
            _semua_menang / max(1, _semua_total), 4
        ),
        "win_rate_layak": round(
            per_hasil.get("menang", 0)
            / max(1, per_hasil.get("menang", 0) + per_hasil.get("kalah", 0)),
            4,
        ),
    }
