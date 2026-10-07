"""Verdict kanonik per pasar — SATU sumber keputusan untuk seluruh UI (audit QA 7 Okt).

MASALAH YANG DIJAWAB
--------------------
Audit eksternal menemukan dua kelas kebingungan yang berulang:

1. **UI menyusun verdict sendiri.** Kartu ringkasan menulis satu hal, bagian gate menulis
   hal lain. Contoh nyata: kartu Polymarket menampilkan "EDGE TERBUKTI" sementara bagian
   evaluasi di halaman yang SAMA menyebut split belum dibekukan. Dua kesimpulan, satu
   halaman — pembaca tidak punya cara tahu mana yang berlaku.

2. **Satu angka untuk banyak arti.** "6 peluang" di Home mencampur kandidat, posisi paper,
   dan hasil yang belum lewat gate. Pembaca menyimpulkan "ada 6 yang layak dieksekusi".

KEPUTUSAN ARSITEKTUR
--------------------
Verdict dihitung DI SINI (backend), bukan di UI. UI hanya merender. Lima state dipisah
tegas karena pertanyaannya memang berbeda:

    signal_state     : ada kandidat atau tidak      (none | candidate | confirmed)
    evidence_state   : sekuat apa buktinya          (unknown | insufficient | directional |
                                                     preliminary | tuning)
    risk_state       : ada pelanggaran risiko?      (unknown | ok | warning | breach)
    execution_state  : jalurnya apa                (unknown | paper | frozen | live)
    promotion_state  : boleh dipromosikan?          (blocked | promotable)

`promotion_state` HANYA "promotable" bila SELURUH syarat lolos: evidence minimal
PRELIMINARY, tidak ada pelanggaran risiko, split beku (bila pasar memakainya), dan
mesinnya tidak beku. Selain itu `blocked` + `blocked_reason` yang bisa dibaca manusia.

Ini menegakkan aturan ADR-003 (split beku wajib) di satu tempat, sehingga tidak mungkin
lagi ada layar yang bilang "terbukti" sementara gate bilang "belum".
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session as SASession

from warroom_core.sinyal import PASAR, sinyal_terbaik_per_pasar

__all__ = ["Verdict", "verdict_semua_pasar", "verdict_pasar"]

# Tingkat pakem → urutan. Dipakai memutuskan apakah bukti sudah cukup untuk promosi.
_TINGKAT_URUT = {"INSUFFICIENT": 0, "DIRECTIONAL": 1, "PRELIMINARY": 2, "TUNING": 3}
_MIN_PROMOSI = "PRELIMINARY"

# Pasar yang mewajibkan split beku sebelum hasilnya boleh dipromosikan (ADR-003).
_WAJIB_SPLIT = {"polymarket"}


@dataclass
class Verdict:
    """Verdict kanonik satu pasar. UI merender ini, tidak menghitung ulang."""

    pasar: str
    label: str

    # Lima state — masing-masing menjawab satu pertanyaan berbeda.
    signal_state: str = "none"
    evidence_state: str = "unknown"
    risk_state: str = "unknown"
    execution_state: str = "unknown"
    promotion_state: str = "blocked"

    # Ringkasan manusia (satu baris, dipakai sebagai headline halaman pasar).
    headline: str = ""
    decision: str = ""
    blocked_reason: str | None = None

    # Bentuk boolean untuk pembaca yang hanya butuh tiga pertanyaan (usulan audit).
    observed_edge: bool = False
    validated_edge: bool = False
    promotable_edge: bool = False

    # Bukti pendukung, apa adanya (bukan kesimpulan).
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ke_utc(t: datetime | None) -> datetime | None:
    if t is None:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _fakta(s: SASession, key: str) -> Any:
    """Nilai fakta terbaru untuk satu kunci (kind apa pun) — None bila tidak ada."""
    from sqlalchemy import select

    from warroom_core.db import Fact

    f = s.scalars(
        select(Fact).where(Fact.key == key).order_by(Fact.observed_at.desc()).limit(1)
    ).first()
    return f.value_json if f else None


def _evidence_state(s: SASession, pasar: str) -> tuple[str, dict[str, Any]]:
    """Tingkat pakem + angka pendukungnya untuk satu pasar."""
    detail: dict[str, Any] = {}
    blok: dict[str, Any] = {}

    if pasar == "idx":
        blok = _fakta(s, "idx_akurasi") or {}
    else:
        pa = _fakta(s, "pasar_akurasi") or {}
        blok = (pa.get("pasar") or {}).get(pasar) or {}

    per_setup = blok.get("per_setup") or {}
    # Ambil setup dengan sampel terbanyak — sama dengan yang ditampilkan halaman pasar.
    kunci, seri = max(
        per_setup.items(), key=lambda kv: (kv[1].get("n") or 0), default=(None, None)
    )
    seri = seri or {}
    tingkat = str(seri.get("tingkat") or seri.get("pakem") or "").upper() or "UNKNOWN"

    detail["setup"] = seri.get("nama") or kunci
    detail["n"] = seri.get("n")
    detail["n_hari"] = seri.get("n_hari")
    detail["winrate_pct"] = seri.get("winrate_pct")
    detail["mean_r"] = seri.get("mean_r")
    detail["total_r"] = seri.get("total_r")
    detail["populasi"] = "trade tuntas di ledger"
    return tingkat, detail


def _risk_state(s: SASession, pasar: str) -> tuple[str, str | None, dict[str, Any]]:
    """Apakah ada pelanggaran risiko? Mengembalikan (state, alasan, detail)."""
    detail: dict[str, Any] = {}

    # IDX: pelanggaran 1R sudah dihitung dompet.py (invariant) — pakai itu, jangan dihitung ulang.
    if pasar == "idx":
        dompet = _fakta(s, "dompet") or {}
        idx = (dompet.get("pasar") or {}).get("idx") or {}
        inv = idx.get("invariant") or {}
        if inv:
            detail["pelanggaran_1r"] = inv.get("pelanggaran_1r")
            detail["terburuk"] = (inv.get("terburuk") or {}).get("r")
            if inv.get("model_breach"):
                return "breach", "model breach: rugi melebihi 1R (stop tidak bisa dieksekusi)", detail
            return "ok", None, detail

    # Pasar lain: dari fakta risiko (hari_ini_r negatif = rugi).
    rk = _fakta(s, "risiko") or _fakta(s, f"{pasar}_risiko") or {}
    hari = rk.get("hari_ini_r")
    batas = rk.get("batas_rugi_r")
    if isinstance(hari, (int, float)) and isinstance(batas, (int, float)) and batas > 0:
        rugi = max(0.0, -float(hari))
        detail["hari_ini_r"] = hari
        detail["batas_rugi_r"] = batas
        detail["kuota_terpakai_pct"] = round(100 * rugi / batas, 1)
        if rugi >= batas:
            return "breach", f"batas rugi harian terlampaui ({rugi:.2f}R / {batas:.2f}R)", detail
        if rugi >= 0.6 * batas:
            return "warning", f"kuota risiko terpakai {100 * rugi / batas:.0f}%", detail
        return "ok", None, detail
    return "unknown", None, detail


def _execution_state(s: SASession, pasar: str) -> tuple[str, str | None]:
    """Jalur eksekusi: paper (semua), beku (IDX), atau live (belum ada)."""
    if pasar == "idx":
        return "frozen", "mesin IDX dibekukan (cron Tencent pause) — ledger tidak bertambah"
    # Live belum pernah menyala; kalau nanti menyala, angkanya datang dari fakta arming.
    arming = _fakta(s, "live_arming") or {}
    if isinstance(arming, dict) and arming.get("armed") is True:
        return "live", None
    return "paper", None


def verdict_pasar(s: SASession, sp: Any) -> Verdict:
    """Verdict kanonik dari satu SinyalPasar + fakta pendukungnya."""
    pasar = sp.pasar
    label = sp.label

    # --- 1) signal_state: dari status_data yang sudah tegas (ada/kosong/gagal) ---
    if sp.status_data == "gagal":
        signal_state = "none"
    elif sp.ada:
        signal_state = "candidate"
    else:
        signal_state = "none"

    # --- 2) evidence_state ---
    evidence_state, ev_detail = _evidence_state(s, pasar)

    # --- 3) risk_state ---
    risk_state, risk_alasan, risk_detail = _risk_state(s, pasar)

    # --- 4) execution_state ---
    execution_state, exec_alasan = _execution_state(s, pasar)

    # --- 5) promotion_state: SEMUA syarat harus lolos ---
    alasan: list[str] = []
    if signal_state == "none":
        alasan.append("tidak ada kandidat aktif")
    if sp.status_data == "gagal":
        alasan.append("sumber data tidak terbaca")
    if _TINGKAT_URUT.get(evidence_state, -1) < _TINGKAT_URUT[_MIN_PROMOSI]:
        alasan.append(f"bukti {evidence_state.lower()} — belum sampai {_MIN_PROMOSI}")

    # EXPECTANCY harus positif. Tanpa syarat ini, setup yang sedang RUGI bisa berstatus
    # "lolos semua gate" hanya karena sampelnya sudah banyak — ditemukan saat menguji
    # modul ini: GMGN berlabel PRELIMINARY dengan win-rate 0% dan PnL negatif, tetapi
    # verdict-nya "LOLOS SEMUA GATE". Pakem mengukur KEMATANGAN SAMPEL, bukan arah hasil;
    # keduanya harus diperiksa.
    mean_r = ev_detail.get("mean_r")
    pnl = None
    if pasar == "gmgn":
        blok = _fakta(s, "pasar_akurasi") or {}
        gm = (blok.get("pasar") or {}).get("gmgn") or {}
        seri = (gm.get("per_setup") or {}).get("LP Terukur (mark lokal)") or {}
        pnl = seri.get("total_pnl_usd") or seri.get("pnl_usd")
    if isinstance(mean_r, (int, float)) and mean_r <= 0:
        alasan.append(f"ekspektasi {mean_r:+.3f} R/trade — belum positif")
    if pnl is not None and isinstance(pnl, (int, float)) and pnl <= 0:
        alasan.append(f"PnL kumulatif {pnl:+.2f} USD — belum positif")
    if risk_state == "breach":
        alasan.append(risk_alasan or "pelanggaran risiko")
    if execution_state == "frozen":
        alasan.append("mesin beku — data historis, bukan kondisi berjalan")
    if pasar in _WAJIB_SPLIT and not sp.terverifikasi:
        alasan.append("split data belum dibekukan (ADR-003) — hasil belum boleh dipromosikan")
    if not sp.terverifikasi and pasar in _WAJIB_SPLIT:
        pass  # sudah masuk di atas

    promotable = not alasan
    promotion_state = "promotable" if promotable else "blocked"

    # --- headline & decision: satu kalimat yang bisa dibaca operator ---
    if signal_state == "none" and sp.status_data == "gagal":
        headline = f"{label} — GAGAL SISTEM"
        decision = "periksa job pengumpul; ini bukan 'tidak ada sinyal'"
    elif signal_state == "none":
        headline = f"{label} — TIDAK ADA KANDIDAT"
        decision = "tidak ada yang perlu dipantau; mesin tetap berjalan"
    elif execution_state == "frozen":
        headline = f"{label} — BEKU / HISTORIS"
        decision = "jangan dipromosikan; angka lama, mesin tidak berjalan"
    elif risk_state == "breach":
        headline = f"{label} — MODEL BREACH"
        decision = "jangan diperbesar; rugi melebihi batas yang direncanakan"
    elif promotion_state == "blocked":
        headline = f"{label} — KANDIDAT, BELUM BISA DIPROMOSIKAN"
        decision = "boleh dipantau sebagai bukti; belum layak dijadikan dasar keputusan"
    else:
        headline = f"{label} — LOLOS SEMUA GATE"
        decision = "boleh dipromosikan ke tahap berikutnya (masih paper)"

    return Verdict(
        pasar=pasar,
        label=label,
        signal_state=signal_state,
        evidence_state=evidence_state,
        risk_state=risk_state,
        execution_state=execution_state,
        promotion_state=promotion_state,
        headline=headline,
        decision=decision,
        blocked_reason="; ".join(alasan) if alasan else None,
        observed_edge=bool(sp.ada),
        validated_edge=bool(sp.terverifikasi),
        promotable_edge=promotable,
        detail={
            "sinyal": {
                "subjek": sp.subjek,
                "arah": sp.arah,
                "skor": sp.skor,
                "tier": sp.tier,
                "status_data": sp.status_data,
                "umur_s": sp.umur_s,
            },
            "bukti": ev_detail,
            "risiko": risk_detail,
            "eksekusi": {"catatan": exec_alasan},
        },
    )


def verdict_semua_pasar(s: SASession) -> list[Verdict]:
    """Verdict kanonik untuk semua pasar, urut sesuai PASAR."""
    urutan = {k: i for i, (k, _l, _s) in enumerate(PASAR)}
    keluar = [verdict_pasar(s, sp) for sp in sinyal_terbaik_per_pasar(s)]
    keluar.sort(key=lambda v: urutan.get(v.pasar, 99))
    return keluar
