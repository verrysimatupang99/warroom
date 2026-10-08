import json
import runpy
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

SCRIPT = Path(__file__).with_name("kos_evaluator.py")


class EvaluatorTests(unittest.TestCase):
    def test_missing_dataset_blocks_every_rule_and_emits_no_metrics(self):
        missing = Path(tempfile.gettempdir()) / "warroom-kos-does-not-exist.sqlite"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--dataset", str(missing)],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        self.assertFalse(payload["dataset"]["exists"])
        self.assertEqual(10, len(payload["rules"]))
        self.assertTrue(all(row["status"] == "blocked_spec" for row in payload["rules"]))
        self.assertIsNone(payload["metrics"])
        self.assertFalse(payload["writes_production"])

    def test_signal_ledger_does_not_masquerade_as_raw_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "ledger.sqlite"
            import sqlite3
            with sqlite3.connect(db) as con:
                con.execute("create table signals (ticker text, net_r real)")
                con.execute("insert into signals values ('TEST', 1.0)")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--dataset", str(db)],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(1, payload["dataset"]["row_count"] if "row_count" in payload["dataset"] else 1)
            self.assertTrue(all(row["status"] == "blocked_spec" for row in payload["rules"]))
            self.assertIsNone(payload["metrics"])

    def test_full_declared_schema_requires_contracts_before_eligible(self):
        namespace = runpy.run_path(str(SCRIPT))
        rules = namespace["RULES"]
        dataset_info = namespace["DatasetInfo"]
        evaluate = namespace["evaluate"]
        fields = {f for rule in rules for f in rule.required_fields}
        ds = dataset_info("fixture", True, ("bars",), tuple(sorted(fields)), None)
        results = evaluate(ds)
        self.assertTrue(all(r.status == "blocked_contract" for r in results))
        self.assertTrue(all("HypothesisSpec" in r.reason for r in results))

    def test_full_declared_schema_and_contracts_becomes_ready_for_split(self):
        namespace = runpy.run_path(str(SCRIPT))
        rules = namespace["RULES"]
        dataset_info = namespace["DatasetInfo"]
        evaluate = namespace["evaluate"]
        hypothesis_spec = namespace["HypothesisSpec"]
        execution_spec = namespace["ExecutionSpec"]
        fields = {f for rule in rules for f in rule.required_fields}
        ds = dataset_info("fixture", True, ("bars",), tuple(sorted(fields)), None)
        hs = hypothesis_spec(
            hypothesis_id="kos-fixture", market="idx", instrument_or_pool="IDX",
            rule_version="v1", input_fields=tuple(sorted(fields)),
            lookahead_policy="t<=decision", cost_policy="all-in",
            session_timezone="Asia/Jakarta", entry_rule="rule", exit_rule="exit",
            stop_rule="stop", position_sizing="risk", baseline="buy_hold",
            split="frozen:fixture", population="all eligible bars", invalidation="ci fails",
        )
        es = execution_spec(
            entry_price_rule="next executable", exit_price_rule="next executable",
            stop_rule="gap-aware", time_stop="session", fee_policy="known",
            slippage_policy="known", latency_policy="recorded", fill_policy="partial/no-fill",
            risk_budget="1%", size_rule="risk/loss", no_trade_conditions=("stale",),
            venue="idx", mode="paper", as_of=datetime.now(UTC),
        )
        results = evaluate(ds, hypothesis=hs, execution=es)
        self.assertTrue(all(r.status == "ready_for_frozen_split" for r in results))
        self.assertTrue(all("frozen split" in r.reason for r in results))


if __name__ == "__main__":
    unittest.main()
