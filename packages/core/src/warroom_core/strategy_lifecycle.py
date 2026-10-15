"""Lifecycle status setup + aturan transisinya — satu kontrak untuk semua pasar.

Kenapa ini ada: tiap pasar menyimpan setup dengan bentuk dan nama status sendiri
(`signal/*` untuk crypto, `idx_sinyal`/`forex_sinyal` untuk IDX & Forex, `lp_paper`
untuk LP). Kalau tiap halaman menebak sendiri arti status itu, dua pasar bisa menulis
"Running" untuk keadaan yang berbeda — dan perbandingan antar-strategi jadi tidak sah,
padahal itu tujuan utama War Room.

Status yang dipakai, urut siklus hidupnya:

- ``WAITING``  — setup ada, harga belum menyentuh zona entry.
- ``IN_AREA``  — harga sudah menyentuh zona entry, posisi belum terisi.
- ``RUNNING``  — posisi terisi, belum kena TP maupun SL.
- ``TP``/``SL`` — selesai, dengan hasilnya.
- ``EXPIRED``  — jendela tunggu habis tanpa pernah terisi.

Aturan yang dikodekan di sini:

- **Status diturunkan dari level & rentang harga yang sudah terjadi**, bukan tebakan.
- **Tak ada data → ``None``/n/a, bukan status karangan.** Level tidak valid = tidak
  dinilai; pemanggil yang memutuskan cara menampilkan.
- **SL menang atas TP bila keduanya tersentuh di jendela yang sama** — pilihan
  konservatif yang sama dengan ``measure.resolve_one``; angka tidak boleh dibaguskan
  oleh asumsi yang menguntungkan diri sendiri.
- **Urutan mengikat.** Status tidak boleh mundur dan tidak boleh melompati ``IN_AREA``
  menuju ``RUNNING``; status akhir tidak bisa berubah lagi.

Modul murni: tanpa jaringan, tanpa berkas, tanpa efek samping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

__all__ = [
    "LABEL_STATUS",
    "STATUS_AKHIR",
    "STATUS_SETUP",
    "URUTAN_STATUS",
    "SetupStatus",
    "status_dari",
    "status_dari_harga",
    "transisi_diizinkan",
]

StatusSetup = Literal["WAITING", "IN_AREA", "RUNNING", "TP", "SL", "EXPIRED"]

# Urutan resmi siklus hidup (indeks = tingkat kemajuan; dipakai menahan kemunduran).
STATUS_SETUP: tuple[str, ...] = ("WAITING", "IN_AREA", "RUNNING", "TP", "SL", "EXPIRED")

# Status akhir: begitu masuk sini, tidak ada transisi keluar.
STATUS_AKHIR: frozenset[str] = frozenset({"TP", "SL", "EXPIRED"})

# Label manusia untuk UI. Pendek saja — angka/waktu ditambahkan pemanggil.
LABEL_STATUS: dict[str, str] = {
    "WAITING": "Menunggu harga masuk zona",
    "IN_AREA": "Harga di zona entry",
    "RUNNING": "Posisi berjalan",
    "TP": "Selesai: target kena",
    "SL": "Selesai: stop kena",
    "EXPIRED": "Kedaluwarsa: tidak pernah terisi",
}

URUTAN_STATUS: dict[str, int] = {nama: i for i, nama in enumerate(STATUS_SETUP)}


@dataclass(frozen=True, slots=True)
class SetupStatus:
    """Status satu setup + alasan yang bisa ditelusuri.

    ``alasan`` wajib: status tanpa alasan tidak bisa dibandingkan antar strategi karena
    pembacanya tidak tahu apakah itu hasil penilaian atau sisa default.
    """

    status: str
    alasan: str
    harga: float | None = None
    di_zona: bool = False
    terisi: bool = False

    def __post_init__(self) -> None:
        if self.status not in URUTAN_STATUS:
            raise ValueError(f"status tidak dikenal: {self.status!r}")
        if not self.alasan.strip():
            raise ValueError("alasan status wajib diisi")

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "label": LABEL_STATUS[self.status],
            "alasan": self.alasan,
            "harga": self.harga,
            "di_zona": self.di_zona,
            "terisi": self.terisi,
        }


def transisi_diizinkan(dari: str, ke: str) -> bool:
    """Apakah transisi SATU LANGKAH ``dari`` → ``ke`` sah?

    Untuk penilacak status antar-pemindaian; hasil evaluasi berbasis rentang harga
    boleh menggabungkan beberapa langkah dalam satu jendela (lihat ``status_dari_harga``).

    Ditolak: mundur (``RUNNING`` → ``WAITING``), melompati ``IN_AREA``/``RUNNING``
    menuju TP/SL/EXPIRED, dan apa pun yang keluar dari status akhir. Transisi ke diri
    sendiri diizinkan.
    """
    if dari not in URUTAN_STATUS or ke not in URUTAN_STATUS:
        raise ValueError(f"status tidak dikenal: {dari!r} -> {ke!r}")
    if dari == ke:
        return True
    if dari in STATUS_AKHIR:
        return False
    if dari == "WAITING" and ke in {"IN_AREA", "RUNNING", "EXPIRED"}:
        return True
    if dari == "IN_AREA" and ke in {"RUNNING", "EXPIRED"}:
        return True
    if dari == "RUNNING" and ke in {"TP", "SL", "EXPIRED"}:
        return True
    return False


def _kemajuan_diizinkan(dari: str, ke: str) -> bool:
    """Boleh tidak mundur, tetapi boleh menggabung langkah (WAITING → SL dalam satu candle).

    Dipakai ``status_dari_harga``: rentang harga bisa membuat satu jendela memuat
    fill dan hasil sekaligus; yang tidak boleh hanya kemunduran status.
    """
    if dari in STATUS_AKHIR:
        return dari == ke
    return URUTAN_STATUS[ke] >= URUTAN_STATUS[dari]


def _rentang(harga: float, harga_min: float | None, harga_max: float | None) -> tuple[float, float]:
    """Rentang harga yang dipakai menilai. Tanpa min/max, rentangnya = harga terakhir."""
    awal = harga if harga_min is None else harga_min
    akhir = harga if harga_max is None else harga_max
    return (awal, akhir) if awal <= akhir else (akhir, awal)


def status_dari_harga(
    *,
    arah: str,
    entry: float,
    sl: float,
    tp1: float,
    harga: float,
    zona_low: float | None = None,
    zona_high: float | None = None,
    harga_min: float | None = None,
    harga_max: float | None = None,
    dimulai_dari: str = "WAITING",
    isi_penetrasi_bps: float = 0.0,
) -> SetupStatus | None:
    """Tentukan status setup dari level dan rentang harga sejak setup dibuat.

    ``harga_min``/``harga_max`` = rentang harga 1H sejak verdict (opsional; kalau tidak
    ada, penilaian memakai ``harga`` terakhir saja — lebih kasar tetapi jujur).
    ``zona_low``/``zona_high`` = zona entry; tanpa zona, ``IN_AREA`` tidak bisa dibedakan
    dan status hanya ``WAITING`` sebelum terisi.

    ``isi_penetrasi_bps`` memakai syarat terisi yang sama dengan ``measure.resolve_one``:
    harga harus menembus level entry sejauh itu, bukan sekadar menyentuh.

    Mengembalikan ``None`` kalau level wajib tidak valid (``entry``/``harga`` ≤ 0) —
    pemanggil yang memutuskan cara menuliskan "tidak bisa dinilai", bukan fungsi ini.
    """
    if harga <= 0 or entry <= 0:
        return None
    if dimulai_dari not in URUTAN_STATUS:
        raise ValueError(f"status awal tidak dikenal: {dimulai_dari!r}")
    if dimulai_dari in STATUS_AKHIR:
        return SetupStatus(
            status=dimulai_dari,
            alasan="status akhir tidak dinilai ulang",
            harga=harga,
        )
    long = str(arah).lower() == "long"
    awal, akhir = _rentang(harga, harga_min, harga_max)

    geser = entry * isi_penetrasi_bps / 10000.0
    level_isi = entry - geser if long else entry + geser
    terisi = awal <= level_isi if long else akhir >= level_isi

    if terisi:
        # SL diperiksa lebih dulu (konservatif). Untuk setup pullback, level SL selalu
        # di balik entry, jadi harga yang menyentuh SL pasti sudah melewati entry —
        # urutan pemeriksaan ini tidak menciptakan fill palsu.
        sl_kena = awal <= sl if long else akhir >= sl
        tp_kena = akhir >= tp1 if long else awal <= tp1
        if sl_kena and tp_kena:
            hasil = SetupStatus(
                status="SL",
                alasan="SL dan TP tersentuh di jendela yang sama — dihitung SL (konservatif)",
                harga=harga,
                terisi=True,
            )
        elif sl_kena:
            hasil = SetupStatus(status="SL", alasan="harga menyentuh SL", harga=harga, terisi=True)
        elif tp_kena:
            hasil = SetupStatus(status="TP", alasan="harga menyentuh TP1", harga=harga, terisi=True)
        else:
            hasil = SetupStatus(
                status="RUNNING",
                alasan="posisi terisi; belum ada level hasil yang tersentuh",
                harga=harga,
                di_zona=True,
                terisi=True,
            )
        return _tahan_bila_tidak_sah(hasil, dimulai_dari, harga)

    if zona_low is not None and zona_high is not None:
        lo, hi = min(zona_low, zona_high), max(zona_low, zona_high)
        if awal <= hi and akhir >= lo:
            hasil = SetupStatus(
                status="IN_AREA",
                alasan="harga menyentuh zona entry, belum terisi penuh",
                harga=harga,
                di_zona=True,
            )
            return _tahan_bila_tidak_sah(hasil, dimulai_dari, harga)

    return _tahan_bila_tidak_sah(
        SetupStatus(status="WAITING", alasan="harga belum mencapai zona entry", harga=harga),
        dimulai_dari,
        harga,
    )


def _tahan_bila_tidak_sah(hasil: SetupStatus, dimulai_dari: str, harga: float) -> SetupStatus:
    """Tolak kemunduran status: kalau tidak boleh maju, pertahankan yang lama."""
    if _kemajuan_diizinkan(dimulai_dari, hasil.status):
        return hasil
    return SetupStatus(
        status=dimulai_dari,
        alasan=(
            f"penilaian harga memberi {hasil.status}, tetapi transisi dari {dimulai_dari} "
            "tidak sah; status dipertahankan"
        ),
        harga=harga,
    )


def status_dari(*, lama: str, baru: str, alasan: str, harga: float | None = None) -> SetupStatus:
    """Terapkan ``baru`` hanya kalau transisinya sah dari ``lama``; kalau tidak, tahan.

    Dipakai pemanggil yang sudah tahu status berikutnya (mis. ``EXPIRED`` karena jendela
    tunggu habis dari sisi waktu, yang tidak dihitung di sini).
    """
    if not transisi_diizinkan(lama, baru):
        return SetupStatus(
            status=lama,
            alasan=f"transisi {lama} -> {baru} tidak sah; status dipertahankan",
            harga=harga,
        )
    return SetupStatus(status=baru, alasan=alasan, harga=harga)
