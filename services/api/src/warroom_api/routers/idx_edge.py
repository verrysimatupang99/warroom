"""Router IDX: sumber idx-edge (stock.arjum.com).

Semua endpoint di sini meneruskan ke modul `idx_edge` yang menyimpan cache dan
menghormati kuota berbayar. Tidak ada angka karangan: kalau sumber gagal, balas
galat yang menyebut sebabnya.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from warroom_api import auth, idx_edge

router = APIRouter(
    prefix="/api/v1/idx-edge", tags=["idx"], dependencies=[Depends(auth.current_user)]
)


def _galat(exc: Exception) -> HTTPException:
    if isinstance(exc, idx_edge.IdxTidakSiap):
        return HTTPException(
            status_code=503,
            detail={"code": "sumber_tidak_siap", "message": str(exc)},
        )
    return HTTPException(status_code=502, detail={"code": "sumber_gagal", "message": str(exc)})


@router.get("/pemakaian")
async def pemakaian() -> dict[str, Any]:
    """Hitungan panggilan keluar hari ini. Sisa kuota RESMI tidak bisa ditanya lewat API."""
    return {"sumber": "hitung-sendiri", "hasil": idx_edge.pemakaian()}


@router.get("/kesehatan")
async def kesehatan() -> dict[str, Any]:
    try:
        return {"sumber": "idx-edge", "hasil": await idx_edge.kesehatan()}
    except Exception as exc:  # noqa: BLE001 - diteruskan sebagai 503/502 yang jujur
        raise _galat(exc) from exc


@router.get("/cari")
async def cari(q: str = Query(..., min_length=2, max_length=12)) -> dict[str, Any]:
    try:
        hasil = await idx_edge.cari(q)
        return {"sumber": "idx-edge", "n": len(hasil), "hasil": hasil[:20]}
    except Exception as exc:  # noqa: BLE001
        raise _galat(exc) from exc


@router.get("/harga/{kode}")
async def harga(kode: str) -> dict[str, Any]:
    try:
        return {"sumber": "idx-edge", "hasil": await idx_edge.harga(kode)}
    except Exception as exc:  # noqa: BLE001
        raise _galat(exc) from exc


@router.get("/harga")
async def harga_banyak(
    codes: str = Query(..., description="Daftar kode dipisah koma, maks 20"),
) -> dict[str, Any]:
    try:
        daftar = [k for k in codes.split(",") if k.strip()]
        return {"sumber": "idx-edge", "hasil": await idx_edge.harga_banyak(daftar)}
    except Exception as exc:  # noqa: BLE001
        raise _galat(exc) from exc


@router.get("/riwayat/{kode}")
async def riwayat(kode: str, limit: int = Query(60, ge=20, le=500)) -> dict[str, Any]:
    try:
        return {"sumber": "idx-edge", "hasil": await idx_edge.riwayat(kode, limit)}
    except Exception as exc:  # noqa: BLE001
        raise _galat(exc) from exc


@router.get("/penggerak")
async def penggerak(urut: str = Query("chg", pattern="^(chg|pct)$")) -> dict[str, Any]:
    try:
        return {"sumber": "idx-edge", "hasil": await idx_edge.penggerak(urut)}
    except Exception as exc:  # noqa: BLE001
        raise _galat(exc) from exc


@router.get("/kapitalisasi")
async def kapitalisasi(halaman: int = Query(1, ge=1, le=100)) -> dict[str, Any]:
    try:
        return {"sumber": "idx-edge", "hasil": await idx_edge.kapitalisasi(halaman)}
    except Exception as exc:  # noqa: BLE001
        raise _galat(exc) from exc


@router.get("/broker/{kode}")
async def broker(kode: str) -> dict[str, Any]:
    try:
        return {"sumber": "idx-edge", "hasil": await idx_edge.ringkasan_broker(kode)}
    except Exception as exc:  # noqa: BLE001
        raise _galat(exc) from exc


@router.get("/akumulasi/{kode}")
async def akumulasi(kode: str) -> dict[str, Any]:
    try:
        return {"sumber": "idx-edge", "hasil": await idx_edge.akumulasi_broker(kode)}
    except Exception as exc:  # noqa: BLE001
        raise _galat(exc) from exc


@router.get("/analisa/{kode}")
async def analisa(kode: str) -> dict[str, Any]:
    try:
        return {"sumber": "idx-edge", "hasil": await idx_edge.analisa(kode)}
    except Exception as exc:  # noqa: BLE001
        raise _galat(exc) from exc


@router.get("/insider/{kode}")
async def insider(kode: str) -> dict[str, Any]:
    try:
        return {"sumber": "idx-edge", "hasil": await idx_edge.insider(kode)}
    except Exception as exc:  # noqa: BLE001
        raise _galat(exc) from exc


@router.get("/keuangan/{kode}")
async def keuangan(kode: str) -> dict[str, Any]:
    try:
        return {"sumber": "idx-edge", "hasil": await idx_edge.laporan_keuangan(kode)}
    except Exception as exc:  # noqa: BLE001
        raise _galat(exc) from exc


@router.get("/musiman/{kode}")
async def musiman(kode: str) -> dict[str, Any]:
    try:
        return {"sumber": "idx-edge", "hasil": await idx_edge.musiman(kode)}
    except Exception as exc:  # noqa: BLE001
        raise _galat(exc) from exc


@router.get("/screener")
async def screener() -> dict[str, Any]:
    try:
        return {"sumber": "idx-edge", "hasil": await idx_edge.screener()}
    except Exception as exc:  # noqa: BLE001
        raise _galat(exc) from exc


@router.get("/ringkas")
async def ringkas() -> dict[str, Any]:
    try:
        return {"sumber": "idx-edge", "hasil": await idx_edge.indeks_ringkas()}
    except Exception as exc:  # noqa: BLE001
        raise _galat(exc) from exc
