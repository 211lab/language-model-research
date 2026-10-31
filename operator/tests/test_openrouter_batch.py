from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx


AUTOMATION_ROOT = Path(__file__).resolve().parents[1] / "harness" / "automation"
sys.path.insert(0, str(AUTOMATION_ROOT))

from burn_pipeline.application import BurnPipeline
from burn_pipeline.domain import BurnContext, GeneratedArtifact, GenerationModality, InferenceRequest, PipelineSpec, ProviderConfig, ProviderKind, StepSpec
from burn_pipeline.infrastructure import ChatCompletionsAdapter


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("bad status", request=httpx.Request("GET", "https://example.test"), response=httpx.Response(self.status_code))

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, *, post=None, gets=None):
        self.post_result = post
        self.get_results = list(gets or [])
        self.posts = []
        self.get_urls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        if isinstance(self.post_result, Exception):
            raise self.post_result
        return self.post_result

    def get(self, url, **kwargs):
        self.get_urls.append(url)
        return self.get_results.pop(0)


def response(text, cost):
    return {"model": "openai/gpt-6-luna", "choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 2, "completion_tokens": 3, "cost": cost}}


class OpenRouterBatchTests(unittest.TestCase):
    def test_default_adapter_keeps_synchronous_endpoint(self):
        client = FakeClient(post=FakeResponse(response("sync", 0.01)))
        adapter = ChatCompletionsAdapter(providerUrl="https://openrouter.ai/api/v1", apiKey="secret", model="openai/gpt-6-luna")
        with patch("burn_pipeline.infrastructure.httpx.Client", return_value=client):
            self.assertEqual(adapter.generate(InferenceRequest(prompt="private", output_format="markdown")).text, "sync")
        self.assertEqual(client.posts[0][0], "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(client.posts[0][1]["headers"]["Authorization"], "Bearer secret")

    def test_batch_polls_maps_by_custom_id_and_records_usage_once(self):
        results = [
            {"custom_id": "second", "response": {"status_code": 200, "body": response("B", 0.02)}},
            {"custom_id": "first", "response": {"status_code": 200, "body": response("A", 0.01)}},
        ]
        client = FakeClient(
            post=FakeResponse({"id": "batch-123", "status": "queued"}),
            gets=[FakeResponse({"id": "batch-123", "status": "in_progress", "request_counts": {"total": 2, "completed": 1, "failed": 0}}), FakeResponse({"id": "batch-123", "status": "completed", "request_counts": {"total": 2, "completed": 2, "failed": 0}, "data": results})],
        )
        adapter = ChatCompletionsAdapter(providerUrl="https://openrouter.ai/api/v1", apiKey="secret", model="openai/gpt-6-luna", batch_enabled=True, retry_wait_seconds=0)
        with tempfile.TemporaryDirectory() as directory:
            usage_path = Path(directory) / "usage.jsonl"
            evidence_path = Path(directory) / "batch.jsonl"
            progress = io.StringIO()
            with patch.dict(os.environ, {"BURN_USAGE_LOG": str(usage_path), "BURN_BATCH_EVIDENCE": str(evidence_path), "BURN_OPENROUTER_BATCH_POLL_INTERVAL_SECONDS": "7"}), patch("burn_pipeline.infrastructure.httpx.Client", return_value=client), patch("burn_pipeline.infrastructure.time.sleep") as sleep, contextlib.redirect_stdout(progress):
                generated = adapter.generate_batch([
                    ("first", InferenceRequest(prompt="private one", output_format="markdown", model="openai/gpt-6-luna")),
                    ("second", InferenceRequest(prompt="private two", output_format="markdown", model="openai/gpt-6-luna")),
                ])
            self.assertEqual({key: value.text for key, value in generated.items()}, {"first": "A", "second": "B"})
            self.assertEqual(len(usage_path.read_text().splitlines()), 2)
            self.assertEqual(sleep.call_args_list[0].args, (7.0,))
            self.assertIn("completed=1/2 failed=0", progress.getvalue())
            submitted = client.posts[0][1]["json"]
            self.assertEqual(client.posts[0][0], "https://openrouter.ai/api/v1/batches")
            self.assertEqual(submitted["endpoint"], "/v1/chat/completions")
            self.assertEqual(submitted["model"], "openai/gpt-6-luna")
            self.assertEqual([entry["custom_id"] for entry in submitted["requests"]], ["first", "second"])
            evidence_text = evidence_path.read_text()
            self.assertIn("batch-123", evidence_text)
            self.assertNotIn("secret", evidence_text)
            self.assertNotIn("private one", evidence_text)

    def test_ambiguous_post_is_not_retried(self):
        client = FakeClient(post=httpx.ReadTimeout("unknown"))
        adapter = ChatCompletionsAdapter(providerUrl="https://openrouter.ai/api/v1", apiKey="secret", model="openai/gpt-6-luna", batch_enabled=True)
        with patch("burn_pipeline.infrastructure.httpx.Client", return_value=client), self.assertRaisesRegex(RuntimeError, "ambiguous"):
            adapter.generate_batch([("one", InferenceRequest(prompt="x", output_format="markdown"))])
        self.assertEqual(len(client.posts), 1)

    def test_failed_batch_and_failed_individual_result_stop_generation(self):
        failed_client = FakeClient(post=FakeResponse({"id": "batch-f", "status": "failed", "error": "provider failure"}))
        adapter = ChatCompletionsAdapter(providerUrl="https://openrouter.ai/api/v1", apiKey=None, model="m", batch_enabled=True)
        with patch("burn_pipeline.infrastructure.httpx.Client", return_value=failed_client), self.assertRaisesRegex(RuntimeError, "status=failed"):
            adapter.generate_batch([("one", InferenceRequest(prompt="x", output_format="markdown"))])

        response_client = FakeClient(post=FakeResponse({"id": "batch-r", "status": "completed", "data": [{"custom_id": "one", "response": {"status_code": 500, "body": {"error": "request failed"}}}]}))
        with patch("burn_pipeline.infrastructure.httpx.Client", return_value=response_client), self.assertRaisesRegex(RuntimeError, "request one failed"):
            adapter.generate_batch([("one", InferenceRequest(prompt="x", output_format="markdown"))])

    def test_mixed_success_and_failure_accounts_successful_usage_before_failing(self):
        client = FakeClient(post=FakeResponse({"id": "batch-mixed", "status": "completed", "data": [
            {"custom_id": "bad", "error": {"message": "failed"}},
            {"custom_id": "good", "response": {"status_code": 200, "body": response("done", 0.03)}},
        ]}))
        adapter = ChatCompletionsAdapter(providerUrl="https://openrouter.ai/api/v1", apiKey=None, model="m", batch_enabled=True)
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "usage.jsonl"
            with patch.dict(os.environ, {"BURN_USAGE_LOG": str(ledger)}), patch("burn_pipeline.infrastructure.httpx.Client", return_value=client), self.assertRaisesRegex(RuntimeError, "request bad failed"):
                adapter.generate_batch([
                    ("bad", InferenceRequest(prompt="bad", output_format="markdown")),
                    ("good", InferenceRequest(prompt="good", output_format="markdown")),
                ])
            records = [json.loads(line) for line in ledger.read_text().splitlines()]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["usage"]["cost"], 0.03)

    def test_batch_cost_cap_is_enforced_after_all_success_usage_is_recorded(self):
        client = FakeClient(post=FakeResponse({"id": "batch-cost", "status": "completed", "data": [
            {"custom_id": "one", "response": {"status_code": 200, "body": response("one", 0.06)}},
            {"custom_id": "two", "response": {"status_code": 200, "body": response("two", 0.06)}},
        ]}))
        adapter = ChatCompletionsAdapter(providerUrl="https://openrouter.ai/api/v1", apiKey=None, model="m", batch_enabled=True)
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "usage.jsonl"
            with patch.dict(os.environ, {"BURN_USAGE_LOG": str(ledger), "BURN_MAX_COST_USD": "0.1"}), patch("burn_pipeline.infrastructure.httpx.Client", return_value=client), self.assertRaisesRegex(RuntimeError, "above BURN_MAX_COST_USD"):
                adapter.generate_batch([
                    ("one", InferenceRequest(prompt="one", output_format="markdown")),
                    ("two", InferenceRequest(prompt="two", output_format="markdown")),
                ])
            self.assertEqual(len(ledger.read_text().splitlines()), 2)

    def test_permanent_poll_404_is_not_retried(self):
        client = FakeClient(post=FakeResponse({"id": "batch-404", "status": "queued"}), gets=[FakeResponse({}, status_code=404)])
        adapter = ChatCompletionsAdapter(providerUrl="https://openrouter.ai/api/v1", apiKey=None, model="m", batch_enabled=True, retry_attempts=4)
        with patch("burn_pipeline.infrastructure.httpx.Client", return_value=client), patch("burn_pipeline.infrastructure.time.sleep") as sleep, self.assertRaisesRegex(RuntimeError, "non-retryable HTTP 404"):
            adapter.generate_batch([("one", InferenceRequest(prompt="x", output_format="markdown"))])
        self.assertEqual(len(client.get_urls), 1)
        self.assertEqual(sleep.call_count, 1)

    def test_batch_poll_interval_defaults_to_60_seconds(self):
        client = FakeClient(post=FakeResponse({"id": "batch-interval", "status": "queued"}), gets=[FakeResponse({"id": "batch-interval", "status": "completed", "data": [{"custom_id": "one", "response": {"status_code": 200, "body": response("ok", 0.0)}}]})])
        adapter = ChatCompletionsAdapter(providerUrl="https://openrouter.ai/api/v1", apiKey=None, model="m", batch_enabled=True)
        env = {key: value for key, value in os.environ.items() if key not in {"BURN_OPENROUTER_BATCH_POLL_INTERVAL_SECONDS", "BURN_USAGE_LOG", "BURN_MAX_COST_USD"}}
        with patch.dict(os.environ, env, clear=True), patch("burn_pipeline.infrastructure.httpx.Client", return_value=client), patch("burn_pipeline.infrastructure.time.sleep") as sleep:
            adapter.generate_batch([("one", InferenceRequest(prompt="x", output_format="markdown"))])
        self.assertEqual(sleep.call_args_list[0].args, (60.0,))

    def test_cli_batch_flag_enables_openrouter_adapter_without_environment_flag(self):
        from burn_pipeline.infrastructure import LocalFileStore
        from burn_pipeline.interface import build_parser, build_pipeline

        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=True):
            root = Path(directory)
            args = build_parser().parse_args([
                "--provider", "openrouter", "--model", "openai/gpt-6-luna",
                "--registry-file", str(root / "registry.json"),
                "generate-step", "--openrouter-batch-mode", "--format", "markdown",
                "--prompt-file", "prompt.md", "--output", "output.md",
            ])
            pipeline = build_pipeline(args, root, LocalFileStore(root))
            step = StepSpec(id="context", format="markdown", prompt_file=Path("prompt.md"), output=Path("output.md"))
            adapter = pipeline._inference_for_step(step)
            self.assertTrue(adapter._batch_enabled)

    def test_batch_does_not_activate_for_non_openrouter_provider(self):
        adapter = ChatCompletionsAdapter(providerUrl="http://localhost:11434", apiKey=None, model="m", batch_enabled=False)
        with self.assertRaisesRegex(RuntimeError, "not enabled"):
            adapter.generate_batch([("one", InferenceRequest(prompt="x", output_format="markdown"))])

    def test_pipeline_batches_ready_same_model_text_wave_and_waits_for_dependencies(self):
        class Files:
            def __init__(self):
                self.contents = {Path("p.md"): "prompt {{current_step.id}}"}
                self.outputs = {}

            def read_text(self, path):
                return self.contents[path]

            def write_text(self, path, content, force):
                self.outputs[path] = content

            def write_bytes(self, path, content, force):
                raise AssertionError("not an image")

            def exists(self, path):
                return path in self.contents or path in self.outputs

            def glob(self, pattern):
                return []

        class BatchInference:
            def __init__(self):
                self.waves = []

            def generate_batch(self, requests):
                self.waves.append([name for name, _ in requests])
                return {name: GeneratedArtifact(text=f"content {name}") for name, _ in requests}

            def generate(self, request):
                raise AssertionError("synchronous path not expected")

        files = Files()
        inference = BatchInference()
        steps = [
            StepSpec(id="a", format="markdown", prompt_file=Path("p.md"), output=Path("a.md")),
            StepSpec(id="b", format="markdown", prompt_file=Path("p.md"), output=Path("b.md")),
            StepSpec(id="c", format="markdown", prompt_file=Path("p.md"), output=Path("c.md"), depends_on=["a", "b"]),
        ]
        pipeline = BurnPipeline(
            files, lambda *_: inference,
            providers={GenerationModality.TEXT: ProviderConfig(kind=ProviderKind.OPENROUTER, model="model")},
            batch_mode=True,
        )
        pipeline.run_pipeline(PipelineSpec(context=BurnContext(), steps=steps), force=True)
        self.assertEqual(inference.waves, [["a", "b"], ["c"]])
        self.assertEqual(set(files.outputs), {Path("a.md"), Path("b.md"), Path("c.md")})


if __name__ == "__main__":
    unittest.main()
