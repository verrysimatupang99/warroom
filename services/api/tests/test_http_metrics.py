"""Tes metrik HTTP in-process: hitungan, error 5xx, dan p95."""

from __future__ import annotations

from warroom_api import metrics


def _reset() -> None:
    with metrics._HTTP_LOCK:
        metrics._HTTP_TOTAL = 0
        metrics._HTTP_ERRORS = 0
        metrics._HTTP_DURASI.clear()


def test_record_http_menghitung_total_error_dan_p95() -> None:
    _reset()
    for i in range(1, 21):
        metrics.record_http(500 if i == 20 else 200, i / 1000.0)
    snap = metrics.http_snapshot()
    assert snap["requests_total"] == 20
    assert snap["errors_total"] == 1
    assert snap["error_rate"] == 0.05
    assert 18.0 <= snap["latency_p95_ms"] <= 20.5
