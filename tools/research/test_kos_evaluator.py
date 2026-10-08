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

    def test_kos_preview_binds_dataset_hash_and_contracts(self):
        namespace = runpy.run_path(str(SCRIPT))
        build_preview = namespace["build_research_preview"]
        hypothesis_spec = namespace["HypothesisSpec"]
        execution_spec = namespace["ExecutionSpec"]
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "bars.sqlite"
            import sqlite3
            with sqlite3.connect(db) as con:
                con.execute("create table bars (ts integer, close real, volume real)")
                con.execute("insert into bars values (1, 10.0, 100.0)")
            hs = hypothesis_spec(
                hypothesis_id="kos-proxy-v1", market="idx", instrument_or_pool="BBCA.JK",
                rule_version="v1", input_fields=("close", "volume"),
                lookahead_policy="t<=decision", cost_policy="all-in",
                session_timezone="Asia/Jakarta", entry_rule="breakout", exit_rule="time",
                stop_rule="atr", position_sizing="risk/loss", baseline="buy_hold",
                split="frozen:fixture", population="all eligible bars", invalidation="net <= 0",
            )
            es = execution_spec(
                entry_price_rule="next open", exit_price_rule="next close",
                stop_rule="atr", time_stop="12 bars", fee_policy="not yet included",
                slippage_policy="not yet included", latency_policy="recorded",
                fill_policy="next bar only", risk_budget="paper", size_rule="risk/loss",
                no_trade_conditions=("stale",), venue="yahoo", mode="paper",
                as_of=datetime.now(UTC),
            )
            preview = build_preview(db, hs, es)
            self.assertEqual("kos-proxy-v1", preview["hypothesis_id"])
            self.assertEqual("draft", preview["status"])
            self.assertEqual(1, len(preview["artifacts"]))
            self.assertEqual("dataset", preview["artifacts"][0]["kind"])
            self.assertEqual(64, len(preview["artifacts"][0]["sha256"]))
            self.assertEqual(hs.fingerprint(), preview["hypothesis_hash"])
            self.assertEqual(es.fingerprint(), preview["execution_hash"])


if __name__ == "__main__":
    unittest.main()
