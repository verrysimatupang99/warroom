"""Sinyal terbaik per pasar — satu kontrak untuk seluruh UI (5 Okt 2026).

Masalah: tiap pasar menyimpan sinyalnya dengan bentuk yang berbeda (`signal/*` untuk crypto,
`poly.verdict` untuk Polymarket, `gmgn/radar` untuk DEX, `snapshot/lp_paper` untuk LP). Home
yang menampilkan "sinyal tiap pasar" harus menormalkan semuanya ke satu bentuk — kalau UI
membaca bentuk mentah per pasar, tiap halaman baru jadi kode khusus yang berbeda.

Prinsip yang dikodekan di sini:

- **Skor harus terukur, bukan selera.** Skor crypto dihitung dari rasio aturan yang lolos
  (`rules[].ok`), bukan dari tebakan. Kalau tak ada angka, skor = None (jujur), bukan 0.
- **Verifikasi ditampilkan, bukan disembunyikan.** Polymarket mengklaim `EDGE` dengan
  win-rate 78% — tetapi `split` masih `null`, artinya belum lewat split beku. Field
  `terverifikasi` + `catatan_kejujuran` membuat UI wajib menampilkan itu. Klaim yang belum
  terverifikasi tidak boleh terlihat sama dengan yang sudah.
- **Pasar tanpa sinyal mengatakannya.** `idx` dan `forex` sering kosong; itu ditampilkan
  sebagai "belum ada sinyal" dengan alasan, bukan kartu kosong atau angka 0.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as SASession

from warroom_core.db import Fact

__all__ = ["SinyalPasar", "sinyal_terbaik_per_pasar", "PASAR"]

# Urutan + label pasar yang ditampilkan di Home. Satu sumber supaya UI dan API tidak
# berbeda definisi (pelajaran yang sama dengan nav.ts).
PASAR: tuple[tuple[str, str, str], ...] = (
    ("crypto", "Crypto (SMC)", "signal"),
    ("polymarket", "Polymarket (favorit 5m)", "poly.verdict"),
    ("gmgn", "DEX / Memecoin (GMGN)", "gmgn"),
    ("lp", "LP / Yield", "lp_paper"),
    ("idx", "IDX (bandarmologi/BSJP)", "idx_posisi"),
    ("forex", "Forex", "forex_posisi"),
)

# Bobot tier → peringkat. Makin tinggi makin baik. Dipakai memilih kandidat terbaik.
_TIER_RANK = {"PREMIUM": 3, "EDGE": 3, "STANDAR": 2, "KANDIDAT": 2, "SKIP": 1, "KELUAR": 2}


@dataclass
class SinyalPasar:
    """Satu sinyal terbaik untuk satu pasar. Bentuk seragam untuk semua pasar."""

    pasar: str
    label: str
    ada: bool
    arah: str | None = None
    subjek: str | None = None
    skor: int | None = None            # 0-100 terukur; None = tidak ada angka (bukan 0)
    tier: str | None = None
    alasan: str = ""
    terverifikasi: bool = False        # edge sudah lewat split beku?
    catatan_kejujuran: str = ""
    umur_s: float | None = None
    sumber_fakta: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ambil(s: SASession, kind: str, key: str) -> tuple[Any, datetime | None]:
    row = s.scalars(
        select(Fact)
        .where(Fact.kind == kind, Fact.key == key)
        .order_by(Fact.observed_at.desc())
        .limit(1)
    ).first()
    if row is None:
        return None, None
    return row.value_json, row.observed_at


def _umur(observed: datetime | None) -> float | None:
    if observed is None:
        return None
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=UTC)
    return round((datetime.now(UTC) - observed).total_seconds(), 1)


def _skor_dari_rules(rules: list[dict[str, Any]]) -> int | None:
    """Skor = persentase aturan yang lolos. Hard rule yang gagal membuat skor kecil —
    itu benar: setup yang melanggar hard rule bukan setup yang 'hampir lolos'."""
    if not rules:
        return None
    ok = sum(1 for r in rules if r.get("ok"))
    return round(100 * ok / len(rules))


def _crypto(s: SASession) -> SinyalPasar:
    kandidat, observed = _ambil(s, "snapshot", "kandidat")
    if not isinstance(kandidat, list) or not kandidat:
        return SinyalPasar(
            pasar="crypto", label="Crypto (SMC)", ada=False, sumber_fakta="snapshot/kandidat",
            umur_s=_umur(observed),
            alasan="Belum ada kandidat dari pemindaian SMC.",
            catatan_kejujuran="Pemindai jalan tiap 30 menit; kosong berarti belum ada pair yang lolos struktur.",
        )

    def kunci(k: dict[str, Any]) -> tuple[int, int, int]:
        rules = k.get("rules") or []
        tier = str(k.get("tier") or "SKIP")
        ok = sum(1 for r in rules if r.get("ok"))
        return (_TIER_RANK.get(tier, 0), ok, len(rules))

    terbaik = max(kandidat, key=kunci)
    rules = terbaik.get("rules") or []
    gagal = [r for r in rules if not r.get("ok")]
    skor = _skor_dari_rules(rules)
    tier = str(terbaik.get("tier") or "SKIP")
    lolos = bool(gagal) is False
    return SinyalPasar(
        pasar="crypto", label="Crypto (SMC)", ada=True,
        arah=str(terbaik.get("direction") or terbaik.get("arah") or "").upper() or None,
        subjek=str(terbaik.get("pair") or "") or None,
        skor=skor, tier=tier,
        alasan=(
            f"{sum(1 for r in rules if r.get('ok'))}/{len(rules)} aturan lolos"
            + ("" if not gagal else f"; gagal: {', '.join(str(g.get('rule')) for g in gagal[:3])}")
        ),
        terverifikasi=False,
        catatan_kejujuran=(
            "Skor = aturan yang lolos, BUKAN edge terbukti. Sampel layak-dagang masih 47 "
            "peluang (win-rate 14,8%, di bawah break-even) — belum cukup untuk promosi."
        ),
        umur_s=_umur(observed), sumber_fakta="snapshot/kandidat",
        detail={"entry": terbaik.get("entry"), "sl": terbaik.get("sl"), "tp1": terbaik.get("tp1"),
                "rr": terbaik.get("rr"), "lolos_gate": lolos, "kandidat": len(kandidat)},
    )


def _polymarket(s: SASession) -> SinyalPasar:
    v, observed = _ambil(s, "poly.verdict", "verdict")
    if not isinstance(v, dict):
        return SinyalPasar(
            pasar="polymarket", label="Polymarket (favorit 5m)", ada=False,
            sumber_fakta="poly.verdict/verdict", umur_s=_umur(observed),
            alasan="Belum ada verdict.", catatan_kejujuran="Verdict dihitung tiap jam.",
        )
    split = v.get("split")
    terverifikasi = bool(split)
    win = v.get("winRate")
    be = v.get("breakEven_pct")
    return SinyalPasar(
        pasar="polymarket", label="Polymarket (favorit 5m)", ada=True,
        arah="BELI" if str(v.get("verdict_alat")) == "EDGE" else "TAHAN",
        subjek=str(v.get("rule") or "favorit"),
        skor=round(float(win)) if isinstance(win, (int, float)) else None,
        tier=str(v.get("verdict_alat") or ""),
        alasan=(
            f"win-rate {win}% vs break-even {be}% "
            f"(CI95 {v.get('ci95')}); butuh n≈{v.get('nNeeded')}"
        ),
        terverifikasi=terverifikasi,
        catatan_kejujuran=(
            "BELUM TERVERIFIKASI: split masih kosong — belum lewat split beku, jadi ini "
            "klaim eksplorasi, bukan edge yang lolos gate."
            if not terverifikasi else
            f"Split beku: {split}"
        ),
        umur_s=_umur(observed), sumber_fakta="poly.verdict/verdict",
        detail={"n": v.get("n"), "win": v.get("win"), "winRate": win,
                "breakEven_pct": be, "ci95": v.get("ci95"), "deff": v.get("deff"),
                "nNeeded": v.get("nNeeded"), "split": split},
    )


def _gmgn(s: SASession) -> SinyalPasar:
    r, observed = _ambil(s, "gmgn", "radar")
    data = (r or {}).get("data") if isinstance(r, dict) else None
    state = (data or {}).get("state") if isinstance(data, dict) else None
    if not isinstance(state, list) or not state:
        return SinyalPasar(
            pasar="gmgn", label="DEX / Memecoin (GMGN)", ada=False, sumber_fakta="gmgn/radar",
            umur_s=_umur(observed), alasan="Belum ada data radar.",
            catatan_kejujuran="Radar butuh cache GMGN; kosong berarti belum ditarik.",
        )
    terbaik = max(state, key=lambda c: (float(c.get("avg_vl") or 0), int(c.get("viable") or 0)))
    vl = float(terbaik.get("avg_vl") or 0)
    viable, pools = int(terbaik.get("viable") or 0), int(terbaik.get("pools") or 0)
    return SinyalPasar(
        pasar="gmgn", label="DEX / Memecoin (GMGN)", ada=True,
        arah="PANTAU", subjek=str(terbaik.get("chain") or ""),
        skor=round(100 * viable / pools) if pools else None,
        tier=str(terbaik.get("window") or ""),
        alasan=f"V/L {vl:.2f} ({viable}/{pools} pool layak); {terbaik.get('note')}",
        terverifikasi=False,
        catatan_kejujuran=(
            "Ini kelayakan likuiditas, BUKAN edge arah harga. Belum ada bukti PnL dari venue ini."
        ),
        umur_s=_umur(observed), sumber_fakta="gmgn/radar",
        detail={"chain": terbaik.get("chain"), "avg_vl": vl, "viable": viable, "pools": pools,
                "total_liq": terbaik.get("total_liq"), "best_vl": terbaik.get("best_vl")},
    )


def _lp(s: SASession) -> SinyalPasar:
    r, observed = _ambil(s, "snapshot", "lp_paper")
    posisi = (r or {}).get("posisi") if isinstance(r, dict) else None
    if not isinstance(posisi, list) or not posisi:
        return SinyalPasar(
            pasar="lp", label="LP / Yield", ada=False, sumber_fakta="snapshot/lp_paper",
            umur_s=_umur(observed), alasan="Tidak ada posisi LP paper aktif.",
            catatan_kejujuran="Kapasitas LP kecil; kosong berarti belum ada kandidat.",
        )
    # Sinyal terpenting LP = yang harus KELUAR (IL terlalu dalam) — itu keputusan, bukan sekadar info.
    keluar = [p for p in posisi if str(p.get("verdict")) == "KELUAR"]
    sorotan = keluar[0] if keluar else posisi[0]
    return SinyalPasar(
        pasar="lp", label="LP / Yield", ada=True,
        arah=str(sorotan.get("verdict") or "PANTAU"), subjek=str(sorotan.get("symbol") or ""),
        skor=None,
        tier=str(sorotan.get("verdict") or ""),
        alasan=str(sorotan.get("alasan") or "posisi LP paper"),
        terverifikasi=False,
        catatan_kejujuran=(
            "Ini simulasi LP (IL + fee), bukan yield nyata. Belum ada rekonsiliasi on-chain."
        ),
        umur_s=_umur(observed), sumber_fakta="snapshot/lp_paper",
        detail={"notional": sorotan.get("notional"), "vl": sorotan.get("vl"),
                "fee_hari": sorotan.get("fee_hari"), "umur_hari": sorotan.get("umur"),
                "posisi": len(posisi)},
    )


def _kosong(pasar: str, label: str, sumber: str, s: SASession, alasan: str) -> SinyalPasar:
    kind, _, key = sumber.partition("/") if "/" in sumber else (sumber, "", "")
    _, observed = _ambil(s, kind, key) if key else (None, None)
    return SinyalPasar(
        pasar=pasar, label=label, ada=False, sumber_fakta=sumber, umur_s=_umur(observed),
        alasan=alasan,
        catatan_kejujuran="Pasar ini belum punya sinyal — ditampilkan apa adanya, bukan angka 0.",
    )


def sinyal_terbaik_per_pasar(s: SASession) -> list[SinyalPasar]:
    """Satu sinyal terbaik per pasar, urut sesuai PASAR. Selalu mengembalikan semua pasar
    (yang kosong pun), supaya UI tidak perlu tahu pasar mana yang kebetulan ada."""
    keluar: list[SinyalPasar] = [
        _crypto(s),
        _polymarket(s),
        _gmgn(s),
        _lp(s),
        _kosong("idx", "IDX (bandarmologi/BSJP)", "snapshot/idx_posisi", s,
                "Belum ada posisi/sinyal IDX. Screener bandarmologi & BSJP belum menghasilkan kandidat."),
        _kosong("forex", "Forex", "snapshot/forex_posisi", s, "Belum ada posisi/sinyal Forex."),
    ]
    urutan = {k: i for i, (k, _l, _s) in enumerate(PASAR)}
    keluar.sort(key=lambda x: urutan.get(x.pasar, 99))
    return keluar
