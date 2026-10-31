"""Per-market signal & accuracy engine — one contract for all markets.

Owner's brief: "dashboard digunakan untuk menampilkan sinyal, akurasi sinyal, data pnl
per market berdasarkan sinyal, dan entry setup per sinyal per market; pastikan isinya
disesuaikan dengan keunikan masing-masing market berdasarkan strategi/metode."

Yang dikodekan di sini:

- **Satu kontrak, isi per market.** Semua market mengembalikan bentuk yang sama
  (``sinyal``: daftar entry + strategi; ``akurasi``: seri + pakem) tetapi KOLOM
  entry tetap khas marketnya (crypto: POI/ATR/gate; forex: zona/konfluensi;
  LP: IL/fee; Polymarket: win-rate/skip).
- **Angka terukur, bukan selera.** Semua metrik dihitung dari berkas yang sudah ada
  (``verdicts.jsonl``, ``crypto_equity.jsonl``, ``forex_journal.json``,
  ``lp_ledger.jsonl``, shadow summary Polymarket). Tidak ada angka karangan.
- **Pakem bukti satu standar** (``pakem.py``): n efektif per hari, INSUFFICIENT →
  TUNING. Market yang serinya bukan R (LP = P&L %, Polymarket = entri menang/kalah)
  TIDAK dipaksa jadi R; dipakai penilaian n yang sama + catatan jujur apa yang
  belum bisa dihitung.
- **Epoch & suplai dikatakan apa adanya.** Crypto & forex berasal dari mesin di
  Tencent (cron Hermes). Kalau server itu mati, sinyal berhenti bertambah — fakta
  itu WAJIB tampil di UI, bukan disembunyikan.

Modul murni baca berkas; tidak menyentuh jaringan dan tidak menulis apa pun.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .pakem import AMBANG_DIRECTIONAL, AMBANG_PRELIMINARY, AMBANG_TUNING, evaluate_pakem, wilson_interval

__all__ = [
    "STRATEGI_PASAR",
    "ringkas_akurasi_pasar",
    "ringkas_crypto_sinyal",
    "ringkas_forex_sinyal",
    "ringkas_idx_sinyal",
]

# ---------------------------------------------------------------------------
# Registry strategi per market. Status HANYA tiga: aktif / paper / rencana.
# "aktif"  = ada mesin yang berjalan & bukti tersimpan
# "paper"  = jalan tanpa uang nyata / simulasi
# "rencana"= belum dipakai sama sekali (jujur: jangan tampak seperti aktif)
# ---------------------------------------------------------------------------
STRATEGI_PASAR: dict[str, list[dict[str, Any]]] = {
    "crypto": [
        {
            "nama": "SMC multi-timeframe (OB/FVG + gate 2-dari-4 POI)",
            "status": "aktif",
            "sumber": "cron Hermes Tencent `crypto-5agent-pipeline-653` → verdicts.jsonl",
        },
        {
            "nama": "Fibonacci Golden Pocket Pullback (0,618–0,786)",
            "status": "aktif",
            "sumber": "live_trading.signals.golden_pullback → SMC Golden Pullback v1",
        },
        {
            "nama": "Orderbook Imbalance Scalping (L2 depth)",
            "status": "rencana",
            "sumber": "rencana riset L2 orderbook — belum diuji walk-forward",
        },
    ],
    "idx": [
        # Status IDX diselaraskan dari bukti ledger: BSJP terbukti positif,
        # sedangkan ARA Hunter dan INTRADAY dihentikan karena drawdowns/ekspektansi negatif.
        {"nama": "ARA Hunter", "status": "dihentikan", "sumber": "ledger idx616 (grader v3): -139,08R"},
        {
            "nama": "BSJP (Beli Sore Jual Pagi)",
            "status": "aktif",
            "sumber": "walk-forward Tencent + peringkat lokal (+20,51R BSJP_STRONG)",
        },
        {"nama": "Scalping INTRADAY", "status": "dihentikan", "sumber": "ledger idx616 (grader v3): -0,38R"},
        {"nama": "Bandarmologi (broker summary, ATS)", "status": "paper", "sumber": "Arjum + screener lokal"},
    ],
    "forex": [
        {
            "nama": "SMC XAUUSD (4-agen: struktur+berita+risiko)",
            "status": "aktif",
            "sumber": "cron Hermes Tencent `xauusd-smc-daily-signal` → xauusd_journal",
        },
        {
            "nama": "SMC FVG/OB multi-pair (NAS100, EURUSD)",
            "status": "aktif",
            "sumber": "cron Hermes Tencent `multi-pair-signal` → multipair_journal",
        },
    ],
    "gmgn": [
        {
            "nama": "LP Terukur (Meteora DAMM v2 / DEX)",
            "status": "paper",
            "sumber": "lp_ledger.jsonl (mark lokal)",
        },
        {
            "nama": "Radar rantai & memecoin (GMGN)",
            "status": "aktif",
            "sumber": "radar lokal Webdock (filter V/L >= 3x & 0 HP)",
        },
        {
            "nama": "FOMO Family (LP Army kasus BAGSPAY)",
            "status": "rencana",
            "sumber": "butuh uji ulang ide — bukan sinyal",
        },
    ],
    "polymarket": [
        {
            "nama": "Momentum 5m (arm A)",
            "status": "rencana",
            "sumber": "shadow summary poly-pilot (underdog win-rate rendah — dihentikan)",
        },
        {
            "nama": "Kandidat (arm B)",
            "status": "rencana",
            "sumber": "shadow summary poly-paper-candidate (slippage di bawah BE — dihentikan)",
        },
        {"nama": "Fade (arm C)", "status": "paper", "sumber": "shadow summary poly-paper-fade"},
        {
            "nama": "Favorit 0,70–0,95 (arm D)",
            "status": "aktif",
            "sumber": "shadow summary poly-paper-favorite (win-rate 82,35%, profitabel)",
        },
    ],
}

# ---------------------------------------------------------------------------
# Utilitas
# ---------------------------------------------------------------------------

def _baca_json(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # Baca langsung saja: sumber state milik admin, dan sudo di konteks service
        # pasti ditolak — `default` di sini berarti belum ada/rusak, bukan nol.
        return default


def _baca_jsonl(p: Path, maks: int | None = None) -> list[dict[str, Any]]:
    baris: list[dict[str, Any]] = []
    try:
        with p.open(encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    d = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                if isinstance(d, dict):
                    baris.append(d)
    except OSError:
        return []
    if maks is not None:
        baris = baris[-maks:]
    return baris


def _tgl(d: Any) -> str:
    return str(d or "")[:10]


def _r_r(entry: Any, sl: Any, tp1: Any) -> float | None:
    try:
        e, s, t = float(entry), float(sl), float(tp1)
        risiko = abs(e - s)
        if risiko <= 0:
            return None
        return round(abs(t - e) / risiko, 2)
    except (TypeError, ValueError):
        return None


def _pakem_hitung(n: int, menang: int) -> dict[str, Any]:
    """Penilaian pakem untuk seri yang BUKAN R (mis. entri menang/kalah Polymarket).

    Ambangnya sama (hari/trade efektif), tetapi karena hari tidak tersedia dipakai
    jumlah entri DAN alasan wajib menyebutkan itu. Tidak ada R yang dikarang.
    """
    if n == 0:
        tingkat = "INSUFFICIENT"
    elif n < AMBANG_DIRECTIONAL:
        tingkat = "INSUFFICIENT"
    elif n < AMBANG_PRELIMINARY:
        tingkat = "DIRECTIONAL"
    elif n < AMBANG_TUNING:
        tingkat = "PRELIMINARY"
    else:
        tingkat = "TUNING"
    bawah, atas = wilson_interval(menang, n)
    return {
        "tingkat": tingkat,
        "n": n,
        "n_hari": None,
        "ci_winrate": [round(bawah, 4), round(atas, 4)],
        "catatan": ["hari independen tidak tersedia — ambang dihitung dari jumlah entri"],
    }


def _baris_akurasi(
    seri: list[dict[str, Any]],
    *,
    nama: str,
    kunci_r: str = "r",
    kunci_tanggal: str = "closed_at",
    biaya_tercatat: bool | None = None,
) -> dict[str, Any]:
    """Satu baris akurasi (market/setup) memakai pakem yang sama dengan IDX."""
    hasil = evaluate_pakem(seri, kunci_r=kunci_r, kunci_tanggal=kunci_tanggal, biaya_tercatat=biaya_tercatat)
    d = hasil.as_dict()
    d["nama"] = nama
    # Ratakan ringkas (n, mean_r, winrate_pct, …) ke tingkat atas supaya UI tinggal baca
    # satu lapis — tabel tetap satu bentuk untuk semua market.
    d.update(hasil.ringkas)
    # JSON tidak mengenal Infinity (Postgres jsonb menolaknya). "Tanpa kerugian" tetap
    # dilaporkan sebagai catatan, bukan angka ajaib yang bikin fakta gagal terbit.
    def _bersih(pf: object) -> object:
        if isinstance(pf, float) and not math.isfinite(pf):
            return None
        return pf

    d["profit_factor"] = _bersih(d.get("profit_factor"))
    if isinstance(d.get("ringkas"), dict):
        ringkas = d["ringkas"]
        if isinstance(ringkas.get("profit_factor"), float) and not math.isfinite(ringkas["profit_factor"]):
            ringkas["profit_factor"] = None
            ringkas["profit_factor_note"] = "tak terhingga — belum ada loss tercatat"
    return d


def _per_hari(seri: list[dict[str, Any]], kunci_tanggal: str = "closed_at") -> list[dict[str, Any]]:
    """Ringkas per hari (untuk kurva/kalender kecil): jumlah, menang, total R."""
    hari: dict[str, dict[str, Any]] = {}
    for row in seri:
        t = _tgl(row.get(kunci_tanggal))
        if not t:
            continue
        h = hari.setdefault(t, {"tanggal": t, "n": 0, "menang": 0, "total_r": 0.0})
        r = row.get("r")
        if r is None:
            continue
        h["n"] += 1
        h["total_r"] = round(h["total_r"] + float(r), 4)
        if float(r) > 0:
            h["menang"] += 1
    return sorted(hari.values(), key=lambda x: x["tanggal"])


# ---------------------------------------------------------------------------
# CRYPTO — sinyal & entry setup (verdicts.jsonl + watchlist)
# ---------------------------------------------------------------------------

def _aturan_ke_nama(rule: str) -> str:
    """Nama manusia untuk aturan gate crypto (dari engine) — dipakai tabel 'dimensi'."""
    return {
        "mtf_alignment": "MTF alignment (1D/4H/1H)",
        "poi_valid": "POI SMC (OB/FVG) valid",
        "freshness": "Kesegaran POI (harga masih dekat)",
        "sl_distance": "Jarak SL vs ATR",
        "atr_min": "ATR minimum (volatilitas)",
        "risk_pct": "Risiko per trade ≤ batas",
    }.get(str(rule), str(rule))


def ringkas_crypto_sinyal(state_dir: Path) -> dict[str, Any]:
    """Sinyal crypto terbaru + skor aturan + entry setup, dari mesin yang sama dengan ledger."""
    verdicts = _baca_jsonl(state_dir / "verdicts.jsonl", maks=400)
    watch = _baca_json(state_dir / "crypto-watchlist.json") or {}
    items = watch.get("items") or []

    entries: list[dict[str, Any]] = []
    for v in verdicts[-14:]:
        rules = v.get("rules") or []
        ok = sum(1 for r in rules if r.get("ok"))
        gagal = [str(r.get("rule")) for r in rules if not r.get("ok")]
        aturan = [
            {
                "rule": str(r.get("rule")),
                "nama": _aturan_ke_nama(str(r.get("rule"))),
                "ok": bool(r.get("ok")),
                "hard": bool(r.get("hard")),
                "alasan": str(r.get("reason") or ""),
            }
            for r in rules
        ]
        ver_ts = v.get("ts")
        try:
            ts_parse = dt.datetime.fromisoformat(str(ver_ts).replace("Z", "+00:00"))
            umur = round((datetime.now(UTC) - ts_parse).total_seconds() / 3600, 1)
        except (TypeError, ValueError):
            umur = None
        entries.append(
            {
                "pair": v.get("pair"),
                "arah": v.get("direction"),
                "tier": v.get("tier"),
                "status": "lolos" if v.get("allowed") else "ditolak",
                "umur_jam": umur,
                "skor": round(100 * ok / len(rules)) if rules else None,
                "ok": ok,
                "total_aturan": len(rules),
                "aturan_gagal": gagal,
                "aturan": aturan,
                "entry": v.get("entry"),
                "sl": v.get("sl"),
                "tp1": v.get("tp1"),
                "r_r": _r_r(v.get("entry"), v.get("sl"), v.get("tp1")),
                "risk_pct": v.get("risk_pct"),
                "atr_pct": round(float(v["atr_pct"]), 3)
                if isinstance(v.get("atr_pct"), (int, float))
                else None,
                "poi": [v.get("poi_low"), v.get("poi_high")],
                "harga_keputusan": v.get("harga_keputusan"),
                "waktu": v.get("ts"),
            }
        )
    entries.reverse()  # terbaru di depan

    aktif = []
    for it in items:
        if str(it.get("status")) in ("still_open", "open", "pending"):
            aktif.append(
                {
                    "signal_id": it.get("signal_id"),
                    "pair": it.get("pair"),
                    "arah": it.get("direction"),
                    "zona_entry": it.get("entry_zone"),
                    "sl": it.get("sl"),
                    "tp1": it.get("tp1"),
                    "tp2": it.get("tp2"),
                    "status": it.get("status"),
                    "r": it.get("pnl_pct"),
                    "sejak": it.get("date_added"),
                }
            )

    # Dimensi aturan: mana yang paling sering menggagalkan setup (dari seluruh jendela).
    dimensi: dict[str, dict[str, Any]] = {}
    for v in verdicts:
        for r in v.get("rules") or []:
            nama = _aturan_ke_nama(str(r.get("rule")))
            d = dimensi.setdefault(nama, {"dimensi": nama, "lolos": 0, "total": 0})
            d["total"] += 1
            if r.get("ok"):
                d["lolos"] += 1
    dimensi_list = sorted(
        (
            {**d, "persen": round(100 * d["lolos"] / d["total"]) if d["total"] else None}
            for d in dimensi.values()
        ),
        key=lambda x: (x["persen"] if x["persen"] is not None else 101),
    )

    # Penghitung veto — adopsi pola "skip-reason counter" poly-paper favorite
    # (outside_price_band 375x, loss_budget 335x, dst.): alasan apa yang paling
    # sering MENOLAK setup, dihitung hanya dari verdict yang ditolak. Melengkapi
    # `dimensi` di atas (pass-rate semua verdict) supaya panel bisa menjawab
    # "kandidat banyak tapi buka nol — kenapa?" dengan hitungan, bukan tebakan.
    veto: dict[str, int] = {}
    for v in verdicts:
        if v.get("allowed"):
            continue
        for nama in {
            _aturan_ke_nama(str(r.get("rule")))
            for r in (v.get("rules") or [])
            if not r.get("ok")
        }:
            veto[nama] = veto.get(nama, 0) + 1

    metadata = watch.get("meta") or {}
    return {
        "tersedia": bool(verdicts) or bool(items),
        "alasan": None if (verdicts or items) else "verdicts.jsonl & crypto-watchlist.json kosong",
        "entries": entries,
        "aktif": aktif,
        "strategi": STRATEGI_PASAR["crypto"],
        "dimensi": dimensi_list,
        "jumlah_verdict": len(verdicts),
        "jumlah_lolos": sum(1 for v in verdicts if v.get("allowed")),
        "jumlah_ditolak": len(verdicts) - sum(1 for v in verdicts if v.get("allowed")),
        "veto": sorted(
            ({"alasan": k, "n": n} for k, n in veto.items()), key=lambda x: (-x["n"], x["alasan"])
        ),
        "sumber": "state/verdicts.jsonl (gate crypto lokal) + state/crypto-watchlist.json",
        "suplai": {
            "mesin": "cron Hermes Tencent `crypto-5agent-pipeline-653` (SMC 5-agen)",
            "catatan": (
                "Tencent = sumber sinyal; War Room = mesin bukti. "
                "Server mati → sinyal berhenti bertambah."
            ),
            "reset_strategi": metadata.get("reset_date"),
            "eval_terakhir": metadata.get("last_eval"),
        },
    }


# ---------------------------------------------------------------------------
# IDX — sinyal & entry setup (ledger mesin, hanya baca)
# ---------------------------------------------------------------------------

def _umur_hari_terbuka(status: Any, created_at: Any) -> float | None:
    """Umur (hari) sinyal yang masih terbuka — supaya "masih jalan" bisa dibedakan
    dari "nyangkut karena mesinnya sudah beku". Gagal parse → None (jangan mengarang)."""
    if str(status) not in ("CREATED", "OPEN") or not created_at:
        return None
    try:
        t = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    return round((datetime.now(UTC) - t).total_seconds() / 86400, 1)


def ringkas_idx_sinyal(state_dir: Path) -> dict[str, Any]:
    """Sinyal IDX terbaru dari ledger mesin (sumber sama dengan idx_akurasi)."""
    import sqlite3

    db = state_dir / "idx_ledger.db"
    if not db.is_file():
        return {
            "tersedia": False,
            "alasan": "state/idx_ledger.db belum ada (impor 6 Okt)",
            "entries": [],
            "strategi": STRATEGI_PASAR["idx"],
        }
    entries: list[dict[str, Any]] = []
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "select event_id,ticker,setup,direction,entry_low,entry_high,sl,tp1,tp2,"
            "status,result,filled_at,closed_at,net_r,note,created_at "
            "from signals order by coalesce(closed_at, created_at) desc limit 24"
        ).fetchall()
        con.close()
    except Exception as exc:  # noqa: BLE001 — satu panel jangan mati karena DB rusak
        return {
            "tersedia": False,
            "alasan": f"{type(exc).__name__}: {exc}",
            "entries": [],
            "strategi": STRATEGI_PASAR["idx"],
        }

    for r in rows:
        entries.append(
            {
                "ticker": r["ticker"],
                "setup": r["setup"],
                "arah": r["direction"],
                "status": r["status"],
                "hasil": r["result"],
                "entry": (
                    r["entry_low"]
                    if r["entry_low"] == r["entry_high"]
                    else f"{r['entry_low']}–{r['entry_high']}"
                ),
                "sl": r["sl"],
                "tp1": r["tp1"],
                "tp2": r["tp2"],
                "r_r": _r_r(r["entry_low"], r["sl"], r["tp1"]),
                "net_r": r["net_r"],
                "dibuat": r["created_at"],
                "ditutup": r["closed_at"],
                "umur_hari": _umur_hari_terbuka(r["status"], r["created_at"]),
                "note": r["note"],
            }
        )
    # Ringkasan SELURUH ledger (bukan hanya 24 yang ditampilkan): berapa sinyal terbuka,
    # berapa yang sudah menggantung ≥10 hari. Mesin IDX beku → angka ini tidak akan turun
    # sendiri; menampilkannya adalah cara jujur memberi tahu bahwa posisi itu mati suri.
    ringkas_terbuka: dict[str, Any] = {"n": 0, "lama": 0, "tertua_hari": None}
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        baris = con.execute(
            "select created_at from signals where status in ('CREATED','OPEN')"
        ).fetchall()
        con.close()
        umur = [
            u for u in (_umur_hari_terbuka("CREATED", b[0]) for b in baris) if u is not None
        ]
        ringkas_terbuka = {
            "n": len(umur),
            "lama": sum(1 for u in umur if u >= 10),
            "tertua_hari": round(max(umur), 1) if umur else None,
        }
    except Exception:  # noqa: BLE001 — ringkasan opsional; daftar tetap tampil
        logging.getLogger(__name__).debug("operasi dilewati", exc_info=True)
    terbuka_lama = ringkas_terbuka["lama"]
    return {
        "tersedia": bool(entries),
        "alasan": None if entries else "ledger IDX kosong",
        "entries": entries,
        "terbuka": ringkas_terbuka["n"],
        "terbuka_lama": terbuka_lama,
        "tertua_hari": ringkas_terbuka["tertua_hari"],
        "catatan_terbuka": (
            f"{terbuka_lama} sinyal terbuka ≥10 hari dan TIDAK akan ditutup: mesin IDX "
            "di Tencent beku (cron di-pause). Hasilnya tidak bisa direkonstruksi tanpa "
            "menghidupkan mesinnya kembali — jangan dianggap posisi berjalan."
        )
        if terbuka_lama
        else None,
        "strategi": STRATEGI_PASAR["idx"],
        "sumber": "state/idx_ledger.db (tencent:idx616_signal_ledger.db)",
        "suplai": {
            "mesin": "cron IDX Tencent (idx616) — saat ini DI-PAUSE (epoch beku 6 Okt)",
            "catatan": "Ledger beku: tidak bertambah sampai mesin Tencent hidup lagi. Bukti tetap utuh.",
        },
    }


# ---------------------------------------------------------------------------
# FOREX — sinyal & entry setup (jurnal Tencent yang diimpor)
# ---------------------------------------------------------------------------

def ringkas_forex_sinyal(state_dir: Path) -> dict[str, Any]:
    """Sinyal forex dari jurnal Tencent: XAUUSD (SMC 4-agen) + multi-pair (NAS100/EURUSD)."""
    j = _baca_json(state_dir / "forex_journal.json")
    if not isinstance(j, dict):
        return {
            "tersedia": False,
            "alasan": "state/forex_journal.json belum ada (impor 6 Okt)",
            "entries": [],
            "strategi": STRATEGI_PASAR["forex"],
        }

    entries: list[dict[str, Any]] = []

    for t in (j.get("xauusd") or {}).get("trades") or []:
        entries.append(
            {
                "pair": "XAUUSD",
                "arah": t.get("side"),
                "entry": t.get("entry"),
                "sl": t.get("sl"),
                "tp1": t.get("tp1"),
                "tp2": t.get("tp2"),
                "r_r": _r_r(t.get("entry"), t.get("sl"), t.get("tp1")),
                "status": t.get("status"),
                "hasil": t.get("outcome"),
                "r": t.get("r_multiple"),
                "zona": None,
                "tf": None,
                "konfluensi": None,
                "waktu": t.get("date_wib"),
                "alasan": t.get("bias"),
                "strategi": "SMC-XAUUSD",
            }
        )

    jumlah_per = Counter()
    for t in (j.get("multipair") or []):
        mr = t.get("market_result") or {}
        r = mr.get("r") if isinstance(mr, dict) else None
        pair = str(t.get("pair") or "?")
        jumlah_per[pair] += 1
        entries.append(
            {
                "pair": pair,
                "arah": t.get("side"),
                "entry": t.get("entry"),
                "sl": t.get("sl"),
                "tp1": t.get("tp1"),
                "tp2": t.get("tp2"),
                "r_r": _r_r(t.get("entry"), t.get("sl"), t.get("tp1")),
                "status": t.get("status"),
                "hasil": t.get("outcome"),
                "r": r,
                "zona": t.get("zone_kind"),
                "tf": t.get("zone_tf"),
                "konfluensi": t.get("confluence"),
                "waktu": t.get("date_wib"),
                "alasan": (
                    (t.get("notes") or [None])[0]
                    if isinstance(t.get("notes"), list)
                    else t.get("notes")
                ),
                "strategi": "SMC-FVG/OB-1H",
            }
        )
    entries.sort(key=lambda e: str(e.get("waktu") or ""), reverse=True)

    # Seri R untuk pakem: HANYA trade yang benar-benar terisi & tuntas.
    seri: list[dict[str, Any]] = []
    for t in (j.get("xauusd") or {}).get("trades") or []:
        if str(t.get("outcome") or "") == "NO FILL":
            continue
        if t.get("r_multiple") is None:
            continue
        seri.append(
            {
                "r": t.get("r_multiple"),
                "closed_at": t.get("date_wib"),
                "status": str(t.get("outcome") or "").lower(),
                "pair": "XAUUSD",
            }
        )
    for t in (j.get("multipair") or []):
        mr = t.get("market_result") or {}
        if not isinstance(mr, dict) or mr.get("r") is None:
            continue
        seri.append(
            {
                "r": mr.get("r"),
                "closed_at": t.get("date_wib"),
                "status": str(t.get("outcome") or "").lower(),
                "pair": t.get("pair"),
            }
        )

    impor = j.get("impor") or {}
    per_setup: dict[str, dict[str, Any]] = {}
    for kunci, label in (
        ("XAUUSD", "XAUUSD (SMC 4-agen)"),
        ("NAS100", "NAS100 (FVG/OB 1H)"),
        ("EURUSD", "EURUSD (FVG/OB 1H)"),
    ):
        rows = [s for s in seri if s.get("pair") == kunci]
        if rows:
            per_setup[label] = _baris_akurasi(
                rows, nama=label, kunci_tanggal="closed_at", biaya_tercatat=None
            )

    # Lapisan per-PAIR: ringkas tiap pair (terakhir, berapa sinyal, hasil) supaya bagian forex
    # tidak terasa "satu blok kosong" — XAUUSD dan NAS100/EURUSD punya watak berbeda.
    per_pair: dict[str, dict[str, Any]] = {}
    for e in entries:
        pair = str(e.get("pair") or "?")
        d = per_pair.setdefault(
            pair,
            {
                "pair": pair,
                "strategi": e.get("strategi"),
                "n_sinyal": 0,
                "n_tuntas": 0,
                "menang": 0,
                "total_r": 0.0,
                "terakhir": None,
                "status_terakhir": None,
                "arah_terakhir": None,
            },
        )
        d["n_sinyal"] += 1
        if d["terakhir"] is None or str(e.get("waktu") or "") > str(d["terakhir"]):
            d["terakhir"] = e.get("waktu")
            d["status_terakhir"] = e.get("hasil") or e.get("status")
            d["arah_terakhir"] = e.get("arah")
        if e.get("r") is not None:
            d["n_tuntas"] += 1
            d["total_r"] = round(d["total_r"] + float(e["r"]), 4)
            if float(e["r"]) > 0:
                d["menang"] += 1
    for d in per_pair.values():
        d["winrate_pct"] = round(100 * d["menang"] / d["n_tuntas"], 1) if d["n_tuntas"] else None
        d["mean_r"] = round(d["total_r"] / d["n_tuntas"], 4) if d["n_tuntas"] else None

    return {
        "tersedia": True,
        "alasan": None,
        "entries": entries,
        "per_pair": per_pair,
        "per_setup": per_setup,
        "seri_pakem": _baris_akurasi(seri, nama="Forex gabungan", biaya_tercatat=None) if seri else None,
        "per_hari": _per_hari(seri),
        "strategi": STRATEGI_PASAR["forex"],
        "sumber": impor.get("sumber") or "state/forex_journal.json",
        "impor": {
            "sha256": impor.get("sha256"),
            "diimpor": impor.get("diimpor"),
            "catatan": impor.get("catatan"),
        },
        "suplai": {
            "mesin": "cron Hermes Tencent (xauusd-smc-daily-signal, multi-pair-signal)",
            "catatan": (
                "Tencent = sumber sinyal; War Room = mesin bukti. "
                "Server mati → sinyal berhenti bertambah."
            ),
        },
        "catatan": [
            "NO FILL tidak dihitung sebagai trade (order tak pernah terisi) — dilaporkan terpisah.",
            "Jurnal berisi trade yang diambil; cron yang menolak tidak meninggalkan "
            "baris trade (lihat scan_log).",
            "BIAYA BELUM TERCATAT: spread/komisi broker tidak ada di jurnal, jadi semua "
            "angka di sini BRUTO. Jangan dibandingkan langsung dengan pasar yang net "
            "(crypto: cost_bps terukur; IDX: grader v3 sudah termasuk biaya).",
        ],
        # Flag biaya dipakai UI agar PnL bruto tidak disandingkan dengan PnL net tanpa penanda.
        "biaya_tercatat": False,
        "biaya_label": "NOT COST-ADJUSTED",
    }


# ---------------------------------------------------------------------------
# AKURASI + PNL per market (crypto, forex, gmgn/LP, polymarket)
# ---------------------------------------------------------------------------

def _akurasi_crypto(state_dir: Path) -> dict[str, Any]:
    rows = _baca_jsonl(state_dir / "crypto_equity.jsonl")
    seri = [
        {"r": r.get("r"), "closed_at": r.get("closed_at"), "status": r.get("status"), "pair": r.get("pair")}
        for r in rows
        if r.get("r") is not None and str(r.get("status") or "") not in ("expired",)
    ]
    total = _baris_akurasi(seri, nama="SMC multi-timeframe", biaya_tercatat=None) if seri else None
    return {
        "tersedia": bool(seri),
        "alasan": None if seri else "crypto_equity.jsonl kosong/belum ada trade tuntas",
        "seri": total,
        "per_setup": {"SMC multi-timeframe": total} if total else {},
        "per_hari": _per_hari(seri),
        "strategi": STRATEGI_PASAR["crypto"],
        "sumber": "state/crypto_equity.jsonl",
        "suplai": "ledger lokal dari watchlist-sync + paper",
        "catatan": [
            "Skor gate crypto = aturan lolos, BUKAN edge terbukti.",
            "Baris 'expired' (order tak pernah terisi) tidak dihitung sebagai trade.",
        ],
    }


def _akurasi_forex(state_dir: Path) -> dict[str, Any]:
    fs = ringkas_forex_sinyal(state_dir)
    if not fs.get("tersedia"):
        return {"tersedia": False, "alasan": fs.get("alasan"), "strategi": STRATEGI_PASAR["forex"]}
    per_setup = dict(fs.get("per_setup") or {})
    if fs.get("seri_pakem"):
        per_setup["Forex gabungan"] = fs["seri_pakem"]
    return {
        "tersedia": True,
        "alasan": None,
        "seri": fs.get("seri_pakem"),
        "per_setup": per_setup,
        "per_hari": fs.get("per_hari") or [],
        "strategi": STRATEGI_PASAR["forex"],
        "sumber": fs.get("sumber"),
        "impor": fs.get("impor"),
        "catatan": fs.get("catatan"),
    }


def _akurasi_gmgn(state_dir: Path) -> dict[str, Any]:
    rows = [r for r in _baca_jsonl(state_dir / "lp_ledger.jsonl") if r.get("status") == "dinilai"]
    n = len(rows)
    menang = sum(1 for r in rows if isinstance(r.get("pnl_usd"), (int, float)) and r["pnl_usd"] > 0)
    total_pnl = round(sum(float(r.get("pnl_usd") or 0) for r in rows), 4)
    pakem = _pakem_hitung(n, menang)
    menang_pct = round(100 * menang / n, 2) if n else None
    return {
        "tersedia": bool(rows),
        "alasan": None if rows else "lp_ledger.jsonl belum ada posisi dinilai",
        "per_setup": {
            "LP Terukur (mark lokal)": {
                "nama": "LP Terukur (mark lokal)",
                "n": n,
                "menang": menang,
                "winrate_pct": menang_pct,
                "total_pnl_usd": total_pnl,
                "total_r": None,
                "mean_r": None,
                **pakem,
            }
        } if rows else {},
        "strategi": STRATEGI_PASAR["gmgn"],
        "sumber": "state/lp_ledger.jsonl",
        "catatan": [
            "R tidak tersedia untuk LP — hasil dinyatakan dalam P&L %/USD (IL + fee), bukan R.",
            "Mark lokal memakai harga masuk+sekarang; rekonsiliasi on-chain belum ada.",
        ],
    }


def _akurasi_polymarket(state_dir: Path) -> dict[str, Any]:
    arms = {
        "A momentum": "/var/lib/poly-paper/execution-paper-shadow-summary.json",
        "B kandidat": "/var/lib/poly-paper-candidate/execution-paper-shadow-summary.json",
        "C fade": "/var/lib/poly-paper-fade/execution-paper-shadow-summary.json",
        "D favorit": "/var/lib/poly-paper-favorite/execution-paper-shadow-summary.json",
    }
    per_setup: dict[str, dict[str, Any]] = {}
    for nama, p in arms.items():
        d = _baca_json(Path(p))
        if not isinstance(d, dict):
            continue
        n = int(d.get("entries") or 0)
        menang = int(d.get("wins") or 0)
        kalah = int(d.get("losses") or 0)
        pakem = _pakem_hitung(n, menang)
        # BE-WR (win-rate impas) diturunkan dari HARGA ENTRY yang sudah ada di shadow
        # summary — bukan ambang baru. Di pasar biner adil, impas ≈ harga beli: beli di
        # 0,82 → hadiah menang +0,22× stake, kalah −1,00× → butuh WR > 82% hanya utk balik
        # modal. Dipakai untuk membandingkan "menang banyak tapi rugi" (arm B) apa adanya.
        lo = (d.get("strategy") or {}).get("entryLo") if isinstance(d.get("strategy"), dict) else None
        hi = (d.get("strategy") or {}).get("entryHi") if isinstance(d.get("strategy"), dict) else None
        be_wr_pct = None
        entry_mid = None
        if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
            entry_mid = round((float(lo) + float(hi)) / 2, 4)
            if 0 < entry_mid < 1:
                be_wr_pct = round(100 * entry_mid, 2)
        per_setup[nama] = {
            "nama": nama,
            "n": n,
            "menang": menang,
            "kalah": kalah,
            "winrate_pct": round(100 * menang / n, 2) if n else None,
            "pnl_usd": round(float(d.get("pnl") or 0), 4),
            "saldo_usd": d.get("balance"),
            "skips": d.get("skips") if isinstance(d.get("skips"), dict) else None,
            "aturan": (d.get("strategy") or {}).get("sideMode")
            if isinstance(d.get("strategy"), dict)
            else None,
            "band": [lo, hi],
            "entry_mid": entry_mid,
            "be_wr_pct": be_wr_pct,
            # Lolos = win-rate NYATA berada di ATAS ambang impas (bukan cuma positif).
            "lolos_be": (
                round(100 * menang / n, 2) > be_wr_pct
                if (n and be_wr_pct is not None)
                else None
            ),
            **pakem,
        }
    total = round(sum(v.get("pnl_usd") or 0 for v in per_setup.values()), 4) if per_setup else None
    return {
        "tersedia": bool(per_setup),
        "alasan": None if per_setup else "shadow summary Polymarket tidak terbaca",
        "per_setup": per_setup,
        "total_pnl_usd": total,
        "strategi": STRATEGI_PASAR["polymarket"],
        "sumber": "/var/lib/poly-paper*/execution-paper-shadow-summary.json",
        "catatan": [
            "Win-rate = entri menang/kalah dari mesin paper; bukan R dan belum lewat split beku.",
            "Fees & slippage sudah dibebankan sesuai 'feeMode: receipt' milik poly-pilot.",
            "BE-WR = win-rate impas, diturunkan dari titik-tengah band harga entry (pasar biner:"
            " impas ≈ harga beli). Win-rate di bawah BE-WR = rugi walau menang banyak.",
        ],
    }


def ringkas_akurasi_pasar(state_dir: Path) -> dict[str, Any]:
    """Akurasi + PnL untuk SEMUA market (IDX punya modul sendiri: ``idx_akurasi``)."""
    pasar: dict[str, Any] = {}
    for nama, fn in (
        ("crypto", _akurasi_crypto),
        ("forex", _akurasi_forex),
        ("gmgn", _akurasi_gmgn),
        ("polymarket", _akurasi_polymarket),
    ):
        try:
            pasar[nama] = fn(state_dir)
        except Exception as exc:  # noqa: BLE001 — satu pasar jangan menjatuhkan yang lain
            pasar[nama] = {"tersedia": False, "alasan": f"{type(exc).__name__}: {exc}"}
    # Bukti per pasar merangkum metrik lengkap (trade, PnL, win rate, drawdown, biaya, periode, denominator).
    # Nilai yang tidak diketahui diisi None (bukan 0) agar tidak menyesatkan.
    for nama, blok in pasar.items():
        blok["bukti"] = _bukti_pasar(nama, blok)
    return {
        "tersedia": any(v.get("tersedia") for v in pasar.values()),
        "pasar": pasar,
        "standar": (
            "pakem.py — n efektif per hari; INSUFFICIENT <10, DIRECTIONAL <30, "
            "PRELIMINARY <100, TUNING ≥100"
        ),
        "dibuat": datetime.now(UTC).isoformat(),
    }


# Biaya per pasar: True = sudah termasuk, False = BRUTO (belum termasuk), None = tidak diketahui.
# Ditulis di satu tempat supaya halaman bukti dan halaman pasar tidak bisa berbeda pendapat.
BIAYA_PASAR: dict[str, tuple[bool | None, str]] = {
    "crypto": (True, "cost_bps terukur per trade (friksi OKX)"),
    "idx": (True, "grader v3 — net_r sudah termasuk biaya"),
    "forex": (False, "spread/komisi broker belum ada di jurnal"),
    "gmgn": (True, "fee LP + IL dihitung di mark lokal"),
    "polymarket": (True, "fees dibebankan sesuai feeMode poly-pilot"),
}


def _bukti_pasar(nama: str, blok: dict[str, Any]) -> dict[str, Any]:
    """Tujuh jawaban bukti untuk satu pasar — angka apa adanya, None bila tidak diketahui."""
    biaya, biaya_ket = BIAYA_PASAR.get(nama, (None, "status biaya tidak diketahui"))

    # Denominasi: pakai seri total bila ada (per_setup "SMC..." / "B forex..." / dst.),
    # kalau tidak jumlahkan per_setup yang tersedia. N = trade TUNTAS (bukan sinyal).
    seri = blok.get("seri") or {}
    per_setup = blok.get("per_setup") or {}
    if not seri and per_setup:
        nilai = [v for v in per_setup.values() if isinstance(v, dict)]
        n = sum(int(v.get("n") or 0) for v in nilai)
        if n:
            seri = {
                "n": n,
                "closed_trades": n,
                "n_hari": max((int(v.get("n_hari") or 0) for v in nilai), default=0) or None,
                "winrate_pct": None,
                "mean_r": None,
                "total_r": None,
                "tingkat": None,
            }

    # Periode: rentang tanggal trade tuntas (dari per_hari bila ada) — bukan tanggal hari ini.
    hari = [h.get("tanggal") for h in (blok.get("per_hari") or []) if h.get("tanggal")]
    periode = {"dari": min(hari) if hari else None, "sampai": max(hari) if hari else None}

    ringkas = seri.get("ringkas") if isinstance(seri.get("ringkas"), dict) else {}
    win_rate = seri.get("winrate_pct") if seri.get("winrate_pct") is not None else ringkas.get("winrate_pct")
    mean_r = seri.get("mean_r") if seri.get("mean_r") is not None else ringkas.get("mean_r")
    total_r = seri.get("total_r") if seri.get("total_r") is not None else ringkas.get("total_r")

    closed_trades = seri.get("closed_trades")
    if closed_trades is None:
        closed_trades = seri.get("n")

    return {
        "closed_trades": closed_trades,
        "win_rate_pct": win_rate,
        "mean_r": mean_r,
        "total_r": total_r,
        "pnl_usd": seri.get("total_pnl_usd") or seri.get("pnl_usd") or blok.get("total_pnl"),
        "max_drawdown_r": (
            ringkas.get("max_drawdown_r")
            if ringkas.get("max_drawdown_r") is not None
            else seri.get("max_drawdown_r")
        ),
        "biaya_tercatat": biaya,
        "biaya_keterangan": biaya_ket,
        "periode": periode,
        "denominator": (
            "trade TUNTAS di ledger (baris 'expired'/tanpa hasil tidak dihitung)"
        ),
        "n_hari": seri.get("n_hari"),
        "tingkat": seri.get("tingkat"),
        "sumber": blok.get("sumber"),
    }
