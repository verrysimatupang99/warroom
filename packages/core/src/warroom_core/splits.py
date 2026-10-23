"""Membekukan split data (ADR-003) — P1 roadmap 5 Okt 2026.

Masalah yang diselesaikan: gate sudah menolak ``split`` yang bukan ``frozen:<id>``, tapi
tidak ada mekanisme yang membuat id itu benar-benar beku. Siapa pun bisa menulis
``frozen:apa-saja`` setelah melihat hasil. Modul ini:

1. **Membekukan** daftar berkas + sha256 + manifest_hash dari satu run dataset menjadi
   baris ``frozen_splits`` (append-only). Id yang dihasilkan dipakai gate.
2. **Memverifikasi** bahwa berkas di disk masih cocok dengan yang dibekukan.

Batas jujur yang dikodekan di sini: recorder Poly menulis partisi
(``development``/``embargo``/``holdout``) tetapi **tidak** menulis hasil/resolusi pasar.
Tanpa outcome, "menang/kalah" tidak bisa dihitung dari dataset ini. Karena itu
``bekukan`` menolak split yang tidak punya penanda outcome — lebih baik menolak daripada
membuat split kosong yang terlihat sah.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as SASession

from warroom_core.db import Event, FrozenSplit

__all__ = [
    "OUTCOME_MARKERS",
    "bekukan",
    "daftar",
    "split_untuk_gate",
    "verifikasi",
]

# Penanda bahwa sebuah baris memuat HASIL (menang/kalah), bukan sekadar keputusan.
#
# Koreksi 23 Okt 2026: sebelumnya di sini tertulis "recorder tidak menulis outcome".
# Itu KELIRU. Rekaman memang memuat resolusi, tetapi dengan nama field `closed` milik
# Gamma API — dan `closed` tidak ada di daftar penanda, sehingga deteksi buta.
# Terukur pada run auto-20261023t105826z: 168 slug 5-menit, 152 di antaranya
# `"closed": true` (resolusi final). Karena itu penandanya sekarang mencakup `closed`.
#
# PENTING: `"closed": false` berarti market BELUM selesai, jadi tidak boleh dianggap
# outcome. Karena itu `_scan_outcome` hanya menerima `closed` bernilai true.
OUTCOME_MARKERS = ("outcome", "resolved", "resolution", "result", "won", "payout", "closed")


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for blok in iter(lambda: fh.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def _scan_outcome(path: Path) -> tuple[bool, int]:
    """Cari penanda outcome di berkas jsonl(.gz). Kembalikan (ada, total_baris).

    Selain mencocokkan nama penanda, `closed` hanya dihitung bila nilainya true:
    market yang belum selesai (`"closed": false`) TIDAK boleh membuat sebuah run
    dianggap punya outcome. Tanpa aturan ini, setiap baris market running akan
    meloloskan split padahal belum ada hasil apa pun.
    """
    import gzip

    pembuka = gzip.open if path.suffix == ".gz" else open
    dibaca = 0
    ada = False
    try:
        with pembuka(path, "rt", encoding="utf-8", errors="replace") as fh:  # type: ignore[operator]
            for baris in fh:
                dibaca += 1
                if ada:
                    continue
                if '"closed"' in baris:
                    # Hanya `closed` bernilai true yang dihitung sebagai resolusi.
                    if '"closed": true' in baris or '"closed":true' in baris:
                        ada = True
                        continue
                    # Baris berisi closed:false saja tidak membuktikan apa pun;
                    # tetap periksa penanda lain di baris yang sama.
                if any(f'"{m}"' in baris for m in OUTCOME_MARKERS if m != "closed"):
                    ada = True
    except (OSError, EOFError):
        return ada, dibaca
    return ada, dibaca


def bekukan(
    s: SASession,
    *,
    dataset: str,
    root: str | Path,
    created_by: str = "system",
    require_outcome: bool = True,
) -> dict[str, Any]:
    """Bekukan satu direktori dataset menjadi ``frozen_splits``.

    ``require_outcome=True`` (bawaan) menolak membekukan bila tidak ada penanda hasil di
    berkas mana pun — supaya split yang tak bisa dinilai tidak pernah terlihat sah.
    Kembalikan ringkasan; ``split`` di dalamnya dipakai gate sebagai ``frozen:<id>``.
    """
    d = Path(root)
    if not d.is_dir():
        raise FileNotFoundError(f"dataset tidak ada: {d}")

    manifest = {}
    mpath = d / "manifest.json"
    if mpath.is_file():
        try:
            manifest = json.loads(mpath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            manifest = {}

    berkas: list[dict[str, Any]] = []
    ada_outcome = False
    total_baris = 0
    for p in sorted(d.glob("events-*.jsonl*")):
        ok, n_baris = _scan_outcome(p)
        ada_outcome = ada_outcome or ok
        total_baris += n_baris
        berkas.append({"file": p.name, "sha256": _sha256_file(p), "bytes": p.stat().st_size})

    if not berkas:
        raise ValueError(f"tidak ada berkas events-*.jsonl di {d}")

    if require_outcome and not ada_outcome:
        raise ValueError(
            "dataset tidak memuat penanda hasil (outcome/resolved/won/payout) — "
            "split ini TIDAK BISA dinilai, jadi tidak dibekukan. Recorder perlu "
            "menulis resolusi pasar lebih dulu (lihat docs/belajar/split-beku-2026-10-05.md)."
        )

    sid = f"{dataset}-{uuid.uuid4().hex[:12]}"
    partisi = manifest.get("partition") or {}
    wf = partisi.get("firstFullWindow")
    hs = partisi.get("holdoutStart")

    def to_dt(ms: object) -> datetime | None:
        return datetime.fromtimestamp(ms, tz=UTC) if isinstance(ms, (int, float)) else None

    baris = FrozenSplit(
        id=sid,
        dataset=dataset,
        source=str(d),
        files_json=berkas,
        manifest_hash=str(manifest.get("codeHashes") and hashlib.sha256(
            json.dumps(manifest.get("codeHashes"), sort_keys=True).encode()
        ).hexdigest() or ""),
        partitions_json=partisi,
        window_from=to_dt(wf),
        window_to=to_dt(hs),
        rows=total_baris,
        created_by=created_by,
    )
    s.add(baris)
    s.add(
        Event(
            type="dataset.frozen",
            actor=created_by,
            payload_json={
                "split": f"frozen:{sid}",
                "dataset": dataset,
                "files": len(berkas),
                "manifest_hash": baris.manifest_hash,
                "partitions": partisi,
            },
            fact_ids=[],
            severity="warning",  # keputusan yang mengikat: layak terlihat
        )
    )
    s.flush()
    return {
        "split": f"frozen:{sid}",
        "id": sid,
        "dataset": dataset,
        "files": len(berkas),
        "ada_outcome": ada_outcome,
        "partitions": partisi,
    }


def daftar(s: SASession, *, dataset: str | None = None) -> list[dict[str, Any]]:
    """Daftar split beku (terbaru dulu)."""
    q = select(FrozenSplit).order_by(FrozenSplit.created_at.desc()).limit(200)
    if dataset:
        q = q.where(FrozenSplit.dataset == dataset)
    return [
        {
            "id": r.id,
            "split": f"frozen:{r.id}",
            "dataset": r.dataset,
            "files": len(r.files_json or []),
            "manifest_hash": r.manifest_hash,
            "partitions": r.partitions_json,
            "created_by": r.created_by,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in s.scalars(q).all()
    ]


def verifikasi(s: SASession, split_id: str) -> dict[str, Any]:
    """Cek berkas di disk masih cocok dengan yang dibekukan (sha256)."""
    sid = split_id.removeprefix("frozen:")
    r = s.get(FrozenSplit, sid)
    if r is None:
        return {"ada": False, "cocok": False, "detail": f"split {sid} tidak terdaftar"}
    d = Path(r.source)
    beda: list[str] = []
    hilang: list[str] = []
    for b in r.files_json or []:
        p = d / str(b.get("file"))
        if not p.is_file():
            hilang.append(str(b.get("file")))
        elif _sha256_file(p) != b.get("sha256"):
            beda.append(str(b.get("file")))
    return {
        "ada": True,
        "cocok": not beda and not hilang,
        "hilang": hilang,
        "berubah": beda,
        "files": len(r.files_json or []),
        "detail": (
            "berkas cocok dengan yang dibekukan"
            if not beda and not hilang
            else "dataset berubah sejak dibekukan"
        ),
    }


def split_untuk_gate(s: SASession, split_id: str) -> str | None:
    """Kembalikan ``frozen:<id>`` HANYA bila id terdaftar dan berkasnya masih cocok.

    Dipakai pemanggil yang ingin mengisi ``evidence["split"]`` tanpa mengarang label.

    Sebelumnya fungsi ini hanya memeriksa "terdaftar", sehingga split yang datasetnya
    sudah hilang/berubah tetap diloloskan ke gate — padahal justru itu yang ingin
    dicegah ADR-003. Ditemukan 23 Okt 2026: split ``poly-paired-131d1ab4aed5``
    melaporkan 411 berkas HILANG dari disk, tetapi tetap menghasilkan
    ``frozen:poly-paired-131d1ab4aed5``. Sekarang verifikasi ikut dijalankan;
    dataset yang tidak utuh menghasilkan ``None`` (arah aman: gate menolak).
    """
    sid = split_id.removeprefix("frozen:")
    r = s.get(FrozenSplit, sid)
    if r is None:
        return None
    if not verifikasi(s, sid).get("cocok"):
        return None
    return f"frozen:{sid}"


def split_terverifikasi_terbaru(s: SASession, dataset: str) -> str | None:
    """``frozen:<id>`` terbaru untuk dataset ini, HANYA bila berkasnya masih cocok.

    Dipakai learner: ia boleh memasang split ke buktinya kalau split itu ada dan masih
    utuh. Bila dataset sudah berubah sejak dibekukan, split itu tidak lagi sah — kembalikan
    ``None`` supaya gate tetap menolak (arah aman).
    """
    q = (
        select(FrozenSplit)
        .where(FrozenSplit.dataset == dataset)
        .order_by(FrozenSplit.created_at.desc())
        .limit(5)
    )
    for r in s.scalars(q).all():
        if verifikasi(s, r.id).get("cocok"):
            return f"frozen:{r.id}"
    return None
