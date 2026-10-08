"""Fail-closed King of Scalper research evaluator.

This module does not fabricate broker-history or indicator inputs. It inspects a local
research dataset and returns an explicit status for each rule. It is intentionally
research-only: it never writes the production ledger or emits a trading signal.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# Keep the research CLI runnable from the repository checkout as well as uv/systemd.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_CORE_SRC = _REPO_ROOT / "packages" / "core" / "src"
_DOMAIN_SRC = _REPO_ROOT / "packages" / "live-trading" / "src"
for _src in (_DOMAIN_SRC, _CORE_SRC):
    if str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

_SPECS_PATH = _CORE_SRC / "warroom_core" / "specs.py"
_specs_loader = importlib.util.spec_from_file_location("warroom_research_specs", _SPECS_PATH)
assert _specs_loader and _specs_loader.loader
_specs_module = importlib.util.module_from_spec(_specs_loader)
sys.modules[_specs_loader.name] = _specs_module
_specs_loader.loader.exec_module(_specs_module)
ExecutionSpec = _specs_module.ExecutionSpec
HypothesisSpec = _specs_module.HypothesisSpec


@dataclass(frozen=True)
class RuleSpec:
    name: str
    required_fields: tuple[str, ...]
    timeframe: str


RULES = (
    RuleSpec("Bandar Blitz", ("top_broker_hist", "volume", "close"), "1m"),
    RuleSpec("Flash Cuan", ("rsi", "close", "top_broker_hist", "volume"), "1m"),
    RuleSpec("Gorilla Punch", ("close", "rsi", "top_broker_hist", "volume", "daily_close"), "5m+daily"),
    RuleSpec("Nitro Push", ("close", "daily_close", "daily_sma_close"), "5m+daily"),
    RuleSpec("Pump Hunter", ("daily_volume", "daily_sma_volume", "daily_close", "top_broker_hist"), "daily"),
    RuleSpec("Precision Hit", ("close", "hhv_high", "volume", "top_broker_hist"), "1m"),
    RuleSpec("Rocket Scalper", ("close", "volume", "obv", "top_broker_hist"), "1m"),
    RuleSpec("Shadow Entry", ("close", "top_broker_hist", "volume"), "5m"),
    RuleSpec("Spike Ride", ("close", "hhv_high", "top_broker_hist", "volume"), "5m"),
    RuleSpec("Tiger Jump", ("close", "volume", "top_broker_hist", "rsi"), "1m"),
)


@dataclass(frozen=True)
class DatasetInfo:
    path: str
    exists: bool
    tables: tuple[str, ...] = ()
    columns: tuple[str, ...] = ()
    row_count: int | None = None


@dataclass(frozen=True)
class RuleResult:
    rule: str
    timeframe: str
    status: str
    missing_fields: tuple[str, ...]
    reason: str


def inspect_sqlite(path: Path) -> DatasetInfo:
    if not path.is_file():
        return DatasetInfo(str(path), False)
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as con:
        tables = tuple(r[0] for r in con.execute("select name from sqlite_master where type='table'"))
        columns: set[str] = set()
        count: int | None = None
        for table in tables:
            columns.update(r[1] for r in con.execute(f'pragma table_info("{table}")'))
        if "signals" in tables:
            count = int(con.execute("select count(*) from signals").fetchone()[0])
    return DatasetInfo(str(path), True, tables, tuple(sorted(columns)), count)


def evaluate(
    dataset: DatasetInfo,
    *,
    hypothesis: HypothesisSpec | None = None,
    execution: ExecutionSpec | None = None,
) -> list[RuleResult]:
    fields = set(dataset.columns)
    results: list[RuleResult] = []
    for spec in RULES:
        missing = tuple(field for field in spec.required_fields if field not in fields)
        if missing:
            results.append(RuleResult(
                spec.name,
                spec.timeframe,
                "blocked_spec",
                missing,
                "dataset lokal tidak menyediakan semua input formula; tidak menghitung proxy",
            ))
        elif hypothesis is None or execution is None:
            results.append(RuleResult(
                spec.name,
                spec.timeframe,
                "blocked_contract",
                (),
                "HypothesisSpec dan ExecutionSpec wajib sebelum evaluasi eligible",
            ))
        else:
            results.append(RuleResult(
                spec.name,
                spec.timeframe,
                "ready_for_frozen_split",
                (),
                "input shape dan contracts tersedia; frozen split dan replay policy masih wajib",
            ))
    return results


def build_research_preview(
    dataset_path: Path,
    hypothesis: HypothesisSpec,
    execution: ExecutionSpec,
) -> dict[str, object]:
    """Build a research-only persistence preview and hash the exact dataset artifact."""
    if not dataset_path.is_file():
        raise ValueError("dataset artifact tidak ditemukan")
    if execution.mode == "live":
        raise ValueError("research preview menolak mode live")
    digest = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    return {
        "research_key": hypothesis.hypothesis_id,
        "status": "draft",
        "hypothesis_id": hypothesis.hypothesis_id,
        "hypothesis_version": hypothesis.rule_version,
        "hypothesis": hypothesis.to_dict(),
        "hypothesis_hash": hypothesis.fingerprint(),
        "execution": execution.to_dict(),
        "execution_hash": execution.fingerprint(),
        "provenance": {
            "source": "kos_evaluator",
            "dataset_path": str(dataset_path),
            "dataset_sha256": digest,
        },
        "artifacts": [{"kind": "dataset", "uri": str(dataset_path), "sha256": digest}],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed research-only KOS evaluator")
    parser.add_argument("--dataset", type=Path, default=Path("/home/admin/live-trading/state/idx_ledger.db"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    dataset = inspect_sqlite(args.dataset)
    result = {
        "mode": "research_only",
        "writes_production": False,
        "dataset": asdict(dataset),
        "rules": [asdict(item) for item in evaluate(dataset)],
        "metrics": None,
        "note": "No metrics are emitted until raw inputs and a frozen split are present.",
    }
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
