"""P3-T5: pemindahan penilai pod ke layanan AI War Room (opt-in) + fallback lokal.

Yang dibuktikan:
1. `WARROOM_AI_URL` disetel & layanan menjawab → nilai diambil dari War Room (bukan lokal).
2. Layanan mati/gagal → **fallback** ke jalur lokal nutaraline (kartu pod tetap terisi).
3. Tanpa `WARROOM_AI_URL` → perilaku lama tidak berubah (nol panggilan ke War Room).
4. Balasan `status != ok` (mis. `insufficient`) tidak dianggap nilai.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from live_trading.pods import nilai


@pytest.fixture
def warroom_palsu(monkeypatch: pytest.MonkeyPatch):
    """Server HTTP kecil yang meniru `/api/v1/ai/verifier`."""
    jawaban: dict[str, object] = {"status": "ok", "setuju": True, "catatan": "dari war room"}
    dipanggil: list[dict[str, object]] = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 — nama wajib dari BaseHTTPRequestHandler
            panjang = int(self.headers.get("Content-Length", 0))
            isi = json.loads(self.rfile.read(panjang) or b"{}")
            dipanggil.append({"path": self.path, "body": isi,
                              "token": self.headers.get("X-Warroom-Token")})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(jawaban).encode())

        def log_message(self, *a: object) -> None:  # senyapkan log server
            return

    server = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("WARROOM_AI_URL", f"http://127.0.0.1:{server.server_port}")
    yield jawaban, dipanggil
    server.shutdown()


def test_pakai_war_room_saat_aktif(warroom_palsu, monkeypatch: pytest.MonkeyPatch) -> None:
    jawaban, dipanggil = warroom_palsu
    monkeypatch.setattr(nilai, "tanya", lambda *a, **k: pytest.fail("jalur lokal tidak boleh dipakai"))
    hasil = nilai.nilai_pod("alpha", ["n=120", "win=71%"])
    assert hasil == {"setuju": True, "catatan": "dari war room"}
    assert dipanggil and dipanggil[0]["path"] == "/api/v1/ai/verifier"
    assert dipanggil[0]["body"]["nama"] == "alpha"
    assert dipanggil[0]["body"]["klaim"] == ["n=120", "win=71%"]
    assert jawaban["setuju"] is True


def test_kirim_token_layanan_bila_ada(warroom_palsu, monkeypatch: pytest.MonkeyPatch) -> None:
    _, dipanggil = warroom_palsu
    monkeypatch.setenv("WARROOM_SERVICE_TOKEN", "token-uji")
    nilai.nilai_pod("alpha", ["n=1"])
    assert dipanggil[0]["token"] == "token-uji"


def test_fallback_lokal_saat_layanan_mati(monkeypatch: pytest.MonkeyPatch) -> None:
    """Port tertutup → urllib gagal → jalur lokal dipakai (tidak melempar, tidak None)."""
    monkeypatch.setenv("WARROOM_AI_URL", "http://127.0.0.1:9")  # port discard: pasti gagal
    lokal = '{"setuju": false, "catatan": "lokal"}'
    monkeypatch.setattr(nilai, "tanya", lambda *a, **k: lokal)
    assert nilai.nilai_pod("beta", ["n=10"]) == {"setuju": False, "catatan": "lokal"}


def test_tanpa_url_perilaku_lama(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WARROOM_AI_URL", raising=False)
    dipanggil: list[str] = []
    lokal = '{"setuju": true, "catatan": "x"}'
    monkeypatch.setattr(nilai, "tanya", lambda prompt, *a, **k: dipanggil.append(prompt) or lokal)
    assert nilai.nilai_pod("gamma", ["n=5"]) == {"setuju": True, "catatan": "x"}
    assert len(dipanggil) == 1


def test_status_tidak_ok_diabaikan(warroom_palsu, monkeypatch: pytest.MonkeyPatch) -> None:
    jawaban, _ = warroom_palsu
    jawaban.update({"status": "insufficient", "setuju": None, "catatan": None})
    lokal = '{"setuju": true, "catatan": "lokal"}'
    monkeypatch.setattr(nilai, "tanya", lambda *a, **k: lokal)
    assert nilai.nilai_pod("delta", ["n=7"]) == {"setuju": True, "catatan": "lokal"}