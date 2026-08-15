from __future__ import annotations

import sys
from pathlib import Path
import tempfile
import unittest


BENCHMARK_ROOT = Path(__file__).resolve().parents[2] / "tools" / "benchmark"
sys.path.insert(0, str(BENCHMARK_ROOT))

from cost_budget import CostBudget, CostBudgetExceeded  # noqa: E402


class CostBudgetTests(unittest.TestCase):
    def test_crossing_ceiling_is_recorded_then_halts_remaining_requests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "usage.jsonl"
            budget = CostBudget(max_cost_usd=0.01, usage_log=ledger, require_reported_cost=True)
            with self.assertRaises(CostBudgetExceeded):
                budget.record_response({"cost": 0.011}, model="provider/model", workload="assistant:task")
            self.assertAlmostEqual(budget.spent_usd, 0.011)
            self.assertTrue(ledger.exists())
            with self.assertRaises(CostBudgetExceeded):
                budget.authorize_request(model="provider/model", workload="assistant:next-task")

    def test_missing_provider_cost_fails_closed(self) -> None:
        budget = CostBudget(max_cost_usd=1, require_reported_cost=True)
        with self.assertRaises(CostBudgetExceeded):
            budget.record_response({"prompt_tokens": 4}, model="provider/model", workload="assistant:task")

    def test_shared_ledger_carries_spend_across_stages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "usage.jsonl"
            latency = CostBudget(max_cost_usd=0.05, usage_log=ledger, require_reported_cost=True)
            latency.record_response({"cost": 0.02}, model="provider/model", workload="latency:cold")
            assistant = CostBudget(max_cost_usd=0.05, usage_log=ledger, require_reported_cost=True)
            self.assertAlmostEqual(assistant.spent_usd, 0.02)
            assistant.record_response({"cost": 0.02}, model="provider/model", workload="assistant:task")
            self.assertAlmostEqual(assistant.spent_usd, 0.04)


if __name__ == "__main__":
    unittest.main()
