#!/usr/bin/env python3
"""Precheck kesiapan uang nyata — Polymarket & crypto (15 Okt 2026).

Baca-saja total: tidak menulis file, tidak menyentuh kunci (hanya KEBERADAAN),
tidak memicu order. Output = daftar SIAP/BLOKIR per pasar dengan alasan yang
bisa ditindaklanjuti owner. Jalankan:
    .venv/bin/python ops/persiapan-live.py            # kedua pasar
    .venv/bin/python ops/persiapan-live.py --pasar crypto
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

STATE = Path(os.environ.get("WARROOM_STATE_DIR", "/home/admin/live-trading/state"))


def _pembanding_poly() -> dict:
    """Kesiapan Polymarket live (jalur poly-pilot, baca-saja)."""
    hasil: dict = {"pasar": "polymarket"}
    # 1) keputusan statistik terbaru dari fakta poly.verdict (DB) atau file verdict
    try:
        q = ("SELECT value_json::text FROM facts WHERE kind='poly.verdict' "
             "ORDER BY observed_at DESC LIMIT 1")
        skrip = ('set -a; source /etc/warroom/db.env; set +a; '
                 'URL="${WARROOM_DB_URL/postgresql+psycopg/postgresql}"; '
                 f'psql "$URL" -t -A -c "{q}"')
        src = subprocess.run(["sudo", "-n", "bash", "-c", skrip],
                             capture_output=True, text=True, timeout=30)
        v = json.loads(src.stdout.strip() or "{}")
        hasil["verdict"] = {
            "status_alat": v.get("verdict_alat", "n/a"),
            "n": v.get("n"), "winrate": v.get("winRate"),
            "be_pct": v.get("breakEven_pct"), "ev_per_stake": v.get("evPerStake"),
            "ci95": v.get("ci95"),
        }
    except Exception as e:  # noqa: BLE001 — precheck harus tetap melapor
        hasil["verdict"] = {"status_alat": "n/a", "galat": str(e)[:120]}
    # 2) gerbang live + state eksekutor
    d = Path("/etc/poly-pilot")
    satu = d.is_dir()
    file_izin, disarmed = "tidak-izin", None
    if satu:
        try:
            file_izin = (d / "activation-approved").is_file()
            disarmed = any(p.name.startswith("DISARMED") for p in d.glob("DISARMED*"))
        except PermissionError:
            pass  # precheck tanpa sudo: laporkan tidak-izin, jangan mengarang
    hasil["gerbang"] = {
        "activation_approved": file_izin,
        "disarmed": disarmed,
        "dir": str(d),
        "ada": satu,
    }
    st = Path("/var/lib/poly-pilot/snipe-live-v1-state.json")
    try:
        jika = st.is_file()
    except PermissionError:
        jika = True  # ada tapi tak terbaca tanpa sudo — coba baca, siap-siap gagal
    if jika:
        try:
            s = json.loads(st.read_text(encoding="utf-8"))
            hasil["eksekutor_terakhir"] = {
                "mode": s.get("mode"), "settled": s.get("settled"),
                "wins": s.get("wins"), "losses": s.get("losses"), "pnl": s.get("pnl"),
            }
        except PermissionError:
            hasil["eksekutor_terakhir"] = "tidak-izin (jalankan precheck dengan sudo allowlist)"
        except Exception as e:  # noqa: BLE001
            hasil["eksekutor_terakhir"] = {"galat": str(e)[:120]}
    else:
        hasil["eksekutor_terakhir"] = "state tidak ditemukan"
    blokir = []
    izin = hasil["gerbang"].get("activation_approved")
    if izin == "tidak-izin":
        blokir.append("gerbang tak terbaca tanpa sudo — jalankan precheck penuh dengan sudo")
        hasil["siap"] = False
        hasil["blokir"] = blokir
        return hasil
    if not izin:
        blokir.append("owner belum membuat /etc/poly-pilot/activation-approved")
    if hasil.get("verdict", {}).get("status_alat") != "EDGE":
        blokir.append("verdict terbaru bukan EDGE — cek fakta poly.verdict")
    hasil["siap"] = (len(blokir) == 0)
    hasil["blokir"] = blokir
    return hasil


def _pembanding_crypto() -> dict:
    """Kesiapan crypto live (jalur live_venue, baca-saja)."""
    from live_trading.execution.live_venue import status_gerbang_live

    hasil: dict = {"pasar": "crypto", "gerbang": status_gerbang_live()}
    # kesehatan jalur paper (yang dijadikan bukti)
    ver = STATE / "verdicts.jsonl"
    hasil["paper"] = {"verdicts_ada": ver.is_file()}
    snap = STATE / "snapshot.json"
    if snap.is_file():
        try:
            eq = json.loads(snap.read_text(encoding="utf-8")).get("equity") or {}
            hasil["paper"]["equity"] = {k: eq.get(k) for k in ("n", "sum_r", "mean_r") if k in eq}
        except Exception as e:  # noqa: BLE001
            hasil["paper"]["galat"] = str(e)[:120]
    blokir = []
    if not hasil["gerbang"].get("siap"):
        if not hasil["gerbang"].get("izin_owner"):
            blokir.append("owner belum membuat /etc/warroom/crypto-live-approved")
        kunci_kurang = [k for k, v in hasil["gerbang"]["kunci_ada"].items() if not v]
        if kunci_kurang:
            blokir.append("kredensial venue belum terpasang: " + ", ".join(kunci_kurang))
    blokir.append("WAJIB: satu order uji kecil (≤$2) terverifikasi di exchange sebelum modal penuh")
    hasil["siap"] = False  # belum ada bukti order uji — sengaja keras
    hasil["blokir"] = blokir
    return hasil


def _guard_kodebase() -> dict:
    """Kode harus hidup di dalam repo /home/admin/warroom — bukan di LT_HOME.

    Pelajaran 14 Okt: salinan kode luar (stale checkout) membuat job 'ok' tapi
    jalan pakai logika lama tanpa suara. Precheck menegakkan dua hal: (1) paket
    live_trading yang diimpor memang dari repo, (2) LT_HOME tidak lagi memuat
    direktori kode (src/, scripts/, crypto/… — boleh berisi data: state, logs).
    """
    import live_trading

    luar = Path(os.environ.get("WARROOM_STATE_DIR", "/home/admin/live-trading"))
    sisa = [d for d in ("src", "scripts", "crypto", "idx616", "frontend", "vendor", "tests")
            if (luar / d).exists()]
    dalam = str(Path(live_trading.__file__).resolve()).startswith("/home/admin/warroom/")
    return {"live_trading_dari": str(live_trading.__file__), "dalam_repo": dalam,
            "lt_home": str(luar), "sisa_kode_luar": sisa or None,
            "ok": dalam and not sisa}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pasar", choices=["polymarket", "crypto"], default=None)
    a = p.parse_args()
    out = []
    if a.pasar in (None, "polymarket"):
        out.append(_pembanding_poly())
    if a.pasar in (None, "crypto"):
        out.append(_pembanding_crypto())
    g = _guard_kodebase()
    print(f"=== KODEBASE: {'SIAP' if g['ok'] else 'BLOKIR'} (harus di dalam /home/admin/warroom)")
    print(f"  {json.dumps(g, ensure_ascii=False)}")
    for r in out:
        status = "SIAP" if r.get("siap") else "BLOKIR"
        print(f"=== {r['pasar'].upper()}: {status}")
        for alasan in r.get("blokir", []):
            print(f"  - {alasan}")
        for k in ("verdict", "gerbang", "eksekutor_terakhir", "paper"):
            if r.get(k):
                print(f"  {k}: {json.dumps(r[k], ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
