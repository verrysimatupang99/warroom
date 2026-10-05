"""Jalur keputusan TUNGGAL untuk paper dan live (5 Okt 2026).

Masalah yang diselesaikan: kalau paper dan live punya jalur keputusan masing-masing, hasil
paper tidak membuktikan apa pun tentang live — dua tempat bisa berbeda ukuran, berbeda SL,
berbeda aturan, dan tidak ada yang tahu sampai uang keluar. Kelas bug ini tidak bisa
diperbaiki dengan uji; ia harus dihapus dengan **konstruksi**: hanya ada SATU fungsi yang
memutuskan, dan paper/live hanya berbeda di bagian *mengirim order*.

Kontrak:

    putuskan_masuk(kandidat, konteks) -> Keputusan
    lalu:
        paper: kirim_ke_paper(keputusan)
        live : kirim_ke_live(keputusan)      # belum ada, sengaja

``Keputusan`` memuat SEMUA yang dibutuhkan eksekutor (ukuran, SL, TP, biaya). Eksekutor tidak
boleh menghitung ulang apa pun — kalau ia menghitung ulang, itu jalan kedua yang lahir lagi.

Modul ini TIDAK mengirim order. Ia memutuskan. ``eksekutor`` di konteks menentukan tujuan.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

__all__ = ["Keputusan", "Konteks", "putuskan_masuk", "jalur_untuk"]

Mode = Literal["paper", "live"]


@dataclass(frozen=True)
class Konteks:
    """Segala yang dibutuhkan untuk memutuskan — dikumpulkan di satu tempat.

    ``mode`` hanya boleh mengubah TUJUAN order, tidak boleh mengubah aturan. Kalau ada
    percabangan ``if mode == "live"`` di dalam keputusan, itu tanda jalur sudah bercabang.
    """

    equity_usd: float
    fee_bps: float | None = None          # biaya TERUKUR (P2); None = belum terukur
    stop_mult: float = 1.5
    mode: Mode = "paper"
    slot_tersisa: int = 99


@dataclass
class Keputusan:
    """Hasil satu keputusan masuk. Ini satu-satunya sumber kebenaran untuk eksekusi."""

    masuk: bool
    alasan: str
    pair: str = ""
    arah: str = ""
    entry: float | None = None
    sl: float | None = None
    tp1: float | None = None
    tp2: float | None = None
    size_usd: float | None = None
    risk_usd: float | None = None
    cost_bps: float | None = None
    mode: Mode = "paper"
    jejak: list[str] = field(default_factory=list)   # urutan langkah — untuk audit 1:1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def putuskan_masuk(kandidat: dict[str, Any], konteks: Konteks) -> Keputusan:
    """SATU-SATUNYA tempat keputusan masuk dibuat.

    Urutan langkah dipakai bersama paper & live; ``jejak`` merekamnya supaya bisa dibandingkan
    baris demi baris antara dua mode (itulah bukti 1:1 yang bisa diperiksa, bukan klaim).

    Kandidat diharapkan sudah lolos pemindaian struktur (`signals.engine.scan`). Gerbang
    risiko tetap dijalankan di sini supaya ukuran & SL tidak pernah dihitung di tempat lain.
    """
    jejak: list[str] = ["kandidat diterima"]

    pair = str(kandidat.get("pair") or "")
    arah = str(kandidat.get("direction") or kandidat.get("arah") or "").upper()
    entry = kandidat.get("entry")
    sl = kandidat.get("sl")
    if not pair or not arah or entry is None or sl is None:
        return Keputusan(False, "kandidat tidak lengkap (pair/arah/entry/sl)", mode=konteks.mode,
                         jejak=[*jejak, "DITOLAK: field wajib kosong"])

    entry, sl = float(entry), float(sl)
    jejak.append(f"field lengkap: {pair} {arah} entry={entry} sl={sl}")

    if konteks.slot_tersisa <= 0:
        return Keputusan(False, "slot posisi penuh", pair=pair, arah=arah, mode=konteks.mode,
                         jejak=[*jejak, "DITOLAK: tidak ada slot"])

    # Ukuran & SL dari gerbang risiko — TIDAK dihitung ulang di eksekutor.
    from live_trading.config import get_settings
    from live_trading.risk import RiskGate

    atr = float(kandidat.get("atr") or abs(entry - sl) / max(konteks.stop_mult, 0.1))
    gate = RiskGate(get_settings(), venue="crypto")
    fee_pct = (konteks.fee_bps / 10000.0) if konteks.fee_bps is not None else 0.0013
    dec = gate.check(pair=pair, price=entry, atr=atr, equity_usd=konteks.equity_usd,
                     stop_mult=konteks.stop_mult, fee_buffer_pct=fee_pct)
    jejak.append(f"gerbang risiko: {'lolos' if dec.allowed else 'tolak'} ({dec.reason})")
    if not dec.allowed:
        return Keputusan(False, f"gerbang risiko: {dec.reason}", pair=pair, arah=arah,
                         mode=konteks.mode, jejak=jejak)

    tp1 = kandidat.get("tp1")
    tp2 = kandidat.get("tp2")
    jejak.append(f"ukuran={dec.size_usd} risiko={dec.risk_usd} biaya={konteks.fee_bps} bps")

    return Keputusan(
        masuk=True, alasan="lolos semua gerbang", pair=pair, arah=arah,
        entry=entry, sl=sl,
        tp1=float(tp1) if tp1 is not None else None,
        tp2=float(tp2) if tp2 is not None else None,
        size_usd=float(dec.size_usd or 0.0), risk_usd=float(dec.risk_usd or 0.0),
        cost_bps=konteks.fee_bps, mode=konteks.mode, jejak=jejak,
    )


def jalur_untuk(keputusan: Keputusan) -> str:
    """Nama jalur eksekusi yang HARUS dipakai keputusan ini.

    Dipakai untuk membuktikan 1:1: dua keputusan dengan isi sama harus menghasilkan jalur
    sama. Kalau `mode` mengubah jalur tanpa mengubah isi, itu memang tujuannya (paper vs
    live) — tetapi `jejak`-nya harus identik.
    """
    return "paper" if keputusan.mode == "paper" else "live"
