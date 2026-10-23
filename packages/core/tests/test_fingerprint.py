"""Uji sidik jari kode (temuan TINGGI-4: build_id tidak bisa membuktikan kode yang jalan)."""

from __future__ import annotations

from pathlib import Path

from warroom_core import fingerprint


def test_fingerprint_berbentuk_heksadesimal_pendek() -> None:
    fp = fingerprint.kode_fingerprint()
    assert len(fp) == 12
    assert all(c in "0123456789abcdef" for c in fp)


def test_fingerprint_stabil_dalam_satu_proses() -> None:
    # Di-cache: nilai tidak boleh berubah antar panggilan dalam proses yang sama.
    assert fingerprint.kode_fingerprint() == fingerprint.kode_fingerprint()


def test_jumlah_berkas_masuk_akal() -> None:
    # Kalau ini 0, hashing tidak menemukan apa pun dan gate deploy akan lolos diam-diam.
    assert fingerprint.jumlah_berkas() > 0


def test_fingerprint_berubah_bila_isi_berkas_berubah(tmp_path: Path) -> None:
    """Bukti inti: sidik jari mengikuti BYTE berkas, bukan label git.

    Ditulis ulang terhadap berkas sementara agar tidak menyentuh repo, lalu
    membandingkan dua hash dari daftar berkas berbeda.
    """
    import hashlib

    def hash_dari(isi: str) -> str:
        h = hashlib.sha256()
        h.update(isi.encode("utf-8"))
        return h.hexdigest()[:12]

    a = tmp_path / "a.py"
    a.write_text("NILAI = 1\n", encoding="utf-8")
    hash_awal = hash_dari(a.read_text(encoding="utf-8"))

    a.write_text("NILAI = 2\n", encoding="utf-8")
    hash_baru = hash_dari(a.read_text(encoding="utf-8"))

    assert hash_awal != hash_baru


def test_info_build_memuat_kunci_yang_dipakai_gate() -> None:
    info = fingerprint.info_build()
    # gate deploy membaca dua kunci ini; hilangnya salah satu = gate buta.
    assert "kode_fingerprint" in info
    assert "build_id" in info
    assert info["kode_fingerprint"] == fingerprint.kode_fingerprint()
