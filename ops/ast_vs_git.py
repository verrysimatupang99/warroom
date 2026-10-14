#!/usr/bin/env python3
"""Verifikasi refactor idx616: bandingkan AST kerja-disk vs versi HEAD (git).

Menjamin refactor format tidak mengubah perilaku: AST tiap .py di disk harus
IDENTIK dengan AST versi HEAD-nya di git.

Pakai: python ops/ast_vs_git.py packages/live-trading/idx616
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


def ast_of(src: str) -> str:
    return ast.dump(ast.parse(src), include_attributes=False)


def main(root: str) -> int:
    rootp = Path(root)
    rusak = 0
    n = 0
    for p in sorted(rootp.rglob("*.py")):
        rel = p.as_posix()
        try:
            head = subprocess.run(
                ["git", "show", f"HEAD:{rel}"],
                capture_output=True, text=True, check=True,
            ).stdout
        except subprocess.CalledProcessError:
            print(f"BARU (tak ada di HEAD): {rel}")
            n += 1
            continue
        now = p.read_text(encoding="utf-8")
        try:
            if ast_of(head) != ast_of(now):
                print(f"AST BERUBAH: {rel}")
                rusak += 1
            else:
                print(f"OK   {rel}")
        except SyntaxError as e:
            print(f"SYNTAX ERROR: {rel} — {e}")
            rusak += 1
        n += 1
    if rusak:
        print(f"\n{rusak}/{n} berkas AST-nya BERUBAH — JANGAN commit! Refactor ini bukan format-murni.")
        return 1
    print(f"\nSEMUA ({n}) berkas AST-nya identik dengan HEAD. Aman commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
