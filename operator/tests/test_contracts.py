from __future__ import annotations

import unittest

from research_operator.contracts import (
    ContractError,
    local_identity_key,
    make_job_payload,
    parse_model_submission,
)


class ModelSubmissionContractTests(unittest.TestCase):
    def local_payload(self) -> dict[str, object]:
        return {
            "provider": "local",
            "model_ref": "peculiar-ragdoll-nail-qwen3-6-35b-a3b-ud-q4-k-xl",
            "display_name": "Nail Qwen3.6 35B A3B Q4_K_XL",
            "source_repo": "peculiar-ragdoll/Nail-Qwen3.6-35B-A3B-GGUF",
            "source_file": "Nail-Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf",
            "source_revision": "main",
            "cohorts": ["editorial", "assistant"],
            "local_model_max_gib": 21,
            "allow_capacity_override": True,
            "operator_acknowledged_idle": True,
            "confirm_paid_run": False,
        }

    def test_local_request_preserves_exact_quant_identity(self) -> None:
        submission = parse_model_submission(self.local_payload())
        self.assertEqual(
            submission.identity_key,
            "local:peculiar-ragdoll/Nail-Qwen3.6-35B-A3B-GGUF@main:Nail-Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf",
        )
        self.assertNotEqual(
            submission.identity_key,
            local_identity_key(
                "peculiar-ragdoll/Nail-Qwen3.6-35B-A3B-GGUF",
                "main",
                "Nail-Qwen3.6-35B-A3B-UD-IQ3_S.gguf",
            ),
        )

    def test_local_switch_requires_explicit_idle_acknowledgement(self) -> None:
        payload = self.local_payload()
        payload["operator_acknowledged_idle"] = False
        with self.assertRaisesRegex(ContractError, "idle"):
            parse_model_submission(payload)

    def test_fixed_assistant_cap_cannot_change(self) -> None:
        payload = self.local_payload()
        payload["assistant_max_tokens"] = 1024
        with self.assertRaisesRegex(ContractError, "fixed at 768"):
            parse_model_submission(payload)

    def test_each_selected_cohort_has_its_own_job_payload(self) -> None:
        submission = parse_model_submission(self.local_payload())
        editorial = make_job_payload(submission, "editorial")
        assistant = make_job_payload(submission, "assistant")
        self.assertEqual(editorial["cohort"], "editorial")
        self.assertEqual(assistant["cohort"], "assistant")
        self.assertEqual(editorial["identity_key"], assistant["identity_key"])

    def test_paid_remote_work_needs_consent_and_cost_ceiling(self) -> None:
        payload = {
            "provider": "openrouter",
            "model_ref": "nvidia/nemotron-3-ultra-550b-a55b",
            "display_name": "Nemotron 3 Ultra",
            "cohorts": ["assistant"],
            "confirm_paid_run": False,
            "target_cost_ceiling_usd": 4.0,
        }
        with self.assertRaisesRegex(ContractError, "confirm_paid_run"):
            parse_model_submission(payload)
        payload["confirm_paid_run"] = True
        submission = parse_model_submission(payload)
        self.assertEqual(submission.target_cost_ceiling_usd, 4.0)
        self.assertIsNone(submission.judge_cost_ceiling_usd)

    def test_editorial_remote_work_requires_judge_budget(self) -> None:
        payload = {
            "provider": "openrouter",
            "model_ref": "tencent/hy3",
            "display_name": "Tencent HY3",
            "cohorts": ["editorial"],
            "confirm_paid_run": True,
            "target_cost_ceiling_usd": 3.0,
        }
        with self.assertRaisesRegex(ContractError, "judge_cost_ceiling_usd"):
            parse_model_submission(payload)
        payload["judge_cost_ceiling_usd"] = 1.0
        self.assertEqual(parse_model_submission(payload).provider, "openrouter")


if __name__ == "__main__":
    unittest.main()
