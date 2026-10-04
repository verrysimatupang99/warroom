"""Risk gate — satu-satunya tempat keputusan "boleh entry atau tidak" dibuat.

Prinsipnya: strategi boleh punya pendapat, tapi **ukuran dan izin** ditentukan di
sini. Kalau gate bilang tidak, tidak ada order — apa pun kata sinyal.

Yang dijaga:

* **batas rugi harian** — kalau R hari ini sudah menyentuh batas, berhenti;
* **jumlah posisi bersamaan** — mencegah akumulasi tanpa sadar;
* **ukuran posisi dari ATR** — risiko per trade tetap, bukan ukuran tetap;
* **kunci satu executor** — dua mesin tidak boleh mengeksekusi akun yang sama.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Settings

LOCK_STALE_SECONDS = 600  # kunci dianggap mati kalau tidak diperbarui > 10 menit


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reason: str
    size_usd: float | None = None
    stop_pct: float | None = None
    risk_usd: float | None = None


def _today_wib() -> str:
    return (dt.datetime.now(dt.UTC) + dt.timedelta(hours=7)).strftime("%Y-%m-%d")


@dataclass
class LedgerRead:
    """Hasil membaca ledger, LENGKAP dengan integritasnya.

    Kenapa integritas ikut dilaporkan: pembacaan lama mengembalikan daftar kosong untuk
    berkas yang tidak ada DAN melewatkan baris rusak tanpa sepatah kata. Bagi gate rugi
    harian keduanya tampak sama: "tidak ada kerugian". Itu membuat satu baris rusak -
    mis. tulisan terpotong saat proses mati - cukup untuk menghapus kerugian dari
    perhitungan dan membuka entry padahal batas harian sudah terlampaui.
    """

    exists: bool
    rows: list[dict[str, Any]]
    unreadable: int          # baris yang ADA tapi tidak bisa diurai


def read_ledger_strict(path: Path) -> LedgerRead:
    """Baca ledger tanpa menyembunyikan kerusakan."""
    if not path.is_file():
        # Berkas belum ada = sistem baru, belum ada trade. Ini keadaan sah, bukan kerusakan.
        return LedgerRead(False, [], 0)
    rows: list[dict[str, Any]] = []
    unreadable = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            unreadable += 1
    return LedgerRead(True, rows, unreadable)


def read_ledger(path: Path) -> list[dict[str, Any]]:
    """Baris ledger yang bisa diurai. Untuk tampilan; gate memakai `read_ledger_strict`."""
    return read_ledger_strict(path).rows


def r_closed_on(rows: list[dict[str, Any]], day: str) -> float:
    """Total R dari trade yang ditutup pada ``day`` (tanggal WIB)."""
    total = 0.0
    for r in rows:
        closed = str(r.get("closed_at") or "")
        if closed[:10] == day:
            total += float(r.get("r") or 0)
    return round(total, 4)


class RiskGate:
    def __init__(self, settings: Settings) -> None:
        self.s = settings

    # ------------------------------------------------------------ keadaan
    def ledger_state(self) -> LedgerRead:
        return read_ledger_strict(self.s.ledger_path)

    def ledger(self) -> list[dict[str, Any]]:
        return self.ledger_state().rows

    def daily_r(self) -> float:
        return r_closed_on(self.ledger(), _today_wib())

    def open_positions(self) -> list[dict[str, Any]]:
        p = self.s.state_dir / "paper_positions.json"
        if not p.is_file():
            return []
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("positions", [])
        except (OSError, json.JSONDecodeError):
            return []

    # ------------------------------------------------------------ kunci executor
    def lock_status(self) -> dict[str, Any]:
        p = self.s.executor_lock_path
        if not p.is_file():
            return {"held": False, "host": None, "age_s": None}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"held": False, "host": None, "age_s": None}
        age = dt.datetime.now(dt.UTC).timestamp() - float(data.get("ts") or 0)
        return {
            "held": age < LOCK_STALE_SECONDS,
            "host": data.get("host"),
            "age_s": round(age),
            "stale": age >= LOCK_STALE_SECONDS,
        }

    def acquire_executor_lock(self) -> dict[str, Any]:
        """Ambil kunci. Menolak kalau host lain masih memegang kunci yang segar."""
        st = self.lock_status()
        me = socket.gethostname()
        if st["held"] and st["host"] != me:
            return {"ok": False, "reason": f"kunci dipegang {st['host']} ({st['age_s']}s lalu)"}
        self.s.state_dir.mkdir(parents=True, exist_ok=True)
        self.s.executor_lock_path.write_text(
            json.dumps({"host": me, "pid": os.getpid(), "ts": dt.datetime.now(dt.UTC).timestamp()}),
            encoding="utf-8",
        )
        return {"ok": True, "host": me}

    def release_executor_lock(self) -> None:
        try:
            self.s.executor_lock_path.unlink()
        except FileNotFoundError:
            pass

    # ------------------------------------------------------------ keputusan
    def check(
        self,
        *,
        pair: str,
        price: float,
        atr: float,
        equity_usd: float,
        stop_mult: float = 1.5,
    ) -> RiskDecision:
        """Boleh entry? Kalau boleh, seberapa besar?"""
        if price <= 0 or atr <= 0:
            return RiskDecision(False, "harga/ATR tidak valid")

        # GAGAL-TERTUTUP: ledger yang tidak bisa dipastikan berarti kita tidak tahu
        # sudah rugi berapa hari ini. "Tidak tahu" bukan "tidak ada kerugian" - gate
        # yang memutuskan uang nyata harus menolak, bukan menebak.
        led = self.ledger_state()
        if led.unreadable:
            return RiskDecision(
                False,
                f"ledger tidak bisa dipastikan: {led.unreadable} baris rusak di "
                f"{self.s.ledger_path.name} - rugi harian tidak bisa dihitung, entry ditolak",
            )

        day_r = r_closed_on(led.rows, _today_wib())
        if day_r <= -abs(self.s.daily_loss_limit_r):
            return RiskDecision(
                False, f"batas rugi harian tercapai ({day_r:+.2f}R ≤ -{self.s.daily_loss_limit_r}R)"
            )

        open_now = self.open_positions()
        if len(open_now) >= self.s.max_concurrent_positions:
            return RiskDecision(
                False, f"posisi bersamaan penuh ({len(open_now)}/{self.s.max_concurrent_positions})"
            )
        if any(p.get("pair") == pair for p in open_now):
            return RiskDecision(False, f"{pair} sudah punya posisi terbuka")

        stop_dist = atr * stop_mult
        stop_pct = stop_dist / price
        if stop_pct <= 0 or stop_pct > 0.5:
            return RiskDecision(False, f"jarak stop tidak masuk akal ({stop_pct:.1%})")

        risk_usd = equity_usd * (self.s.risk_per_trade_pct / 100.0)
        size_usd = risk_usd / stop_pct

        cap = equity_usd * self.s.max_leverage
        if size_usd > cap:
            perlu = size_usd / equity_usd
            return RiskDecision(
                False,
                f"ukuran ${size_usd:.0f} butuh leverage {perlu:.2f}x, "
                f"batas sekarang {self.s.max_leverage:.2f}x "
                f"(naikkan LT_MAX_LEVERAGE kalau memang disengaja)",
            )

        return RiskDecision(
            True,
            f"ok: risiko ${risk_usd:.2f} ({self.s.risk_per_trade_pct}% ekuitas), stop {stop_pct:.2%}",
            size_usd=round(size_usd, 2),
            stop_pct=round(stop_pct, 6),
            risk_usd=round(risk_usd, 2),
        )

    def status(self) -> dict[str, Any]:
        led = self.ledger_state()
        rows = led.rows
        day_r = r_closed_on(rows, _today_wib())
        return {
            # Kerusakan ledger harus TERLIHAT sebelum gate menolak, bukan baru ketahuan
            # dari pesan penolakan. `hari_ini_r` di bawah hanya menjumlah baris yang bisa
            # diurai, jadi tanpa bidang ini angkanya tampak normal padahal tidak lengkap.
            "ledger_baris_rusak": led.unreadable,
            "ledger_angka_bisa_dipercaya": led.unreadable == 0,
            "mode": "paper" if self.s.paper else "live",
            "hari_ini_r": day_r,
            "batas_rugi_r": self.s.daily_loss_limit_r,
            "sisa_ruang_r": round(self.s.daily_loss_limit_r + day_r, 3),
            "posisi_terbuka": len(self.open_positions()),
            "maks_posisi": self.s.max_concurrent_positions,
            "risiko_per_trade_pct": self.s.risk_per_trade_pct,
            "total_trade": len(rows),
            "kunci_executor": self.lock_status(),
        }
