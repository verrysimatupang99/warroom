"""Tes adapter Polymarket/GMGN (P4) — memakai fixture sintetis, tanpa menyentuh /var/lib.

Prinsip yang diuji: sumber tidak terbaca ⇒ **status + alasan**, bukan nol; klaim uang tanpa
verifikasi on-chain ⇒ `terverifikasi=False`; eksekutor tanpa keputusan ⇒ `tidak-bisa-dibandingkan`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from warroom_core.db import Alert, Event, Fact, Job, session_scope
from warroom_worker.adapters import gmgn, poly
from warroom_worker.adapters.io import baca_json, baca_jsonl_ekor, ringkas_dir


@pytest.fixture
def pohon(tmp_path: Path) -> Path:
    """Tiruan struktur /var/lib/poly-* + ~/gmgn-paper/state."""
    dasar = tmp_path / "var_lib"
    for nama in ("poly-paper", "poly-paper-candidate", "poly-paper-fade", "poly-paper-favorite"):
        d = dasar / nama
        d.mkdir(parents=True)
        (d / "execution-paper-shadow-summary.json").write_text(
            json.dumps(
                {
                    "mode": "paper-mirror",
                    "execution": False,
                    "strategy": {"entryLo": 0.7, "entryHi": 0.95, "sideMode": "ahead"},
                    "totals": {"entries": 111, "wins": 93},
                }
            ),
            encoding="utf-8",
        )
        (d / "execution-paper-shadow-state.json").write_text('{"posisi": []}', encoding="utf-8")
        baris = [
            {"kind": "candidate", "key": "btc:1", "status": "entered", "coin": "btc"},
            {"kind": "candidate", "key": "eth:1", "status": "outside_window", "coin": "eth"},
            {"kind": "candidate", "key": "btc:2", "status": "loss_budget", "coin": "btc"},
        ]
        (d / "execution-paper-shadow.jsonl").write_text(
            "\n".join(json.dumps(b) for b in baris) + "\n", encoding="utf-8"
        )

    agen = tmp_path / "poly-agent"
    agen.mkdir()
    (agen / "agent-summary.json").write_text('{"threshold": 0.82}', encoding="utf-8")
    (agen / "agent-lessons.jsonl").write_text(
        json.dumps({"ts": 1, "label": "x", "applied": ["threshold"],
                    "rejected": [{"key": "weights.book", "value": 0.602, "reason": "di_luar_bounds"}]})
        + "\n",
        encoding="utf-8",
    )
    (agen / "agent-upgrades.jsonl").write_text(json.dumps({"ts": 2, "applied": ["threshold"]}) + "\n",
                                               encoding="utf-8")

    riset = tmp_path / "poly-research" / "paired"
    riset.mkdir(parents=True)
    (riset / "a.jsonl").write_text("{}\n", encoding="utf-8")

    pilot = tmp_path / "poly-pilot"
    pilot.mkdir()
    (pilot / "snipe-live-v1-state.json").write_text('{"claimablePayout": 8.62}', encoding="utf-8")
    (pilot / "execution-paper-shadow.jsonl").write_text(
        json.dumps({"kind": "candidate", "key": "btc:1", "status": "feed_or_momentum_unavailable",
                    "coin": "btc"}) + "\n",
        encoding="utf-8",
    )

    gm = tmp_path / "gmgn-paper" / "state"
    gm.mkdir(parents=True)
    (gm / "run_config.json").write_text('{"paper": true}', encoding="utf-8")
    (gm / "cycle.lock").write_text("", encoding="utf-8")
    return tmp_path


# --- io ---------------------------------------------------------------------------------


def test_baca_json_menyertakan_mtime_dan_sha256(pohon: Path) -> None:
    b = baca_json(pohon / "poly-agent" / "agent-summary.json", pakai_sudo=False)
    assert b.ok and b.data == {"threshold": 0.82}
    assert b.mtime is not None and len(b.sha256 or "") == 64


def test_berkas_tidak_ada_statusnya_jujur(pohon: Path) -> None:
    b = baca_json(pohon / "tidak-ada.json", pakai_sudo=False)
    assert b.status == "tidak-ada" and b.data is None


def test_json_rusak_dilaporkan_rusak(pohon: Path) -> None:
    rusak = pohon / "rusak.json"
    rusak.write_text("{bukan json", encoding="utf-8")
    assert baca_json(rusak, pakai_sudo=False).status == "rusak"


def test_baca_jsonl_menghitung_baris_rusak(pohon: Path) -> None:
    f = pohon / "campur.jsonl"
    f.write_text('{"a":1}\nbukan-json\n{"a":2}\n', encoding="utf-8")
    b = baca_jsonl_ekor(f, n=10, pakai_sudo=False)
    assert b.ok and len(b.data) == 2 and b.meta["rusak"] == 1


def test_ringkas_dir_menghitung_berkas(pohon: Path) -> None:
    r = ringkas_dir(pohon / "poly-research" / "paired", pakai_sudo=False)
    assert r["status"] == "ok" and r["files"] == 1 and r["bytes"] > 0


# --- poly.arms --------------------------------------------------------------------------


def test_arms_ringkas_angka_dari_berkas(pohon: Path) -> None:
    a = poly.arms(str(pohon / "var_lib"))
    assert set(a) == {"A-shadow", "B-kandidat", "C-fade", "D-favorit"}
    b = a["B-kandidat"]
    assert b["summary"]["mode"] == "paper-mirror"
    assert b["summary"]["totals"]["entries"] == 111
    # 3 baris: 1 masuk, 2 bukan (outside_window dihitung tolak? tidak: difilter di _keputusan saja)
    assert b["masuk_400_baris"] == 1
    assert b["tolak_400_baris"] == 2
    assert len(b["jsonl_sha256"] or "") == 64


def test_arms_sumber_hilang_bukan_nol(tmp_path: Path) -> None:
    a = poly.arms(str(tmp_path / "kosong"))
    assert a["A-shadow"]["summary"]["status"] == "tidak-ada"
    assert a["A-shadow"]["masuk_400_baris"] is None


def test_agent_ringkas_memisahkan_diterapkan_dan_ditolak(pohon: Path, monkeypatch) -> None:
    import warroom_worker.adapters.poly as p

    monkeypatch.setattr(p, "AGENT_DIR", str(pohon / "poly-agent"))
    r = p.agent_ringkas()
    assert r["summary"]["threshold"] == 0.82
    assert any(d["kunci"] == "weights.book" and d["alasan"] == "di_luar_bounds" for d in r["ditolak_200"])
    assert any(d["kunci"] == "threshold" for d in r["diterapkan_200"])


def test_datasets_ringkas_mencatat_ukuran(pohon: Path, monkeypatch) -> None:
    import warroom_worker.adapters.poly as p

    monkeypatch.setattr(p, "RESEARCH_DIR", str(pohon / "poly-research"))
    d = p.datasets_ringkas()
    assert d["paired"]["files"] == 1


# --- parity -----------------------------------------------------------------------------


def test_parity_drift_menghitung_selisih_hanya_pada_keputusan(pohon: Path) -> None:
    """Status 'tidak mampu menilai' tidak dihitung sebagai keputusan."""
    ex = pohon / "poly-pilot-1"
    ex.mkdir()
    (ex / "execution-paper-shadow.jsonl").write_text(
        "\n".join(
            json.dumps(b)
            for b in (
                {"kind": "candidate", "key": "btc:1", "status": "entered", "coin": "btc"},
                {"kind": "candidate", "key": "eth:9", "status": "outside_price_band", "coin": "eth"},
            )
        )
        + "\n",
        encoding="utf-8",
    )
    d = poly.parity_drift(
        mirror_dir=str(pohon / "var_lib" / "poly-paper-candidate"), executor_dir=str(ex), n=50
    )
    assert d.status == "ok"
    # mirror: entered(btc:1) + outside_window(eth:1) + loss_budget(btc:2) = 3 keputusan
    assert d.mirror_n == 3
    assert d.executor_n == 2  # entered(btc:1) + outside_price_band(eth:9)
    assert d.drift == 3  # 2 hanya-mirror + 1 hanya-eksekutor
    assert any("outside_window" in c for c in d.contoh)


def test_status_tidak_mampu_tidak_dihitung_sebagai_keputusan(pohon: Path) -> None:
    """feed_or_momentum_unavailable bukan keputusan — kalau dihitung, drift jadi palsu."""
    baris = [
        {"kind": "candidate", "key": "btc:1", "status": "feed_or_momentum_unavailable", "coin": "btc"},
        {"kind": "candidate", "key": "btc:2", "status": "empty_book", "coin": "btc"},
        {"kind": "candidate", "key": "btc:3", "status": "entered", "coin": "btc"},
    ]
    assert poly._keputusan(baris) == {("btc:3", "entered"): 1}
    assert poly.ringkas_status(baris) == {"masuk": 1, "tolak": 0, "tidak-mampu": 2, "lain": 0}


def test_parity_drift_tanpa_keputusan_eksekutor_tidak_mengarang(pohon: Path) -> None:
    """Eksekutor hanya mencatat 'tidak mampu' ⇒ tidak bisa dibandingkan, bukan drift 0."""
    ex = pohon / "poly-pilot-2"
    ex.mkdir()
    (ex / "execution-paper-shadow.jsonl").write_text(
        json.dumps({"key": "btc:1", "status": "feed_or_momentum_unavailable"}) + "\n",
        encoding="utf-8",
    )
    d = poly.parity_drift(
        mirror_dir=str(pohon / "var_lib" / "poly-paper-candidate"), executor_dir=str(ex), n=50
    )
    assert d.status == "tidak-bisa-dibandingkan"
    assert d.executor_n == 0
    assert "tidak bisa dihitung" in d.detail
    assert "tidak-mampu" in d.detail


def test_parity_drift_sumber_tidak_ada(pohon: Path) -> None:
    d = poly.parity_drift(mirror_dir=str(pohon / "kosong"), executor_dir=str(pohon / "kosong2"))
    assert d.status == "tidak-bisa-dibandingkan" and "mirror=tidak-ada" in d.detail


# --- rekonsiliasi -----------------------------------------------------------------------


def test_klaim_tanpa_rpc_tidak_pernah_dianggap_terverifikasi(pohon: Path, monkeypatch) -> None:
    monkeypatch.delenv("WARROOM_POLYGON_RPC", raising=False)
    r = poly.reconcile_klaim(pilot_dir=str(pohon / "poly-pilot"))
    assert r["status"] == "ok"
    assert r["klaim"] == 8.62
    assert r["terverifikasi"] is False
    assert "BELUM terverifikasi" in r["keterangan"]
    assert r["saldo_onchain"]["status"] == "tidak-dikonfigurasi"


def test_klaim_nol_dengan_rpc_ok_dianggap_cocok(pohon: Path, monkeypatch) -> None:
    monkeypatch.setenv("WARROOM_POLYGON_RPC", "http://127.0.0.1:9")
    (pohon / "poly-pilot" / "snipe-live-v1-state.json").write_text('{"claimablePayout": 0}',
                                                                  encoding="utf-8")
    # RPC tidak bisa dihubungi → tetap belum terverifikasi (tidak menyimpulkan dari kegagalan)
    r = poly.reconcile_klaim(pilot_dir=str(pohon / "poly-pilot"), alamat="0xabc")
    assert r["terverifikasi"] is False
    assert r["saldo_onchain"]["status"] == "gagal"


def test_reconcile_state_hilang(pohon: Path) -> None:
    r = poly.reconcile_klaim(pilot_dir=str(pohon / "kosong"))
    assert r["status"] == "tidak-ada" and r["terverifikasi"] is False


# --- gmgn -------------------------------------------------------------------------------


def test_gmgn_ringkas_membaca_state_lokal(pohon: Path, monkeypatch) -> None:
    monkeypatch.setattr(gmgn, "GMGN_STATE", str(pohon / "gmgn-paper" / "state"))
    r = gmgn.gmgn_ringkas()
    assert r["status"] == "ok"
    assert r["isi"]["run_config.json"] == {"paper": True}


def test_radar_ditandai_sebagai_cache(pohon: Path) -> None:
    cache = pohon / "radar_cache.json"
    cache.write_text('{"window": {}}', encoding="utf-8")
    r = gmgn.radar_ringkas(str(cache))
    assert r["status"] == "ok"
    assert r["sumber"] == "cache", "harus jelas ini cache, bukan bacaan langsung dari Azure"


# --- job handler ------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _bersihkan_job(db):
    from warroom_core.db import Strategy

    with session_scope() as s:
        for row in s.query(Job).all():
            s.delete(row)
        s.query(Fact).delete()
        s.query(Alert).delete()
        s.query(Event).delete()
        s.query(Strategy).delete()
    yield


def test_job_poly_sync_menulis_fakta_dan_mencatat_ketidakpastian(pohon: Path, monkeypatch) -> None:
    from warroom_worker import schedule
    from warroom_worker.jobs import register_handlers

    register_handlers()
    import warroom_worker.adapters.poly as p

    monkeypatch.setattr(p, "AGENT_DIR", str(pohon / "poly-agent"))
    monkeypatch.setattr(p, "RESEARCH_DIR", str(pohon / "poly-research"))

    with session_scope() as s:
        schedule.ensure_jobs(s)
        job = s.scalar(__import__("sqlalchemy").select(Job).where(Job.name == "poly-sync"))
        job.payload_json = {"base": str(pohon / "var_lib"), "ttl_s": 900}
        status, detail = schedule.run_one(s, job)
    assert status == "ok"
    assert "arm=4" in detail
    with session_scope() as s:
        kinds = {k for (k,) in s.query(Fact.kind).distinct()}
    assert {"poly.arm", "poly.agent", "poly.dataset"} <= kinds


def test_job_reconcile_membuat_alert_klaim_belum_terverifikasi(pohon: Path, monkeypatch) -> None:
    from sqlalchemy import select
    from warroom_worker import schedule
    from warroom_worker.jobs import register_handlers

    register_handlers()
    import warroom_worker.adapters.poly as p

    monkeypatch.setattr(p, "PILOT_DIR", str(pohon / "poly-pilot"))
    with session_scope() as s:
        schedule.ensure_jobs(s)
        job = s.scalar(select(Job).where(Job.name == "reconcile"))
        status, detail = schedule.run_one(s, job)
    assert status == "ok"
    assert "terverifikasi=False" in detail
    with session_scope() as s:
        al = s.query(Alert).filter_by(subject="poly/klaim-uang").all()
        assert len(al) == 1
        assert "on-chain" in al[0].suggested_action


def test_job_parity_tidak_alert_saat_tidak_bisa_dibandingkan(pohon: Path, monkeypatch) -> None:
    from sqlalchemy import select
    from warroom_worker import schedule
    from warroom_worker.jobs import register_handlers

    register_handlers()
    import warroom_worker.adapters.poly as p

    monkeypatch.setattr(p, "PILOT_DIR", str(pohon / "kosong"))
    with session_scope() as s:
        schedule.ensure_jobs(s)
        job = s.scalar(select(Job).where(Job.name == "parity-drift"))
        status, detail = schedule.run_one(s, job)
    assert status == "ok"
    assert "tidak-bisa-dibandingkan" in detail
    with session_scope() as s:
        assert s.query(Alert).filter_by(subject="poly/parity-drift").count() == 0

# --- W2: verdict favorit dari alat Poly (baca-saja) ------------------------------------


def _proc(returncode: int, stdout: str = "", stderr: str = ""):
    import types

    return types.SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_verdict_favorit_parse_json(monkeypatch) -> None:
    """Keluaran JSON alat → status ok, nilai apa adanya (tanpa hitung ulang)."""
    import subprocess

    isi = json.dumps(
        {
            "coins": ["btc", "eth"], "windows": 4938, "n": 3977, "wins": 3107,
            "winRate": 78.12, "ask": 0.7662, "breakEven": 76.62, "evPerStake": 1.96,
            "ci95": [76.59, 79.57], "deff": 1.345, "rho": 0.412, "nEff": 2957,
            "verdict": "NOT_PROVEN", "nNeeded": 8266,
        }
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _proc(0, stdout=isi + "\n"))
    v = poly.verdict_favorit()
    assert v["status"] == "ok"
    assert v["value"]["n"] == 3977 and v["value"]["deff"] == 1.345
    assert v["sumber"].endswith("favorite-live-verdict.py")


def test_verdict_favorit_tidak_izin_bukan_nol(monkeypatch) -> None:
    """Gagal sudo → status `tidak-izin` + alasan; tidak pernah mengarang angka."""
    import subprocess

    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _proc(1, stderr="sudo: a password is required")
    )
    v = poly.verdict_favorit()
    assert v["status"] == "tidak-izin"
    assert "value" not in v


def test_job_verdict_sync_menerbitkan_fakta(db, monkeypatch) -> None:
    """Job menerbitkan fakta `verdict` dengan kontrak GateBlok: be pecahan + ci 95% + deff."""
    from sqlalchemy import select
    from warroom_worker import schedule
    from warroom_worker.jobs import register_handlers

    register_handlers()
    import warroom_worker.adapters.poly as p

    contoh = {
        "coins": ["btc", "eth"], "windows": 4938, "n": 3977, "wins": 3107,
        "winRate": 78.12, "ask": 0.7662, "breakEven": 76.62, "evPerStake": 1.96,
        "ci95": [76.59, 79.57], "deff": 1.345, "rho": 0.412, "nEff": 2957,
        "verdict": "NOT_PROVEN", "nNeeded": 8266,
    }
    monkeypatch.setattr(
        p, "verdict_favorit", lambda **k: {"status": "ok", "value": contoh, "sumber": p.VERDICT_SCRIPT}
    )

    with session_scope() as s:
        schedule.ensure_jobs(s)
        job = s.scalar(select(Job).where(Job.name == "verdict-sync"))
        status, detail = schedule.run_one(s, job)
    assert status == "ok", detail
    with session_scope() as s:
        f = s.scalar(select(Fact).where(Fact.kind == "poly.verdict"))
    assert f is not None and f.key == "verdict"
    v = f.value_json
    assert v["n"] == 3977 and v["win"] == 3107
    assert v["be"] == pytest.approx(0.7662, abs=1e-9), "BE harus pecahan 0..1 (kontrak gate)"
    assert v["ci"] == 0.95 and v["deff"] == pytest.approx(1.345)
    assert v["split"] is None, "split hanya boleh dibekukan manusia, bukan agen"
    assert v["verdict_alat"] == "NOT_PROVEN"


def test_job_verdict_sync_gagal_baca_status_jujur(db, monkeypatch) -> None:
    from sqlalchemy import select
    from warroom_worker import schedule
    from warroom_worker.jobs import register_handlers

    register_handlers()
    import warroom_worker.adapters.poly as p

    monkeypatch.setattr(
        p,
        "verdict_favorit",
        lambda **k: {"status": "tidak-izin", "detail": "sudo", "sumber": p.VERDICT_SCRIPT},
    )
    with session_scope() as s:
        schedule.ensure_jobs(s)
        job = s.scalar(select(Job).where(Job.name == "verdict-sync"))
        status, _ = schedule.run_one(s, job)
    assert status == "ok"
    with session_scope() as s:
        f = s.scalar(select(Fact).where(Fact.kind == "poly.verdict"))
    assert f.value_json["status"] == "tidak-izin"
    assert "be" not in f.value_json, "tidak boleh ada angka saat sumber tidak terbaca"
