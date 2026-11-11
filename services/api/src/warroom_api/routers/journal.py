"""Router jurnal eksekusi lintas market.

Sumber: data lokal di server ini.
  - Forex  : telemetri MT5 (facts `mt5_snapshot`) + catatan fill `/var/lib/warroom/fills.csv`
  - Crypto : paper trader momentum (`momentum_paper.json`, `momentum_trades.csv`)

Lima endpoint menerima `market=all|forex|crypto`; sisanya khusus forex karena
hanya forex yang punya antrean order nyata (slippage, latensi, sesi).
"""

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from warroom_core.db.models import User

from warroom_api import auth, lokal, paper_real
from warroom_api.jam_terbaik import agregat_jam_hari
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


@router.get("/paper-vs-real")
async def journal_paper_vs_real(
    user: Annotated[User, Depends(auth.current_user)],
) -> dict[str, Any]:
    """Bandingkan trade NYATA (forex) dengan PAPER (crypto) berdampingan.

    Ledger mencampur dua jenis catatan: forex = deal tertutup EA MT5 di akun
    nyata, crypto = simulasi paper bot. Win-rate paper jauh lebih tinggi, jadi
    angkanya dipisah di sini supaya tidak terbaca sebagai hasil uang nyata.
    Menang/rugi real dari `pnl_usd`, paper dari `r`; seri tidak dihitung di
    winrate. Data kosong dikirim `null`, bukan 0.
    """
    forex, crypto = await asyncio.to_thread(lokal.trades_terpisah)
    return paper_real.banding(forex, crypto)


@router.get("/best-hours")
async def journal_best_hours(
    user: Annotated[User, Depends(auth.current_user)],
    market: str = Query("forex", pattern="^(forex|crypto)$", description="forex|crypto"),
) -> dict[str, Any]:
    """Jam & hari terbaik: win-rate dan total PnL per jam 0-23 dan per hari.

    `iso` pada sumber adalah waktu TUTUP trade (UTC); analisis jam/hari memakai itu.
    Penentu menang/rugi adalah `pnl_usd` untuk forex dan `r` untuk crypto paper,
    karena `pnl_pct`/`close_price` kosong untuk forex. Fungsi agregatnya murni
    (`jam_terbaik.agregat_jam_hari`) supaya bisa diuji tanpa DB.
    """
    data = await lokal.journal_trades(market)
    trades = data.get("closed") if isinstance(data, dict) else None
    hasil = agregat_jam_hari(trades if isinstance(trades, list) else [], market=market)
    hasil["sumber"] = str((data or {}).get("sumber") or "lokal")
    hasil["catatan"] = (
        "iso = waktu TUTUP trade (UTC; waktu tanpa zona dianggap UTC). Menang/rugi dari "
        "pnl_usd (forex) atau r (crypto) karena pnl_pct kosong untuk forex. "
        "winrate_pct = menang/(menang+rugi); seri tidak dihitung. jam_terbaik/hari_terbaik "
        f"butuh n >= {hasil['min_n']}: n kecil belum signifikan, jadi angka kosong dikirim null."
    )
    return hasil


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


@router.delete("/trades/{ticket}")
def hapus_trade(
    ticket: str,
    user: Annotated[User, Depends(auth.require_role("owner"))],
    venue: str = Query(..., description="venue trade (mis. forex)"),
    mode: str = Query("live", description="mode trade (live|paper|warisan)"),
) -> dict[str, Any]:
    """Hapus satu baris trade (owner-only) — bersihkan baris uji/keliru.

    Kunci = (venue, mode, ext_id) mengikuti unique constraint `trades`, supaya
    tidak menghapus baris yang salah. Mengembalikan ringkasan baris yang dihapus.
    """
    from sqlalchemy import select
    from warroom_core.db import session_scope
    from warroom_core.db.models import Trade

    with session_scope() as ses:
        row = ses.execute(
            select(Trade).where(
                Trade.venue == venue, Trade.mode == mode, Trade.ext_id == ticket
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(404, "Trade tidak ditemukan")
        info = {"id": row.id, "venue": row.venue, "mode": row.mode, "ext_id": row.ext_id}
        ses.delete(row)
    return {"status": "deleted", **info}
