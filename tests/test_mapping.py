import builtins
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "bin" / "_mapping.py"


def load_mapping_module():
    spec = importlib.util.spec_from_file_location("broke_mapping_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()


class MappingTestCase(unittest.TestCase):
    def setUp(self):
        self.mod = load_mapping_module()
        self.tempdir = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tempdir.name)
        self.mod.DIR = root
        self.mod.MAPPING = root / ".mapping.json"
        self.mod.BACKENDS = root / ".backends.json"
        self.mod.CONFIG = root / "config.json"
        self.mod.TEAMS = root / ".teams.json"
        self.mod.PROFILES = root / ".profiles.json"
        self.mod.SNAPSHOTS = root / ".snapshots"
        self.mod.FREEZE = root / ".freeze"
        self.mod.cmd_init()

    def tearDown(self):
        self.tempdir.cleanup()

    def capture(self, fn, *args, **kwargs):
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args, **kwargs)
        return buf.getvalue()

    def write_mapping(self, mapping):
        self.mod.MAPPING.write_text(json.dumps(mapping, indent=2))

    def load_mapping(self):
        return json.loads(self.mod.MAPPING.read_text())

    def test_route_and_explain_use_canonical_health_identity(self):
        mapping = {
            "sonnet": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "label": "GitHub/GPT-4o-mini",
                "key": "GITHUB_TOKEN",
                "api_base": "https://models.inference.ai.azure.com",
                "pinned": False,
            }
        }
        self.write_mapping(mapping)
        health_payload = {
            "healthy_endpoints": [{"model": "openai/gpt-4o-mini"}],
            "unhealthy_endpoints": [],
        }

        with patch.object(self.mod.urllib.request, "urlopen", return_value=FakeResponse(health_payload)):
            route_out = self.capture(self.mod.cmd_route, "sonnet")
            explain_out = self.capture(self.mod.cmd_explain, "sonnet")
            doctor_out = self.capture(self.mod.cmd_doctor)

        self.assertIn("health        : OK", route_out)
        self.assertIn("health            : OK", explain_out)
        self.assertIn("openai/gpt-4o-mini", doctor_out)

    def test_cmd_swap_persists_pinned_metadata(self):
        original_input = builtins.input
        answers = iter(["0", "8"])
        try:
            builtins.input = lambda _prompt="": next(answers)
            self.capture(self.mod.cmd_swap)
        finally:
            builtins.input = original_input

        mapping = self.load_mapping()
        self.assertIn("pinned", mapping["sonnet"])
        self.assertFalse(mapping["sonnet"]["pinned"])

    def test_doctor_warns_on_floating_alias_after_swap(self):
        original_input = builtins.input
        answers = iter(["0", "8"])
        try:
            builtins.input = lambda _prompt="": next(answers)
            self.capture(self.mod.cmd_swap)
        finally:
            builtins.input = original_input

        health_payload = {
            "healthy_endpoints": [{"model": "openrouter/openai/gpt-4o-mini"}],
            "unhealthy_endpoints": [],
        }
        env_path = self.mod.DIR / ".env"
        env_path.write_text("OPENROUTER_API_KEY=test-key\n")

        with patch.object(self.mod.urllib.request, "urlopen", return_value=FakeResponse(health_payload)):
            doctor_out = self.capture(self.mod.cmd_doctor)

        self.assertIn("floating alias", doctor_out)
        self.assertIn("warning", doctor_out.lower())

    def test_team_access_zero_clears_limits(self):
        teams = {
            "demo": {
                "mode": 1,
                "slots": self.mod.load(),
                "fallbacks": {},
                "access": {"allowed_slots": ["sonnet"], "rpm": 60, "tpm": 1200},
            }
        }
        self.mod.TEAMS.write_text(json.dumps(teams, indent=2))

        self.capture(self.mod.cmd_team_access, "demo", rpm="0", tpm="0")

        saved = json.loads(self.mod.TEAMS.read_text())
        self.assertEqual(saved["demo"]["access"]["rpm"], 0)
        self.assertEqual(saved["demo"]["access"]["tpm"], 0)

    def test_install_uses_python_module_pip(self):
        install_sh = (REPO_ROOT / "install.sh").read_text()
        self.assertIn('"$PY" -m pip install -r "$DIR/requirements.txt" --quiet', install_sh)
        self.assertNotIn("\npip install -r \"$DIR/requirements.txt\" --quiet", install_sh)

    def test_gemini_env_name_is_consistent(self):
        broke_sh = (REPO_ROOT / "bin" / "broke").read_text()
        env_template = (REPO_ROOT / ".env.template").read_text()
        self.assertIn("GEMINI_API_KEY", broke_sh)
        self.assertIn("GEMINI_API_KEY", env_template)
        self.assertNotIn("GOOGLE_AI_STUDIO_API_KEY", broke_sh)

    def test_export_import_round_trip_preserves_teams_and_profiles(self):
        teams = {
            "work": {
                "mode": 1,
                "slots": self.mod.load(),
                "fallbacks": {"sonnet": ["haiku"]},
                "access": {"allowed_slots": ["sonnet"], "rpm": 30, "tpm": 0},
            }
        }
        profiles = {
            "app": {
                "team": "work",
                "description": "Production app",
                "access": {"allowed_slots": ["sonnet"], "rpm": 15, "tpm": 0},
            }
        }
        self.mod.TEAMS.write_text(json.dumps(teams, indent=2))
        self.mod.PROFILES.write_text(json.dumps(profiles, indent=2))

        export_path = self.mod.DIR / "broke-export.json"
        self.capture(self.mod.cmd_export, export_path)

        self.mod.TEAMS.unlink()
        self.mod.PROFILES.unlink()

        self.capture(self.mod.cmd_import, export_path)

        restored_teams = json.loads(self.mod.TEAMS.read_text())
        restored_profiles = json.loads(self.mod.PROFILES.read_text())
        self.assertEqual(restored_teams, teams)
        self.assertEqual(restored_profiles, profiles)

    def test_snapshot_save_and_restore_round_trip(self):
        initial = self.mod.load()
        modified = json.loads(json.dumps(initial))
        modified["sonnet"] = {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "label": "GitHub/GPT-4o-mini",
            "key": "GITHUB_TOKEN",
            "api_base": "https://models.inference.ai.azure.com",
            "pinned": False,
        }
        self.write_mapping(modified)

        save_out = self.capture(self.mod.cmd_snapshot_save)
        snapshots = sorted(self.mod.SNAPSHOTS.glob("*.json"))
        self.assertEqual(len(snapshots), 1)
        self.assertIn("Snapshot saved:", save_out)

        self.write_mapping(initial)
        self.capture(self.mod.cmd_snapshot_restore, "0")

        restored = self.load_mapping()
        self.assertEqual(restored, modified)


if __name__ == "__main__":
    unittest.main()
