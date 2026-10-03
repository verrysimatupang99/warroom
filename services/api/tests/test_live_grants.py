"""Tes P5 (parameter/usulan/kill switch) + P6 (arming/grant) lewat API.

Aturan yang diuji: aksi live tanpa grant → **409 dengan daftar grant kurang**; arming
dibaca dari tiga sumber dan `armed` hanya bila semuanya lulus; kill switch hanya untuk owner.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from warroom_api import auth, live
from warroom_core import autonomy
from warroom_core.db import Event, Grant, Parameter, Proposal, session_scope


def _cookie(sid: str) -> dict[str, str]:
    return {"Cookie": f"{auth.COOKIE_NAME}={sid}"}


@pytest.fixture(autouse=True)
def _isolasi(bersihkan_db):
    with session_scope() as s:
        s.query(Proposal).delete()
        s.query(Parameter).delete()
        s.query(Grant).delete()
        s.query(Event).delete()
    yield


# --- P5 -----------------------------------------------------------------------------------


def test_params_terdaftar_dan_terbaca(client, make_user) -> None:
    _, sid = make_user("p5-viewer", role="viewer")
    with session_scope() as s:
        autonomy.seed_parameters(s)
    body = client.get("/api/v1/params", headers=_cookie(sid)).json()
    nama = {p["nama"] for p in body["params"]}
    assert {"agent.threshold", "risk.sizeUsd", "gate.min_n", "ai.kill_switch"} <= nama
    gate = next(p for p in body["params"] if p["nama"] == "gate.min_n")
    assert gate["terkunci"] is True, "ambang gate wajib terkunci"


def test_proposal_ditolak_di_luar_batas_terlihat_di_api(client, make_user) -> None:
    _, sid = make_user("p5-viewer2", role="viewer")
    with session_scope() as s:
        autonomy.seed_parameters(s)
        autonomy.usulkan(
            s, "agent.weights.book", 0.602, alasan="patch agen",
            evidence={"n": 340, "win": 305, "be": 0.8675},
        )
    body = client.get("/api/v1/proposals", headers=_cookie(sid)).json()
    pr = body["proposals"][0]
    assert pr["status"] == "ditolak"
    assert "di_luar_bounds" in pr["ditolak_karena"]
    assert pr["bukti"]["n"] == 340


def test_kill_switch_hanya_owner(client, make_user) -> None:
    _, sid_op = make_user("p5-op", role="operator")
    _, sid_owner = make_user("p5-owner", role="owner")
    with session_scope() as s:
        autonomy.seed_parameters(s)

    r = client.post("/api/v1/ai/kill-switch", json={"aktif": True}, headers=_cookie(sid_op))
    assert r.status_code == 403

    r = client.post("/api/v1/ai/kill-switch", json={"aktif": True}, headers=_cookie(sid_owner))
    assert r.status_code == 200 and r.json()["kill_switch"] is True

    st = client.get("/api/v1/ai/status", headers=_cookie(sid_op)).json()
    assert st["kill_switch"] is True


def test_apply_dan_rollback_proposal_lewat_api(client, make_user) -> None:
    _, sid = make_user("p5-owner2", role="owner")
    with session_scope() as s:
        autonomy.seed_parameters(s)
        autonomy.usulkan(
            s, "agent.threshold", 0.86, alasan="ubah",
            evidence={"n": 500, "win": 420, "be": 0.77, "split": "frozen:x"},
        )
        pid = s.query(Proposal).one().id

    assert client.post(f"/api/v1/proposals/{pid}/rollback", headers=_cookie(sid)).status_code == 200
    with session_scope() as s:
        p = s.scalar(__import__("sqlalchemy").select(Parameter).where(Parameter.name == "agent.threshold"))
        assert p.value_json == 0.82
    # rollback kedua kali → 409 (belum/tidak pernah diterapkan lagi)
    assert client.post(f"/api/v1/proposals/{pid}/rollback", headers=_cookie(sid)).status_code == 409


# --- P6 -----------------------------------------------------------------------------------


def test_arming_membaca_tiga_sumber(client, make_user) -> None:
    _, sid = make_user("p6-viewer", role="viewer")
    body = client.get("/api/v1/live/arming", headers=_cookie(sid)).json()
    nama = {c["nama"] for c in body["checks"]}
    assert {"gate_file", "operator_json", "unit_env", "heartbeat"} == nama
    assert isinstance(body["armed"], bool)
    for c in body["checks"]:
        assert "sumber" in c and "lulus" in c and "arti" in c


def test_arming_tidak_armed_saat_gate_hilang(monkeypatch) -> None:
    """Gate hilang = tidak armed, walaupun operator.json bilang siap."""
    monkeypatch.setattr(live, "_ada_root", lambda p: False)
    _ok = ('{"paused": false, "submissionAllowed": true}', "ok")
    monkeypatch.setattr(live, "_baca_root", lambda p, timeout_s=10.0: _ok)
    st = live.arming_status()
    assert st.armed is False
    assert "gate_file" in st.detail


def test_arming_armed_hanya_bila_semua_lulus(monkeypatch) -> None:
    monkeypatch.setattr(live, "_ada_root", lambda p: True)
    monkeypatch.setattr(
        live, "_baca_root",
        lambda p, timeout_s=10.0: ('{"paused": false, "submissionAllowed": true}', "ok"),
    )

    class _U:
        returncode = 0
        stdout = "LoadState=loaded\nActiveState=inactive\nEnvironment=SNIPER_MODE=paper\n"

    monkeypatch.setattr(live.subprocess, "run", lambda *a, **k: _U())
    st = live.arming_status()
    assert st.armed is True
    # env hanya nama variabel, bukan nilainya
    env_check = next(c for c in st.checks if c["nama"] == "unit_env")
    assert env_check["nilai"]["env_vars"] == ["SNIPER_MODE"]


def test_aksi_live_tanpa_grant_409_dengan_daftar_kurang(client, make_user, monkeypatch) -> None:
    _, sid = make_user("p6-owner", role="owner")
    monkeypatch.setattr(live, "_ada_root", lambda p: False)
    monkeypatch.setattr(live, "_baca_root", lambda p, timeout_s=10.0: (None, "tidak-ada"))
    r = client.post("/api/v1/live/action", json={"scope": "live.start"}, headers=_cookie(sid))
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "conflict_grant_required"
    kurang = err["detail"]["kurang"]
    assert any("grant aktif" in k for k in kurang)
    assert any("gate live" in k for k in kurang)


def test_aksi_live_scope_asing_fail_closed(client, make_user) -> None:
    _, sid = make_user("p6-owner2", role="owner")
    r = client.post("/api/v1/live/action", json={"scope": "live.hapus-semua"}, headers=_cookie(sid))
    assert r.status_code == 409
    assert any("tidak dikenal" in k for k in r.json()["error"]["detail"]["kurang"])


def test_grant_butuh_message_id_dan_scope_dikenal(client, make_user) -> None:
    _, sid = make_user("p6-owner3", role="owner")
    r = client.post("/api/v1/live/grant",
                    json={"scope": "live.start", "message_id": ""}, headers=_cookie(sid))
    assert r.status_code == 422
    r2 = client.post("/api/v1/live/grant",
                     json={"scope": "live.ngawur", "message_id": "m1"}, headers=_cookie(sid))
    assert r2.status_code == 422


def test_grant_aktif_membuat_aksi_lolos_syarat_grant(client, make_user, monkeypatch) -> None:
    _, sid = make_user("p6-owner4", role="owner")
    # gate dibuka hanya di dunia tes (di host nyata berkas gate TIDAK pernah dibuat agen)
    monkeypatch.setattr(live, "_ada_root", lambda p: True)
    monkeypatch.setattr(
        live, "_baca_root",
        lambda p, timeout_s=10.0: ('{"paused": false, "submissionAllowed": true}', "ok"),
    )

    class _U:
        returncode = 0
        stdout = "LoadState=loaded\nActiveState=inactive\nEnvironment=\n"

    monkeypatch.setattr(live.subprocess, "run", lambda *a, **k: _U())
    assert live.arming_status().armed is True

    r = client.post("/api/v1/live/grant",
                    json={"scope": "live.start", "message_id": "pesan-123", "ttl_s": 600},
                    headers=_cookie(sid))
    assert r.status_code == 200

    a = client.post("/api/v1/live/action", json={"scope": "live.start"}, headers=_cookie(sid))
    assert a.status_code == 200
    assert a.json()["ok"] is True
    assert "tidak ada aksi yang dijalankan" in a.json()["catatan"]


def test_grant_kedaluwarsa_tidak_dianggap_aktif(db) -> None:
    with session_scope() as s:
        s.add(
            Grant(
                scope="live.stop",
                granted_by="owner",
                message_id="m-lama",
                granted_at=datetime.now(UTC) - timedelta(hours=3),
                expires_at=datetime.now(UTC) - timedelta(hours=1),
            )
        )
    with session_scope() as s:
        assert live.grant_aktif(s, "live.stop") is None
        assert live.scope_kurang(s, "live.stop")


def test_grant_tercatat_di_event(client, make_user) -> None:
    _, sid = make_user("p6-owner5", role="owner")
    client.post("/api/v1/live/grant",
                json={"scope": "live.stop", "message_id": "m-9", "reason": "uji"}, headers=_cookie(sid))
    with session_scope() as s:
        ev = s.query(Event).filter_by(type="live.grant").one()
        assert ev.payload_json["message_id"] == "m-9"
        assert ev.severity == "warning"


def test_dry_run_tidak_mengirim_order(client, make_user, monkeypatch) -> None:
    _, sid = make_user("p6-op", role="operator")
    dipanggil: list[list[str]] = []

    class _H:
        returncode = 0
        stdout = "kedalaman: 5 share @ 0.78\n"

    def _run(cmd, **kw):
        dipanggil.append(list(cmd))
        return _H()

    monkeypatch.setattr(live.subprocess, "run", _run)
    monkeypatch.setattr(live.Path, "exists", lambda self: True)
    r = client.post("/api/v1/live/dry-run", json={"subperintah": "depth"}, headers=_cookie(sid))
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert dipanggil and dipanggil[0][-1] == "depth"
    # tidak ada perintah yang mengeksekusi order
    assert all("order" not in " ".join(c) for c in dipanggil)
    assert json.dumps(r.json())[:1] == "{"

# --- W6: kesehatan provider di ai/status & llm-console ------------------------------------


def test_ai_status_melaporkan_kesehatan_provider(client, make_user) -> None:
    """Provider yang gagal harus terlihat beserta kode dan rasio ok-nya — dari llm_calls."""
    from warroom_core.db import LLMCall

    _, sid = make_user("ai-health", role="viewer")
    with session_scope() as s:
        s.add(LLMCall(role="narrator", provider="nutaraline", model="m", ok=False,
                      error_code="http_401", latency_ms=203))
        s.add(LLMCall(role="narrator", provider="nutaraline", model="m", ok=True,
                      latency_ms=5300))
        s.add(LLMCall(role="verifier", provider="qonek", model="m", ok=True,
                      fallback_from="nutaraline", latency_ms=3400))
    body = client.get("/api/v1/ai/status", headers=_cookie(sid)).json()
    per = {p["provider"]: p for p in body["provider"]}
    assert per["nutaraline"]["gagal"] == 1
    assert per["nutaraline"]["error_terakhir"] == "http_401"
    assert per["nutaraline"]["ok_rate"] == 0.5
    assert per["qonek"]["fallback"] == 1 and per["qonek"]["ok"] == 1

    konsol = client.get("/api/v1/ai/llm-console", headers=_cookie(sid)).json()
    assert konsol["per_provider"] and "ok_rate" in konsol["per_provider"][0]
    assert konsol["per_provider"][0]["error_terakhir"] in ("http_401", None)
