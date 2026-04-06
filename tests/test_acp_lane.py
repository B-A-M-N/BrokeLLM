import importlib.util
import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "bin" / "_acp_lane.py"


def load_module():
    spec = importlib.util.spec_from_file_location("broke_acp_lane_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ACPLaneSpecTestCase(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def test_default_runtime_registry_maps_expected_bindings(self):
        registry = self.mod.default_runtime_registry()
        self.assertEqual(registry["gemini"]["binding_kind"], "native_acp")
        self.assertEqual(registry["claude"]["binding_kind"], "cli_adapter")
        self.assertEqual(registry["codex"]["binding_kind"], "cli_adapter")
        self.assertEqual(registry["openrouter"]["binding_kind"], "headless_adapter")

    def test_validate_lane_result_rejects_missing_fields(self):
        errors = self.mod.validate_lane_result({"lane_role": "worker"})
        self.assertIn("missing field: status", errors)
        self.assertIn("missing field: provider_metadata", errors)

    def test_normalize_provider_output_marks_schema_failure_as_degraded(self):
        result = self.mod.normalize_provider_output(
            "verifier",
            {"summary": "partial only", "provider_metadata": []},
            provider="claude",
            runtime_binding="cli_adapter",
        )
        self.assertTrue(result["degraded"])
        self.assertEqual(result["status"], "failed_schema")
        self.assertIn("provider_metadata must be an object", result["degraded_reason"])


if __name__ == "__main__":
    unittest.main()
