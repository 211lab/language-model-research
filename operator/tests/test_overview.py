from __future__ import annotations

import unittest

from research_operator.config import Settings
from research_operator.overview import build_overview


class OverviewTests(unittest.TestCase):
    def test_published_data_exposes_identity_readability_and_assistant_cost_fields(self) -> None:
        data = build_overview(Settings.from_env())
        self.assertGreater(data["editorial"]["model_count"], 0)
        self.assertGreater(data["assistant"]["model_count"], 0)
        local_editorial = next(
            item for item in data["editorial"]["models"] if item.get("cost_source") == "local"
        )
        self.assertTrue(str(local_editorial["identity_key"]).startswith("local:"))
        self.assertIn("bundle total", local_editorial["readability"])
        self.assertTrue(
            all("provider_reported_cost_usd" in item for item in data["assistant"]["models"])
        )


if __name__ == "__main__":
    unittest.main()
