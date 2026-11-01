"""Tes ambang SLO: kondisi normal tidak menghasilkan temuan, pelanggaran menghasilkan."""

from __future__ import annotations

from warroom_worker.jobs.infra import evaluate_slo


def test_semua_normal_tanpa_temuan() -> None:
    assert evaluate_slo(disk_pct=50, backup_age_h=3, drill_age_d=5, api_ok=True) == []


def test_disk_warn_dan_crit() -> None:
    warn = evaluate_slo(disk_pct=81, backup_age_h=1, drill_age_d=1, api_ok=True)
    assert [(t["kode"], t["severity"]) for t in warn] == [("disk", "warning")]
    crit = evaluate_slo(disk_pct=92, backup_age_h=1, drill_age_d=1, api_ok=True)
    assert [(t["kode"], t["severity"]) for t in crit] == [("disk", "critical")]


def test_backup_drill_dan_api() -> None:
    temuan = evaluate_slo(disk_pct=50, backup_age_h=30, drill_age_d=40, api_ok=False)
    assert {t["kode"] for t in temuan} == {"backup", "drill", "api"}


def test_backup_tidak_ada_dihitung_pelanggaran() -> None:
    temuan = evaluate_slo(disk_pct=50, backup_age_h=None, drill_age_d=None, api_ok=True)
    assert {t["kode"] for t in temuan} == {"backup", "drill"}


def test_latency_dan_error_rate_di_atas_ambang() -> None:
    temuan = evaluate_slo(
        disk_pct=50, backup_age_h=1, drill_age_d=1, api_ok=True,
        p95_ms=1500, requests_total=100, error_rate=0.02,
    )
    assert {t["kode"] for t in temuan} == {"latency", "error_rate"}


def test_request_sedikit_tidak_divonis() -> None:
    temuan = evaluate_slo(
        disk_pct=50, backup_age_h=1, drill_age_d=1, api_ok=True,
        p95_ms=5000, requests_total=5, error_rate=1.0,
    )
    assert temuan == []
