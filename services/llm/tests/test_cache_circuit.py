"""Tes cache hasil (TTL/batas) dan circuit breaker."""

from __future__ import annotations

import json
import re

import httpx
from sqlalchemy import select
from warroom_core.db import LLMCall, session_scope
from warroom_llm.facts import FactRef
from warroom_llm.gateway import CallRequest
from warroom_llm.providers import CircuitBreaker


def test_cache_hasil_dipakai_ulang(gateway_factory, fakta, bersih_llm, jawaban) -> None:
    fid = fakta(1)[0]
    fakta_ref = (FactRef(fid, "F1", "n=1175, win=79.0%"),)
    sah = json.dumps({"kalimat": [{"teks": "win 79.0% n=1175.", "fact_ids": [fid]}], "nada": "netral"})
    hitungan = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        hitungan["n"] += 1
        return jawaban(sah)

    gw = gateway_factory(handler)
    a = gw.call(CallRequest(role="narrator", facts=fakta_ref))
    b = gw.call(CallRequest(role="narrator", facts=fakta_ref))

    assert a.status == "ok" and b.status == "ok"
    assert hitungan["n"] == 1, "panggilan kedua harus dilayani cache"
    assert b.cached is True
    assert b.result_hash == a.result_hash
    with session_scope() as s:
        rows = list(s.scalars(select(LLMCall).order_by(LLMCall.id)))
    assert rows[-1].provider == "cache"


def test_cache_miss_untuk_fakta_berbeda(gateway_factory, fakta, bersih_llm, jawaban) -> None:
    ids = fakta(2)
    hitungan = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        # Selalu kutip fact_id yang benar-benar diinjeksi pada permintaan ini.
        hitungan["n"] += 1
        system = json.loads(request.content.decode("utf-8"))["messages"][0]["content"]
        fid = int(re.search(r"fact_id=(\d+)", system).group(1))
        return jawaban(json.dumps({"kalimat": [{"teks": "win 79.0%.", "fact_ids": [fid]}], "nada": "netral"}))

    gw = gateway_factory(handler)
    a = gw.call(CallRequest(role="narrator", facts=(FactRef(ids[0], "F1", "n=1175"),)))
    b = gw.call(CallRequest(role="narrator", facts=(FactRef(ids[1], "F2", "n=1200"),)))
    assert a.status == "ok" and b.status == "ok"
    assert hitungan["n"] == 2, "fakta berbeda harus memanggil provider, bukan cache"


def test_circuit_breaker_buka_dan_tutup_setelah_cooldown() -> None:
    now = [0.0]
    cb = CircuitBreaker(failures=2, window_sec=10, cooldown_sec=30, clock=lambda: now[0])
    assert cb.is_open("p") is False
    cb.record_failure("p")
    assert cb.is_open("p") is False
    cb.record_failure("p")
    assert cb.is_open("p") is True
    now[0] = 31.0
    assert cb.is_open("p") is False  # cooldown lewat → dicoba lagi


def test_gateway_melewati_provider_dengan_sirkuit_terbuka(
    gateway_factory, config_factory, fakta, bersih_llm, jawaban
) -> None:
    cfg = config_factory(
        retry={"attempts": 1, "backoffMs": 0}, circuit={"failures": 2, "windowSec": 120, "cooldownSec": 300}
    )
    fid = fakta(1)[0]
    fakta_ref = (FactRef(fid, "F1", "n=1175"),)
    sah = json.dumps({"kalimat": [{"teks": "n=1175", "fact_ids": [fid]}], "nada": "netral"})
    hitungan = {"nutaraline": 0, "qonek": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "nutaraline" in (request.url.host or ""):
            hitungan["nutaraline"] += 1
            return httpx.Response(500, json={"error": "boom"})
        hitungan["qonek"] += 1
        return jawaban(sah)

    gw = gateway_factory(handler, config=cfg)
    for _ in range(3):
        hasil = gw.call(CallRequest(role="narrator", facts=fakta_ref, use_cache=False))
        assert hasil.status == "ok"

    assert hitungan["nutaraline"] == 2, "setelah 2 kegagalan sirkuit harus terbuka"
    assert hitungan["qonek"] == 3
    with session_scope() as s:
        assert any(r.error_code == "circuit_open" for r in s.scalars(select(LLMCall)).all())
