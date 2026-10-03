"""Tes pencatatan ``llm_calls`` dan anggaran harian."""

from __future__ import annotations

import json

import httpx
from sqlalchemy import select
from warroom_core.db import LLMCall, session_scope
from warroom_llm.facts import FactRef
from warroom_llm.gateway import CallRequest


def test_setiap_panggilan_tercatat_lengkap(gateway_factory, fakta, bersih_llm, jawaban) -> None:
    fid = fakta(1)[0]
    fakta_ref = (FactRef(fid, "F1", "n=1175, win=79.0%"),)
    sah = json.dumps({"kalimat": [{"teks": "win 79.0% n=1175.", "fact_ids": [fid]}], "nada": "netral"})

    def handler(request: httpx.Request) -> httpx.Response:
        return jawaban(sah, tokens=(123, 45))

    gw = gateway_factory(handler)
    hasil = gw.call(CallRequest(role="narrator", facts=fakta_ref))
    assert hasil.status == "ok"

    with session_scope() as s:
        row = s.scalars(select(LLMCall).order_by(LLMCall.id.desc())).first()
    assert row is not None
    assert row.role == "narrator"
    assert row.provider == "nutaraline"
    assert row.model == "mimo-v2.6-flash"
    assert row.prompt_version == "narrator/1.0.0"
    assert row.tokens_in == 123 and row.tokens_out == 45
    assert row.cost_usd is not None and float(row.cost_usd) > 0
    assert row.latency_ms is not None and row.latency_ms >= 0
    assert row.ok is True
    assert row.fallback_from is None
    assert row.result_hash and len(row.result_hash) == 64
    assert row.fact_ids == [fid]


def test_anggaran_harian_memblokir_peran_non_esensial(gateway_factory, config_factory, bersih_llm) -> None:
    cfg = config_factory(budget={"dailyUsd": 0.0, "perRoleDailyUsd": {}})
    dipanggil = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        dipanggil["n"] += 1
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    gw = gateway_factory(handler, config=cfg)
    hasil = gw.call(CallRequest(role="verifier", user="periksa klaim", min_facts=0))

    assert hasil.status == "insufficient"
    assert hasil.error_code == "budget_terlampaui"
    assert dipanggil["n"] == 0
    assert not any(c.isdigit() for c in json.dumps(hasil.output))


def test_narrator_tetap_jalan_saat_anggaran_habis(
    gateway_factory, config_factory, fakta, bersih_llm, jawaban
) -> None:
    cfg = config_factory(budget={"dailyUsd": 0.0, "perRoleDailyUsd": {}})
    fid = fakta(1)[0]
    fakta_ref = (FactRef(fid, "F1", "n=1175"),)
    sah = json.dumps({"kalimat": [{"teks": "n=1175", "fact_ids": [fid]}], "nada": "netral"})

    def handler(request: httpx.Request) -> httpx.Response:
        return jawaban(sah)

    gw = gateway_factory(handler, config=cfg)
    hasil = gw.call(CallRequest(role="narrator", facts=fakta_ref))
    assert hasil.status == "ok", "peran baca esensial tidak boleh dijeda oleh anggaran"


def test_kode_galat_panjang_dipotong_sebelum_dicatat(gateway_factory, bersih_llm) -> None:
    """Regresi produksi: kode galat validasi skema bisa > 60 karakter, sedangkan kolom
    `llm_calls.error_code` varchar(60). Insert-nya dulu meledak (DataError) sehingga
    kegagalan justru TIDAK tercatat dan job ikut gagal — kode harus dipotong, bukan
    dibiarkan menggagalkan pencatatan itu sendiri."""
    gw = gateway_factory(lambda request: httpx.Response(200, json={}))
    panjang = "schema_invalid:kalimat.0.fact_ids.0:Input should be a valid integer"
    assert len(panjang) > 60  # kondisi yang dulu memicu galat

    gw._log(role="narrator", provider="kiyara", model="m", ok=False, error_code=panjang)

    with session_scope() as s:
        row = s.scalars(select(LLMCall).order_by(LLMCall.id.desc())).first()
    assert row is not None and row.ok is False
    assert row.error_code is not None
    assert len(row.error_code) == 60
    assert row.error_code.startswith("schema_invalid:")
