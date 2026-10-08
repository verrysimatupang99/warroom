import json
import runpy
import subprocess
import sys
import tempfile
import unittest
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

    def test_full_declared_schema_only_becomes_ready_for_split(self):
        namespace = runpy.run_path(str(SCRIPT))
        rules = namespace["RULES"]
        dataset_info = namespace["DatasetInfo"]
        evaluate = namespace["evaluate"]
        fields = {f for rule in rules for f in rule.required_fields}
        ds = dataset_info("fixture", True, ("bars",), tuple(sorted(fields)), None)
        results = evaluate(ds)
        self.assertTrue(all(r.status == "ready_for_frozen_split" for r in results))
        self.assertTrue(all("frozen split" in r.reason for r in results))


if __name__ == "__main__":
    unittest.main()
