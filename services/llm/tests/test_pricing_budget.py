"""Regresi: akuntansi biaya & anggaran harian pada konfigurasi EFEKTIF produksi.

Latar (bug yang ditutup): `default_config()` (bentuk baku yang dipakai saat
`/etc/warroom/llm.json` tidak ada) TIDAK memuat blok `pricing`. Akibatnya
`Gateway._cost()` selalu `None`, kolom `llm_calls.cost_usd` selalu NULL, dan
`_budget_blocked()` yang menjumlahkan `SUM(cost_usd)` selalu bernilai 0 sehingga
anggaran harian (mis. $3) tidak pernah terpicu (fail-open).

Fixture tes (`conftest._config_dict`) menyisipkan `pricing`, sehingga tes lama
(`test_gateway_logging.py`) hijau padahal produksi rusak. Tes di berkas ini
mengunci jalur produksi yang sebenarnya.

Butuh fixture `db`/`bersih_llm` (lihat conftest root & services/llm/tests/conftest.py).
"""

from __future__ import annotations

import json

import httpx
from sqlalchemy import select
from warroom_core.db import LLMCall, session_scope
from warroom_llm.config import LLMConfig, default_config
from warroom_llm.facts import FactRef
from warroom_llm.gateway import CallRequest, Gateway
from warroom_llm.prompts import PromptRegistry

# --- Gerbang bentuk: konfigurasi efektif produksi WAJIB punya harga ---------------


def test_default_config_punya_pricing_untuk_semua_provider(tmp_path, monkeypatch) -> None:
    """Bentuk baku (tanpa berkas root) harus punya harga untuk SETIAP provider.

    Tanpa ini, anggaran tidak bisa ditegakkan sama sekali di produksi.
    """
    monkeypatch.setenv("WARROOM_LLM_CONFIG", str(tmp_path / "tidak-ada.json"))
    cfg = default_config()
    tanpa_harga = [p.name for p in cfg.chain() if p.name not in cfg.pricing]
    assert not tanpa_harga, (
        f"provider tanpa `pricing`: {tanpa_harga} — anggaran harian tidak akan pernah "
        "terpicu (fail-open). Isi `pricing` di default_config()."
    )


def test_load_menolak_konfigurasi_produksi_tanpa_pricing(tmp_path, monkeypatch) -> None:
    """Gerban anti fail-open: berkas produksi tanpa `pricing` tidak boleh lolos DIAM-DIAM.

    Desain yang dipilih: `load` TIDAK melempar (itu akan mematikan gateway saat startup),
    melainkan menandai `budget_fail_closed` — dan runtime memblokir peran non-eksempt.
    Yang diuji di sini: flag itu menyala saat harga tak lengkap.
    """
    p = tmp_path / "llm.json"
    p.write_text(
        json.dumps(
            {
                "primary": "x",
                "budget": {"dailyUsd": 3.0},
                "providers": [{"name": "x", "baseUrl": "https://x.example/v1",
                               "keyEnv": "X_KEY", "models": {"fast": "m"}}],
            }
        ),
        encoding="utf-8",
    )
    cfg = LLMConfig.load(p)
    # Harga kosong → fail-closed menyala; anggaran tidak bisa ditegakkan.
    assert cfg.budget_fail_closed is True
    assert [pr.name for pr in cfg.chain() if pr.name not in cfg.pricing] == ["x"]


def test_load_menerima_konfigurasi_dengan_pricing(tmp_path) -> None:
    """Kontrol positif: berkas ber-`pricing` tetap dimuat seperti biasa."""
    p = tmp_path / "llm.json"
    p.write_text(
        json.dumps(
            {
                "primary": "x",
                "budget": {"dailyUsd": 3.0},
                "providers": [{"name": "x", "baseUrl": "https://x.example/v1",
                               "keyEnv": "X_KEY", "models": {"fast": "m"}}],
                "pricing": {"x": {"in": 0.001, "out": 0.002}},
            }
        ),
        encoding="utf-8",
    )
    cfg = LLMConfig.load(p)
    assert cfg.pricing["x"]["in"] == 0.001


# --- Jalur produksi: anggaran ber-nilai nyata harus terpicu -----------------------


def _gateway_produksi(handler, *, budget: float, pricing: dict | None = None) -> Gateway:
    """Gateway dari default_config() efektif (bentuk baku), deng/ tanpa pricing."""
    import os

    os.environ.pop("WARROOM_LLM_CONFIG", None)
    base = default_config()
    overrides = {"budget_daily_usd": budget}
    if pricing is not None:
        overrides["pricing"] = pricing
    cfg = LLMConfig(**{**base.__dict__, **overrides})
    prompts = PromptRegistry.from_dir(
        __import__("pathlib").Path(__file__).resolve().parents[3] / "prompts"
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return Gateway(cfg, prompts, http_client=client, sleep=lambda _s: None)


def _handler_verifier(fact_id: int, tokens: tuple[int, int]):
    content = json.dumps(
        {"setuju": True, "alasan": "win 79.0% didukung fakta", "fact_ids": [fact_id],
         "tingkat": "yakin"}
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": tokens[0], "completion_tokens": tokens[1]},
            },
        )

    return handler


def test_anggaran_terpicu_pada_konfigurasi_efektif_produksi(
    fakta, bersih_llm
) -> None:
    """Anggaran $3 harus menghentikan panggilan berikutnya bila biaya benar-benar dihitung.

    Regresi: pada kode lama `pricing` kosong -> SUM(cost_usd)=0 -> 5 panggilan @10jt token
    semuanya `ok` dan tidak pernah diblokir.
    """
    fid = fakta(1)[0]
    faktaref = (FactRef(fid, "F1", "n=1175, win=79.0%"),)
    gw = _gateway_produksi(
        _handler_verifier(fid, (5_000_000, 5_000_000)),
        budget=3.0,
        pricing={"nutaraline": {"in": 0.001, "out": 0.002},
                 "qonek": {"in": 0.001, "out": 0.002}},
    )

    codes = []
    for _ in range(5):
        r = gw.call(CallRequest(role="verifier", facts=faktaref, user="periksa",
                                min_facts=0, use_cache=False))
        codes.append(r.error_code)

    assert "budget_terlampaui" in codes, (
        "anggaran $3 tidak pernah terpicu meski tiap panggilan 10 juta token — "
        f"error_code berurutan: {codes}"
    )
    with session_scope() as s:
        total = float(s.scalar(select(__import__("sqlalchemy").func.coalesce(
            __import__("sqlalchemy").func.sum(LLMCall.cost_usd), 0))) or 0)
    assert total > 3.0, f"SUM(cost_usd)={total} — biaya tidak terakumulasi"


def test_biaya_tercatat_bukan_none_pada_konfigurasi_produksi(fakta, bersih_llm) -> None:
    """Keluaran sukses harus meninggalkan cost_usd non-NULL & > 0 (jalur produksi)."""
    fid = fakta(1)[0]
    faktaref = (FactRef(fid, "F1", "n=1175, win=79.0%"),)
    gw = _gateway_produksi(
        _handler_verifier(fid, (123, 45)),
        budget=3.0,
        pricing={"nutaraline": {"in": 0.001, "out": 0.002},
                 "qonek": {"in": 0.001, "out": 0.002}},
    )
    r = gw.call(CallRequest(role="verifier", facts=faktaref, user="periksa",
                            min_facts=0, use_cache=False))
    assert r.status == "ok"
    assert r.cost_usd is not None and r.cost_usd > 0
    with session_scope() as s:
        row = s.scalars(select(LLMCall).order_by(LLMCall.id.desc())).first()
    assert row is not None and row.cost_usd is not None and float(row.cost_usd) > 0


# --- Penjaga kebijakan: perbaikan tidak boleh over-blocking -----------------------


def test_narrator_tetap_jalan_saat_anggaran_habis(fakta, bersih_llm) -> None:
    """`narrator` esensial tetap `ok` walau anggaran habis (EXEMPT_BUDGET_ROLES)."""
    fid = fakta(1)[0]
    content = json.dumps({"kalimat": [{"teks": "n=1175", "fact_ids": [fid]}], "nada": "netral"})

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}],
                                         "usage": {"prompt_tokens": 10, "completion_tokens": 5}})

    gw = _gateway_produksi(handler, budget=0.0,
                           pricing={"nutaraline": {"in": 0.001, "out": 0.002}})
    r = gw.call(CallRequest(role="narrator", facts=(FactRef(fid, "F1", "n=1175"),),
                            use_cache=False))
    assert r.status == "ok", "peran baca esensial tidak boleh dijeda anggaran"


def test_fail_closed_tidak_menyala_bila_pricing_lengkap(fakta, bersih_llm) -> None:
    """Penjaga fail-closed TIDAK boleh menyala saat harga lengkap & anggaran wajar.

    Ini penjaga anti over-blocking: perbaikan fail-closed hanya boleh aktif ketika
    provider benar-benar tak punya harga. Kalau `pricing` lengkap, pemanggilan normal
    harus jalan seperti sebelumnya.

    (Catatan semantik yang ada: `budget_daily_usd=0` berarti "0 boleh dipakai" = blokir
    semua — itu perilaku lama, bukan efek perbaikan ini.)
    """
    fid = fakta(1)[0]
    gw = _gateway_produksi(
        _handler_verifier(fid, (10, 5)),
        budget=3.0,
        pricing={p.name: {"in": 0.001, "out": 0.002} for p in default_config().chain()},
    )
    r = gw.call(CallRequest(role="verifier", facts=(FactRef(fid, "F1", "n=1175"),),
                            user="periksa", min_facts=0, use_cache=False))
    assert r.error_code != "budget_terlampaui"
