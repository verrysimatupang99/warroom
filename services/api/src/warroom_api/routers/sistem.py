"""Router sistem — build, health, ready, design tokens, docs, freshness.

Diekstrak dari app.py (P1-2, langkah 2). Refactor murni: path, status kode, dan
auth dependency tidak berubah.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from warroom_core import build_id as core_build_id
from warroom_core import domain_version as core_domain_version
from warroom_core.db import Fact, User, session_scope

from warroom_api import auth
from warroom_api.metrics import collect_readiness

router = APIRouter()


def _docs_dir() -> Path | None:
    """Lokasi docs/belajar — dicari dari beberapa akar supaya tahan cara deploy."""
    for p in (
        Path("/home/admin/warroom/docs/belajar"),
        Path(__file__).resolve().parents[4] / "docs" / "belajar",
    ):
        if p.is_dir():
            return p
    return None


@router.get("/api/v1/build")
def build() -> dict[str, Any]:
    """Identitas build yang sedang berjalan — **tanpa auth**, untuk verifikasi deploy.

    Hanya mengembalikan `build_id` + `domain_version`; bukan data sesi, bukan
    konfigurasi. Dipakai skrip deploy (ops/deploy-web.sh) untuk memastikan proses
    yang JALAN memegang build yang BARU, bukan versi lama di memori — penyebab
    insiden 2026-10-08/09 (HTTP 500 di semua halaman karena manifest lama).

    Sengaja publik & terpisah dari /health (yang butuh sesi): saat deploy kita belum
    punya sesi, dan justru saat itulah verifikasi paling dibutuhkan.
    """
    return {
        "build_id": core_build_id(),
        "domain_version": core_domain_version(),
        "time": datetime.now(UTC).isoformat(),
    }


@router.get("/api/v1/health")
def health(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
    db_ok = True
    try:
        with session_scope() as s:
            s.execute(select(1))
    except Exception:  # noqa: BLE001 — kegagalan DB harus jadi status, bukan 500 mentah
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "time": datetime.now(UTC).isoformat(),
        "build_id": core_build_id(),
        "user": user.username,
    }


@router.get("/api/v1/ready")
def ready(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
    checks: dict[str, Any] = {"database": "failed"}
    db_ok = False
    try:
        with session_scope() as s:
            s.execute(select(1))
            checks = collect_readiness(s)
            db_ok = True
    except Exception:  # noqa: BLE001 — readiness reports dependency state
        pass
    worker = checks.get("worker_heartbeats", {})
    stale = checks.get("stale_facts", {})
    blocking = (
        not db_ok
        or worker.get("status") == "stale"
        or stale.get("status") == "stale"
    )
    return {
        "status": "ready" if not blocking else "not_ready",
        "db": db_ok,
        "checks": checks,
        "time": datetime.now(UTC).isoformat(),
        "user": user.username,
    }


@router.get("/api/v1/design/tokens")
def design_tokens(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
    """Token desain dari SATU sumber: blok `@theme` di apps/web/src/app.css.

    Kenapa endpoint ini ada: token hidup di CSS, tetapi alat non-browser (chart,
    ekspor, atau sesi agen) kadang butuh nilainya. Menyalinnya ke Python akan
    menciptakan sumber kedua yang bisa menyimpang — jadi di sini CSS-nya DIBACA,
    bukan disalin. Bila berkas tak terbaca, jawab jujur (`ada: false`), bukan
    mengarang nilai.
    """
    import re

    kandidat = [
        Path("/home/admin/warroom/apps/web/src/app.css"),
        Path(__file__).resolve().parents[5] / "apps" / "web" / "src" / "app.css",
    ]
    berkas = next((p for p in kandidat if p.exists()), None)
    if berkas is None:
        return {"ada": False, "alasan": "app.css tidak ditemukan dari API ini"}
    teks = berkas.read_text(encoding="utf-8")
    # Hanya ambil blok @theme (lapis primitive + semantic); nilai mentah token.
    token: dict[str, str] = {}
    for blok in re.findall(r"@theme\s*\{(.*?)\n\}", teks, re.DOTALL):
        for m in re.finditer(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", blok):
            token[m.group(1)] = m.group(2).strip()
    return {
        "ada": bool(token),
        "sumber": "apps/web/src/app.css",
        "jumlah": len(token),
        "token": token,
    }


@router.get("/api/v1/docs")
def docs_list(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
    """Daftar catatan (docs/belajar/*.md) — judul dari baris `# ` pertama.

    Catatan hidup di repo sebagai markdown. Alih-alih menyalinnya ke DB (sumber
    kedua yang bisa menyimpang), endpoint ini MEMBACA berkasnya langsung.
    """
    import re

    root = _docs_dir()
    if root is None:
        return {"ada": False, "alasan": "docs/belajar tidak ditemukan", "dokumen": []}
    out = []
    for p in sorted(root.glob("*.md")):
        try:
            teks = p.read_text(encoding="utf-8")
        except OSError:
            continue
        m = re.search(r"^#\s+(.+)$", teks, re.MULTILINE)
        judul = m.group(1).strip() if m else p.stem
        out.append({"slug": p.stem, "judul": judul, "ukuran": len(teks)})
    return {"ada": bool(out), "jumlah": len(out), "dokumen": out}


@router.get("/api/v1/docs/{slug}")
def docs_isi(slug: str, user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
    """Isi satu catatan. Slug dibatasi ke nama berkas aman (tanpa `/`, `..`)."""
    import re

    if not re.fullmatch(r"[A-Za-z0-9._-]+", slug):
        raise HTTPException(status_code=422, detail="slug tidak sah")
    root = _docs_dir()
    if root is None:
        raise HTTPException(status_code=404, detail="catatan tidak tersedia")
    p = root / f"{slug}.md"
    if not p.exists():
        raise HTTPException(status_code=404, detail="catatan tidak ditemukan")
    teks = p.read_text(encoding="utf-8")
    m = re.search(r"^#\s+(.+)$", teks, re.MULTILINE)
    return {"slug": slug, "judul": (m.group(1).strip() if m else slug), "isi": teks}


@router.get("/api/v1/freshness")
def freshness(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
    """Umur setiap fakta terbaru vs TTL-nya. Tidak ada fakta → daftar kosong, bukan angka karangan."""
    now = datetime.now(UTC)
    out: list[dict[str, Any]] = []
    with session_scope() as s:
        # fakta terbaru per (kind,key)
        sub = (
            select(Fact.kind, Fact.key, func.max(Fact.observed_at).label("obs"))
            .group_by(Fact.kind, Fact.key)
            .subquery()
        )
        rows = s.scalars(
            select(Fact).join(
                sub,
                (Fact.kind == sub.c.kind) & (Fact.key == sub.c.key) & (Fact.observed_at == sub.c.obs),
            )
        ).all()
        for f in rows:
            age = (now - f.observed_at).total_seconds()
            out.append(
                {
                    "kind": f.kind,
                    "key": f.key,
                    "source": f.source,
                    "observed_at": f.observed_at.isoformat(),
                    "age_s": round(age, 1),
                    "ttl_s": f.ttl_s,
                    "status": "segar" if age <= f.ttl_s else "basi",
                }
            )
    out.sort(key=lambda r: (r["status"] != "basi", r["kind"], r["key"]))
    return {"facts": out, "count": len(out), "checked_at": now.isoformat()}
