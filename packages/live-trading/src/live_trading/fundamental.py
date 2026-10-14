"""fundamental.py — fundamental emiten IDX dari laporan keuangan Arjum.

KENAPA MODUL INI ADA
--------------------
Sebelumnya War Room tidak punya data fundamental IDX sama sekali: kolektor hanya
mengambil harga, screener, broker summary, dan analisis. Akibatnya skor IDX hanya bisa
dibentuk dari sisi teknikal/bandarmologi — tidak tahu apakah perusahaan itu untung,
berapa EPS-nya, atau berapa ekuitasnya.

Sumbernya dipilih Arjum, **bukan** scraper idx.co.id, setelah diuji: idx.co.id memblokir
server ini lewat Cloudflare (HTTP 403) karena IP datacenter. Arjum menyajikannya sudah
terstruktur, satu bentuk untuk semua emiten, dan endpoint-nya sudah dipakai repo ini.

DUA TAKSONOMI — INI YANG PALING MUDAH SALAH
-------------------------------------------
Bank dan non-bank punya struktur laporan yang berbeda, dan Arjum mengembalikannya apa
adanya. Nama blok level-1 memang berbeda:

  Bank (BBRI)   : pendapatan_dan_beban_operasional, laba_rugi, laba_rugi_per_saham
  Umum (ANTM)   : penjualan_dan_pendapatan_usaha, laba_bruto, laba_rugi, laba_rugi_per_saham

Kalau keduanya dipaksa ke satu jalur, sisi pendapatan akan kosong untuk separuh emiten
dan tidak ada yang memberi tahu. Karena itu ada ``deteksi_jenis`` yang menentukan jalur
dari NAMA BLOK yang benar-benar ada, bukan dari daftar sektor yang di-hardcode.

BATAS YANG DIKODEKAN DI SINI
----------------------------
1. Nilai yang tidak ditemukan → ``None``, **bukan 0**. Nol berarti "labanya nol";
   None berarti "tidak ada datanya". Menyamakan keduanya membuat UI berbohong.
2. Angka dilaporkan sebagai **nilai apa adanya** (rupiah penuh), tanpa pembulatan
   otomatis — pembulatan menyembunyikan besaran dan menyulitkan pemeriksaan ulang.
3. Laba per saham (EPS) diambil dari laporan; PER **tidak** dihitung di sini karena
   butuh harga saham dan jumlah saham beredar yang konsisten. Itu pekerjaan pemanggil,
   dan menaksirnya di sini akan menyamarkan asumsi sebagai fakta.
4. Laporan keuangan terbit per kuartal, jadi TTL cache-nya panjang (7 hari).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["FundamentalEmiten", "read_fundamental", "JENIS_BANK", "JENIS_UMUM"]

JENIS_BANK = "bank"
JENIS_UMUM = "umum"

# Blok level-1 yang menandai jenis laporan. Dipakai untuk MENDETEKSI, bukan mengasumsikan.
_BLOK_BANK = "pendapatan_dan_beban_operasional"
_BLOK_UMUM = "penjualan_dan_pendapatan_usaha"


def _kemas(blok: Any) -> float | None:
    """Total satu blok.

    Blok di Arjum datang dalam DUA bentuk, dan keduanya nyata:
      - angka langsung : ``"laba_bruto": 5234283000000.0``
      - dict bersarang : ``"pendapatan_dan_beban_operasional": {"total": 40160669000000.0}``

    Versi pertama fungsi ini hanya menangani dict, sehingga seluruh blok berbentuk angka
    (mayoritas, termasuk `laba_rugi` dan `laba_bruto`) terbaca None — laporan yang penuh
    terlihat kosong. Itu kesalahan yang menghasilkan angka sah terlihat tidak ada.
    """
    if isinstance(blok, (int, float)):
        return float(blok)
    if not isinstance(blok, dict):
        return None
    for kunci in ("total", "jumlah", "nilai", "amount"):
        v = blok.get(kunci)
        if isinstance(v, (int, float)):
            return float(v)
    # Tidak ada kunci total: jumlahkan anak yang berupa angka saja. Pendekatan yang bisa
    # salah bila blok memuat rincian yang saling meniadakan, jadi hanya upaya terakhir —
    # dan pemanggil menandainya lewat catatan.
    angka = [float(v) for v in blok.values() if isinstance(v, (int, float))]
    return sum(angka) if angka else None


def _eps(blok: Any) -> float | None:
    """EPS dari blok bersarang dua lapis.

    Bentuk nyatanya (ANTM Q2 2026):

        {"laba_per_saham_dasar_diatribusikan_kepada_pemilik_entitas_induk":
            {"laba_rugi_per_saham_dasar_dari_operasi_yang_dilanjutkan": 124.08, "total": 124.08},
         "laba_rugi_per_saham_dilusian": {...}}

    Dicari bertingkat: utamakan versi DASAR (yang umum dipakai), lalu dilusian. Nilai
    total di dalam sub-blok dipakai lebih dulu karena ia yang sudah dijumlahkan.
    """
    if isinstance(blok, (int, float)):
        return float(blok)
    if not isinstance(blok, dict):
        return None
    # Utamakan sub-blok dasar.
    dasar = next(
        (v for k, v in blok.items() if isinstance(v, dict) and "dasar" in k.lower()),
        None,
    )
    for kandidat in (dasar, blok):
        if not isinstance(kandidat, dict):
            continue
        for kunci in ("total", "nilai", "amount"):
            v = kandidat.get(kunci)
            if isinstance(v, (int, float)):
                return float(v)
        angka = [float(v) for v in kandidat.values() if isinstance(v, (int, float))]
        if angka:
            return angka[0]
    return None


@dataclass
class FundamentalEmiten:
    """Ringkasan satu kuartal. Semua field boleh None — None != 0."""

    kode: str
    label: str = ""
    tahun: str = ""
    kuartal: str = ""
    jenis: str = JENIS_UMUM
    pendapatan: float | None = None
    laba_bruto: float | None = None
    laba_operasional: float | None = None
    laba_sebelum_pajak: float | None = None
    laba_bersih: float | None = None
    laba_komprehensif: float | None = None
    eps: float | None = None
    laporan_type: str = ""
    jumlah_kuartal: int = 0
    catatan: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kode": self.kode,
            "label": self.label,
            "tahun": self.tahun,
            "kuartal": self.kuartal,
            "jenis": self.jenis,
            "pendapatan": self.pendapatan,
            "laba_bruto": self.laba_bruto,
            "laba_operasional": self.laba_operasional,
            "laba_sebelum_pajak": self.laba_sebelum_pajak,
            "laba_bersih": self.laba_bersih,
            "laba_komprehensif": self.laba_komprehensif,
            "eps": self.eps,
            "laporan_type": self.laporan_type,
            "jumlah_kuartal": self.jumlah_kuartal,
            "catatan": self.catatan,
        }

    @property
    def ada(self) -> bool:
        """True bila setidaknya satu angka inti terisi."""
        return any(
            v is not None
            for v in (self.pendapatan, self.laba_bruto, self.laba_bersih, self.eps)
        )


def deteksi_jenis(data: dict[str, Any]) -> str:
    """Tentukan jalur bank vs umum dari nama blok yang benar-benar ada.

    Sengaja TIDAK memakai daftar sektor: daftar seperti itu usang tanpa terasa, dan
    emiten yang tidak ada di daftar akan salah jalur tanpa peringatan.
    """
    if _BLOK_BANK in data:
        return JENIS_BANK
    if _BLOK_UMUM in data:
        return JENIS_UMUM
    return JENIS_UMUM


def read_fundamental(payload: dict[str, Any] | None) -> FundamentalEmiten:
    """Baca payload ``/api/financial-statements/<KODE>`` menjadi satu ringkasan kuartal.

    Mengembalikan kuartal TERBARU (item pertama — server menyusunnya terbaru-dulu).
    """
    payload = payload or {}
    kode = str(payload.get("stock_code") or "")
    items = payload.get("items") or []
    out = FundamentalEmiten(
        kode=kode,
        laporan_type=str(payload.get("report_type") or ""),
        jumlah_kuartal=int(payload.get("count") or len(items)),
    )
    if not items:
        out.catatan.append("laporan keuangan kosong untuk emiten ini")
        return out

    item = items[0] if isinstance(items[0], dict) else {}
    data = item.get("data") or {}
    if not isinstance(data, dict):
        out.catatan.append("bentuk data tidak dikenali")
        return out

    out.label = str(item.get("label") or "")
    out.tahun = str(item.get("year") or "")
    out.kuartal = str(item.get("quarter") or "")
    out.jenis = deteksi_jenis(data)

    if out.jenis == JENIS_BANK:
        # Bank: pendapatan = pendapatan bunga (+ operasional lainnya), tidak ada laba bruto.
        out.pendapatan = _kemas(data.get(_BLOK_BANK))
        out.catatan.append("bank: laba bruto tidak berlaku (tidak ada beban pokok penjualan)")
    else:
        out.pendapatan = _kemas(data.get(_BLOK_UMUM))
        out.laba_bruto = _kemas(data.get("laba_bruto"))

    out.laba_operasional = _kemas(data.get("laba_operasional"))
    out.laba_sebelum_pajak = _kemas(data.get("laba_rugi_sebelum_pajak_penghasilan"))
    out.laba_bersih = _kemas(data.get("laba_rugi"))
    out.laba_komprehensif = _kemas(data.get("laba_rugi_komprehensif"))
    out.eps = _eps(data.get("laba_rugi_per_saham"))

    if out.pendapatan is None and out.laba_bersih is None:
        out.catatan.append("tidak ada angka pendapatan/laba yang terbaca dari kuartal terbaru")

    # Penjaga kewajaran EPS. Diuji 6 Okt 2026: Arjum mengirim EPS 0,0001 untuk BBRI dan
    # 0,0 untuk TLKM — padahal EPS BBRI seharusnya ratusan rupiah. Nilainya dibiarkan apa
    # adanya (sumbernya begitu), TAPI ditandai, karena EPS ~0 would membuat PER tak hingga
    # dan siapa pun yang memakainya akan menyimpulkan "saham ini tak bernilai".
    if out.eps is not None:
        laba = out.laba_bersih
        if out.eps == 0 or (laba is not None and laba > 1e11 and abs(out.eps) < 1):
            out.catatan.append(
                f"EPS {out.eps} mencurigakan (laba bersih {laba}) — jangan dipakai menghitung PER "
                "tanpa memeriksa ulang di sumber; kemungkinan satuan berbeda"
            )
    return out
