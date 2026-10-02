"""Acceptance (b): fakta kurang → ``insufficient`` dan NOL angka baru.

Dua jalur dibuktikan: fakta kosong (tanpa memanggil provider), dan jawaban provider yang
mengarang angka tanpa kutipan (ditolak pipeline → ``insufficient``).
"""

from __future__ import annotations

import json
import re

import httpx
from sqlalchemy import select
from warroom_core.db import LLMCall, session_scope
from warroom_llm.facts import FactRef
from warroom_llm.gateway import CallRequest


def _rows() -> list[LLMCall]:
    with session_scope() as s:
        return list(s.scalars(select(LLMCall).order_by(LLMCall.id)))


def test_fakta_kurang_insufficient_tanpa_memanggil_provider(gateway_factory, bersih_llm) -> None:
    dipanggil = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        dipanggil["n"] += 1
        return httpx.Response(500, json={"error": "tidak boleh dipanggil"})

    gw = gateway_factory(handler)
    hasil = gw.call(CallRequest(role="narrator", facts=(), min_facts=1))

    assert hasil.status == "insufficient"
    assert hasil.error_code == "fakta_kurang"
    assert dipanggil["n"] == 0, "provider tidak boleh dipanggil saat fakta kurang"
    assert hasil.output is not None and hasil.output["status"] == "insufficient"
    assert not re.search(r"\d", json.dumps(hasil.output)), "insufficient harus nol angka"
    assert any(r.error_code == "fakta_kurang" for r in _rows())


def test_jawaban_angka_tanpa_grounding_ditolak_insufficient(
    gateway_factory, fakta, bersih_llm, jawaban
) -> None:
    fid = fakta(1)[0]
    fakta_ref = (FactRef(fid, "F1", "n=1175, win=79.0%"),)
    nakal = json.dumps({"kalimat": [{"teks": "win rate 88.8% besok.", "fact_ids": []}], "nada": "x"})

    def handler(request: httpx.Request) -> httpx.Response:
        return jawaban(nakal)

    gw = gateway_factory(handler)
    hasil = gw.call(CallRequest(role="narrator", facts=fakta_ref, min_facts=1))

    assert hasil.status == "insufficient"
    teks = json.dumps(hasil.output)
    assert not re.search(r"\d", teks), "angka karangan tidak boleh bocor ke keluaran"
    assert "88.8" not in teks
    kode = {r.error_code for r in _rows()}
    assert any(k and k.startswith("angka_tanpa_fact_id") for k in kode)


def test_fact_id_yang_tidak_ada_di_db_ditolak(gateway_factory, bersih_llm, jawaban) -> None:
    # fakta dirujuk (diberikan) tetapi TIDAK ada barisnya di DB → keluaran harus ditolak
    fakta_ref = (FactRef(999999, "F9", "n=1"),)
    aman = json.dumps({"kalimat": [{"teks": "n=1 pada klaim.", "fact_ids": [999999]}], "nada": "x"})

    def handler(request: httpx.Request) -> httpx.Response:
        return jawaban(aman)

    gw = gateway_factory(handler)
    hasil = gw.call(CallRequest(role="narrator", facts=fakta_ref, min_facts=1))

    assert hasil.status == "insufficient"
    assert hasil.error_code == "semua_provider_gagal"
    kode = " ".join(r.error_code or "" for r in _rows())
    assert "fact_id_tidak_ada" in kode
    assert not re.search(r"\d", json.dumps(hasil.output))


def test_hasil_sah_menyertakan_fact_id(gateway_factory, fakta, bersih_llm, jawaban) -> None:
    """Kontrol positif: dengan fakta nyata dan kutipan benar, keluaran diterima."""
    fid = fakta(1)[0]
    fakta_ref = (FactRef(fid, "F1", "n=1175, win=79.0%"),)
    sah = json.dumps(
        {"kalimat": [{"teks": "win rate 79.0% pada n=1175.", "fact_ids": [fid]}], "nada": "netral"}
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return jawaban(sah)

    gw = gateway_factory(handler)
    hasil = gw.call(CallRequest(role="narrator", facts=fakta_ref, min_facts=1))

    assert hasil.status == "ok"
    assert hasil.fact_ids == (fid,)
    assert hasil.output["kalimat"][0]["fact_ids"] == [fid]
