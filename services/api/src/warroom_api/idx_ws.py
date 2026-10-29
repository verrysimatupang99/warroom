"""Stream running-trade IDX lewat WebSocket, untuk dipakai router.

Kenapa lapisan terpisah dari idx_edge: REST berbayar per panggilan (anggaran 1.000/hari),
sedangkan WebSocket tidak. Data transaksi real-time karena itu diambil dari stream dan
disimpan sebagai snapshot terakhir, bukan ditarik berulang lewat REST.

Endpoint yang benar (hasil uji 29 Okt 2026): wss://stock.arjum.com/ws/running-trade
Autentikasi WAJIB lewat header `X-API-Key`. Tanpa header, server langsung mengirim close
frame 0x88 kode 11 — bukan pesan galat yang jelas.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import ssl
import struct
import threading
import time
from pathlib import Path
from typing import Any

HOST = "stock.arjum.com"
PATH = "/ws/running-trade"
SIMPAN = Path("/var/lib/warroom/idx-cache/running-trade.json")
KEY_ENV = "WARROOM_IDX_API_KEY"
KEY_FILE = Path("/etc/warroom/idx.env")

_benang: threading.Thread | None = None
_kunci_lock = threading.Lock()


def _kunci() -> str:
    nilai = os.environ.get(KEY_ENV, "").strip()
    if nilai:
        return nilai
    if KEY_FILE.exists():
        for baris in KEY_FILE.read_text().splitlines():
            if baris.strip().startswith(KEY_ENV + "="):
                return baris.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(f"Kunci API IDX belum dipasang ({KEY_FILE} atau env {KEY_ENV}).")


def _urai(data: bytes) -> tuple[int, bytes, int]:
    """Urai satu frame WebSocket. Kembalikan (opcode, payload, panjang terpakai)."""
    if len(data) < 2:
        return -1, b"", 0
    opcode = data[0] & 0x0F
    bertopeng = bool(data[1] & 0x80)
    panjang = data[1] & 0x7F
    idx = 2
    if panjang == 126:
        if len(data) < 4:
            return -1, b"", 0
        panjang = struct.unpack(">H", data[2:4])[0]
        idx = 4
    elif panjang == 127:
        if len(data) < 10:
            return -1, b"", 0
        panjang = struct.unpack(">Q", data[2:10])[0]
        idx = 10
    mask = None
    if bertopeng:
        if len(data) < idx + 4:
            return -1, b"", 0
        mask = data[idx:idx + 4]
        idx += 4
    if len(data) < idx + panjang:
        return -1, b"", 0
    isi = data[idx:idx + panjang]
    if mask:
        isi = bytes(b ^ mask[i % 4] for i, b in enumerate(isi))
    return opcode, isi, idx + panjang


def sambung(detik_maks: float = 600.0, saat_pesan=None) -> int:
    """Sambung ke stream dan teruskan tiap pesan JSON ke callback."""
    kunci = _kunci()
    ctx = ssl.create_default_context()
    k = base64.b64encode(os.urandom(16)).decode()
    diterima = 0
    mulai = time.time()

    with socket.create_connection((HOST, 443), timeout=25) as s:
        with ctx.wrap_socket(s, server_hostname=HOST) as ss:
            ss.sendall(
                (
                    f"GET {PATH} HTTP/1.1\r\nHost: {HOST}\r\nUpgrade: websocket\r\n"
                    f"Connection: Upgrade\r\nSec-WebSocket-Key: {k}\r\n"
                    f"Sec-WebSocket-Version: 13\r\nOrigin: https://{HOST}\r\n"
                    f"X-API-Key: {kunci}\r\n\r\n"
                ).encode()
            )
            buf = b""
            while b"\r\n\r\n" not in buf:
                potong = ss.recv(4096)
                if not potong:
                    raise RuntimeError("koneksi ditutup saat handshake")
                buf += potong
            if b" 101 " not in buf.split(b"\r\n")[0]:
                raise RuntimeError(buf.decode(errors="replace")[:200])
            sisa = buf.split(b"\r\n\r\n", 1)[1]

            ss.settimeout(45)
            while time.time() - mulai < detik_maks:
                try:
                    potong = ss.recv(65536)
                except socket.timeout:
                    continue
                if not potong:
                    break
                sisa += potong
                while True:
                    opcode, isi, pakai = _urai(sisa)
                    if opcode == -1:
                        break
                    sisa = sisa[pakai:]
                    if opcode == 8:
                        return diterima
                    if opcode == 9:
                        ss.sendall(bytes([0x8A, 0x80]) + os.urandom(4))
                        continue
                    if opcode in (1, 2):
                        diterima += 1
                        if saat_pesan:
                            try:
                                saat_pesan(json.loads(isi.decode(errors="replace")))
                            except (ValueError, TypeError):
                                pass
    return diterima


def _simpan(data: dict[str, Any]) -> None:
    try:
        SIMPAN.parent.mkdir(parents=True, exist_ok=True)
        SIMPAN.write_text(json.dumps({"ts": time.time(), "data": data}, ensure_ascii=False))
    except OSError:
        pass


def snapshot() -> dict[str, Any]:
    """Snapshot terakhir dari berkas. Tidak membuka koneksi, tidak memakai kuota."""
    if not SIMPAN.exists():
        return {
            "tersedia": False,
            "alasan": "Belum ada snapshot. Pendengar latar belum pernah menerima pesan.",
        }
    try:
        isi = json.loads(SIMPAN.read_text())
    except (OSError, ValueError):
        return {"tersedia": False, "alasan": "Berkas snapshot rusak."}
    umur = time.time() - isi.get("ts", 0)
    data = isi.get("data", {})
    if data.get("type") == "galat":
        return {"tersedia": False, "alasan": data.get("pesan", "galat tidak diketahui"), "umur_detik": round(umur, 1)}
    return {"tersedia": True, "umur_detik": round(umur, 1), **data}


def _loop() -> None:
    while True:
        try:
            sambung(detik_maks=3600, saat_pesan=_simpan)
        except Exception as exc:  # noqa: BLE001 - semua penyebab dicoba ulang
            _simpan({"type": "galat", "pesan": str(exc)})
        time.sleep(15)


def mulai_latar() -> bool:
    """Nyalakan pendengar latar sekali saja. Balik True kalau baru dinyalakan."""
    global _benang
    with _kunci_lock:
        if _benang and _benang.is_alive():
            return False
        _benang = threading.Thread(target=_loop, name="idx-ws", daemon=True)
        _benang.start()
        return True


def status_benang() -> str:
    return "hidup" if (_benang and _benang.is_alive()) else "mati"
