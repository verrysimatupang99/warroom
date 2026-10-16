# ruff: noqa: E501, E741, F401
#!/usr/bin/env python3
"""Unduh PNG + HTML untuk semua layar yang tersimpan di screens/*.json."""
import importlib.util
import json
import os
import re
import subprocess
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
SCR = os.path.join(DIR, "screens")
OUT = os.path.join(DIR, "unduhan")

spec = importlib.util.spec_from_file_location("stitch_mcp", "/home/admin/.stitch_mcp.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

os.makedirs(OUT, exist_ok=True)


def unduh(url: str, dst: str) -> bool:
    r = subprocess.run(["curl", "-sL", "--max-time", "120", "-o", dst, url], check=False)
    ok = r.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 1000
    if ok and dst.endswith(".png"):
        with open(dst, "rb") as f:
            head = f.read(8)
        ok = head.startswith(b"\x89PNG")
    return ok


rows = []
for fn in sorted(os.listdir(SCR)):
    layar = fn[:-5]
    res = json.load(open(os.path.join(SCR, fn)))
    texts = [
        c.get("text", "")
        for c in res.get("result", {}).get("content", [])
        if isinstance(c, dict) and c.get("type") == "text"
    ]
    blob = "\n".join(texts)
    sm = re.search(r"projects/\d+/screens/[a-f0-9]+", blob)
    if not sm:
        print(f"{layar}: screenId tidak ketemu")
        continue
    name = sm.group(0)
    gs = m.tool("get_screen", {"name": name})
    gtxt = "\n".join(
        c.get("text", "") for c in gs.get("result", {}).get("content", [])
        if isinstance(c, dict) and c.get("type") == "text"
    )
    json.dump(gs, open(os.path.join(OUT, f"{layar}-screen.json"), "w"))
    ss = re.search(r'"screenshot"\s*:\s*\{[^}]*?"downloadUrl"\s*:\s*"([^"]+)"', gtxt)
    hm = re.search(r'"htmlCode"\s*:\s*\{[^}]*?"downloadUrl"\s*:\s*"([^"]+)"', gtxt)
    ti = re.search(r'"title"\s*:\s*"([^"]{0,80})"', gtxt)
    png = os.path.join(OUT, f"{layar}.png")
    htm = os.path.join(OUT, f"{layar}.html")
    okp = unduh(ss.group(1).encode().decode("unicode_escape"), png) if ss else False
    if not okp and ss:
        okp = unduh(ss.group(1), png)
    okh = unduh(hm.group(1), htm) if hm else False
    rows.append({"layar": layar, "screen": name, "title": ti.group(1) if ti else "", "png": okp, "html": okh})
    print(f"{layar}: png={okp} html={okh} title={ti.group(1) if ti else '-'}")

with open(os.path.join(OUT, "indeks-unduhan.json"), "w") as f:
    json.dump(rows, f, indent=2)
png_ok = sum(1 for r in rows if r["png"])
print(f"RINGKAS png {png_ok}/{len(rows)}")
sys.exit(0 if png_ok == len(rows) else 2)
