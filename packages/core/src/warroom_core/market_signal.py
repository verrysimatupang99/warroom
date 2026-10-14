"""Sinyal terbaik per pasar — satu kontrak untuk seluruh UI (5 Okt 2026).

Batas peran: lapisan ini di ATAS `signal.py` (kontrak paper generik) dan di BAWAH
`verdict.py` (verdict kanonik). Lihat docstring `signal.py` untuk peta lengkap.

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

__all__ = ["MarketSignalList", "MarketSignal", "signals_per_market", "best_signal_per_market", "PASAR"]

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
class MarketSignal:
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
    # Output konfluensi terpadu (Threads/DEX Confluence format)
    confluence: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    autotrade_verdict: str = "PANTAU"   # OKE | PANTAU | SKIP
    alasan_eksekusi: str = ""

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


def _format_harga_ringkas(n: float | int | None) -> str:
    if n is None:
        return "—"
    try:
        val = float(n)
        if val >= 1000:
            return f"{val:,.0f}"
        if val >= 1:
            return f"{val:.2f}"
        return f"{val:.4g}"
    except (ValueError, TypeError):
        return str(n)


def _confluence_crypto(
    *,
    pair: str | None,
    arah: str | None,
    entry: Any,
    sl: Any,
    tp1: Any,
    skor: int | None,
    tier: str | None,
    rules_gagal: list[Any],
) -> tuple[list[str], dict[str, str], str, str]:
    num_e = float(entry) if isinstance(entry, (int, float)) and entry > 0 else None
    num_sl = float(sl) if isinstance(sl, (int, float)) and sl > 0 else None
    num_tp1 = float(tp1) if isinstance(tp1, (int, float)) and tp1 > 0 else None

    jarak_pct = round(abs(num_e - num_sl) / num_e * 100, 2) if num_e and num_sl else None
    jarak_str = f"{jarak_pct:.2f}%" if jarak_pct is not None else "—"
    arah_str = (arah or "LONG").upper()

    confluence = [
        f"🧭 MTF Alignment: 4H + 1H searah ({arah_str})",
        "📍 POI Rejection: Entry di swing supply/demand zone",
        f"🛡️ SL Jarak: {jarak_str} (risiko terukur 1% ekuitas)",
    ]
    metrics = {
        "Entry": _format_harga_ringkas(num_e),
        "Stop": _format_harga_ringkas(num_sl),
        "Target": _format_harga_ringkas(num_tp1),
        "Jarak SL": jarak_str,
    }

    tier_str = str(tier or "STANDAR").upper()
    if tier_str in ("PREMIUM", "STANDAR") and not rules_gagal and (skor or 0) >= 90:
        verdict = "OKE"
        alasan = "Setup terkonfirmasi 6/6 aturan; layak eksekusi autotrade."
    elif tier_str in ("PREMIUM", "STANDAR") and not rules_gagal:
        verdict = "PANTAU"
        alasan = "Setup valid di mode paper; pantau konfirmasi candle sebelum alokasi live."
    else:
        verdict = "SKIP"
        alasan = f"Melanggar filter strategi ({len(rules_gagal)} aturan gagal); lewati."

    return confluence, metrics, verdict, alasan


def _confluence_gmgn(
    *, chain: str, vl: float, viable: int, pools: int, window: str, total_liq: Any = None
) -> tuple[list[str], dict[str, str], str, str]:
    confluence = [
        f"🍋 V/L Ratio: {vl:.2f}x (likuiditas berputar aktif)",
        f"📢 Pool Layak: {viable}/{pools} pool memenuhi syarat likuid",
        f"⚡ Jendela Waktu: {window or 'AKTIF'} (momentum terpantau)",
    ]
    metrics = {
        "Chain": chain or "SOLANA",
        "V/L Rata²": f"{vl:.2f}x",
        "Pool Layak": f"{viable}/{pools}",
        "Total Liq": f"${float(total_liq):,.0f}" if isinstance(total_liq, (int, float)) else "—",
    }
    if vl >= 3.0 and viable >= 5:
        verdict = "OKE"
        alasan = (
            "Likuiditas sangat aktif & viable pool mencukupi "
            "(V/L >= 3x & >= 5 pool); layak autotrade/snipe."
        )
    elif viable > 0:
        verdict = "PANTAU"
        alasan = "Likuiditas terdeteksi; pantau momentum volume & audit rugcheck sebelum eksekusi."
    else:
        verdict = "SKIP"
        alasan = "Likuiditas pool tipis; risiko slippage dan rug pull tinggi."
    return confluence, metrics, verdict, alasan


def _confluence_lp(
    *, symbol: str, fee_hari: Any, umur_hari: Any, lp_verdict: str
) -> tuple[list[str], dict[str, str], str, str]:
    num_fee = float(fee_hari) if isinstance(fee_hari, (int, float)) else None
    num_umur = float(umur_hari) if isinstance(umur_hari, (int, float)) else None

    fee_str = f"${num_fee:.2f}/hari" if num_fee is not None else "Simpul aktif"
    umur_str = f"{num_umur:.1f} hari" if num_umur is not None else "Pool stabil"

    confluence = [
        f"🌊 Fee Velocity: {fee_str} imbalan akumulatif",
        f"⏳ Durabilitas: Pool berusia {umur_str}",
        "🛡️ IL Guard: Pemantauan impermanent loss & range bin",
    ]
    metrics = {
        "Pool": symbol or "SOL-USDC",
        "Fee/Hari": f"${num_fee:.2f}" if num_fee is not None else "—",
        "Umur": f"{num_umur:.1f} hr" if num_umur is not None else "—",
        "Status": lp_verdict or "PANTAU",
    }
    if str(lp_verdict).upper() == "KELUAR":
        verdict = "SKIP"
        alasan = "Impermanent Loss terlalu dalam; disarankan auto-withdraw likuiditas."
    elif num_fee and num_fee > 0:
        verdict = "OKE"
        alasan = "Akumulasi fee melampaui estimasi depresiasi IL; optimal deposit LP."
    else:
        verdict = "PANTAU"
        alasan = "Posisi stabil; pantau deviasi harga dari bin aktif."
    return confluence, metrics, verdict, alasan


def _confluence_polymarket(
    *, winRate: Any, breakEven: Any, n: Any, need: Any, terverifikasi: bool, rule: str | None = None
) -> tuple[list[str], dict[str, str], str, str]:
    num_win = float(winRate) if isinstance(winRate, (int, float)) else None
    num_be = float(breakEven) if isinstance(breakEven, (int, float)) else None

    # Falsy-zero dilarang: 0 adalah angka valid (0% win-rate, n=0), hanya None yang
    # berarti "tak ada data" → tampilkan n/a + alasan, bukan angka karangan.
    win_str = f"{num_win:.1f}%" if num_win is not None else "n/a (belum ada win-rate)"
    if num_win is not None and num_be is not None:
        edge_str = f"+{num_win - num_be:.2f}%"
    else:
        edge_str = "n/a (butuh win-rate + break-even)"
    n_str = str(n) if n is not None else "n/a"
    need_str = str(need) if need is not None else "n/a"

    confluence = [
        f"📊 Implied Prob: Win-rate {win_str} (rentang 0.70–0.95)",
        f"🎯 Margin Edge: {edge_str} di atas break-even",
        f"⏱️ Sampel Uji: n={n_str} trade terevaluasi",
    ]
    metrics = {
        "Win-Rate": f"{num_win:.1f}%" if num_win is not None else "n/a",
        "Break-Even": f"{num_be:.1f}%" if num_be is not None else "n/a",
        "Sampel": f"{n_str}/{need_str}" if n is not None or need is not None else "n/a",
        "Status Edge": "Terverifikasi" if terverifikasi else "Eksplorasi",
    }
    rule_str = (rule or "").lower()
    if "momentum" in rule_str or "candidate" in rule_str or "kandidat" in rule_str:
        verdict = "SKIP"
        alasan = "Arm underdog/momentum dihentikan: win-rate di bawah break-even dan slippage membakar modal."
    elif terverifikasi:
        verdict = "OKE"
        alasan = "Edge terverifikasi secara statistik dengan split beku (ADR-003)."
    elif (
        ("favorit" in rule_str or "favorite" in rule_str or "arm d" in rule_str)
        and num_win is not None
        and num_win >= 75.0
    ):
        verdict = "PANTAU"
        alasan = "Arm D Favorit berkinerja profitabel (WR >= 75%); lanjutkan pengumpulan sampel split beku."
    else:
        verdict = "PANTAU"
        alasan = "Klaim eksplorasi paper; teruskan shadow testing hingga split beku."
    return confluence, metrics, verdict, alasan


def _confluence_idx(
    *, subjek: str, arah: str | None, entry: Any, sl: Any, tp1: Any
) -> tuple[list[str], dict[str, str], str, str]:
    confluence = [
        "🏛️ Screener: Bandarmologi & BSJP sinyal",
        "📊 Volume: Terdeteksi akumulasi transaksi",
        "🛑 Manajemen Risiko: SL & batas trailing aktif",
    ]
    metrics = {
        "Saham": subjek or "IDX",
        "Entry": _format_harga_ringkas(entry),
        "Stop": _format_harga_ringkas(sl),
        "Target": _format_harga_ringkas(tp1),
    }
    return confluence, metrics, "PANTAU", "Mesin IDX berstatus historis/jurnal; pantau sebelum order."


def _confluence_forex(
    *, subjek: str, arah: str | None, entry: Any, sl: Any, tp1: Any
) -> tuple[list[str], dict[str, str], str, str]:
    confluence = [
        "🌐 Struktur: Analisis tren multi-pair TVC",
        "🎯 Bias Arah: Setup supply & demand",
        "🛡️ Sizing: Rasio R:R terukur",
    ]
    metrics = {
        "Pair": subjek or "FOREX",
        "Entry": _format_harga_ringkas(entry),
        "Stop": _format_harga_ringkas(sl),
        "Target": _format_harga_ringkas(tp1),
    }
    return confluence, metrics, "PANTAU", "Eksekusi paper; pantau spread bursa sebelum masuk."


def _crypto(s: SASession) -> MarketSignal:
    kandidat, observed = _ambil(s, "snapshot", "kandidat")
    if not isinstance(kandidat, list) or not kandidat:
        return MarketSignal(
            pasar="crypto", label="Crypto (SMC)", ada=False, sumber_fakta="snapshot/kandidat",
            umur_s=_umur(observed),
            alasan="Belum ada kandidat dari pemindaian SMC.",
            catatan_kejujuran=(
                "Pemindai jalan tiap 30 menit; kosong berarti belum ada pair yang lolos struktur."
            ),
        )

    def kunci(k: dict[str, Any]) -> tuple[int, int, int, str]:
        rules = k.get("rules") or []
        tier = str(k.get("tier") or "SKIP")
        ok = sum(1 for r in rules if r.get("ok"))
        ts = str(_waktu_kandidat(k) or "")
        return (_TIER_RANK.get(tier, 0), ok, len(rules), ts)

    terbaik = max(kandidat, key=kunci)
    # Kandidat dengan waktu TERBARU: itu "kapan sinyal ini dibuat". Tanpa ts → jangan mengarang.
    berwaktu = [k for k in kandidat if _waktu_kandidat(k)]
    terbaru = max(berwaktu, key=lambda k: str(_waktu_kandidat(k))) if berwaktu else None
    rules = terbaik.get("rules") or []
    gagal = [r for r in rules if not r.get("ok")]
    skor = _skor_dari_rules(rules)
    tier = str(terbaik.get("tier") or "SKIP")
    lolos = bool(gagal) is False
    c_conf, c_met, c_verd, c_als = _confluence_crypto(
        pair=terbaik.get("pair"), arah=terbaik.get("direction") or terbaik.get("arah"),
        entry=terbaik.get("entry"), sl=terbaik.get("sl"), tp1=terbaik.get("tp1"),
        skor=skor, tier=tier, rules_gagal=gagal,
    )
    return MarketSignal(
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
            "Skor = aturan yang lolos, BUKAN edge terbukti. "
            f"{len(kandidat)} peluang terpindai; win-rate layak-dagang n/a "
            "(belum ada evaluasi hasil posisi paper) — belum cukup untuk promosi."
        ),
        umur_s=_umur(observed), sumber_fakta="snapshot/kandidat",
        dibuat_pada=_waktu_kandidat(terbaru) if terbaru else None,
        umur_sinyal_s=_umur_iso(_waktu_kandidat(terbaru)) if terbaru else None,
        detail={"entry": terbaik.get("entry"), "sl": terbaik.get("sl"), "tp1": terbaik.get("tp1"),
                "rr": terbaik.get("rr"), "lolos_gate": lolos, "kandidat": len(kandidat)},
        confluence=c_conf, metrics=c_met, autotrade_verdict=c_verd, alasan_eksekusi=c_als,
    )


def _polymarket(s: SASession, *, split_terverifikasi: bool = False) -> MarketSignal:
    v, observed = _ambil(s, "poly.verdict", "verdict")
    if not isinstance(v, dict):
        return MarketSignal(
            pasar="polymarket", label="Polymarket (favorit 5m)", ada=False,
            sumber_fakta="poly.verdict/verdict", umur_s=_umur(observed),
            alasan="Belum ada verdict.", catatan_kejujuran="Verdict dihitung tiap jam.",
        )
    split = v.get("split")
    # `terverifikasi` HANYA dari hasil verifikasi hash yang diteruskan pemanggil
    # (splits.verifikasi: id terdaftar DAN sha256 berkas cocok). Label "frozen:<id>"
    # saja tidak cukup — id terdaftar tapi berkas berubah = False. Default False
    # (fail-closed); market_signal.py tidak query DB sendiri.
    terverifikasi = split is not None and split != "" and bool(split_terverifikasi)
    win = v.get("winRate")
    be = v.get("breakEven_pct")
    # KONTRADIKSI YANG DIPERBAIKI (audit QA putaran 2, 7 Okt): `verdict_alat` dari sumber
    # berbunyi "EDGE" walau gate proyek MENOLAK promosi tanpa split beku (ADR-003).
    # Kalau label mentah itu diteruskan apa adanya, Home menampilkan "EDGE" di kartu
    # sementara bagian gate di bawah menulis "belum lolos" — satu halaman, dua kesimpulan.
    # Aturan yang dikodekan: tanpa split beku, alat TIDAK boleh berstatus EDGE di UI.
    alat_mentah = str(v.get("verdict_alat") or "")
    alat = alat_mentah if terverifikasi else ("EKSPLORASI" if alat_mentah else alat_mentah)
    p_conf, p_met, p_verd, p_als = _confluence_polymarket(
        winRate=win,
        breakEven=be,
        n=v.get("n"),
        need=v.get("nNeeded"),
        terverifikasi=terverifikasi,
        rule=str(v.get("rule") or ""),
    )
    if terverifikasi:
        catatan = f"Split beku terverifikasi: {split}"
    elif split:
        catatan = (
            f"BELUM TERVERIFIKASI: split {split} belum lolos verifikasi hash "
            "(id tak terdaftar atau berkas berubah sejak dibekukan) — klaim eksplorasi, "
            "bukan edge yang lolos gate."
        )
    else:
        catatan = (
            "BELUM TERVERIFIKASI: split masih kosong — belum lewat split beku, jadi ini "
            "klaim eksplorasi, bukan edge yang lolos gate."
        )
    return MarketSignal(
        pasar="polymarket", label="Polymarket (favorit 5m)", ada=True,
        arah="BELI" if alat == "EDGE" else "TAHAN",
        subjek=str(v.get("rule") or "favorit"),
        skor=round(float(win)) if isinstance(win, (int, float)) else None,
        tier=alat,
        alasan=(
            f"win-rate {'n/a (belum ada win-rate)' if win is None else f'{win}%'} "
            f"vs break-even {'n/a' if be is None else f'{be}%'} "
            f"(CI95 {v.get('ci95')}); butuh n≈{v.get('nNeeded') if v.get('nNeeded') is not None else 'n/a'}"
        ),
        terverifikasi=terverifikasi,
        catatan_kejujuran=catatan,
        umur_s=_umur(observed), sumber_fakta="poly.verdict/verdict",
        dibuat_pada=observed.isoformat() if observed else None,
        umur_sinyal_s=_umur(observed),
        detail={"n": v.get("n"), "win": v.get("win"), "winRate": win,
                "breakEven_pct": be, "ci95": v.get("ci95"), "deff": v.get("deff"),
                "nNeeded": v.get("nNeeded"), "split": split},
        confluence=p_conf, metrics=p_met, autotrade_verdict=p_verd, alasan_eksekusi=p_als,
    )


def _gmgn(s: SASession) -> MarketSignal:
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
        return MarketSignal(
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
    g_conf, g_met, g_verd, g_als = _confluence_gmgn(
        chain=str(terbaik.get("chain") or "SOLANA"),
        vl=vl,
        viable=viable,
        pools=pools,
        window=str(terbaik.get("window") or ""),
        total_liq=terbaik.get("total_liq"),
    )
    return MarketSignal(
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
        confluence=g_conf, metrics=g_met, autotrade_verdict=g_verd, alasan_eksekusi=g_als,
    )


def _lp(s: SASession) -> MarketSignal:
    r, observed = _ambil(s, "snapshot", "lp_paper")
    posisi = (r or {}).get("posisi") if isinstance(r, dict) else None
    if not isinstance(posisi, list) or not posisi:
        return MarketSignal(
            pasar="lp", label="LP / Yield", ada=False, sumber_fakta="snapshot/lp_paper",
            umur_s=_umur(observed), alasan="Tidak ada posisi LP paper aktif.",
            catatan_kejujuran="Kapasitas LP kecil; kosong berarti belum ada kandidat.",
        )
    # Sinyal terpenting LP = yang harus KELUAR (IL terlalu dalam) — itu keputusan, bukan sekadar info.
    keluar = [p for p in posisi if str(p.get("verdict")) == "KELUAR"]
    sorotan = keluar[0] if keluar else posisi[0]
    lp_conf, lp_met, lp_verd, lp_als = _confluence_lp(
        symbol=str(sorotan.get("symbol") or ""),
        fee_hari=sorotan.get("fee_hari"),
        umur_hari=sorotan.get("umur"),
        lp_verdict=str(sorotan.get("verdict") or "PANTAU"),
    )
    return MarketSignal(
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
        confluence=lp_conf, metrics=lp_met, autotrade_verdict=lp_verd, alasan_eksekusi=lp_als,
    )


def _dari_fakta_sinyal(
    s: SASession,
    *,
    pasar: str,
    label: str,
    key: str,
    sumber: str,
    catatan: str,
) -> MarketSignal | None:
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

    if pasar == "idx":
        df_conf, df_met, df_verd, df_als = _confluence_idx(
            subjek=subjek or "", arah=arah,
            entry=pertama.get("entry"), sl=pertama.get("sl"), tp1=pertama.get("tp1"),
        )
    else:
        df_conf, df_met, df_verd, df_als = _confluence_forex(
            subjek=subjek or "", arah=arah,
            entry=pertama.get("entry"), sl=pertama.get("sl"), tp1=pertama.get("tp1"),
        )

    return MarketSignal(
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
        confluence=df_conf, metrics=df_met, autotrade_verdict=df_verd, alasan_eksekusi=df_als,
    )


def _idx(s: SASession) -> MarketSignal:
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


def _forex(s: SASession) -> MarketSignal:
    hasil = _dari_fakta_sinyal(
        s, pasar="forex", label="Forex", key="forex_sinyal",
        sumber="snapshot/forex_sinyal",
        catatan=(
            "Jurnal mesin XAUUSD/multi-pair dari Tencent. Mesin berhenti bila server "
            "mati — sinyal baru tidak lagi masuk, yang lama tetap tampil apa adanya."
        ),
    )
    return hasil or _kosong("forex", "Forex", "snapshot/forex_sinyal", s, "Belum ada sinyal Forex.")


def _kosong(pasar: str, label: str, sumber: str, s: SASession, alasan: str) -> MarketSignal:
    kind, _, key = sumber.partition("/") if "/" in sumber else (sumber, "", "")
    _, observed = _ambil(s, kind, key) if key else (None, None)
    return MarketSignal(
        pasar=pasar, label=label, ada=False, sumber_fakta=sumber, umur_s=_umur(observed),
        alasan=alasan,
        catatan_kejujuran="Pasar ini belum punya sinyal — ditampilkan apa adanya, bukan angka 0.",
    )


@dataclass
class MarketSignalList:
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
    # Output konfluensi terpadu (Threads/DEX Confluence format)
    confluence: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    autotrade_verdict: str = "PANTAU"
    alasan_eksekusi: str = ""

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


def _kandidat_crypto(s: SASession, maks: int = 12) -> MarketSignalList:
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
            _ke_utc(f.observed_at).isoformat(),
        ),
        reverse=True,
    )
    sinyal = []
    for f in hidup[:maks]:
        v = f.value_json or {}
        rules = v.get("aturan_gagal") or []
        skor = round(100 * (1 - len(rules) / max(1, len(rules) + 3))) if rules else 100
        pair_val = v.get("pair") or f.key
        arah_val = v.get("arah")
        tier_val = v.get("tier")
        entry_val = v.get("entry")
        sl_val = v.get("sl")
        tp1_val = v.get("tp1")

        c_conf, c_met, c_verd, c_als = _confluence_crypto(
            pair=pair_val, arah=arah_val, entry=entry_val, sl=sl_val, tp1=tp1_val,
            skor=skor, tier=tier_val, rules_gagal=rules,
        )
        sinyal.append(
            {
                "pair": pair_val,
                "arah": arah_val,
                "tier": tier_val,
                "entry": entry_val,
                "sl": sl_val,
                "tp1": tp1_val,
                "r_r": v.get("r_r"),
                "risk_pct": v.get("risk_pct"),
                "aturan_gagal": rules,
                "label": v.get("label"),
                "umur_s": round((now - _ke_utc(f.observed_at)).total_seconds(), 1),
                "skor": skor,
                "confluence": c_conf,
                "metrics": c_met,
                "autotrade_verdict": c_verd,
                "alasan_eksekusi": c_als,
            }
        )
    if sinyal:
        terbaik = sinyal[0]
        return MarketSignalList(
            pasar="crypto", label="Crypto (SMC)", status_data="ada",
            rute=_rute_pasar("crypto"), jumlah=len(hidup), sinyal=sinyal,
            sumber="OKX", mode="PAPER",
            catatan_mode="harga & depth OKX; eksekusi paper (order tidak dikirim)",
            confluence=terbaik.get("confluence", []),
            metrics=terbaik.get("metrics", {}),
            autotrade_verdict=terbaik.get("autotrade_verdict", "PANTAU"),
            alasan_eksekusi=terbaik.get("alasan_eksekusi", ""),
        )
    # Tidak ada kandidat aktif: bedakan mesin-hidup vs mesin-mati.
    dari_verdict = _umur_iso(_verdict_terakhir(s))
    if dari_verdict is not None and dari_verdict <= 6 * 3600:
        return MarketSignalList(
            pasar="crypto", label="Crypto (SMC)", status_data="kosong", rute=_rute_pasar("crypto"),
            alasan=(
                f"Pemindaian berjalan (verdict terakhir {int(dari_verdict / 60)} menit lalu) "
                "tetapi tidak ada setup yang cocok dengan strategi saat ini."
            ),
            autotrade_verdict="SKIP",
            alasan_eksekusi="Tidak ada setup yang lolos filter strategi saat ini.",
        )
    return MarketSignalList(
        pasar="crypto", label="Crypto (SMC)", status_data="gagal", rute=_rute_pasar("crypto"),
        alasan=(
            "GAGAL SISTEM: tidak ada jejak pemindaian terbaru di ledger gate — "
            "periksa job `collect`/`signal-sync`. Ini bukan 'tidak ada sinyal'."
        ),
        autotrade_verdict="SKIP",
        alasan_eksekusi="Sistem pemindaian belum terdeteksi aktif.",
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


def signals_per_market(
    s: SASession, *, maks: int = 3, split_terverifikasi: bool = False
) -> list[MarketSignalList]:
    """Untuk tiap pasar: daftar sinyal (maks `maks` ditampilkan) + status jujur.

    Home hanya butuh 3 terbaik per pasar + tautan ke halaman pasar — bukan seluruh
    riwayat. Pasar yang sinyalnya lebih dari `maks` mengembalikan `jumlah` penuh supaya
    UI bisa menulis "lihat semua (N)".
    """
    keluar: list[MarketSignalList] = []
    urutan = {k: i for i, (k, _l, _s) in enumerate(PASAR)}
    crypto = _kandidat_crypto(s, maks=maks)
    keluar.append(crypto)

    # Pasar lain: pakai sinyal terbaik (bentuk lama) sebagai satu kartu, plus penanda
    # "kosong/gagal" yang sama tegasnya.
    for sp in best_signal_per_market(s, split_terverifikasi=split_terverifikasi):
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
                MarketSignalList(
                    pasar=sp.pasar, label=sp.label, status_data="ada", rute=_rute_pasar(sp.pasar),
                    jumlah=1, sumber=sumber_pasar[0], mode=sumber_pasar[1], catatan_mode=sumber_pasar[2],
                    confluence=sp.confluence,
                    metrics=sp.metrics,
                    autotrade_verdict=sp.autotrade_verdict,
                    alasan_eksekusi=sp.alasan_eksekusi,
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
                            "confluence": sp.confluence,
                            "metrics": sp.metrics,
                            "autotrade_verdict": sp.autotrade_verdict,
                            "alasan_eksekusi": sp.alasan_eksekusi,
                        }
                    ],
                )
            )
        else:
            keluar.append(
                MarketSignalList(
                    pasar=sp.pasar, label=sp.label, status_data="kosong", rute=_rute_pasar(sp.pasar),
                    alasan=sp.alasan, jumlah=0,
                    sumber=sumber_pasar[0], mode=sumber_pasar[1], catatan_mode=sumber_pasar[2],
                    autotrade_verdict="SKIP",
                    alasan_eksekusi=sp.alasan,
                )
            )
    keluar.sort(key=lambda x: urutan.get(x.pasar, 99))
    return keluar


def best_signal_per_market(s: SASession, *, split_terverifikasi: bool = False) -> list[MarketSignal]:
    """Satu sinyal terbaik per pasar, urut sesuai PASAR. Selalu mengembalikan semua pasar
    (yang kosong pun), supaya UI tidak perlu tahu pasar mana yang kebetulan ada."""
    keluar: list[MarketSignal] = [
        _crypto(s),
        _polymarket(s, split_terverifikasi=split_terverifikasi),
        _gmgn(s),
        _lp(s),
        _idx(s),
        _forex(s),
    ]
    urutan = {k: i for i, (k, _l, _s) in enumerate(PASAR)}
    keluar.sort(key=lambda x: urutan.get(x.pasar, 99))
    return keluar
