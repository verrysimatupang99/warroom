#!/usr/bin/env python3
"""Sinkronkan manifest strategi (`strategi/*/*/manifest.yaml`) ke `v1.strategy`.

Manifest adalah sumber kebenaran; tabel `v1.strategy` hanya cermin.

Mode:
    --check   (bawaan) bandingkan saja, tidak menulis apa pun
    --apply   UPSERT baris v1.strategy dari manifest

Butuh `V1_DSN` di environment, mengikuti konvensi `v1/*`:

    set -a; . /etc/warroom/v1-api.env; set +a
    /home/admin/warroom/.venv/bin/python ops/strategi-sync.py --check
    /home/admin/warroom/.venv/bin/python ops/strategi-sync.py --apply

Yang divalidasi:
  * kunci wajib manifest (id, nama, market, executor, status)
  * `venue` harus ada di `v1.venue.code` ATAU `v1.feed.code`
  * `market` dipetakan ke enum `v1.market_kind` (memecoin→onchain, openmarket→crypto)
  * `status` dipetakan ke enum `v1.strat_status_t` (dihentikan→retired)
  * `instrument` dicocokkan dengan `v1.instrument` (peringatan, bukan gagal)

Keluaran: tabel manifest vs DB + ringkasan. Exit code 1 bila ada pelanggaran keras
di mode --check, supaya bisa dipakai di CI.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
import yaml

ROOT = Path(__file__).resolve().parents[1]
STRATEGI_DIR = ROOT / "strategi"

# market di manifest -> enum v1.market_kind
MARKET_MAP = {
    "forex": "forex",
    "crypto": "crypto",
    "equity": "equity",
    "prediction": "prediction",
    "openmarket": "crypto",
    "memecoin": "onchain",
}

# status di manifest -> enum v1.strat_status_t
STATUS_MAP = {
    "draft": "draft",
    "paper": "paper",
    "live": "live",
    "dihentikan": "retired",
    "retired": "retired",
}

WAJIB = ("id", "nama", "market", "executor", "status")


@dataclass
class Manifest:
    path: Path
    data: dict[str, Any]
    code: str
    nama: str
    market: str
    status: str
    version: str
    repo_ref: str

    @property
    def venue(self) -> str:
        return str(self.data.get("venue") or "")

    @property
    def instruments(self) -> list[str]:
        out: list[str] = []
        for key in ("instrument", "simbol"):
            val = self.data.get(key)
            if isinstance(val, list):
                out.extend(str(v) for v in val)
        # dedup sambil menjaga urutan
        return list(dict.fromkeys(out))


def discover(base: Path) -> list[Path]:
    if not base.is_dir():
        return []
    found = []
    for p in sorted(base.glob("*/*/manifest.yaml")):
        if p.parent.parent.name.startswith("_"):
            continue
        found.append(p)
    return found


def load_manifest(path: Path, errors: list[str]) -> Manifest | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        errors.append(f"{path}: tidak bisa dibaca ({exc})")
        return None
    if not isinstance(data, dict):
        errors.append(f"{path}: manifest harus mapping YAML")
        return None

    missing = [k for k in WAJIB if not data.get(k)]
    if missing:
        errors.append(f"{path}: kunci wajib hilang: {', '.join(missing)}")
        return None

    code = str(data["id"]).strip()
    if code != path.parent.name:
        errors.append(
            f"{path}: id '{code}' tidak sama dengan nama folder '{path.parent.name}'"
        )

    market = str(data["market"])
    if market not in MARKET_MAP:
        errors.append(f"{path}: market '{market}' tidak dikenal (pilihan: {', '.join(MARKET_MAP)})")
        return None

    status = str(data["status"])
    if status not in STATUS_MAP:
        errors.append(f"{path}: status '{status}' tidak dikenal (pilihan: {', '.join(STATUS_MAP)})")
        return None

    return Manifest(
        path=path,
        data=data,
        code=code,
        nama=str(data["nama"]),
        market=market,
        status=status,
        version=str(data.get("versi") or "unknown"),
        repo_ref=str(data.get("repo_ref") or ""),
    )


def fetch_db(cur) -> dict[str, dict[str, Any]]:
    cur.execute(
        """
        select code, name, market::text, version, status::text, coalesce(repo_ref,'')
        from v1.strategy
        """
    )
    return {
        row[0]: {
            "name": row[1],
            "market": row[2],
            "version": row[3],
            "status": row[4],
            "repo_ref": row[5],
        }
        for row in cur.fetchall()
    }


def fetch_ref(cur) -> tuple[set[str], set[str], dict[str, set[str]]]:
    cur.execute("select code from v1.venue")
    venues = {r[0] for r in cur.fetchall()}
    cur.execute("select code from v1.feed")
    feeds = {r[0] for r in cur.fetchall()}
    cur.execute(
        """
        select v.code, i.symbol
        from v1.instrument i
        join v1.venue v on v.id = i.venue_id
        """
    )
    instruments: dict[str, set[str]] = {}
    for venue_code, symbol in cur.fetchall():
        instruments.setdefault(venue_code, set()).add(symbol)
    return venues, feeds, instruments


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Sinkronkan manifest strategi ke v1.strategy")
    ap.add_argument("--apply", action="store_true", help="tulis ke DB (bawaan: hanya cek)")
    ap.add_argument("--check", action="store_true", help="hanya cek (bawaan)")
    ap.add_argument("--dir", default=str(STRATEGI_DIR), help="akar folder strategi")
    args = ap.parse_args(argv)

    apply_mode = bool(args.apply)

    dsn = os.environ.get("V1_DSN")
    if not dsn:
        print(
            "V1_DSN tidak ada di environment.\n"
            "Jalankan: set -a; . /etc/warroom/v1-api.env; set +a",
            file=sys.stderr,
        )
        return 2

    errors: list[str] = []
    warnings: list[str] = []

    paths = discover(Path(args.dir))
    if not paths:
        print(f"Tidak ada manifest di {args.dir}/*/*/manifest.yaml", file=sys.stderr)
        return 2

    manifests: list[Manifest] = []
    for p in paths:
        m = load_manifest(p, errors)
        if m:
            manifests.append(m)

    codes = [m.code for m in manifests]
    dupes = {c for c in codes if codes.count(c) > 1}
    for c in sorted(dupes):
        errors.append(f"id ganda: {c}")

    with psycopg.connect(dsn, connect_timeout=8) as conn:
        with conn.cursor() as cur:
            db = fetch_db(cur)
            venues, feeds, instruments = fetch_ref(cur)

            rows: list[tuple[str, str, str, str, str, str, str]] = []
            for m in manifests:
                if m.venue and m.venue not in venues and m.venue not in feeds:
                    errors.append(
                        f"{m.path}: venue '{m.venue}' tidak ada di v1.venue maupun v1.feed"
                    )

                if m.venue and m.instruments:
                    known = instruments.get(m.venue)
                    if known is not None:
                        belum = [i for i in m.instruments if i not in known]
                        if belum:
                            warnings.append(
                                f"{m.code}: instrument belum terdaftar di v1.instrument "
                                f"untuk {m.venue}: {', '.join(belum[:6])}"
                            )

                db_market = MARKET_MAP[m.market]
                db_status = STATUS_MAP[m.status]

                current = db.get(m.code)
                if current is None:
                    state = "BARU"
                else:
                    diffs = []
                    if current["name"] != m.nama:
                        diffs.append("name")
                    if current["market"] != db_market:
                        diffs.append("market")
                    if current["version"] != m.version:
                        diffs.append("version")
                    if current["status"] != db_status:
                        diffs.append("status")
                    if current["repo_ref"] != m.repo_ref:
                        diffs.append("repo_ref")
                    state = "=" if not diffs else "UBAH:" + ",".join(diffs)

                rows.append(
                    (m.code, m.nama, db_market, m.version, db_status, m.venue, state)
                )

                if apply_mode:
                    cur.execute(
                        """
                        insert into v1.strategy (code, name, market, version, repo_ref, manifest_json, status)
                        values (%s, %s, %s::v1.market_kind, %s, %s, %s::jsonb, %s::v1.strat_status_t)
                        on conflict (code) do update set
                            name = excluded.name,
                            market = excluded.market,
                            version = excluded.version,
                            repo_ref = excluded.repo_ref,
                            manifest_json = excluded.manifest_json,
                            status = excluded.status
                        """,
                        (
                            m.code,
                            m.nama,
                            db_market,
                            m.version,
                            m.repo_ref,
                            _json(m.data),
                            db_status,
                        ),
                    )

            if apply_mode:
                conn.commit()

            orphans = sorted(set(db) - set(codes))

    _render(rows, orphans, warnings, errors, apply_mode)
    if errors:
        return 1
    return 0


def _json(data: dict[str, Any]) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, default=str)


def _render(rows, orphans, warnings, errors, apply_mode) -> None:
    print("=" * 96)
    print("SINKRON MANIFEST STRATEGI -> v1.strategy" + (" (APPLY)" if apply_mode else " (CHECK)"))
    print("=" * 96)
    print()
    print(f"{'id':<26} {'market':<10} {'status':<8} {'versi':<8} {'venue':<11} keadaan")
    print("-" * 96)
    for code, nama, market, version, status, venue, state in sorted(rows):
        print(f"{code[:26]:<26} {market:<10} {status:<8} {version:<8} {venue[:11]:<11} {state}")

    if orphans:
        print()
        print("ADA DI DB, TIDAK ADA MANIFEST (tidak dihapus otomatis):")
        for code in orphans:
            print(f"  - {code}")

    if warnings:
        print()
        print("PERINGATAN:")
        for w in warnings:
            print(f"  ! {w}")

    if errors:
        print()
        print("GALAT (harus diperbaiki):")
        for e in errors:
            print(f"  x {e}")

    print()
    if not errors and not apply_mode:
        print("Siap di-apply. Jalankan dengan --apply untuk menulis ke DB.")
    print()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
