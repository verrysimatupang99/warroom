"""Evaluator formula aman untuk strategy config (TANPA eval()).

Formula strategy ditulis sebagai ekspresi, mis.:
    "rsi < 35 and ema_cepat > ema_lambat"
    "atr > 0.5"
    "close > EMA(200)"            (pemanggilan indikator inline)

Keamanan: kita TIDAK memakai eval()/exec(). Ekspresi di-parse ke AST Python,
lalu dijalan-kan oleh evaluator yang HANYA mengizinkan node dalam whitelist.
Apa pun di luar whitelist (atribut, subscript, lambda, import, dsb.) ditolak
dengan FormulaError. Ini mencegah injeksi kode lewat config.

Kontrak:
- Nama variabel (Name) di-resolve dari dict konteks; kalau tak ada -> FormulaError.
- Pemanggilan fungsi (Call) hanya boleh ke indikator dalam INDIKATOR whitelist.
- Konstanta hanya boleh angka (int/float). String/bool literal dibatasi.
- Operator: aritmetika, perbandingan, and/or/not, unary minus.
"""
from __future__ import annotations

import ast
from typing import Any

from .variabel import INDIKATOR


class FormulaError(Exception):
    """Formula tidak valid / memakai konstruksi di luar whitelist."""


# Node AST yang diizinkan.
_NODE_IZIN = (
    ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
    ast.USub, ast.UAdd, ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div,
    ast.Mod, ast.Pow, ast.FloorDiv, ast.Compare, ast.Eq, ast.NotEq,
    ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Call, ast.Name, ast.Load,
    ast.Constant, ast.Tuple, ast.List,
)


def _validasi_ast(tree: ast.AST) -> None:
    """Tolak node apa pun di luar whitelist (fail-closed)."""
    for node in ast.walk(tree):
        if not isinstance(node, _NODE_IZIN):
            raise FormulaError(f"konstruksi tidak diizinkan: {type(node).__name__}")
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)):
                # izinkan bool (turunan int) tapi tolak string/None arbitrer
                if not isinstance(node.value, bool):
                    raise FormulaError(f"literal tidak diizinkan: {node.value!r}")


def evaluasi(ekspresi: str, konteks: dict[str, Any]) -> Any:
    """Evaluasi ekspresi formula terhadap konteks variabel. Aman (tanpa eval)."""
    try:
        tree = ast.parse(ekspresi, mode="eval")
    except SyntaxError as e:
        raise FormulaError(f"sintaks formula salah: {ekspresi!r} ({e})") from e
    _validasi_ast(tree)
    return _eval_node(tree.body, konteks)


def _eval_node(node: ast.AST, ctx: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in ctx:
            raise FormulaError(f"variabel tak dikenal: {node.id}")
        return ctx[node.id]
    if isinstance(node, ast.BinOp):
        kiri = _eval_node(node.left, ctx)
        kanan = _eval_node(node.right, ctx)
        return _binop(node.op, kiri, kanan)
    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, ctx)
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return +operand
        raise FormulaError("unary op tak dikenal")
    if isinstance(node, ast.BoolOp):
        return _boolop(node, ctx)
    if isinstance(node, ast.Compare):
        return _compare(node, ctx)
    if isinstance(node, ast.Call):
        return _call(node, ctx)
    if isinstance(node, (ast.Tuple, ast.List)):
        return [_eval_node(el, ctx) for el in node.elts]
    raise FormulaError(f"node tak didukung: {type(node).__name__}")


def _binop(op: ast.AST, kiri: Any, kanan: Any) -> Any:
    if isinstance(op, ast.Add):
        return kiri + kanan
    if isinstance(op, ast.Sub):
        return kiri - kanan
    if isinstance(op, ast.Mult):
        return kiri * kanan
    if isinstance(op, ast.Div):
        return kiri / kanan if kanan != 0 else float("inf")
    if isinstance(op, ast.FloorDiv):
        return kiri // kanan if kanan != 0 else float("inf")
    if isinstance(op, ast.Mod):
        return kiri % kanan
    if isinstance(op, ast.Pow):
        return kiri ** kanan
    raise FormulaError("operator aritmetika tak dikenal")


def _boolop(node: ast.BoolOp, ctx: dict[str, Any]) -> Any:
    hasil: Any = None
    if isinstance(node.op, ast.And):
        for val in node.values:
            hasil = _eval_node(val, ctx)
            if not hasil:
                return hasil  # short-circuit, kembalikan nilai falsy
        return hasil
    if isinstance(node.op, ast.Or):
        for val in node.values:
            hasil = _eval_node(val, ctx)
            if hasil:
                return hasil
        return hasil
    raise FormulaError("boolean op tak dikenal")


def _compare(node: ast.Compare, ctx: dict[str, Any]) -> Any:
    kiri = _eval_node(node.left, ctx)
    for op, komparator in zip(node.ops, node.comparators, strict=False):
        kanan = _eval_node(komparator, ctx)
        if not _cmp(op, kiri, kanan):
            return False
        kiri = kanan
    return True


def _cmp(op: ast.AST, kiri: Any, kanan: Any) -> bool:
    if isinstance(op, ast.Eq):
        return kiri == kanan
    if isinstance(op, ast.NotEq):
        return kiri != kanan
    if isinstance(op, ast.Lt):
        return kiri < kanan
    if isinstance(op, ast.LtE):
        return kiri <= kanan
    if isinstance(op, ast.Gt):
        return kiri > kanan
    if isinstance(op, ast.GtE):
        return kiri >= kanan
    raise FormulaError("operator perbandingan tak dikenal")


def _call(node: ast.Call, ctx: dict[str, Any]) -> Any:
    if not isinstance(node.func, ast.Name):
        raise FormulaError("pemanggilan hanya boleh ke nama indikator")
    nama = node.func.id
    if nama not in INDIKATOR:
        raise FormulaError(f"indikator tidak dalam whitelist: {nama}")
    # indikator bekerja pada deret candle penuh, jadi butuh akses ke candles.
    # Konteks menyediakan candles di bawah kunci khusus __candles__.
    candles = ctx.get("__candles__")
    if candles is None:
        raise FormulaError(f"indikator {nama} butuh deret candle (tak tersedia di konteks ini)")
    args = [_eval_node(a, ctx) for a in node.args]
    fn = INDIKATOR[nama]
    # konvensi: argumen pertama (period) dari formula; candles otomatis.
    return fn(candles, *args)
