"""Tes pipeline keluaran (murni, tanpa DB/jaringan)."""

from __future__ import annotations

import json

from warroom_llm.pipeline import evaluate_output, extract_json, insufficient_output, screen_sparse_facts


def test_extract_json_menerima_code_fence() -> None:
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('pembuka {"a": 1} penutup') == {"a": 1}
    assert extract_json("bukan json") is None


def test_insufficient_output_nol_angka() -> None:
    teks = json.dumps(insufficient_output("fakta_kurang"))
    assert not any(c.isdigit() for c in teks)


def test_screen_sparse_facts() -> None:
    assert screen_sparse_facts(0, 1).verdict == "insufficient"
    assert screen_sparse_facts(1, 1) is None


def test_narrator_ok_dengan_kutipan() -> None:
    out = json.dumps({"kalimat": [{"teks": "n=1175", "fact_ids": [101]}], "nada": "netral"})
    d = evaluate_output("narrator", out, {101}, {101})
    assert d.verdict == "ok" and d.fact_ids == (101,)


def test_narrator_angka_tanpa_kutipan_ditolak() -> None:
    out = json.dumps({"kalimat": [{"teks": "win 88%", "fact_ids": []}], "nada": "x"})
    d = evaluate_output("narrator", out, {101}, {101})
    assert d.verdict == "rejected"
    assert d.issues[0].startswith("angka_tanpa_fact_id")


def test_fact_id_tidak_diberikan_ditolak() -> None:
    out = json.dumps({"kalimat": [{"teks": "n=1", "fact_ids": [202]}], "nada": "x"})
    d = evaluate_output("narrator", out, {101}, {101, 202})
    assert d.verdict == "rejected"
    assert d.issues[0].startswith("fact_id_tidak_diberikan")


def test_fact_id_tidak_ada_di_db_ditolak() -> None:
    out = json.dumps({"kalimat": [{"teks": "n=1", "fact_ids": [101]}], "nada": "x"})
    d = evaluate_output("narrator", out, {101}, {999})
    assert d.verdict == "rejected"
    assert d.issues[0].startswith("fact_id_tidak_ada")


def test_skema_salah_ditolak() -> None:
    d = evaluate_output("verifier", json.dumps({"setuju": "ya"}), {101}, {101})
    assert d.verdict == "rejected"
    assert d.issues[0].startswith("schema_invalid")


def test_kredensial_ditolak(monkeypatch) -> None:
    monkeypatch.setenv("QONEK_API_KEY", "sk-live-RAHASIA123456")
    d = evaluate_output("narrator", "kunci sk-live-RAHASIA123456", {101}, {101}, env_names=("QONEK_API_KEY",))
    assert d.verdict == "rejected"
    assert d.issues == ("kredensial_terdeteksi",)


def test_verifier_tanpa_angka_boleh_tanpa_kutipan() -> None:
    out = json.dumps({"setuju": False, "alasan": "belum cukup", "fact_ids": [], "tingkat": "kurang"})
    d = evaluate_output("verifier", out, set(), set())
    assert d.verdict == "ok"


def test_anomali_wajib_kutipan() -> None:
    out = json.dumps(
        {"anomali": [{"metrik": "m", "arah": "naik", "magnitudo": 1.0, "fact_ids": []}], "catatan": "x"}
    )
    d = evaluate_output("anomaly", out, {101}, {101})
    assert d.verdict == "rejected"
    assert d.issues[0].startswith("angka_tanpa_fact_id")
