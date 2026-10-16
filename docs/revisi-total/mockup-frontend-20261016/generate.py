# ruff: noqa: E501, E741, F401
#!/usr/bin/env python3
"""Orkestrator generate 14 layar Stitch -> docs/revisi-total/mockup-frontend-20261016/.

Alur:
  1. Layar pertama (home) digenerate dulu tanpa designSystem -> Stitch
     otomatis membentuk design system dari layar pertama.
  2. 13 layar sisanya jalan paralel (3 jalur) dengan designSystem dari home.

Semua respons mentah disimpan di screens/<id>.json; progress ke progress.log.
"""
import importlib.util
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

DIR = os.path.dirname(os.path.abspath(__file__))
SCR = os.path.join(DIR, "screens")
LOG = os.path.join(DIR, "progress.log")

spec = importlib.util.spec_from_file_location("stitch_mcp", "/home/admin/.stitch_mcp.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

conf = json.load(open(os.path.join(DIR, "prompts.json")))
PROJECT = conf["proyek_stitch"]
STYLE = conf["STYLE_PRE"]
LAYAR = conf["layar"]

_lock = threading.Lock()
os.makedirs(SCR, exist_ok=True)


def log(line: str) -> None:
    with _lock:
        with open(LOG, "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {line}\n")
    print(line, flush=True)


def extract(res: dict) -> dict:
    out = {"status": "unknown", "screen": None, "designSystem": None, "err": None}
    if "error" in res:
        out["status"] = "error"
        out["err"] = json.dumps(res["error"])[:500]
        return out
    content = res.get("result", {}).get("content", [])
    texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
    blob = "\n".join(texts)
    sm = re.search(r"projects/\d+/screens/[a-f0-9]+", blob)
    if sm:
        out["screen"] = sm.group(0)
        out["status"] = "ok"
    dm = re.search(r"designSystems/\d+|design_system[s]?/[\w-]+|\d{16,25}", blob)
    low = blob.lower()
    if "design" in low and dm and out["screen"]:
        out["designSystem"] = dm.group(0)
    if out["status"] != "ok":
        out["status"] = "empty"
        out["err"] = blob[:400]
    return out


def gen_task(layar: dict, design_system: str | None) -> dict:
    args = {
        "projectId": PROJECT,
        "prompt": (STYLE + " " + layar["prompt"])[:4000],
        "deviceType": conf["device"],
    }
    if design_system:
        args["designSystem"] = design_system
    last = None
    for attempt in range(3):
        try:
            res = m.tool("generate_screen_from_text", args)
            info = extract(res)
            info["attempt"] = attempt + 1
            if info["status"] == "ok":
                info["layar"] = layar
                with open(os.path.join(SCR, f"{layar['id']}.json"), "w") as f:
                    json.dump(res, f)
                return info
            last = info
            exists = os.path.exists(os.path.join(SCR, f"{layar['id']}.json"))
            if exists:
                break
        except Exception as e:  # noqa: BLE001
            last = {"status": "exception", "err": str(e)[:400], "attempt": attempt + 1}
        time.sleep(45)
    last = last or {"status": "no-run"}
    last["layar"] = layar
    return last


def main() -> int:
    home = LAYAR[0]
    log(f"MULAI proyek {PROJECT}, total {len(LAYAR)} layar")
    h = gen_task(home, None)
    ds = h.get("designSystem")
    log(f"HOME {h['layar']['id']}: {h['status']} screen={h.get('screen')} ds={ds}")
    sisa = LAYAR[1:]
    if h["status"] != "ok":
        log("PERINGATAN: home gagal, lanjut tanpa designSystem eksplisit")
    hasil = {home["id"]: h["status"]}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = {pool.submit(gen_task, l, ds): l["id"] for l in sisa}
        for fut in as_completed(futs):
            lid = futs[fut]
            try:
                r = fut.result()
            except Exception as e:  # noqa: BLE001
                r = {"status": "exception", "err": str(e)[:400]}
            hasil[lid] = r.get("status")
            log(f"SELESAI {lid}: {r.get('status')} {r.get('err', '') or ''}")
    log(f"RINGKASAN: {json.dumps(hasil)}")
    gagal = [k for k, v in hasil.items() if v != "ok"]
    log(f"SELESAI-SEMUA ok={len(LAYAR)-len(gagal)}/{len(LAYAR)} gagal={gagal}")
    return 0 if not gagal else 2


if __name__ == "__main__":
    sys.exit(main())
