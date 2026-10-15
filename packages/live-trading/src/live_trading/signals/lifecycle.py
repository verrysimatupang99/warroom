"""Status daur hidup setup per strategi — Waiting -> In Area -> Running -> TP/SL.

Menjawab "setup tiap strategi sekarang di tahap mana" dari bahan yang SUDAH ada,
tanpa berkas baru:

- baris ``state/verdicts.jsonl`` — ts, pair, direction, entry/sl/tp1, poi, ``strategy``;
- candle 1H (rentang low/high per candle) untuk status LIVE saat ini;
- keluaran ``measure.outcomes`` (kalau ada) untuk kandidat yang sudah diselesaikan.

Pemisahan per strategi adalah syarat, bukan tambahan: status digabung lintas strategi
akan menyembunyikan bahwa satu strategi belum pernah keluar dari WAITING sementara
strategi lain sudah TP/SL — persis perbandingan yang jadi tujuan War Room.

Aturan (sama konservatifnya dengan ``measure``):

- SL menang atas TP bila keduanya tersentuh di jendela yang sama.
- Jendela tunggu 8 jam → ``EXPIRED`` bila tidak terisi; tahan maksimum 24 jam setelah
  terisi → ``EXPIRED`` juga (beda alasan).
- Tanpa level/harga yang valid → ``None`` + alasan "tidak ada bahan penilaian",
  bukan status karangan.

Modul baca-saja: tidak menulis berkas, tidak memanggil jaringan sendiri.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from warroom_core.strategy_lifecycle import LABEL_STATUS, SetupStatus, status_dari, status_dari_harga

__all__ = [
    "FILL_WINDOW_H",
    "HOLD_MAX_H",
    "nilai_baris",
    "ringkas_per_strategi",
    "status_dari_outcome",
    "status_live",
    "strategi_baris",
]

# Jendela yang sama dengan measure.py — kalau berbeda, dua pembacaan status akan
# saling bertentangan dan perbandingan antar strategi kehilangan dasarnya.
FILL_WINDOW_H = 8
HOLD_MAX_H = 24

STRATEGI_BAWAAN = "legacy-smc"  # baris lama tanpa field strategy = proposal SMC lama


def strategi_baris(row: Mapping[str, Any]) -> str:
    """Nama strategi dari baris verdict; baris lama tanpa field = proposal SMC lama."""
    return str(row.get("strategy") or STRATEGI_BAWAAN)


def _angka(nilai: Any) -> float | None:
    try:
        return float(nilai) if nilai is not None else None
    except (TypeError, ValueError):
        return None


def _waktu(iso: Any) -> dt.datetime | None:
    if not iso:
        return None
    try:
        t = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.UTC)


def _candles(klines: Sequence[Sequence[Any]]) -> list[tuple[int, float, float, float]]:
    """(waktu_ms, high, low, close) dari array kline Binance; baris rusak dilewati."""
    out: list[tuple[int, float, float, float]] = []
    for k in klines:
        try:
            out.append((int(k[0]), float(k[2]), float(k[3]), float(k[4])))
        except (IndexError, TypeError, ValueError):
            continue
    return out


def status_live(
    row: Mapping[str, Any],
    klines: Sequence[Sequence[Any]],
    *,
    sekarang: dt.datetime | None = None,
) -> SetupStatus | None:
    """Status setup dari baris verdict + candle 1H sejak verdict (walk per candle).

    ``klines`` wajib dimulai dari waktu verdict — kontrak yang sama dengan
    ``measure.outcomes``. Candle dievaluasi berurutan supaya urutan fill → hasil
    dihormati; di dalam satu candle aturan konservatif tetap berlaku (SL menang).
    """
    ts = _waktu(row.get("ts"))
    entry, sl, tp1 = _angka(row.get("entry")), _angka(row.get("sl")), _angka(row.get("tp1"))
    if ts is None or entry is None or sl is None or tp1 is None:
        return None
    arah = str(row.get("direction") or "")
    zona_low, zona_high = _angka(row.get("poi_low")), _angka(row.get("poi_high"))
    candles = _candles(klines)
    if not candles:
        return None
    now = sekarang or dt.datetime.now(dt.UTC)

    status = "WAITING"
    waktu_isi_jam: float | None = None
    for t_ms, high, low, close in candles:
        jam_candle = (dt.datetime.fromtimestamp(t_ms / 1000, tz=dt.UTC) - ts).total_seconds() / 3600
        if status in {"WAITING", "IN_AREA"} and jam_candle >= FILL_WINDOW_H:
            return status_dari(
                lama=status,
                baru="EXPIRED",
                alasan=f"tidak terisi dalam {FILL_WINDOW_H} jam sejak verdict",
            )
        if status == "RUNNING" and waktu_isi_jam is not None and jam_candle - waktu_isi_jam >= HOLD_MAX_H:
            # Batas tahan dipotong per candle, sama dengan measure: TP/SL di luar jendela
            # tahan tidak dihitung — kalau dihitung, hasil akan lebih bagus dari kenyataan.
            return status_dari(
                lama="RUNNING",
                baru="EXPIRED",
                alasan=f"terisi, tetapi lewat batas tahan {HOLD_MAX_H} jam tanpa TP/SL",
            )
        hasil = status_dari_harga(
            arah=arah,
            entry=entry,
            sl=sl,
            tp1=tp1,
            harga=close,
            zona_low=zona_low,
            zona_high=zona_high,
            harga_min=low,
            harga_max=high,
            dimulai_dari=status,
        )
        if hasil is None:
            return None
        status = hasil.status
        if status == "RUNNING" and waktu_isi_jam is None:
            waktu_isi_jam = jam_candle
        if status in {"TP", "SL"}:
            return hasil

    umur_jam = (now - ts).total_seconds() / 3600
    if status in {"WAITING", "IN_AREA"} and umur_jam >= FILL_WINDOW_H:
        return status_dari(
            lama=status,
            baru="EXPIRED",
            alasan=f"tidak terisi dalam {FILL_WINDOW_H} jam sejak verdict",
        )
    if status == "RUNNING":
        # Batas tahan sudah ditegakkan per candle di dalam loop; di sini hanya sisa
        # yang masih berjalan (jam sejak isi selalu < HOLD_MAX_H saat mencapai titik ini).
        isi_txt = f"jam {int(waktu_isi_jam)}" if waktu_isi_jam is not None else "waktu tak tercatat"
        return SetupStatus(
            status="RUNNING",
            alasan=f"posisi terisi ({isi_txt} sejak verdict); belum ada level hasil tersentuh",
            harga=candles[-1][3],
            di_zona=True,
            terisi=True,
        )
    return _belum_selesai(status, candles[-1][3])


def _belum_selesai(status: str, harga: float) -> SetupStatus:
    """Status akhir walk saat kandidat masih menunggu — belum selesai, bukan gagal."""
    return SetupStatus(
        status=status,
        alasan=(
            "harga belum mencapai zona entry; jendela tunggu belum habis"
            if status == "WAITING"
            else "harga di zona entry, menunggu terisi (jendela tunggu belum habis)"
        ),
        harga=harga,
        di_zona=status == "IN_AREA",
    )


def status_dari_outcome(outcome: Mapping[str, Any] | None) -> SetupStatus | None:
    """Status dari hasil pelacakan ``measure`` (kalau kandidat sudah diselesaikan).

    Hanya hasil DEFINITIF yang dipakai (tp1/sl/tidak_terisi/kedaluwarsa); status yang
    masih berjalan (``menunggu_terisi``/``terbuka``) dikembalikan ``None`` supaya
    pemanggil menilai dari harga terkini dengan ``status_live`` — bukan dari hasil
    yang belum ada. Hasil yang tidak bisa dinilai (data hilang) juga ``None``.
    """
    if not outcome:
        return None
    hasil = str(outcome.get("hasil") or "")
    if hasil == "tp1":
        return SetupStatus(status="TP", alasan="pelacakan measure: TP1 kena", terisi=True)
    if hasil == "sl":
        return SetupStatus(status="SL", alasan="pelacakan measure: SL kena", terisi=True)
    if hasil == "terbuka":
        return SetupStatus(
            status="RUNNING", alasan="pelacakan measure: posisi terbuka (mark terakhir)", terisi=True
        )
    if hasil == "tidak_terisi":
        return SetupStatus(
            status="EXPIRED",
            alasan=f"pelacakan measure: tidak terisi dalam {FILL_WINDOW_H} jam",
        )
    if hasil == "kedaluwarsa":
        return SetupStatus(
            status="EXPIRED", alasan=f"pelacakan measure: lewat batas tahan {HOLD_MAX_H} jam"
        )
    return None


def nilai_baris(
    row: Mapping[str, Any],
    *,
    klines: Sequence[Sequence[Any]] | None = None,
    outcome: Mapping[str, Any] | None = None,
    sekarang: dt.datetime | None = None,
) -> dict[str, Any]:
    """Status satu baris verdict, siap dikirim ke ringkasan/UI.

    Prioritas: hasil definitif ``measure`` > status harga live > n/a + alasan.
    Field ``sumber`` menuliskan mana yang dipakai, supaya pembaca tidak menebak.
    """
    st_outcome = status_dari_outcome(outcome)
    st_live = status_live(row, klines or [], sekarang=sekarang) if klines else None
    pilih = st_outcome or st_live
    return {
        "strategi": strategi_baris(row),
        "pair": row.get("pair"),
        "ts": row.get("ts"),
        "arah": str(row.get("direction") or "").upper() or None,
        "entry": row.get("entry"),
        "sl": row.get("sl"),
        "tp1": row.get("tp1"),
        "status": pilih.status if pilih else None,
        "label": LABEL_STATUS[pilih.status] if pilih else None,
        "alasan": pilih.alasan if pilih else "tidak ada bahan penilaian (klines/outcome kosong)",
        "harga": pilih.harga if pilih else None,
        "sumber": "measure" if st_outcome else ("harga" if st_live else None),
    }


def ringkas_per_strategi(daftar: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Ringkas daftar status (keluaran ``nilai_baris``) TERPISAH per strategi.

    Tiap strategi mendapat: jumlah baris, jumlah yang berstatus, sebaran status, dan
    setup terakhir (baris paling baru, dengan statusnya). Baris tanpa status dihitung
    terpisah — tidak dilebur jadi WAITING supaya tidak menambah angka palsu.
    """
    keluar: dict[str, dict[str, Any]] = {}
    for baris in daftar:
        nama = str(baris.get("strategi") or STRATEGI_BAWAAN)
        slot = keluar.setdefault(
            nama,
            {"jumlah": 0, "berstatus": 0, "tanpa_status": 0, "sebaran": {}, "terakhir": None},
        )
        slot["jumlah"] += 1
        status = baris.get("status")
        if status:
            slot["berstatus"] += 1
            slot["sebaran"][status] = slot["sebaran"].get(status, 0) + 1
        else:
            slot["tanpa_status"] += 1
        ts = str(baris.get("ts") or "")
        terakhir_ts = str((slot["terakhir"] or {}).get("ts") or "")
        if slot["terakhir"] is None or ts > terakhir_ts:
            slot["terakhir"] = dict(baris)
    return keluar
