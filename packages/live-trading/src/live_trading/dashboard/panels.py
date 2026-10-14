"""Panel data dashboard: radar, lp, poly, gmgn, snapshot."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import Settings, get_settings
from ..risk import RiskGate
from .format import MODEL_POD, _wib, e, log
from .html_parts import _arti, _card, _lencana, _sumber


def _pesan_error(exc: BaseException) -> str:
    """Pesan error yang SELALU informatif — jangan pernah hasilkan 'None'.

    Bug 14 Okt: _pesan_error(exc) -> "X: None" bila str(exc) kosong,
    sehingga bagian dashboard yang gagal tak bisa didiagnosis dari snapshot.
    """
    import traceback

    pesan = str(exc).strip() or repr(exc)
    tb = traceback.extract_tb(exc.__traceback__)
    if tb:
        lokasi = tb[-1]
        return f"{type(exc).__name__}: {pesan} ({lokasi.filename.split('/')[-1]}:{lokasi.lineno})"
    return f"{type(exc).__name__}: {pesan}"


GMGN_DIR = Path.home() / "gmgn-paper" / "state"


# Catatan path: modul ini sekarang di dashboard/, satu level lebih dalam dari
# dashboard.py semula -> parents[3], bukan parents[2].
_FRONTEND_DIR = (Path(__file__).resolve().parents[3] / "frontend").resolve()


_ASETS_DIR = _FRONTEND_DIR / "assets"


def _backtest_panel(settings: Any) -> dict[str, Any] | None:
    """Ringkas hasil backtest tersimpan — tanpa jaringan, hanya membaca berkas."""
    from .. import backtest

    rows = backtest.load_rows(settings, 300) or backtest.load_rows(settings, 150)
    if not rows:
        return None
    a = backtest.aggregate(rows, fee_per_sisi=backtest.FEE_PER_SISI_DEFAULT)
    b = backtest.bandingkan(rows, fee_per_sisi=backtest.FEE_PER_SISI_DEFAULT)
    kl = backtest.test_cluster(rows, fee_per_sisi=backtest.FEE_PER_SISI_DEFAULT)
    nol = backtest.test_cluster_null(rows, fee_per_sisi=backtest.FEE_PER_SISI_DEFAULT)
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
    """Panel paper LP lokal — baca lp_paper_state.json (arsip gmgn-scan)."""
    from pathlib import Path as _P

    p = _P(path or str(_P.home() / "live-trading" / "state" / "lp_paper_state.json"))
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"tersedia": False}
    pos = d.get("positions") or []
    mark = None
    try:
        # Jejak mark kini di state/lp_mark_terakhir.json (dulu lp_mark.log di gmgn-scan).
        mk = (p.parent / "lp_mark_terakhir.json").read_text(encoding="utf-8")
        mark = mk.strip().splitlines()[-1][:160] if mk.strip() else None
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
    total_balance = sum(float(a.get("balance") or 0) for a in hidup)
    return {
        "tersedia": bool(hidup),
        "arms": arms,
        "total_pnl": round(total_pnl, 4),
        "total_balance": round(total_balance, 4),
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
    log_file = GMGN_DIR / "cycle.log"
    if log_file.is_file():
        try:
            lines = log_file.read_text(encoding="utf-8", errors="replace").strip().splitlines()
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
            from ..collectors.crypto import CryptoCollector

            snap["bagian"]["crypto"] = CryptoCollector(s).digest()
        except Exception as exc:  # noqa: BLE001 — dashboard jangan mati karena satu bagian
            snap["bagian"]["crypto"] = {"error": _pesan_error(exc)}

        try:
            from ..collectors.idx import ArjumCollector

            col = ArjumCollector(s)
            scr = col.screener(limit=5)
            baris = (scr.get("rows") or [])[:5]
            cross = []
            try:
                from ..collectors.idx_check import gabungkan, tv_snapshot

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
            snap["bagian"]["idx"] = {"error": _pesan_error(exc)}

        try:
            from ..collectors.forex import ForexCollector

            snap["bagian"]["forex"] = ForexCollector(s).structure("60", 120)
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["forex"] = {"error": _pesan_error(exc)}

        try:
            from ..collectors import macro

            # Gerbang stand-down: event berdampak tinggi dalam 60 menit ke depan.
            snap["bagian"]["macro"] = macro.MacroCollector(s).snapshot(s.state_dir)
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["macro"] = {"error": _pesan_error(exc)}

        try:
            from ..collectors import news

            # Berita kripto (RSS publik, tanpa kuota). Judul + tautan saja.
            snap["bagian"]["news"] = news.snapshot(s)
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["news"] = {"error": _pesan_error(exc)}

        try:
            from ..collectors import hyperliquid

            snap["bagian"]["hyperliquid"] = hyperliquid.snapshot(s, top=5)
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["hyperliquid"] = {"error": _pesan_error(exc)}

        try:
            from ..collectors import idx_tv

            snap["bagian"]["idx_tv"] = idx_tv.summary(idx_tv.screen(uptrend_only=True, limit=5))
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["idx_tv"] = {"error": _pesan_error(exc)}

        try:
            # BSJP (beli sore jual pagi): peringkat kandidat tahan semalam, memakai filter
            # yang sudah diuji walk-forward (lihat signals/bsjp.py). SMA10 diambil dari arsip
            # tick Arjum (collectors/riwayat_idx.py) supaya TIDAK menambah panggilan kuota REST.
            # Angka net-nya BERSUMBER dari walk-forward Tencent, bukan hitungan ulang di sini —
            # `terverifikasi_di_warroom=False` dan catatan_kejujuran wajib ikut tampil.
            from ..collectors import riwayat_idx
            from ..signals import bsjp

            scr_rows = (snap["bagian"].get("idx") or {}).get("rows") or []
            tv_rows = (snap["bagian"].get("idx_tv") or {}).get("rows") or []
            # SMA10 hanya untuk ticker yang lolos gerbang harga dulu: menghemat kueri dan
            # tidak menarik riwayat emiten yang toh akan ditolak.
            calon = [str(r.get("ticker") or "").upper() for r in tv_rows if r.get("ticker")]
            riwayat: dict[str, dict] = {}
            try:
                if calon:
                    riwayat = {t: v.to_dict() for t, v in riwayat_idx.fetch_history(calon).items()}
            except Exception as exc:  # noqa: BLE001 — SMA10 opsional; BSJP tetap jalan tanpa itu
                log.warning("bsjp: riwayat SMA10 gagal: %s", exc)
            snap["bagian"]["bsjp"] = bsjp.rank(
                scr_rows, tv_rows, riwayat=riwayat
            ).to_dict()
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["bsjp"] = {"error": _pesan_error(exc)}

        try:
            from ..collectors import dexscreen

            gshadow = []
            try:
                gshadow = (_gmgn_panel().get("shadow") or [])[-15:]
            except Exception:  # noqa: BLE001 — shadow opsional
                gshadow = []
            snap["bagian"]["dex"] = dexscreen.snapshot(s.state_dir, gshadow)
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["dex"] = {"error": _pesan_error(exc)}

        try:
            from .. import lp_positions

            # Posisi LP nyata yang dicatat + kolam kandidat Solana (discovery).
            # Dua hal yang sengaja dipisah: `posisi` = uang betul-betul diparkir,
            # `kandidat` = layar pencarian. Mencampur keduanya = cara medsos mengelabui.
            from ..collectors import dexscreen

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
            snap["bagian"]["lp"] = {"error": _pesan_error(exc)}

        try:
            from ..collectors import idx616

            snap["bagian"]["idx616"] = idx616.snapshot(s.state_dir)
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["idx616"] = {"error": _pesan_error(exc)}

        try:
            from ..collectors import crypto as _crypto
            from ..collectors import overextended

            # Selalu disertai hasil uji edge-nya — label "overextended" saja tidak pernah cukup.
            snap["bagian"]["overextended"] = overextended.snapshot(
                _crypto.DEFAULT_PAIRS, s.state_dir
            )
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["overextended"] = {"error": _pesan_error(exc)}

        try:
            from ..collectors import bandarmologi
            from ..collectors.idx import ArjumCollector

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
            snap["bagian"]["bandarmologi"] = {"error": _pesan_error(exc)}

        try:
            from ..collectors import dexscreen, memecoin

            # Sumber memecoin (Pumpfun / DEX Solana / Robinhood). Label aslinya dipertahankan:
            # data mentah, bukan rekomendasi — tidak ada track record yang bisa diverifikasi.
            snap["bagian"]["memecoin"] = memecoin.skrining(
                s.state_dir, per_venue=5, ambil=dexscreen.cari_pool
            )
        except Exception as exc:  # noqa: BLE001
            snap["bagian"]["memecoin"] = {"error": _pesan_error(exc)}

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
        from .. import equity as _equity

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
    # `lp_paper` SENGAJA TIDAK ditulis ke snapshot.
    #
    # Temuan 10 Okt: kunci `lp_paper` dipakai DUA sumber dengan ARTI BERBEDA:
    #   - domain ini: POSISI arc LP dari `~/live-trading/state/lp_paper_state.json` (panel HTML laporan;
    #     dulu `~/gmgn-scan/`, dilepas 10 Okt)
    #   - adapter gmgn: KINERJA arm LP dari `~/gmgn-paper/state/sim_ledger.jsonl` (panel /lp UI)
    # Keduanya kind=`snapshot`, key=`lp_paper` — jadi saling MENIMPA. API memilih
    # `observed_at` terbaru, dan snapshot domain (irama 15 menit) hampir selalu lebih baru.
    # Begitu berkas state LP hilang (10 Okt), domain menulis
    # `{"tersedia": false}` yang **menimpa** kinerja nyata n=283 → panel vonis /lp buta
    # (17 kali pada 10 Okt). Laporan HTML domain tetap membaca lewat `_lp_panel()` sendiri.
    snap["poly_paper"] = _poly_panel()

    # Akurasi IDX per setup — dari ledger mesin (impor 6 Okt, beku). Lokal, tanpa jaringan,
    # jadi tetap tampil saat offline; jejak sumber dibaca dari berkas marker.
    try:
        from .. import idx_akurasi as _ia

        ak = _ia.summarize_accuracy(s.state_dir / "idx_ledger.db")
        marker_p = s.state_dir / "idx_ledger_sumber.json"
        if marker_p.is_file():
            try:
                ak["impor"] = json.loads(marker_p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                ak["impor"] = None
        snap["idx_akurasi"] = ak
    except Exception as exc:  # noqa: BLE001 — satu panel jangan menjatuhkan snapshot
        snap["idx_akurasi"] = {"tersedia": False, "alasan": _pesan_error(exc)}

    if use_network:
        snap["radar"] = _radar_panel(state_dir=s.state_dir)
    else:
        snap["radar"] = {"tersedia": False, "error": "offline"}

    # Per-market signal & accuracy engine (6 Okt): sinyal+entry setup khas tiap market,
    # akurasi+pakem satu standar. Lokal & offline-safe — tetap tampil saat jaringan mati.
    try:
        from .. import bandarmologi_skor as _bs
        from .. import pasar as _pasar

        snap["crypto_sinyal"] = _pasar.ringkas_crypto_sinyal(s.state_dir)
        snap["forex_sinyal"] = _pasar.ringkas_forex_sinyal(s.state_dir)
        snap["idx_sinyal"] = _pasar.ringkas_idx_sinyal(s.state_dir)
        snap["pasar_akurasi"] = _pasar.ringkas_akurasi_pasar(s.state_dir)
        # Skor bandarmologi (adopsi pola ihsgscreener): satu angka 0–100 per emiten,
        # komponennya diaudit. Butuh `bagian.bandarmologi` — ada hanya saat use_network.
        snap["bandarmologi_skor"] = _bs.bandarmologi_score(snap.get("bagian") or {})
        # Dompet paper Rp 10 juta per market (7 Okt): ukuran yang bisa dibandingkan
        # antar-market — R tidak bisa dibandingkan, rupiah bisa.
        from .. import dompet as _dompet

        snap["dompet"] = _dompet.summarize_all_wallets(s.state_dir)
        # Verifikasi silang LP vs API publik (jawaban "data kita vs internet live").
        # Berat (3 panggilan HTTP/pool) → hanya saat use_network, dan gagal = ditandai.
        if use_network:
            from .. import lp_verification as _lpv

            try:
                snap["lp_verifikasi"] = _lpv.pool_contoh()
            except Exception as exc:  # noqa: BLE001 — verifikasi opsional
                snap["lp_verifikasi"] = {"tersedia": False, "alasan": _pesan_error(exc)}
    except Exception as exc:  # noqa: BLE001 — satu panel jangan menjatuhkan snapshot
        kosong = {"tersedia": False, "alasan": _pesan_error(exc)}
        snap["crypto_sinyal"] = dict(kosong)
        snap["forex_sinyal"] = dict(kosong)
        snap["idx_sinyal"] = dict(kosong)
        snap["pasar_akurasi"] = dict(kosong)
        snap["bandarmologi_skor"] = dict(kosong)
        snap["dompet"] = dict(kosong)
        snap["lp_verifikasi"] = dict(kosong)

    # kandidat & pengukuran (berkas; pengukuran butuh jaringan untuk melacak hasil)
    try:
        from .. import measure

        snap["kandidat"] = measure.load_verdicts(s)[-8:]
        if use_network:
            rep = measure.report(s)
            snap["pengukuran"] = {k: v for k, v in rep.items() if k != "rows"}
    except Exception as exc:  # noqa: BLE001 — dashboard jangan mati karena satu bagian
        snap["kandidat"] = []
        snap["pengukuran"] = {"error": _pesan_error(exc)}

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

            snap["pod_llm"] = _nilai.evaluate_all(
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


