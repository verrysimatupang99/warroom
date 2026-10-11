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

__all__ = ["DaftarSinyal", "SinyalPasar", "sinyal_per_pasar", "sinyal_terbaik_per_pasar", "PASAR"]

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
    # Kapan sinyal ini DIGENERATE oleh mesinnya (ISO apa adanya), + umurnya saat ini.
    # Dipisah dari `umur_s` (umur FAKTA di DB) — pertanyaan owner 6 Okt: "status hari ini
    # X peluang itu ada timestamp kapan sinyal itu digenerate ya".
    dibuat_pada: str | None = None
    umur_sinyal_s: float | None = None
    # Status ketersediaan dipisah tegas (revisi owner 7 Okt):
    #   "ada"      — ada sinyal, disajikan
    #   "kosong"   — mesin HIDUP tapi tidak ada setup yang cocok dengan strategi. Ini
    #                hasil kerja sistem, bukan kegagalan. Ditulis "tidak ada sinyal".
    #   "gagal"    — sumber data tidak terbaca / mesin mati. INI failure yang harus
    #                berbunyi — jangan pernah disamarkan sebagai "tidak ada sinyal".
    status_data: str = "ada"
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


def _ke_utc(t: datetime) -> datetime:
    """Pastikan datetime punya tzinfo (DB bisa mengembalikan naive)."""
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _umur_iso(iso: str | None) -> float | None:
    """Umur dari string ISO mentah. Gagal parse → None (jujur, bukan 0)."""
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    return _umur(t)


def _skor_dari_rules(rules: list[dict[str, Any]]) -> int | None:
    """Skor = persentase aturan yang lolos. Hard rule yang gagal membuat skor kecil —
    itu benar: setup yang melanggar hard rule bukan setup yang 'hampir lolos'."""
    if not rules:
        return None
    ok = sum(1 for r in rules if r.get("ok"))
    return round(100 * ok / len(rules))


def _waktu_kandidat(k: dict[str, Any]) -> str | None:
    """Waktu sinyal dibuat, apa adanya dari kandidat (``ts`` ISO dari gate)."""
    for kunci in ("ts", "diambil", "waktu", "created_at"):
        nilai = k.get(kunci)
        if nilai:
            return str(nilai)
    return None


def _crypto(s: SASession) -> SinyalPasar:
    kandidat, observed = _ambil(s, "snapshot", "kandidat")
    if not isinstance(kandidat, list) or not kandidat:
        return SinyalPasar(
            pasar="crypto", label="Crypto (SMC)", ada=False, sumber_fakta="snapshot/kandidat",
            umur_s=_umur(observed),
            alasan="Belum ada kandidat dari pemindaian SMC.",
            catatan_kejujuran=(
                "Pemindai jalan tiap 30 menit; kosong berarti belum ada pair yang lolos struktur."
            ),
        )

    def kunci(k: dict[str, Any]) -> tuple[int, int, int]:
        rules = k.get("rules") or []
        tier = str(k.get("tier") or "SKIP")
        ok = sum(1 for r in rules if r.get("ok"))
        return (_TIER_RANK.get(tier, 0), ok, len(rules))

    terbaik = max(kandidat, key=kunci)
    # Kandidat dengan waktu TERBARU: itu "kapan sinyal ini dibuat". Tanpa ts → jangan mengarang.
    berwaktu = [k for k in kandidat if _waktu_kandidat(k)]
    terbaru = max(berwaktu, key=lambda k: str(_waktu_kandidat(k))) if berwaktu else None
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
        dibuat_pada=_waktu_kandidat(terbaru) if terbaru else None,
        umur_sinyal_s=_umur_iso(_waktu_kandidat(terbaru)) if terbaru else None,
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
    # KONTRADIKSI YANG DIPERBAIKI (audit QA putaran 2, 7 Okt): `verdict_alat` dari sumber
    # berbunyi "EDGE" walau gate proyek MENOLAK promosi tanpa split beku (ADR-003).
    # Kalau label mentah itu diteruskan apa adanya, Home menampilkan "EDGE" di kartu
    # sementara bagian gate di bawah menulis "belum lolos" — satu halaman, dua kesimpulan.
    # Aturan yang dikodekan: tanpa split beku, alat TIDAK boleh berstatus EDGE di UI.
    alat_mentah = str(v.get("verdict_alat") or "")
    alat = alat_mentah if terverifikasi else ("EKSPLORASI" if alat_mentah else alat_mentah)
    return SinyalPasar(
        pasar="polymarket", label="Polymarket (favorit 5m)", ada=True,
        arah="BELI" if alat == "EDGE" else "TAHAN",
        subjek=str(v.get("rule") or "favorit"),
        skor=round(float(win)) if isinstance(win, (int, float)) else None,
        tier=alat,
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
        dibuat_pada=observed.isoformat() if observed else None,
        umur_sinyal_s=_umur(observed),
        detail={"n": v.get("n"), "win": v.get("win"), "winRate": win,
                "breakEven_pct": be, "ci95": v.get("ci95"), "deff": v.get("deff"),
                "nNeeded": v.get("nNeeded"), "split": split},
    )


def _gmgn(s: SASession) -> SinyalPasar:
    # Radar ditulis job `gmgn-sync` dengan kind `gmgn` (bukan `snapshot`), dan daftar
    # jendelanya bernama `chains` (bukan `state`). Salah kind/nama = kartu "TIDAK ADA"
    # palsu di Home padahal radar hidup — ditemukan & diperbaiki 6 Okt.
    r, observed = _ambil(s, "gmgn", "radar")
    if not isinstance(r, dict):
        r, observed = _ambil(s, "snapshot", "radar")
    data = (r or {}).get("data") if isinstance(r, dict) else None
    state = None
    if isinstance(data, dict):
        state = data.get("state") if isinstance(data.get("state"), list) else data.get("chains")
    if not isinstance(state, list) or not state:
        # Fallback terakhir: bentuk panel snapshot (`_radar_panel`) — daftar `chains`.
        chains = (r or {}).get("chains") if isinstance(r, dict) else None
        state = chains if isinstance(chains, list) else state
    if not isinstance(state, list) or not state:
        return SinyalPasar(
            pasar="gmgn", label="DEX / Memecoin (GMGN)", ada=False, sumber_fakta="gmgn/radar",
            umur_s=_umur(observed), alasan="Belum ada data radar.",
            catatan_kejujuran="Radar butuh cache GMGN; kosong berarti belum ditarik.",
        )
    terbaik = max(state, key=lambda c: (float(c.get("avg_vl") or 0), int(c.get("viable") or 0)))
    vl = float(terbaik.get("avg_vl") or 0)
    viable, pools = int(terbaik.get("viable") or 0), int(terbaik.get("pools") or 0)
    # Waktu radar ditarik: `diambil_epoch` (sumber) → ISO; kalau tidak ada, waktu fakta.
    epoch = data.get("diambil_epoch") if isinstance(data, dict) else None
    waktu = None
    if isinstance(epoch, (int, float)) and epoch > 0:
        waktu = datetime.fromtimestamp(float(epoch), tz=UTC).isoformat()
    return SinyalPasar(
        pasar="gmgn", label="DEX / Memecoin (GMGN)", ada=True,
        arah="PANTAU", subjek=str(terbaik.get("chain") or ""),
        skor=round(100 * viable / pools) if pools else None,
        tier=str(terbaik.get("window") or ""),
        alasan=(
            f"V/L {vl:.2f} ({viable}/{pools} pool layak); {terbaik.get('note')}"
            if pools
            else f"V/L {vl:.2f}; {terbaik.get('note')}"
        ),
        terverifikasi=False,
        catatan_kejujuran=(
            "Ini kelayakan likuiditas, BUKAN edge arah harga. Belum ada bukti PnL dari venue ini."
        ),
        umur_s=_umur(observed), sumber_fakta="gmgn/radar",
        dibuat_pada=waktu or (observed.isoformat() if observed else None),
        umur_sinyal_s=_umur_iso(waktu) if waktu else _umur(observed),
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
        dibuat_pada=observed.isoformat() if observed else None,
        umur_sinyal_s=_umur(observed),
        detail={"notional": sorotan.get("notional"), "vl": sorotan.get("vl"),
                "fee_hari": sorotan.get("fee_hari"), "umur_hari": sorotan.get("umur"),
                "posisi": len(posisi)},
    )


def _dari_fakta_sinyal(
    s: SASession,
    *,
    pasar: str,
    label: str,
    key: str,
    sumber: str,
    catatan: str,
) -> SinyalPasar | None:
    """Sinyal terbaik dari fakta ``*_sinyal`` (diterbitkan pasar.py): entry teratas + waktu.

    Dipakai IDX & Forex — sebelumnya keduanya selalu "TIDAK ADA" di Home karena hanya
    membaca posisi kosong, padahal ledger sinyalnya berisi. Angka diambil apa adanya;
    baris tanpa waktu tetap tampil tanpa timestamp (tidak dikarang).
    """
    nilai, observed = _ambil(s, "snapshot", key)
    entries = (nilai or {}).get("entries") if isinstance(nilai, dict) else None
    if not isinstance(entries, list) or not entries:
        return None
    pertama = entries[0] if isinstance(entries[0], dict) else {}
    waktu = None
    for k in ("waktu", "dibuat", "ditutup"):
        if pertama.get(k):
            waktu = str(pertama[k])
            break
    subjek = str(pertama.get("pair") or pertama.get("ticker") or "") or None
    arah = str(pertama.get("arah") or "").upper() or None
    hasil = str(pertama.get("hasil") or pertama.get("status") or "")
    return SinyalPasar(
        pasar=pasar, label=label, ada=True,
        arah=arah, subjek=subjek, skor=None,
        tier=str(pertama.get("setup") or pertama.get("tier") or ""),
        alasan=(
            f"{len(entries)} sinyal di ledger; teratas {subjek or '—'} "
            f"{arah or ''} · status {hasil or '—'}"
        ),
        terverifikasi=False,
        catatan_kejujuran=catatan,
        umur_s=_umur(observed), sumber_fakta=sumber,
        dibuat_pada=waktu,
        umur_sinyal_s=_umur_iso(waktu),
        detail={
            "entry": pertama.get("entry"), "sl": pertama.get("sl"), "tp1": pertama.get("tp1"),
            "r": pertama.get("r") if pertama.get("r") is not None else pertama.get("net_r"),
            "setup": pertama.get("setup"), "zona": pertama.get("zona"), "tf": pertama.get("tf"),
            "entries": len(entries),
        },
    )


def _idx(s: SASession) -> SinyalPasar:
    hasil = _dari_fakta_sinyal(
        s, pasar="idx", label="IDX (bandarmologi/BSJP)", key="idx_sinyal",
        sumber="snapshot/idx_sinyal",
        catatan=(
            "Ledger mesin IDX (ARA/BSJP/INTRADAY). Mesin sinyalnya di Tencent dan sedang "
            "BEKU (cron di-pause) — ledger tidak bertambah, bukti tetap utuh."
        ),
    )
    return hasil or _kosong(
        "idx", "IDX (bandarmologi/BSJP)", "snapshot/idx_sinyal", s,
        "Belum ada sinyal IDX di ledger mesin; screener bandarmologi & BSJP belum menghasilkan kandidat.",
    )


def _forex(s: SASession) -> SinyalPasar:
    hasil = _dari_fakta_sinyal(
        s, pasar="forex", label="Forex", key="forex_sinyal",
        sumber="snapshot/forex_sinyal",
        catatan=(
            "Jurnal mesin XAUUSD/multi-pair dari Tencent. Mesin berhenti bila server "
            "mati — sinyal baru tidak lagi masuk, yang lama tetap tampil apa adanya."
        ),
    )
    return hasil or _kosong("forex", "Forex", "snapshot/forex_sinyal", s, "Belum ada sinyal Forex.")


def _kosong(pasar: str, label: str, sumber: str, s: SASession, alasan: str) -> SinyalPasar:
    kind, _, key = sumber.partition("/") if "/" in sumber else (sumber, "", "")
    _, observed = _ambil(s, kind, key) if key else (None, None)
    return SinyalPasar(
        pasar=pasar, label=label, ada=False, sumber_fakta=sumber, umur_s=_umur(observed),
        alasan=alasan,
        catatan_kejujuran="Pasar ini belum punya sinyal — ditampilkan apa adanya, bukan angka 0.",
    )


@dataclass
class DaftarSinyal:
    """Kumpulan sinyal SATU pasar untuk Home (maks 3 ditampilkan + tautan ke halaman)."""

    pasar: str
    label: str
    status_data: str            # ada | kosong | gagal
    alasan: str = ""
    rute: str = ""              # tautan "lihat semua"
    jumlah: int = 0
    # QA 7 Okt: pembaca tidak boleh menebak apakah angka ini LIVE, PAPER, atau HISTORIS.
    # `sumber` = dari mana angka datang; `mode` = tingkat kepercayaan eksekusi.
    sumber: str = ""
    mode: str = "PAPER"          # LIVE (belum ada) · PAPER · HISTORIS (beku/tidak diperbarui)
    catatan_mode: str = ""
    sinyal: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rute_pasar(pasar: str) -> str:
    return {
        "crypto": "/crypto?sub=setup",
        "polymarket": "/polymarket?sub=setup-b",
        "gmgn": "/gmgn?sub=memecoin",
        "lp": "/gmgn?sub=lp",
        "idx": "/idx?sub=sinyal",
        "forex": "/forex?sub=struktur",
    }.get(pasar, f"/{pasar}")


def _kandidat_crypto(s: SASession, maks: int = 12) -> DaftarSinyal:
    """Sinyal crypto AKTIF dari fakta `signal/*` (kind signal) — urut skor aturan.

    Dipisah tegas: tidak ada fakta sama sekali BISA berarti (a) mesin baru selesai dan
    memang tak ada setup, atau (b) mesin mati. Kita cek jejak `verdicts` terakhir:
    kalau ada verdict baru (< 6 jam), berarti mesin hidup → "kosong"; kalau tidak,
    → "gagal" (jangan pernah disebut "tidak ada sinyal").
    """
    rows = s.scalars(
        select(Fact).where(Fact.kind == "signal").order_by(Fact.observed_at.desc())
    ).all()
    now = datetime.now(UTC)
    # `facts` menyimpan SATU BARIS PER PENGAMATAN (ADR-005) — jadi satu pair bisa punya
    # puluhan baris. Ambil yang TERBARU per pair saja; kalau tidak, 6 kandidat terbaca
    # sebagai 53 (bug yang langsung terlihat di hitungan Home).
    terbaru: dict[str, Fact] = {}
    for f in rows:
        if f.key not in terbaru:
            terbaru[f.key] = f
    hidup: list[Fact] = []
    for f in terbaru.values():
        obs = _ke_utc(f.observed_at)
        if (now - obs).total_seconds() <= f.ttl_s:
            hidup.append(f)
    hidup.sort(
        key=lambda f: (
            _TIER_RANK.get(str((f.value_json or {}).get("tier") or "").upper(), 0),
            -len((f.value_json or {}).get("aturan_gagal") or []),
        ),
        reverse=True,
    )
    sinyal = []
    for f in hidup[:maks]:
        v = f.value_json or {}
        rules = v.get("aturan_gagal") or []
        sinyal.append(
            {
                "pair": v.get("pair") or f.key,
                "arah": v.get("arah"),
                "tier": v.get("tier"),
                "entry": v.get("entry"),
                "sl": v.get("sl"),
                "tp1": v.get("tp1"),
                "r_r": v.get("r_r"),
                "risk_pct": v.get("risk_pct"),
                "aturan_gagal": rules,
                "label": v.get("label"),
                "umur_s": round((now - _ke_utc(f.observed_at)).total_seconds(), 1),
                "skor": round(100 * (1 - len(rules) / max(1, len(rules) + 3))) if rules else 100,
            }
        )
    if sinyal:
        return DaftarSinyal(
            pasar="crypto", label="Crypto (SMC)", status_data="ada",
            rute=_rute_pasar("crypto"), jumlah=len(hidup), sinyal=sinyal,
            sumber="OKX", mode="PAPER",
            catatan_mode="harga & depth OKX; eksekusi paper (order tidak dikirim)",
        )
    # Tidak ada kandidat aktif: bedakan mesin-hidup vs mesin-mati.
    dari_verdict = _umur_iso(_verdict_terakhir(s))
    if dari_verdict is not None and dari_verdict <= 6 * 3600:
        return DaftarSinyal(
            pasar="crypto", label="Crypto (SMC)", status_data="kosong", rute=_rute_pasar("crypto"),
            alasan=(
                f"Pemindaian berjalan (verdict terakhir {int(dari_verdict / 60)} menit lalu) "
                "tetapi tidak ada setup yang cocok dengan strategi saat ini."
            ),
        )
    return DaftarSinyal(
        pasar="crypto", label="Crypto (SMC)", status_data="gagal", rute=_rute_pasar("crypto"),
        alasan=(
            "GAGAL SISTEM: tidak ada jejak pemindaian terbaru di ledger gate — "
            "periksa job `collect`/`signal-sync`. Ini bukan 'tidak ada sinyal'."
        ),
    )


def _verdict_terakhir(s: SASession) -> str | None:
    """Waktu verdict crypto terakhir dari fakta snapshot/kandidat (kalau ada)."""
    f = s.scalars(
        select(Fact)
        .where(Fact.kind == "snapshot", Fact.key == "kandidat")
        .order_by(Fact.observed_at.desc())
        .limit(1)
    ).first()
    if f is None or not isinstance(f.value_json, list) or not f.value_json:
        return None
    return str((f.value_json[-1] or {}).get("ts") or "") or None


def sinyal_per_pasar(s: SASession, *, maks: int = 3) -> list[DaftarSinyal]:
    """Untuk tiap pasar: daftar sinyal (maks `maks` ditampilkan) + status jujur.

    Home hanya butuh 3 terbaik per pasar + tautan ke halaman pasar — bukan seluruh
    riwayat. Pasar yang sinyalnya lebih dari `maks` mengembalikan `jumlah` penuh supaya
    UI bisa menulis "lihat semua (N)".
    """
    keluar: list[DaftarSinyal] = []
    urutan = {k: i for i, (k, _l, _s) in enumerate(PASAR)}
    crypto = _kandidat_crypto(s, maks=maks)
    keluar.append(crypto)

    # Pasar lain: pakai sinyal terbaik (bentuk lama) sebagai satu kartu, plus penanda
    # "kosong/gagal" yang sama tegasnya.
    for sp in sinyal_terbaik_per_pasar(s):
        if sp.pasar == "crypto":
            continue
        sumber_pasar = {
            "idx": (
                "Stock Arjum",
                "HISTORIS",
                "mesin dibekukan (cron Tencent pause) — angka lama, tidak diperbarui",
            ),
            "forex": (
                "TVC (TradingView)",
                "PAPER",
                "bias/struktur dari seri TVC; eksekusi paper, biaya belum tercatat",
            ),
            "polymarket": ("Dokumentasi Polymarket", "PAPER", "arm B favorit 0,70–0,95; ledger shadow/paper"),
            "gmgn": ("GMGN / FOMO", "PAPER", "radar + bot paper; belum ada eksekusi on-chain"),
            "lp": ("Meteora (Solana)", "PAPER", "posisi LP disimulasikan; belum direkonsiliasi on-chain"),
        }.get(sp.pasar, ("—", "PAPER", ""))
        if sp.ada:
            keluar.append(
                DaftarSinyal(
                    pasar=sp.pasar, label=sp.label, status_data="ada", rute=_rute_pasar(sp.pasar),
                    jumlah=1, sumber=sumber_pasar[0], mode=sumber_pasar[1], catatan_mode=sumber_pasar[2],
                    sinyal=[
                        {
                            "pair": sp.subjek,
                            "arah": sp.arah,
                            "tier": sp.tier,
                            "entry": (sp.detail or {}).get("entry"),
                            "sl": (sp.detail or {}).get("sl"),
                            "tp1": (sp.detail or {}).get("tp1"),
                            "r_r": (sp.detail or {}).get("rr"),
                            "risk_pct": None,
                            "aturan_gagal": [],
                            "label": sp.catatan_kejujuran,
                            "umur_s": (
                                sp.umur_sinyal_s if sp.umur_sinyal_s is not None else sp.umur_s
                            ),
                            "skor": sp.skor,
                        }
                    ],
                )
            )
        else:
            keluar.append(
                DaftarSinyal(
                    pasar=sp.pasar, label=sp.label, status_data="kosong", rute=_rute_pasar(sp.pasar),
                    alasan=sp.alasan, jumlah=0,
                    sumber=sumber_pasar[0], mode=sumber_pasar[1], catatan_mode=sumber_pasar[2],
                )
            )
    keluar.sort(key=lambda x: urutan.get(x.pasar, 99))
    return keluar


def sinyal_terbaik_per_pasar(s: SASession) -> list[SinyalPasar]:
    """Satu sinyal terbaik per pasar, urut sesuai PASAR. Selalu mengembalikan semua pasar
    (yang kosong pun), supaya UI tidak perlu tahu pasar mana yang kebetulan ada."""
    keluar: list[SinyalPasar] = [
        _crypto(s),
        _polymarket(s),
        _gmgn(s),
        _lp(s),
        _idx(s),
        _forex(s),
    ]
    urutan = {k: i for i, (k, _l, _s) in enumerate(PASAR)}
    keluar.sort(key=lambda x: urutan.get(x.pasar, 99))
    return keluar
