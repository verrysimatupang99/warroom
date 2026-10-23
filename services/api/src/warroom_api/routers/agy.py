"""Router AGY-CLI & Antigravity Interactive Chat Assistant untuk War Room Web Control.

Menyediakan antarmuka interaktif layaknya Web AI Chat modern (ChatGPT / Claude Style):
- Mengalirkan percakapan (User vs Antigravity AI Agent).
- Memfilter raw logs (tool calls, bash debug) agar tampilan chat bersih, elegan, dan nyaman dibaca.
- Mendukung direct chat exchange, history polling, dan model selector.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from warroom_core.db import User
from warroom_api import auth
from warroom_api.auth_ea import verify_mt5_or_admin

log = logging.getLogger("warroom_api.agy")

router = APIRouter(prefix="/api/v1/agy", tags=["agy-control"])

BRAIN_BASE = Path("/home/admin/.gemini/antigravity-cli/brain")
AGY_WRAPPER = "/home/admin/.local/bin/agy"
AGY_REAL = "/home/admin/.local/bin/agy.real"


class AgyPromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Pesan chat dari user ke AI Agent")
    model: str = Field(default="inherit", description="Model yang dipilih (inherit, deepseek, gpt6, gemini, dll)")
    async_mode: bool = Field(default=True, description="Jalankan sebagai background task")


def _cari_sesi_terbaru() -> tuple[str, Path] | None:
    if not BRAIN_BASE.exists():
        return None
    candidates = []
    for d in BRAIN_BASE.iterdir():
        if d.is_dir() and not d.name.startswith("."):
            t_file = d / ".system_generated" / "logs" / "transcript.jsonl"
            if t_file.exists():
                candidates.append((t_file.stat().st_mtime, d.name, d))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1], candidates[0][2]


def _bersihkan_pesan_ai(text: str) -> str:
    """Membersihkan tag sistem dan meta-instruksi agar tampilan chat bersih seperti ChatGPT."""
    if not text:
        return ""
    # Ekstrak konten di dalam <USER_REQUEST>...</USER_REQUEST> jika ada
    m = re.search(r"<USER_REQUEST>([\s\S]*?)</USER_REQUEST>", text)
    if m:
        text = m.group(1)
    # Hapus tag pendukung lainnya
    text = re.sub(r"<ADDITIONAL_METADATA>[\s\S]*?</ADDITIONAL_METADATA>", "", text)
    text = re.sub(r"<SYSTEM_MESSAGE>[\s\S]*?</SYSTEM_MESSAGE>", "", text)
    text = re.sub(r"<RULE\[.*?\]>[\s\S]*?</RULE\[.*?\]>", "", text)
    text = re.sub(r"<!-- antislop:.*? -->", "", text)
    return text.strip()


@router.get("/status", dependencies=[Depends(verify_mt5_or_admin)])
def get_agy_status() -> dict[str, Any]:
    sesi_info = _cari_sesi_terbaru()
    active_conv_id = sesi_info[0] if sesi_info else "none"
    conv_dir = sesi_info[1] if sesi_info else None
    
    total_steps = 0
    last_activity = None
    if conv_dir:
        t_file = conv_dir / ".system_generated" / "logs" / "transcript.jsonl"
        if t_file.exists():
            try:
                with open(t_file, "rb") as f:
                    lines = f.readlines()
                    total_steps = len(lines)
                    if lines:
                        last_obj = json.loads(lines[-1].decode("utf-8", errors="ignore"))
                        last_activity = last_obj.get("created_at")
            except Exception as e:
                log.warning("Gagal membaca transcript: %s", e)

    return {
        "status": "ONLINE" if os.path.exists(AGY_REAL) else "UNAVAILABLE",
        "active_conversation_id": active_conv_id,
        "total_transcript_steps": total_steps,
        "last_activity_utc": last_activity,
        "server_time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "engine": "Antigravity Autonomous Core (DeepMind Gemini)",
        "supported_models": [
            {"id": "inherit", "name": "Inherit (Sesi Aktif)", "badge": "Core"},
            {"id": "deepseek-v4.1-flash", "name": "DeepSeek V4.1 Flash", "badge": "Qonek"},
            {"id": "grok-4.7", "name": "Grok 4.7 Reasoning", "badge": "Qonek"},
            {"id": "mimo-v2.6-flash", "name": "MiMo v2.6 Flash", "badge": "Qonek"},
            {"id": "gpt-6-luna", "name": "GPT-6 Luna", "badge": "Kiyara"},
            {"id": "gemini-3.8-flash", "name": "Gemini 3.8 Flash", "badge": "Kiyara"},
            {"id": "glm-5.3-flash", "name": "GLM 5.3 Flash", "badge": "Kiyara"}
        ]
    }


@router.get("/messages", dependencies=[Depends(verify_mt5_or_admin)])
def get_chat_messages(
    limit: int = Query(default=100, ge=1, le=300)
) -> dict[str, Any]:
    """Mengambil riwayat percakapan bersih (User vs Assistant) layaknya ChatGPT."""
    sesi_info = _cari_sesi_terbaru()
    if not sesi_info:
        return {"conversation_id": "none", "messages": []}

    conv_id, conv_dir = sesi_info
    t_file = conv_dir / ".system_generated" / "logs" / "transcript.jsonl"
    if not t_file.exists():
        return {"conversation_id": conv_id, "messages": []}

    messages = []
    try:
        with open(t_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            for line in lines[-limit:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    src = obj.get("source")
                    step_type = obj.get("type")
                    content = obj.get("content", "")

                    # Saring hanya interaksi User dan Planner/Model Response yang berisi teks nyata
                    if src == "USER_EXPLICIT" and step_type == "USER_INPUT":
                        clean_content = _bersihkan_pesan_ai(content)
                        if clean_content:
                            messages.append({
                                "role": "user",
                                "step": obj.get("step_index"),
                                "time": obj.get("created_at"),
                                "text": clean_content
                            })
                    elif src == "MODEL" and step_type == "PLANNER_RESPONSE":
                        clean_content = _bersihkan_pesan_ai(content)
                        tool_calls = obj.get("tool_calls", [])
                        # Hanya sertakan pesan percakapan asli, bukan dump mentah stdout/system
                        if clean_content and len(clean_content) > 5 and not clean_content.startswith("Created At:"):
                            messages.append({
                                "role": "assistant",
                                "step": obj.get("step_index"),
                                "time": obj.get("created_at"),
                                "text": clean_content,
                                "tools": [t.get("name") for t in tool_calls if isinstance(t, dict)]
                            })
                except Exception:
                    continue
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Gagal membaca berkas log: {exc}")

    return {
        "conversation_id": conv_id,
        "messages": messages,
        "count": len(messages)
    }


@router.post("/dispatch", dependencies=[Depends(verify_mt5_or_admin)])
async def dispatch_agy_prompt(
    body: AgyPromptRequest
) -> dict[str, Any]:
    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Pesan tidak boleh kosong.")

    sesi_info = _cari_sesi_terbaru()
    active_conv_id = sesi_info[0] if sesi_info else "none"

    log.info("Dispatch chat ke AGY (sesi: %s, model: %s): %s", active_conv_id, body.model, prompt[:80])

    # Bila memilih model 'inherit', kita sambungkan langsung ke sesi aktif tanpa membuat sesi agy baru
    cmd = [AGY_WRAPPER]
    if active_conv_id != "none":
        cmd.extend(["--conversation", active_conv_id])
    else:
        cmd.append("--continue")

    cmd.extend(["-p", prompt])

    if body.model and body.model != "inherit":
        cmd.extend(["--model", body.model])

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    return {
        "ok": True,
        "mode": "session_continued",
        "conversation_id": active_conv_id,
        "pid": proc.pid,
        "prompt": prompt,
        "model": body.model,
        "pesan": f"Pesan terkirim ke sesi aktif ({active_conv_id})."
    }
