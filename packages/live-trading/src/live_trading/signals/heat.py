"""Konteks pasar per strategi: skor panas (heat) + filter funding/OI.

Kenapa per strategi: hasil tiap strategi harus bisa dibandingkan secara adil, jadi
penilaian konteks tidak boleh satu angka global untuk semua. Setiap strategi punya
profilnya sendiri (bobot heat, ambang filter) dan hasilnya dilaporkan per strategi —
mengubah profil satu strategi tidak boleh diam-diam mengubah penilaian strategi lain.

Semua ambang & referensi di sini HIPOTESIS — angka awal yang masuk akal, belum
divalidasi. Ambang yang sudah dipakai ``signals/agents.py`` dipakai ULANG di sini
(FUNDING_EKSTREM_PCT, OI_LONJAKAN_PCT) supaya dua tempat tidak saling bertentangan.
Validasi menyusul lewat atribusi R di ``measure``, bukan lewat keyakinan.

Filter hanya menolak setup bila datanya benar-benar terbaca. Data tak terbaca →
``ok=None`` (n/a + alasan) — bukan lolos diam-diam, bukan ditolak tanpa bukti.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from warroom_core.heat_score import HeatComponent, HeatScore, hitung_heat

from . import agents as agents_mod
from .golden_pullback import GoldenPullbackStrategy

__all__ = [
    "AMBANG_FILTER_BAWAAN",
    "AmbangFilter",
    "HasilFilter",
    "KATALOG_HEAT",
    "PROFIL_FILTER",
    "PROFIL_HEAT",
    "STRATEGI_GOLDEN",
    "STRATEGI_LEGACY",
    "SpesifikasiHeat",
    "filter_funding_oi",
    "heat_strategi",
    "konteks_dari_agents",
    "konteks_dari_snapshot",
]

# Nama strategi yang dipakai di catatan verdict (verdicts.jsonl). "legacy-smc" =
# proposal SMC lama (engine.propose); nama panjang itu milik Golden Pullback.
STRATEGI_LEGACY = "legacy-smc"
STRATEGI_GOLDEN = GoldenPullbackStrategy.name


@dataclass(frozen=True, slots=True)
class SpesifikasiHeat:
    """Satu komponen heat yang bisa diukur: dari field konteks mana, skala penuhnya."""

    field: str
    referensi: float
    catatan: str


# Referensi = nilai yang dianggap "penuh" (skor komponen 100). Semua HIPOTESIS.
KATALOG_HEAT: tuple[SpesifikasiHeat, ...] = (
    SpesifikasiHeat(
        field="volume_24j_usd_m",
        referensi=1000.0,
        catatan="volume 24 jam (juta USD); 1.000 = pasar sangat ramai (hipotesis)",
    ),
    SpesifikasiHeat(
        field="funding_abs_pct",
        referensi=agents_mod.FUNDING_EKSTREM_PCT,
        catatan="|funding 8 jam|; 0,05% = ekstrem, ambang yang sama dengan agents.py",
    ),
    SpesifikasiHeat(
        field="oi_delta_abs_pct",
        referensi=agents_mod.OI_LONJAKAN_PCT,
        catatan="|delta OI 24 jam|; 10% = lonjakan, ambang yang sama dengan agents.py",
    ),
    SpesifikasiHeat(
        field="taker_dev",
        referensi=0.5,
        catatan="|taker ratio - 1|; 0,5 = agresi satu sisi kuat (hipotesis)",
    ),
    SpesifikasiHeat(
        field="chg24h_abs_pct",
        referensi=10.0,
        catatan="|perubahan harga 24 jam|; 10% = gerak harian besar (hipotesis)",
    ),
)

# Bobot heat per strategi (nama komponen → bobot). Beda bobot = beda makna konteks:
# entry di POI (legacy) lebih dipengaruhi posisi crowd, sedangkan Golden Pullback
# adalah kelanjutan setelah sweep — arus taker & pertumbuhan OI lebih informatif.
# Semua bobot HIPOTESIS; akan dinilai lewat measure, bukan dipertahankan buta.
PROFIL_HEAT: dict[str, dict[str, float]] = {
    STRATEGI_LEGACY: {
        "volume_24j_usd_m": 1.0,
        "funding_abs_pct": 1.5,
        "oi_delta_abs_pct": 1.0,
        "taker_dev": 0.5,
        "chg24h_abs_pct": 0.5,
    },
    STRATEGI_GOLDEN: {
        "volume_24j_usd_m": 1.0,
        "funding_abs_pct": 1.0,
        "oi_delta_abs_pct": 1.5,
        "taker_dev": 1.0,
        "chg24h_abs_pct": 0.5,
    },
}


@dataclass(frozen=True, slots=True)
class AmbangFilter:
    """Ambang filter funding/OI untuk satu strategi."""

    funding_ekstrem_pct: float = agents_mod.FUNDING_EKSTREM_PCT
    oi_mengempis_pct: float = -agents_mod.OI_LONJAKAN_PCT

    def __post_init__(self) -> None:
        if self.funding_ekstrem_pct <= 0:
            raise ValueError("funding_ekstrem_pct harus > 0")
        if self.oi_mengempis_pct >= 0:
            raise ValueError("oi_mengempis_pct harus negatif (ambang penurunan)")


AMBANG_FILTER_BAWAAN = AmbangFilter()

# Ambang per strategi. Sama di kedua strategi hari ini — tidak ada bukti yang
# membenarkan pemisahan angka; mekanismenya sudah per-strategi supaya tuning nanti
# (keputusan owner) tidak mengubah strategi lain tanpa sengaja.
PROFIL_FILTER: dict[str, AmbangFilter] = {
    STRATEGI_LEGACY: AmbangFilter(),
    STRATEGI_GOLDEN: AmbangFilter(),
}


@dataclass(frozen=True, slots=True)
class HasilFilter:
    """Hasil filter funding/OI untuk satu setup satu strategi.

    ``ok=None`` = tidak dievaluasi karena data tidak terbaca — ditampilkan sebagai
    n/a + alasan, bukan seolah-olah lolos.
    """

    strategi: str
    ok: bool | None
    alasan: str
    aturan: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategi": self.strategi,
            "ok": self.ok,
            "alasan": self.alasan,
            "aturan": list(self.aturan),
        }


def _angka(nilai: Any) -> float | None:
    try:
        return float(nilai) if nilai is not None else None
    except (TypeError, ValueError):
        return None


def konteks_dari_agents(hasil_agents: Mapping[str, Any] | None) -> dict[str, float | None]:
    """Field konteks dari keluaran ``signals.agents.collect`` (dipakai jalur --agents)."""
    if not hasil_agents:
        return {}
    a = hasil_agents.get("agents") or {}
    of = ((a.get("orderflow") or {}).get("data") or {}) if isinstance(a, dict) else {}
    wh = ((a.get("whale") or {}).get("data") or {}) if isinstance(a, dict) else {}
    return {
        "funding_pct": _angka(of.get("funding_pct")),
        "oi_delta_pct": _angka(wh.get("oi_delta_24h_pct")),
        "taker_ratio": _angka(of.get("taker_ratio")),
        "volume_24j_usd_m": None,
        "chg24h_pct": None,
    }


def konteks_dari_snapshot(snap: Mapping[str, Any] | None) -> dict[str, float | None]:
    """Field konteks dari ``CryptoCollector.pair_snapshot`` (satu pair, sekali tarik)."""
    if not snap:
        return {}
    return {
        "funding_pct": _angka(snap.get("funding")),
        "oi_delta_pct": None,  # snapshot memuat OI level, bukan deltanya
        "taker_ratio": _angka(snap.get("taker")),
        "volume_24j_usd_m": _angka(snap.get("quote_vol")),
        "chg24h_pct": _angka(snap.get("chg24h")),
    }


def _nilai_terhitung(konteks: Mapping[str, float | None]) -> dict[str, float | None]:
    """Ubah konteks mentah → nilai komponen (absolut di mana arah tidak relevan).

    ``None`` diteruskan apa adanya: komponen tak terbaca tetap tak terbaca, tidak
    berubah jadi nol.
    """

    def _abs(kunci: str) -> float | None:
        v = _angka(konteks.get(kunci))
        return abs(v) if v is not None else None

    taker = _angka(konteks.get("taker_ratio"))
    return {
        "volume_24j_usd_m": _angka(konteks.get("volume_24j_usd_m")),
        "funding_abs_pct": _abs("funding_pct"),
        "oi_delta_abs_pct": _abs("oi_delta_pct"),
        "taker_dev": abs(taker - 1.0) if taker is not None else None,
        "chg24h_abs_pct": _abs("chg24h_pct"),
    }


def heat_strategi(
    strategi: str,
    konteks: Mapping[str, float | None],
    *,
    bobot: Mapping[str, float] | None = None,
) -> HeatScore:
    """Skor heat untuk satu strategi dari konteks pasar yang terbaca.

    ``bobot`` bisa menimpa profil (dipakai uji & pemanggil yang ingin eksplisit);
    tanpa itu, profil strategi yang berlaku. Strategi tak dikenal memakai bobot 1,0.
    """
    efektif = bobot if bobot is not None else PROFIL_HEAT.get(strategi, {})
    nilai = _nilai_terhitung(konteks)
    komponen = [
        HeatComponent(
            nama=spec.field,
            nilai=nilai.get(spec.field),
            referensi=spec.referensi,
            bobot=float(efektif.get(spec.field, 1.0)),
            catatan=spec.catatan,
        )
        for spec in KATALOG_HEAT
    ]
    return hitung_heat(komponen)


def filter_funding_oi(
    strategi: str,
    arah: str,
    konteks: Mapping[str, float | None],
    *,
    ambang: AmbangFilter | None = None,
) -> HasilFilter:
    """Filter funding/OI: tolak setup yang melawan arus pendanaan / saat OI mengempis.

    Dua aturan (keduanya HIPOTESIS, ambang dari agents.py):

    - ``funding_berlawanan`` — funding ekstrem yang SEPARAH dengan posisi berarti
      sudah terlambat masuk crowd (long saat funding sangat positif = long membayar);
      arah inilah yang ditolak. Funding moderat tidak dinilai.
    - ``oi_mengempis`` — delta OI 24 jam di bawah ambang: posisi keluar pasar, bahan
      bakar tren menguap. Berlaku untuk kedua arah.

    Data tak terbaca (None) tidak menghasilkan penolakan: aturan itu ditandai tidak
    dievaluasi. Kalau tak satu pun aturan bisa dinilai, ``ok=None``.
    """
    a = ambang or PROFIL_FILTER.get(strategi, AMBANG_FILTER_BAWAAN)
    funding = _angka(konteks.get("funding_pct"))
    oi = _angka(konteks.get("oi_delta_pct"))
    long = str(arah).lower() == "long"
    aturan: list[dict[str, Any]] = []

    if funding is None:
        aturan.append({"aturan": "funding_berlawanan", "dievaluasi": False, "lolos": None,
                       "alasan": "funding tidak terbaca"})
    else:
        lawan = funding >= a.funding_ekstrem_pct if long else funding <= -a.funding_ekstrem_pct
        aturan.append({
            "aturan": "funding_berlawanan",
            "dievaluasi": True,
            "lolos": not lawan,
            "alasan": (
                f"funding {funding:+.4f}% ekstrem searah {arah.upper()} — sudah terlambat masuk crowd"
                if lawan
                else f"funding {funding:+.4f}% tidak ekstrem berlawanan"
            ),
        })

    if oi is None:
        aturan.append({"aturan": "oi_mengempis", "dievaluasi": False, "lolos": None,
                       "alasan": "delta OI tidak terbaca"})
    else:
        empis = oi <= a.oi_mengempis_pct
        aturan.append({
            "aturan": "oi_mengempis",
            "dievaluasi": True,
            "lolos": not empis,
            "alasan": (
                f"OI {oi:+.1f}% — posisi keluar pasar, bahan bakar tren menguap"
                if empis
                else f"OI {oi:+.1f}% tidak mengempis"
            ),
        })

    dinilai = [x for x in aturan if x["dievaluasi"]]
    if not dinilai:
        return HasilFilter(
            strategi=strategi,
            ok=None,
            alasan="funding & OI sama-sama tidak terbaca — filter tidak dievaluasi (n/a)",
            aturan=tuple(aturan),
        )
    gagal = [x for x in dinilai if not x["lolos"]]
    if gagal:
        alasan = "; ".join(str(x["alasan"]) for x in gagal)
    else:
        alasan = "; ".join(str(x["alasan"]) for x in dinilai)
    return HasilFilter(strategi=strategi, ok=not gagal, alasan=alasan, aturan=tuple(aturan))
