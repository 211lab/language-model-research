from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research_operator.editorial import GENERATOR_COMMIT, _generator_revision, run_editorial_benchmark
from research_operator.config import Settings


class EditorialGeneratorTests(unittest.TestCase):
    def _exercise(self, batch: bool) -> tuple[list[list[str]], dict[str, str], Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        research = root / "research"
        research.mkdir()
        operator = research / "operator"
        runs = operator / "runs"
        seed = research / "seed.md"
        seed.write_text("fixed assessment source\n", encoding="utf-8")
        (research / "tools" / "gutenberg" / "ralph").mkdir(parents=True)
        (operator / "harness" / "automation" / "content_scoring").mkdir(parents=True)
        with patch.dict(os.environ, {
            "RESEARCH_ROOT": str(research),
            "OPERATOR_ROOT": str(operator),
            "OPERATOR_RUNS_ROOT": str(runs),
            "EDITORIAL_SEED_PATH": str(seed),
            "EDITORIAL_HARNESS_ROOT": str(operator / "harness"),
        }, clear=True):
            settings = Settings.from_env()

        commands: list[list[str]] = []
        generation_environment: dict[str, str] = {}

        def fake_run(command, *, cwd, environment=None, on_line=None):
            args = list(command)
            commands.append(args)
            if args[1:4] == ["-m", "gutenberg_ralph.interface", "generate"]:
                generation_environment.update(environment or {})
                output = Path(args[args.index("--output") + 1])
                source = Path(args[args.index("--source") + 1])
                output.mkdir(parents=True)
                (output / "CONTEXT.md").write_text("generated candidate", encoding="utf-8")
                (output / "manifest.json").write_text(json.dumps({
                    "purpose": "candidate-assessment",
                    "profile": "steadyburn-profile-v1",
                    "selected_tracks": ["core", "communications"],
                    "sources": [{"sha256": hashlib.sha256(source.read_bytes()).hexdigest()}],
                    "artifacts": [{"path": "CONTEXT.md", "sha256": "artifact-hash", "depends_on": ["source"]}],
                }), encoding="utf-8")
                (output / "usage.json").write_text(json.dumps({
                    "provider": "openrouter",
                    "model": "test/provider-model",
                    "batch": batch,
                    "cost_total_usd": 0.25,
                    "usage": [{"artifact": "CONTEXT.md", "model": "test/provider-model", "usage": {"cost": 0.25, "total_tokens": 10}}],
                    "batch_events": [{"status": "completed"}] if batch else [],
                }), encoding="utf-8")
            elif args[1:3] == ["-m", "content_scoring.interface"] and "--case-study" in args:
                case_study = Path(args[args.index("--case-study") + 1])
                (case_study / "CONTENT_SCORE.json").write_text(json.dumps({"content_score": 0.8, "confidence": 0.9, "evaluator": {"judge_model": "judge"}}), encoding="utf-8")

        job = {
            "id": "test-job",
            "run_id": "test-run",
            "payload": {
                "provider": "openrouter",
                "display_name": "Test model",
                "target_cost_ceiling_usd": 2.0,
                "judge_cost_ceiling_usd": 1.0,
                "openrouter_batch_mode": batch,
            },
        }
        with patch("research_operator.editorial._generator_revision", return_value=GENERATOR_COMMIT), patch(
            "research_operator.editorial.run_streaming", side_effect=fake_run
        ):
            run_editorial_benchmark(settings, job, effective_model_ref="test/provider-model", log=lambda _: None)
        published = research / "docs" / "model-comparisons" / "test-provider-model" / f"{settings.editorial_date}-{settings.editorial_slug}"
        return commands, generation_environment, published

    def test_generator_call_is_pinned_scored_and_evidenced_synchronously_by_default(self) -> None:
        commands, environment, published = self._exercise(False)
        command = commands[0]
        self.assertEqual(command[:4], ["python", "-m", "gutenberg_ralph.interface", "generate"])
        self.assertEqual(command[command.index("--profile") + 1], "steadyburn-profile-v1")
        self.assertEqual(command[command.index("--purpose") + 1], "candidate-assessment")
        self.assertEqual(command[command.index("--provider") + 1], "openrouter")
        self.assertEqual(command[command.index("--model") + 1], "test/provider-model")
        self.assertEqual(command[command.index("--provider-url") + 1], "https://openrouter.ai/api/v1")
        self.assertEqual(command[command.index("--image-provider") + 1], "openrouter")
        self.assertEqual(command[command.index("--image-model") + 1], "openai/gpt-5.4-image-2")
        self.assertEqual(command[command.index("--image-provider-url") + 1], "https://openrouter.ai/api/v1")
        self.assertFalse("--batch" in command)
        self.assertEqual(Path(command[command.index("--output") + 1]).parts[-2:], ("test-job", "editorial-candidate"))
        self.assertEqual(environment["BURN_MAX_COST_USD"], "2.0")
        self.assertTrue(any("content_scoring.interface" in item for item in commands))
        evidence = json.loads((published / "MODEL_COMPARISON.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["generator"]["commit"], GENERATOR_COMMIT)
        self.assertEqual(evidence["generator"]["profile"], "steadyburn-profile-v1")
        self.assertEqual(evidence["generator"]["source_sha256"], evidence["generator"]["manifest"]["sources"][0]["sha256"])
        self.assertEqual(evidence["generator"]["manifest"]["artifacts"][0]["sha256"], "artifact-hash")
        self.assertEqual(evidence["generator"]["usage"]["cost_total_usd"], 0.25)
        report = (published / "MODEL_COMPARISON.md").read_text(encoding="utf-8")
        self.assertIn(GENERATOR_COMMIT, report)
        self.assertIn("artifact-hash", report)
        self.assertIn('"cost": 0.25', report)
        self.assertTrue((published / "OPENROUTER_USAGE.jsonl").is_file())
        self.assertTrue((published / "CONTENT_SCORE.json").is_file())

    def test_batch_option_is_forwarded_only_when_enabled(self) -> None:
        commands, _, published = self._exercise(True)
        self.assertIn("--batch", commands[0])
        evidence = json.loads((published / "MODEL_COMPARISON.json").read_text(encoding="utf-8"))
        self.assertTrue(evidence["generator"]["batch"])
        self.assertEqual(evidence["generator"]["batch_events"], [{"status": "completed"}])

    def test_research_does_not_keep_active_production_generator(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        self.assertEqual(_generator_revision(repository / "tools" / "gutenberg"), GENERATOR_COMMIT)
        harness = repository / "operator" / "harness"
        self.assertFalse((harness / "scripts" / "burn-pipeline.py").exists())
        self.assertEqual(list((harness / "automation" / "burn_pipeline").glob("*.py")) if (harness / "automation" / "burn_pipeline").exists() else [], [])
        self.assertFalse((harness / "automation" / "pipelines" / "burn-all.template.yaml").exists())
        self.assertEqual(list((harness / "automation" / "prompts" / "burn").glob("*")) if (harness / "automation" / "prompts" / "burn").exists() else [], [])
        self.assertTrue((harness / "automation" / "content_scoring").is_dir())


if __name__ == "__main__":
    unittest.main()
