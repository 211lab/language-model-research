from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


TOOL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOL_ROOT.parents[1]
sys.path.insert(0, str(TOOL_ROOT))

import evidence  # noqa: E402
import assistant_benchmark as assistant  # noqa: E402


class ModelDiscoveryTests(unittest.TestCase):
    def test_embedding_and_image_endpoints_are_not_chat_models(self) -> None:
        advertised = {
            "data": [
                {"id": "chat-model"},
                {"id": "embeddinggemma-300m-q8_0"},
                {
                    "id": "image-model",
                    "architecture": {"output_modalities": ["image"]},
                    "capabilities": {"image_generation": True},
                },
            ]
        }
        with patch.object(assistant, "request_json", return_value=advertised):
            included, excluded = assistant.discover_chat_models("http://example.test/v1", None, 1)
        self.assertEqual([row["id"] for row in included], ["chat-model"])
        self.assertEqual([row["id"] for row in excluded], ["embeddinggemma-300m-q8_0", "image-model"])


class ComparabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = {
            "suite": "assistant",
            "suite_version": "1.0",
            "replicate": {"seed": 42},
            "execution": {"provider_kind": "local", "endpoint_class": "llama.cpp"},
            "reproducibility": {
                "fixture_sha256": "fixture", "tasks_sha256": "tasks",
                "seed_document_sha256": "seed-doc", "prompt_sha256": "prompt",
                "tool_schema_sha256": "tools",
            },
        }

    def test_matching_contract_and_runtime_is_comparable(self) -> None:
        self.assertEqual(evidence.comparability(self.base, copy.deepcopy(self.base))["level"], "comparable")

    def test_remote_execution_is_directional(self) -> None:
        other = copy.deepcopy(self.base)
        other["execution"]["provider_kind"] = "remote"
        self.assertEqual(evidence.comparability(self.base, other)["level"], "directional")

    def test_seed_or_fixture_change_is_not_comparable(self) -> None:
        for mutation in ("seed", "fixture"):
            with self.subTest(mutation=mutation):
                other = copy.deepcopy(self.base)
                if mutation == "seed":
                    other["replicate"]["seed"] = 7
                else:
                    other["reproducibility"]["fixture_sha256"] = "different"
                self.assertEqual(evidence.comparability(self.base, other)["level"], "not-comparable")


class PublishedBundleTests(unittest.TestCase):
    def test_every_published_bundle_validates(self) -> None:
        bundles = sorted(path.parent for path in (REPO_ROOT / "runs").glob("*/manifest.json"))
        self.assertTrue(bundles)
        errors = [error for bundle in bundles for error in evidence.validate_bundle(bundle)]
        self.assertEqual(errors, [])

    def test_registry_count_matches_manifests(self) -> None:
        registry = evidence.load_json(REPO_ROOT / "runs" / "index.json")
        manifests = list((REPO_ROOT / "runs").glob("*/manifest.json"))
        self.assertEqual(registry["run_count"], len(manifests))


if __name__ == "__main__":
    unittest.main()
