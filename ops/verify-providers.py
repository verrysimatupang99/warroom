#!/usr/bin/env python
"""Diagnosis provider LLM (W6) — panggil tiap provider dengan prompt minimal.

Jalankan (butuh kunci dari env; biasanya lewat root):

    sudo bash -c 'set -a; . /etc/warroom/llm.env; set +a; \
      /home/admin/warroom/.venv/bin/python /home/admin/warroom/ops/verify-providers.py'

Yang dicetak: satu baris JSON per provider (status, HTTP, latensi, model) + ringkasan.
Kunci **tidak pernah** dicetak — hanya nama env var-nya. Keluar 1 bila provider utama gagal,
supaya bisa dipakai sebagai gerbang cepat; keluar 2 bila konfigurasi tidak terbaca.
"""

from __future__ import annotations

import json
import os
import sys
import time

import httpx
from warroom_llm.config import DEFAULT_CONFIG_PATH, LLMConfig, ProviderSpec

TIMEOUT_S = 30.0


def probe(spec: ProviderSpec) -> dict[str, object]:
    kunci = os.environ.get(spec.key_env)
    if not kunci:
        return {"provider": spec.name, "status": "kunci-kosong", "detail": f"env {spec.key_env} kosong"}
    model = spec.models.get("fast") or next(iter(spec.models.values()), "")
    if not model:
        return {"provider": spec.name, "status": "model-kosong", "detail": "models kosong di konfigurasi"}
    t0 = time.monotonic()
    try:
        r = httpx.post(
            f"{spec.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {kunci}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 5,
            },
            timeout=TIMEOUT_S,
        )
        ms = round((time.monotonic() - t0) * 1000)
        if r.status_code == 200:
            pilihan = (r.json() or {}).get("choices") or []
            if pilihan:
                return {"provider": spec.name, "status": "ok", "http": 200, "latency_ms": ms, "model": model}
            return {"provider": spec.name, "status": "gagal", "http": 200, "latency_ms": ms,
                    "detail": "jawaban tanpa choices"}
        return {"provider": spec.name, "status": "gagal", "http": r.status_code, "latency_ms": ms,
                "detail": r.text[:120]}
    except httpx.HTTPError as exc:
        return {"provider": spec.name, "status": "gagal", "detail": type(exc).__name__,
                "latency_ms": round((time.monotonic() - t0) * 1000)}


def main() -> int:
    path = os.environ.get("WARROOM_LLM_CONFIG", str(DEFAULT_CONFIG_PATH))
    try:
        cfg = LLMConfig.from_file(path)
    except Exception as exc:  # noqa: BLE001 — diagnosis, bukan jalur produksi
        print(json.dumps({"ok": False, "error": f"konfigurasi tidak terbaca: {type(exc).__name__}"}))
        return 2
    print(f"# konfigurasi: {path} · provider utama: {cfg.primary} · kunci tidak pernah dicetak")
    hasil = [probe(p) for p in cfg.providers]
    for h in hasil:
        print(json.dumps(h, ensure_ascii=False))
    utama = next((h for h in hasil if h["provider"] == cfg.primary), None)
    sehat = sum(1 for h in hasil if h["status"] == "ok")
    print(
        f"# ringkas: utama={cfg.primary} "
        f"{'ok' if utama and utama['status'] == 'ok' else 'GAGAL'} · sehat={sehat}/{len(hasil)}"
    )
    return 0 if utama and utama["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
