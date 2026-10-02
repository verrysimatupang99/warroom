"""Adapter Polymarket — **baca-saja** (P4-T1/T2/T5).

Batas mutlak: tidak menulis, tidak me-restart unit, tidak mengubah config di
``/opt/polymarket/**`` maupun ``/var/lib/poly-*``. Semua akses lewat :mod:`io` (punya
jejak `mtime`+`sha256`) dan setiap kegagalan dilaporkan apa adanya.

Tiga peran:

1. **arms()** — ringkasan tiap arm paper + state agen (P4-T1).
2. **parity_drift()** — bandingkan keputusan mirror vs eksekutor (P4-T2).
3. **reconcile_klaim()** — verifikasi klaim uang ke sumber on-chain; **tanpa RPC
   terkonfigurasi hasilnya "tidak terverifikasi"**, bukan "aman" (P4-T5).
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from warroom_worker.adapters.io import Bacaan, baca_json, baca_jsonl_ekor, ringkas_dir

__all__ = [
    "ARM_DIRS",
    "agent_ringkas",
    "arms",
    "datasets_ringkas",
    "parity_drift",
    "reconcile_klaim",
]

# Nama arm → direktori state (dari studi `01-studi-polymarket.md` §2.2).
ARM_DIRS: dict[str, str] = {
    "A-shadow": "/var/lib/poly-paper",
    "B-kandidat": "/var/lib/poly-paper-candidate",
    "C-fade": "/var/lib/poly-paper-fade",
    "D-favorit": "/var/lib/poly-paper-favorite",
}
AGENT_DIR = "/var/lib/poly-agent"
PILOT_DIR = "/var/lib/poly-pilot"
RESEARCH_DIR = "/var/lib/poly-research"

# Status yang berarti "benar-benar memutuskan masuk" (bukan penolakan/penundaan).
STATUS_MASUK = ("entered", "entry", "filled", "posted", "order_sent")

# Status penolakan yang DISENGAJA (keputusan juga).
STATUS_TOLAK = (
    "outside_window",
    "outside_price_band",
    "loss_budget",
    "insufficient_depth",
    "no_open_reference",
)

# Status "tidak mampu menilai" — bukan keputusan. Kalau eksekutor hanya menghasilkan ini,
# membandingkannya akan memunculkan drift palsu (pernah terjadi: drift 597 dari 400 baris).
STATUS_TIDAK_MAMPU = (
    "unavailable",
    "unverified",
    "empty_book",
    "error",
    "timeout",
    "exception",
)


def _klasifikasi(status: str) -> str:
    s = status.lower()
    if any(s.startswith(p) for p in STATUS_MASUK):
        return "masuk"
    if any(s.startswith(p) for p in STATUS_TIDAK_MAMPU) or "unavailable" in s or "unverified" in s:
        return "tidak-mampu"
    if any(s.startswith(p) for p in STATUS_TOLAK):
        return "tolak"
    return "lain"


def _ringkas_summary(b: Bacaan) -> dict[str, Any]:
    """Ambil angka penting dari summary arm; kunci yang tidak ada tidak diisi 0."""
    if not b.ok or not isinstance(b.data, dict):
        return {"status": b.status, "detail": b.detail or "summary tidak terbaca"}
    d = b.data
    out: dict[str, Any] = {"status": "ok", "rawat": False}
    for kunci in ("mode", "execution", "modelVersion"):
        if kunci in d:
            out[kunci] = d[kunci]
    # Bentuk ringkasan berbeda antar versi: ambil apa pun yang ada, jangan mengarang.
    for kandidat in ("totals", "summary", "stats", "result"):
        blok = d.get(kandidat)
        if isinstance(blok, dict):
            out[kandidat] = {k: blok[k] for k in list(blok)[:12]}
    strat = d.get("strategy")
    if isinstance(strat, dict):
        out["strategi"] = {
            k: strat[k] for k in ("entryLo", "entryHi", "sideMode", "invert", "momThresh")
            if k in strat
        }
    return out


def arms(base: str | None = None) -> dict[str, dict[str, Any]]:
    """Ringkasan tiap arm + jejak berkasnya. Sumber tak terbaca = status, bukan angka."""
    base = base or "/var/lib"
    hasil: dict[str, dict[str, Any]] = {}
    for nama, dirrel in ARM_DIRS.items():
        d = Path(base) / Path(dirrel).relative_to("/var/lib")
        summ = baca_json(d / "execution-paper-shadow-summary.json")
        state = baca_json(d / "execution-paper-shadow-state.json")
        ekor = baca_jsonl_ekor(d / "execution-paper-shadow.jsonl", n=400)
        masuk = 0
        tolak = 0
        if ekor.ok and isinstance(ekor.data, list):
            for baris in ekor.data:
                st = str(baris.get("status", ""))
                if any(st.startswith(p) for p in STATUS_MASUK):
                    masuk += 1
                else:
                    tolak += 1
        hasil[nama] = {
            "dir": str(d),
            "summary": _ringkas_summary(summ),
            "state_status": state.status,
            "state_mtime": state.mtime.isoformat() if state.mtime else None,
            "jsonl_status": ekor.status,
            "jsonl_sha256": ekor.sha256,
            "baris_dibaca": (ekor.meta or {}).get("baris"),
            "masuk_400_baris": masuk if ekor.ok else None,
            "tolak_400_baris": tolak if ekor.ok else None,
        }
    return hasil


def agent_ringkas(dirpath: str | None = None) -> dict[str, Any]:
    """State agen + hitungan pelajaran/upgrades. Ditulis apa adanya (bukan ringkasan opini)."""
    d = Path(dirpath or AGENT_DIR)
    summary = baca_json(d / "agent-summary.json")
    state = baca_json(d / "agent-state.json")
    lessons = baca_jsonl_ekor(d / "agent-lessons.jsonl", n=200)
    upgrades = baca_jsonl_ekor(d / "agent-upgrades.jsonl", n=200)
    heartbeat = baca_json(d / "harness-heartbeat.json")

    diterapkan: list[dict[str, Any]] = []
    ditolak: list[dict[str, Any]] = []
    if lessons.ok and isinstance(lessons.data, list):
        for baris in lessons.data:
            for kunci in baris.get("applied", []) or []:
                diterapkan.append({"ts": baris.get("ts"), "kunci": kunci, "label": baris.get("label")})
            for item in baris.get("rejected", []) or []:
                if isinstance(item, dict):
                    ditolak.append(
                        {"ts": baris.get("ts"), "kunci": item.get("key"),
                         "nilai": item.get("value"), "alasan": item.get("reason")}
                    )
    return {
        "summary_status": summary.status,
        "summary": summary.data if summary.ok else None,
        "state_status": state.status,
        "state": state.data if state.ok else None,
        "heartbeat_status": heartbeat.status,
        "heartbeat": heartbeat.data if heartbeat.ok else None,
        "lessons": {"status": lessons.status, "n": (lessons.meta or {}).get("baris")},
        "upgrades": {"status": upgrades.status, "n": (upgrades.meta or {}).get("baris")},
        "diterapkan_200": diterapkan[-40:],
        "ditolak_200": ditolak[-40:],
    }


def datasets_ringkas(research_dir: str | None = None) -> dict[str, Any]:
    """Katalog dataset recorder (jumlah berkas + byte) — untuk DatasetExplorer."""
    research_dir = research_dir or RESEARCH_DIR
    paired = ringkas_dir(Path(research_dir) / "paired")
    dataset = ringkas_dir(Path(research_dir) / "dataset")
    orderflow = ringkas_dir(Path(research_dir) / "orderflow-confirm")
    return {"paired": paired, "dataset": dataset, "orderflow_confirm": orderflow}


def _keputusan(baris: list[dict[str, Any]]) -> dict[tuple[str, str], int]:
    """Peta (key window, status) → jumlah, hanya untuk baris yang benar-benar memutuskan.

    "Tidak mampu menilai" (feed mati, buku kosong) **bukan** keputusan — memasukkannya
    membuat drift terlihat besar padahal eksekutor memang tidak memutuskan apa pun.
    """
    out: dict[tuple[str, str], int] = {}
    for b in baris:
        st = str(b.get("status", ""))
        if not st or _klasifikasi(st) not in {"masuk", "tolak"}:
            continue
        kunci = str(b.get("key") or f"{b.get('coin', '?')}:?")
        out[(kunci, st)] = out.get((kunci, st), 0) + 1
    return out


def ringkas_status(baris: list[dict[str, Any]]) -> dict[str, int]:
    """Hitungan per klasifikasi — dipakai untuk menjelaskan kenapa drift tidak bisa dihitung."""
    hasil: dict[str, int] = {"masuk": 0, "tolak": 0, "tidak-mampu": 0, "lain": 0}
    for b in baris:
        hasil[_klasifikasi(str(b.get("status", "")))] += 1
    return hasil


@dataclass
class Drift:
    status: str  # ok | tidak-bisa-dibandingkan
    mirror_n: int = 0
    executor_n: int = 0
    drift: int = 0
    contoh: list[str] = field(default_factory=list)
    detail: str = ""


def parity_drift(
    mirror_dir: str | None = None,
    executor_dir: str | None = None,
    *,
    n: int = 400,
) -> Drift:
    """Bandingkan keputusan mirror (arm) vs eksekutor (pilot) pada ekor log yang sama.

    Bila eksekutor tidak memutuskan apa pun (mis. feed mati / live dihentikan), hasilnya
    **tidak-bisa-dibandingkan** dengan alasan — bukan "drift 0" yang menyesatkan.
    """
    mirror_dir = mirror_dir or ARM_DIRS["B-kandidat"]
    executor_dir = executor_dir or PILOT_DIR
    mk = baca_jsonl_ekor(Path(mirror_dir) / "execution-paper-shadow.jsonl", n=n)
    ex = baca_jsonl_ekor(Path(executor_dir) / "execution-paper-shadow.jsonl", n=n)
    if not mk.ok or not ex.ok:
        return Drift(
            status="tidak-bisa-dibandingkan",
            detail=f"mirror={mk.status} eksekutor={ex.status}",
        )
    km = _keputusan(mk.data or [])
    ke = _keputusan(ex.data or [])
    if not ke:
        kls = ringkas_status(ex.data or [])
        return Drift(
            status="tidak-bisa-dibandingkan",
            mirror_n=len(km),
            executor_n=0,
            detail=(
                "eksekutor tidak mencatat keputusan masuk/tolak pada jendela ekor ini "
                f"(klasifikasi: {kls}). Drift tidak bisa dihitung dari apa yang tidak ada."
            ),
        )
    hanya_m = {k for k in km if k not in ke}
    hanya_e = {k for k in ke if k not in km}
    return Drift(
        status="ok",
        mirror_n=len(km),
        executor_n=len(ke),
        drift=len(hanya_m) + len(hanya_e),
        contoh=[f"mirror-only {k[0]}/{k[1]}" for k in list(hanya_m)[:5]]
        + [f"executor-only {k[0]}/{k[1]}" for k in list(hanya_e)[:5]],
    )


# --- rekonsiliasi klaim uang (P4-T5) ----------------------------------------------------


def _rpc_url() -> str | None:
    import os

    return os.environ.get("WARROOM_POLYGON_RPC") or None


def cek_saldo_onchain(alamat: str, *, timeout_s: float = 8.0) -> dict[str, Any]:
    """Cek jumlah share CTF seorang alamat lewat `eth_call` (ERC-1155 balanceOf).

    Tanpa ``WARROOM_POLYGON_RPC`` → ``{"status": "tidak-dikonfigurasi"}``. Kita **tidak**
    menyimpulkan "saldo nol" dari ketiadaan RPC — itu persis kesalahan yang pernah terjadi
    (state melaporkan claimable $8,62 padahal saldo share 0,000000).
    """
    rpc = _rpc_url()
    if not rpc:
        return {"status": "tidak-dikonfigurasi",
                "detail": "WARROOM_POLYGON_RPC belum diset; klaim uang tidak bisa diverifikasi"}
    # Pemanggilan ERC-1155 balanceOf(address,uint256) pada kontrak CTF Polygon.
    ctf = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
    selector = "0x00fdd58e"
    alamat_bersih = alamat.lower().replace("0x", "").rjust(64, "0")
    token_id = "0" * 64  # token id spesifik tidak diketahui dari sini; lihat catatan di detail
    data = selector + alamat_bersih + token_id
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "eth_call",
         "params": [{"to": ctf, "data": data}, "latest"]}
    ).encode()
    req = urllib.request.Request(rpc, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
            jawab = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"status": "gagal", "detail": f"{type(exc).__name__}: {exc}"}
    if "result" not in jawab:
        return {"status": "gagal", "detail": str(jawab.get("error", "tanpa hasil"))[:200]}
    return {
        "status": "ok",
        "saldo_raw": jawab["result"],
        "catatan": "token id harus diketahui per posisi; angka ini tidak dipakai untuk klaim",
    }


def reconcile_klaim(pilot_dir: str | None = None, *, alamat: str | None = None) -> dict[str, Any]:
    """Baca klaim uang dari state pilot dan tandai apakah bisa diverifikasi.

    Aturan: klaim **tidak** pernah ditampilkan sebagai "nyata" tanpa verifikasi on-chain.
    """
    state = baca_json(Path(pilot_dir or PILOT_DIR) / "snipe-live-v1-state.json")
    if not state.ok or not isinstance(state.data, dict):
        return {"status": state.status, "detail": "state pilot tidak terbaca",
                "klaim": None, "terverifikasi": False}
    d = state.data
    klaim = None
    for kunci in ("claimablePayout", "claimable", "payout"):
        if kunci in d:
            klaim = d[kunci]
            break
    saldo = cek_saldo_onchain(alamat) if alamat else {
        "status": "tidak-dikonfigurasi", "detail": "alamat tidak diberikan"
    }
    terverifikasi = bool(saldo.get("status") == "ok" and klaim in (0, 0.0, None))
    return {
        "status": "ok",
        "sumber": state.path,
        "observed_at": state.mtime.isoformat() if state.mtime else None,
        "sha256": state.sha256,
        "klaim": klaim,
        "saldo_onchain": saldo,
        "terverifikasi": terverifikasi,
        "keterangan": (
            "klaim nol → cocok dengan pemeriksaan on-chain"
            if terverifikasi
            else "klaim uang BELUM terverifikasi ke sumber; jangan ditampilkan sebagai uang nyata"
        ),
    }


def sidik_jari(data: Any) -> str:
    """Hash kanonik untuk deteksi perubahan sunyi (state berubah tanpa mtime baru)."""
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()
    ).hexdigest()


def sekarang() -> datetime:
    return datetime.now(UTC)