#!/usr/bin/env python3
"""Backtest keputusan peran `verifier` atas trade lampau — UJI sebelum peran LLM dipasang.

DASAR
=====
Dokumen usul `docs/usul-peran-llm-penilai-2026-10-09.md` (bagian 4) menyatakan peran LLM
sebagai "penilai kedua" WAJIB diuji sebelum dipasang. Skrip ini menjalankan uji itu:

  Pertanyaan:  dari trade yang SUDAH tuntas (hasil diketahui), apakah `verifier` akan
               MENOLAK yang rugi dan MELOLOSKAN yang untung?

  Kegunaan:    (a) `tambah_nilai`  = verifier menolak trade rugi (menghindari kerugian)
               (b) `false_negatif` = verifier menolak trade UNTUNG (membuang peluang)
               Kriteria GO (usulan, hak owner): (a) >= 60% DAN (b) <= 20%.

CARA PAKAI
==========
  # 1. Load kredensial LLM (WAJIB — tanpa ini gateway membaca kunci KOSONG -> 401):
  sudo bash -c 'set -a; . /etc/warroom/llm.env; set +a; \\
    cd /home/admin/warroom && \\
    PYTHONPATH=services/worker/src:packages/core/src:services/llm/src:. \\
    .venv/bin/python tools/uji_backtest_verifier.py --n 12'

  # Atau dengan env DB sekaligus (kalau butuh menulis hasil sebagai fakta):
  sudo bash -c 'set -a; . /etc/warroom/db.env; . /etc/warroom/llm.env; set +a; ...'

CATATAN PENTING (temuan 9 Okt)
==============================
- `fact_id` HARUS id asli dari tabel `facts`. Skrip ini mengambilnya sendiri; `verifier`
  menolak (benar!) bila `fact_id` tidak ada — itu perilaku yang diinginkan (ADR-004 butir 5).
- `--dry` = tidak memanggil LLM sama sekali (uji kerangka, hemat anggaran).
- Anggaran LLM harian $3 (lihat /etc/warroom/llm.json). Pakai `--n` kecil dulu.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

LEDGER = Path("/home/admin/live-trading/state/idx_ledger.db")
MENANG = {"TP1", "TP2", "WIN"}


def ambil_trade(n: int, hanya: str | None = None, sebar: bool = False) -> list[dict]:
    """Ambil `n` trade TUNTAS berimbang (setengah untung, setengah rugi) dari ledger IDX.

    `sebar=True` menyebar lintas-setup (round-robin per setup) — memperbaiki cacat uji-1
    (9 Okt): sampel "teratas menurut net_r" semuanya jatuh ke ARA_HUNTER, sehingga
    "untung_ditolak" tak bermakna. Dengan sebar, tiap setup terwakili.
    """
    if not LEDGER.exists():
        sys.exit(f"ledger tidak ada: {LEDGER}")
    c = sqlite3.connect(f"file:{LEDGER}?mode=ro", uri=True)  # baca-saja, tak pernah menulis
    c.row_factory = sqlite3.Row
    rows = [dict(r) for r in c.execute(
        "select ticker,setup,direction,result,net_r,note,entry_low,sl,tp1 "
        "from signals where status='CLOSED'"
    ).fetchall()]
    c.close()
    untung = sorted([r for r in rows if r["result"] in MENANG], key=lambda r: -r["net_r"])
    rugi = sorted([r for r in rows if r["result"] not in MENANG], key=lambda r: r["net_r"])
    if hanya == "untung":
        kandidat = (untung, [])
    elif hanya == "rugi":
        kandidat = ([], rugi)
    else:
        kandidat = (untung, rugi)

    if not sebar:
        half = max(1, n // 2)
        return kandidat[0][:half] + kandidat[1][:half]

    # Sebar lintas-setup: ambil bergiliran dari tiap setup agar tidak didominasi satu setup.
    def sebar_per_setup(pool: list[dict]) -> list[dict]:
        per: dict[str, list[dict]] = {}
        for r in pool:
            per.setdefault(r["setup"], []).append(r)
        keluar: list[dict] = []
        i = 0
        while len(keluar) < len(pool):
            maju = False
            for setup in sorted(per):
                if i < len(per[setup]):
                    keluar.append(per[setup][i])
                    maju = True
                    if len(keluar) >= len(pool):
                        break
            if not maju:
                break
            i += 1
        return keluar

    half = max(1, n // 2)
    return sebar_per_setup(kandidat[0])[:half] + sebar_per_setup(kandidat[1])[:half]


def fact_refs_nyata(trade: dict, n_facts: int) -> tuple:
    """Bangun FactRef dengan `fact_id` ASLI dari tabel `facts`.

    Ini menjawab temuan 9 Okt: mengarang fact_id (1,2,3) membuat `verifier` menolak
    dengan `fact_id_tidak_ada` — benar secara aturan, tapi salah sebagai bahan uji.

    PELAJARAN uji-1 (9 Okt): menyuapkan `idx_akurasi` (statistik agregat) + parameter trade
    membuat `verifier` menolak SEMUA ("blok fakta tidak memuat data kelayakan") — benar,
    karena yang diminta menilai adalah KELAYAKAN, bukan sekadar parameter. Jadi di sini
    blok FAKTA memuat **riwayat kinerja setup itu sendiri** (n, WR, mean_r, total_r) —
    bukti kelayakan yang relevan — plus parameter trade yang diuji, semuanya dari baris
    fakta NYATA (`idx_akurasi`), dengan `fact_id` asli.
    """
    from sqlalchemy import text
    from warroom_core.db import session_scope
    from warroom_llm import FactRef

    with session_scope() as s:
        fakta_db = s.execute(
            text(
                "select id, key, value_json from facts "
                "where key in ('idx_akurasi','pasar_akurasi') "
                "order by observed_at desc limit :n"
            ),
            {"n": n_facts},
        ).fetchall()

    # Ambil riwayat kinerja setup ini dari fakta (bukti kelayakan yang tepat).
    riwayat = {}
    fact_id_riwayat = None
    for f in fakta_db:
        d = f[2] or {}
        ps = d.get("per_setup") or {}
        if trade["setup"] in ps:
            riwayat = ps[trade["setup"]]
            fact_id_riwayat = int(f[0])
            break

    refs = []
    if fact_id_riwayat is not None:
        r = riwayat
        refs.append(
            FactRef(
                fact_id=fact_id_riwayat,
                label="F1",
                text=(
                    f"riwayat_setup {trade['setup']}: n={r.get('n')} hari={r.get('n_hari')} "
                    f"winrate={r.get('winrate_pct')}% mean_r={r.get('mean_r')} total_r={r.get('total_r')} "
                    f"pakem={r.get('pakem')}"
                ),
            )
        )
        refs.append(
            FactRef(
                fact_id=fact_id_riwayat,
                label="F2",
                text=(
                    f"trade_diuji: {trade['setup']} {trade['direction']} {trade['ticker']} "
                    f"entry={trade['entry_low']} sl={trade['sl']} tp1={trade['tp1']}"
                ),
            )
        )

    # Sisipkan fakta lain (jika ada) sebagai konteks tambahan — tetap fact_id asli.
    for f in fakta_db:
        if int(f[0]) == fact_id_riwayat:
            continue
        refs.append(
            FactRef(
                fact_id=int(f[0]),
                label=f"F{len(refs) + 1}",
                text=f"{f[1]}={json.dumps(f[2], ensure_ascii=False)[:80]}",
            )
        )
        if len(refs) >= max(2, n_facts + 1):
            break
    return tuple(refs)


def jalankan(n: int, hanya: str | None, dry: bool, min_facts: int, sebar: bool = False) -> dict:
    sampel = ambil_trade(n, hanya, sebar=sebar)
    print(f"=== UJI verifier atas {len(sampel)} trade tuntas (ledger {LEDGER.name}) ===")
    print("(verifier menilai KLAIM: 'trade ini layak dijalankan' terhadap blok FAKTA nyata)\n")

    if dry:
        print("[DRY] tidak memanggil LLM. Sampel yang AKAN diuji:")
        for s in sampel:
            jenis = "UNTUNG" if s["result"] in MENANG else "RUGI"
            print(f"  {jenis:6} {s['ticker']:12} {s['setup']:12} netR={s['net_r']:+.2f}")
        return {"dry": True, "n": len(sampel)}

    from warroom_core import prompts_dir
    from warroom_llm import CallRequest, Gateway
    from warroom_llm.config import default_config
    from warroom_llm.prompts import PromptRegistry

    gw = Gateway(config=default_config(), prompts=PromptRegistry.from_dir(str(prompts_dir())))

    hasil = []
    for i, s in enumerate(sampel):
        menang = s["result"] in MENANG
        try:
            refs = fact_refs_nyata(s, n_facts=2)
        except Exception as exc:  # noqa: BLE001
            print(f"[{i + 1}] LEWATI {s['ticker']}: gagal ambil fakta ({exc})")
            continue
        r = gw.call(
            CallRequest(
                role="verifier",
                user=(
                    f"Klaim: 'trade {s['ticker']} {s['setup']} {s['direction']} layak dijalankan'. "
                    f"Nilai kelayakan dari riwayat kinerja setup itu (F1): bila mean_r>0 & sampel cukup "
                    f"-> layak; bila mean_r<=0 -> tidak layak. Setujui hanya bila angka pada klaim "
                    f"didukung fact_id di blok FAKTA."
                ),
                facts=refs,
                min_facts=min_facts,
            )
        )
        out = r.output or {}
        baris = {
            "ticker": s["ticker"],
            "setup": s["setup"],
            "asli": "UNTUNG" if menang else "RUGI",
            "setuju": out.get("setuju"),
            "tingkat": out.get("tingkat"),
            "alasan": (out.get("alasan") or "")[:100],
            "status": r.status,
            "provider": r.provider,
            "error_code": r.error_code,
        }
        hasil.append(baris)
        print(
            f"[{i + 1}] {baris['ticker']:12} {baris['setup']:12} asli={baris['asli']:6} "
            f"-> setuju={baris['setuju']} tingkat={baris['tingkat']} "
            f"({baris['status']}/{baris['provider']}/"
            f"{baris['error_code'] or '-'})"
        )
        if baris["alasan"]:
            print(f"      alasan: {baris['alasan']}")

    # --- Ringkasan nilai ---
    sah = [h for h in hasil if h["setuju"] is not None]
    rugi_total = [h for h in sah if h["asli"] == "RUGI"]
    untung_total = [h for h in sah if h["asli"] == "UNTUNG"]
    ditolak_rugi = [h for h in rugi_total if h["setuju"] is False]
    ditolak_untung = [h for h in untung_total if h["setuju"] is False]

    ringkas = {
        "n_uji": len(hasil),
        "n_sah": len(sah),
        "rugi_ditolak": len(ditolak_rugi),
        "rugi_total": len(rugi_total),
        "untung_ditolak": len(ditolak_untung),
        "untung_total": len(untung_total),
    }
    if rugi_total:
        ringkas["tambah_nilai_pct"] = round(100 * len(ditolak_rugi) / len(rugi_total), 1)
    if untung_total:
        ringkas["false_negatif_pct"] = round(100 * len(ditolak_untung) / len(untung_total), 1)

    print("\n=== RINGKASAN ===")
    for k, v in ringkas.items():
        print(f"  {k}: {v}")
    if "tambah_nilai_pct" in ringkas:
        go = (ringkas.get("tambah_nilai_pct", 0) >= 60) and (ringkas.get("false_negatif_pct", 100) <= 20)
        hasil_go = 'GO' if go else 'NO-GO'
        print(f"  -> kriteria GO (usulan): tambah_nilai>=60% DAN "
              f"false_negatif<=20% => {hasil_go}")
    print("\nCATATAN: kriteria GO/NO-GO adalah USULAN; keputusan akhir hak owner (ADR-006).")
    return {"ringkasan": ringkas, "hasil": hasil}


def main() -> None:
    ap = argparse.ArgumentParser(description="Backtest peran verifier atas trade lampau.")
    ap.add_argument("--n", type=int, default=12, help="jumlah trade yang diuji (default 12)")
    ap.add_argument("--hanya", choices=["untung", "rugi"], help="batasi ke satu jenis hasil")
    ap.add_argument("--dry", action="store_true", help="tidak memanggil LLM (uji kerangka)")
    ap.add_argument("--min-facts", type=int, default=1, dest="min_facts", help="minimal fakta (default 1)")
    ap.add_argument("--sebar", action="store_true", help="sebar sampel lintas-setup (rekomendasi)")
    ap.add_argument("--out", default="/tmp/uji_backtest_hasil.json", help="simpan hasil JSON ke sini")
    a = ap.parse_args()
    hasil = jalankan(a.n, a.hanya, a.dry, a.min_facts, sebar=a.sebar)
    try:
        Path(a.out).write_text(json.dumps(hasil, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"\ndisimpan: {a.out}")
    except OSError as exc:
        print(f"\n(gagal simpan: {exc})")


if __name__ == "__main__":
    main()
