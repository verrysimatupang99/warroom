"""Loader strategi plug-and-play dari DI LUAR codebase.

Sifat platform: inti War Room tidak berubah bila strategi ditambah/dihapus.
Strategi eksternal (mis. hasil eksport EA MT5, modul Python pihak ketiga)
diletakkan sebagai file ``*.py`` di direktori plugin. Default:
``~/.warroom/strategies``; override via env ``WARROOM_STRATEGY_PATH``
(bisa beberapa path, dipisah ``os.pathsep``).

Kontrak file plugin (fail-closed — pelanggaran DITOLAK, bukan diabaikan):

- Definisikan atribut modul ``STRATEGY`` berupa class (atau factory callable
  tanpa argumen) yang menghasilkan instance ``BaseStrategy``.
- Nama file diawali ``_`` di-skip (mis. ``_rahasia.py``, utilitas bersama).
- File yang gagal dimuat / tidak punya ``STRATEGY`` / class-nya bukan
  ``BaseStrategy`` => error ``PluginStrategyError`` dengan nama file yang
  jelas; loader tidak pernah menebak dan tidak pernah mendaftar parsial.

Penggunaan::

    from warroom_core.strategy_plugins import load_external_strategies

    ringkasan = load_external_strategies()   # idempotent per proses
    # -> [{"key": "ea_scalper_v1", "name": "...", "source": "/path/file.py"}]

Key registrasi diambil dari atribut modul ``STRATEGY_KEY`` bila ada,
selain itu dari nama file tanpa ``.py`` (snake_case dipertahankan).
"""

from __future__ import annotations

import importlib.util
import inspect
import os
import sys
from pathlib import Path
from typing import Any

from warroom_core.forex.strategies.base import BaseStrategy
from warroom_core.forex.strategies.registry import pnp_registry

ENV_STRATEGY_PATH = "WARROOM_STRATEGY_PATH"
DEFAULT_DIR = Path.home() / ".warroom" / "strategies"

_loaded_sources: set[str] = set()


class PluginStrategyError(Exception):
    """Plugin strategi eksternal gagal dimuat / tidak memenuhi kontrak."""


def plugin_directories() -> list[Path]:
    raw = os.environ.get(ENV_STRATEGY_PATH, "").strip()
    if raw:
        parts = [p for p in (s.strip() for s in raw.split(os.pathsep)) if p]
    else:
        parts = [str(DEFAULT_DIR)]
    return [Path(p).expanduser() for p in parts]


def _instantiate(candidate: Any, source: str) -> BaseStrategy:
    obj = candidate() if inspect.isclass(candidate) is False else candidate
    try:
        instance = obj() if inspect.isclass(obj) else obj
    except Exception as exc:  # noqa: BLE001 - fail-closed dengan konteks file
        raise PluginStrategyError(f"{source}: gagal instansiasi STRATEGY: {exc}") from exc
    if not isinstance(instance, BaseStrategy):
        raise PluginStrategyError(
            f"{source}: STRATEGY bukan subclass BaseStrategy (dapat {type(instance).__name__})"
        )
    return instance


def load_module(path: Path) -> tuple[str, BaseStrategy]:
    """Muat satu file plugin -> (key, instance BaseStrategy). Fail-closed."""
    source = str(path)
    if not path.is_file():
        raise PluginStrategyError(f"{source}: bukan file")
    spec = importlib.util.spec_from_file_location(f"warroom_ext_{path.stem}_{abs(hash(source))}", path)
    if spec is None or spec.loader is None:
        raise PluginStrategyError(f"{source}: tidak dapat membuat spec import")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001
        raise PluginStrategyError(f"{source}: error eksekusi modul: {exc}") from exc

    candidate = getattr(module, "STRATEGY", None)
    if candidate is None:
        raise PluginStrategyError(f"{source}: tidak mendefinisikan atribut modul STRATEGY")
    key = str(getattr(module, "STRATEGY_KEY", "") or path.stem).strip()
    if not key:
        raise PluginStrategyError(f"{source}: STRATEGY_KEY kosong")
    return key, _instantiate(candidate, source)


def load_external_strategies(*, overwrite: bool = False) -> list[dict[str, str]]:
    """Muat semua plugin dari direktori terdaftar dan registrasi ke pnp_registry.

    Idempotent per sumber file dalam satu proses: file yang sudah dimuat
    di-skip kecuali ``overwrite=True``. File berawalan ``_`` di-skip.
    Error satu file TIDAK menghentikan file lain, tapi dikumpulkan dan
    dilempar sebagai satu ``PluginStrategyError`` di akhir (fail-closed:
    proses tahu plugin mana yang rusak).
    """
    ringkasan: list[dict[str, str]] = []
    errors: list[str] = []
    for directory in plugin_directories():
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.py")):
            if path.name.startswith("_"):
                continue
            resolved = str(path.resolve())
            if resolved in _loaded_sources and not overwrite:
                continue
            try:
                key, strategy = load_module(path)
            except PluginStrategyError as exc:
                errors.append(str(exc))
                continue
            pnp_registry.register(key, strategy)
            _loaded_sources.add(resolved)
            ringkasan.append(
                {
                    "key": key,
                    "name": getattr(strategy, "name", key),
                    "source": resolved,
                }
            )
    if errors:
        raise PluginStrategyError("plugin strategi gagal dimuat:\n- " + "\n- ".join(errors))
    return ringkasan
