"""Baris `deals.csv` (deal tertutup dari EA MetaTrader) → record tabel `trades`.

`deals.csv` adalah bukti eksekusi forex — satu baris per posisi tertutup yang
dilaporkan EA. Koreksi append-only diterapkan lebih dulu supaya yang masuk DB
adalah angka yang sudah dikoreksi, bukan yang sudah diketahui salah.

Aturan yang sama dengan jalur crypto (`trades_crypto`): tidak ada angka yang
dikarang. `pnl_usd` hanya diisi bila memang dilaporkan; `strategy_id` dibiarkan
None kecuali EA mengirim nama strategi yang nyata.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from warroom_core.db import Trade
from warroom_core.deal_koreksi import KOREKSI_DEFAULT, baca_koreksi, terapkan

VENUE = "forex"
MODE = "live"
DEALS_DEFAULT = Path("/var/lib/warroom/deals.csv")


def baca_deals(jalur: Path = DEALS_DEFAULT, koreksi: Path = KOREKSI_DEFAULT) -> list[dict[str, Any]]:
    """Baris deal terkoreksi. Berkas tidak ada → daftar kosong (bukan galat).

    Berkas tidak ada berarti EA belum pernah melapor — itu keadaan yang sah,
    dan pemanggil harus bisa membedakannya dari "nol trade" lewat `jalur_hilang()`.
    """
    if not jalur.is_file():
        return []
    try:
        with jalur.open(newline="", encoding="utf-8", errors="replace") as f:
            baris = [dict(r) for r in csv.DictReader(f)]
    except OSError:
        return []
    return terapkan(baris, baca_koreksi(koreksi))


def jalur_hilang(jalur: Path = DEALS_DEFAULT) -> bool:
    """True bila berkas sumber belum ada — jurnal kosong BUKAN berarti nol trade."""
    return not jalur.is_file()


def _waktu(teks: str) -> datetime | None:
    if not teks:
        return None
    try:
        t = datetime.fromisoformat(teks.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _angka(v: Any) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def ke_trade(baris: dict[str, Any]) -> Trade | None:
    """Satu deal → Trade. None bila tidak ada kunci yang bisa dipertanggungjawabkan."""
    ticket = str(baris.get("ticket") or "").strip()
    if not ticket:
        return None
    symbol = str(baris.get("symbol") or "").strip().upper()
    arah = str(baris.get("side") or "").strip().upper()
    # EA menulis BUY/SELL (gaya MetaTrader). Arah lain tidak diterjemahkan —
    # menebak sisi posisi adalah cara termudah mengarang angka.
    side = "BUY" if arah.startswith("BUY") else "SELL" if arah.startswith("SELL") else None
    if side is None:
        return None

    opened_at = _waktu(str(baris.get("open_time") or baris.get("opened_at") or ""))
    closed_at = _waktu(str(baris.get("iso") or baris.get("close_time") or ""))
    open_price = _angka(baris.get("open_price"))
    close_price = _angka(baris.get("close_price"))
    net = _angka(baris.get("net"))
    volume = _angka(baris.get("volume"))

    strategi = str(baris.get("strategy_version") or "").strip()
    evidence = {
        "ticket": ticket,
        "symbol": symbol,
        "side": side,
        "volume": volume,
        "open_price": open_price,
        "close_price": close_price,
        "net": net,
        "account": str(baris.get("account") or "unknown"),
        "strategy_version": strategi or "unknown",
    }
    jejak = baris.get("_koreksi")
    if jejak:
        # Jejak koreksi ikut disimpan: pembaca bisa melihat angka mana yang
        # pernah diubah dan mengapa, tanpa membuka berkas koreksi.
        evidence["koreksi"] = jejak

    return Trade(
        venue=VENUE,
        mode=MODE,
        ext_id=ticket,
        # strategy_id butuh baris tabel `strategies` yang nyata; nama versi EA
        # bukan id. Menyimpannya di evidence lebih jujur.
        strategy_id=None,
        side=side,
        qty=volume,
        price=close_price,
        pnl_usd=net,
        pnl_r=None,  # deals.csv tidak membawa R; jangan menghitung ulang dari SL yang tak ada
        opened_at=opened_at,
        closed_at=closed_at,
        evidence_json=evidence,
    )
