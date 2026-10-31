"""Regresi: scan harus menilai exposure dari posisi paper yang nyata.

Insiden 30 Okt 2026: verdict OPUSDT menulis `0/2 posisi` padahal
`paper_positions.json` berisi dua SHORT (SOL, ETH). Penyebabnya `scan()`
memanggil `evaluate()` tanpa `open_positions`, sehingga gate melihat daftar kosong.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from live_trading.config import Settings
from live_trading.signals import engine


class _Assessment:
    duplicate_of = None
    tier = "PREMIUM"
    allowed = True

    def summary(self) -> str:
        return "ok"


def _settings_dengan_posisi(tmp_path) -> Settings:
    s = Settings(home=tmp_path)
    s.state_dir.mkdir(parents=True, exist_ok=True)
    (s.state_dir / "paper_positions.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-10-30T17:00:00+07:00",
                "positions": [
                    {
                        "signal_id": "#A",
                        "pair": "SOLUSDT",
                        "direction": "SHORT",
                        "entry": 98.54,
                        "stop": 101.27,
                        "tp1": 95.80,
                        "tp2": 95.80,
                        "size_usd": 33.63,
                        "stop_init": 101.27,
                        "cost_bps": 20.0,
                        "opened_at": "2026-10-30T14:05:14+07:00",
                        "status": "open",
                        "source": "paper-crypto",
                        "note": "",
                        "strategi": "legacy-smc",
                    },
                    {
                        "signal_id": "#B",
                        "pair": "ETHUSDT",
                        "direction": "SHORT",
                        "entry": 2228.07,
                        "stop": 2275.04,
                        "tp1": 2181.09,
                        "tp2": 2181.09,
                        "size_usd": 43.33,
                        "stop_init": 2275.04,
                        "cost_bps": 20.0,
                        "opened_at": "2026-10-30T16:26:04+07:00",
                        "status": "open",
                        "source": "paper-crypto",
                        "note": "",
                        "strategi": "legacy-smc",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return s


def test_posisi_paper_crypto_membaca_state(tmp_path) -> None:
    posisi = engine.posisi_paper_crypto(_settings_dengan_posisi(tmp_path))
    assert len(posisi) == 2
    assert {p["direction"] for p in posisi} == {"SHORT"}


def test_scan_mengoper_posisi_paper_ke_evaluate(tmp_path, monkeypatch) -> None:
    settings = _settings_dengan_posisi(tmp_path)
    st = SimpleNamespace(price=100.0, atr_pct=2.0, bias={}, high_6h=101.0, low_6h=99.0)
    seen: dict[str, object] = {}

    monkeypatch.setattr(engine, "analyze", lambda *a, **k: st)
    monkeypatch.setattr(engine, "supported_direction", lambda st: "SHORT")
    monkeypatch.setattr(
        engine, "propose", lambda st, direction: {"entry": 100.0, "sl": 101.0, "tp1": 99.0}
    )

    def fake_evaluate(settings_, pair, direction, **kwargs):
        seen.update(kwargs)
        return st, {}, _Assessment()

    monkeypatch.setattr(engine, "evaluate", fake_evaluate)

    out = engine.scan(settings, ["FAKEUSDT"], client=object(), record=False)

    assert len(seen["open_positions"]) == 2
    assert out and out[0]["tier"] == "PREMIUM"
