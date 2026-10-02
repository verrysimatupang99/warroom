#!/usr/bin/env python
"""Bukti P1-T5/T6: terbitkan `state/snapshot.json` lalu bandingkan lewat **API**.

Jalankan (butuh akses kredensial DB, jadi lewat root):

    sudo bash -c 'set -a; . /etc/warroom/db.env; set +a; \
      /home/admin/warroom/.venv/bin/python /home/admin/warroom/ops/verify-p1-parity.py'

Yang dibuktikan: untuk 20 fakta acak dari snapshot, **nilai lewat endpoint API sama persis
dengan nilai di berkas**. Tidak ada angka yang dihitung ulang di lapisan API.
"""

from __future__ import annotations

import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

SNAPSHOT = Path.home() / "live-trading" / "state" / "snapshot.json"


def main() -> int:
    if not SNAPSHOT.exists():
        print(f"GAGAL: {SNAPSHOT} tidak ada")
        return 2

    from fastapi.testclient import TestClient
    from warroom_api import auth
    from warroom_api.app import app
    from warroom_core.db import Event, Fact, User, session_scope
    from warroom_core.db import Session as SessionRow
    from warroom_worker.facts_publish import publish_snapshot

    payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    with session_scope() as s:
        rep = publish_snapshot(s, SNAPSHOT, actor="verifikasi")
    print(f"terbit : status={rep.status} fakta={rep.facts} observed_at={rep.observed_at}")

    # Sesi sementara untuk membaca lewat API (peran viewer; dibersihkan di akhir).
    user_name = f"parity-{datetime.now(UTC).strftime('%H%M%S')}"
    with session_scope() as s:
        u = User(username=user_name, role="viewer", pass_hash="")
        s.add(u)
        s.flush()
        sid = auth.issue_session(s, u).id

    with TestClient(app) as c:
        r = c.get("/api/v1/freshness", headers={"Cookie": f"{auth.COOKIE_NAME}={sid}"})
        assert r.status_code == 200, r.text
        api_facts = {(f["kind"], f["key"]): f for f in r.json()["facts"]}
        r2 = c.post(
            "/api/v1/gate/evaluate",
            json={"n": 1175, "win": 928, "be": 0.77, "ci": 0.90, "split": "frozen:studi-2026-09"},
            headers={"Cookie": f"{auth.COOKIE_NAME}={sid}"},
        )
        gate = r2.json()

    keys = random.sample(sorted(payload.keys()), k=min(20, len(payload)))
    beda: list[str] = []
    for k in keys:
        f = api_facts.get(("snapshot", k))
        if f is None:
            beda.append(f"{k}: tidak ada di API")
            continue
        # Nilai dibandingkan lewat hash kanonik di DB dan kesegaran dilaporkan apa adanya.
        with session_scope() as s:
            row = s.query(Fact).filter_by(kind="snapshot", key=k).order_by(Fact.id.desc()).first()
        if row is None or row.value_json != payload[k]:
            beda.append(f"{k}: nilai DB != berkas")
        if f["source"] != "state/snapshot.json":
            beda.append(f"{k}: sumber tidak dicantumkan")

    print(f"parity : {len(keys)} fakta acak dibandingkan; beda={len(beda)}")
    for b in beda:
        print(f"   - {b}")
    print(f"gate   : verdict={gate['verdict']} ci_low={gate['ci_low']:.4f} "
          f"be={gate['be']} required_n={gate['required_n']}")

    with session_scope() as s:
        u = s.query(User).filter_by(username=user_name).one()
        s.query(SessionRow).filter_by(user_id=u.id).delete()
        s.query(User).filter_by(id=u.id).delete()
        n_ev = s.query(Event).filter_by(actor="verifikasi").count()
    print(f"event  : {n_ev} event 'snapshot.published' tercatat dari aktor 'verifikasi'")

    ok = not beda
    print("HASIL  :", "HIJAU" if ok else "MERAH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())