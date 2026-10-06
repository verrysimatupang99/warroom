"""Dashboard satu layar — crypto + IDX + forex + GMGN + risiko.

Desain: **snapshot, bukan tiap request**. Membangun snapshot berarti memanggil
beberapa API (dan memakai kuota Arjum), jadi snapshot disimpan di
``state/snapshot.json`` dan dipakai ulang sampai TTL habis. Request HTTP hanya
membaca berkas — cepat, dan tidak bisa menghabiskan kuota.

Tampilan: gelap minimal, tanpa neon — angka dulu, hiasan belakangan.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import logging
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .config import Settings, get_settings
from .risk import RiskGate

log = logging.getLogger(__name__)

GMGN_DIR = Path.home() / "gmgn-paper" / "state"
_FRONTEND_DIR = (Path(__file__).resolve().parent.parent.parent / "frontend").resolve()
_ASETS_DIR = _FRONTEND_DIR / "assets"

e = html.escape


def _persen(x) -> str:
    """Persen atau n/a bila data kosong."""
    return f"{x:.1f}%" if isinstance(x, (int, float)) else "n/a"


def fharga(x) -> str:
    """Format harga adaptif: 2 desimal utk besar, presisi utk kecil."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return e(str(x))
    if v >= 100:
        return f"{v:,.2f}"
    if v >= 1:
        return f"{v:,.4f}"
    return f"{v:,.6f}"


MODEL_POD = "mimo-v2.6-flash"


def _wib() -> str:
    return (dt.datetime.now(dt.UTC) + dt.timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S WIB")


def _backtest_panel(settings: Any) -> dict[str, Any] | None:
    """Ringkas hasil backtest tersimpan — tanpa jaringan, hanya membaca berkas."""
    from . import backtest

    rows = backtest.muat_rows(settings, 300) or backtest.muat_rows(settings, 150)
    if not rows:
        return None
    a = backtest.aggregate(rows, fee_per_sisi=backtest.FEE_PER_SISI_DEFAULT)
    b = backtest.bandingkan(rows, fee_per_sisi=backtest.FEE_PER_SISI_DEFAULT)
    kl = backtest.uji_klaster(rows, fee_per_sisi=backtest.FEE_PER_SISI_DEFAULT)
    nol = backtest.uji_klaster_nol(rows, fee_per_sisi=backtest.FEE_PER_SISI_DEFAULT)
    return {
        "n": a["n_kandidat"],
        "terisi_pct": a["fill_rate_pct"],
        "biaya_bps": backtest.FEE_PER_SISI_DEFAULT * 10_000,
        "kotor_semua": a["semua"]["expectancy_r"],
        "semua_bersih": a["semua"]["expectancy_bersih_r"],
        "lolos_bersih": a["lolos"]["expectancy_bersih_r"],
        "lolos_terisi": a["lolos"]["terisi"],
        "lolos_keyakinan": a["lolos"]["keyakinan"],
        "ditolak_bersih": a["ditolak"]["expectancy_bersih_r"],
        "masuk_pasar_bersih": a["masuk_pasar"]["expectancy_bersih_r"],
        "masuk_pasar_terisi": a["masuk_pasar"]["terisi"],
        "klaster_r": kl.get("beda_r"),
        "klaster_t": kl.get("t"),
        "klaster_n_pair": kl.get("n_pair"),
        "nol_r": nol.get("rata_r"),
        "nol_t": nol.get("t"),
        "nol_keterangan": nol.get("keterangan"),
        "beda_lolos": b["lolos_vs_ditolak"],
        "beda_aturan": {
            k: {"beda_r": v["beda_r"], "t": v["t"], "keterangan": v["keterangan"]}
            for k, v in b["per_aturan"].items()
        },
        "per_aturan": {
            k: {"bersih": v["expectancy_bersih_r"], "n": v["n"], "putusan": v["putusan"]}
            for k, v in a["per_aturan"].items()
        },
    }


_RADAR_SEGAR_MNT = 45.0


def _radar_ringkas(
    chains: list,
    *,
    mtime: float | None = None,
    sumber: str = "live",
    cache_umur: float | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Bentuk panel dari daftar chain + jejak kesegaran. Gagal = tersedia False."""
    import time as _t

    arc = next((c for c in chains if c.get("chain") == "arc"), None)
    if not arc:
        return {"tersedia": False, "error": "arc tidak ada di state"}
    ringkas = [
        {
            "chain": c.get("chain"),
            "window": c.get("window"),
            "hp": c.get("hp_count"),
            "avg_vl": c.get("avg_vl"),
            "age": c.get("age_days"),
        }
        for c in chains
    ]
    out: dict[str, Any] = {
        "tersedia": True,
        "sumber": sumber,
        "umur_mnt": round((_t.time() - mtime) / 60, 1) if isinstance(mtime, (int, float)) else None,
        "cache_umur_mnt": (
            round(cache_umur, 1) if isinstance(cache_umur, (int, float)) else 0.0
        ),
        "arc_window": arc.get("window"),
        "arc_hp": arc.get("hp_count"),
        "arc_avg_vl": arc.get("avg_vl"),
        "arc_age": arc.get("age_days"),
        "n_chain": len(chains),
        "chains": ringkas,
    }
    if error:
        out["error"] = error
    return out


def _radar_panel(raw: str | None = None, state_dir: Any = None) -> dict[str, Any]:
    """Panel radar rantai — dibaca dari state **lokal** (hasil `lt radar-update`).

    Sejak 6 Okt 2026 radar dijalankan di Webdock sendiri (recreate dari VM Azure yang
    akan dimatikan), jadi TIDAK ada lagi SSH. Sumber kebenaran: ``state/radar_state.json``,
    ditulis oleh collector ``live_trading.collectors.radar`` saat perintah
    ``lt radar-update`` dijalankan.

    ``raw`` hanya untuk tes (isi state sebagai daftar chain) — tanpa berkas.
    Berkas hilang/rusak → ``tersedia=False`` + alasan (bukan nol, bukan nilai karangan).
    """
    if raw is not None:
        try:
            chains = json.loads(raw)
            if not isinstance(chains, list):
                raise ValueError("state bukan daftar")
            return _radar_ringkas(chains, sumber="lokal")
        except Exception as exc:  # noqa: BLE001 — panel jangan mati karena satu input
            return {"tersedia": False, "error": type(exc).__name__}

    if state_dir is None:
        return {"tersedia": False, "error": "state_dir tidak diberikan"}

    p = Path(state_dir) / "radar_state.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except OSError:
        return {"tersedia": False, "error": "radar_state.json tidak ada — jalankan `lt radar-update`"}
    except json.JSONDecodeError:
        return {"tersedia": False, "error": "radar_state.json rusak (JSON)"}

    if isinstance(d, dict):
        chains = d.get("chains") or []
        diambil = d.get("diambil_epoch")
    elif isinstance(d, list):  # format lama (daftar saja)
        chains, diambil = d, None
    else:
        return {"tersedia": False, "error": "bentuk state tidak dikenal"}

    try:
        mtime = p.stat().st_mtime
    except OSError:
        mtime = None
    # `diambil_epoch` (kapan radar benar-benar jalan) lebih jujur daripada mtime:
    # salinan berkas / restore bisa memperbarui mtime tanpa data baru.
    if isinstance(diambil, (int, float)):
        mtime = float(diambil)
    hasil = _radar_ringkas(chains, mtime=mtime, sumber="lokal")
    if not hasil.get("tersedia"):
        return {"tersedia": False, "error": hasil.get("error", "chain arc tidak ada di state")}
    return hasil


def _lencana_lp(verdict: str | None) -> str:
    if verdict == "KELUAR":
        return _lencana("fail", "KELUAR")
    if verdict == "TAHAN":
        return _lencana("ok", "TAHAN")
    return _lencana("tua", "tunggu mark")


def _arti_lp(lp: dict) -> str:
    """Artinya LP: verdict exit strategy per posisi (threads: entry+exit jelas)."""
    det = []
    for x in lp.get("posisi", []):
        v, a = x.get("verdict"), x.get("alasan") or ""
        if v == "KELUAR":
            det.append(f"{x.get('symbol')} CABUT — {a}")
        elif v == "TAHAN":
            det.append(f"{x.get('symbol')} tahan — {a}")
    if det:
        return "aturan exit: " + "; ".join(det) + "."
    return "eksperimen paper — verdict exit muncul setelah cron mark jalan."


WARNA_POD = {"hijau": "ok", "kuning": "warn", "merah": "fail", "abu": "tua"}


def _pod_card(lap, llm: dict | None = None) -> str:
    """Kartu laporan lead pod: badge status + ringkasan analis + nilai LLM."""
    baris = "".join(f"<li>{e(r)}</li>" for r in lap.ringkas)
    extra = ""
    if llm:
        cap = "setuju" if llm.get("setuju") else "tidak setuju"
        extra = f"<p class='sub'>Penilaian {MODEL_POD}: {cap} — {e(llm.get('catatan', ''))}</p>"
    return _card(
        f"Pod {e(lap.pod)} {_lencana(WARNA_POD.get(lap.status, 'tua'), lap.status)}",
        f"<ul>{baris}</ul>"
        + extra
        + _sumber("pod Fase 1: analis deterministik + nilai LLM, baca-saja")
        + _arti(
        f"laporan lead {lap.status}: tim pod pantau rutin, eskalasi ke kamu bila merah."
    ),
    )


def _lp_panel(path: str | None = None) -> dict[str, Any]:
    """Panel paper LP lokal — baca lp_paper_state.json, tidak pernah ditulis."""
    from pathlib import Path as _P

    p = _P(path or str(_P.home() / "gmgn-scan" / "lp_paper_state.json"))
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"tersedia": False}
    pos = d.get("positions") or []
    mark = None
    try:
        log = (p.parent / "lp_mark.log").read_text(encoding="utf-8").strip().splitlines()
        mark = log[-1] if log else None
    except OSError:
        mark = None
    return {
        "tersedia": True,
        "capital": d.get("capital_usd"),
        "mark_terakhir": mark,
        "posisi": [
            {
                "symbol": x.get("symbol"),
                "notional": x.get("notional_usd"),
                "fee_hari": x.get("fee_usd_per_day_est"),
                "vl": x.get("vl_at_entry"),
                "vl_now": x.get("vl_now"),
                "umur": x.get("umur_hari"),
                "verdict": x.get("exit_verdict"),
                "alasan": x.get("exit_alasan"),
            }
            for x in pos
        ],
    }


_POLY_ARMS = {
    "A momentum": "/var/lib/poly-paper/execution-paper-shadow-summary.json",
    "B kandidat": "/var/lib/poly-paper-candidate/execution-paper-shadow-summary.json",
    "C fade": "/var/lib/poly-paper-fade/execution-paper-shadow-summary.json",
    "D favorit": "/var/lib/poly-paper-favorite/execution-paper-shadow-summary.json",
}


def _poly_panel(path: str | None = None) -> dict[str, Any]:
    """Panel paper Polymarket — baca SEMUA arm mirror yang hidup, tanpa sudo wajib.

    Arm A (momentum, /var/lib/poly-paper/) merah; arm B (kandidat) dan D (favorit)
    hijau. Legacy /var/lib/poly-pilot/ mati sejak 24 Sep — tidak dibaca lagi.
    Berkas milik poly-pilot: coba baca langsung, lalu ``sudo -n``; gagal = n/a.
    Tidak pernah ditulis dari sini.
    """
    import subprocess

    if path:
        paths = {"arm": path}
    else:
        paths = _POLY_ARMS
    arms = []
    for nama, p in paths.items():
        raw = None
        try:
            with open(p, encoding="utf-8") as fh:
                raw = fh.read()
        except (OSError, PermissionError):
            try:
                r = subprocess.run(["sudo", "-n", "cat", p], capture_output=True, text=True, timeout=10)
                raw = r.stdout if r.returncode == 0 else None
            except Exception:  # noqa: BLE001
                raw = None
        if not raw:
            arms.append({"nama": nama, "tersedia": False})
            continue
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            arms.append({"nama": nama, "tersedia": False})
            continue
        arms.append(
            {
                "nama": nama,
                "tersedia": True,
                "balance": d.get("balance"),
                "pnl": d.get("pnl"),
                "entries": d.get("entries"),
                "wins": d.get("wins"),
                "losses": d.get("losses"),
                "settled": d.get("settled"),
                "open": d.get("open"),
                "updated": d.get("updated"),
            }
        )
    hidup = [a for a in arms if a.get("tersedia")]
    total_pnl = sum(float(a.get("pnl") or 0) for a in hidup)
    return {
        "tersedia": bool(hidup),
        "arms": arms,
        "total_pnl": round(total_pnl, 4),
        "updated": max((str(a.get("updated") or "") for a in hidup), default=""),
    }


def _gmgn_panel() -> dict[str, Any]:
    """Panel GMGN — dibaca saja, tidak pernah ditulis. Proyek GMGN tidak disentuh."""
    out: dict[str, Any] = {"tersedia": False}
    f = GMGN_DIR / "backtest_flow.json"
    if f.is_file():
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            out["tersedia"] = True
            out["profil"] = d.get("profile")
            out["sampel"] = d.get("samples")
            out["stats"] = (d.get("stats") or [])[:3]
        except (OSError, json.JSONDecodeError):
            pass
    log = GMGN_DIR / "cycle.log"
    if log.is_file():
        try:
            lines = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()
            out["log_terakhir"] = lines[-1][:160] if lines else ""
        except OSError:
            pass
    # radar 5 tab: shadow smart-money terbaru + pool LP
    sig = GMGN_DIR / "signals.jsonl"
    if sig.is_file():
        try:
            rows = []
            for line in sig.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-60:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            out["shadow"] = rows[-30:]
        except OSError:
            pass
    lpp = GMGN_DIR / "lp_pools.jsonl"
    if lpp.is_file():
        try:
            pools = []
            for line in lpp.read_text(encoding="utf-8", errors="replace").strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    pools.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            pools.sort(key=lambda p: float(p.get("volume_24h_usd") or 0), reverse=True)
            out["lp_top"] = [
                {
                    "symbol": p.get("symbol"),
                    "chain": p.get("chain"),
                    "dex": p.get("exchange"),
                    "fee": p.get("fee_pct"),
                    "liq": p.get("liquidity_usd"),
                    "vol24": p.get("volume_24h_usd"),
                }
                for p in pools[:8]
            ]
        except OSError:
            pass
    return out


def build_snapshot(settings: Settings | None = None, *, use_network: bool = True) -> dict[str, Any]:
    s = settings or get_settings()
    snap: dict[str, Any] = {"dibuat": _wib(), "mode": "paper" if s.paper else "live", "bagian": {}}

    gate = RiskGate(s)
    snap["risiko"] = gate.status()

    if use_network:
        try:
            from .collectors.crypto import CryptoCollector

            snap["bagian"]["crypto"] = CryptoCollector(s).digest()
        except Exception as exc:  # noqa: BLE001 — dashboard jangan mati karena satu bagian
            snap["bagian"]["crypto"] = {"error": f"{type(exc).__name__}: {exc}"}

        try:
            from .collectors.idx import ArjumCollector

            col = ArjumCollector(s)
            scr = col.screener(limit=5)
            baris = (scr.get("rows") or [])[:5]
            cross = []
            try:
                from .collectors.idx_check import gabungkan, tv_snapshot

                cross = gabungkan(baris, tv_snapshot([str(r.get("stock_code", "")) for r in baris]))
            except Exception as exc:  # noqa: BLE001 — cross-check opsional, jangan matikan panel
                cross = [{"putusan": f"gagal: {type(exc).__name__}"}]
            snap["bagian"]["idx"] = {
                "rows": baris,
                "sumber": scr.get("source"),
                "kuota": col.quota(),
                "cross_check": cross,
            }
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["idx"] = {"error": f"{type(exc).__name__}: {exc}"}

        try:
            from .collectors.forex import ForexCollector

            snap["bagian"]["forex"] = ForexCollector(s).structure("60", 120)
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["forex"] = {"error": f"{type(exc).__name__}: {exc}"}

        try:
            from .collectors import macro

            # Gerbang stand-down: event berdampak tinggi dalam 60 menit ke depan.
            snap["bagian"]["macro"] = macro.MacroCollector(s).snapshot(s.state_dir)
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["macro"] = {"error": f"{type(exc).__name__}: {exc}"}

        try:
            from .collectors import news

            # Berita kripto (RSS publik, tanpa kuota). Judul + tautan saja.
            snap["bagian"]["news"] = news.snapshot(s)
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["news"] = {"error": f"{type(exc).__name__}: {exc}"}

        try:
            from .collectors import hyperliquid

            snap["bagian"]["hyperliquid"] = hyperliquid.snapshot(s, top=5)
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["hyperliquid"] = {"error": f"{type(exc).__name__}: {exc}"}

        try:
            from .collectors import idx_tv

            snap["bagian"]["idx_tv"] = idx_tv.summary(idx_tv.screen(uptrend_only=True, limit=5))
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["idx_tv"] = {"error": f"{type(exc).__name__}: {exc}"}

        try:
            # BSJP (beli sore jual pagi): peringkat kandidat tahan semalam, memakai filter
            # yang sudah diuji walk-forward (lihat signals/bsjp.py). SMA10 diambil dari arsip
            # tick Arjum (collectors/riwayat_idx.py) supaya TIDAK menambah panggilan kuota REST.
            # Angka net-nya BERSUMBER dari walk-forward Tencent, bukan hitungan ulang di sini —
            # `terverifikasi_di_warroom=False` dan catatan_kejujuran wajib ikut tampil.
            from .collectors import riwayat_idx
            from .signals import bsjp

            scr_rows = (snap["bagian"].get("idx") or {}).get("rows") or []
            tv_rows = (snap["bagian"].get("idx_tv") or {}).get("rows") or []
            # SMA10 hanya untuk ticker yang lolos gerbang harga dulu: menghemat kueri dan
            # tidak menarik riwayat emiten yang toh akan ditolak.
            calon = [str(r.get("ticker") or "").upper() for r in tv_rows if r.get("ticker")]
            riwayat: dict[str, dict] = {}
            try:
                if calon:
                    riwayat = {t: v.to_dict() for t, v in riwayat_idx.ambil_riwayat(calon).items()}
            except Exception as exc:  # noqa: BLE001 — SMA10 opsional; BSJP tetap jalan tanpa itu
                log.warning("bsjp: riwayat SMA10 gagal: %s", exc)
            snap["bagian"]["bsjp"] = bsjp.susun_peringkat(
                scr_rows, tv_rows, riwayat=riwayat
            ).to_dict()
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["bsjp"] = {"error": f"{type(exc).__name__}: {exc}"}

        try:
            from .collectors import dexscreen

            gshadow = []
            try:
                gshadow = (_gmgn_panel().get("shadow") or [])[-15:]
            except Exception:  # noqa: BLE001 — shadow opsional
                gshadow = []
            snap["bagian"]["dex"] = dexscreen.snapshot(s.state_dir, gshadow)
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["dex"] = {"error": f"{type(exc).__name__}: {exc}"}

        try:
            from . import lp_positions

            # Posisi LP nyata yang dicatat + kolam kandidat Solana (discovery).
            # Dua hal yang sengaja dipisah: `posisi` = uang betul-betul diparkir,
            # `kandidat` = layar pencarian. Mencampur keduanya = cara medsos mengelabui.
            from .collectors import dexscreen

            laporan_lp = lp_positions.laporan(s.state_dir)
            try:
                kandidat = dexscreen.lp_cari("SOL", 5, rantai="solana")
            except Exception:  # noqa: BLE001 — discovery opsional, posisi tetap tampil
                kandidat = []
            snap["bagian"]["lp"] = {
                **laporan_lp,
                "kandidat": kandidat,
                "catatan": [
                    "posisi = uang nyata yang dicatat; kandidat = hasil pencarian, belum diparkir",
                    "fee APR nyata & LP-vs-hold-USD butuh harga masuk+keluar posisi (lihat halaman Bukti)",
                ],
            }
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["lp"] = {"error": f"{type(exc).__name__}: {exc}"}

        try:
            from .collectors import idx616

            snap["bagian"]["idx616"] = idx616.snapshot(s.state_dir)
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["idx616"] = {"error": f"{type(exc).__name__}: {exc}"}

        try:
            from .collectors import crypto as _crypto
            from .collectors import overextended

            # Selalu disertai hasil uji edge-nya — label "overextended" saja tidak pernah cukup.
            snap["bagian"]["overextended"] = overextended.snapshot(
                _crypto.DEFAULT_PAIRS, s.state_dir
            )
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["overextended"] = {"error": f"{type(exc).__name__}: {exc}"}

        try:
            from .collectors import bandarmologi
            from .collectors.idx import ArjumCollector

            # Broker-flow IDX. Kuota Arjum 6000/hari untuk SELURUH pemakaian, jadi kandidat
            # diambil dari screener (1 panggilan) lalu dibatasi 4 ticker — dan hasilnya
            # di-cache 6 jam. Cache-nya bukan optimasi, itu bagian dari disiplin kuota.
            _ac = ArjumCollector(s)
            _rows = (_ac.screener(limit=8).get("rows") or [])
            _kode = [r["stock_code"] for r in _rows if r.get("stock_code")][:4]
            snap["bagian"]["bandarmologi"] = bandarmologi.skrining(
                _kode, s.state_dir, maks_ticker=4, ambil=_ac.broker_summary
            )
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["bandarmologi"] = {"error": f"{type(exc).__name__}: {exc}"}

        try:
            from .collectors import dexscreen, memecoin

            # Sumber memecoin (Pumpfun / DEX Solana / Robinhood). Label aslinya dipertahankan:
            # data mentah, bukan rekomendasi — tidak ada track record yang bisa diverifikasi.
            snap["bagian"]["memecoin"] = memecoin.skrining(
                s.state_dir, per_venue=5, ambil=dexscreen.cari_pool
            )
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["memecoin"] = {"error": f"{type(exc).__name__}: {exc}"}

    # posisi & ledger dari berkas (tanpa jaringan)
    p = s.state_dir / "paper_positions.json"
    try:
        snap["posisi"] = json.loads(p.read_text(encoding="utf-8")).get("positions", [])
    except (OSError, json.JSONDecodeError):
        snap["posisi"] = []

    rows = gate.ledger()
    total_r = round(sum(float(r.get("r") or 0) for r in rows), 3)
    wins = sum(1 for r in rows if float(r.get("r") or 0) > 0)
    snap["ledger"] = {
        "trade": len(rows),
        "total_r": total_r,
        "winrate_pct": round(wins / len(rows) * 100, 1) if rows else None,
        "expectancy_r": round(total_r / len(rows), 3) if rows else None,
        "terakhir": rows[-3:],
    }
    try:
        from . import equity as _equity

        c = _equity.curve(s)
        snap["equity"] = {"stats": c["stats"], "points": c["points"][-12:]}
    except Exception:  # noqa: BLE001 — kartu ekuitas opsional
        snap["equity"] = {"stats": {}, "points": []}

    # Data paper & risiko per-venue (5 pasar independen: $200 x 5 = $1,000)
    for v in ("idx", "forex", "gmgn", "polymarket"):
        try:
            v_gate = RiskGate(s, venue=v)
            v_pos = v_gate.open_positions()
            v_rows = v_gate.ledger()
            v_tot_r = round(sum(float(r.get("r") or 0) for r in v_rows), 3)
            v_wins = sum(1 for r in v_rows if float(r.get("r") or 0) > 0)
            v_c = _equity.curve(s, venue=v)

            prefix = "poly" if v == "polymarket" else v
            snap[f"{prefix}_posisi"] = v_pos
            snap[f"{prefix}_risiko"] = v_gate.status()
            snap[f"{prefix}_ledger"] = {
                "trade": len(v_rows),
                "total_r": v_tot_r,
                "winrate_pct": round(v_wins / len(v_rows) * 100, 1) if v_rows else None,
                "expectancy_r": round(v_tot_r / len(v_rows), 3) if v_rows else None,
                "terakhir": v_rows[-3:],
            }
            snap[f"{prefix}_equity"] = {"stats": v_c["stats"], "points": v_c["points"][-12:]}
        except Exception:
            pass

    snap["gmgn"] = _gmgn_panel()
    snap["lp_paper"] = _lp_panel()
    snap["poly_paper"] = _poly_panel()
    if use_network:
        snap["radar"] = _radar_panel(state_dir=s.state_dir)
    else:
        snap["radar"] = {"tersedia": False, "error": "offline"}

    # kandidat & pengukuran (berkas; pengukuran butuh jaringan untuk melacak hasil)
    try:
        from . import measure

        snap["kandidat"] = measure.load_verdicts(s)[-8:]
        if use_network:
            rep = measure.report(s)
            snap["pengukuran"] = {k: v for k, v in rep.items() if k != "rows"}
    except Exception as exc:  # noqa: BLE001 — dashboard jangan mati karena satu bagian
        snap["kandidat"] = []
        snap["pengukuran"] = {"error": f"{type(exc).__name__}: {exc}"}

    try:
        snap["backtest"] = _backtest_panel(s)
    except Exception:  # noqa: BLE001
        snap["backtest"] = None

    # nilai LLM lead pod (nutaraline mimo; opsional — gagal = kartu jalan tanpa nilai)
    try:
        if use_network:
            from live_trading.pods import gmgn as _pg
            from live_trading.pods import idx as _pi
            from live_trading.pods import kripto as _pk
            from live_trading.pods import nilai as _nilai
            from live_trading.pods import poly as _pp

            snap["pod_llm"] = _nilai.nilai_semua(
                {
                    n: [r for r in m.lead(snap).ringkas]
                    for n, m in (
                        ("kripto", _pk),
                        ("poly", _pp),
                        ("gmgn", _pg),
                        ("idx", _pi),
                    )
                }
            )
    except Exception:  # noqa: BLE001
        snap["pod_llm"] = {}

    return snap


def load_snapshot(settings: Settings, *, force: bool = False) -> dict[str, Any]:
    """Snapshot dari berkas; dibangun ulang kalau belum ada atau sudah kedaluwarsa."""
    import time

    p = settings.state_dir / "snapshot.json"
    if not force and p.is_file() and (time.time() - p.stat().st_mtime) < settings.snapshot_ttl_s:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    snap = build_snapshot(settings)
    settings.state_dir.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    return snap


# --------------------------------------------------------------------- render
def _grafik_ekuitas(pts: list[dict[str, Any]]) -> str:
    """Grafik garis SVG kurva kumulatif R — murni presentasi, tanpa JS."""
    w, h, pad = 300, 90, 6
    vals = [float(p.get("cum", 0)) for p in pts]
    lo, hi = min(vals + [0.0]), max(vals + [0.0])
    span = (hi - lo) or 1.0
    n = len(vals)
    xy = [
        (pad + i * (w - 2 * pad) / max(n - 1, 1), h - pad - (v - lo) / span * (h - 2 * pad))
        for i, v in enumerate(vals)
    ]
    garis = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    y0 = h - pad - (0 - lo) / span * (h - 2 * pad)
    warna = "#3ed68f" if vals[-1] >= 0 else "#ff6b7d"
    # Arsiran periode drawdown terbesar (pola plot-profit Freqtrade): puncak ke lembah.
    puncak, dd_max, i_puncak, i_dd0, i_dd1 = vals[0], 0.0, 0, 0, 0
    for i, v in enumerate(vals):
        if v > puncak:
            puncak, i_puncak = v, i
        dd = puncak - v
        if dd > dd_max:
            dd_max, i_dd0, i_dd1 = dd, i_puncak, i
    arsir = ""
    if dd_max > 0 and i_dd1 > i_dd0:
        arsir = (
            f"<rect x='{xy[i_dd0][0]:.1f}' y='0' width='{xy[i_dd1][0] - xy[i_dd0][0]:.1f}' "
            f"height='{h}' fill='#ff6b7d' opacity='0.10'/>"
        )
    return (
        f"<svg viewBox='0 0 {w} {h}' style='width:100%;max-width:100%;display:block' role='img'>"
        f"{arsir}"
        f"<line x1='0' y1='{y0:.1f}' x2='{w}' y2='{y0:.1f}' stroke='#202a3a' stroke-width='1'/>"
        f"<polyline points='{garis}' fill='none' stroke='{warna}' stroke-width='2'/>"
        f"<circle cx='{xy[-1][0]:.1f}' cy='{xy[-1][1]:.1f}' r='3' fill='{warna}'/></svg>"
    )


def _bar_pair(pts: list[dict[str, Any]]) -> str:
    """Bar profit per pair (pola Freqtrade) — agregat R per pair dari titik kurva."""
    agg: dict[str, float] = {}
    for p in pts:
        nama = str(p.get("pair") or "—")
        agg[nama] = agg.get(nama, 0.0) + float(p.get("r") or 0)
    if not agg:
        return ""
    maks = max(abs(v) for v in agg.values()) or 1.0
    baris = []
    for nama, v in sorted(agg.items(), key=lambda kv: kv[1], reverse=True):
        if nama == "—":
            continue  # titik awal tanpa pair — bukan data
        kiri = 50.0 if v < 0 else 0.0
        lebar = abs(v) / maks * 50.0
        warna = "#3ed68f" if v >= 0 else "#ff6b7d"
        nol = " nol" if abs(v) < 0.005 else ""
        baris.append(
            f"<div class='bar{nol}'><span class='nm'>{html.escape(nama)}</span>"
            f"<span class='rel'><span class='isi' style='left:{kiri:.1f}%;width:{lebar:.1f}%;"
            f"background:{warna}'></span></span>"
            f"<span class='vl'>{v:+.2f}R</span></div>"
        )
    return "".join(baris)


_TERMINAL = """<section id='terminal-live'><h2>Terminal live
<span class='badge mati'>menghubungkan</span></h2>
<p class='src'>chart: klines Binance langsung di browser · garis = zona paper kita ·
<span id='t-jam'></span></p>
<div class='tape'><div class='tape-dalam' id='tape'><span class='tk'>memuat harga…</span></div></div>
<div class='tbar' id='t-pairs'></div>
<div class='tbar' id='t-tfs'></div>
<canvas id='chart'></canvas>
<p class='sub' id='t-info'>menyiapkan chart…</p>
</section>
<script>
(function(){
var PAIRS=['BTCUSDT','ETHUSDT','SOLUSDT','HYPEUSDT','BNBUSDT','DOGEUSDT'];
var TFS=['15m','1h','4h'];
var pair='BTCUSDT',tf='1h',zones=[],bi=0;
var BASES=['https://api.binance.com','https://data-api.binance.vision'];
var UP='#3ed68f',DN='#ff6b7d',GOLD='#55c7df',GRID='rgba(32,42,58,.9)',TXT='#7c8aa0';
function $(id){return document.getElementById(id);}
function fmt(n){n=Number(n);return n.toLocaleString('en-US',{maximumFractionDigits:(n<10?4:2)});}
async function jget(path){
  var last='?';
  for(var k=0;k<BASES.length;k++){
    try{
      var r=await fetch(BASES[(bi+k)%BASES.length]+path);
      if(r.ok){bi=(bi+k)%BASES.length;return await r.json();}
      last='http '+r.status;
    }catch(e){last='jaringan';}
  }
  throw new Error(last);
}
function status(ok,txt){
  var b=document.querySelector('#terminal-live .badge');
  if(!b){return;}
  b.className='badge '+(ok?'ok':'mati');
  b.textContent=txt;
}
async function tape(){
  try{
    var sym=PAIRS.map(function(p){return '\"'+p+'\"';}).join(',');
    var d=await jget('/api/v3/ticker/24hr?symbols=['+sym+']');
    var html='';
    d.forEach(function(t){
      var c=Number(t.priceChangePercent)>=0;
      var pc=Number(t.priceChangePercent).toFixed(2)+'%';
      html+='<span class=\"tk\">'+t.symbol.replace('USDT','');
      html+=' <b style=\"color:'+(c?UP:DN)+'\">'+fmt(t.lastPrice)+'</b>';
      html+=' <span style=\"color:'+(c?UP:DN)+'\">'+pc+'</span></span>';
    });
    $('tape').innerHTML=html+html;
  }catch(e){$('tape').innerHTML='<span class=\"tk\">harga live belum bisa dimuat ('+e.message+')</span>';}
}
async function muatZona(){
  try{
    var s=await (await fetch('api/snapshot',{cache:'no-store'})).json();
    zones=(s.kandidat||[]).filter(function(k){return k.pair===pair&&k.entry;});
  }catch(e){zones=[];}
}
function tombol(el,daftar,aktif,klik){
  var box=$(el);box.innerHTML='';
  daftar.forEach(function(nama){
    var b=document.createElement('button');
    b.textContent=nama.replace('USDT','');
    if(nama===aktif){b.className='aktif';}
    b.onclick=function(){klik(nama);};
    box.appendChild(b);
  });
}
function ema(data,n){
  var k=2/(n+1),out=[],prev=null;
  data.forEach(function(v,i){
    prev=(i===0)?v:v*k+prev*(1-k);
    out.push(prev);
  });
  return out;
}
async function chart(){
  var cv=$('chart');
  var dpr=window.devicePixelRatio||1;
  var W=cv.clientWidth*dpr,H=300*dpr;
  cv.width=W;cv.height=H;
  var g=cv.getContext('2d');
  g.clearRect(0,0,W,H);
  try{
    var kl=null;
    try{
      var rk=await fetch('api/klines?pair='+pair+'&tf='+tf,{cache:'no-store'});
      if(rk.ok){kl=await rk.json();}
    }catch(e){kl=null;}
    if(!Array.isArray(kl)||!kl.length){
      kl=await jget('/api/v3/klines?symbol='+pair+'&interval='+tf+'&limit=120');
    }
    var O=[],Hh=[],L=[],C=[],V=[];
    kl.forEach(function(r){O.push(+r[1]);Hh.push(+r[2]);L.push(+r[3]);C.push(+r[4]);V.push(+r[5]);});
    var lo=Math.min.apply(null,L),hi=Math.max.apply(null,Hh);
    zones.forEach(function(z){
      [z.entry,z.sl,z.tp1,z.poi_low,z.poi_high].forEach(function(v){
        if(v){lo=Math.min(lo,v);hi=Math.max(hi,v);}
      });
    });
    var pad=(hi-lo)*0.08||1;lo-=pad;hi+=pad;
    var labelW=64*dpr,plotW=W-labelW,plotH=H-20*dpr,volH=plotH*0.2;
    function y(p){return (hi-p)/(hi-lo)*(plotH-volH-8*dpr)+4*dpr;}
    function x(i){return i/119*plotW;}
    g.strokeStyle=GRID;g.fillStyle=TXT;g.font=(10*dpr)+'px sans-serif';
    for(var q=0;q<4;q++){
      var pv=lo+(hi-lo)*q/3,py=y(pv);
      g.beginPath();g.moveTo(0,py);g.lineTo(W,py);g.stroke();
      g.fillText(fmt(pv),plotW+6*dpr,py+3*dpr);
    }
    var vmax=Math.max.apply(null,V)||1;
    var cw=plotW/120;
    for(var i=0;i<120;i++){
      var up=C[i]>=O[i],col=up?UP:DN,xx=x(i);
      g.strokeStyle=col;g.fillStyle=col;
      g.beginPath();g.moveTo(xx,y(Hh[i]));g.lineTo(xx,y(L[i]));g.stroke();
      var yO=y(O[i]),yC=y(C[i]);
      g.fillRect(xx-cw*0.32,Math.min(yO,yC),cw*0.64,Math.max(1,Math.abs(yC-yO)));
      var vh=V[i]/vmax*volH;
      g.globalAlpha=0.35;g.fillRect(xx-cw*0.32,plotH-vh,cw*0.64,vh);g.globalAlpha=1;
    }
    var E=ema(C,20);
    g.strokeStyle=GOLD;g.beginPath();
    E.forEach(function(v,i){var px=x(i),py=y(v);if(i===0){g.moveTo(px,py);}else{g.lineTo(px,py);}});
    g.stroke();
    zones.forEach(function(z){
      var arah=(z.direction||'').toLowerCase()==='short';
      var zcol=arah?DN:UP;
      if(z.poi_low&&z.poi_high){
        g.fillStyle='rgba(233,237,245,0.07)';
        g.fillRect(0,y(z.poi_high),plotW,y(z.poi_low)-y(z.poi_high));
      }
      [['entry',z.entry,zcol,'-'],['sl',z.sl,DN,'.'],['tp',z.tp1,GOLD,'.']].forEach(function(L3){
        if(!L3[1]){return;}
        var yy=y(L3[1]);
        g.strokeStyle=L3[2];g.setLineDash(L3[3]==='-'?[5*dpr,4*dpr]:[2*dpr,3*dpr]);
        g.beginPath();g.moveTo(0,yy);g.lineTo(plotW,yy);g.stroke();g.setLineDash([]);
        g.fillStyle=L3[2];g.fillText(L3[0]+' '+fmt(L3[1]),6*dpr,yy-3*dpr);
      });
    });
    var last=C[119];
    g.fillStyle=last>=O[119]?UP:DN;
    g.fillRect(plotW,Math.max(0,y(last)-9*dpr),labelW,18*dpr);
    g.fillStyle='#0b0611';g.fillText(fmt(last),plotW+6*dpr,y(last)+3*dpr);
    var now=new Date();
    $('t-info').textContent=pair.replace('USDT','')+' '+tf+' · 120 candle · ';
    var wib=now.toLocaleTimeString('id-ID',{timeZone:'Asia/Jakarta'});
  $('t-info').textContent+=zones.length+' zona paper · '+wib+' WIB';
    status(true,'live');
  }catch(e){
    $('t-info').textContent='chart belum bisa dimuat ('+e.message+') — coba lagi sebentar.';
    status(false,'n/a');
  }
}
function segar(){
  tombol('t-pairs',PAIRS,pair,function(nama){pair=nama;muatZona().then(chart);});
  tombol('t-tfs',TFS,tf,function(nama){tf=nama;chart();});
}
segar();muatZona().then(chart);tape();
setInterval(chart,15000);setInterval(tape,10000);
setInterval(function(){
  var el=$('t-jam');
  if(el){el.textContent=new Date().toLocaleTimeString('id-ID');}
  var top=$('t-jam-top');
  if(top){top.textContent=new Date().toLocaleTimeString('id-ID',{hour:'2-digit',minute:'2-digit'});}
},1000);
})();
</script>"""


def _ringkas(snap: dict[str, Any]) -> list[tuple[str, str]]:
    """Ringkasan 10 detik — tiap peluru menjawab 'jadi apa artinya buat saya'.

    Murni baca snapshot, tanpa jaringan. Nada mengikuti tanda angka.
    """
    out: list[tuple[str, str]] = []
    led = snap.get("ledger", {})
    tr, total = led.get("trade", 0) or 0, led.get("total_r", 0) or 0
    out.append(
        (
            f"Paper kripto {total:+.2f}R dari {tr} trade (warisan, bukan hasil gate)",
            "pass" if total > 0 else "fail" if total < 0 else "",
        )
    )
    ukur = snap.get("pengukuran") or {}
    lo = ukur.get("lolos", {}) if isinstance(ukur, dict) else {}
    if lo.get("n"):
        exp = lo.get("expectancy_r")
        out.append(
            (
                f"Forward: {lo['n']} kandidat lolos, expectancy {exp:+.2f}R — sistem belum terbukti"
                if (exp or 0) < 0
                else f"Forward: {lo['n']} kandidat lolos, expectancy {exp:+.2f}R",
                "fail" if (exp or 0) < 0 else "pass" if (exp or 0) > 0 else "",
            )
        )
    bt = snap.get("backtest") or {}
    if bt.get("lolos_bersih") is not None:
        bersih = bt["lolos_bersih"] or 0
        out.append(
            (
                f"Backtest: gate {bersih:+.3f}R, keyakinan {bt.get('lolos_keyakinan')} "
                "— ambang terkunci oleh bukti",
                "fail" if bersih < 0 else "pass",
            )
        )
    pos = snap.get("posisi") or []
    out.append((f"{len(pos)} posisi paper terbuka" if pos else "Tidak ada posisi paper terbuka", ""))
    rd = snap.get("radar", {})
    if rd.get("tersedia"):
        out.append(
            (
                f"Radar: Arc {rd.get('arc_window')} {rd.get('arc_age')} hari, HP {rd.get('arc_hp')}",
                "pass" if rd.get("arc_window") == "PRIME" else "",
            )
        )
    pp = snap.get("poly_paper", {})
    if pp.get("tersedia"):
        tpnl = float(pp.get("total_pnl") or 0)
        det = " · ".join(
            f"{str(a.get('nama', '')).split()[0]} {float(a.get('pnl') or 0):+.2f}"
            for a in pp.get("arms", [])
            if a.get("tersedia")
        )
        out.append(
            (
                f"Polymarket 4 arm gabungan {tpnl:+.2f} USD ({det})",
                "pass" if tpnl > 0 else "fail" if tpnl < 0 else "",
            )
        )
    return out[:6]


def _radar_tabs(shadow: list[dict], lp_top: list[dict], dex: dict | None = None) -> str:
    """6 tab Radar: Smart Buy, Smart Money, Whale, Copy, LP Edge, DEX Boost.

    Murni dari signals.jsonl + lp_pools.jsonl + DEX Screener (baca-saja, gratis).
    Label tren dihitung saat tampil dari ret_5m yang tersimpan — bukan data baru.
    """
    e = html.escape
    dex = dex or {}
    enrich = dex.get("enrich") or {}

    def bs_txt(r: dict) -> str:
        info = enrich.get(str(r.get("key") or ""))
        if not info:
            return "—"
        v = info.get("bs_m5")
        return f"{v}x" if isinstance(v, (int, float)) else "—"

    def tren(r: dict) -> tuple[str, str]:
        m = r.get("ret_5m_pct")
        if m is None:
            return ("—", "")
        if m >= 15:
            return ("Panas", "down")
        if m >= 5:
            return ("Hangat", "")
        return ("Tenang", "up")

    def baris(r: dict, ekstra: str = "") -> str:
        t, nada = tren(r)
        sh = r.get("shadow_pct")
        sh_txt = f"{sh:+.1f}%" if isinstance(sh, (int, float)) else "—"
        return (
            f"<tr><td>{e(str(r.get('symbol') or '?'))}</td>"
            f"<td class='n'>{r.get('cluster_wallets', '?')}</td>"
            f"<td class='n'>${r.get('cluster_buy_usd', '?')}</td>"
            f"<td class='{nada}'>{t}</td>"
            f"<td class='n'>{bs_txt(r)}</td>"
            f"<td class='n'>{sh_txt}</td>{ekstra}</tr>"
        )

    head = (
        "<table><tr><th>token</th><th>wallet</th><th>beli</th><th>tren</th>"
        "<th>B/S 5m</th><th>vs entry</th></tr>"
    )
    tabs = ""
    if shadow:
        beli = [r for r in shadow if (r.get("ret_5m_pct") or 99) < 15 and (r.get("ret_1h_pct") or 0) >= 100]
        tabs += (
            f"<details open><summary>{_tab('Smart Buy', len(beli), 'sinyal — cek tren tiap baris')}</summary>"
            + (
                f"{head}{''.join(baris(r) for r in reversed(beli[-12:]))}</table>"
                "<p class='sub'>tenang 5 menit + momentum sejam — lolos veto entry. "
                "Yang lolos veto inilah bahan paper-trade; minus sejak sinyal = hati-hati.</p>"
                if beli
                else "<p class='sub'>tidak ada yang memenuhi syarat veto sekarang</p>"
            )
            + "</details>"
        )
        tabs += (
            f"<details><summary>{_tab('Smart Money', len(shadow), 'sinyal')}</summary>"
            f"{head}{''.join(baris(r) for r in reversed(shadow[-12:]))}</table>"
            "<p class='sub'>semua wallet jago + label tren dari gerak 5 menit. "
            "Tenang = belum lari.</p></details>"
        )
        paus = [r for r in shadow if r.get("whale") or (r.get("max_single_usd") or 0) >= 1000]
        tabs += (
            f"<details><summary>{_tab('Whale', len(paus), 'print ≥$1.000')}</summary>"
            + (
                "<table><tr><th>token</th><th>wallet</th><th>beli</th><th>tren</th><th>B/S 5m</th>"
                "<th>sejak sinyal</th><th>print max</th></tr>"
                + "".join(
                    baris(r, f"<td class='n'>${r.get('max_single_usd', '?')}</td>")
                    for r in reversed(paus[-12:])
                )
                + "</table>"
                if paus
                else "<p class='sub'>belum ada print paus di window ini</p>"
            )
            + "</details>"
        )
        kopi = [r for r in shadow if r.get("copy")]
        tabs += (
            f"<details><summary>{_tab('Copy', len(kopi), 'sinyal ≥7 wallet')}</summary>"
            + (
                f"{head}{''.join(baris(r) for r in reversed(kopi[-12:]))}</table>"
                "<p class='sub'>cluster besar = banyak wallet jago sepakat. Marker ukur, "
                "bukan perintah — shadow_pct yang membuktikan.</p>"
                if kopi
                else "<p class='sub'>belum ada cluster ≥7 wallet di window ini</p>"
            )
            + "</details>"
        )
    if lp_top:
        rows = "".join(
            f"<tr><td>{e(str(p.get('symbol') or '?'))}</td><td>{e(str(p.get('chain') or ''))}</td>"
            f"<td>{e(str(p.get('dex') or ''))}</td>"
            f"<td class='n'>{p.get('fee') if p.get('fee') is not None else '?'}%</td>"
            f"<td class='n'>${float(p.get('liq') or 0):,.0f}</td>"
            f"<td class='n'>${float(p.get('vol24') or 0):,.0f}</td></tr>"
            for p in lp_top
        )
        tabs += (
            f"<details><summary>LP Edge ({len(lp_top)} pool)</summary>"
            "<table><tr><th>pool</th><th>chain</th><th>dex</th><th>fee</th>"
            "<th>likuiditas</th><th>vol 24j</th></tr>"
            f"{rows}</table>"
            "<p class='sub'>skor pool buat jadi LP: fee × volume vs likuiditas. "
            "Angka mentah — putusan isi/tidak tetap nunggu paper LP hijau.</p></details>"
        )
    boosts = dex.get("boosts") or []
    if boosts:
        rows = "".join(
            f"<tr><td>{e(str(b.get('symbol') or '?'))}</td><td>{e(str(b.get('chain') or ''))}</td>"
            f"<td><a href='{e(str(b.get('url') or ''))}'>chart</a></td>"
            f"<td>{e(str(b.get('description') or ''))}</td></tr>"
            for b in boosts
        )
        tabs += (
            f"<details><summary>DEX Boost ({len(boosts)} token)</summary>"
            "<table><tr><th>token</th><th>chain</th><th>chart</th><th>deskripsi</th></tr>"
            f"{rows}</table>"
            "<p class='sub'>token yang bayar boost = perhatian, bukan kualitas. "
            "Discovery saja — tetap lewat gate + veto sebelum paper.</p></details>"
        )
    metas = (dex.get("metas") or {}).get("metas") or []
    if metas:
        rows = "".join(
            f"<tr><td>{e(str(m.get('name') or '?'))}</td>"
            f"<td class='n'>${float(m.get('marketCap') or 0):,.0f}</td>"
            f"<td class='n'>${float(m.get('volume') or 0):,.0f}</td>"
            f"<td class='n'>{float(m.get('chg_h24') or 0):+.1f}%</td>"
            f"<td class='n'>{(m.get('overlap') or 0)}</td></tr>"
            for m in metas
        )
        tabs += (
            f"<details><summary>Narrative ({len(metas)} meta)</summary>"
            "<table><tr><th>narasi</th><th>mcap</th><th>vol</th>"
            "<th>24j</th><th>irisan sinyal</th></tr>"
            f"{rows}</table>"
            "<p class='sub'>narasi panas (ala Narrative Labs) × token yang wallet jago beli. "
            "Irisan = perhatian ganda, bukan perintah entry.</p></details>"
        )
    return tabs


def _cur(page: str, route: str) -> str:
    return " aria-current='page'" if page == route else ""


_e = html.escape

def _card(title: str, body: str) -> str:
    import re as _re

    _tanpa_badge = _re.sub(r"<span[^>]*>.*?</span>", "", title)
    _polos = _re.sub(r"<[^>]+>", "", _tanpa_badge)
    _slug = _re.sub(r"[^a-z0-9]+", "-", _polos.lower()).strip("-")
    _judul = title if "<" in title else html.escape(title)
    return f"<section id='{_slug}'><h2>{_judul}</h2>{body}</section>"

def _ubin(items: list[tuple]) -> str:
    out = []
    for it in items:
        k, v = it[0], it[1]
        tone = f" data-tone='{it[2]}'" if len(it) > 2 and it[2] else ""
        out.append(f"<div class='tile'{tone}><p class='k'>{k}</p><p class='v'>{v}</p></div>")
    return "<div class='ubin'>" + "".join(out) + "</div>"

def _lencana(jenis: str, teks: str) -> str:
    return f"<span class='badge {jenis}'>{_e(teks)}</span>"

def _sumber(teks: str) -> str:
    return f"<p class='src'>sumber: {_e(teks)}</p>"

def _arti(teks: str) -> str:
    return f"<p class='arti'><b>Artinya:</b> {teks}</p>"

def _grup(judul: str, tanya: str) -> str:
    return f"<div class='grup'><h3>{_e(judul)}</h3><p>{_e(tanya)}</p></div>"


def _tab(nama: str, n: int, satuan: str) -> str:
    """Judul tab jujur: sebut 12 teratas bila dipotong."""
    potong = " — 12 teratas" if n > 12 else ""
    return f"{nama} ({n} {satuan}{potong})"


def _grup_badge(snap, page: str, judul: str, tanya: str) -> str:
    badge = _lencana(*_status_halaman(snap, page))
    return f"<div class='grup'><h3>{_e(judul)} {badge}</h3><p>{_e(tanya)}</p></div>"


def _ctx(snap):
    e = _e
    r = snap.get("risiko", {})
    led0 = snap.get("ledger", {})
    lp0 = snap.get("lp_paper", {})
    pp0 = snap.get("poly_paper", {})
    g0 = snap.get("gmgn", {})
    gstats = g0.get("stats") or [{}]
    gmgn_pnl = gstats[0].get("total_pnl_usd")
    gmgn_txt = f"{gmgn_pnl:+.2f} USD" if isinstance(gmgn_pnl, (int, float)) else "n/a"
    total_r = led0.get("total_r", 0) or 0
    mode = e(snap.get("mode", "?"))
    dibuat = e(str(snap.get("dibuat", "")))
    risiko = (
        f"risiko hari ini {r.get('hari_ini_r', 0):+}R / batas -{r.get('batas_rugi_r')} · "
        f"posisi {r.get('posisi_terbuka')}/{r.get('maks_posisi')}"
    )
    return {
        "r": r,
        "led0": led0,
        "lp0": lp0,
        "pp0": pp0,
        "g0": g0,
        "gmgn_txt": gmgn_txt,
        "total_r": total_r,
        "mode": mode,
        "dibuat": dibuat,
        "risiko": risiko,
    }


def _nav(page: str, dibuat: str) -> str:
    """Navigasi atas — dipakai SSR dan (statis) oleh frontend."""
    return (
        "<div class='topbar'><div class='topbar-dalam'>"
        f"<a class='nav nama' href='/'>War Room</a>"
        f"<a class='nav' href='/terminal'{_cur(page, 'terminal')}>Terminal</a>"
        f"<a class='nav' href='/uang'{_cur(page, 'uang')}>Uang</a>"
        f"<a class='nav' href='/bukti'{_cur(page, 'bukti')}>Bukti</a>"
        f"<a class='nav' href='/pasar'{_cur(page, 'pasar')}>Pasar</a>"
        f"<a class='nav' href='/proyek'{_cur(page, 'proyek')}>Proyek</a>"
        f"<span class='kanan'><span class='badge ok'>paper</span> "
        f"{dibuat} · <span id='t-jam-top'>—</span></span>"
        "</div></div>"
    )


def _sparkline(vals: list, *, w: int = 300, h: int = 38, warna: str = "var(--aksen2)") -> str:
    """SVG mini-kurva untuk kartu — murni presentasi, tanpa JS. Kosong bila < 2 titik."""
    angka = [float(v) for v in vals if isinstance(v, (int, float))]
    if len(angka) < 2:
        return ""
    lo, hi = min(angka), max(angka)
    span = (hi - lo) or 1.0
    pad, n = 3.0, len(angka)
    xy = [
        (pad + i * (w - 2 * pad) / (n - 1), h - pad - (v - lo) / span * (h - 2 * pad))
        for i, v in enumerate(angka)
    ]
    garis = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    area = f"{pad:.1f},{h - pad:.1f} {garis} {w - pad:.1f},{h - pad:.1f}"
    return (
        f"<svg class='spark-svg' viewBox='0 0 {w} {h}' preserveAspectRatio='none' "
        f"role='img' aria-hidden='true'>"
        f"<polygon points='{area}' fill='{warna}' opacity='0.08'/>"
        f"<polyline points='{garis}' fill='none' stroke='{warna}' stroke-width='1.5'/></svg>"
    )


def _bar_divergen(nama: str, v: float, maks: float, satuan: str = "") -> str:
    """Bar divergen (nol di tengah) untuk daftar nilai R/USD — murni presentasi."""
    lebar = (abs(v) / maks * 50.0) if maks else 0.0
    kiri = 50.0 - lebar if v < 0 else 50.0
    warna = "var(--ok)" if v >= 0 else "var(--fail)"
    return (
        f"<div class='bar'><span class='nm'>{html.escape(nama)}</span>"
        f"<span class='rel'><span class='isi' style='left:{kiri:.1f}%;width:{lebar:.1f}%;"
        f"background:{warna}'></span></span>"
        f"<span class='vl'>{v:+.2f}{satuan}</span></div>"
    )


def _minibar(v: float, maks: float) -> str:
    """Bar divergen mungil untuk sel tabel (baris aturan gate)."""
    lebar = (abs(v) / maks * 50.0) if maks else 0.0
    kiri = 50.0 - lebar if v < 0 else 50.0
    warna = "var(--ok)" if v >= 0 else "var(--fail)"
    return (
        f"<span class='minibar'><i style='left:{kiri:.1f}%;width:{lebar:.1f}%;"
        f"background:{warna}'></i></span>"
    )


def _hero(snap) -> str:
    """Hero Home — angka dinamis, jadi fragmen backend (bukan statis)."""
    c = _ctx(snap)
    mode, dibuat = c["mode"], c["dibuat"]
    lo0 = ((snap.get("pengukuran") or {}).get("lolos") or {})
    exp0, n0 = lo0.get("expectancy_r") or 0, lo0.get("n") or 0
    if exp0 > 0 and n0 >= 50:
        status_txt, status_nada = "STATUS: MENGHIJAU — tetap paper, belum live", "ok"
    elif exp0 < 0:
        status_txt, status_nada = "STATUS: BELUM TERBUKTI — jangan live", "fail"
    else:
        status_txt, status_nada = "STATUS: TUNGGU DATA", "warn"
    import datetime as _dt

    try:
        _ts = _dt.datetime.strptime(dibuat.replace(" WIB", ""), "%Y-%m-%d %H:%M:%S")
        _basi = int((_dt.datetime.now() - _ts).total_seconds() // 60)
        basi_txt = f" ({_basi} mnt lalu)" if _basi >= 0 else ""
    except Exception:
        basi_txt = ""
    total_r, gmgn_txt = c["total_r"], c["gmgn_txt"]
    pp0, lp0, risiko = c["pp0"], c["lp0"], c["risiko"]
    pts = (snap.get("equity") or {}).get("points") or []
    vals = [float(p.get("cum") or 0) for p in pts]
    spark = ""
    if len(vals) >= 2:
        warna = "var(--ok)" if vals[-1] >= 0 else "var(--fail)"
        spark = (
            "<div class='spark'><span class='spark-k'>kurva R kripto (warisan)</span>"
            f"{_sparkline(vals, warna=warna)}"
            f"<span class='spark-v {'ok' if vals[-1] >= 0 else 'down'}'>{vals[-1]:+.2f}R</span></div>"
        )
    return (
        "<header class='hero' id='top'>"
        f"<p class='kicker'>War Room · mode <b>{mode}</b> · "
        f"diperbarui {dibuat}{basi_txt} · layar segar tiap 60 dtk</p>"
        "<h1>Tiga proyek paper</h1>"
        f"<p class='statusline'>{_lencana(status_nada, status_txt)}</p>"
        + _ubin(
            [
                ("Kripto", f"{total_r:+.2f}R", "pass" if total_r > 0 else "fail" if total_r < 0 else ""),
                ("GMGN", gmgn_txt, "pass" if "+" in gmgn_txt else "fail" if "-" in gmgn_txt else ""),
                (
                    "Polymarket",
                    f"{float(pp0.get('total_pnl') or 0):+.2f} USD",
                    "pass"
                    if (pp0.get("total_pnl") or 0) > 0
                    else "fail"
                    if (pp0.get("total_pnl") or 0) < 0
                    else "",
                ),
            ]
        )
        + spark
        + f"<p class='rincian'>Kripto warisan (bukan hasil gate) · "
        f"LP ${float(lp0.get('capital') or 0):.0f} · {risiko}</p>"
        "</header>"
    )


def _kepala(snap, page):
    return _nav(page, _ctx(snap)["dibuat"]) + (_hero(snap) if page == "semua" else "")


def _status_halaman(snap, page) -> tuple[str, str]:
    """Badge status jujur per rute (kunci QA: tiap hero bawa status)."""
    if page == "bukti":
        lo = ((snap.get("pengukuran") or {}).get("lolos") or {})
        exp = lo.get("expectancy_r") or 0
        if exp > 0:
            return "ok", "TERUKUR: MENGHIJAU"
        if exp < 0:
            return "fail", "TERUKUR: BELUM TERBUKTI"
        return "tua", "TERUKUR: TUNGGU DATA"
    if page == "pasar":
        return "tua", "KONTEKS: BUKAN PERINTAH"
    if page == "terminal":
        return "ok", "GRAFIK LANGSUNG"
    if page == "uang":
        return "ok", "TERCATAT"
    if page == "proyek":
        return "tua", "PANTAU SEMUA MESIN"
    return "tua", "WAR ROOM"


def _blok(snap):
    e = _e
    c = _ctx(snap)
    r = c['r']
    lp0 = c['lp0']
    pp0 = c['pp0']
    # crypto
    blok: dict[str, str] = {}
    crypto = snap.get("bagian", {}).get("crypto")
    if isinstance(crypto, list):
        rows = "".join(
            f"<tr><td>{e(str(c.get('pair')))}</td><td class='n'>{c.get('price', 0):,.2f}</td>"
            f"<td class='n {'up' if (c.get('chg24h') or 0) >= 0 else 'down'}'>{c.get('chg24h', 0):+.2f}%</td>"
            f"<td class='n'>{c.get('funding', 0):+.4f}%</td>"
            f"<td class='n'>{c.get('taker')}</td><td class='n'>{c.get('quote_vol', 0):,.0f}</td></tr>"
            for c in crypto
            if "error" not in c
        )
        body = (
            "<table><tr><th>pair</th><th>harga</th><th>24j</th><th>funding</th><th>taker</th>"
            f"<th>vol $M</th></tr>{rows}</table>"
        )
    else:
        body = f"<p class='err'>{e(str(crypto))}</p>"
    # risiko & alokasi — tepat di bawah terminal, sebelum data pasar
    lp_usd = float(lp0.get("capital") or 0)
    pp_usd = float(pp0.get("balance") or 0)
    tot_usd = lp_usd + pp_usd
    if tot_usd > 0:
        lp_pct, pp_pct = lp_usd / tot_usd * 100, pp_usd / tot_usd * 100
        alokasi = (
            f"<p class='legenda'><span>LP Arc ${lp_usd:.0f} ({lp_pct:.0f}%)</span>"
            f"<span>Poly ${pp_usd:.0f} ({pp_pct:.0f}%)</span></p>"
        )
    else:
        alokasi = "<p class='sub'>belum ada modal paper terlacak</p>"
    ubin_risiko = _ubin(
        [
            ("ruang rugi", f"{r.get('sisa_ruang_r', '?')}R"),
            ("posisi", f"{r.get('posisi_terbuka', '?')}/{r.get('maks_posisi', '?')}"),
            ("batas", f"-{r.get('batas_rugi_r', '?')}R"),
        ]
    )
    risiko_body = f"{ubin_risiko}{alokasi}"
    kartu_risiko = _card("Risiko & alokasi", risiko_body + _sumber("risk gate + state paper"))
    blok["terminal"] = _TERMINAL
    from live_trading.pods import gmgn as _pod_gmgn
    from live_trading.pods import idx as _pod_idx
    from live_trading.pods import kripto as _pod_kripto
    from live_trading.pods import poly as _pod_poly

    for _nama, _mod in (
        ("pod_kripto", _pod_kripto),
        ("pod_idx", _pod_idx),
        ("pod_poly", _pod_poly),
        ("pod_gmgn", _pod_gmgn),
    ):
        try:
            lap = _mod.lead(snap)
            blok[_nama] = _pod_card(lap, (snap.get("pod_llm") or {}).get(_nama[4:]))
        except Exception as ex:  # noqa: BLE001
            blok[_nama] = _card(f"Pod {_nama}", f"<p class='sub'>pod error: {e(str(ex))}</p>")
    blok["risiko"] = kartu_risiko
    blok["crypto"] = _card(
        "Crypto — Binance perp",
        body + _arti("hijau belum tentu boleh entry — tunggu gate, lihat kartu Ukur."),
    )

    # idx
    idx = snap.get("bagian", {}).get("idx", {})
    if isinstance(idx, dict) and idx.get("rows"):
        cross = {str(c.get("kode")): c for c in (idx.get("cross_check") or []) if c.get("kode")}

        def selaras(kode: str) -> str:
            c = cross.get(str(kode))
            if not c:
                return "<td class='sub'>—</td><td class='sub'>n/a</td>"
            putusan = str(c.get("putusan"))
            kelas = "ok" if putusan == "sejalan" else "down" if putusan == "bertentangan" else "sub"
            ema = c.get("ema_state", "n/a")
            rsi = c.get("rsi14")
            rsi_txt = f"{rsi:.0f}" if isinstance(rsi, (int, float)) else "n/a"
            return f"<td>{e(ema)} · RSI {rsi_txt}</td><td class='{kelas}'>{e(putusan)}</td>"

        rows = "".join(
            f"<tr><td>{e(str(x.get('stock_code')))}</td><td>{e(str(x.get('bucket')))}</td>"
            f"<td class='n'>{_persen(x.get('wr_event'))}</td><td class='n'>{_persen(x.get('potential'))}</td>"
            f"{selaras(str(x.get('stock_code')))}</tr>"
            for x in idx["rows"]
        )
        q = idx.get("kuota") or {}
        body = (
            f"<p class='sub'>sumber {e(str(idx.get('sumber')))} · "
            f"kuota {q.get('remaining')}/{q.get('limit')} · kolom terakhir = cross-check TradingView</p>"
            "<table><tr><th>kode</th><th>bucket</th><th>WR</th><th>potensi</th>"
            f"<th>harga</th><th>selaras?</th></tr>{rows}</table>"
        )
    else:
        body = f"<p class='err'>{e(str(idx.get('error') if isinstance(idx, dict) else idx))}</p>"
    blok["idx"] = _card(
        "IDX — Arjum screener × TradingView",
        body + _arti("kandidat saham hasil screener — bukan rekomendasi beli."),
    )

    # forex
    fx = snap.get("bagian", {}).get("forex", {})
    if isinstance(fx, dict) and fx.get("close"):
        body = (
            f"<p class='big'>{fx.get('close')}</p><p class='sub'>{e(str(fx.get('symbol')))} · "
            f"EMA20 {fx.get('ema20')} · EMA50 {fx.get('ema50')} · ATR14 {fx.get('atr14')} "
            f"({fx.get('atr_pct')}%) · bias <b>{e(str(fx.get('bias')))}</b></p>"
        )
    else:
        body = f"<p class='err'>{e(str(fx.get('error') if isinstance(fx, dict) else fx))}</p>"
    blok["forex"] = _card("Forex — XAUUSD", body + _arti("konteks emas saja — tidak ada posisi forex."))

    # posisi
    pos = snap.get("posisi") or []
    if pos:
        rows = "".join(
            f"<tr><td>{e(str(p.get('pair')))}</td><td>{e(str(p.get('direction')))}</td>"
            f"<td class='n'>{p.get('entry')}</td><td class='n'>{p.get('stop')}</td>"
            f"<td class='n'>{p.get('tp1')}/{p.get('tp2')}</td><td>{e(str(p.get('status')))}</td></tr>"
            for p in pos
        )
        head = "<tr><th>pair</th><th>arah</th><th>entry</th><th>stop</th><th>TP1/TP2</th><th>status</th></tr>"
        body = f"<table>{head}{rows}</table>"
    else:
        lolos = [k for k in (snap.get("kandidat") or []) if k.get("allowed")]
        unik = {(k.get("pair"), k.get("direction")) for k in lolos}
        body = (
            "<p class='sub'>tidak ada posisi paper terbuka — "
            f"{len(lolos)} sinyal ({len(unik)} unik) lolos belum dibuka (eksekusi paper manual)</p>"
        )
    blok["posisi"] = _card("Posisi paper", body)

    # ledger
    led = snap.get("ledger", {})
    eq = (snap.get("equity") or {}).get("stats") or {}
    body = (
        f"<p class='big'>{led.get('total_r', 0):+.2f}R</p><p class='sub'>{led.get('trade')} trade · "
        f"winrate {led.get('winrate_pct')}% · expectancy {led.get('expectancy_r')} R/trade</p>"
    )
    if eq.get("trades"):
        pf = eq.get("profit_factor")
        body += (
            f"<p class='sub'>max drawdown {eq.get('max_drawdown_r')}R · "
            f"profit factor {pf if pf is not None else 'n/a'}</p>"
        )
        pts = (snap.get("equity") or {}).get("points") or []
        if pts:
            body += _grafik_ekuitas(pts[-20:])
            body += _bar_pair(pts)
            rows = "".join(
                f"<tr><td class='n'>#{p['i']}</td><td>{e(str(p.get('pair') or '—'))}</td>"
                f"<td class='n {'up' if (p.get('r') or 0) > 0 else 'down' if (p.get('r') or 0) < 0 else ''}'>"
                f"{p.get('r', 0):+.2f}R</td><td class='n'>{p.get('cum', 0):+.2f}R</td></tr>"
                for p in pts[-6:]
                if p.get("pair")
            )
            body += (
                "<table><tr><th class='n'>#</th><th>pair</th>"
                "<th class='n'>R</th><th class='n'>kum</th></tr>"
                f"{rows}</table>"
            )
    blok["ledger"] = _card(
        "Ledger (warisan)",
        body
        + _sumber("crypto_equity.jsonl (paper executor)")
        + _arti("angka ini warisan, bukan hasil gate — jangan dipakai menilai sistem."),
    )

    # gmgn
    g = snap.get("gmgn", {})
    if g.get("tersedia"):
        semua = g.get("stats") or [{}]
        polis = []
        for st in semua[:2]:
            pf = st.get("profit_factor")
            wr = st.get("win_rate_pct")
            pnl = st.get("total_pnl_usd")
            polis.append(
                f"<p class='sub'><b>{e(str(st.get('policy', '?')))}</b> · "
                f"winrate {wr}% · PF {pf} · "
                f"<span class='{'up' if (pnl or 0) >= 0 else 'down'}'>{pnl} USD</span> · "
                f"{st.get('trades', '?')} trade</p>"
            )
        body = (
            f"<p class='sub'>profil {e(str(g.get('profil')))} · sampel {g.get('sampel')}</p>"
            + "".join(polis)
            + _radar_tabs(g.get("shadow") or [], g.get("lp_top") or [], snap.get("bagian", {}).get("dex"))
            + f"<p class='sub'>{e(str(g.get('log_terakhir', '')))}</p>"
        )
    else:
        body = "<p class='sub'>state GMGN belum ada</p>"
    blok["gmgn"] = _card(
        "GMGN (paper)",
        body + _arti("kedua policy paper masih merah — jangan live sebelum hijau."),
    )

    # radar rantai — LOKAL (recreate 6 Okt; dulu SSH ke VM Azure)
    rd = snap.get("radar", {})
    um = rd.get("umur_mnt")
    if rd.get("tersedia"):
        chains = "".join(
            f"<tr><td>{e(str(c.get('chain')))}</td><td>{e(str(c.get('window')))}</td>"
            f"<td class='n'>{c.get('hp')}</td><td class='n'>{c.get('avg_vl')}</td>"
            f"<td class='n'>{c.get('age')} hari</td></tr>"
            for c in (rd.get("chains") or [])
        )
        body = (
            f"<p class='big'>{e(str(rd.get('arc_window')))}</p>"
            f"<p class='sub'>arc {rd.get('arc_age')} hari · HP {rd.get('arc_hp')} · "
            f"avg V/L {rd.get('arc_avg_vl')} · {rd.get('n_chain')} chain terpantau</p>"
            "<table><tr><th>chain</th><th>window</th><th class='n'>HP</th>"
            f"<th class='n'>V/L</th><th class='n'>umur</th></tr>{chains}</table>"
        )
        if isinstance(um, (int, float)):
            body += f"<p class='sub'>radar lokal terakhir jalan {int(um)} mnt lalu</p>"
    else:
        body = f"<p class='sub'>radar n/a ({e(str(rd.get('error', 'tidak tersedia')))})</p>"
    if not rd.get("tersedia"):
        bd = _lencana("mati", "n/a")
    elif isinstance(um, (int, float)) and um > _RADAR_SEGAR_MNT:
        bd = _lencana("warn", f"basi {int(um)}m")
    elif isinstance(um, (int, float)):
        bd = _lencana("ok", f"segar {int(um)}m")
    else:
        bd = _lencana("ok", "lokal")
    blok["radar"] = _card(
        f"Radar Rantai {bd}",
        body
        + _sumber("radar lokal dijalankan di host ini (`lt radar-update`) — bukan lagi SSH Azure")
        + _arti(
        f"window Arc {rd.get('arc_window')} — "
        + (
            "lihat kartu LP."
            if any(
                (x.get("verdict") == "KELUAR")
                for x in ((snap.get("lp_paper") or {}).get("posisi") or [])
            )
            else "tidak perlu tindakan."
        )
    ),
    )

    # paper LP lokal (baca-saja)
    lp = snap.get("lp_paper", {})
    if lp.get("tersedia") and lp.get("posisi"):
        rows = "".join(
            f"<tr><td>{e(str(x.get('symbol')))}</td><td class='n'>${float(x.get('notional') or 0):,.2f}</td>"
            f"<td class='n'>V/L {x.get('vl_now', x.get('vl'))}</td>"
            f"<td class='n'>{_lencana_lp(x.get('verdict'))}</td></tr>"
            for x in lp["posisi"]
        )
        body = (
            f"<p class='sub'>paper ${float(lp.get('capital') or 0):,.2f}</p>"
            "<p class='sub'>asumsi tier 1% · fee estimasi, bukan hasil</p>"
            f"<table><tr><th>pool</th><th>notional</th><th>V/L</th><th>exit</th></tr>{rows}</table>"
        )
        if lp.get("mark_terakhir"):
            mark_txt = e(str(lp['mark_terakhir']).replace(chr(42), "").replace("$-", "-$")[:120])
            body += f"<p class='sub'>mark: {mark_txt}</p>"
    else:
        body = "<p class='sub'>belum ada posisi paper LP</p>"
    bd = _lencana("ok", "paper") if lp.get("tersedia") else _lencana("mati", "n/a")
    blok["lp"] = _card(
        "LP Arc",
        body
        + _sumber("lp_paper_state.json + cron mark 00:05 WIB")
        + _arti(_arti_lp(lp)),
    )

    # paper polymarket (baca-saja)
    pp = snap.get("poly_paper", {})
    upd = str(pp.get("updated") or "")
    basi = bool(
        upd[:10] and str(snap.get("dibuat", ""))[:10] and upd[:10] != str(snap.get("dibuat", ""))[:10]
    )
    if pp.get("tersedia"):
        rows = "".join(
            (
                f"<tr><td>{e(str(a.get('nama')))}</td>"
                f"<td class='n'>{a.get('balance')}</td>"
                f"<td class='n {'ok' if (a.get('pnl') or 0) >= 0 else 'down'}'>{a.get('pnl')}</td>"
                f"<td class='n'>{a.get('entries')}</td>"
                f"<td class='n'>{a.get('wins')}W/{a.get('losses')}L</td></tr>"
            )
            if a.get("tersedia")
            else f"<tr><td>{e(str(a.get('nama')))}</td><td colspan='4'>n/a</td></tr>"
            for a in pp.get("arms", [])
        )
        tp = pp.get("total_pnl", 0)
        arms_hidup = [a for a in pp.get("arms", []) if a.get("tersedia")]
        maks_pnl = max((abs(float(a.get("pnl") or 0)) for a in arms_hidup), default=1.0) or 1.0
        bars = "".join(
            _bar_divergen(str(a.get("nama")), float(a.get("pnl") or 0), maks_pnl, " USD")
            for a in arms_hidup
        )
        body = (
            f"<p class='big'>gabungan {tp:+.2f} USD</p>"
            + bars
            + f"<table><tr><th>arm</th><th>saldo</th><th>PnL</th><th>entry</th>"
            f"<th>W/L</th></tr>{rows}</table>"
            + f"<p class='sub'>update {e(str(pp.get('updated') or ''))[:16]} WIB</p>"
        )
    else:
        body = "<p class='sub'>ringkasan mirror tidak terbaca</p>"
    bd = (
        _lencana("tua", f"basi {upd[:10]}")
        if basi
        else (_lencana("ok", "segar") if pp.get("tersedia") else _lencana("mati", "n/a"))
    )
    info_arm = {str(a.get("nama", "")).split()[0]: a for a in pp.get("arms", [])}
    b, d = info_arm.get("B", {}), info_arm.get("D", {})
    arti_poly = (
        f"arm B {b.get('pnl', '?')} USD ({b.get('wins', '?')}W/{b.get('losses', '?')}L) "
        f"dan D {d.get('pnl', '?')} USD ({d.get('wins', '?')}W/{d.get('losses', '?')}L) — "
        "beli favorit 0,70-0,95, bukan ekor murah."
        if b or d
        else "belum ada data arm — mirror belum terbaca."
    )
    blok["poly"] = _card(
        f"Polymarket {bd}",
        body
        + _sumber("4 arm /var/lib/poly-paper*/execution-paper-shadow-summary.json (mirror hidup)")
        + _arti(arti_poly),
    )

    # kandidat & pengukuran gate
    kand = snap.get("kandidat") or []
    ukur = snap.get("pengukuran") or {}
    bagian = []
    if kand:
        tampil = list(reversed(kand))[:12]
        rows = "".join(
            f"<tr><td>{e(str(k.get('pair')))}</td><td>{e(str(k.get('direction')))}</td>"
            f"<td class='n'>{fharga(k.get('entry'))}</td><td class='n'>{fharga(k.get('sl'))}</td>"
            f"<td class='{'ok' if k.get('allowed') else 'down'}'>"
            f"{'LOLOS' if k.get('allowed') else 'TOLAK'}</td>"
            f"<td>{e(str(k.get('tier')))}</td></tr>"
            for k in tampil
        )
        bagian.append(
            f"<p class='sub'>{len(tampil)} terbaru dari {ukur.get('total_tercatat', len(kand))} tercatat</p>"
            "<table><tr><th>pair</th><th>arah</th><th>entry</th><th>SL</th><th>gate</th>"
            f"<th>tier</th></tr>{rows}</table>"
        )
    else:
        bagian.append("<p class='sub'>belum ada kandidat tercatat</p>")

    if ukur and "error" not in ukur:
        lolos, ditolak = ukur.get("lolos", {}), ukur.get("ditolak_bayangan", {})
        bagian.append(
            f"<p class='sub'>tercatat {ukur.get('total_tercatat')} · dinilai {ukur.get('dinilai')}</p>"
        )
        if lolos.get("n") or ditolak.get("n"):

            def _exp(d: dict) -> str:
                v = d.get("expectancy_r")
                if v is None:
                    return "n/a"
                cls = "up" if v > 0 else "down" if v < 0 else ""
                return f"<span class='{cls}'>{v:+.2f}R</span>"

            def _nada(d: dict) -> str:
                v = d.get("expectancy_r")
                return "pass" if (v or 0) > 0 else "fail" if (v or 0) < 0 else ""

            bagian.append(
                _ubin(
                    [
                        ("lolos exp", _exp(lolos) + f" · n={lolos.get('n', 0)}", _nada(lolos)),
                        (
                            "ditolak exp",
                            _exp(ditolak) + f" · n={ditolak.get('n', 0)}",
                            _nada(ditolak),
                        ),
                    ]
                )
            )
        for _kat, _d in (("LOLOS", lolos), ("DITOLAK bayangan", ditolak)):
            if _d.get("n"):
                _sel = _d.get("tp1", 0) + _d.get("sl", 0)
                _tot = _d.get("total_r", 0)
                bagian.append(
                    f"<p class='sub'>{_kat} — winrate {_d['winrate']}% · "
                    f"{_sel}/{_d['n']} selesai · total {_tot:+.2f}R</p>"
                )
        aturan = ukur.get("per_aturan") or {}
        if aturan:
            maks_r = max(
                (abs(float(v.get("expectancy_r") or 0)) for v in aturan.values()), default=1.0
            ) or 1.0
            bagian.append(
                "".join(
                    _bar_divergen(rule, float(v["expectancy_r"]), maks_r, "R")
                    for rule, v in sorted(aturan.items(), key=lambda kv: kv[1]["expectancy_r"])
                )
            )
            baris = "".join(
                f"<tr><td>{e(rule)}</td><td class='n'>{v['n']}</td>"
                f"<td class='n {'up' if v['expectancy_r'] < 0 else 'down'}'>{v['expectancy_r']:+.2f}R</td>"
                f"<td>{e(v['putusan'])}</td></tr>"
                for rule, v in sorted(aturan.items(), key=lambda kv: kv[1]["expectancy_r"])
            )
            bagian.append(
                f"<table><tr><th>aturan</th><th>n</th><th>bayangan</th><th>putusan</th></tr>{baris}</table>"
            )
        pag = ukur.get("per_agent") or {}
        if pag:
            prow = "".join(
                f"<tr><td>{e(nama)}</td><td class='n'>{a.get('n', 0)}</td>"
                f"<td class='n'>{a.get('avg_setuju_r')}</td>"
                f"<td class='n'>{a.get('avg_tak_setuju_r')}</td>"
                f"<td>{e(str(a.get('putusan', '')))}</td></tr>"
                for nama, a in sorted(pag.items())
            )
            bagian.append(
                "<table><tr><th>agent</th><th>n</th><th>setuju</th>"
                f"<th>tak-setuju</th><th>status</th></tr>{prow}</table>"
            )
        bagian.append(
            "<p class='sub'>'berguna' = kandidat yang ditolak aturan itu memang cenderung rugi. "
            "'merugikan' = aturan itu membuang kandidat yang justru untung.</p>"
        )
    elif ukur:
        bagian.append(f"<p class='err'>{e(str(ukur.get('error')))}</p>")
    exp_u = ((ukur.get("lolos") or {}).get("expectancy_r") or 0) if isinstance(ukur, dict) else 0
    bagian.append(
        _arti(
            "forward menghijau (pengukuran, bukan profit) — sistem belum terbukti, sabar kumpulkan sampel."
            if exp_u > 0
            else "forward masih merah — sistem belum terbukti, sabar kumpulkan sampel."
        )
    )
    blok["ukur"] = _card("Kandidat & pengukuran gate", "".join(bagian))

    # backtest: pertanyaan "apakah gate berguna" pada sampel besar
    bt = snap.get("backtest")
    if bt:

        def _r(v: Any) -> str:
            if v is None:
                return "n/a"
            cls = "up" if v > 0 else "down" if v < 0 else ""
            return f"<span class='{cls}'>{v:+.2f}R</span>"

        baris = "".join(
            f"<tr><td>{e(k)}</td><td class='n'>{v['n']}</td>"
            f"<td class='n'>{_r(v['bersih'])}</td><td>{e(v['putusan'])}</td></tr>"
            for k, v in sorted((bt.get("per_aturan") or {}).items())
        )
        bl = bt.get("beda_lolos") or {}
        aturan_bt = bt.get("per_aturan") or {}
        maks_bt = (
            max((abs(float(v.get("bersih") or 0)) for v in aturan_bt.values()), default=1.0) or 1.0
        )
        bars_bt = "".join(
            _bar_divergen(k, float(v["bersih"]), maks_bt, "R")
            for k, v in sorted(aturan_bt.items(), key=lambda kv: kv[1]["bersih"])
        )

        def nada(v: Any) -> str:
            return "pass" if (v or 0) > 0 else "fail" if (v or 0) < 0 else ""

        tiles = [
            ("lolos bersih", _r(bt.get("lolos_bersih")), nada(bt.get("lolos_bersih"))),
            (
                "keyakinan",
                f"{bt.get('lolos_keyakinan')} (t={(bt.get('beda_lolos') or {}).get('t', '?')})",
                "warn",
            ),
            ("tanpa gate", _r(bt.get("semua_bersih")), nada(bt.get("semua_bersih"))),
            ("terisi", f"{bt.get('terisi_pct')}%", ""),
        ]
        uji = " · ".join(
            f"{e(k)} t={v['t']}"
            for k, v in sorted((bt.get("beda_aturan") or {}).items())
            if v.get("t") is not None
        )
        badan = (
            f"{_ubin(tiles)}"
            f"<p class='sub'>setelah biaya · {bt['lolos_terisi']} posisi · sampel {bt['n']} kandidat</p>"
            f"<p>masuk di harga pasar (tanpa menunggu POI): "
            f"{_r(bt.get('masuk_pasar_bersih'))} · {bt.get('masuk_pasar_terisi')} posisi</p>"
            f"{bars_bt}"
            f"<table><tr><th>aturan (penolak sendiri)</th><th class='n'>n</th>"
            f"<th class='n'>bersih</th><th>putusan</th></tr>{baris}</table>"
            "<details><summary>metodologi + semua uji</summary>"
            f"<p class='dim'>biaya {bt.get('biaya_bps', 5):.0f} bps/sisi (taker). Edge kotor tanpa "
            f"biaya: {_r(bt.get('kotor_semua'))} — selisihnya yang dimakan biaya. Di bursa "
            f"maker 0% (MEXC futures) biaya mendekati nol, jadi angka gate di atas adalah "
            f"sisi paling pesimis.</p>"
            f"<p><b>Uji klaster (satu pair = satu unit)</b>: beda lolos vs ditolak "
            f"{bt.get('klaster_r')}R · t={bt.get('klaster_t')} · n={bt.get('klaster_n_pair')} "
            f"pair. Ini uji yang dipakai untuk menyimpulkan, karena kandidat dalam satu pair "
            f"saling berkorelasi.</p>"
            f"<p><b>Edge aliran kandidat</b>: {bt.get('nol_r')}R · t={bt.get('nol_t')} → "
            f"{e(str(bt.get('nol_keterangan')))}</p>"
            f"<p><b>Uji beda lolos vs ditolak (per kandidat)</b>: {bl.get('beda_r')}R · "
            f"t={bl.get('t')} → {e(str(bl.get('keterangan')))}</p>"
            f"<p class='dim'>t per aturan: {uji or 'n/a'}. Tabel di atas membandingkan "
            f"penolak-sendiri terhadap sisanya dan bisa menyesatkan; uji beda yang dipakai "
            f"untuk menyimpulkan. Angka ini belum dasar mengubah ambang.</p>"
            "</details>"
        )
        blok["backtest"] = _card(
            "Backtest gate (historis)",
            badan + _arti("gate belum terbukti nambah cuan — jangan ubah ambang."),
        )

    # hyperliquid — konteks
    hl = snap.get("bagian", {}).get("hyperliquid") or {}
    if hl.get("total_perp"):
        rows = "".join(
            f"<tr><td>{e(str(c.get('coin')))}</td><td class='n'>{c.get('mark', 0):,.4f}</td>"
            f"<td class='n'>${c.get('oi_usd', 0) / 1e6:,.1f}M</td>"
            f"<td class='n {'up' if (c.get('funding_hourly_pct') or 0) >= 0 else 'down'}'>"
            f"{c.get('funding_hourly_pct', 0):+.4f}%</td></tr>"
            for c in hl.get("top_by_oi", [])
        )
        body = (
            f"<p class='sub'>{hl.get('total_perp')} perp aktif · konteks, bukan gate</p>"
            f"<table><tr><th>coin</th><th>mark</th><th>OI</th><th>funding/jam</th></tr>{rows}</table>"
        )
    else:
        body = f"<p class='err'>{e(str(hl.get('error', 'belum ada data')))}</p>"
    blok["hl"] = _card(
        "Hyperliquid — positioning",
        body + _arti("posisi pasar futures — konteks, bukan gate."),
    )

    # IDX screener via TradingView
    tv = snap.get("bagian", {}).get("idx_tv") or {}
    if tv.get("rows"):
        movers = sorted(tv["rows"], key=lambda x: x.get("change_pct") or 0)
        naik, turun = movers[-1], movers[0]

        def _tile_mover(x: dict, label: str) -> str:
            v = x.get("change_pct") or 0
            cls = "up" if v >= 0 else "down"
            return (
                f"<div class='tile'><p class='k'>{label} {e(str(x.get('ticker')))}</p>"
                f"<p class='v {cls}'>{v:+.2f}%</p></div>"
            )

        movers_html = (
            "<div class='ubin'>" + _tile_mover(naik, "top naik") + _tile_mover(turun, "top turun") + "</div>"
        )
        rows = "".join(
            f"<tr><td>{e(str(x.get('ticker')))}</td><td class='n'>{x.get('close', 0):,.0f}</td>"
            f"<td class='n {'up' if (x.get('change_pct') or 0) >= 0 else 'down'}'>"
            f"{x.get('change_pct', 0):+.2f}%</td><td class='n'>{x.get('rsi14') or 0:,.1f}</td>"
            f"<td>{e(str(x.get('ema_state')))}</td></tr>"
            for x in tv["rows"]
        )
        body = (
            movers_html + "<p class='sub'>TradingView · 'EMA naik' = keadaan, bukan cross baru</p>"
            f"<table><tr><th>ticker</th><th>harga</th><th>chg</th><th>RSI14</th><th>EMA</th></tr>{rows}</table>"
        )
    else:
        body = f"<p class='err'>{e(str(tv.get('error', 'belum ada data')))}</p>"
    blok["idx_tv"] = _card(
        "IDX — screener TradingView",
        body + _arti("konfirmasi silang untuk screener Arjum di atas."),
    )

    # IDX 616 mirror (baca-saja dari Tencent)
    m616 = snap.get("bagian", {}).get("idx616") or {}
    if m616.get("error"):
        blok["idx616"] = _card("IDX 616 mirror", f"<p class='err'>{e(str(m616['error']))}</p>")
    elif "terbuka" in m616:
        buka = m616.get("terbuka") or []
        tutup = m616.get("tutup") or []
        setup_rows = "".join(
            f"<tr><td>{e(str(k))}</td><td class='n'>{v.get('n', 0)}</td>"
            f"<td class='n {'up' if (v.get('r') or 0) >= 0 else 'down'}'>"
            f"{(v.get('r') or 0):+.2f}R</td></tr>"
            for k, v in sorted(m616.get("per_setup", {}).items())
        )
        tutup_r = [(t.get("ticker"), float(t.get("net_r") or 0)) for t in (tutup or [])]
        tot_r = sum(v[1] for v in tutup_r)
        if tutup_r and tot_r > 0:
            top_k, top_r = max(tutup_r, key=lambda kv: kv[1])
            share = top_r / tot_r * 100
            kons = f"konsentrasi: {e(str(top_k))} {top_r:+.2f}R ({share:.0f}% dari total)."
        elif tutup_r:
            kons = (
                f"konsentrasi: {len(tutup_r)} tutup {tot_r:+.2f}R "
                "(sampel kecil, belum ada konsentrasi)."
            )
        else:
            kons = "konsentrasi: belum ada data tutup."
        unik: dict[tuple, dict] = {}
        for x in buka:
            unik[(x.get("ticker"), x.get("setup"), x.get("direction"))] = x
        buka_rows = "".join(
            f"<tr><td>{e(str(x.get('ticker') or '?'))}</td>"
            f"<td>{e(str(x.get('setup') or ''))}</td>"
            f"<td>{e(str(x.get('direction') or ''))}</td>"
            f"<td class='n'>{x.get('entry_low', '?')}</td>"
            f"<td class='n'>{x.get('sl', '?')}</td>"
            f"<td class='n'>{x.get('tp1', '?')}</td></tr>"
            for x in list(unik.values())
        )
        tutup_rows = "".join(
            f"<tr><td>{e(str(x.get('ticker') or '?'))}</td>"
            f"<td>{e(str(x.get('result') or '?'))}</td>"
            f"<td class='n {'up' if (x.get('net_r') or 0) >= 0 else 'down'}'>"
            f"{(x.get('net_r') or 0):+.2f}R</td></tr>"
            for x in tutup[-8:]
        )
        body616 = (
            (f"<table><tr><th>setup</th><th>n</th><th>R</th></tr>{setup_rows}</table>" if setup_rows else "")
            + f"<details open><summary>Sinyal terbuka ({len(unik)} unik / {len(buka)} event)</summary>"
            f"<table><tr><th>ticker</th><th>setup</th><th>arah</th><th>entry</th><th>SL</th><th>TP1</th></tr>"
            f"{buka_rows}</table></details>" + f"<p class='sub'>{kons}</p>"
            + (
                f"<details><summary>Baru tutup ({len(tutup)})</summary>"
                f"<table><tr><th>ticker</th><th>hasil</th><th>R</th></tr>{tutup_rows}</table></details>"
                if tutup_rows else ""
            )
        )
        blok["idx616"] = _card(
            "IDX 616 mirror",
            body616
            + _sumber(
                "43.155.219.37/idx616/api (baca-saja, diambil "
                + e(str(m616.get("diambil", "?"))) + " WIB)"
                + (
                    f" — ⚠️ dari cache {m616.get('cache_umur_mnt')} menit, "
                    f"Tencent tak terjangkau ({e(str(m616.get('peringatan', '?')))})"
                    if m616.get("dari_cache") else ""
                )
            )
            + _arti(
                f"mirror IDX Tencent — {len(tutup or [])} tutup "
                f"{sum(float(t.get('net_r') or 0) for t in (tutup or [])):+.2f}R "
                f"(cermin {e(str(m616.get('diambil', '?')))} WIB) — tampilkan, bukan eksekusi."
            ),
        )

    return blok


def _rakit(snap, page="semua"):
    """Susun body satu halaman dari fragmen (dipakai SSR + daftar fragmen)."""
    e = _e
    blok = _blok(snap)
    tldr = "".join(f"<li>{e(teks)}</li>" for teks, _nada in _ringkas(snap))
    urutan = [
        ("tldr", _card("Ringkasan 10 detik", f"<ul class='tldr'>{tldr}</ul>")),
        ("terminal", None),
        ("pod_kripto", None),
        ("uang", _grup("Uang", "Ke mana perginya uang paper?")),
        ("ledger", None),
        ("posisi", None),
        ("risiko", None),
        ("bukti", _grup("Bukti", "Apakah sistemnya terbukti? Jawaban jujur di sini.")),
        ("ukur", None),
        ("backtest", None),
        ("pasar", _grup("Pasar", "Kondisi lapangan — konteks, bukan perintah entry.")),
        ("crypto", None),
        ("hl", None),
        ("idx", None),
        ("idx_tv", None),
        ("idx616", None),
        ("pod_idx", None),
        ("forex", None),
        ("proyek", _grup("Proyek", "Mesin lain yang jalan paper — semua baca-saja.")),
        ("radar", None),
        ("lp", None),
        ("poly", None),
        ("gmgn", None),
        ("pod_poly", None),
        ("pod_gmgn", None),
    ]
    # Multipage: tiap rute hanya merakit blok grupnya (sumber snapshot sama).
    halaman: dict[str, tuple[str, list[str]]] = {
        "semua": ("War Room", [k for k, _c in urutan]),
        "terminal": ("Terminal", ["terminal", "pod_kripto"]),
        "uang": ("Uang", ["uang", "ledger", "posisi", "risiko"]),
        "bukti": ("Bukti", ["bukti", "ukur", "backtest"]),
        "pasar": ("Pasar", ["pasar", "crypto", "hl", "idx", "idx_tv", "idx616", "pod_idx", "forex"]),
        "proyek": ("Proyek", ["radar", "lp", "poly", "pod_poly", "gmgn", "pod_gmgn"]),
    }
    judul, kunci = halaman.get(page, halaman["semua"])
    pilih = {k: (c if c is not None else blok.get(k, "")) for k, c in urutan if k in kunci}
    out = "".join(pilih[k] for k in kunci)
    if page not in ("semua",):
        badge = _lencana(*_status_halaman(snap, page))
        out = f"<header class='hero slim'><h1>{e(judul)}</h1>{badge}</header>" + out
    out += (
        f"<footer><p class='sub'>snapshot {e(snap.get('dibuat', ''))} · "
        "data dibangun ulang tiap 15 mnt</p><details><summary>Kamus singkat</summary><p class='sub'>"
        "R = kelipatan risiko per trade · warisan = trade lama, bukan hasil gate · "
        "gate = 6 aturan saring sinyal · HP = print paus · V/L = volume/likuiditas · "
        "shadow = hasil bayangan tanpa modal · exp = expectancy (rata2 R per trade) · "
        "tier = SKIP/STANDAR/PREMIUM (boleh entry atau tidak)</p></details></footer>"
    )
    return out


def _css() -> str:
    """CSS satu-satunya: frontend/assets/style.css (dipakai SSR + statis)."""
    try:
        return (_ASETS_DIR / "style.css").read_text(encoding="utf-8")
    except OSError:
        return ""


def render(snap, page="semua"):
    return _SHELL.format(css=_css(), header=_kepala(snap, page), body=_rakit(snap, page))


_SHELL = """<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>War Room</title><meta http-equiv="refresh" content="60">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap">
<style>{css}</style></head><body>{header}<div class="wrap">{body}</div></body></html>"""


def serve(settings: Settings | None = None) -> None:
    s = settings or get_settings()
    build_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:  # senyap di journal
            return

        def do_GET(self) -> None:  # noqa: N802
            seg = self.path.split("?")[0]
            if seg.startswith("/refresh"):
                with build_lock:
                    load_snapshot(s, force=True)
                dest = self.headers.get("Referer", "/")
                path_only = "/" + dest.split("/", 3)[-1] if "://" in dest else dest.split("?")[0]
                if not path_only.startswith(("/terminal", "/uang", "/bukti", "/pasar", "/proyek")):
                    path_only = "/"
                self.send_response(302)
                self.send_header("Location", path_only)
                self.end_headers()
                return
            if seg.startswith("/api/snapshot"):
                try:
                    raw = (s.state_dir / "snapshot.json").read_bytes()
                except OSError:
                    raw = b"{}"
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if seg.startswith("/api/klines"):
                import urllib.parse as _up

                q = _up.urlparse(self.path).query
                arg = _up.parse_qs(q)
                try:
                    raw = _klines(arg.get("pair", [""])[0].upper(), arg.get("tf", [""])[0])
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Cache-Control", "public, max-age=60")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except ValueError:
                    self.send_response(400)
                    self.end_headers()
                except OSError:
                    self.send_response(502)
                    self.end_headers()
                return
            if seg.startswith("/frag/"):
                nama = seg[len("/frag/") :]
                try:
                    snap = load_snapshot(s)
                    semua = fragments(snap)
                except OSError:
                    semua = {}
                if nama not in semua:
                    self.send_response(404)
                    self.end_headers()
                    return
                data = semua[nama].encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if seg.startswith("/assets/"):
                import mimetypes

                f = _ASETS_DIR / seg[len("/assets/") :]
                try:
                    data = f.resolve().read_bytes()
                    if _FRONTEND_DIR not in f.resolve().parents:
                        raise OSError("di luar frontend")
                except OSError:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    mimetypes.guess_type(str(f))[0] or "application/octet-stream",
                )
                self.send_header("Cache-Control", "public, max-age=300")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            rute = {
                "/": "index.html",
                "/terminal": "terminal.html",
                "/uang": "uang.html",
                "/bukti": "bukti.html",
                "/pasar": "pasar.html",
                "/proyek": "proyek.html",
            }
            nama_file = rute.get(seg, "index.html")
            try:
                data = (_FRONTEND_DIR / nama_file).read_bytes()
            except OSError:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    srv = ThreadingHTTPServer(("127.0.0.1", s.dashboard_port), Handler)
    print(f"War Room dashboard: http://127.0.0.1:{s.dashboard_port}", flush=True)
    srv.serve_forever()


def render_shell(snap: dict[str, Any]) -> str:
    """Alias untuk tes."""
    return render(snap)


_KLINES_CACHE: dict[str, tuple[float, bytes]] = {}
_KLINES_TTL = 60.0


def _klines(pair: str, tf: str) -> bytes:
    """Ambil klines Binance lewat server (browser user kadang diblokir Binance).

    Mengembalikan body JSON mentah. Raise ValueError untuk input jelek,
    OSError kalau kedua host Binance gagal.
    """
    import time as _t
    import urllib.request as _ur

    if not re.fullmatch(r"[A-Z0-9]{4,20}", pair or ""):
        raise ValueError("pair jelek")
    if tf not in ("15m", "1h", "4h", "1d"):
        raise ValueError("tf jelek")
    kunci = f"{pair}/{tf}"
    entri = _KLINES_CACHE.get(kunci)
    if entri and _t.time() - entri[0] < _KLINES_TTL:
        return entri[1]
    err: Exception | None = None
    for host in ("https://api.binance.com", "https://data-api.binance.vision"):
        try:
            req = _ur.Request(
                f"{host}/api/v3/klines?symbol={pair}&interval={tf}&limit=120",
                headers={"User-Agent": "war-room/1.0"},
            )
            with _ur.urlopen(req, timeout=10) as r:
                raw = r.read()
            json.loads(raw)
            _KLINES_CACHE[kunci] = (_t.time(), raw)
            return raw
        except Exception as exc:  # noqa: BLE001
            err = exc
    raise OSError(f"binance gagal: {err}")


def fragments(snap):
    """Backend API: semua fragmen HTML untuk frontend statis.

    Kunci = nama seksi blok + potongan rakitan (hero/tldr/grup/footer).
    Frontend mengambil yang dibutuhkannya per halaman via /frag/<nama>.
    """
    e = _e
    out = _blok(snap)
    tldr = "".join(f"<li>{e(teks)}</li>" for teks, _nada in _ringkas(snap))
    out["hero"] = _hero(snap)
    out["tldr"] = _card("Ringkasan 10 detik", f"<ul class='tldr'>{tldr}</ul>")
    out["g-uang"] = _grup_badge(snap, "uang", "Uang", "Ke mana perginya uang paper?")
    out["g-bukti"] = _grup_badge(snap, "bukti", "Bukti", "Apakah sistemnya terbukti? Jawaban jujur di sini.")
    out["g-pasar"] = _grup_badge(snap, "pasar", "Pasar", "Kondisi lapangan — konteks, bukan perintah entry.")
    out["g-proyek"] = _grup_badge(snap, "proyek", "Proyek", "Mesin lain yang jalan paper — semua baca-saja.")
    out["footer"] = (
        f"<footer><p class='sub'>snapshot {e(snap.get('dibuat', ''))} · "
        "data dibangun ulang tiap 15 mnt</p><details><summary>Kamus singkat</summary><p class='sub'>"
        "R = kelipatan risiko per trade · warisan = trade lama, bukan hasil gate · "
        "gate = 6 aturan saring sinyal · HP = print paus · V/L = volume/likuiditas · "
        "shadow = hasil bayangan tanpa modal · exp = expectancy (rata2 R per trade) · "
        "tier = SKIP/STANDAR/PREMIUM (boleh entry atau tidak)</p></details></footer>"
    )
    for daftar in FRAGMEN_HALAMAN.values():
        for nama in daftar:
            out.setdefault(nama, "")
    return out


FRAGMEN_HALAMAN = {
    "index": ["hero", "tldr", "g-uang", "ledger", "posisi", "risiko", "footer"],
    "terminal": ["terminal", "pod_kripto", "footer"],
    "uang": ["g-uang", "ledger", "posisi", "risiko", "footer"],
    "bukti": ["g-bukti", "ukur", "backtest", "footer"],
    "pasar": ["g-pasar", "crypto", "hl", "idx", "idx_tv", "idx616", "pod_idx", "forex", "footer"],
    "proyek": ["g-proyek", "radar", "lp", "poly", "pod_poly", "gmgn", "pod_gmgn", "footer"],
}
