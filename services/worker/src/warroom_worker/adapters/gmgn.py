"""Adapter GMGN (baca-saja) — P4-T4.

Sumber: ``~/gmgn-paper/state`` (lokal) dan **state radar lokal**
(``~/live-trading/state/radar_state.json``, hasil `lt radar-update`). Tidak ada SSH,
tidak ada perubahan apa pun di host lain.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from warroom_worker.adapters.io import baca_json, ringkas_dir

__all__ = ["gmgn_ringkas", "radar_ringkas"]

GMGN_STATE = "~/gmgn-paper/state"
RADAR_STATE = "~/live-trading/state/radar_state.json"
LP_MARK_STATE = "~/live-trading/state/lp_mark_terakhir.json"


def gmgn_ringkas(state_dir: str | None = None) -> dict[str, Any]:
    """Ringkasan state GMGN paper: berkas, ukuran, umur. Gagal → status, bukan nol."""
    d = Path(state_dir or GMGN_STATE).expanduser()
    if not d.exists():
        return {"status": "tidak-ada", "dir": str(d)}
    ringkas = ringkas_dir(d, pakai_sudo=False)
    berkas: list[dict[str, Any]] = []
    try:
        for f in sorted(d.glob("*")):
            if f.is_file():
                st = f.stat()
                berkas.append({"nama": f.name, "bytes": st.st_size, "mtime": st.st_mtime})
    except OSError as exc:
        return {"status": "tidak-izin", "dir": str(d), "detail": type(exc).__name__}
    # cycle.lock = penanda proses; run_config = parameter aktif
    kunci = ("run_config.json", "positions.json", "signals.jsonl")
    isi: dict[str, Any] = {}
    for nama in kunci:
        b = baca_json(d / nama, pakai_sudo=False)
        if b.ok:
            isi[nama] = b.data
        else:
            isi[nama] = {"status": b.status}
    return {
        "status": ringkas.get("status", "ok"),
        "dir": str(d),
        "files": ringkas.get("files"),
        "bytes": ringkas.get("bytes"),
        "berkas": berkas[:40],
        "isi": isi,
    }


def lp_mark_ringkas(state_path: str | None = None) -> dict[str, Any]:
    """Mark LP terukur (hasil `lt lp-mark`) + pakem bukti — dibaca apa adanya.

    Sumber: `state/lp_mark_terakhir.json`, ditulis job `lp-mark` dari harga nyata
    (DexScreener per alamat pool). Belum ada → status jujur, bukan nol.
    """
    b = baca_json(state_path or LP_MARK_STATE, pakai_sudo=False)
    if not b.ok:
        return {"status": b.status, "path": b.path, "detail": b.detail}
    data = b.data if isinstance(b.data, dict) else {}
    return {
        "status": data.get("status", "ok"),
        "path": b.path,
        "mtime": b.mtime.isoformat() if b.mtime else None,
        "sha256": b.sha256,
        "mark": data.get("mark") or [],
        "total_pnl_usd": data.get("total_pnl_usd"),
        "total_vs_hold_usd": data.get("total_vs_hold_usd"),
        "fee_tier": data.get("fee_tier"),
        "fee_tier_adalah_asumsi": data.get("fee_tier_adalah_asumsi", True),
        "pakem": data.get("pakem"),
        "catatan": data.get("catatan") or [],
    }


def radar_ringkas(state_path: str | None = None) -> dict[str, Any]:
    """Radar rantai dibaca dari state **lokal** hasil `lt radar-update`.

    Sejak 6 Okt 2026 radar dijalankan di Webdock sendiri (recreate dari VM Azure yang
    akan dimatikan) — tidak ada lagi SSH. Kesegaran tetap dibawa apa adanya: ``mtime``
    dari ``diambil_epoch`` (kapan radar benar-benar jalan), bukan waktu berkas disentuh.
    """
    b = baca_json(state_path or RADAR_STATE, pakai_sudo=False)
    if not b.ok:
        return {"status": b.status, "path": b.path, "detail": b.detail}
    data = b.data if isinstance(b.data, dict) else {}
    diambil = data.get("diambil_epoch")
    chains = data.get("chains") if isinstance(data.get("chains"), list) else None
    return {
        "status": "ok",
        "path": b.path,
        "mtime": b.mtime.isoformat() if b.mtime else None,
        "diambil_epoch": diambil,
        "sha256": b.sha256,
        "data": data,
        "chains": chains,
        "sumber": "lokal",  # radar lokal Webdock, bukan cache host lain
    }

# --- LP paper (arm LP/GMGN) -------------------------------------------------
# Sumber: ~/gmgn-paper/state/sim_ledger.jsonl (ledger simulasi, ditulis mesin GMGN).
# Rumus dipakai SAMA seperti mesin (gmgn_paper/sim.py::summarize): median/mean net_pct,
# tp_rate/sl_rate, expectancy_usd = mean/100*4.0 (notional $4), "cukup" = n>=30.
# TIDAK ada rumus baru, TIDAK ada default angka: berkas hilang -> status jujur.
SIM_LEDGER_STATE = "~/gmgn-paper/state/sim_ledger.jsonl"
_LP_NOTIONAL_USD = 4.0


def _lp_stats(nets: list[float], results: list[dict]) -> dict[str, Any]:
    """Ringkas satu kelompok memakai rumus mesin (bukan rumus baru)."""
    nets = sorted(x for x in nets if isinstance(x, (int, float)))
    n = len(nets)
    if n == 0:
        return {"n": 0, "cukup": False}
    tp = sum(1 for r in results if r.get("exit_reason") == "tp")
    sl = sum(1 for r in results if r.get("exit_reason") == "sl")
    return {
        "n": n,
        "cukup": n >= 30,  # ambang gate yang sudah ada, bukan ambang baru
        "median_net_pct": nets[n // 2],
        "mean_net_pct": sum(nets) / n,
        "menang_pct": sum(1 for x in nets if x > 0) / n * 100.0,
        "tp_rate_pct": tp / n * 100.0,
        "sl_rate_pct": sl / n * 100.0,
        "expectancy_usd": sum(nets) / n / 100.0 * _LP_NOTIONAL_USD,
    }


def _lp_gross(nets: list[float]) -> dict[str, Any]:
    nets = sorted(x for x in nets if isinstance(x, (int, float)))
    n = len(nets)
    if n == 0:
        return {"n": 0}
    return {"n": n, "median_pct": nets[n // 2], "mean_pct": sum(nets) / n,
            "menang_pct": sum(1 for x in nets if x > 0) / n * 100.0}


def lp_paper_ringkas(state_dir: str | None = None) -> dict[str, Any]:
    """Ringkas kinerja arm LP paper dari `sim_ledger.jsonl` — baca-saja.

    Kenapa ada: UI `/lp` butuh angka apa adanya, dan fact `lp_paper` selama ini
    kosong (`{"tersedia": false}`) sehingga halaman tak bisa menampilkan apa pun.
    Ringkasan ini murni hitungan dari ledger; tidak menyentuh mesin, tidak menulis
    ke `~/gmgn-paper`, tidak menyentuh wallet/venue.
    """
    p = Path(state_dir or SIM_LEDGER_STATE).expanduser()
    if not p.exists():
        return {"tersedia": False, "status": "tidak-ada", "path": str(p)}

    rows: list[dict] = []
    rusak = 0
    try:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rusak += 1  # dilaporkan, bukan disembunyikan (pelajaran sim.py)
    except OSError as exc:
        return {"tersedia": False, "status": "tidak-izin", "path": str(p),
                "detail": type(exc).__name__}

    done = [r for r in rows if r.get("status") == "done" and r.get("results")]
    if not done:
        return {"tersedia": False, "status": "kosong", "path": str(p),
                "baris": len(rows), "baris_rusak": rusak}

    # Geometri basis = hasil[0] (TP100/SL65), sama seperti pembacaan mesin.
    def _basis(r: dict) -> dict | None:
        res = r.get("results") or []
        return res[0] if res else None

    basis_rows = [(r, _basis(r)) for r in done]
    basis_rows = [(r, b) for r, b in basis_rows if b]

    nets = [b["net_pct"] for _, b in basis_rows if b.get("net_pct") is not None]
    gross = [b["gross_pct"] for _, b in basis_rows if b.get("gross_pct") is not None]
    res_all = [b for _, b in basis_rows]
    tp0 = basis_rows[0][1]

    ringkas: dict[str, Any] = {
        "tersedia": True,
        "path": str(p),
        "baris": len(rows),
        "baris_rusak": rusak,
        "status": "ok" if rusak == 0 else "rusak-sebagian",
        "sampel": len(nets),
        "geometri": f"TP+{tp0.get('tp_pct', 0):g}/SL-{tp0.get('sl_pct', 0):g}",
        "basis": _lp_stats(nets, res_all),
        "gross": _lp_gross(gross),
        "notional_usd": _LP_NOTIONAL_USD,
    }

    # Kelompok: signal (pakai sinyal) vs control (acak, tanpa sinyal) — pembanding kunci.
    per_kelompok = {}
    for g in ("signal", "control", "admitted"):
        sub = [(r, b) for r, b in basis_rows if r.get("group") == g]
        if len(sub) >= 5:
            per_kelompok[g] = _lp_stats([b["net_pct"] for _, b in sub if b.get("net_pct") is not None],
                                        [b for _, b in sub])
    ringkas["per_kelompok"] = per_kelompok

    # Gesekan: median, dibawa apa adanya (bukan tafsir).
    def _med(vals: list[float]) -> float | None:
        vals = sorted(x for x in vals if isinstance(x, (int, float)))
        return vals[len(vals) // 2] if vals else None

    ringkas["gesekan"] = {
        "slippage_median_pct": _med([r.get("slippage_pct") for r, _ in basis_rows]),
        "friction_median_pct": _med([r.get("friction_pct") for r, _ in basis_rows]),
        "fee_pct_per_side_median": _med([r.get("fee_pct_per_side") for r, _ in basis_rows]),
    }

    # Slippage per kelompok — bukti "sinyal menyasar pool lebih tipis".
    sl_kel = {}
    for g, sub in ((g, [(r, b) for r, b in basis_rows if r.get("group") == g])
                   for g in ("signal", "control")):
        if len(sub) >= 5:
            sl_kel[g] = _med([r.get("slippage_pct") for r, _ in sub])
    ringkas["slippage_per_kelompok"] = sl_kel

    # Sebaran exit — apa yang sebenarnya terjadi.
    exit_reason = {}
    for _, b in basis_rows:
        k = b.get("exit_reason") or "?"
        exit_reason[k] = exit_reason.get(k, 0) + 1
    ringkas["exit_reason"] = exit_reason

    # Kepekaan TP/SL: semua geometri yang sudah diuji mesin (tak ada yang selamat?).
    per_geo: dict[str, list[float]] = {}
    for r in done:
        for res in (r.get("results") or []):
            label = f"TP+{res.get('tp_pct', 0):g}/SL-{res.get('sl_pct', 0):g}"
            if res.get("net_pct") is not None:
                per_geo.setdefault(label, []).append(res["net_pct"])
    ringkas["per_geometri"] = {
        lab: {"n": len(v), "mean_net_pct": sum(v) / len(v),
              "median_net_pct": sorted(v)[len(v) // 2]}
        for lab, v in sorted(per_geo.items())
    }
    return ringkas
