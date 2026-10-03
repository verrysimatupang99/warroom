"""Tes validasi skema keluaran per peran (pydantic strict)."""

from __future__ import annotations

from warroom_llm.schemas import ROLE_MODELS, validate_output


def test_tiga_peran_punya_skema() -> None:
    assert set(ROLE_MODELS) == {"narrator", "verifier", "anomaly"}


def test_narrator_sah() -> None:
    out, issues = validate_output(
        "narrator", {"kalimat": [{"teks": "n=1", "fact_ids": [1]}], "nada": "netral"}
    )
    assert issues == []
    assert out == {"kalimat": [{"teks": "n=1", "fact_ids": [1]}], "nada": "netral"}


def test_boolean_string_ditolak_strict() -> None:
    # Tanpa strict, pydantic mengubah "true" menjadi True — itu bug yang harus dicegah.
    out, issues = validate_output(
        "verifier", {"setuju": "true", "alasan": "ok", "fact_ids": [1], "tingkat": "yakin"}
    )
    assert out is None
    assert issues and issues[0].startswith("schema_invalid")


def test_kunci_tambahan_ditolak() -> None:
    out, issues = validate_output(
        "verifier", {"setuju": True, "alasan": "ok", "fact_ids": [1], "tingkat": "yakin", "extra": 1}
    )
    assert out is None and issues


def test_tingkat_enum_dibatasi() -> None:
    out, issues = validate_output(
        "verifier", {"setuju": True, "alasan": "ok", "fact_ids": [1], "tingkat": "mungkin"}
    )
    assert out is None and issues


def test_magnitudo_int_diterima_boolean_ditolak() -> None:
    out, issues = validate_output(
        "anomaly",
        {"anomali": [{"metrik": "m", "arah": "naik", "magnitudo": 2, "fact_ids": [1]}], "catatan": "x"},
    )
    assert issues == []
    assert isinstance(out["anomali"][0]["magnitudo"], float)

    out2, issues2 = validate_output(
        "anomaly",
        {"anomali": [{"metrik": "m", "arah": "naik", "magnitudo": True, "fact_ids": [1]}], "catatan": "x"},
    )
    assert out2 is None and issues2


def test_magnitudo_string_angka_diterima_kata_ditolak() -> None:
    """Regresi: model sering mengirim magnitudo sebagai string ("2.0"). Itu angka yang sama,
    jadi diterima; tetapi kata seperti "tinggi" TETAP ditolak — menerimanya berarti mengarang
    besaran yang tidak ada di fakta."""
    out, issues = validate_output(
        "anomaly",
        {"anomali": [{"metrik": "m", "arah": "naik", "magnitudo": "2.0", "fact_ids": [1]}],
         "catatan": "x"},
    )
    assert issues == []
    assert out["anomali"][0]["magnitudo"] == 2.0

    out2, issues2 = validate_output(
        "anomaly",
        {"anomali": [{"metrik": "m", "arah": "naik", "magnitudo": "tinggi", "fact_ids": [1]}],
         "catatan": "x"},
    )
    assert out2 is None and issues2


def test_peran_tidak_dikenal() -> None:
    out, issues = validate_output("entah", {})
    assert out is None
    assert issues == ["peran_tidak_dikenal:entah"]
