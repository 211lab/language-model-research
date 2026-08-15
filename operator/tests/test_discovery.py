import unittest
from types import SimpleNamespace
from unittest.mock import patch

from research_operator.discovery import _submission, scan_once


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(
            discovery_local_model_max_gib=32.0,
            discovery_idle_acknowledged=False,
            harness_contract_id="assistant-fixtures-v1-seed42-max768",
            local_ai_base_url="http://127.0.0.1:11434",
            research_root=SimpleNamespace(),
        )
        self.nail_q4 = {
            "id": "nail-qwen-q4",
            "name": "Nail Qwen 3.6",
            "architecture": {"output_modalities": ["text"]},
            "meta": {"llamaswap": {
                "sourceRepo": "peculiar-ragdoll/Nail-Qwen3.6-35B-A3B-GGUF",
                "sourceFile": "Nail-Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf",
                "sourceRevision": "main",
            }},
        }

    def test_q4_records_exact_identity_and_local_suffix(self):
        submission = _submission(self.nail_q4, self.settings, idle_acknowledged=True)
        self.assertIsNotNone(submission)
        assert submission is not None
        self.assertEqual(submission.display_name, "Nail Qwen 3.6 (Local)")
        self.assertEqual(submission.local_model_max_gib, 32.0)
        self.assertTrue(submission.allow_capacity_override)
        self.assertTrue(submission.operator_acknowledged_idle)

    def test_image_and_embedding_models_are_excluded(self):
        image = self.nail_q4 | {"id": "qwen-image", "description": "image generation"}
        embedding = self.nail_q4 | {"id": "text-embedding-model"}
        self.assertIsNone(_submission(image, self.settings, idle_acknowledged=True))
        self.assertIsNone(_submission(embedding, self.settings, idle_acknowledged=True))

    def test_scan_does_not_queue_without_idle_acknowledgement(self):
        class Repository:
            def enqueue_discovered_local_run(self, *args, **kwargs):
                raise AssertionError("must not queue before idle acknowledgement")

        with patch("research_operator.discovery._provider_models", return_value=[self.nail_q4]), patch(
            "research_operator.discovery._published_identities", return_value=set()
        ):
            result = scan_once(self.settings, Repository())
        self.assertEqual(result[0]["reason"], "awaiting-idle-acknowledgement")
