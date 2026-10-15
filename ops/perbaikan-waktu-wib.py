#!/usr/bin/env python3
"""Koreksi LABEL zona waktu pada data lama yang ditulis `_now_wib()`.

Konteks (temuan QA 15 Okt 2026, High):
    `_now_wib()` di `execution/paper.py` & `equity.py` dulu menulis jam WIB
    (+7) tetapi dengan offset `+00:00`. String itu BERBOHONG soal zona:
    - feed memakai `created_at` DB (benar) → menampilkan 09.30 WIB;
    - /riset mempercayai label dan mengonversi → menampilkan 16.30 WIB.
    Satu trade tampil beda 7 jam antar panel.

Bukti bahwa jam-nya memang WIB (bukan UTC):
    trade INJUSDT payload `closed_at=2026-10-15T05:28:44+00:00` ditulis pada
    event `created_at=2026-10-14 22:28:41+00:00` (UTC). 22:28 UTC + 7 = 05:28 WIB
    → jam-nya WIB, hanya labelnya salah. Maka koreksi = GANTI OFFSET, bukan geser jam.

Yang dikoreksi (hanya baris yang TERBUKTI dari penulis lama):
    1. `state/crypto_equity.jsonl` — baris `source=paper-crypto` ber-offset `+00:00`.
       Baris `rekonsiliasi` memakai UTC asli (jangan disentuh); `watchlist-sync`
       sudah `+07:00`.
    2. `state/paper_positions.json` — `opened_at`/`updated_at` ber-offset `+00:00`.
    3. `--db`: payload `events` tipe `trade.*` (closed_at/opened_at) — dengan
       cadangan payload lama ke berkas JSON sebelum UPDATE.

Aman & reversibel:
    - dry-run default menampilkan rencana;
    - setiap berkas dicadangkan ke `state/arsip/koreksi-waktu-<stamp>/` SEBELUM diubah;
    - perubahan = penggantian literal `+00:00` → `+07:00` pada field waktu yang
      terbukti; tidak ada jam yang digeser, tidak ada baris ditambah/dihapus.

Pakai:
    python ops/perbaikan-waktu-wib.py --dry-run
    python ops/perbaikan-waktu-wib.py --ya            # berkas saja
    python ops/perbaikan-waktu-wib.py --ya --db       # + payload events
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
from pathlib import Path

LEDGER = "crypto_equity.jsonl"
POSISI = "paper_positions.json"
# Sumber yang JELAS dari penulis lama `_now_wib()` (jam WIB salah label).
SUMBER_WIB_SALAH = {"paper-crypto", "paper", "paper-idx", "paper-forex", "paper-gmgn"}
STAMP_FMT = "%Y%m%dT%H%M%SZ"


def _state_dir() -> Path:
    env = os.environ.get("WARROOM_DOMAIN_HOME")
    base = Path(env) if env else Path.home() / "live-trading"
    return base / "state"


def _stamp() -> str:
    return dt.datetime.now(dt.UTC).strftime(STAMP_FMT)


def _perbaiki_ledger(path: Path) -> list[dict]:
    """Kembalikan daftar perubahan (indeks, sebelum, sesudah). Tidak menulis."""
    if not path.is_file():
        return []
    ubah: list[dict] = []
    for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines()):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except json.JSONDecodeError:
            continue
        ca = str(d.get("closed_at") or "")
        if ca.endswith("+00:00") and str(d.get("source")) in SUMBER_WIB_SALAH:
            ubah.append(
                {
                    "i": i,
                    "signal_id": d.get("signal_id"),
                    "sebelum": ca,
                    "sesudah": ca[:-6] + "+07:00",
                }
            )
    return ubah


def _perbaiki_posisi(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    ubah: list[dict] = []
    for kunci in ("updated_at",):
        v = str(d.get(kunci) or "")
        if v.endswith("+00:00"):
            ubah.append({"field": kunci, "sebelum": v, "sesudah": v[:-6] + "+07:00"})
    for p in d.get("positions") or []:
        v = str(p.get("opened_at") or "")
        if v.endswith("+00:00"):
            ubah.append(
                {
                    "field": f"positions[{p.get('signal_id')}].opened_at",
                    "sebelum": v,
                    "sesudah": v[:-6] + "+07:00",
                }
            )
    return ubah


def _terapkan_ledger(path: Path) -> int:
    baris = path.read_text(encoding="utf-8").splitlines()
    n = 0
    for i, ln in enumerate(baris):
        if not ln.strip():
            continue
        try:
            d = json.loads(ln)
        except json.JSONDecodeError:
            continue
        ca = str(d.get("closed_at") or "")
        if ca.endswith("+00:00") and str(d.get("source")) in SUMBER_WIB_SALAH:
            d["closed_at"] = ca[:-6] + "+07:00"
            baris[i] = json.dumps(d, ensure_ascii=False)
            n += 1
    tmp = path.with_suffix(".jsonl.tmp")
    tmp.write_text("\n".join(baris) + "\n", encoding="utf-8")
    tmp.replace(path)
    return n


def _terapkan_posisi(path: Path) -> int:
    d = json.loads(path.read_text(encoding="utf-8"))
    n = 0
    for kunci in ("updated_at",):
        v = str(d.get(kunci) or "")
        if v.endswith("+00:00"):
            d[kunci] = v[:-6] + "+07:00"
            n += 1
    for p in d.get("positions") or []:
        v = str(p.get("opened_at") or "")
        if v.endswith("+00:00"):
            p["opened_at"] = v[:-6] + "+07:00"
            n += 1
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, indent=2), encoding="utf-8")
    tmp.replace(path)
    return n


def _db_rencana(url: str) -> tuple[list[dict], int]:
    import psycopg

    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, type, payload_json FROM events WHERE type LIKE 'trade.%' "
            "AND (payload_json->>'closed_at' LIKE '%+00:00' "
            "OR payload_json->>'opened_at' LIKE '%+00:00') ORDER BY id"
        )
        rows = cur.fetchall()
    rencana = [
        {"id": r[0], "type": r[1], "payload": r[2]} for r in rows
    ]
    return rencana, len(rows)


def _db_terapkan(url: str, cadangan: Path) -> int:
    import psycopg

    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, type, payload_json FROM events WHERE type LIKE 'trade.%' "
            "AND (payload_json->>'closed_at' LIKE '%+00:00' "
            "OR payload_json->>'opened_at' LIKE '%+00:00') ORDER BY id"
        )
        rows = cur.fetchall()
        cadangan.write_text(
            json.dumps([{"id": r[0], "type": r[1], "payload": r[2]} for r in rows],
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        n = 0
        for id_, _tipe, payload in rows:
            baru = dict(payload)
            for kunci in ("closed_at", "opened_at"):
                v = str(baru.get(kunci) or "")
                if v.endswith("+00:00"):
                    baru[kunci] = v[:-6] + "+07:00"
            cur.execute(
                "UPDATE events SET payload_json = %s::jsonb WHERE id = %s",
                (json.dumps(baru), id_),
            )
            n += 1
        conn.commit()
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="tampilkan rencana, jangan ubah apa pun")
    ap.add_argument("--ya", action="store_true", help="lewati konfirmasi interaktif")
    ap.add_argument("--db", action="store_true", help="ikut koreksi payload events trade.*")
    ap.add_argument("--state", type=Path, default=None, help="override direktori state")
    args = ap.parse_args()

    state = args.state or _state_dir()
    if not state.is_dir():
        print(f"GAGAL: state tidak ada: {state}")
        return 1

    ledger_p = state / LEDGER
    posisi_p = state / POSISI
    ubah_ledger = _perbaiki_ledger(ledger_p)
    ubah_posisi = _perbaiki_posisi(posisi_p)

    print(f"State : {state}")
    print(f"Ledger: {len(ubah_ledger)} baris ber-offset +00:00 dari penulis lama")
    for u in ubah_ledger[:8]:
        print(f"  - {u['signal_id']}: {u['sebelum']} → {u['sesudah']}")
    if len(ubah_ledger) > 8:
        print(f"  … {len(ubah_ledger) - 8} lagi")
    print(f"Posisi: {len(ubah_posisi)} field ber-offset +00:00")
    for u in ubah_posisi:
        print(f"  - {u['field']}: {u['sebelum']} → {u['sesudah']}")

    url = None
    if args.db:
        url = os.environ.get("WARROOM_DB_URL")
        if not url:
            print("GAGAL: --db butuh WARROOM_DB_URL")
            return 1
        url = url.replace("postgresql+psycopg", "postgresql")
        rencana, n = _db_rencana(url)
        print(f"Events: {n} payload trade.* akan di-relabel (+00:00 → +07:00)")

    if args.dry_run:
        print("\n(dry-run: tidak ada yang diubah)")
        return 0

    if not args.ya:
        j = input("\nLanjut koreksi label waktu? [y/N] ").strip().lower()
        if j != "y":
            print("Dibatalkan.")
            return 1

    arsip = state / "arsip" / f"koreksi-waktu-{_stamp()}"
    arsip.mkdir(parents=True, exist_ok=True)
    for p in (ledger_p, posisi_p):
        if p.is_file():
            shutil.copy2(p, arsip / p.name)
    print(f"Cadangan berkas: {arsip}")

    n_led = _terapkan_ledger(ledger_p) if ubah_ledger else 0
    n_pos = _terapkan_posisi(posisi_p) if ubah_posisi else 0
    print(f"Ledger: {n_led} baris di-relabel; posisi: {n_pos} field di-relabel")

    if args.db and url:
        n_db = _db_terapkan(url, arsip / "events-trade-sebelum.json")
        print(f"Events: {n_db} payload di-relabel (cadangan: events-trade-sebelum.json)")

    print("\nSelesai. Snapshot akan diregenerasi oleh job refresh-snapshot (≤15 mnt).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
