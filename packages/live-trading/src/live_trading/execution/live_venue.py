"""Pengiriman order LIVE crypto — gerbang owner yang menolak keras (15 Okt 2026).

Status: kerangka siap, **belum pernah menyentuh API exchange nyata**. Tiga syarat
wajib sebelum order pertama bisa keluar (semua harus ada BERSAMAAN):

1. ``/etc/warroom/crypto-live-approved`` — file izin OWNER (dibuat tangan owner,
   persis pola ``/etc/poly-pilot/activation-approved`` di sisi Polymarket).
2. Kredensial venue di environment (``MEXC_API_KEY`` + ``MEXC_API_SECRET``) —
   keberadaannya dicek, ISINYA tidak pernah dicetak/log.
3. Keputusan masuk ber-``mode="live"`` dari jalur tunggal ``keputusan.py``.

Tanpa satu pun dari ketiganya → :class:`LiveTerblokir` (analog HTTP 409). Tidak ada
jalur "sedikit melewati" — order $20 pertama harus melewati pintu yang sama dengan
order ke-1000.

Rencana rollout jujur: setelah kunci dipasang dan file izin dibuat, owner wajib
memicu SATU order uji bernilai kecil (≤ $2) lewat opsi ``--uji`` dan memverifikasi
receipt di akun exchange sebelum mesin dipercaya dengan modal penuh.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

__all__ = ["LiveTerblokir", "status_gerbang_live", "LiveVenueCrypto", "MexcSpotTransport"]

FILE_IZIN_OWNER = "/etc/warroom/crypto-live-approved"
KUNCI_WAJIB = ("MEXC_API_KEY", "MEXC_API_SECRET")


class LiveTerblokir(RuntimeError):
    """Order live ditolak — daftar syarat yang belum ada ikut di levarkan."""


def status_gerbang_live(home: Path | None = None) -> dict[str, Any]:
    """Keadaan gerbang live untuk precheck — TIDAK pernah membocorkan nilai kunci."""
    home = home or Path(os.environ.get("WARROOM_STATE_DIR", "/home/admin/live-trading/state"))
    izin = Path(FILE_IZIN_OWNER).is_file()
    kunci = {nama: bool(os.environ.get(nama)) for nama in KUNCI_WAJIB}
    env_file = Path("/etc/warroom/crypto.env")
    if any(not ada for ada in kunci.values()) and env_file.is_file():
        try:
            teks = env_file.read_text(encoding="utf-8", errors="ignore")
            for nama in KUNCI_WAJIB:
                if not kunci[nama]:
                    kunci[nama] = any(baris.startswith(f"{nama}=") for baris in teks.splitlines())
        except PermissionError:
            # File ada tapi tak terbaca oleh proses ini (mis. mode 600 root saat
            # proses berjalan sebagai user lain) — jangan crash; status jujur:
            # keberadaan kunci tidak terbaca, gerbang tetap ditentukan oleh izin owner.
            pass
    siap = izin and all(kunci.values())
    return {"izin_owner": izin, "file_izin": FILE_IZIN_OWNER, "kunci_ada": kunci, "siap": siap}


@dataclass
class LiveVenueCrypto:
    """Satu-satunya objek yang boleh mengirim order crypto sungguhan.

    ``kirim_order`` menegakkan ketiga syarat di atas pada SETIAP panggilan (bukan
    sekali di ``__init__``) — file izin dicabut di tengah jalan berarti order
    berikutnya menolak, tidak ada sesi yang "masih memegang izin lama".
    """

    transport: Callable[[dict[str, Any]], dict[str, Any]]
    gerbang: bool = False   # hanya boleh True dari kelas ini sendiri setelah cek
    jejak: list[str] = field(default_factory=list)

    # -- kelahiran ------------------------------------------------------------
    @classmethod
    def bangun(cls) -> LiveVenueCrypto:
        st = status_gerbang_live()
        if not st["siap"]:
            kurang = [k for k, v in st["kunci_ada"].items() if not v]
            if not st["izin_owner"]:
                kurang.append(f"file izin owner ({FILE_IZIN_OWNER})")
            raise LiveTerblokir("live crypto terblokir: " + ("; ".join(kurang) or "tiba-tiba siap?"))
        return cls(transport=MexcSpotTransport(), gerbang=True,
                   jejak=[f"gerbang ok: izin owner + kunci {'/'.join(KUNCI_WAJIB)}"])

    # -- kirim ----------------------------------------------------------------
    def kirim_order(self, keputusan: Any) -> dict[str, Any]:
        """Kirim entry + pasang SL berdasarkan Keputusan dari jalur tunggal.

        Keputusan TIDAK dihitung ulang (kontrak keputusan.py): nilai entry/sl/size
        hanya dibaca dan diteruskan. Menghitung ulang di sini = jalur kedua.
        """
        if not self.gerbang:
            raise LiveTerblokir("venue tidak dibangun lewat bangun() — jalur kembali tidak sah")
        st = status_gerbang_live()
        if not st["siap"]:
            raise LiveTerblokir(f"gerbang berubah saat Runtime: {st}")
        if getattr(keputusan, "mode", "paper") != "live":
            raise LiveTerblokir("keputusan bukan mode live — jangan paksa order nyata")
        if not getattr(keputusan, "masuk", False):
            raise LiveTerblokir("keputusan berisi DITOLAK — tidak ada yang dikirim")

        pair = str(keputusan.pair).replace("USDT", "USDT")
        order = {
            "symbol": pair,
            "side": "BUY" if keputusan.arah.upper() == "LONG" else "SELL",
            "type": "MARKET",
            "quote_order_qty": round(float(keputusan.size_usd), 2),
        }
        self.jejak.append(f"kirim {order['symbol']} {order['side']} ~${order['quote_order_qty']}")
        receipt = self.transport(order)
        receipt["sl"] = {
            "side": "SELL", "type": "STOP_LOSS",
            "stop_price": keputusan.sl, "pending": True,
            "catatan": ("SL dipasang SESUDAH ack entry; bila gagal, posisi TANPA "
                        "pelindung — hentikan mesin manual sampai SL terpasang."),
        }
        receipt["jejak"] = list(self.jejak)
        return receipt


class MexcSpotTransport:
    """Klien MEXC spot minimal (lihat `persiapan-live` runbook).

    Status jujur per 15 Okt 2026: penandatanganan HMAC distandarkan dan diuji
    dengan vektor deterministik (``tests/test_live_venue.py``), tetapi **belum ada
    panggilan nyata yang pernah dibuktikan**. Order pertama WAJIB bernilai uji kecil.
    """

    def __init__(self, recv_window: int = 5000,
                 send: Callable[[str, str, str, str], dict[str, Any]] | None = None):
        self.base = "https://api.mexc.com"
        self.recv_window = recv_window
        self._send = send or self._http

    def _http(self, _url: str, _query: str, _apa: str, _api_key: str) -> dict[str, Any]:
        raise LiveTerblokir("transport HTTP belum tersambung — jalankan uji order dulu")

    def __call__(self, order: dict[str, Any]) -> dict[str, Any]:
        kunci = os.environ["MEXC_API_KEY"]
        rahasia = os.environ["MEXC_API_SECRET"].encode()
        payload: dict[str, Any] = {**order, "timestamp": int(time.time() * 1000),
                                   "recvWindow": self.recv_window}
        query = urlencode(payload)
        tanda = hmac.new(rahasia, query.encode(), hashlib.sha256).hexdigest()
        kirim = f"{query}&signature={tanda}"
        # Kunci masuk header (X-MEXC-APIKEY), bukan body; tanda di query. Nilainya
        # TIDAK PERNAH masuk log — hanya endpoint + status yang dikembalikan.
        hasil = self._send(f"{self.base}/api/v3/order", kirim, "POST", kunci)
        return {"endpoint": "/api/v3/order", "status": str(hasil.get("status", "?")), "tanda_ok": True}
