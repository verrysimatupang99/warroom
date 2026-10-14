"""Dompet paper per market — Rp 10.000.000 saldo awal, angka apa adanya (6 Okt 2026).

KEPUTUSAN YANG DIKODEKAN DI SINI
--------------------------------
1. **Satu ukuran untuk semua market: Rp 10 juta.** Nilai R tidak bisa dibandingkan
   antar-market (1R crypto ≠ 1R IDX), jadi pertanyaan "market mana yang paling
   menghasilkan" tidak terjawab oleh R. Dengan saldo yang sama + risiko % yang sama,
   saldo akhir menjadi ukuran yang adil — dengan syarat satuan kursnya jelas.
2. **Kurs ditulis, bukan diasumsikan.** Saldo awal Rp 10 juta dikonversi ke mata uang
   venue memakai kurs yang DISEBUT di output (`kurs_usd_idr`). Untuk crypto & forex
   venue-nya USD; kalau kurs tidak tersedia, saldo tidak dikarang — `tersedia=False`.
3. **Tidak ada compounding diam-diam.** Setiap trade mempertaruhkan `risk_pct` ×
   **saldo awal** (bukan saldo berjalan). Compounding dari sampel 5–10 trade adalah
   cara memperbesar derau, bukan bukti.
4. **Saldo tidak pernah ditulis ulang.** Dihitung ulang dari ledger tiap kali — satu
   sumber kebenaran (pelajaran dari Tencent: dua sumber = drift).
5. **Biaya disebut.** Ledger crypto punya `cost_bps` terukur; market lain belum, dan
   itu dinyatakan sebagai catatan, bukan diisi nol seolah gratis.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

__all__ = [
    "WALLET_IDR",
    "kurs_usd_idr",
    "summarize_wallet",
    "summarize_all_wallets",
]

WALLET_IDR = 10_000_000.0
_KURS_CACHE = "kurs_usd_idr.json"
_KURS_TTL_JAM = 24
_DEFAULT_RISK_PCT = 1.0

# Rupiah per unit mata uang venue. KRW untuk IDX (harga saham dalam rupiah, jadi 1:1).
_PPN = {
    "crypto": 1.0,       # USD
    "forex": 1.0,        # USD (XAUUSD/NAS100/EURUSD dinyatakan dalam USD)
    "gmgn": 1.0,         # USD (LP stablecoin)
    "polymarket": 1.0,   # USDC
    "idx": 1.0,          # IDR (harga saham sudah rupiah)
}


def kurs_usd_idr(state_dir: Path) -> tuple[float | None, str]:
    """Kurs USD→IDR hidup dengan cache 24 jam. Gagal → (None, alasan); jangan mengarang."""
    cache = state_dir / _KURS_CACHE
    try:
        d = json.loads(cache.read_text(encoding="utf-8"))
        ts = dt.datetime.fromisoformat(str(d["diambil"]))
        if (dt.datetime.now(dt.UTC) - ts) < dt.timedelta(hours=_KURS_TTL_JAM):
            return float(d["kurs"]), str(d.get("sumber", "cache"))
    except (OSError, KeyError, ValueError, json.JSONDecodeError):
        pass

    try:
        import urllib.request

        req = urllib.request.Request(
            "https://api.frankfurter.app/latest?from=USD&to=IDR",
            headers={"User-Agent": "war-room/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
        kurs = float((data.get("rates") or {})["IDR"])
        cache.write_text(
            json.dumps(
                {"kurs": kurs, "diambil": dt.datetime.now(dt.UTC).isoformat(), "sumber": "frankfurter.app"}
            ),
            encoding="utf-8",
        )
        return kurs, "frankfurter.app"
    except Exception as exc:  # noqa: BLE001 — kurs gagal bukan alasan mengarang saldo
        # Cache basi masih jauh lebih jujur daripada angka karangan — tapi ditandai.
        try:
            d = json.loads(cache.read_text(encoding="utf-8"))
            return float(d["kurs"]), f"cache-basi ({d.get('diambil', '?')[:16]})"
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            return None, f"tidak tersedia: {type(exc).__name__}"


def _ledger(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict):
            out.append(d)
    out.sort(key=lambda r: (str(r.get("closed_at") or ""), str(r.get("signal_id") or "")))
    return out


def summarize_wallet(
    state_dir: Path,
    *,
    market: str,
    kurs: float | None = None,
    saldo_awal_idr: float = WALLET_IDR,
    risk_pct: float = _DEFAULT_RISK_PCT,
    sumber: str,
    catatan: list[str] | None = None,
) -> dict[str, Any]:
    """Hitung saldo berjalan dari ledger market. Menolak menghitung bila kurs tak ada."""
    baris = _ledger(state_dir / _nama_ledger(market))
    if not baris:
        return {
            "market": market,
            "tersedia": False,
            "alasan": f"ledger {_nama_ledger(market)} kosong/belum ada",
            "saldo_awal_idr": saldo_awal_idr,
            "sumber": sumber,
        }
    if kurs is None:
        return {
            "market": market,
            "tersedia": False,
            "alasan": "kurs USD→IDR tidak tersedia — saldo tidak dikarang",
            "saldo_awal_idr": saldo_awal_idr,
            "sumber": sumber,
        }

    ppn = _PPN.get(market, 1.0)
    unit_saldo_awal = saldo_awal_idr / kurs / ppn
    risiko_per_trade = unit_saldo_awal * (risk_pct / 100.0)

    poin: list[dict[str, Any]] = [
        {"i": 0, "label": "start", "pnl_usd": 0.0, "saldo_usd": round(unit_saldo_awal, 2)}
    ]
    pnl_kum = 0.0
    wins = losses = 0
    biaya_tercatat = False
    for i, t in enumerate(baris, 1):
        r = t.get("r")
        if r is None:
            continue
        pnl = float(r) * risiko_per_trade
        if t.get("cost_bps") is not None:
            biaya_tercatat = True
        pnl_kum += pnl
        if pnl > 0:
            wins += 1
        elif pnl < 0:
            losses += 1
        poin.append(
            {
                "i": i,
                "pair": t.get("pair"),
                "status": t.get("status"),
                "r": round(float(r), 3),
                "pnl_usd": round(pnl, 2),
                "saldo_usd": round(unit_saldo_awal + pnl_kum, 2),
                "closed_at": t.get("closed_at"),
                "sumber": t.get("source"),
            }
        )

    saldo_akhir_usd = unit_saldo_awal + pnl_kum
    return {
        "market": market,
        "tersedia": True,
        "saldo_awal_idr": saldo_awal_idr,
        "saldo_awal_unit": round(unit_saldo_awal, 2),
        "mata_uang": "IDR" if market == "idx" else "USD",
        "kurs_usd_idr": kurs,
        "risk_pct": risk_pct,
        "risiko_per_trade_usd": round(risiko_per_trade, 2),
        "saldo_akhir_usd": round(saldo_akhir_usd, 2),
        "pnl_usd": round(pnl_kum, 2),
        "pnl_idr": round(pnl_kum * kurs * ppn, 0),
        "pnl_pct": round(100 * pnl_kum / unit_saldo_awal, 3),
        "trade": len([p for p in poin if p.get("r") is not None]),
        "wins": wins,
        "losses": losses,
        "titik": poin,
        "biaya_tercatat": biaya_tercatat,
        "sumber": sumber,
        "catatan": [
            "Risiko per trade = risk_pct × SALDO AWAL (tanpa compounding — sampel kecil, "
            "compounding hanya memperbesar derau).",
            "Saldo dihitung ulang dari ledger setiap kali; tidak pernah ditulis balik ke ledger.",
            *(
                []
                if biaya_tercatat
                else ["Biaya (fee/slippage) belum tercatat di ledger market ini — PnL masih bruto."]
            ),
            *(catatan or []),
        ],
    }


def _nama_ledger(market: str) -> str:
    return {
        "crypto": "crypto_equity.jsonl",
        "idx": "idx_equity.jsonl",
        "forex": "forex_equity.jsonl",
        "gmgn": "gmgn_equity.jsonl",
        "polymarket": "polymarket_equity.jsonl",
    }.get(market, f"{market}_equity.jsonl")


def _dompet_forex(state_dir: Path, kurs: float | None) -> dict[str, Any]:
    """Forex: ledger R adalah trade MetaTrader (bukan equity.jsonl) — dibaca dari jurnal."""
    j = state_dir / "forex_journal.json"
    if not j.is_file():
        return {"market": "forex", "tersedia": False, "alasan": "forex_journal.json belum ada"}
    try:
        d = json.loads(j.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"market": "forex", "tersedia": False, "alasan": "forex_journal.json rusak"}
    baris: list[dict[str, Any]] = []
    for t in (d.get("xauusd") or {}).get("trades") or []:
        if str(t.get("outcome")) == "NO FILL" or t.get("r_multiple") is None:
            continue
        baris.append(
            {
                "signal_id": t.get("id"),
                "pair": "XAUUSD",
                "r": t.get("r_multiple"),
                "closed_at": t.get("date_wib"),
                "status": str(t.get("outcome") or "").lower(),
                "source": "jurnal-xauusd",
            }
        )
    for t in d.get("multipair") or []:
        mr = t.get("market_result") or {}
        if not isinstance(mr, dict) or mr.get("r") is None:
            continue
        baris.append(
            {
                "signal_id": f"{t.get('pair')}-{t.get('date_wib')}",
                "pair": t.get("pair"),
                "r": mr.get("r"),
                "closed_at": t.get("date_wib"),
                "status": str(t.get("outcome") or "").lower(),
                "source": "jurnal-multipair",
            }
        )
    if not baris:
        return {"market": "forex", "tersedia": False, "alasan": "belum ada trade tuntas di jurnal"}
    if kurs is None:
        return {"market": "forex", "tersedia": False, "alasan": "kurs USD→IDR tidak tersedia"}
    baris.sort(key=lambda r: str(r.get("closed_at") or ""))
    unit = WALLET_IDR / kurs
    risiko = unit * (_DEFAULT_RISK_PCT / 100.0)
    kum = 0.0
    titik = [{"i": 0, "label": "start", "pnl_usd": 0.0, "saldo_usd": round(unit, 2)}]
    for i, b in enumerate(baris, 1):
        pnl = float(b["r"]) * risiko
        kum += pnl
        titik.append({**b, "i": i, "pnl_usd": round(pnl, 2), "saldo_usd": round(unit + kum, 2)})
    return {
        "market": "forex",
        "tersedia": True,
        "saldo_awal_idr": WALLET_IDR,
        "saldo_awal_unit": round(unit, 2),
        "mata_uang": "USD",
        "kurs_usd_idr": kurs,
        "risk_pct": _DEFAULT_RISK_PCT,
        "risiko_per_trade_usd": round(risiko, 2),
        "saldo_akhir_usd": round(unit + kum, 2),
        "pnl_usd": round(kum, 2),
        "pnl_idr": round(kum * kurs, 0),
        "pnl_pct": round(100 * kum / unit, 3),
        "trade": len(baris),
        "titik": titik,
        "biaya_tercatat": False,
        "sumber": "state/forex_journal.json (XAUUSD + multi-pair)",
        "catatan": [
            "Biaya spread/komisi broker belum tercatat — PnL masih bruto.",
            "Jurnal berisi trade yang benar-benar diambil; NO FILL tidak dihitung.",
            "Risiko per trade = 1% × saldo awal (tanpa compounding).",
        ],
    }


def summarize_all_wallets(state_dir: Path) -> dict[str, Any]:
    """Dompet Rp 10 juta untuk SEMUA market — satu kurs, satu aturan risiko."""
    kurs, asal_kurs = kurs_usd_idr(state_dir)
    keluaran: dict[str, Any] = {}
    for market, sumber in (
        ("crypto", "state/crypto_equity.jsonl (paper + watchlist-sync + rekonsiliasi)"),
        ("idx", "state/idx_equity.jsonl"),
        ("gmgn", "state/gmgn_equity.jsonl"),
        ("polymarket", "state/polymarket_equity.jsonl"),
    ):
        try:
            keluaran[market] = summarize_wallet(state_dir, market=market, kurs=kurs, sumber=sumber)
        except Exception as exc:  # noqa: BLE001 — satu market jangan menjatuhkan yang lain
            keluaran[market] = {"market": market, "tersedia": False, "alasan": f"{type(exc).__name__}: {exc}"}
    for nama, fn in (("forex", _dompet_forex), ("idx", _dompet_idx),
                     ("polymarket", _dompet_polymarket), ("gmgn", _dompet_gmgn)):
        try:
            keluaran[nama] = fn(state_dir, kurs)
        except Exception as exc:  # noqa: BLE001 — satu market jangan menjatuhkan yang lain
            keluaran[nama] = {"market": nama, "tersedia": False, "alasan": f"{type(exc).__name__}: {exc}"}
    return {
        "saldo_awal_idr": WALLET_IDR,
        "kurs_usd_idr": kurs,
        "kurs_sumber": asal_kurs,
        "pasar": keluaran,
        "aturan": (
            "Tiap market punya dompet paper Rp 10 juta sendiri; risiko default 1% saldo awal "
            "per trade; PnL dihitung ulang dari ledger (tidak ada angka yang ditulis balik)."
        ),
    }


def _dompet_idx(state_dir: Path, kurs: float | None) -> dict[str, Any]:
    """IDX: dompet rupiah dari ledger mesin (628 sinyal, net_r per baris).

    Harga saham sudah dalam rupiah → tidak perlu kurs. PnL per trade =
    `net_r` × (risk_pct × saldo awal), risiko dinyatakan dalam rupiah langsung.
    """
    import sqlite3

    db = state_dir / "idx_ledger.db"
    if not db.is_file():
        return {"market": "idx", "tersedia": False, "alasan": "idx_ledger.db belum ada"}
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = con.execute(
            "select event_id, ticker, setup, status, result, net_r, closed_at "
            "from signals where net_r is not null order by closed_at"
        ).fetchall()
        con.close()
    except Exception as exc:  # noqa: BLE001
        return {"market": "idx", "tersedia": False, "alasan": f"{type(exc).__name__}: {exc}"}
    if not rows:
        return {"market": "idx", "tersedia": False, "alasan": "belum ada baris net_r di ledger IDX"}

    risiko = WALLET_IDR * (_DEFAULT_RISK_PCT / 100.0)
    kum = 0.0
    titik: list[dict[str, Any]] = [{"i": 0, "label": "start", "pnl_idr": 0.0, "saldo_idr": WALLET_IDR}]
    for i, (event_id, ticker, setup, status, result, net_r, closed_at) in enumerate(rows, 1):
        pnl = float(net_r) * risiko
        kum += pnl
        titik.append(
            {
                "i": i,
                "signal_id": event_id,
                "pair": ticker,
                "setup": setup,
                "status": str(result or status or "").lower(),
                "r": round(float(net_r), 4),
                "pnl_idr": round(pnl, 0),
                "saldo_idr": round(WALLET_IDR + kum, 0),
                "closed_at": closed_at,
            }
        )
    # Pecahan per SETUP: pertanyaan sebenarnya bukan "IDX rugi berapa", melainkan
    # "setup mana yang menghasilkan dan mana yang menghabiskan dompet". Bukti 7 Okt:
    # ARA_HUNTER (198 trade) sendirian membuat dompet Rp 10 jt habis; BSJP positif.
    per_setup: dict[str, dict[str, Any]] = {}
    try:
        con2 = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        nama_setup = [r[0] for r in con2.execute(
            "select distinct setup from signals where net_r is not null"
        ).fetchall()]
        for nama in nama_setup:
            rs = [
                float(x[0])
                for x in con2.execute(
                    "select net_r from signals where net_r is not null and setup = ?", (nama,)
                ).fetchall()
            ]
            if not rs:
                continue
            kum_s = sum(rs) * risiko
            terburuk = min(rs)
            # Klasifikasi per setup (QA putaran 2): "pisahkan breach/gap loss" — supaya
            # pembaca tahu BERAPA BANYAK dan SEBERAPA DALAM pelanggaran 1R di setup itu,
            # bukan hanya "ada yang ekstrem". Hitungan ini juga yang membuat dompet bisa
            # negatif; tanpa ini saldo negatif tampak seperti kejadian tak terjelaskan.
            lewat = [r for r in rs if r < -1.05]
            per_setup[str(nama)] = {
                "setup": str(nama),
                "n": len(rs),
                "total_r": round(sum(rs), 2),
                "mean_r": round(sum(rs) / len(rs), 4),
                "min_r": round(terburuk, 2),
                "max_r": round(max(rs), 2),
                "lewat_1r": len(lewat),
                "lewat_1r_pct": round(100 * len(lewat) / len(rs), 1) if rs else 0.0,
                "rugi_ekstrem_5r": len([r for r in rs if r < -5]),
                # Risiko tak terbatas: satu trade rugi JAUH melebihi 1R (stop tak dihormati).
                # Temuan 7 Okt: ARA_HUNTER punya trade -13,84R — exit di open sesi berikutnya,
                # jadi gap bisa 14× risiko yang direncanakan. Dompet "1% per trade" pada setup
                # seperti ini MENYEMBUNYIKAN risiko nyata; karena itu flag ini wajib ikut terbit.
                "risiko_tak_terbatas": bool(terburuk <= -3.0),
                "pnl_idr": round(kum_s, 0),
                "saldo_idr": round(WALLET_IDR + kum_s, 0),
                "pnl_pct": round(100 * kum_s / WALLET_IDR, 2),
            }
        con2.close()
    except Exception:  # noqa: BLE001 — pecahan opsional; total tetap tampil
        pass

    # --- INVARIANT RISIKO (temuan QA eksternal, 7 Okt 2026) ---------------------------
    # Keluhan: "satu trade tidak boleh menghasilkan R < -1R kecuali diberi status khusus".
    # Kenyataannya BISA, dan penyebabnya bukan grader: ARA_HUNTER menahan posisi sampai
    # open sesi berikutnya, sehingga gap pembukaan bisa 14× risiko yang direncanakan.
    # Karena itu, bukan angkanya yang kami tutupi — melainkan kami KLASIFIKASIKAN:
    #   wajar    : R ≥ -1,05 (stop 1R dihormati, toleransi biaya)
    #   gap      : -1,05 > R ≥ -2   (gap kecil / biaya lebih besar dari perkiraan)
    #   dalam    : -2 > R ≥ -5      (gap signifikan di luar jam bursa)
    #   ekstrem  : R < -5           (posisi nyangkut; ARB/gap besar)
    # `pelanggaran_1r` = jumlah trade di luar kelas wajar. Angka ini WAJIB terbit supaya
    # halaman tidak pernah menyiratkan "rugi maksimal 1R" pada setup yang tidak begitu.
    kelas = {"wajar": 0, "gap": 0, "dalam": 0, "ekstrem": 0}
    pelanggaran = 0
    terburuk: dict[str, Any] | None = None
    for event_id, ticker, setup, _status, result, net_r, closed_at in rows:
        r = float(net_r)
        if r >= -1.05:
            kelas["wajar"] += 1
        else:
            pelanggaran += 1
            kelas["gap" if r >= -2 else "dalam" if r >= -5 else "ekstrem"] += 1
        if terburuk is None or r < float(terburuk["r"]):
            terburuk = {
                "signal_id": event_id, "pair": ticker, "setup": setup,
                "r": round(r, 2), "result": result, "closed_at": closed_at,
            }

    # Sinyal CREATED yang tak pernah tuntas: mesin IDX dibekukan (cron Tencent pause),
    # jadi baris ini BUKAN "posisi berjalan" — ia yatim. Menyebutnya berjalan = berbohong.
    yatim = {"jumlah": 0, "tertua": None}
    try:
        con3 = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        jml, tertua = con3.execute(
            "select count(*), min(created_at) from signals where status = 'CREATED'"
        ).fetchone()
        con3.close()
        yatim = {"jumlah": int(jml or 0), "tertua": tertua}
    except Exception:  # noqa: BLE001
        pass

    return {
        "market": "idx",
        "tersedia": True,
        "invariant": {
            "pelanggaran_1r": pelanggaran,
            "kelas_loss": kelas,
            "terburuk": terburuk,
            "model_breach": pelanggaran > 0,
            "penjelasan": (
                f"{pelanggaran} dari {len(rows)} trade tuntas rugi MELEBIHI 1R "
                "(stop 1R tidak bisa dieksekusi — exit di open sesi berikutnya / gap). "
                "Artinya: dompet ini TIDAK mengenal rugi maksimal 1R pada setup tersebut."
                if pelanggaran
                else "Semua trade tuntas rugi ≤ 1R — asumsi risiko terbatas terpenuhi."
            ),
        },
        "sinyal_yatim": yatim,
        "per_setup": dict(sorted(per_setup.items(), key=lambda kv: kv[1]["pnl_idr"], reverse=True)),
        "saldo_awal_idr": WALLET_IDR,
        "saldo_awal_unit": WALLET_IDR,
        "mata_uang": "IDR",
        "risk_pct": _DEFAULT_RISK_PCT,
        "risiko_per_trade_idr": risiko,
        "saldo_akhir_idr": round(WALLET_IDR + kum, 0),
        "pnl_idr": round(kum, 0),
        "pnl_usd": round(kum / kurs, 2) if kurs else None,
        "pnl_pct": round(100 * kum / WALLET_IDR, 3),
        "trade": len(rows),
        "titik": titik,
        "biaya_tercatat": True,
        "sumber": "state/idx_ledger.db (grader v3, net_r sudah termasuk biaya)",
        "catatan": [
            "net_r dari mesin sudah memperhitungkan biaya (grader v3).",
            "Posisi berstatus CREATED tidak dihitung — belum tuntas (lihat tab Sinyal).",
            "Risiko per trade = 1% × saldo awal, dalam rupiah langsung.",
            "PENTING: setup dengan min_r ≤ −3R (mis. ARA_HUNTER, terburuk −13,84R) TIDAK "
            "menghormati stop 1R — saldo bisa jauh lebih buruk daripada yang terlihat. "
            "Lihat kolom min_r per setup.",
        ],
    }


def _dompet_polymarket(state_dir: Path, kurs: float | None) -> dict[str, Any]:
    """Polymarket: dompet mengikuti ARM YANG DIPILIH (keputusan owner 7 Okt: arm B).

    Arm lain dibekukan: ditampilkan sebagai catatan, tidak dihitung ke saldo. Persentase
    PnL arm diambil apa adanya dari shadow summary (bukan dihitung ulang), lalu diterapkan
    ke saldo awal dompet — itu satu-satunya cara jujur memakai angka yang sudah terekam.
    """
    import subprocess

    arm = "B kandidat"
    berkas = {
        "A momentum": "/var/lib/poly-paper/execution-paper-shadow-summary.json",
        "B kandidat": "/var/lib/poly-paper-candidate/execution-paper-shadow-summary.json",
        "C fade": "/var/lib/poly-paper-fade/execution-paper-shadow-summary.json",
        "D favorit": "/var/lib/poly-paper-favorite/execution-paper-shadow-summary.json",
    }
    data: dict[str, Any] | None = None
    p = Path(berkas[arm])
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, PermissionError):
        try:
            r = subprocess.run(["sudo", "-n", "cat", str(p)], capture_output=True, text=True, timeout=10)
            data = json.loads(r.stdout) if r.returncode == 0 and r.stdout else None
        except Exception:  # noqa: BLE001
            data = None
    if not isinstance(data, dict):
        return {"market": "polymarket", "tersedia": False, "alasan": f"shadow summary {arm} tidak terbaca"}
    if kurs is None:
        return {"market": "polymarket", "tersedia": False, "alasan": "kurs USD→IDR tidak tersedia"}

    unit = WALLET_IDR / kurs
    pnl_arm = float(data.get("pnl") or 0)
    saldo_arm = float(data.get("initialBalance") or 0)
    if saldo_arm <= 0:
        return {"market": "polymarket", "tersedia": False, "alasan": "initialBalance arm tidak ada"}
    pnl_pct = pnl_arm / saldo_arm
    pnl = unit * pnl_pct
    return {
        "market": "polymarket",
        "tersedia": True,
        "saldo_awal_idr": WALLET_IDR,
        "saldo_awal_unit": round(unit, 2),
        "mata_uang": "USD",
        "kurs_usd_idr": kurs,
        "risk_pct": None,
        "saldo_akhir_usd": round(unit + pnl, 2),
        "pnl_usd": round(pnl, 2),
        "pnl_idr": round(pnl * kurs, 0),
        "pnl_pct": round(100 * pnl_pct, 3),
        "trade": int(data.get("entries") or 0),
        "wins": int(data.get("wins") or 0),
        "losses": int(data.get("losses") or 0),
        "titik": [],
        "biaya_tercatat": True,
        "sumber": f"shadow summary {arm} ({berkas[arm]}) — fee mode 'receipt'",
        "catatan": [
            f"Arm aktif: {arm} (keputusan owner 7 Okt). Arm lain dibekukan — tidak dihitung.",
            f"PnL arm {pnl_arm:+.4f} USD pada modal {saldo_arm:.0f} USD → {pnl_pct*100:+.2f}%; "
            f"persentase itu diterapkan ke dompet Rp 10 juta (kurs {kurs:,.0f}).",
            "Win-rate 82% arm ini belum lewat split beku — ini simulasi, bukan jaminan.",
        ],
    }


def _dompet_gmgn(state_dir: Path, kurs: float | None) -> dict[str, Any]:
    """GMGN/LP: dompet dari posisi LP TERBUKA (mark terakhir per posisi), diskalakan ke Rp 10 juta.

    KOREKSI 7 Okt (temuan audit): `lp_ledger.jsonl` adalah ledger **mark** — satu baris
    per penilaian. Satu posisi UBI menghasilkan 22 baris mark (naik lalu turun mengikuti
    harga). Versi sebelumnya menjumlahkan SEMUA baris sebagai posisi terpisah:
    modal terhitung $660 (22 × $30) padahal nyata $30, dan PnL dijumlahkan dari
    mark-mark di waktu berbeda → angka tak bermakna (dan menakutkan: −3,17%).

    Sekarang: kelompokkan per posisi (symbol + harga_masuk + notional), ambil mark
    TERAKHIR per grup; itu nilai posisi saat ini. Jumlah posisi = jumlah grup.
    """

    p = state_dir / "lp_ledger.jsonl"
    if not p.is_file():
        return {"market": "gmgn", "tersedia": False, "alasan": "lp_ledger.jsonl belum ada"}
    baris = [b for b in _ledger(p)]
    dinilai = [b for b in baris if b.get("status") == "dinilai" and b.get("pnl_usd") is not None]
    if not dinilai:
        return {"market": "gmgn", "tersedia": False, "alasan": "belum ada posisi LP dinilai"}
    if kurs is None:
        return {"market": "gmgn", "tersedia": False, "alasan": "kurs USD→IDR tidak tersedia"}

    # Pos = satu posisi LP. Mark terbaru per pos = nilainya SEKARANG.
    def _kunci(b: dict[str, Any]) -> tuple:
        return (b.get("symbol"), b.get("harga_masuk"), b.get("notional_usd"))

    def _waktu(b: dict[str, Any]) -> float:
        """Waktu mark sebagai ANGKA (untuk perbandingan).

        lp_ledger memakai `ts` epoch (float) — membandingkannya sebagai string membuat
        "999.0" > "1000.0" dan memilih mark yang salah. ISO juga diterima (di-parse).
        """
        mentah = b.get("dinilai_pada") or b.get("dicatat") or b.get("ts")
        if isinstance(mentah, (int, float)):
            return float(mentah)
        if isinstance(mentah, str) and mentah:
            try:
                from datetime import datetime as _dt

                return _dt.fromisoformat(mentah.replace("Z", "+00:00")).timestamp()
            except ValueError:
                return 0.0
        return 0.0

    grup: dict[tuple, dict[str, Any]] = {}
    for b in dinilai:
        k = _kunci(b)
        if k not in grup or _waktu(b) >= _waktu(grup[k]):
            grup[k] = b
    posisi: list[dict[str, Any]] = list(grup.values())

    unit = WALLET_IDR / kurs
    modal_ledger = sum(float(b.get("notional_usd") or 0) for b in posisi)
    pnl_ledger = sum(float(b.get("pnl_usd") or 0) for b in posisi)
    if modal_ledger <= 0:
        return {"market": "gmgn", "tersedia": False, "alasan": "notional LP tidak tercatat"}
    pratinjau = [
        {
            "i": i,
            "pair": b.get("symbol"),
            "pnl_usd": round(float(b.get("pnl_usd") or 0) * unit / modal_ledger, 2),
            "pnl_pct": b.get("pnl_pct"),
            "mark_terakhir": _waktu(b),
        }
        for i, b in enumerate(posisi, 1)
    ]
    pnl = unit * (pnl_ledger / modal_ledger)
    return {
        "market": "gmgn",
        "tersedia": True,
        "saldo_awal_idr": WALLET_IDR,
        "saldo_awal_unit": round(unit, 2),
        "mata_uang": "USD",
        "kurs_usd_idr": kurs,
        "risk_pct": None,
        "saldo_akhir_usd": round(unit + pnl, 2),
        "pnl_usd": round(pnl, 2),
        "pnl_idr": round(pnl * kurs, 0),
        "pnl_pct": round(100 * pnl_ledger / modal_ledger, 3),
        "trade": len(posisi),
        "mark_baris": len(dinilai),
        "titik": pratinjau,
        "biaya_tercatat": True,
        "sumber": "state/lp_ledger.jsonl (mark lokal: IL + fee terkumpul)",
        "catatan": [
            "Pos-fee: fee terkumpul dikurangi IL (perhitungan mark lokal, bukan rekonsiliasi on-chain).",
            f"Modal berputar: {modal_ledger:.2f} USD pada {len(posisi)} posisi "
            f"({len(dinilai)} baris mark — audit 7 Okt: satu posisi bisa punya puluhan mark; "
            "yang dipakai hanya mark TERAKHIR per posisi, bukan penjumlahan seluruh baris).",
        ],
    }
