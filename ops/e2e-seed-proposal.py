#!/usr/bin/env python3
"""Seed parameter + usulan (proposal) untuk e2e — DB tes/CI saja, bukan produksi.

Kenapa ada: `qa-lengkap` memeriksa panel Kebijakan → butuh minimal satu
`proposal-card`. Di DB tes tabel `proposals` kosong, jadi kartunya tidak pernah
dirender dan tes gagal karena tidak ada data — bukan karena UI rusak.

Yang disemai (2 baris, sengaja berbeda status supaya dua cabang teruji):
- parameter `seed_e2e_threshold` sebagai induk (foreign key parameter_name)
- usulan berstatus `butuh_manusia` → tombol terapkan HARUS tampil untuk owner
- usulan berstatus `ditolak`       → tombol terapkan TIDAK boleh tampil

Pengaman:
- menolak jalan bila WARROOM_DB_URL bukan loopback (sama seperti e2e-seed-user.py);
- idempoten: baris dengan parameter_name sama diperbarui, bukan diduplikasi;
- tidak pernah mencetak kredensial.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from warroom_core.db.models import Parameter, Proposal

LOOPBACK = {"127.0.0.1", "localhost", "::1"}
PARAM = "seed_e2e_threshold"


def _pastikan_lokal(db_url: str) -> None:
    host = urlparse(db_url).hostname or ""
    if host not in LOOPBACK:
        raise SystemExit(
            f"DITOLAK: WARROOM_DB_URL menunjuk host non-loopback ({host!r}). "
            "Skrip ini hanya untuk DB tes lokal/CI."
        )


def main() -> int:
    db_url = os.environ.get("WARROOM_DB_URL", "")
    if not db_url:
        raise SystemExit("DITOLAK: WARROOM_DB_URL tidak diset.")
    _pastikan_lokal(db_url)

    kini = datetime.now(UTC)
    mesin = create_engine(db_url)
    with Session(mesin) as s:
        # 1) parameter induk
        par = s.scalar(select(Parameter).where(Parameter.name == PARAM))
        if par is None:
            par = Parameter(name=PARAM, scope="global", locked=False, note="data uji e2e")
            s.add(par)
        par.value_json = {"nilai": 0.55}
        par.bounds_json = {"min": 0.30, "max": 0.80}
        s.flush()

        # 2) dua usulan dengan status berbeda
        seed = [
            {
                "status": "butuh_manusia",
                "to_json": {"nilai": 0.60},
                "reason": "seed e2e: usulan menunggu keputusan owner",
                "rejected_reason": "",
                "decided_by": None,
            },
            {
                "status": "ditolak",
                "to_json": {"nilai": 0.40},
                "reason": "seed e2e: usulan yang sudah ditolak",
                "rejected_reason": "seed e2e: bukti belum mencukupi",
                "decided_by": "uji-owner",
            },
        ]
        dibuat = 0
        for d in seed:
            ada = s.scalar(
                select(Proposal).where(
                    Proposal.parameter_name == PARAM,
                    Proposal.status == d["status"],
                )
            )
            if ada is None:
                ada = Proposal(parameter_name=PARAM)
                s.add(ada)
                dibuat += 1
            ada.from_json = {"nilai": 0.55}
            ada.to_json = d["to_json"]
            ada.reason = d["reason"]
            ada.evidence_json = {
                "n": 40,
                "winrate": 52.5,
                "mean_r": 0.14,
                "catatan": "data uji e2e, bukan bukti nyata",
            }
            ada.gate_verdict = "BUTUH_MANUSIA" if d["status"] == "butuh_manusia" else "TOLAK"
            ada.status = d["status"]
            ada.rejected_reason = d["rejected_reason"]
            ada.decided_by = d["decided_by"]
            ada.created_at = kini

        s.commit()

    print(
        f"seed e2e: parameter {PARAM!r} siap; {dibuat} usulan baru "
        f"(status: butuh_manusia, ditolak)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())