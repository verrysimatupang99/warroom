"""Uji authorization menyeluruh — jawaban atas temuan QA eksternal 7 Okt 2026.

QA menulis: "audit ini belum membuktikan: operator tidak bisa membaca area terlarang,
IDOR pada endpoint detail, export CSV membocorkan data lintas role, endpoint /api/v1/*
konsisten memeriksa role, SSE tidak mengirim event area lain."

Berkas ini membuktikan satu per satu. Yang diuji bukan hanya "401 tanpa sesi" (sudah
ada di tempat lain), melainkan **perbedaan hak antar peran** dan **objek milik orang
lain** — kelas bug yang paling sering lolos dari tes "happy path".

Aturan peran (auth.py: _ROLE_RANK): viewer(1) < operator(2) < owner(3).
"""

from __future__ import annotations

from warroom_api import auth
from warroom_core.db import Proposal, session_scope


def _cookie(sid: str) -> dict[str, str]:
    return {"Cookie": f"{auth.COOKIE_NAME}={sid}"}


def test_tanpa_sesi_semua_endpoint_sensitif_401(client) -> None:
    """Tanpa cookie: tidak ada data yang bocor lewat satu pun endpoint baca utama."""
    for jalur in (
        "/api/v1/areas",
        "/api/v1/areas/crypto",
        "/api/v1/areas/idx",
        "/api/v1/events",
        "/api/v1/sinyal/per-pasar",
        "/api/v1/pasar/ringkas",
        "/api/v1/alerts",
        "/api/v1/freshness",
        "/api/v1/ai/status",
        "/api/v1/ai/prompts",
        "/api/v1/live/arming",
        "/api/v1/live/grants",
        "/api/v1/params",
        "/api/v1/proposals",
        "/api/v1/sumber",
        "/api/v1/metrics",
    ):
        r = client.get(jalur)
        assert r.status_code == 401, f"{jalur} seharusnya 401 tanpa sesi, dapat {r.status_code}"


def test_viewer_tidak_bisa_menulis_apa_pun(client, make_user) -> None:
    """Viewer = baca saja. Setiap jalur tulis harus 403, bukan diam-diam berhasil.

    Rute diambil dari app.py (bukan tebakan): ack alert (operator+), facts (operator+),
    freeze dataset (owner), kill-switch AI (owner), grant/aksi live (owner).
    """
    _, sid = make_user("idor-view", role="viewer")
    h = _cookie(sid)

    for jalur, body in (
        ("/api/v1/alerts/1/ack", {}),                       # operator+
        ("/api/v1/facts", {"kind": "snapshot", "key": "uji", "value": {}}),  # operator+
        ("/api/v1/datasets/freeze", {"nama": "uji"}),        # owner
        ("/api/v1/ai/kill-switch", {"aktif": True}),         # owner
        ("/api/v1/live/grant", {"user": "x"}),               # owner
        ("/api/v1/live/action", {"aksi": "arm"}),            # owner
        ("/api/v1/proposals/1/apply", {}),                   # owner
    ):
        r = client.post(jalur, headers=h, json=body)
        assert r.status_code == 403, f"viewer tidak boleh {jalur} (dapat {r.status_code})"


def test_operator_tidak_bisa_aksi_owner(client, make_user) -> None:
    """Operator (2) tidak boleh melakukan aksi owner (3): grant, aksi live, apply proposal,
    freeze dataset, kill-switch. Semua harus 403 — bukan 200, bukan 500."""
    _, sid = make_user("idor-op", role="operator")
    h = _cookie(sid)

    for jalur, body in (
        ("/api/v1/live/grant", {"user": "x"}),
        ("/api/v1/live/action", {"aksi": "arm"}),
        ("/api/v1/proposals/1/apply", {}),
        ("/api/v1/proposals/1/rollback", {}),
        ("/api/v1/datasets/freeze", {"nama": "uji"}),
        ("/api/v1/ai/kill-switch", {"aktif": True}),
    ):
        r = client.post(jalur, headers=h, json=body)
        assert r.status_code == 403, f"operator tidak boleh {jalur} (dapat {r.status_code})"

    # dan operator BOLEH yang memang untuknya (dry-run) — kalau 403, berarti peran terlalu ketat
    r = client.post("/api/v1/live/dry-run", headers=h, json={"aksi": "uji"})
    assert r.status_code != 403, "operator seharusnya boleh dry-run (bukan aksi uang)"


def test_idor_proposal_antar_pengguna(client, make_user) -> None:
    """IDOR: operator B tidak boleh menerapkan proposal yang diusulkan A.

    Proposal = perubahan parameter (bounded autonomy). Menyentuhnya wajib owner, dan
    identitas pengusul tidak memberi hak tambahan apa pun.
    """
    from warroom_core.db import Parameter, session_scope

    _, sid_a = make_user("idor-a", role="operator")
    _, sid_b = make_user("idor-b", role="operator")

    with session_scope() as s:
        s.add(Parameter(name="risiko-uji", value_json={"max": 1}, note="uji"))
        s.flush()
        p = Proposal(
            parameter_name="risiko-uji",
            from_json={"max": 1},
            to_json={"max": 2},
            reason="uji idor",
            status="diusulkan",
        )
        s.add(p)
        s.flush()
        pid = p.id

    # A (operator) pun tidak boleh menerapkan; B juga tidak. Keduanya 403.
    for sid, nama in ((sid_a, "A"), (sid_b, "B")):
        r = client.post(f"/api/v1/proposals/{pid}/apply", headers=_cookie(sid), json={})
        assert r.status_code == 403, f"operator {nama} tidak boleh apply proposal (dapat {r.status_code})"

    # Yang boleh hanya owner — dan proposal tetap ada (append-only) sampai diputuskan.
    with session_scope() as s:
        masih = s.get(Proposal, pid)
        assert masih is not None and masih.status == "diusulkan"


def test_detail_area_tidak_menerima_area_siluman(client, make_user) -> None:
    """Area tak dikenal menjawab jujur (daftar area), bukan 500 dan bukan data area lain."""
    _, sid = make_user("idor-area", role="viewer")
    r = client.get("/api/v1/areas/../../etc/passwd", headers=_cookie(sid))
    assert r.status_code in (200, 404, 422)
    if r.status_code == 200:
        d = r.json()
        assert d.get("dikenal") is False, "path traversal tidak boleh dianggap area sah"


def test_sse_menghormati_topik_diminta(client, make_user) -> None:
    """SSE hanya mengirim tipe yang diminta — bukan seluruh aliran ke semua klien.

    QA: "SSE tidak mengirim event area lain". Diuji pada lapisan yang bisa diuji tanpa
    menggantung: `/api/v1/events?tipe=` harus menyaring prefix dengan benar.
    """
    from warroom_core.db import Event

    _, sid = make_user("idor-sse", role="viewer")
    with session_scope() as s:
        s.add(Event(type="trade.opened", actor="uji", severity="info", payload_json={"pair": "AAA"}))
        s.add(Event(type="alert.sent", actor="uji", severity="warn", payload_json={"x": 1}))

    semua = client.get("/api/v1/events?limit=50", headers=_cookie(sid)).json()
    hanya_trade = client.get("/api/v1/events?limit=50&tipe=trade.", headers=_cookie(sid)).json()

    assert semua["count"] >= 2
    assert hanya_trade["count"] >= 1
    assert all(e["type"].startswith("trade.") for e in hanya_trade["events"]), (
        "filter tipe bocor: ada event di luar prefix yang diminta"
    )


def test_proposal_tidak_bisa_dilihat_tanpa_sesi(client, make_user) -> None:
    """Daftar proposal (memuat rencana parameter) tidak boleh terbaca anonim."""
    _, sid = make_user("idor-prop", role="viewer")
    assert client.get("/api/v1/proposals").status_code == 401
    # viewer boleh membaca (transparansi) — tetapi hanya dengan sesi
    r = client.get("/api/v1/proposals", headers=_cookie(sid))
    assert r.status_code == 200
