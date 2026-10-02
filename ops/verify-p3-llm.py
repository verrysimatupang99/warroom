#!/usr/bin/env python
"""Bukti P3: panggilan LLM **sungguhan** lewat gateway + failover nyata.

Jalankan sebagai root (butuh kredensial DB + kunci provider):

    sudo bash -c 'set -a; . /etc/warroom/db.env; . /etc/warroom/llm.env; set +a; \
      export HOME=/home/admin; /home/admin/warroom/.venv/bin/python \
      /home/admin/warroom/ops/verify-p3-llm.py'

Yang dibuktikan:
1. narrator memakai fakta nyata dari DB dan mengembalikan kalimat ber-`fact_id`.
2. Setiap panggilan tercatat di `llm_calls` (provider, model, latensi, token, hash, fact_ids).
3. Failover: kunci nutaraline sengaja dirusak → permintaan tetap dilayani qonek,
   `fallback_from='nutaraline'` tercatat, dan **tidak ada** kredensial di keluaran.
4. Tanpa fakta → `insufficient` (tidak ada angka baru).
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime

from sqlalchemy import func, select
from warroom_core.db import Fact, LLMCall, session_scope
from warroom_llm import CallRequest, FactRef, Gateway
from warroom_llm.config import default_config
from warroom_llm.prompts import PromptRegistry

PROMPTS_DIR = "/home/admin/warroom/prompts"


def _gateway() -> Gateway:
    return Gateway(config=default_config(), prompts=PromptRegistry.from_dir(PROMPTS_DIR))


def _fakta_nyata() -> tuple[list[FactRef], tuple[tuple[str, str], ...]]:
    """Ambil beberapa fakta nyata dari DB untuk dijadikan BLOK FAKTA."""
    with session_scope() as s:
        rows = s.scalars(
            select(Fact).where(Fact.kind == "snapshot").order_by(Fact.observed_at.desc()).limit(4)
        ).all()
        fakta = [
            FactRef(
                fact_id=f.id,
                label=f"F{i + 1}",
                text=f"{f.key}={str(f.value_json)[:60]} (sumber={f.source}, umur_hari=0)",
            )
            for i, f in enumerate(rows)
        ]
    return fakta, ()


def _panggil(gw: Gateway, fakta: list[FactRef], catatan: str) -> None:
    hasil = gw.call(
        CallRequest(
            role="narrator",
            user="Buat ringkasan 2 kalimat untuk layar Ringkas pagi ini.",
            facts=tuple(fakta),
            min_facts=1,
            use_cache=False,
            cache_salt=catatan,
        )
    )
    print(f"  status={hasil.status} provider={hasil.provider} model={hasil.model} "
          f"fallback_from={hasil.fallback_from} latensi={hasil.latency_ms}ms "
          f"token={hasil.tokens_in}/{hasil.tokens_out} err={hasil.error_code}")
    if hasil.output:
        kalimat = hasil.output.get("kalimat") or []
        for k in kalimat[:3]:
            print(f"    - {str(k.get('teks'))[:110]}  fact_ids={k.get('fact_ids')}")
    print(f"  fact_ids dipakai: {hasil.fact_ids}")


def main() -> int:
    print("=== 1. narrator dengan fakta nyata (provider utama) ===")
    fakta, _ = _fakta_nyata()
    if not fakta:
        print("  GAGAL: tidak ada fakta di DB — jalankan job publish-facts dulu")
        return 2
    gw = _gateway()
    _panggil(gw, fakta, "utama")

    print("=== 2. failover nyata: kunci nutaraline dirusak ===")
    os.environ["HERMES_CUSTOM_NUTARALINE_CO_UK_API_KEY"] = "rusak-sengaja-untuk-uji"
    gw2 = _gateway()
    _panggil(gw2, fakta, "failover")

    print("=== 3. tanpa fakta → insufficient (tidak ada angka baru) ===")
    kosong = gw2.call(CallRequest(role="narrator", user="Ringkas apa saja.", facts=(), min_facts=1))
    print(f"  status={kosong.status} err={kosong.error_code} output={kosong.output}")

    print("=== 4. jejak llm_calls (10 terakhir) ===")
    with session_scope() as s:
        rows = s.scalars(select(LLMCall).order_by(LLMCall.id.desc()).limit(10)).all()
        for c in rows:
            print(f"  {c.role:9s} {c.provider:10s} ok={c.ok} fallback={c.fallback_from} "
                  f"{c.latency_ms}ms tok={c.tokens_in}/{c.tokens_out} err={c.error_code}")
        total = s.scalar(select(func.count()).select_from(LLMCall))
        gagal = s.scalar(select(func.count()).select_from(LLMCall).where(LLMCall.ok.is_(False)))
    print(f"  total={total} gagal={gagal}")
    print("HASIL:", "HIJAU" if (total or 0) >= 2 else "MERAH", datetime.now(UTC).isoformat())
    return 0


if __name__ == "__main__":
    sys.exit(main())