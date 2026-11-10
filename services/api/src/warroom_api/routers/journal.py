"""Router jurnal eksekusi lintas market.

Sumber: data lokal di server ini.
  - Forex  : telemetri MT5 (facts `mt5_snapshot`) + catatan fill `/var/lib/warroom/fills.csv`
  - Crypto : paper trader momentum (`momentum_paper.json`, `momentum_trades.csv`)

Lima endpoint menerima `market=all|forex|crypto`; sisanya khusus forex karena
hanya forex yang punya antrean order nyata (slippage, latensi, sesi).
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from warroom_api import auth, lokal
from warroom_api.routers.tencent import _fetch_tencent

router = APIRouter(
    prefix="/api/v1/journal", tags=["journal"], dependencies=[Depends(auth.current_user)]
)

MarketQ = Query("all", pattern="^(all|forex|crypto)$", description="Filter market")

# Endpoint yang mengerti filter market.
_FILTER = (
    "/forex/journal/stats",
    "/forex/journal/trades",
    "/forex/journal/edge",
    "/forex/journal/performance",
    "/forex/journal/multipair",
    "/forex/journal/scanlog",
)

# Padanan lokal untuk tiap endpoint. Jalur crypto TIDAK pernah ada di Tencent:
# ledger paper crypto (`crypto_equity.jsonl`) ditulis di host ini oleh `paper-scan`,
# jadi `market=crypto` harus dilayani fungsi lokal. Sebelum ini semua permintaan
# diteruskan ke Tencent, sehingga 106 trade paper tidak pernah tampil di UI.
_LOKAL = {
    "/forex/journal/stats": lokal.journal_stats,
    "/forex/journal/trades": lokal.journal_trades,
    "/forex/journal/edge": lokal.journal_edge,
    "/forex/journal/performance": lokal.journal_performance,
    "/forex/journal/multipair": lokal.journal_multipair,
    "/forex/journal/scanlog": lokal.journal_scanlog,
}


def _gabung_forex_crypto(forex: Any, crypto: Any) -> Any:
    """Gabungkan hasil Tencent (forex) dengan lokal (crypto) untuk `market=all`.

    Hanya daftar `closed`/`entries` yang digabung lalu diurutkan ulang; angka `n`
    dihitung dari hasil gabungan supaya tidak ada dua kebenaran. Kalau bentuk salah
    satu respons tidak seperti yang diharapkan, kembalikan apa adanya alih-alih
    menebak — kehilangan data lebih buruk daripada daftar yang tidak tergabung.
    """
    if not isinstance(forex, dict) or not isinstance(crypto, dict):
        return forex
    if not isinstance(forex.get("closed"), list) or not isinstance(crypto.get("closed"), list):
        return forex
    hasil = dict(forex)
    closed = list(forex.get("closed") or []) + list(crypto.get("closed") or [])
    # Deduplikasi: trade yang sama (waktu+simbol+harga) bisa muncul dobel saat
    # gabungan sumber. Pertahankan kemunculan pertama.
    _terlihat: set[tuple] = set()
    _unik: list[Any] = []
    for _t in closed:
        _k = (str(_t.get("iso", "")), str(_t.get("symbol", "")), str(_t.get("price_filled", "")))
        if _k in _terlihat:
            continue
        _terlihat.add(_k)
        _unik.append(_t)
    closed = _unik
    closed.sort(key=lambda r: str(r.get("iso", "")), reverse=True)
    entries = list(forex.get("entries") or []) + list(crypto.get("entries") or [])
    hasil["closed"] = closed[:200]
    hasil["entries"] = entries[:200]
    hasil["n"] = len(closed)
    hasil["n_entry"] = len(entries)
    hasil["sumber"] = f"{forex.get('sumber', 'tencent')} + {crypto.get('sumber', 'lokal')}"
    return hasil


async def _ambil(path: str, market: str | None = None, account: str | None = None) -> Any:
    m = (market or "all").lower()
    if m not in ("all", "forex", "crypto"):
        m = "all"
    fn = _LOKAL.get(path)
    if fn is not None:
        if m == "crypto":
            return await fn("crypto")
        if m == "all":
            return _gabung_forex_crypto(
                await _fetch_tencent(path), await fn("crypto")
            )
    params: dict[str, Any] = {}
    if market is not None and path in _FILTER:
        params["market"] = m
        if account:
            params["account"] = account
    return await _fetch_tencent(path, params=params) if params else await _fetch_tencent(path)


@router.get("/stats")
async def journal_stats(market: str = MarketQ) -> dict[str, Any]:
    """Statistik jurnal per market: ekuitas, PnL, trade, win rate."""
    return await _ambil("/forex/journal/stats", market)


@router.get("/trades")
async def journal_trades(market: str = MarketQ) -> dict[str, Any]:
    """Trade tercatat dari kedua market, terbaru lebih dulu."""
    return await _ambil("/forex/journal/trades", market)


@router.get("/watchlist")
async def journal_watchlist() -> dict[str, Any]:
    """Posisi dan pending order yang sedang terbuka di terminal MT5."""
    return await _ambil("/forex/journal/watchlist")


@router.get("/edge")
async def journal_edge(market: str = MarketQ) -> dict[str, Any]:
    """Slippage dan latensi per jam, dari fill nyata."""
    return await _ambil("/forex/journal/edge", market)


@router.get("/signals")
async def journal_signals() -> dict[str, Any]:
    """Jurnal sinyal terkirim: hasil dihitung dari candle sejak jam setelah kirim."""
    try:
        return await lokal.journal_signals()
    except lokal.SumberKosong as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "not_available", "message": str(exc)},
        ) from exc


@router.get("/scanlog")
async def journal_scanlog(market: str = MarketQ) -> dict[str, Any]:
    """Riwayat keputusan: forex = evaluasi EA, crypto = verdicts. Tidak dicampur."""
    return await _ambil("/forex/journal/scanlog", market)


@router.get("/performance")
async def journal_performance(
    market: str = MarketQ, account: str | None = Query(None)
) -> dict[str, Any]:
    """Kurva ekuitas forex dari snapshot per menit, opsional per akun MT5."""
    return await _ambil("/forex/journal/performance", market, account)


@router.get("/session")
async def journal_session() -> dict[str, Any]:
    """Kondisi sesi terakhir: spread, bid/ask, posisi."""
    return await _ambil("/forex/journal/session")


@router.get("/multipair")
async def journal_multipair(market: str = MarketQ) -> dict[str, Any]:
    """Rekap per simbol dari kedua market."""
    return await _ambil("/forex/journal/multipair", market)


@router.get("/charts")
async def journal_charts() -> list[dict[str, Any]]:
    """Deret ekuitas untuk grafik."""
    raw = await _ambil("/forex/journal/charts")
    return raw if isinstance(raw, list) else []


@router.get("/symbol/{symbol}")
async def journal_symbol(symbol: str) -> dict[str, Any]:
    """Ringkasan jurnal untuk satu simbol."""
    raw = await _ambil("/forex/journal/multipair")
    pairs = raw.get("per_simbol", {}) if isinstance(raw, dict) else {}
    for nama, row in pairs.items():
        if str(nama).upper() == symbol.upper():
            return {"pair": symbol.upper(), "found": True, **row}
    return {"pair": symbol.upper(), "found": False}
