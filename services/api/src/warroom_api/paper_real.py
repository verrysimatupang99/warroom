"""Ringkasan paper-vs-real: pisahkan trade NYATA dari trade PAPER.

Kenapa modul ini ada: ledger menyimpan dua jenis trade dalam satu daftar. Trade
forex adalah deal NYATA yang dilaporkan EA MT5 (`deals.csv` / tabel `trades`),
sedangkan trade crypto adalah simulasi paper bot (`crypto_equity.jsonl`). Win-rate
paper crypto jauh lebih tinggi daripada forex nyata, sehingga tanpa pemisahan
pemilik bisa mengira angka paper adalah hasil uang nyata.

Modul ini murni (tanpa DB, berkas, atau jaringan) supaya bisa diuji dengan data
contoh. Angka yang tidak punya dasar dikirim `null`, bukan 0 — 0% win-rate dan
"tidak ada trade" adalah dua hal berbeda.
"""

from __future__ import annotations

from typing import Any

PERINGATAN = "paper != uang nyata; real sampel kecil"


def _angka(nilai: Any) -> float | None:
    """Ubah nilai longgar (str/None/Decimal) jadi float; kosong -> None."""
    if nilai is None:
        return None
    teks = str(nilai).strip()
    if teks in ("", "None", "nan", "NaN", "null"):
        return None
    try:
        return float(teks)
    except (TypeError, ValueError):
        return None


def _winrate(menang: int, rugi: int) -> float | None:
    """Win-rate atas trade yang tuntas; seri tidak dihitung. Tanpa data -> None."""
    tuntas = menang + rugi
    if tuntas <= 0:
        return None
    return round(menang / tuntas * 100, 1)


def _rentang(trades: list[dict[str, Any]]) -> dict[str, str] | None:
    """Tanggal paling awal & paling akhir dari `iso` (waktu tutup)."""
    tanggal = sorted(str(t.get("iso") or "")[:19] for t in trades if str(t.get("iso") or ""))
    if not tanggal:
        return None
    return {"awal": tanggal[0], "akhir": tanggal[-1]}


def ringkas_real(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Blok REAL: forex tertutup, menang/rugi dari `pnl_usd`."""
    menang = rugi = seri = 0
    net = 0.0
    ada_pnl = False
    simbol: set[str] = set()
    for t in trades:
        nama = str(t.get("symbol") or "").strip()
        if nama:
            simbol.add(nama)
        pnl = _angka(t.get("pnl_usd"))
        if pnl is None:
            continue
        ada_pnl = True
        net += pnl
        if pnl > 0:
            menang += 1
        elif pnl < 0:
            rugi += 1
        else:
            seri += 1
    return {
        "n": len(trades),
        "menang": menang,
        "rugi": rugi,
        "seri": seri,
        "winrate_pct": _winrate(menang, rugi),
        "net_usd": round(net, 2) if ada_pnl else None,
        "rentang_tanggal": _rentang(trades),
        "simbol": sorted(simbol),
    }


def ringkas_paper(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Blok PAPER: crypto simulasi, menang/rugi & total dari `r`."""
    menang = rugi = 0
    total_r = 0.0
    ada_r = False
    for t in trades:
        r = _angka(t.get("r"))
        if r is None:
            continue
        ada_r = True
        total_r += r
        if r > 0:
            menang += 1
        elif r < 0:
            rugi += 1
    return {
        "n": len(trades),
        "menang": menang,
        "rugi": rugi,
        "winrate_pct": _winrate(menang, rugi),
        "total_r": round(total_r, 2) if ada_r else None,
    }


def banding(
    forex: list[dict[str, Any]] | None, crypto: list[dict[str, Any]] | None
) -> dict[str, Any]:
    """Dua blok berdampingan + peringatan, apa adanya dari data yang ada."""
    nyata = ringkas_real(list(forex or []))
    paper = ringkas_paper(list(crypto or []))
    return {
        "real": {**nyata, "label": "REAL", "sumber": "mt5-forwardtest", "status": "closed_deal"},
        "paper": {**paper, "label": "PAPER", "sumber": "paper-crypto"},
        "peringatan": PERINGATAN,
        "catatan": (
            "real = deal tertutup EA MT5 di akun nyata (USD). paper = simulasi paper bot "
            "crypto (R, bukan USD). Menang/rugi real dari pnl_usd, paper dari r; seri "
            "tidak dihitung di winrate. Angka kosong dikirim null, bukan 0."
        ),
    }
