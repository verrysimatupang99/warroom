"""Kesiapan live + grant (P6). Semua pembacaan **baca-saja**.

Prinsip yang dikodekan: **armed ≠ running**. Status live dibaca dari tiga sumber berbeda
(berkas gate, `operator.json`, env unit) + heartbeat — dan ketiganya ditampilkan apa adanya.
Menyalakan unit eksekusi = langsung live, jadi kita tidak pernah menyalakannya dari sini.

Endpoint aksi live **tidak** melakukan apa pun terhadap eksekusi: ia hanya memeriksa grant
dan menolak 409 bila grant kurang. Eksekusi nyata tetap milik owner, di luar repo ini.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as SASession
from warroom_core.db import Event, Grant

__all__ = [
    "ARMING_PATHS",
    "SUBPERINTAH_DRY_RUN_DIIZINKAN",
    "arming_status",
    "grant_aktif",
    "grant_baru",
    "ensure_grant",
    "scope_kurang",
]

GATE_FILE = "/etc/poly-pilot/activation-approved"
OPERATOR_FILE = "/etc/poly-pilot/operator.json"
UNIT = "poly-pilot.service"
HEARTBEAT = "/var/lib/poly-agent/harness-heartbeat.json"

ARMING_PATHS = {"gate": GATE_FILE, "operator": OPERATOR_FILE, "unit": UNIT, "heartbeat": HEARTBEAT}

# Scope aksi live yang dikenal. Aksi di luar daftar ini ditolak (fail-closed).
SCOPE_DIKENAL = (
    "live.start",
    "live.stop",
    "live.size.change",
    "live.strategy.change",
    "live.gate.touch",
)


def _baca_root(path: str, *, timeout_s: float = 10.0) -> tuple[str | None, str]:
    """Baca berkas di direktori root-only lewat sudo tanpa sandi (baca-saja)."""
    p = Path(path)
    try:
        if p.exists():
            return p.read_text(encoding="utf-8", errors="replace"), "ok"
    except PermissionError:
        pass
    except OSError as exc:
        return None, f"rusak:{type(exc).__name__}"
    hasil = subprocess.run(  # noqa: S603 — path tetap, bukan input pengguna
        ["sudo", "-n", "cat", path], capture_output=True, text=True, check=False, timeout=timeout_s
    )
    if hasil.returncode == 0:
        return hasil.stdout, "ok"
    if "No such file" in hasil.stderr:
        return None, "tidak-ada"
    return None, "tidak-bisa-dibaca"


def _ada_root(path: str) -> bool:
    hasil = subprocess.run(  # noqa: S603
        ["sudo", "-n", "test", "-e", path], capture_output=True, text=True, check=False, timeout=10
    )
    return hasil.returncode == 0


@dataclass
class Arming:
    armed: bool
    checks: list[dict[str, Any]] = field(default_factory=list)
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"armed": self.armed, "checks": self.checks, "detail": self.detail}


def arming_status() -> Arming:
    """Tiga sumber + heartbeat. `armed` HANYA bila gate ada, operator tidak paused, unit ada."""
    checks: list[dict[str, Any]] = []

    gate_ada = _ada_root(GATE_FILE)
    checks.append(
        {
            "nama": "gate_file",
            "sumber": GATE_FILE,
            "nilai": "ada" if gate_ada else "tidak ada",
            "lulus": gate_ada,
            "arti": "berkas gate hadir = izin live diberikan; TIDAK PERNAH dibuat oleh agen",
        }
    )

    op_teks, op_status = _baca_root(OPERATOR_FILE)
    op: dict[str, Any] = {}
    if op_status == "ok" and op_teks:
        try:
            val = json.loads(op_teks)
            op = val if isinstance(val, dict) else {}
        except json.JSONDecodeError:
            op = {}
    paused = bool(op.get("paused", True))  # default aman: dianggap paused bila tak terbaca
    checks.append(
        {
            "nama": "operator_json",
            "sumber": OPERATOR_FILE,
            "nilai": {"paused": op.get("paused"), "submissionAllowed": op.get("submissionAllowed"),
                      "status_baca": op_status},
            "lulus": (op_status == "ok") and not paused and bool(op.get("submissionAllowed")),
            "arti": "paused=false DAN submissionAllowed=true",
        }
    )

    try:
        unit = subprocess.run(  # noqa: S603
            ["systemctl", "show", UNIT, "-p", "LoadState", "-p", "ActiveState", "-p", "Environment"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        unit_out = unit.stdout if unit.returncode == 0 else ""
    except (subprocess.SubprocessError, OSError):
        unit_out = ""
    load = next((b.split("=", 1)[1] for b in unit_out.splitlines() if b.startswith("LoadState=")), "?")
    active = next((b.split("=", 1)[1] for b in unit_out.splitlines() if b.startswith("ActiveState=")), "?")
    env_raw = next((b.split("=", 1)[1] for b in unit_out.splitlines() if b.startswith("Environment=")), "")
    # Env bisa memuat kredensial: hanya NAMA variabel yang ditampilkan.
    nama_env = sorted({tok.split("=")[0] for tok in env_raw.split() if "=" in tok})
    unit_ada = load not in {"not-found", "?", ""}
    checks.append(
        {
            "nama": "unit_env",
            "sumber": UNIT,
            "nilai": {"load": load, "active": active, "env_vars": nama_env},
            "lulus": unit_ada,
            "arti": "unit ada; env hanya menampilkan NAMA variabel, bukan nilainya",
        }
    )

    hb_teks, hb_status = _baca_root(HEARTBEAT)
    hb: dict[str, Any] = {}
    if hb_status == "ok" and hb_teks:
        try:
            hb = json.loads(hb_teks)
        except json.JSONDecodeError:
            hb = {}
    checks.append(
        {
            "nama": "heartbeat",
            "sumber": HEARTBEAT,
            "nilai": hb if hb else {"status_baca": hb_status},
            "lulus": hb_status == "ok",
            "arti": "harness agen masih hidup (informatif, bukan izin)",
        }
    )

    lulus = [c for c in checks if c["nama"] in {"gate_file", "operator_json", "unit_env"}]
    armed = all(c["lulus"] for c in lulus)
    kurang = [c["nama"] for c in lulus if not c["lulus"]]
    return Arming(
        armed=armed,
        checks=checks,
        detail="siap live" if armed else f"belum siap: {', '.join(kurang)} belum lulus",
    )


def grant_aktif(s: SASession, scope: str, *, now: datetime | None = None) -> Grant | None:
    t = now or datetime.now(UTC)
    baris = s.scalars(
        select(Grant)
        .where(Grant.scope == scope)
        .where(Grant.revoked_at.is_(None))
        .order_by(Grant.granted_at.desc())
    ).all()
    for g in baris:
        if g.expires_at is None or g.expires_at > t:
            return g
    return None


def scope_kurang(s: SASession, scope: str) -> list[str]:
    """Daftar grant yang kurang untuk satu aksi live (dipakai isi pesan 409)."""
    if scope not in SCOPE_DIKENAL:
        return [f"scope '{scope}' tidak dikenal → fail-closed (tidak ada aksi live)"]
    kurang: list[str] = []
    if grant_aktif(s, scope) is None:
        kurang.append(f"grant aktif untuk scope '{scope}'")
    # Aksi yang mengubah live selalu butuh gate terbuka — bukan hanya grant.
    if not arming_status().armed and scope != "live.stop":
        kurang.append("gate live terbuka (berkas activation-approved) — hanya owner")
    return kurang


def grant_baru(
    s: SASession,
    *,
    scope: str,
    granted_by: str,
    message_id: str,
    reason: str = "",
    ttl_s: int | None = 3600,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Catat izin baru. `message_id` wajib: izin sah selalu berasal dari pesan user."""
    t = now or datetime.now(UTC)
    if not message_id.strip():
        raise ValueError("message_id wajib — izin live harus merujuk pesan user")
    if scope not in SCOPE_DIKENAL:
        raise ValueError(f"scope '{scope}' tidak dikenal; pilihan: {', '.join(SCOPE_DIKENAL)}")
    g = Grant(
        scope=scope,
        granted_by=granted_by,
        message_id=message_id,
        reason=reason,
        granted_at=t,
        expires_at=(t + timedelta(seconds=ttl_s)) if ttl_s else None,
    )
    s.add(g)
    s.flush()
    s.add(
        Event(
            type="live.grant",
            actor=granted_by,
            payload_json={"scope": scope, "message_id": message_id, "ttl_s": ttl_s, "reason": reason},
            fact_ids=[],
            severity="warning",
        )
    )
    s.flush()
    return {"id": g.id, "scope": g.scope, "expires_at": g.expires_at.isoformat() if g.expires_at else None}


def ensure_grant(s: SASession, scope: str) -> None:
    """Lempar ValueError berisi daftar grant kurang (dipakai handler → 409)."""
    kurang = scope_kurang(s, scope)
    if kurang:
        raise PermissionError(json.dumps({"kurang": kurang}))


# Subperintah CLI `lt` yang AMAN dipanggil dari endpoint HTTP: hanya baca/ukur, tanpa
# efek samping state, tanpa jalur tulis. Temuan audit 5 Okt 2026: endpoint ini dulu
# meneruskan `subperintah` apa adanya, sehingga subperintah ber-efek samping
# (`snapshot` menulis, `paper` membuka/menutup posisi, `dedupe` menghapus, `dashboard`
# menjalankan server) bisa dipanggil dari web. `depth` = satu-satunya yang sesuai
# maksud "uji kering kedalaman buku".
SUBPERINTAH_DRY_RUN_DIIZINKAN = frozenset({"depth"})


def _lt_bin() -> Path:
    """Lokasi CLI `lt` yang benar — dari venv tempat API ini berjalan.

    Temuan QA 5 Okt 2026: kode lama memakai `$WARROOM_DOMAIN_HOME/.venv/bin/lt`
    (`/home/admin/live-trading/.venv/bin/lt`), yang **sudah tidak ada** di host ini —
    jadi `/live/dry-run` selalu membalas `{"status":"tidak-ada"}` (mati, bukan jalan).
    Aturan yang sama dipakai worker (`_lt_bin` di jobs.py): venv tempat proses ini
    berjalan selalu menunjuk paket repo, jadi itu yang dipakai lebih dulu.
    """
    kandidat = Path(sys.executable).parent / "lt"
    if kandidat.exists():
        return kandidat
    return Path(os.environ.get("WARROOM_DOMAIN_HOME", str(Path.home() / "live-trading"))) / ".venv/bin/lt"


def run_dry_depth(subperintah: str = "depth", *, timeout_s: int = 120) -> dict[str, Any]:
    """Uji kering: ukur kedalaman buku (tanpa order), lewat CLI domain.

    Dipakai P6-T3. Angka yang keluar adalah hasil perintah nyata; bila gagal → status+alasan.
    Hanya subperintah di ``SUBPERINTAH_DRY_RUN_DIIZINKAN`` yang dijalankan (fail-closed).
    """
    if subperintah not in SUBPERINTAH_DRY_RUN_DIIZINKAN:
        return {
            "status": "ditolak",
            "detail": (
                f"subperintah '{subperintah}' tidak diizinkan untuk uji kering; "
                f"pilihan: {', '.join(sorted(SUBPERINTAH_DRY_RUN_DIIZINKAN))}"
            ),
        }
    lt = _lt_bin()
    if not lt.exists():
        return {"status": "tidak-ada", "detail": f"CLI domain tidak ada: {lt}"}
    hasil = subprocess.run(  # noqa: S603 — path tetap + subperintah sudah di-allowlist
        [str(lt), subperintah], capture_output=True, text=True, check=False, timeout=timeout_s
    )
    if hasil.returncode != 0:
        return {"status": "gagal", "kode": hasil.returncode, "detail": hasil.stderr.strip()[:300]}
    return {"status": "ok", "keluaran": hasil.stdout.strip()[:2000].splitlines()}