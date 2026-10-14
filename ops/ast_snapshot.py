#!/usr/bin/env python3
"""Baseline AST + verifikasi untuk refactor format idx616.

1. `snapshot <dir>` — simpan AST tiap .py ke JSON.
2. `verifikasi <dir> <json>` — bandingkan AST sekarang vs snapshot.

Pakai:
  python ops/ast_snapshot.py snapshot <dir> <out.json>
  python ops/ast_snapshot.py verifikasi <dir> <json>
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


def iter_py(root: str):
    return sorted(Path(root).rglob("*.py"))


def snapshot(root: str, out: str) -> int:
    data: dict[str, str] = {}
    for p in iter_py(root):
        src = p.read_text(encoding="utf-8")
        data[str(p)] = ast.dump(ast.parse(src), include_attributes=False)
    Path(out).write_text(json.dumps(data), encoding="utf-8")
    print(f"snapshot {len(data)} berkas -> {out}")
    return 0


def verifikasi(root: str, snap: str) -> int:
    data = json.loads(Path(snap).read_text(encoding="utf-8"))
    rusak = 0
    for p in iter_py(root):
        key = str(p)
        now = ast.dump(ast.parse(p.read_text(encoding="utf-8")), include_attributes=False)
        if key not in data:
            print(f"BARU (tak ada di baseline): {p}")
            rusak += 1
        elif data[key] != now:
            print(f"AST BERUBAH: {p}")
            rusak += 1
    for key in data:
        if not Path(key).exists():
            print(f"HILANG: {key}")
            rusak += 1
    if rusak:
        print(f"\n{rusak} berkas TIDAK identik — JANGAN commit.")
        return 1
    print(f"\nSEMUA AST IDENTIK ({len(data)} berkas). Aman.")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "snapshot":
        raise SystemExit(snapshot(sys.argv[2], sys.argv[3]))
    if cmd == "verifikasi":
        raise SystemExit(verifikasi(sys.argv[2], sys.argv[3]))
    raise SystemExit(f"perintah tak dikenal: {cmd}")
