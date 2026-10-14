"""Router LLM gateway (P3) — konsol kesehatan, prompt, narasi, verifier.

Diekstrak dari app.py (P1-2). Refactor murni: path, status kode, pembatas laju,
dan auth (operator / optional_user + token layanan) tidak berubah.
"""

from __future__ import annotations

import hmac
import os
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from warroom_core import prompts_dir
from warroom_core.db import User, session_scope

from warroom_api import auth, limits
from warroom_api.areas import AREA_KEYS, latest_facts
from warroom_api.providers import provider_ringkas

router = APIRouter()


@router.get("/api/v1/ai/llm-console")
def llm_console(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
    """Kesehatan provider dari `llm_calls` — tanpa perhitungan manual."""
    from warroom_core.db import LLMCall

    with session_scope() as s:
        total = s.scalar(select(func.count()).select_from(LLMCall)) or 0
        per_provider = provider_ringkas(s)
        per_peran = [
            {"role": r, "n": n, "gagal": g}
            for (r, n, g) in s.execute(
                select(LLMCall.role, func.count(), func.count().filter(LLMCall.ok.is_(False)))
                .group_by(LLMCall.role)
            ).all()
        ]
        biaya = float(s.scalar(select(func.coalesce(func.sum(LLMCall.cost_usd), 0))) or 0)
    fallback_rate = (
        round(sum(p["fallback"] for p in per_provider) / total, 4) if total else None
    )
    return {
        "total_panggilan": total,
        "fallback_rate": fallback_rate,
        "biaya_usd": biaya,
        "per_provider": per_provider,
        "per_peran": per_peran,
        "catatan": "angka dihitung dari tabel llm_calls, bukan penghitung di memori",
    }


@router.get("/api/v1/ai/prompts")
def ai_prompts(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
    from warroom_core.db import Prompt

    with session_scope() as s:
        rows = s.scalars(select(Prompt).order_by(Prompt.role, Prompt.version)).all()
        data = [
            {"role": p.role, "versi": p.version, "aktif": p.active,
             "skema": bool(p.schema_json), "contoh": len(p.contoh_json or [])}
            for p in rows
        ]
    return {"prompts": data, "count": len(data)}


@router.post("/api/v1/ai/narrate")
def ai_narrate(
    body: dict[str, Any],
    request: Request,
    user: Annotated[User, Depends(auth.require_role("operator"))],
) -> dict[str, Any]:
    """Narasi ber-grounding dari fakta di DB. Tanpa fakta → `insufficient`, bukan tebakan."""
    if not limits.NARRATE_LIMITER.izinkan(limits.kunci_klien(request)):
        raise HTTPException(status_code=429, detail="terlalu banyak permintaan narasi; coba lagi nanti")
    from warroom_llm import CallRequest, FactRef, Gateway
    from warroom_llm.config import default_config
    from warroom_llm.prompts import PromptRegistry

    area = str(body.get("area", "crypto"))
    kunci = AREA_KEYS.get(area, ())
    with session_scope() as s:
        terbaru = latest_facts(s)
        dipakai = [terbaru[k] for k in kunci if k in terbaru][:8]
        fakta = [
            FactRef(fact_id=f.id, label=f"F{i + 1}",
                    text=f"{f.key}={str(f.value_json)[:80]} (sumber={f.source}, umur_s="
                         f"{int((datetime.now(UTC) - f.observed_at).total_seconds())})")
            for i, f in enumerate(dipakai)
        ]
    gw = Gateway(config=default_config(), prompts=PromptRegistry.from_dir(str(prompts_dir())))
    hasil = gw.call(
        CallRequest(
            role="narrator",
            user=str(body.get("pertanyaan", f"Ringkas 2 kalimat untuk area {area}.")),
            facts=tuple(fakta),
            min_facts=1,
            use_cache=bool(body.get("cache", True)),
        )
    )
    return {
        "status": hasil.status,
        "provider": hasil.provider,
        "model": hasil.model,
        "fallback_from": hasil.fallback_from,
        "prompt_version": hasil.prompt_version,
        "latency_ms": hasil.latency_ms,
        "fact_ids": list(hasil.fact_ids),
        "output": hasil.output,
        "error_code": hasil.error_code,
        "catatan": "semua angka di keluaran harus berasal dari fact_ids di atas",
    }


@router.post("/api/v1/ai/verifier")
def ai_verifier(
    body: dict[str, Any],
    request: Request,
    user: Annotated[User | None, Depends(auth.optional_user)],
) -> dict[str, Any]:
    """Penilai kedua untuk kartu pod (P3-T5).

    Dipanggil **hanya** dari proses lokal: token layanan (`WARROOM_SERVICE_TOKEN`)
    atau berasal dari 127.0.0.1. Jalur sesi pengguna **wajib** peran `operator` —
    temuan audit 5 Okt 2026: sebelumnya `viewer` pun bisa memanggil, dan endpoint
    ini membakar kuota LLM berbayar. Setiap jalur dibatasi laju.
    """
    if not limits.VERIFIER_LIMITER.izinkan(limits.kunci_klien(request)):
        raise HTTPException(status_code=429, detail="terlalu banyak permintaan verifier; coba lagi nanti")
    token_env = os.environ.get("WARROOM_SERVICE_TOKEN", "")
    token_kirim = request.headers.get("x-warroom-token", "")
    dari_lokal = request.client is not None and request.client.host in {"127.0.0.1", "::1"}
    token_sah = bool(token_env) and hmac.compare_digest(token_env, token_kirim)
    # Sesi pengguna: wajib peran operator. Token/lokal: tanpa peran (proses internal).
    sesi_berwenang = user is not None and auth.has_role(user, "operator")
    if not sesi_berwenang and not token_sah and not dari_lokal:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "unauthenticated",
                "message": "butuh sesi operator, token layanan, atau lokal",
            },
        )
    klaim = [str(k) for k in (body.get("klaim") or [])][:12]
    if not klaim:
        raise HTTPException(
            status_code=422,
            detail={"code": "klaim_kosong", "message": "kirim daftar `klaim` ringkas"},
        )
    from warroom_llm import CallRequest, FactRef, Gateway
    from warroom_llm.config import default_config
    from warroom_llm.prompts import PromptRegistry

    gw = Gateway(config=default_config(), prompts=PromptRegistry.from_dir(str(prompts_dir())))
    fakta = tuple(
        FactRef(fact_id=int(f["id"]), label=f"F{i + 1}",
                text=f"{f['key']}={str(f['value_json'])[:80]} (sumber={f['source']})")
        for i, f in enumerate(body.get("fakta") or [])
        if isinstance(f, dict) and "id" in f and "key" in f
    )
    hasil = gw.call(
        CallRequest(
            role="verifier",
            user=f"Klaim pod {body.get('nama', '?')}: " + " | ".join(klaim),
            facts=fakta,
            min_facts=int(body.get("min_facts", 0)),
            use_cache=bool(body.get("cache", True)),
        )
    )
    return {
        "status": hasil.status,
        "setuju": (hasil.output or {}).get("setuju"),
        "catatan": (hasil.output or {}).get("catatan"),
        "provider": hasil.provider,
        "fallback_from": hasil.fallback_from,
        "fact_ids": list(hasil.fact_ids),
        "error_code": hasil.error_code,
    }
