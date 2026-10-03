"""Tes endpoint area, SSE, dan /metrics (P1-T6/T7/T8)."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest
from warroom_api import auth
from warroom_api.areas import AREA_KEYS
from warroom_api.metrics import collect_metrics, render_prometheus
from warroom_api.stream import event_stream, parse_last_event_id, topic_matches
from warroom_core.db import Alert, Event, Fact, Job, session_scope


@pytest.fixture(autouse=True)
def _isolasi(bersihkan_db):
    """Tes ini mengasumsikan tabel kosong di awal (dipakai bersama berkas tes lain)."""
    yield


def _cookie(sid: str) -> dict[str, str]:
    return {"Cookie": f"{auth.COOKIE_NAME}={sid}"}


def _fakta(kind: str, key: str, value, umur_s: int = 5, ttl_s: int = 1800, source="state/snapshot.json"):
    return Fact(
        kind=kind,
        key=key,
        value_json=value,
        source=source,
        observed_at=datetime.now(UTC) - timedelta(seconds=umur_s),
        ttl_s=ttl_s,
        hash="h",
    )


# --- P1-T6: baca per-area ---------------------------------------------------------------


def test_area_mengembalikan_fakta_dengan_metadata(client, make_user) -> None:
    _, sid = make_user("baca-area", role="viewer")
    with session_scope() as s:
        s.add(_fakta("snapshot", "kandidat", [{"pair": "BTCUSDT"}]))
        s.add(_fakta("snapshot", "bagian", {"crypto": "ok"}))

    r = client.get("/api/v1/crypto", headers=_cookie(sid))
    assert r.status_code == 200
    body = r.json()
    assert body["area"] == "crypto" and body["dikenal"] is True
    assert body["data"]["bagian"] == {"crypto": "ok"}
    for f in body["facts"]:
        assert {"fact_id", "source", "observed_at", "ttl_s", "status", "value"} <= set(f)


def test_semua_area_punya_rute(client, make_user) -> None:
    _, sid = make_user("baca-semua", role="viewer")
    for area in AREA_KEYS:
        assert client.get(f"/api/v1/{area}", headers=_cookie(sid)).status_code == 200


def test_area_kosong_melaporkan_hilang_bukan_nol(client, make_user) -> None:
    _, sid = make_user("baca-kosong", role="viewer")
    body = client.get("/api/v1/forex", headers=_cookie(sid)).json()
    assert body["data"] == {}
    assert "bagian" in body["kunci_hilang"], "kunci tanpa fakta harus dilaporkan hilang, bukan diisi 0"


def test_fakta_satu_404_bila_belum_ada(client, make_user) -> None:
    _, sid = make_user("baca-404", role="viewer")
    r = client.get("/api/v1/facts/snapshot/tidak-ada", headers=_cookie(sid))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_fakta_satu_riwayat(client, make_user) -> None:
    _, sid = make_user("baca-riwayat", role="viewer")
    with session_scope() as s:
        s.add(_fakta("snapshot", "mode", "paper", umur_s=100))
        s.add(_fakta("snapshot", "mode", "paper", umur_s=5))
    body = client.get("/api/v1/facts/snapshot/mode?riwayat=2", headers=_cookie(sid)).json()
    assert len(body["facts"]) == 2


def test_ringkasan_area_menandai_basi(client, make_user) -> None:
    _, sid = make_user("baca-ringkas", role="viewer")
    with session_scope() as s:
        s.add(_fakta("snapshot", "kandidat", [], umur_s=7200, ttl_s=60))
    body = client.get("/api/v1/areas", headers=_cookie(sid)).json()
    crypto = next(a for a in body["areas"] if a["area"] == "crypto")
    assert crypto["basi"] >= 1


# --- P1-T7: SSE -------------------------------------------------------------------------


def test_parse_last_event_id_aman() -> None:
    assert parse_last_event_id(None) is None
    assert parse_last_event_id("abc") is None
    assert parse_last_event_id("-5") is None
    assert parse_last_event_id("42") == 42


def test_topik_filter() -> None:
    assert topic_matches("verdict.updated", ["verdicts"])
    assert topic_matches("job.ran", ["services"])
    assert not topic_matches("snapshot.published", ["verdicts"])
    assert topic_matches("apa.saja", None)


def test_sse_mengirim_event_dari_id_tertentu(client, make_user, db) -> None:
    _, sid = make_user("sse", role="viewer")
    with session_scope() as s:
        s.add(Event(type="verdict.updated", actor="uji", payload_json={"n": 1175}, fact_ids=[1]))
        s.add(Event(type="job.ran", actor="uji", payload_json={"job": "freshness"}, fact_ids=[]))
    with session_scope() as s:
        id_awal = min(e.id for e in s.query(Event).all()) - 1

    async def kumpulkan() -> list[str]:
        gen = event_stream(["verdicts"], str(id_awal), poll_s=0.01, max_iterations=2)
        out = []
        async for chunk in gen:
            out.append(chunk)
        return out

    potongan = asyncio.run(kumpulkan())
    teks = "".join(potongan)
    assert "event: verdict.updated" in teks
    assert "job.ran" not in teks, "topik lain tidak boleh ikut terkirim"
    assert '"n": 1175' in teks


def test_sse_tanpa_last_event_id_tidak_membanjiri_riwayat(db) -> None:
    with session_scope() as s:
        for i in range(5):
            s.add(Event(type="verdict.updated", actor="uji", payload_json={"i": i}, fact_ids=[]))

    async def kumpulkan() -> list[str]:
        gen = event_stream(None, None, poll_s=0.01, max_iterations=1)
        return [c async for c in gen]

    teks = "".join(asyncio.run(kumpulkan()))
    assert "event: verdict.updated" not in teks, "tanpa Last-Event-ID, riwayat lama tidak dikirim"
    assert "retry: 3000" in teks


def test_sse_bisa_dihentikan_dari_luar(db) -> None:
    """Disconnect klien harus mengakhiri generator (tidak ada kebocoran)."""
    berhenti = {"v": False}

    async def jalankan() -> int:
        gen = event_stream(None, None, poll_s=0.01, disconnect=lambda: berhenti["v"])
        n = 0
        async for _ in gen:
            n += 1
            berhenti["v"] = True
        return n

    n = asyncio.run(asyncio.wait_for(jalankan(), timeout=5))
    assert n <= 3, "generator harus berhenti setelah disconnect"


# --- P1-T8: /metrics --------------------------------------------------------------------


def test_metrics_butuh_login_secara_default(client, make_user) -> None:
    r = client.get("/metrics")
    assert r.status_code == 401


def test_metrics_bisa_dibuka_untuk_scraper_lokal(client, make_user, monkeypatch) -> None:
    monkeypatch.setenv("WARROOM_METRICS_PUBLIC", "1")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "warroom_up 1" in r.text


def test_metrics_isi_dari_db(client, make_user) -> None:
    _, sid = make_user("metrik", role="viewer")
    with session_scope() as s:
        s.add(_fakta("snapshot", "mode", "paper", umur_s=7200, ttl_s=60))  # basi
        s.add(Event(type="job.ran", actor="uji", payload_json={}, fact_ids=[]))
        s.add(Alert(severity="warning", subject="snapshot/mode", message="basi", suggested_action="cek"))
        s.add(Job(name="uji-job", interval_s=60, enabled=True))

    teks = client.get("/metrics", headers=_cookie(sid)).text
    assert "warroom_facts_basi 1" in teks
    assert 'warroom_events_total{type="job.ran"} 1' in teks
    assert "warroom_alerts_open 1" in teks
    assert 'warroom_job_enabled{job="uji-job"} 1' in teks


def test_collect_metrics_tanpa_data_tidak_mengarang(db) -> None:
    with session_scope() as s:
        m = collect_metrics(s)
    assert m["facts_total"] == 0
    assert m["facts_basi"] == 0
    assert m["alerts_terbuka"] == 0
    assert "warroom_facts_total 0" in render_prometheus(m)


def test_metrik_basi_menghitung_per_kind_dan_key(db) -> None:
    """Kunci yang sama dipakai dua kind (`ringkas`) — yang basi tetap harus terhitung.

    Regresi: grouping lama hanya `key`, sehingga fakta segar dari kind lain menutupi
    fakta basi (metrik bilang 0 padahal UI benar menampilkan "BASI").
    """
    with session_scope() as s:
        # key "ringkas": poly.agent segar, learner basi (TTL harian, fakta kemarin).
        s.add(_fakta("poly.agent", "ringkas", {"ok": True}, umur_s=5, ttl_s=1800))
        s.add(_fakta("learner", "ringkas", {"n": 1}, umur_s=7200, ttl_s=3600))
        s.add(_fakta("snapshot", "mode", "paper", umur_s=5, ttl_s=1800))
        m = collect_metrics(s)
    assert m["facts_basi"] == 1, m
    assert m["facts_terbaru"] == 3


def test_area_polymarket_menyertakan_fakta_verdict(client, make_user) -> None:
    """Fakta `poly.verdict` (kind non-snapshot) ikut payload area — GateMeter membacanya."""
    _, sid = make_user("verdict-uji", role="viewer")
    with session_scope() as s:
        s.add(
            _fakta(
                "poly.verdict",
                "verdict",
                {"n": 3977, "win": 3107, "be": 0.7662, "ci": 0.95, "deff": 1.345, "split": None},
            )
        )
    body = client.get("/api/v1/areas/polymarket", headers=_cookie(sid)).json()
    verdict = [f for f in body["facts"] if f["key"] == "verdict"]
    assert len(verdict) == 1, "fakta verdict harus muncul di area polymarket"
    assert verdict[0]["kind"] == "poly.verdict"
    assert verdict[0]["value"]["deff"] == 1.345
    assert body["data"]["verdict"]["n"] == 3977


def test_area_polymarket_menyertakan_katalog_dataset(client, make_user) -> None:
    """Fakta `poly.dataset/recorder` + `poly.akses/cakupan` ikut area — DatasetExplorer (P4-T3)."""
    _, sid = make_user("dataset-uji", role="viewer")
    with session_scope() as s:
        s.add(
            _fakta(
                "poly.dataset",
                "recorder",
                {"paired": {"path": "/var/lib/poly-research/paired", "files": 2571, "status": "ok"}},
            )
        )
        s.add(_fakta("poly.akses", "cakupan", {"arm_jsonl": "ok", "dataset_paired": "ok"}))
    body = client.get("/api/v1/areas/polymarket", headers=_cookie(sid)).json()
    recorder = [f for f in body["facts"] if f["key"] == "recorder"]
    cakupan = [f for f in body["facts"] if f["key"] == "cakupan"]
    assert len(recorder) == 1 and recorder[0]["kind"] == "poly.dataset"
    assert len(cakupan) == 1 and cakupan[0]["kind"] == "poly.akses"
    assert body["data"]["recorder"]["paired"]["files"] == 2571
    assert body["data"]["cakupan"]["dataset_paired"] == "ok"


def test_json_log_satu_baris(capsys) -> None:
    import logging

    from warroom_api.metrics import setup_json_logging

    setup_json_logging("uji")
    logging.getLogger("uji").warning("halo %s", "dunia")
    keluar = capsys.readouterr().out.strip().splitlines()[-1]
    data = json.loads(keluar)
    assert data["svc"] == "uji" and data["level"] == "WARNING" and data["msg"] == "halo dunia"