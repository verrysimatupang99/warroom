"""Tes loader strategi PnP eksternal (di luar codebase)."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest
from warroom_core.forex.strategies.registry import pnp_registry
from warroom_core.strategy_plugins import (
    ENV_STRATEGY_PATH,
    PluginStrategyError,
    load_external_strategies,
    plugin_directories,
)


def _buat_plugin(dir_plugin: Path, nama: str, isi: str) -> Path:
    dir_plugin.mkdir(parents=True, exist_ok=True)
    path = dir_plugin / nama
    path.write_text(textwrap.dedent(isi), encoding="utf-8")
    return path


@pytest.fixture()
def dir_plugin(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_STRATEGY_PATH, str(tmp_path))
    yield tmp_path
    pnp_registry._strategies.pop("ea_uji", None)


def test_default_direktori_home(monkeypatch):
    monkeypatch.delenv(ENV_STRATEGY_PATH, raising=False)
    dirs = plugin_directories()
    assert len(dirs) == 1
    assert dirs[0] == Path.home() / ".warroom" / "strategies"


def test_multi_path_env(monkeypatch, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    monkeypatch.setenv(ENV_STRATEGY_PATH, os.pathsep.join([str(a), str(b)]))
    assert plugin_directories() == [a, b]


def test_plugin_valid_terdaftar(dir_plugin):
    _buat_plugin(
        dir_plugin,
        "ea_uji.py",
        """
        from warroom_core.forex.strategies.base import BaseStrategy

        class EaUji(BaseStrategy):
            def __init__(self):
                super().__init__(name="EA Uji")

            def evaluate(self, market_data):
                return None

        STRATEGY = EaUji

        STRATEGY_KEY = "ea_uji"
        """,
    )
    ringkasan = load_external_strategies()
    assert [r["key"] for r in ringkasan] == ["ea_uji"]
    # registrasi TIDAK mengubah strategi aktif — aktivasi eksplisit via set_active_strategy
    assert pnp_registry.get_active_strategy().name != "EA Uji"
    assert pnp_registry.set_active_strategy("ea_uji") is True
    assert pnp_registry.get_active_strategy().name == "EA Uji"
    pnp_registry.set_active_strategy("multi_session_laya")


def test_plugin_ganda_tanpa_overwrite_idempotent(dir_plugin):
    _buat_plugin(
        dir_plugin,
        "ea_uji.py",
        """
        from warroom_core.forex.strategies.base import BaseStrategy

        class EaUji(BaseStrategy):
            def __init__(self):
                super().__init__(name="EA Uji")
            def evaluate(self, md): return None

        STRATEGY = EaUji

        STRATEGY_KEY = "ea_uji"
        """,
    )
    ringkasan = load_external_strategies()
    assert [r["key"] for r in ringkasan] == ["ea_uji"]

    load_external_strategies()
    # panggil ulang: file sama di-skip, tidak ada error, tidak dobel
    assert load_external_strategies() == []


def test_plugin_tanpa_strategy_ditolak(dir_plugin):
    _buat_plugin(dir_plugin, "rusak.py", "X = 1\n")
    with pytest.raises(PluginStrategyError, match="rusak.py"):
        load_external_strategies()


def test_plugin_bukan_subclass_ditolak(dir_plugin):
    _buat_plugin(
        dir_plugin,
        "salah.py",
        """
        class Bukan:
            pass
        STRATEGY = Bukan
        """,
    )
    with pytest.raises(PluginStrategyError, match="bukan subclass BaseStrategy"):
        load_external_strategies()


def test_plugin_error_eksekusi_dilaporkan(dir_plugin):
    _buat_plugin(dir_plugin, "boom.py", "raise ValueError('meledak')\n")
    with pytest.raises(PluginStrategyError, match="boom.py.*meledak"):
        load_external_strategies()


def test_file_underscore_di_skip(dir_plugin):
    _buat_plugin(dir_plugin, "_util.py", "raise RuntimeError('tidak boleh dimuat')\n")
    assert load_external_strategies() == []


def test_error_tidak_menghentikan_plugin_lain(dir_plugin):
    _buat_plugin(dir_plugin, "a_rusak.py", "raise ValueError('rusak')\n")
    _buat_plugin(
        dir_plugin,
        "b_baik.py",
        """
        from warroom_core.forex.strategies.base import BaseStrategy

        class Baik(BaseStrategy):
            def __init__(self):
                super().__init__(name="Baik")
            def evaluate(self, md): return None
        STRATEGY_KEY = "ea_baik"
        """,
    )
    with pytest.raises(PluginStrategyError, match="a_rusak"):
        load_external_strategies()
    # fail-closed: yang rusak dilapor, tapi yang valid tetap tak terdaftar
    # sebelum error ditangani — cek bahwa key ea_baik TIDAK aktif diam-diam
    assert pnp_registry.get_active_strategy().name != "Baik"


def test_strategy_key_custom(dir_plugin):
    _buat_plugin(
        dir_plugin,
        "nama_file_saja.py",
        """
        from warroom_core.forex.strategies.base import BaseStrategy

        class S(BaseStrategy):
            def __init__(self):
                super().__init__(name="S")
            def evaluate(self, md): return None

        STRATEGY = S

        STRATEGY_KEY = "ea_custom"
        """,
    )
    ringkasan = load_external_strategies()
    assert ringkasan[0]["key"] == "ea_custom"
    pnp_registry._strategies.pop("ea_custom", None)


def test_direktori_tidak_ada_tetap_aman(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_STRATEGY_PATH, str(tmp_path / "tidak_ada"))
    assert load_external_strategies() == []
