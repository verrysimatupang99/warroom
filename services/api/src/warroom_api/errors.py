"""Skema error baku: `{error: {code, message, detail?}}` (03-backend.md §7).

UI tidak boleh menerima HTML error atau pesan kosong; setiap kegagalan harus punya kode
yang bisa ditampilkan apa adanya dan dicatat di log.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

__all__ = ["install_error_handlers"]


def _body(code: str, message: str, detail: Any | None = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if detail is not None:
        err["detail"] = detail
    return {"error": err}


_CODES = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    409: "conflict_grant_required",
    422: "unprocessable",
    429: "rate_limited",
    500: "internal",
    503: "unavailable",
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def _http(_: Request, exc: HTTPException) -> JSONResponse:
        code = _CODES.get(exc.status_code, f"http_{exc.status_code}")
        # `detail` boleh berupa objek (mis. daftar grant yang kurang) — diteruskan apa adanya
        # supaya klien bisa menampilkan kekurangan spesifik, bukan pesan kabur.
        if isinstance(exc.detail, (dict, list)):
            pesan = str(exc.detail.get("catatan") if isinstance(exc.detail, dict) else "detail terstruktur")
            return JSONResponse(status_code=exc.status_code, content=_body(code, pesan, exc.detail))
        return JSONResponse(status_code=exc.status_code, content=_body(code, str(exc.detail)))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_body("unprocessable", "permintaan tidak sesuai skema", exc.errors()),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Detail asli TIDAK dibocorkan ke klien (bisa memuat path/kredensial); dicatat di log.
        return JSONResponse(status_code=500, content=_body("internal", "kesalahan internal"))