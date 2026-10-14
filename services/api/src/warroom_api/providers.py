"""Util bersama API — kesehatan per provider LLM (dipakai ai/status & llm-console).

Dipindah dari app.py (P1-2) supaya bisa dipakai bersama oleh router governance
dan app.py tanpa saling impor (menghindari circular import).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from warroom_core.db.session import SASession

__all__ = ["provider_ringkas"]


def provider_ringkas(s: SASession) -> list[dict[str, Any]]:
    """Kesehatan per provider dari `llm_calls` — satu tempat (dipakai ai/status & llm-console).

    Tanpa penghitung di memori: `ok_rate` dihitung dari jumlah baris, `error_terakhir`
    diambil dari baris gagal terbaru per provider (kode HTTP/kelas error, bukan tebakan).
    """
    from warroom_core.db import LLMCall

    per = s.execute(
        select(
            LLMCall.provider,
            func.count(),
            func.count().filter(LLMCall.ok.is_(True)),
            func.count().filter(LLMCall.ok.is_(False)),
            func.count().filter(LLMCall.fallback_from.is_not(None)),
            func.percentile_cont(0.5).within_group(LLMCall.latency_ms.asc().nulls_last()),
            func.percentile_cont(0.95).within_group(LLMCall.latency_ms.asc().nulls_last()),
            func.coalesce(func.sum(LLMCall.tokens_in), 0),
            func.coalesce(func.sum(LLMCall.tokens_out), 0),
        ).group_by(LLMCall.provider)
    ).all()
    error_terakhir: dict[str, str] = {}
    for (p, code) in s.execute(
        select(LLMCall.provider, LLMCall.error_code)
        .where(LLMCall.error_code.is_not(None))
        .order_by(LLMCall.created_at.desc(), LLMCall.id.desc())
    ).all():
        error_terakhir.setdefault(str(p), str(code))
    return [
        {
            "provider": p,
            "n": n,
            "ok": ok_n,
            "gagal": g,
            "ok_rate": round(ok_n / n, 4) if n else None,
            "fallback": f,
            "p50_ms": p50,
            "p95_ms": p95,
            "token_in": ti,
            "token_out": to,
            "error_terakhir": error_terakhir.get(str(p)),
        }
        for (p, n, ok_n, g, f, p50, p95, ti, to) in per
    ]
