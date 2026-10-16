"""Regresi: sinyal terbaik per pasar (5 Okt 2026).

Yang dikunci:
1. Selalu mengembalikan SEMUA pasar (yang kosong pun) — UI tidak perlu tahu pasar mana yang
   kebetulan ada; kalau ini berubah, Home akan diam-diam kehilangan kartu.
2. Pasar kosong `ada=False` dan `skor=None` — BUKAN 0. Nol adalah angka; "tidak ada" bukan.
3. Skor crypto dihitung dari aturan yang lolos, dan kandidat PREMIUM dipilih di atas SKIP.
4. Klaim Polymarket yang belum lewat split beku WAJIB `terverifikasi=False` + catatan.
"""

from __future__ import annotations

from datetime import UTC, datetime

from warroom_core.db import Fact, session_scope
from warroom_core.market_signal import PASAR, best_signal_per_market


def _fakta(s, kind: str, key: str, value) -> None:
    s.add(Fact(kind=kind, key=key, value_json=value, source="uji",
               observed_at=datetime.now(UTC), ttl_s=3600, hash=f"h-{kind}-{key}"))


def test_selalu_semua_pasar(bersihkan_db) -> None:
    """Tanpa fakta apa pun, semua pasar tetap muncul — sebagai 'tidak ada', bukan hilang.

    `bersihkan_db`: pertanyaan tes ini adalah keadaan dunia KOSONG, jadi baris sisa
    berkas tes lain harus dibuang dulu (kalau tidak, hasilnya bergantung urutan).
    """
    with session_scope() as s:
        rows = best_signal_per_market(s)
    assert len(rows) == len(PASAR)
    assert {r.pasar for r in rows} == {k for k, _l, _s in PASAR}
    assert all(r.ada is False for r in rows)
    assert all(r.skor is None for r in rows), "kosong harus None, bukan 0"


def test_crypto_pilih_premium_dan_skor_dari_aturan(db) -> None:
    with session_scope() as s:
        _fakta(s, "snapshot", "kandidat", [
            {"pair": "SKIPUSDT", "direction": "LONG", "tier": "SKIP", "entry": 1.0, "sl": 0.9,
             "rules": [{"ok": True, "rule": "a"}, {"ok": False, "rule": "b"}]},
            {"pair": "BAGUSUSDT", "direction": "LONG", "tier": "PREMIUM", "entry": 2.0, "sl": 1.9,
             "tp1": 2.2, "rules": [{"ok": True, "rule": "a"}, {"ok": True, "rule": "b"}]},
        ])
    with session_scope() as s:
        rows = {r.pasar: r for r in best_signal_per_market(s)}
    c = rows["crypto"]
    assert c.ada is True
    assert c.subjek == "BAGUSUSDT", "PREMIUM harus menang atas SKIP"
    assert c.skor == 100
    assert c.terverifikasi is False
    assert "BUKAN edge terbukti" in c.catatan_kejujuran


def test_polymarket_klaim_tanpa_split_tidak_terverifikasi(db) -> None:
    """Klaim EDGE dengan split null = eksplorasi. Harus ditandai, bukan disembunyikan."""
    with session_scope() as s:
        _fakta(s, "poly.verdict", "verdict", {
            "winRate": 78.25, "breakEven_pct": 76.66, "ci95": [76.75, 79.67],
            "nNeeded": 7392, "verdict_alat": "EDGE", "split": None, "rule": "favorit btc/eth",
        })
    with session_scope() as s:
        rows = {r.pasar: r for r in best_signal_per_market(s)}
    p = rows["polymarket"]
    assert p.ada is True
    assert p.terverifikasi is False
    assert "BELUM TERVERIFIKASI" in p.catatan_kejujuran
    assert p.skor == 78
    # Temuan audit putaran 2: label mentah sumber "EDGE" TIDAK boleh diteruskan ke UI
    # selama split belum beku — kalau diteruskan, kartu Home bertentangan dengan gate.
    assert p.tier == "EKSPLORASI", f"tier tanpa split beku harus EKSPLORASI, bukan {p.tier}"
    assert p.arah == "TAHAN", "tanpa split beku, arah tidak boleh BELI (gate belum lolos)"


def test_polymarket_dengan_split_terverifikasi(db) -> None:
    """Split yang LOLOS verifikasi hash (id terdaftar + sha256 cocok) = terverifikasi.

    Hasil verifikasi dihitung lapisan pemanggil (splits.verifikasi) lalu diteruskan
    sebagai parameter — market_signal.py tidak query DB sendiri.
    """
    with session_scope() as s:
        _fakta(s, "poly.verdict", "verdict", {
            "winRate": 80.0, "breakEven_pct": 76.66, "verdict_alat": "EDGE",
            "split": "frozen:poly-paired-abc", "rule": "favorit btc/eth",
        })
    with session_scope() as s:
        rows = {r.pasar: r for r in best_signal_per_market(s, split_terverifikasi=True)}
    p = rows["polymarket"]
    assert p.terverifikasi is True
    assert "frozen:poly-paired-abc" in p.catatan_kejujuran
    assert p.tier == "EDGE"
    assert p.arah == "BELI"


def test_polymarket_split_mentah_tanpa_verifikasi_tetap_eksplorasi(db) -> None:
    """Label split saja TIDAK cukup: tanpa hasil verifikasi hash, tetap eksplorasi.

    Regresi inti — `bool(split)` mentah tidak boleh lagi meloloskan `terverifikasi`.
    """
    with session_scope() as s:
        _fakta(s, "poly.verdict", "verdict", {
            "winRate": 80.0, "breakEven_pct": 76.66, "verdict_alat": "EDGE",
            "split": "frozen:poly-paired-abc", "rule": "favorit btc/eth",
        })
    with session_scope() as s:
        rows = {r.pasar: r for r in best_signal_per_market(s)}
    p = rows["polymarket"]
    assert p.terverifikasi is False
    assert p.tier == "EKSPLORASI"
    assert p.arah == "TAHAN"
    assert "BELUM TERVERIFIKASI" in p.catatan_kejujuran


def test_polymarket_hash_berbeda_tidak_terverifikasi(db, tmp_path) -> None:
    """Split id TERDAFTAR tapi berkas berubah (sha256 beda) → terverifikasi False.

    Simulasi ujung-ke-ujung seperti lapisan pemanggil: bekukan dataset sungguhan,
    ubah berkasnya, hitung splits.verifikasi, teruskan hasilnya ke sinyal.
    """
    import gzip
    import json

    from warroom_core import splits

    d = tmp_path / "auto-uji-hash"
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps({"codeHashes": {"recorder": "abc"}}),
                                      encoding="utf-8")
    with gzip.open(d / "events-0000.jsonl.gz", "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "decision", "side": "Up", "token": "1"}) + "\n")
        fh.write(json.dumps({"kind": "resolution", "outcome": "won", "token": "1"}) + "\n")
    with session_scope() as s:
        hasil = splits.bekukan(s, dataset="paired", root=d, created_by="uji")
    # berkas berubah SETELAH dibekukan → hash tidak cocok lagi
    with gzip.open(d / "events-0000.jsonl.gz", "at", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "resolution", "outcome": "won", "token": "2"}) + "\n")
    with session_scope() as s:
        cocok = splits.verifikasi(s, hasil["id"])["cocok"]
    assert cocok is False, "pra-kondisi: verifikasi hash harus gagal setelah berkas diubah"
    with session_scope() as s:
        _fakta(s, "poly.verdict", "verdict", {
            "winRate": 80.0, "breakEven_pct": 76.66, "verdict_alat": "EDGE",
            "split": hasil["split"], "rule": "favorit btc/eth",
        })
    with session_scope() as s:
        rows = {r.pasar: r for r in best_signal_per_market(s, split_terverifikasi=cocok)}
    p = rows["polymarket"]
    assert p.terverifikasi is False
    assert p.tier == "EKSPLORASI", "hash beda = belum terverifikasi, label EDGE dilarang"
    assert p.arah == "TAHAN"


def test_lp_sorot_yang_harus_keluar(db) -> None:
    """Sinyal LP terpenting adalah yang harus KELUAR — itu keputusan, bukan info."""
    with session_scope() as s:
        _fakta(s, "snapshot", "lp_paper", {"posisi": [
            {"symbol": "AMAN", "verdict": "PANTAU", "alasan": "sehat", "notional": 30.0},
            {"symbol": "BAHAYA", "verdict": "KELUAR", "alasan": "IL -9% terlalu dalam", "notional": 30.0},
        ]})
    with session_scope() as s:
        rows = {r.pasar: r for r in best_signal_per_market(s)}
    lp = rows["lp"]
    assert lp.subjek == "BAHAYA"
    assert lp.arah == "KELUAR"


def test_idx_dan_forex_kosong_menyebut_alasan(bersihkan_db) -> None:
    with session_scope() as s:
        rows = {r.pasar: r for r in best_signal_per_market(s)}
    assert "BSJP" in rows["idx"].alasan
    assert rows["forex"].ada is False


# --- Timestamp sinyal (6 Okt): "kapan sinyal itu digenerate" --------------------------
# Kelas bug yang dicegah: UI menampilkan "X PELUANG" tanpa waktu — pembaca tidak bisa
# menilai apakah sinyalnya masih segar atau sisa semalam. `umur_s` (umur fakta di DB)
# TIDAK sama dengan umur sinyal; keduanya harus ada dan dibedakan.

def test_crypto_membawa_waktu_sinyal_terbaru(db) -> None:
    from warroom_core.db import Fact

    with session_scope() as s:
        s.add(
            Fact(
                kind="snapshot",
                key="kandidat",
                value_json=[
                    # kandidat terbaik (skor penuh) dibuat lebih lama…
                    {
                        "ts": "2026-10-06T08:00:00+00:00",
                        "pair": "AAAUSDT",
                        "direction": "LONG",
                        "tier": "STANDAR",
                        "entry": 1.0,
                        "sl": 0.9,
                        "tp1": 1.2,
                        "rules": [{"rule": "poi_valid", "ok": True}],
                    },
                    # …tetapi ada kandidat lebih baru; waktu itu yang dipakai.
                    {
                        "ts": "2026-10-06T13:00:00+00:00",
                        "pair": "BBBUSDT",
                        "direction": "SHORT",
                        "tier": "STANDAR",
                        "entry": 2.0,
                        "sl": 2.1,
                        "tp1": 1.8,
                        "rules": [{"rule": "poi_valid", "ok": True}],
                    },
                ],
                source="state/snapshot.json",
                observed_at=datetime.now(UTC),
                ttl_s=1800,
                hash="h-timestamp",
            )
        )
    with session_scope() as s:
        rows = {r.pasar: r for r in best_signal_per_market(s)}
    crypto = rows["crypto"]
    assert crypto.dibuat_pada == "2026-10-06T13:00:00+00:00"
    assert crypto.umur_sinyal_s is not None and crypto.umur_sinyal_s > 0


def test_idx_forex_membawa_entry_dan_waktu(db) -> None:
    from warroom_core.db import Fact

    with session_scope() as s:
        s.add(
            Fact(
                kind="snapshot",
                key="idx_sinyal",
                value_json={
                    "tersedia": True,
                    "entries": [
                        {
                            "ticker": "MPOW.JK",
                            "setup": "BSJP_ARA",
                            "arah": "LONG",
                            "entry": 105,
                            "sl": 102.38,
                            "tp1": 106.05,
                            "status": "CREATED",
                            "dibuat": "2026-10-06T09:00:00+07:00",
                        }
                    ],
                },
                source="state/snapshot.json",
                observed_at=datetime.now(UTC),
                ttl_s=1800,
                hash="h-idx",
            )
        )
        s.add(
            Fact(
                kind="snapshot",
                key="forex_sinyal",
                value_json={
                    "tersedia": True,
                    "entries": [
                        {
                            "pair": "XAUUSD",
                            "arah": "BUY",
                            "entry": 4151.8,
                            "sl": 4121.0,
                            "tp1": 4182.6,
                            "hasil": "SL",
                            "waktu": "2026-10-05T13:32:00+07:00",
                        }
                    ],
                },
                source="state/snapshot.json",
                observed_at=datetime.now(UTC),
                ttl_s=1800,
                hash="h-fx",
            )
        )
    with session_scope() as s:
        rows = {r.pasar: r for r in best_signal_per_market(s)}

    idx = rows["idx"]
    assert idx.ada is True
    assert idx.subjek == "MPOW.JK"
    assert idx.tier == "BSJP_ARA"
    assert idx.dibuat_pada == "2026-10-06T09:00:00+07:00"
    assert idx.detail["entry"] == 105

    fx = rows["forex"]
    assert fx.ada is True
    assert fx.subjek == "XAUUSD"
    assert fx.dibuat_pada == "2026-10-05T13:32:00+07:00"
    assert fx.detail["r"] is None
