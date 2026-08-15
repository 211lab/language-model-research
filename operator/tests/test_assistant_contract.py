from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research_operator.assistant import _sha256, _validate_contract, run_luna_preflight
from research_operator.config import Settings


class AssistantPublicationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings.from_env()
        self.fixture = self.settings.research_root / "tools" / "benchmark" / "fixtures" / "base_environment.json"
        self.tasks = self.settings.research_root / "tools" / "benchmark" / "fixtures" / "tasks.json"

    def _results(self, status: str = "ok", tasks_total: int = 1) -> tuple[dict, dict]:
        assistant = {
            "metadata": {
                "seed": 42,
                "max_tokens_per_model_turn": 768,
                "fixture_sha256": _sha256(self.fixture),
                "tasks_sha256": _sha256(self.tasks),
                "selected_models": ["provider/model"],
                "selected_tasks": ["task-1"],
            },
            "model_summaries": [
                {"model": "provider/model", "status": status, "tasks_total": tasks_total}
            ],
        }
        latency = {"metadata": {"seed": 42, "selected_models": ["provider/model"]}}
        return assistant, latency

    def test_complete_fixed_contract_is_publishable(self) -> None:
        assistant, latency = self._results()
        _validate_contract(self.settings, assistant, latency)

    def test_partial_contract_is_not_publishable(self) -> None:
        assistant, latency = self._results(status="partial")
        with self.assertRaisesRegex(RuntimeError, "not fully completed"):
            _validate_contract(self.settings, assistant, latency)

    def test_luna_preflight_covers_streaming_latency_and_one_assistant_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = replace(self.settings, runs_root=Path(directory))
            commands: list[list[str]] = []

            def fake_run(command: list[str], **_kwargs: object) -> None:
                commands.append(command)
                if "--validate" in command:
                    return
                output = Path(command[command.index("--output-dir") + 1])
                output.mkdir(parents=True, exist_ok=True)
                if any(Path(str(value)).name == "benchmark.py" for value in command):
                    (output / "results.json").write_text(
                        json.dumps({"results": [{"status": "ok"}]}), encoding="utf-8"
                    )
                else:
                    (output / "results.json").write_text(
                        json.dumps(
                            {
                                "metadata": {"provider_reported_cost_usd": 0.02},
                                "model_summaries": [{"status": "ok"}],
                            }
                        ),
                        encoding="utf-8",
                    )

            with patch("research_operator.assistant.run_streaming", side_effect=fake_run):
                result = run_luna_preflight(settings, "job", lambda _line: None)

            self.assertEqual(result["latency_status"], "ok")
            self.assertEqual(result["run_status"], "ok")
            paid_commands = [command for command in commands if "--validate" not in command]
            self.assertEqual(len(paid_commands), 2)
            self.assertTrue(all("--require-reported-cost" in command for command in paid_commands))
            ledgers = [command[command.index("--usage-log") + 1] for command in paid_commands]
            self.assertEqual(ledgers[0], ledgers[1])


if __name__ == "__main__":
    unittest.main()
