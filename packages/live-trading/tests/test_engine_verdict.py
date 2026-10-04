"""Uji verdict per aturan: rekam + ringkas tahan baris korup."""

import json


def _settings(tmp_path):
    from live_trading.config import get_settings

    s = get_settings()
    s.home = tmp_path
    return s


def test_rekam_dan_ringkas_per_aturan(tmp_path):
    from live_trading.signals import engine

    s = _settings(tmp_path)
    (tmp_path / "state").mkdir(exist_ok=True)
    (tmp_path / "state" / "verdicts.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "pair": "BTCUSDT",
                        "allowed": True,
                        "rules": [
                            {"rule": "atr_min", "ok": True},
                            {"rule": "freshness", "ok": True},
                        ],
                    }
                ),
                json.dumps(
                    {
                        "pair": "ETHUSDT",
                        "allowed": False,
                        "rules": [
                            {"rule": "atr_min", "ok": False},
                            {"rule": "freshness", "ok": True},
                        ],
                    }
                ),
                "baris korup {{{",
                json.dumps({"pair": "X", "allowed": False, "rules": [{"ok": True}]}),
            ]
        ),
        encoding="utf-8",
    )
    out = engine.summarize_verdicts(s)
    assert out["total"] == 3
    assert out["allowed"] == 1
    assert out["per_rule"]["atr_min"] == {"lolos": 1, "gagal": 1}
    assert out["per_rule"]["freshness"] == {"lolos": 2, "gagal": 0}
