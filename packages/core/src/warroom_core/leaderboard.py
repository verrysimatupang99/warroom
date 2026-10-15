"""Papan peringkat strategi — perbandingan adil lintas pasar dari fakta nyata.

Batas peran: lapisan PENYAJIAN di atas `verdict.py` — verdict menjawab "boleh
dipromosikan atau tidak", leaderboard menjawab "strategi mana yang paling baik
dibanding yang mana". Lihat docstring `signal.py` untuk peta lengkap.

Aturan yang dikodekan di sini:

- **Angka hanya dari seri `per_setup`** (fakta `pasar_akurasi` / `idx_akurasi`,
  diterbitkan mesin pasar.py). Tidak ada hitung ulang; yang tidak diukur = None
  (bukan 0), termasuk pasar yang memang tidak memakai satuan R (LP/Polymarket).
- **Status jujur terpisah dari angka.** `kosong` = fakta belum ada; `gagal` =
  mesin sendiri menyatakan sumbernya tak terbaca (ini kegagalan, bukan
  "tidak ada data"); `benched` = dikarantina (rugi dalam data uji, aturan
  owner yang sama dengan verdict); `beku` = mesin dibekukan (angka historis).
- **Peringkat jujur.** `rank` hanya diberikan pada baris yang punya expectancy R;
  baris tanpa angka tidak diberi peringkat palsu.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as SASession

from warroom_core.db import Fact
from warroom_core.market_signal import PASAR
from warroom_core.verdict import biaya_pasar, execution_state, karantina_setup

__all__ = ["StrategyRow", "strategy_leaderboard"]

# Eksekusi verdict → label UI papan peringkat.
_TIPE_EKSEKUSI = {
    "paper": "PAPER",
    "live": "LIVE",
    "frozen": "RESEARCH",
    "unknown": "SIGNAL-ONLY",
}


@dataclass
class StrategyRow:
    """Satu baris papan peringkat: satu strategi (setup) di satu pasar.

    Bentuk mengikuti `StrategyItem` di StrategyLeaderboard.svelte (id, nama,
    venue, tipe, angka, status) — supaya UI bisa memakai 1:1 tanpa penerjemahan
    yang bisa berbeda pendapat dengan backend.
    """

    id: str
    nama: str
    venue: str
    pasar: str
    tipe: str

    # Angka apa adanya. None = tidak diukur (bukan 0, bukan "tidak ada").
    n: int | None = None
    n_hari: int | None = None
    winrate_pct: float | None = None
    expectancy_r: float | None = None
    total_r: float | None = None
    pnl_usd: float | None = None
    max_drawdown_r: float | None = None

    # Status operasional — jujur, terpisah dari angka.
    status: str = "kosong"            # aktif | benched | beku | gagal | kosong
    status_detail: str = ""
    benched: bool = False
    alasan_benched: str | None = None
    beku: bool = False
    rank: int | None = None

    # Biaya per pasar (dari `bukti` mesin) — PnL bruto tidak boleh menyamar net.
    biaya: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fakta(s: SASession, key: str) -> dict[str, Any] | None:
    """Fakta terbaru kind `snapshot` untuk satu kunci — None bila tidak ada."""
    f = s.scalars(
        select(Fact).where(Fact.kind == "snapshot", Fact.key == key)
        .order_by(Fact.observed_at.desc())
        .limit(1)
    ).first()
    return f.value_json if f is not None else None


def strategy_leaderboard(s: SASession) -> dict[str, Any]:
    """Baris peringkat satu per satu setup, urut expectancy R menurun.

    Status mesin (beku/frozen) dan biaya dipakai langsung dari aturan `verdict`
    (satu definisi); angka hanya dari seri `per_setup`.

    Pasar yang mesinnya gagal/tidak punya fakta TETAP muncul sebagai baris
    status (bukan dihilangkan) — kalau dihilangkan, papan terlihat "lengkap"
    padahal satu mesin hanya tidak terbaca.
    """
    pa = _fakta(s, "pasar_akurasi") or {}

    rows: list[StrategyRow] = []
    for pasar, label, _kind in PASAR:
        if pasar == "idx":
            blok = _fakta(s, "idx_akurasi") or {}
        else:
            blok = (pa.get("pasar") or {}).get(pasar) or {}

        eksekusi, _catatan_eksekusi = execution_state(s, pasar)
        beku = eksekusi == "frozen"
        biaya = biaya_pasar(s, pasar)
        tipe = _TIPE_EKSEKUSI.get(eksekusi, "SIGNAL-ONLY")

        per_setup = blok.get("per_setup") or {}
        tersedia = bool(blok.get("tersedia"))

        if not per_setup:
            if blok and not tersedia:
                status = "gagal"
                detail = str(blok.get("alasan") or "mesin menyatakan sumber tidak terbaca")
            elif not blok:
                status = "kosong"
                detail = "fakta akurasi belum ada — mesin belum menerbitkan bukti"
            else:
                status = "kosong"
                detail = "mesin hidup, belum ada setup yang terekam"
            rows.append(StrategyRow(
                id=f"{pasar}.-",
                nama=label,
                venue=label,
                pasar=pasar,
                tipe=tipe,
                status=status,
                status_detail=detail,
                beku=beku,
                biaya=biaya,
            ))
            continue

        for kunci, seri in per_setup.items():
            seri = seri if isinstance(seri, dict) else {}
            nama = str(seri.get("nama") or kunci)
            benched, alasan_bench = karantina_setup(seri)
            mean_r = seri.get("mean_r")
            angka_ada = isinstance(mean_r, (int, float))
            if benched:
                status, detail = "benched", alasan_bench or "dikarantina (rugi dalam data uji)"
            elif beku:
                status = "beku"
                detail = _catatan_eksekusi or "mesin dibekukan — angka historis, bukan kondisi berjalan"
            else:
                status, detail = "aktif", ""
            rows.append(StrategyRow(
                id=f"{pasar}.{kunci}",
                nama=nama,
                venue=label,
                pasar=pasar,
                tipe=tipe,
                n=seri.get("n"),
                n_hari=seri.get("n_hari"),
                winrate_pct=seri.get("winrate_pct"),
                expectancy_r=mean_r if angka_ada else None,
                total_r=seri.get("total_r"),
                pnl_usd=seri.get("total_pnl_usd", seri.get("pnl_usd")),
                # max_dd bisa ada di seri langsung atau di blok `ringkas` (crypto).
                max_drawdown_r=(
                    seri.get("max_drawdown_r")
                    if seri.get("max_drawdown_r") is not None
                    else (seri.get("ringkas") or {}).get("max_drawdown_r")
                ),
                status=status,
                status_detail=detail or "",
                benched=benched,
                alasan_benched=alasan_bench,
                beku=beku,
                biaya=biaya,
            ))

    # Peringkat: expectancy R menurun. Baris tanpa angka TIDAK diberi peringkat —
    # mengurutkannya ke posisi terakhir seolah "terburuk" adalah klaim palsu.
    berangka = [r for r in rows if r.expectancy_r is not None]
    berangka.sort(key=lambda r: (-(r.expectancy_r or 0.0), -(r.n or 0)))
    for i, r in enumerate(berangka, 1):
        r.rank = i
    rows.sort(key=lambda r: (r.rank is None, r.rank or 0, r.pasar))

    return {
        "strategi": [r.to_dict() for r in rows],
        "count": len([r for r in rows if r.status == "aktif"]),
        "total_baris": len(rows),
        "benched": sum(1 for r in rows if r.benched),
        "beku": sum(1 for r in rows if r.beku),
        # Kriteria urutan dinyatakan eksplisit — papan tanpa kriteria = selera.
        "urutan": "expectancy R (R/trade) menurun; sampel sebagai taut; baris tanpa angka tidak diberi rank",
        "dibuat": datetime.now(UTC).isoformat(),
    }
