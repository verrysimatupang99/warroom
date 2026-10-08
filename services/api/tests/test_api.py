"""Tes API P1-T3 (auth/RBAC) + P1-T2 (endpoint gate memakai implementasi yang sama)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from warroom_api import auth


def _cookie(sid: str) -> dict[str, str]:
    return {"Cookie": f"{auth.COOKIE_NAME}={sid}"}


# --- 401 tanpa login ------------------------------------------------------------------


def test_tanpa_login_401_dan_skema_error(client) -> None:
    r = client.get("/api/v1/freshness")
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == "unauthenticated"


def test_cookie_palsu_401(client) -> None:
    r = client.get("/api/v1/health", headers=_cookie("tidak-ada-sesi-ini"))
    assert r.status_code == 401


def test_gate_endpoint_tanpa_login_401(client) -> None:
    r = client.post("/api/v1/gate/evaluate", json={"n": 100, "win": 80, "be": 0.7})
    assert r.status_code == 401


def test_research_read_only_viewer_can_list_and_read_run_records(client, make_user) -> None:
    from warroom_core.db import ResearchRecord, ResearchRun, session_scope

    _, sid = make_user("research-viewer", role="viewer")
    with session_scope() as s:
        s.add(ResearchRun(
            id="run-test-1", research_key="kos-proxy", hypothesis_id="h-1",
            hypothesis_version="v1", hypothesis_json={"baseline": "buy_hold"},
            hypothesis_hash="a" * 64, execution_json={"mode": "paper"},
            execution_hash="b" * 64, status="draft", provenance_json={"source": "test"},
        ))
        s.flush()
        s.add(ResearchRecord(
            id="record-test-1", research_run_id="run-test-1", kind="dataset",
            uri="file:///tmp/dataset.json", sha256="c" * 64, status="observed",
            provenance_json={"source": "test"},
        ))

    runs = client.get("/api/v1/research/runs", headers=_cookie(sid))
    assert runs.status_code == 200
    assert runs.json()["runs"][0]["id"] == "run-test-1"
    detail = client.get("/api/v1/research/runs/run-test-1", headers=_cookie(sid))
    assert detail.status_code == 200
    assert detail.json()["hypothesis_hash"] == "a" * 64
    records = client.get("/api/v1/research/runs/run-test-1/records", headers=_cookie(sid))
    assert records.status_code == 200
    assert records.json()["records"][0]["sha256"] == "c" * 64


def test_research_read_only_requires_auth_and_missing_run_is_404(client) -> None:
    assert client.get("/api/v1/research/runs").status_code == 401


def test_research_read_only_missing_run_does_not_leak_or_fallback(client, make_user) -> None:
    _, sid = make_user("research-missing", role="viewer")
    r = client.get("/api/v1/research/runs/does-not-exist", headers=_cookie(sid))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_ready_melaporkan_kesiapan_database(client, make_user) -> None:
    _, sid = make_user("ready-check", role="viewer")
    r = client.get("/api/v1/ready", headers=_cookie(sid))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["db"] is True
    assert body["checks"]["database"] == "ok"





def test_login_sandi_benar_lalu_me(client, make_user) -> None:
    username, _ = make_user("operator1", role="operator")
    r = client.post("/api/v1/auth/login", json={"username": username, "password": "rahasia-uji-123"})
    assert r.status_code == 200
    assert r.json()["ok"] is True

    r2 = client.get("/api/v1/auth/me")
    assert r2.status_code == 200
    assert r2.json() == {"username": "operator1", "role": "operator"}


def test_login_sandi_salah_dan_pengguna_tidak_ada_pesan_sama(client, make_user) -> None:
    make_user("ada", role="viewer")
    a = client.post("/api/v1/auth/login", json={"username": "ada", "password": "salah"})
    b = client.post("/api/v1/auth/login", json={"username": "tidak-ada", "password": "salah"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json(), "pesan tidak boleh membedakan pengguna ada/tidak"


def test_sesi_kedaluwarsa_ditolak(client, make_user) -> None:
    from warroom_core.db import Session as SessionRow
    from warroom_core.db import session_scope

    username, sid = make_user("basi", role="viewer")
    with session_scope() as s:
        row = s.get(SessionRow, sid)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert client.get("/api/v1/auth/me", headers=_cookie(sid)).status_code == 401


def test_logout_mencabut_sesi(client, make_user) -> None:
    username, sid = make_user("keluar", role="viewer")
    assert client.post("/api/v1/auth/logout", headers=_cookie(sid)).status_code == 200
    assert client.get("/api/v1/auth/me", headers=_cookie(sid)).status_code == 401


# --- RBAC: 403 untuk peran kurang -------------------------------------------------------


def test_viewer_tidak_boleh_menulis_fakta(client, make_user) -> None:
    _, sid = make_user("penonton", role="viewer")
    payload = {
        "facts": [
            {
                "kind": "uji",
                "key": "a",
                "value": 1,
                "source": "tes",
                "observed_at": datetime.now(UTC).isoformat(),
                "ttl_s": 60,
            }
        ]
    }
    r = client.post("/api/v1/facts", json=payload, headers=_cookie(sid))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_viewer_boleh_baca(client, make_user) -> None:
    _, sid = make_user("pembaca", role="viewer")
    assert client.get("/api/v1/health", headers=_cookie(sid)).status_code == 200


def test_operator_boleh_menulis_fakta_dan_terbaca_di_freshness(client, make_user) -> None:
    _, sid = make_user("op2", role="operator")
    now = datetime.now(UTC)
    r = client.post(
        "/api/v1/facts",
        json={
            "facts": [
                {
                    "kind": "poly.verdict",
                    "key": "favorit-btc",
                    "value": {"n": 1175, "win": 928},
                    "source": "state/snapshot.json",
                    "observed_at": now.isoformat(),
                    "ttl_s": 900,
                    "hash": "abc",
                }
            ]
        },
        headers=_cookie(sid),
    )
    assert r.status_code == 200
    assert r.json()["saved"] == 1

    fr = client.get("/api/v1/freshness", headers=_cookie(sid)).json()
    item = next(f for f in fr["facts"] if f["key"] == "favorit-btc")
    assert item["status"] == "segar"
    assert item["source"] == "state/snapshot.json"


def test_fakta_basi_ditandai_basi(client, make_user) -> None:
    _, sid = make_user("op3", role="operator")
    old = datetime.now(UTC) - timedelta(hours=3)
    client.post(
        "/api/v1/facts",
        json={
            "facts": [
                {
                    "kind": "uji",
                    "key": "basi",
                    "value": 1,
                    "source": "tes",
                    "observed_at": old.isoformat(),
                    "ttl_s": 60,
                }
            ]
        },
        headers=_cookie(sid),
    )
    fr = client.get("/api/v1/freshness", headers=_cookie(sid)).json()
    item = next(f for f in fr["facts"] if f["key"] == "basi")
    assert item["status"] == "basi"
    assert item["age_s"] > item["ttl_s"]


# --- gate: endpoint == modul (satu implementasi) -----------------------------------------


def test_endpoint_gate_sama_dengan_modul(client, make_user, db) -> None:
    from warroom_core.db import FrozenSplit, session_scope
    from warroom_core.gate import GateInput, evaluate

    # Split beku harus TERDAFTAR — sejak P1 (5 Okt 2026), gate menolak label "frozen:"
    # yang dikarang karena itu membuat split bisa ditulis SETELAH hasilnya dilihat.
    with session_scope() as s:
        s.add(FrozenSplit(
            id="studi-2026-09", dataset="studi", source="/tmp", files_json=[], manifest_hash="x"
        ))

    _, sid = make_user("gatecek", role="viewer")
    body = {"n": 1175, "win": 928, "be": 0.77, "ci": 0.90, "split": "frozen:studi-2026-09"}
    r = client.post("/api/v1/gate/evaluate", json=body, headers=_cookie(sid))
    assert r.status_code == 200
    api = r.json()
    mod = evaluate(GateInput(**body))  # type: ignore[arg-type]
    assert api["verdict"] == mod.verdict == "gagal"
    assert api["ci_low"] == mod.ci_low
    assert api["required_n"] == mod.required_n


def test_endpoint_gate_menolak_split_tidak_beku(client, make_user) -> None:
    _, sid = make_user("gatecek2", role="viewer")
    r = client.post(
        "/api/v1/gate/evaluate",
        json={"n": 500, "win": 420, "be": 0.70},
        headers=_cookie(sid),
    )
    assert r.status_code == 200
    assert r.json()["verdict"] == "insufficient"


def test_totp_diwajibkan_bila_terdaftar(client, make_user) -> None:
    import pyotp
    from warroom_core.db import User, session_scope

    secret = pyotp.random_base32()
    username, _ = make_user("berTOTP", role="owner")
    with session_scope() as s:
        u = s.query(User).filter_by(username=username).one()
        u.totp_secret_enc = secret

    # tanpa kode → gagal
    assert client.post("/api/v1/auth/login", json={"username": username,
                                                   "password": "rahasia-uji-123"}).status_code == 401
    # dengan kode benar → berhasil
    code = pyotp.TOTP(secret).now()
    r = client.post("/api/v1/auth/login",
                    json={"username": username, "password": "rahasia-uji-123", "totp": code})
    assert r.status_code == 200

def test_design_tokens_membaca_css_dan_bukan_mengarang(client, make_user) -> None:
    """Endpoint token membaca app.css; kalau tak terbaca, menjawab jujur (ada:false).

    Yang dijaga: token tidak boleh disalin ke Python (sumber kedua bisa menyimpang),
    dan ketiadaan berkas tidak boleh jadi angka karangan.
    """
    username, sid = make_user("owner-token", role="owner")
    body = client.get("/api/v1/design/tokens", headers=_cookie(sid)).json()

    if body["ada"]:
        # app.css ada di mesin ini -> wajib memuat token inti.
        assert body["sumber"] == "apps/web/src/app.css"
        assert body["jumlah"] > 10
        for t in ("--color-accent", "--color-bg", "--radius-card"):
            assert t in body["token"], f"token {t} tidak terbaca dari app.css"
    else:
        # Tidak boleh ada token separuh — harus jujur menyebut alasan.
        assert body.get("alasan")
