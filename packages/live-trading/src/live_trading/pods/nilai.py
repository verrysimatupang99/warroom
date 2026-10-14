"""Nilai LLM untuk lead pod — lewat War Room (bila diaktifkan) atau gateway nutaraline lokal.

Peran: penilai kedua. Fakta deterministik tetap otoritatif — LLM hanya menjawab
setuju/tidak + 1 kalimat catatan. Gagal/offline = None (kartu jalan tanpa nilai).

P3-T5 (blueprint): pemanggilan dipindahkan ke layanan AI War Room. Perpindahan bersifat
**opt-in**: setel `WARROOM_AI_URL` (mis. `http://127.0.0.1:8800`) untuk memakai gateway
platform (rantai provider + cache + audit `llm_calls`). Bila kosong, tidak dijangkau, atau
gagal, jalur lokal di bawah tetap dipakai — jadi kartu pod tidak pernah kosong karena
perpindahan ini. `WARROOM_SERVICE_TOKEN` opsional (bila API tidak diakses dari 127.0.0.1).
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

NUTARA_URL = "https://nutaraline.co.uk/v1/chat/completions"
NUTARA_KEY_ENV = "HERMES_CUSTOM_NUTARALINE_CO_UK_API_KEY"
MODEL_ANALIS = "mimo-v2.6-flash"

def _warroom_url() -> str:
    """Dibaca saat panggilan, bukan saat impor — supaya monkeypatch/tes dan perubahan env
    (mis. systemd EnvironmentFile) langsung berlaku tanpa memuat ulang modul."""
    return os.environ.get("WARROOM_AI_URL", "").rstrip("/")


def _lewat_warroom(nama: str, ringkas: list[str], timeout: int = 25) -> dict[str, Any] | None:
    """Penilai kedua lewat layanan AI War Room. None = tidak tersedia → pakai jalur lokal."""
    basis = _warroom_url()
    if not basis:
        return None
    try:
        headers = {"Content-Type": "application/json", "User-Agent": "WarRoom-pod/2.0"}
        token = os.environ.get("WARROOM_SERVICE_TOKEN")
        if token:
            headers["X-Warroom-Token"] = token
        req = urllib.request.Request(
            f"{basis}/api/v1/ai/verifier",
            data=json.dumps({"nama": nama, "klaim": ringkas}).encode(),
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
        if d.get("status") != "ok" or d.get("setuju") is None:
            return None
        return {"setuju": bool(d.get("setuju")), "catatan": str(d.get("catatan") or "")[:200]}
    except Exception:  # noqa: BLE001 — nilai opsional, jangan matikan snapshot
        return None


def tanya(prompt: str, model: str = MODEL_ANALIS, timeout: int = 45) -> str | None:
    key = os.environ.get(NUTARA_KEY_ENV)
    if not key:
        return None
    try:
        req = urllib.request.Request(
            NUTARA_URL,
            data=json.dumps(
                {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                }
            ).encode(),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "User-Agent": "WarRoom-pod/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
        return (d["choices"][0]["message"].get("content") or "").strip() or None
    except Exception:  # noqa: BLE001 — nilai opsional, jangan matikan snapshot
        return None


def evaluate_pod(nama: str, ringkas: list[str]) -> dict[str, Any] | None:
    """Minta penilai kedua atas ringkasan lead. Kembali {setuju, catatan} atau None.

    Urutan: layanan AI War Room (bila `WARROOM_AI_URL` disetel) → gateway lokal nutaraline.
    """
    v = _lewat_warroom(nama, ringkas)
    if v:
        return v
    isi = " | ".join(ringkas)
    for prompt in (
        f"Laporan analis paper pod {nama}: {isi} "
        'Balas HANYA JSON valid tanpa teks lain: {"setuju": true, "catatan": "maks 20 kata"}',
        f'{{"setuju": true, "catatan": "nilai pod {nama}"}} — salin pola itu, isi penilaianmu. HANYA JSON.',
    ):
        raw = tanya(prompt)
        if not raw:
            continue
        try:
            d = json.loads(raw[raw.index("{") : raw.rindex("}") + 1])
            return {"setuju": bool(d.get("setuju")), "catatan": str(d.get("catatan", ""))[:200]}
        except Exception:  # noqa: BLE001
            continue
    return None


def evaluate_all(laporan: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for nama, ringkas in laporan.items():
        v = evaluate_pod(nama, ringkas)
        if v:
            out[nama] = v
    return out
