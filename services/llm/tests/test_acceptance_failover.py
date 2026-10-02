"""Acceptance (a): failover nutaraline → qonek, tercatat di ``llm_calls``.

nutaraline dibuat gagal (HTTP 500 / timeout) lewat MockTransport; permintaan harus tetap
dilayani qonek dan ``fallback_from`` terekam.
"""

from __future__ import annotations

import json
import re

import httpx
from sqlalchemy import select
from warroom_core.db import LLMCall, session_scope
from warroom_llm.facts import FactRef
from warroom_llm.gateway import CallRequest


def _pesan_benar(fact_id: int) -> str:
    return json.dumps(
        {"kalimat": [{"teks": "win rate 79.0% pada n=1175.", "fact_ids": [fact_id]}], "nada": "netral"}
    )


def _rows() -> list[LLMCall]:
    with session_scope() as s:
        return list(s.scalars(select(LLMCall).order_by(LLMCall.id)))


def test_failover_http_500_dilayani_provider_kedua(gateway_factory, fakta, bersih_llm, jawaban) -> None:
    fid = fakta(1)[0]
    fakta_ref = (FactRef(fid, "F1", "n=1175, win=79.0%"),)
    hitungan = {"nutaraline": 0, "qonek": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host or ""
        if "nutaraline" in host:
            hitungan["nutaraline"] += 1
            return httpx.Response(500, json={"error": "boom"})
        hitungan["qonek"] += 1
        return jawaban(_pesan_benar(fid))

    gw = gateway_factory(handler)
    hasil = gw.call(CallRequest(role="narrator", facts=fakta_ref, user="ringkas"))

    assert hasil.status == "ok"
    assert hasil.provider == "qonek"
    assert hasil.fallback_from == "nutaraline"
    assert hasil.fact_ids == (fid,)
    # provider utama dicoba ulang (attempts=2) sebelum menyerah ke fallback
    assert hitungan["nutaraline"] == 2
    assert hitungan["qonek"] == 1

    rows = _rows()
    assert any(r.provider == "nutaraline" and r.ok is False and r.error_code == "http_500" for r in rows)
    sukses = [r for r in rows if r.ok is True]
    assert sukses and sukses[0].provider == "qonek"
    assert sukses[0].fallback_from == "nutaraline"
    assert sukses[0].role == "narrator"
    assert sukses[0].prompt_version == "narrator/1.0.0"
    assert sukses[0].result_hash
    assert sukses[0].fact_ids == [fid]


def test_failover_timeout_dilayani_provider_kedua(gateway_factory, fakta, bersih_llm, jawaban) -> None:
    fid = fakta(1)[0]
    fakta_ref = (FactRef(fid, "F1", "n=1175"),)

    def handler(request: httpx.Request) -> httpx.Response:
        if "nutaraline" in (request.url.host or ""):
            raise httpx.ReadTimeout("habis waktu")
        return jawaban(_pesan_benar(fid))

    gw = gateway_factory(handler)
    hasil = gw.call(CallRequest(role="narrator", facts=fakta_ref, user="ringkas"))

    assert hasil.status == "ok" and hasil.provider == "qonek"
    assert hasil.fallback_from == "nutaraline"
    assert any(r.provider == "nutaraline" and r.error_code == "timeout" for r in _rows())


def test_kedua_provider_gagal_insufficient_tanpa_angka(gateway_factory, fakta, bersih_llm) -> None:
    fid = fakta(1)[0]
    fakta_ref = (FactRef(fid, "F1", "n=1175"),)

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host or ""
        if "nutaraline" in host:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(503, json={"error": "tutup"})

    gw = gateway_factory(handler)
    hasil = gw.call(CallRequest(role="narrator", facts=fakta_ref, user="ringkas"))

    assert hasil.status == "insufficient"
    assert hasil.error_code == "semua_provider_gagal"
    assert not re.search(r"\d", json.dumps(hasil.output)), "insufficient tidak boleh memuat angka baru"
    assert hasil.output is not None and hasil.output["status"] == "insufficient"
    rows = _rows()
    assert any(r.provider == "nutaraline" and r.error_code == "http_500" for r in rows)
    assert any(r.provider == "qonek" and r.error_code == "http_503" for r in rows)
