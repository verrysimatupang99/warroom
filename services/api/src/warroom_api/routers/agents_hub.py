"""Router Multi-Agent War Room Council (Orchestrator & Specialized Market Agents).

Setiap agen beroperasi dalam workspace terisolasi (Git worktree di /home/admin/warroom-agents/<agent_id>)
sehingga memiliki FULL PERMISSION untuk melakukan CRUD codebase, manipulasi file, eksekusi tool,
tanpa merusak runtime utama produksi (/home/admin/warroom) saat menerima perintah destruktif.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from warroom_api.auth_ea import verify_mt5_or_admin

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])
log = logging.getLogger("warroom_api.agents")

AGENTS_BASE_DIR = Path("/home/admin/warroom-agents")
MAIN_REPO_DIR = Path("/home/admin/warroom")
AGY_BIN = "/home/admin/.local/bin/agy"

# Definisi Registry Agen & Market Specialization
AGENT_REGISTRY = {
    "orchestrator": {
        "id": "orchestrator",
        "name": "War Room Chief Orchestrator",
        "role": "Master Strategist & Cross-Market Coordinator",
        "market": "all",
        "badge": "Commander",
        "workspace": str(AGENTS_BASE_DIR / "orchestrator"),
        "branch": "agent-orchestrator",
        "default_model": "deepseek-v4.1-flash",  # Qonek ultra-fast
        "description": "Menerima mandat makro pengguna, mengoordinasikan dan mendelegasikan "
        "tugas ke agen spesialis pasar.",
    },
    "forex": {
        "id": "forex",
        "name": "Forex & Gold Specialist",
        "role": "XAUUSD & FX Precision Scalper",
        "market": "forex",
        "badge": "Gold / FX",
        "workspace": str(AGENTS_BASE_DIR / "forex"),
        "branch": "agent-forex",
        "default_model": "deepseek-v4.1-flash",  # Qonek ultra-fast
        "description": "Spesialis pasar Forex/Gold (Exness MT5, Laya Sentinel, News "
        "Blackout, M5 Micro-trend, EA source).",
    },
    "crypto": {
        "id": "crypto",
        "name": "Crypto & Altcoins Specialist",
        "role": "Binance & Perp Scalper",
        "market": "crypto",
        "badge": "Crypto",
        "workspace": str(AGENTS_BASE_DIR / "crypto"),
        "branch": "agent-crypto",
        "default_model": "deepseek-v4.1-flash",  # Qonek
        "description": "Spesialis pasar Crypto (Tencent levels, Binance live flow, volume "
        "momentum, liquidation hunt).",
    },
    "polymarket": {
        "id": "polymarket",
        "name": "Polymarket Event Specialist",
        "role": "Binary Odds & Event Hedging Agent",
        "market": "polymarket",
        "badge": "Prediction",
        "workspace": str(AGENTS_BASE_DIR / "polymarket"),
        "branch": "agent-polymarket",
        "default_model": "grok-4.7",  # Qonek reasoning
        "description": "Spesialis Polymarket CLOB, odds mispricing, arbitrage "
        "probabilitas, dan event macro hedging.",
    },
    "idx": {
        "id": "idx",
        "name": "IDX Equity Specialist",
        "role": "IHSG & Foreign Flow Analyst",
        "market": "idx",
        "badge": "IDX",
        "workspace": str(AGENTS_BASE_DIR / "idx"),
        "branch": "agent-idx",
        "default_model": "mimo-v2.6-flash",  # Qonek
        "description": "Spesialis saham Indonesia (IDX), akumulasi/distribusi bandarmologi, "
        "aliran dana asing, dan fundamental.",
    },
}

SUPPORTED_MODELS = [
    # --- Current Session / Default ---
    {"id": "inherit", "name": "Inherit (Sesi Aktif Antigravity)", "provider": "Core", "badge": "Sesi Aktif"},

    # --- Native Core Models ---
    {
        "id": "gemini-3.8-flash-high",
        "name": "Gemini 3.8 Flash (High)",
        "provider": "Core",
        "badge": "Native Core",
    },
    {
        "id": "gemini-3.8-flash-medium",
        "name": "Gemini 3.8 Flash (Medium)",
        "provider": "Core",
        "badge": "Native Core",
    },
    {
        "id": "claude-sonnet-4-6",
        "name": "Claude Sonnet 4.6 (Thinking)",
        "provider": "Core",
        "badge": "Native Core",
    },
    {
        "id": "claude-opus-4-6-thinking",
        "name": "Claude Opus 4.6 (Thinking)",
        "provider": "Core",
        "badge": "Native Core",
    },
    {
        "id": "gpt-oss-120b-medium",
        "name": "GPT-OSS 120B (Medium)",
        "provider": "Core",
        "badge": "Native Core",
    },

    # --- Qonek Models (Primary: 30 RPM / 7 Concurrency) ---
    {"id": "deepseek-v4.1-flash", "name": "DeepSeek V4.1 Flash", "provider": "Qonek", "badge": "Qonek"},
    {"id": "deepseek-v4", "name": "DeepSeek V4 Flash", "provider": "Qonek", "badge": "Qonek"},
    {"id": "grok-4.7", "name": "Grok 4.7 Reasoning", "provider": "Qonek", "badge": "Qonek"},
    {"id": "mimo-v2.6-flash", "name": "MiMo v2.6 Flash", "provider": "Qonek", "badge": "Qonek"},
    {"id": "muse-spark", "name": "Muse Spark 1.3", "provider": "Qonek", "badge": "Qonek"},
    {"id": "space-bunny", "name": "Space Bunny Alpha", "provider": "Qonek", "badge": "Qonek"},
    {"id": "longcat", "name": "LongCat 2.5 Preview", "provider": "Qonek", "badge": "Qonek"},

    # --- Kiyara Models ---
    {"id": "gpt-6-luna", "name": "GPT-6 Luna", "provider": "Kiyara", "badge": "Kiyara"},
    {"id": "gemini-3.8-flash", "name": "Gemini 3.8 Flash", "provider": "Kiyara", "badge": "Kiyara"},
    {"id": "glm-5.3-flash", "name": "GLM 5.3 Flash", "provider": "Kiyara", "badge": "Kiyara"},

    # --- Nutaraline Models ---
    {"id": "laguna", "name": "Laguna S 2.1", "provider": "Nutaraline", "badge": "Nutaraline"},
    {"id": "nemotron", "name": "Nemotron 3 Ultra", "provider": "Nutaraline", "badge": "Nutaraline"},
    {
        "id": "nemotron-lightning",
        "name": "Nemotron 3.5 Lightning",
        "provider": "Nutaraline",
        "badge": "Nutaraline",
    },
    {"id": "north-code", "name": "North Mini Code", "provider": "Nutaraline", "badge": "Nutaraline"},
    {"id": "dots3", "name": "Dots3-Note Preview", "provider": "Nutaraline", "badge": "Nutaraline"},
]


class AgentDispatchRequest(BaseModel):
    agent_id: str
    prompt: str
    model: str | None = None
    async_mode: bool = True


def _ensure_agent_workspace(agent_id: str) -> Path:
    """Memastikan workspace Git worktree untuk agen tersedia dan sehat."""
    info = AGENT_REGISTRY.get(agent_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' tidak dikenal.")

    ws = Path(info["workspace"])
    if not ws.exists():
        ws.parent.mkdir(parents=True, exist_ok=True)
        # Buat worktree dari main repo
        try:
            branch = info["branch"]
            subprocess.run(
                ["git", "worktree", "add", str(ws), "-b", branch],
                cwd=str(MAIN_REPO_DIR),
                check=True,
                capture_output=True,
            )
        except Exception as e:
            log.warning("Gagal buat worktree baru untuk %s: %s", agent_id, e)
    return ws


@router.get("/list", dependencies=[Depends(verify_mt5_or_admin)])
def list_agents() -> dict[str, Any]:
    """Mengembalikan daftar seluruh agen terisolasi beserta status workspace & modelnya."""
    agents = []
    for aid, info in AGENT_REGISTRY.items():
        ws = Path(info["workspace"])
        git_ok = (ws / ".git").exists()
        history_file = ws / ".agent_chat_history.json"
        has_history = history_file.exists()
        last_activity = None
        if has_history:
            try:
                stat = history_file.stat()
                last_activity = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(stat.st_mtime))
            except Exception:
                pass

        agents.append({
            "id": aid,
            "name": info["name"],
            "role": info["role"],
            "market": info["market"],
            "badge": info["badge"],
            "description": info["description"],
            "workspace": str(ws),
            "branch": info["branch"],
            "default_model": info["default_model"],
            "is_isolated": True,
            "can_crud_codebase": True,
            "workspace_ready": git_ok,
            "last_activity": last_activity,
        })

    return {
        "status": "OK",
        "orchestrator_id": "orchestrator",
        "agents": agents,
        "models": SUPPORTED_MODELS,
        "base_directory": str(AGENTS_BASE_DIR),
        "note": "Semua agen memiliki akses CRUD codebase penuh di direktori kerja terisolasi masing-masing."
    }


@router.get("/messages", dependencies=[Depends(verify_mt5_or_admin)])
def get_agent_messages(
    agent_id: str = Query(..., description="ID agen: orchestrator, forex, crypto, polymarket, idx")
) -> dict[str, Any]:
    """Membaca riwayat interaksi khusus agen terkait."""
    if agent_id not in AGENT_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' tidak ditemukan.")

    ws = Path(AGENT_REGISTRY[agent_id]["workspace"])
    history_file = ws / ".agent_chat_history.json"
    messages = []
    if history_file.exists():
        try:
            messages = json.loads(history_file.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Gagal baca riwayat pesan agen %s: %s", agent_id, e)

    return {
        "agent_id": agent_id,
        "agent_name": AGENT_REGISTRY[agent_id]["name"],
        "messages": messages,
    }


@router.post("/dispatch", dependencies=[Depends(verify_mt5_or_admin)])
def dispatch_to_agent(req: AgentDispatchRequest) -> dict[str, Any]:
    """Mengirim perintah ke agen tertentu (atau orchestrator) di workspace terisolasi."""
    agent_id = req.agent_id.lower().strip()
    if agent_id not in AGENT_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' tidak dikenal.")

    info = AGENT_REGISTRY[agent_id]
    ws = _ensure_agent_workspace(agent_id)
    selected_model = req.model or info["default_model"]

    # Simpan pesan pengguna ke history lokal agen
    history_file = ws / ".agent_chat_history.json"
    messages = []
    if history_file.exists():
        try:
            messages = json.loads(history_file.read_text(encoding="utf-8"))
        except Exception:
            messages = []

    user_msg = {
        "role": "user",
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "text": req.prompt,
        "model": selected_model,
    }
    messages.append(user_msg)
    try:
        history_file.write_text(json.dumps(messages, indent=2), encoding="utf-8")
    except Exception as e:
        log.warning("Gagal simpan user history: %s", e)

    # Susun system prompt instruksi peran agen
    if agent_id == "orchestrator":
        role_directive = (
            f"[SYSTEM ROLE: Anda adalah War Room Chief Orchestrator. "
            f"Anda memiliki izin penuh CRUD codebase di workspace {ws}. "
            f"Tugas Anda: mengarahkan, merancang strategi makro, dan membagi perintah ke sub-agen pasar "
            f"(forex di {AGENTS_BASE_DIR}/forex, crypto di {AGENTS_BASE_DIR}/crypto, "
            f"polymarket di {AGENTS_BASE_DIR}/polymarket, idx di {AGENTS_BASE_DIR}/idx). "
            f"Anda dapat memeriksa atau mengubah kode di sub-repo atau repo "
            f"Anda sendiri secara langsung.]\n\n"
        )
    else:
        role_directive = (
            f"[SYSTEM ROLE: Anda adalah agen spesialis pasar '{info['badge']}' ({info['name']}). "
            f"Anda memiliki izin penuh CRUD codebase di direktori ini tanpa khawatir "
            f"merusak runtime server utama. "
            f"Fokus Anda hanya pada analisis, strategi, data feeds, dan kode terkait "
            f"pasar {info['market'].upper()}.]\n\n"
        )

    full_prompt = role_directive + req.prompt

    # Eksekusi agy CLI di dalam direktori workspace agen
    cmd = [
        AGY_BIN,
        f"--model={selected_model}",
        "-p", full_prompt,
        "--dangerously-skip-permissions"
    ]

    log_file = ws / ".agent_last_execution.log"

    def _run():
        try:
            with open(log_file, "w", encoding="utf-8") as out:
                p = subprocess.Popen(
                    cmd,
                    cwd=str(ws),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                stdout_text, _ = p.communicate(timeout=180)
                out.write(stdout_text)

                # Simpan respons asisten ke .agent_chat_history.json
                if stdout_text and stdout_text.strip():
                    try:
                        curr_msgs = []
                        if history_file.exists():
                            curr_msgs = json.loads(history_file.read_text(encoding="utf-8"))
                        curr_msgs.append({
                            "role": "assistant",
                            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "text": stdout_text.strip(),
                            "model": selected_model
                        })
                        history_file.write_text(json.dumps(curr_msgs, indent=2), encoding="utf-8")
                    except Exception as he:
                        log.warning("Gagal append asisten ke history: %s", he)
        except Exception as err:
            log.error("Error menjalankan agen %s: %s", agent_id, err)

    if req.async_mode:
        import threading
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return {
            "status": "DISPATCHED",
            "agent_id": agent_id,
            "agent_name": info["name"],
            "model_used": selected_model,
            "workspace": str(ws),
            "mode": "background_worker",
            "message": f"Instruksi berhasil dikirim ke {info['name']} di workspace terisolasi.",
        }
    else:
        _run()
        out_text = log_file.read_text(encoding="utf-8", errors="ignore") if log_file.exists() else ""
        return {
            "status": "COMPLETED",
            "agent_id": agent_id,
            "agent_name": info["name"],
            "model_used": selected_model,
            "output": out_text,
        }
