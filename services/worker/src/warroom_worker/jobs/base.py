"""Basis handler job worker: path, pemanggil CLI domain, penulis fakta, alert."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as SASession
from warroom_core.db import Alert, Fact, Job, Service

from warroom_worker.facts_publish import canonical_hash
from warroom_worker.facts_publish import publish_snapshot as publish_snapshot  # noqa: F401

log = logging.getLogger("warroom_worker.jobs")

def root_dir() -> Path:
    """Direktori domain (live-trading). Bisa ditimpa lewat env `WARROOM_DOMAIN_HOME`."""
    import os

    return Path(os.environ.get("WARROOM_DOMAIN_HOME", str(Path.home() / "live-trading")))


def root_dir_repo() -> Path:
    """Root repo warroom (tempat kode resmi hidup — guard kodebase-dalam-repo)."""
    return Path(__file__).resolve().parents[5]


def _lt_bin() -> Path:
    """Lokasi CLI `lt` yang benar — dari venv tempat worker ini berjalan.

    Kenapa tidak dari `root_dir()/.venv`: `root_dir()` adalah `WARROOM_DOMAIN_HOME`
    (`/home/admin/live-trading`), dan folder itu masih menyimpan **venv lama** yang meng-import
    dari source lama (`/home/admin/live-trading/src`). Akibatnya setiap job yang memanggil `lt`
    menjalankan kode sebelum merge: `lt snapshot` menghasilkan `bagian` yang lebih sedikit
    (macro/lp/overextended hilang) tanpa error apa pun — dan penjaga anti-snapshot-separuh pun
    tidak menangkapnya, karena kode lama itu melaporkan bagian yang sama dengan yang ia tulis.

    Venv worker sendiri (`sys.executable`) selalu menunjuk paket repo, jadi itu yang dipakai.
    """
    kandidat = Path(sys.executable).parent / "lt"
    if kandidat.exists():
        return kandidat
    return root_dir() / ".venv" / "bin" / "lt"


def _jalankan_lt(subperintah: str, job: Job, *, timeout_s: int) -> str:
    """Jalankan CLI domain (`lt <subperintah>`) sebagai subproses.

    Memakai entry point venv langsung (bukan `uv run`) supaya tidak membangun ulang
    lingkungan pada setiap job. Keluaran disimpan ringkas; yang penting jejaknya.
    """
    lt = _lt_bin()
    if not lt.exists():
        raise FileNotFoundError(f"CLI domain tidak ada: {lt}")
    hasil = subprocess.run(  # noqa: S603 — path tetap, dari repo domain yang tepercaya
        [str(lt), subperintah],
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
        cwd=str(root_dir()),
        env={**os.environ, "LT_HOME": str(root_dir())},
    )
    if hasil.returncode != 0:
        raise RuntimeError(
            f"lt {subperintah} gagal (kode {hasil.returncode}): {hasil.stderr.strip()[:200]}"
        )
    # Penjaga anti-snapshot-separuh. Snapshot ditulis dengan `write_text` (bukan atomik), jadi
    # satu-satunya cara sebuah bagian ("bagian") bisa HILANG sementara prosesnya keluar kode 0
    # adalah snapshot ditulis oleh **kode lama** — mis. satu layanan lain yang masih menjalankan
    # salinan lama dan menimpa berkas state yang sama. Menyimpan bagian-bagian yang sudah
    # dilaporkan ringkasan stdout lalu membandingkannya membuat keadaan itu **kelihatan**,
    # bukan lewat begitu saja dengan status "ok".
    ringkas = [b.strip() for b in hasil.stdout.splitlines() if b.strip()]
    dilaporkan = {b.split()[0] for b in ringkas if b.split() and b.split()[-1] == "ok"}
    ditulis = set()
    if subperintah == "snapshot":
        try:
            snap = json.loads((Path(root_dir()) / "state" / "snapshot.json").read_text("utf-8"))
            ditulis = set((snap.get("bagian") or {}).keys())
        except (OSError, json.JSONDecodeError):
            ditulis = set()
        hilang = sorted(dilaporkan - ditulis)
        if hilang:
            raise RuntimeError(
                f"snapshot tidak lengkap: {hilang} dilaporkan ok tetapi tidak ada di berkas — "
                "berkas kemungkinan ditimpa oleh kode lama (unit lain yang belum ikut diperbarui)"
            )
    return f"lt {subperintah} ok; " + " | ".join(ringkas[-3:])[:240]


def _tulis_fakta(s: SASession, *, kind: str, key: str, value: Any, source: str, ttl_s: int) -> None:
    """Satu fakta berversi. `observed_at` = sekarang (kita yang baru membacanya)."""
    s.add(
        Fact(
            kind=kind,
            key=key,
            value_json=value,
            source=source,
            observed_at=datetime.now(UTC),
            ttl_s=ttl_s,
            hash=canonical_hash(value),
        )
    )
    s.flush()


def _alert(
    s: SASession,
    *,
    subject: str,
    message: str,
    aksi: str,
    severity: str = "warning",
    fact_ids: list[int] | None = None,
) -> bool:
    """Buat alert KECUALI sudah ada alert BELUM DI-ACK dengan subjek yang sama.

    Menahan diri selama alert lama masih terbuka (bukan hanya selama jendela waktu tetap)
    itu penting: jendela tetap yang lebih pendek dari interval job membuat alert menumpuk
    tanpa batas untuk kondisi yang tidak berubah — terbukti 9 alert `learner/ringkas` dan
    13 alert `poly/klaim-uang` terbuka hanya dari DUA kondisi. Selama satu alert masih
    terbuka, pengingat ditangani notifier; setelah di-ack, kondisi yang masih berjalan boleh
    memunculkan alert baru. Kembalikan True bila alert baru benar-benar dibuat.
    """
    sudah = s.scalar(
        select(Alert.id).where(Alert.subject == subject).where(Alert.ack_at.is_(None)).limit(1)
    )
    if sudah is not None:
        return False
    s.add(
        Alert(
            severity=severity,
            subject=subject,
            message=message,
            suggested_action=aksi,
            fact_ids=list(fact_ids or []),
        )
    )
    s.flush()
    return True


def _fakta_terbaru(s: SASession, kunci: list[str] | None, *, batas: int) -> list[Any]:
    """Fakta terbaru per kunci (atau semua kunci bila `kunci` kosong)."""
    from warroom_core.db import Fact

    q = select(Fact).order_by(Fact.observed_at.desc()).limit(batas * 6 if kunci else batas)
    if kunci:
        q = q.where(Fact.key.in_(kunci))
    baris = list(s.scalars(q).all())
    unik: dict[str, Any] = {}
    for f in baris:
        unik.setdefault(f.key, f)
    return list(unik.values())[:batas]


def _ringkas_fakta(f: Any, kunci: str) -> str:
    """Ubah fakta besar jadi teks ANGKA-utuh untuk narator.

    Masalah nyata (6 Okt): narator hanya melihat 80 karakter pertama JSON, sehingga ia
    bercerita tentang metadata (sha256/checksum) alih-alih hasilnya. Di sini kita ambil
    bagian yang berisi angka, tanpa mengubah nilainya — LLM tidak boleh menghitung ulang.
    """
    v = f.value_json
    if not isinstance(v, dict):
        return str(v)[:400]
    if kunci.endswith("_sinyal"):
        entries = (v.get("entries") or [])[:5]
        baris = [
            {
                "pair": e.get("pair") or e.get("ticker"),
                "arah": e.get("arah"),
                "setup": e.get("setup"),
                "status": e.get("hasil") or e.get("status"),
                "skor_gate": e.get("skor"),
                "entry": e.get("entry"),
                "sl": e.get("sl"),
                "tp1": e.get("tp1"),
                "r": e.get("r") if e.get("r") is not None else e.get("net_r"),
            }
            for e in entries
        ]
        return f"n_entries={len(v.get('entries') or [])} | " + str(baris)[:1100]
    if kunci == "pasar_akurasi":
        pasar = v.get("pasar") or {}
        baris = []
        for nama, p in pasar.items():
            for setup, s in (p.get("per_setup") or {}).items():
                baris.append(
                    f"{nama}/{setup}: n={s.get('n')} hari={s.get('n_hari')} "
                    f"WR={s.get('winrate_pct')}% meanR={s.get('mean_r')} totalR={s.get('total_r')} "
                    f"pnl_usd={s.get('total_pnl_usd', s.get('pnl_usd'))} tingkat={s.get('tingkat')}"
                )
        return " || ".join(baris)[:1200]
    if kunci == "idx_akurasi":
        ringkas = v.get("per_setup") or {}
        baris = [
            f"{k}: n={s.get('n')} hari={s.get('n_hari')} WR={s.get('winrate_pct')}% "
            f"meanR={s.get('mean_r')} tingkat={s.get('pakem')}"
            for k, s in ringkas.items()
        ]
        return f"tuntas={v.get('tuntas')} belum={v.get('belum_tuntas')} | " + " || ".join(baris)[:1000]
    return str(v)[:600]


def _pesan_sinyal(sg: dict[str, Any], label: str) -> str:
    """Format pesan sinyal untuk Telegram — angka apa adanya + label jujur wajib."""
    baris = [f"{sg['pair']} · {sg['arah']} · tier {sg.get('tier')}"]
    harga = f"entry {sg.get('entry')} · SL {sg.get('sl')} · TP1 {sg.get('tp1')}"
    # QA 7 Okt: yang ditulis mesin adalah JARAK STOP. Ukuran posisi dibuat agar risiko
    # akun tetap 1% ekuitas; menulis "risiko" di sini menyesatkan (dibaca sebagai pelanggaran).
    if sg.get("risk_pct") is not None:
        harga += f" · jarak stop {sg['risk_pct']}%"
    baris.append(harga)
    baris.append(label)
    if sg.get("aturan_gagal"):
        baris.append("aturan belum lulus: " + ", ".join(str(x) for x in sg["aturan_gagal"]))
    return "\n".join(baris)


def _pelajaran_terakhir() -> dict[str, Any] | None:
    """Ambil pelajaran terakhir yang memuat n/win/be (yang lain tidak bisa dinilai)."""
    from warroom_worker.adapters import poly

    b = poly.baca_jsonl_ekor(f"{poly.AGENT_DIR}/agent-lessons.jsonl", n=50)
    if not b.ok or not isinstance(b.data, list):
        return None
    for baris in reversed(b.data):
        if isinstance(baris, dict) and baris.get("rows") and baris.get("winPct"):
            return baris
    return None


def _unit_state(unit: str) -> str:
    """Status unit systemd (baca-saja). Gagal/tak ada → 'unknown'/'not-found', bukan tebakan."""
    import subprocess

    try:
        r = subprocess.run(  # noqa: S603
            ["systemctl", "show", unit, "-p", "LoadState", "-p", "ActiveState"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if r.returncode != 0:
        return "unknown"
    load = next((b.split("=", 1)[1] for b in r.stdout.splitlines() if b.startswith("LoadState=")), "")
    active = next((b.split("=", 1)[1] for b in r.stdout.splitlines() if b.startswith("ActiveState=")), "")
    if load in {"not-found", ""}:
        return "not-found"
    return active or "unknown"


def _upsert_service(
    s: SASession, *, host: str, unit: str, status: str, detail: dict[str, Any]
) -> None:
    """Satu baris per (host, unit) — pakai unique constraint, bukan tumpuk baris baru."""
    row = s.scalar(select(Service).where(Service.host == host, Service.unit == unit))
    if row is None:
        s.add(Service(host=host, unit=unit, status=status, detail_json=detail))
    else:
        row.status = status
        row.detail_json = detail
        row.updated_at = datetime.now(UTC)


