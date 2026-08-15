from __future__ import annotations

import unittest

from research_operator.local_switcher import LocalSwitcher


class LocalIdentityTests(unittest.TestCase):
    def test_resolved_snapshot_is_part_of_the_local_artifact_record(self) -> None:
        activated = LocalSwitcher._activated_from_environment(
            {
                "LLAMA_MODEL_ID": "peculiar-ragdoll-nail-qwen3-6-35b-a3b-ud-q4-k-xl",
                "LLAMA_MODEL_REPO": "peculiar-ragdoll/Nail-Qwen3.6-35B-A3B-GGUF",
                "LLAMA_MODEL_FILE": "Nail-Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf",
                "LLAMA_MODEL_REVISION": "main",
                "LLAMA_MODEL_PATH": "/models/models--peculiar-ragdoll--Nail-Qwen3.6-35B-A3B-GGUF/snapshots/432c4276b23955ee4e27dc6aff237bfb9c635cee/Nail-Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf",
            },
            switched=False,
        )
        self.assertEqual(activated.source_revision, "main")
        self.assertEqual(activated.source_snapshot, "432c4276b23955ee4e27dc6aff237bfb9c635cee")


if __name__ == "__main__":
    unittest.main()
