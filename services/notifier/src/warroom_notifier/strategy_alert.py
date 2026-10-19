"""Alert per strategi: entry, exit, benched, kill-switch — satu subjek per kondisi.

Aturan yang dikodekan di sini (bukan di pemanggil):

- **Subjek = dedup.** Setiap kondisi punya subjek tetap (``strategi/…``) sehingga
  ``_alert`` di worker menahan alert kedua selama yang pertama belum di-ack.
  Kondisi yang berulang tiap siklus (mis. strategi tetap benched selama sehari)
  karena itu menghasilkan SATU alert, bukan satu per tick.
- **Kejadian, bukan keadaan.** ``entry``/``exit`` diberi subjek per aksi
  (``trade/<signal_id>/entry`` dan ``trade/<signal_id>/exit``) — trade baru =
  alert entry; penutupan = alert exit; entry yang belum di-ack tak menahan exit.
- **Benched/kill hanya saat BERUBAH.** Alert dibangkitkan pada transisi
  aktif→benched dan aktif→kill; pemanggil menyuplai keadaan sebelumnya. Strategi
  yang masih benched pada siklus berikutnya tidak memicu apa pun.
- **Angka apa adanya.** Pesan hanya memuat nilai yang diberikan pemanggil; tidak
  ada persen/harga yang dihitung ulang di sini.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = [
    "KondisiStrategi",
    "alert_benched",
    "alert_entry",
    "alert_exit",
    "alert_kill_switch",
    "alert_tp1",
    "to_payload",
]

# Subjek per kondisi. Nama kondisi dipakai apa adanya di subjek supaya alert lama
# dan baru dengan kondisi berbeda tidak saling menahan dedup.
_SUBJEK = {
    "benched": "strategi/benched",
    "kill": "strategi/kill-switch",
}

# Tingkat: benched = peringatan (uang dibatasi, bukan rusak); kill = kritis
# (eksekusi berhenti). Dua-duanya TIDAK pernah info: info di-ack otomatis saat
# terkirim (dispatch), dan alert keselamatan uang tidak boleh hilang begitu saja.
_SEVERITY = {"benched": "warning", "kill": "critical"}


@dataclass(frozen=True)
class KondisiStrategi:
    """Satu kondisi operasional satu strategi — nilai apa adanya, tanpa hitungan."""

    strategi: str
    kondisi: str            # benched | kill
    subjek: str             # kunci dedup tetap
    severity: str
    pesan: str
    subjek_aksi: str        # aksi yang disarankan ke operator


def _subjek_kondisi(kondisi: str, strategi: str) -> str:
    return f"{_SUBJEK[kondisi]}:{strategi}"


def alert_benched(
    strategi: str,
    *,
    alasan: str,
    trade: int | str | None = None,
    fee_usd: float | None = None,
    hari: str | None = None,
) -> KondisiStrategi:
    """Strategi baru masuk ``benched`` — dipanggil HANYA pada transisi.

    ``trade``/``fee_usd`` hanya ditampilkan bila pemanggil benar-benar punya
    nilainya; tanpa itu pesan tidak menyebut angka sama sekali (bukan nol).
    Subjek menyertakan tanggal hari (WIB) agar tidak menahan dedup lintas hari.
    """
    if hari is None:
        from datetime import UTC, datetime, timedelta

        hari = (datetime.now(UTC) + timedelta(hours=7)).strftime("%Y-%m-%d")
    subjek = f"{_SUBJEK['benched']}:{strategi}:{hari}"
    pesan = f"{strategi} benched: {alasan}"
    bagian = []
    if trade is not None:
        bagian.append(f"{trade} trade")
    if fee_usd is not None:
        bagian.append(f"fee ${float(fee_usd):.2f}")
    if bagian:
        pesan += f" ({', '.join(bagian)} hari ini)"
    return KondisiStrategi(
        strategi=strategi,
        kondisi="benched",
        subjek=subjek,
        severity=_SEVERITY["benched"],
        pesan=pesan,
        subjek_aksi="batas harian per strategi — entry baru untuk strategi ini ditahan sampai hari berganti",
    )


def alert_kill_switch(
    strategi: str,
    *,
    alasan: str,
    posisi_ditutup: int | None = None,
) -> KondisiStrategi:
    """Kill-switch / HALTED baru aktif untuk satu strategi — hanya pada transisi."""
    pesan = f"{strategi} kill-switch aktif: {alasan}"
    if posisi_ditutup is not None:
        pesan += f" ({posisi_ditutup} posisi ditutup)"
    return KondisiStrategi(
        strategi=strategi,
        kondisi="kill",
        subjek=_subjek_kondisi("kill", strategi),
        severity=_SEVERITY["kill"],
        pesan=pesan,
        subjek_aksi="eksekusi strategi ini berhenti; reset hanya oleh owner",
    )


def alert_entry(
    strategi: str,
    *,
    signal_id: str,
    pair: str,
    direction: str,
    entry: float | None = None,
    stop: float | None = None,
    tp1: float | None = None,
    tp2: float | None = None,
    mode: str | None = None,
    size_usd: float | None = None,
    risk_usd: float | None = None,
    biaya_bps: float | None = None,
) -> KondisiStrategi:
    """Trade paper baru dibuka. Subjek per aksi → satu alert per entry trade.

    ``mode`` (mis. ``paper``) memberi label jujur pada pesan; ukuran/risiko/biaya
    hanya ditampilkan bila pemanggil benar-benar menyuplainya.
    """
    baris = [f"{strategi} {direction.upper()} {pair}"]
    if entry is not None:
        baris.append(f"entry {entry}")
    if stop is not None:
        baris.append(f"stop {stop}")
    if tp1 is not None:
        baris.append(f"tp1 {tp1}")
    if tp2 is not None:
        baris.append(f"tp2 {tp2}")
    if size_usd is not None:
        baris.append(f"size ${float(size_usd):.2f}")
    if risk_usd is not None:
        baris.append(f"risiko ${float(risk_usd):.2f}")
    if biaya_bps is not None:
        baris.append(f"biaya {float(biaya_bps):g} bps")
    pesan = " | ".join(baris)
    if mode:
        pesan = f"[{mode.upper()}] {pesan}"
    return KondisiStrategi(
        strategi=strategi,
        kondisi="entry",
        subjek=f"trade/{signal_id}/entry",
        severity="info",
        pesan=pesan,
        subjek_aksi="lihat posisi terbuka di /crypto?sub=eksekusi",
    )


def alert_exit(
    strategi: str,
    *,
    signal_id: str,
    pair: str,
    status: str,
    r: float | None = None,
    mode: str | None = None,
) -> KondisiStrategi:
    """Trade paper ditutup (SL/TP/manual). Subjek per aksi → satu alert per exit trade."""
    pesan = f"{strategi} {pair} ditutup: {status}"
    if r is not None:
        pesan += f" ({float(r):+.3f}R)"
    if mode:
        pesan = f"[{mode.upper()}] {pesan}"
    return KondisiStrategi(
        strategi=strategi,
        kondisi="exit",
        subjek=f"trade/{signal_id}/exit",
        severity="info",
        pesan=pesan,
        subjek_aksi="periksa buku kas di /crypto?sub=eksekusi",
    )


def alert_tp1(
    strategi: str,
    *,
    signal_id: str,
    pair: str,
    direction: str,
    stop: float | int | str,
    tp2: float | int | str,
    mode: str | None = "paper",
) -> KondisiStrategi:
    """TP1 tercapai — runner aktif, stop loss digeser ke break-even."""
    pesan = (
        f"[TP1 TERCAPAI - RUNNER AKTIF]\nPair: {pair} ({direction})\n"
        f"Stop loss digeser ke break-even (${stop}). Sisa posisi menuju TP2 (${tp2})."
    )
    if mode:
        pesan = f"[{mode.upper()}] {pesan}"
    return KondisiStrategi(
        strategi=strategi,
        kondisi="tp1",
        subjek=f"tp1/{signal_id}",
        severity="info",
        pesan=pesan,
        subjek_aksi="pantau posisi di Command Center",
    )


def to_payload(k: KondisiStrategi) -> dict[str, Any]:
    """Payload transport (tanpa kredensial, tanpa angka turunan)."""
    return {
        "strategi": k.strategi,
        "kondisi": k.kondisi,
        "suggested_action": k.subjek_aksi,
    }
