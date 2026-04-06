import builtins
import importlib.util
import io
import json
import os
import pathlib
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
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


def load_proxy_module():
    proxy_path = REPO_ROOT / "bin" / "_proxy.py"
    spec = importlib.util.spec_from_file_location("broke_proxy_test", proxy_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_socket_bridge_module():
    bridge_path = REPO_ROOT / "bin" / "_socket_bridge.py"
    spec = importlib.util.spec_from_file_location("broke_socket_bridge_test", bridge_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_harness_shim_module():
    shim_path = REPO_ROOT / "bin" / "_harness_shim.py"
    spec = importlib.util.spec_from_file_location("broke_harness_shim_test", shim_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_pty_harness_module():
    pty_path = REPO_ROOT / "bin" / "_pty_harness.py"
    spec = importlib.util.spec_from_file_location("broke_pty_harness_test", pty_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_dashboard_module():
    dashboard_path = REPO_ROOT / "bin" / "_dashboard.py"
    spec = importlib.util.spec_from_file_location("broke_dashboard_test", dashboard_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_harness_common_module():
    common_path = REPO_ROOT / "bin" / "_harness_common.py"
    spec = importlib.util.spec_from_file_location("broke_harness_common_test", common_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()


class FakeHTTPResponse:
    def __init__(self, status=200, reason="OK", headers=None, body=b"{}"):
        self.status = status
        self.reason = reason
        self._headers = headers or []
        self._body = body

    def getheaders(self):
        return list(self._headers)

    def read(self):
        return self._body


class FakeHTTPConnection:
    last_request = None

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.response = FakeHTTPResponse(headers=[("Content-Type", "application/json")], body=b'{"ok":true}')

    def request(self, method, path, body=None, headers=None):
        FakeHTTPConnection.last_request = {
            "host": self.host,
            "port": self.port,
            "timeout": self.timeout,
            "method": method,
            "path": path,
            "body": body,
            "headers": headers or {},
        }

    def getresponse(self):
        return self.response

    def close(self):
        return None


class MappingTestCase(unittest.TestCase):
    def setUp(self):
        self.mod = load_mapping_module()
        self.tempdir = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tempdir.name)
        self.mod.DIR = root
        self.mod.MAPPING = root / ".mapping.json"
        self.mod.BACKENDS = root / ".backends.json"
        self.mod.CONFIG = root / "config.json"
        self.mod.DEPLOYMENTS = root / ".deployments.json"
        self.mod.TEAMS = root / ".teams.json"
        self.mod.PROFILES = root / ".profiles.json"
        self.mod.CLIENT_BINDINGS = root / ".client_bindings.json"
        self.mod.SNAPSHOTS = root / ".snapshots"
        self.mod.FREEZE = root / ".freeze"
        self.mod.ROTATION_POLICY = root / ".rotation.json"
        self.mod.KEY_STATE = root / ".key_state.json"
        self.mod.ROTATION_LOG = root / ".rotation.log"
        self.mod.MODEL_POLICY = root / ".model_policy.json"
        self.mod.MODEL_STATE = root / ".model_state.json"
        self.mod.HARNESS_CONFIG = root / ".harness.json"
        self.mod.HARNESS_STATE = root / ".harness_state.json"
        self.mod.HARNESS_RUNS = root / ".harness_runs.json"
        self.mod.HARNESS_ACTIVE_RUN = root / ".harness_active_run.json"
        self.mod.HARNESS_PROMPT_CONTRACTS = root / ".harness_prompt_contracts.json"
        self.mod.HARNESS_PREFIX_CACHE = root / ".harness_prefix_cache.json"
        self.mod.HARNESS_EVIDENCE_CACHE = root / ".harness_evidence_cache.json"
        self.mod.HARNESS_REVIEW_CACHE = root / ".harness_review_cache.json"
        self.mod.HARNESS_RUN_ROOT = root / ".runtime" / "harness"
        self.mod.ENV_FILE = root / ".env"
        self.mod.CLAUDE_ENV_FILE = root / ".env.claude"
        self.mod.CLIENT_TOKEN_FILE = root / ".broke_client_token"
        self.mod.INTERNAL_TOKEN_FILE = root / ".broke_internal_token"
        self.mod.LAUNCH_AUDIT_LOG = root / ".launch_audit.log"
        self.mod.SANDBOX_PROFILE_FILE = root / ".sandbox-profile"
        self.mod.PROXY_SOCKET = root / ".runtime" / "proxy.sock"
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

    def _build_harness_env(self, root, run_id="run_test"):
        events = root / "events.jsonl"
        artifacts = root / "artifacts"
        state = root / "state"
        artifacts.mkdir(parents=True, exist_ok=True)
        state.mkdir(parents=True, exist_ok=True)
        realpaths = root / "realpaths.json"
        return {
            "BROKE_HARNESS_RUN_ID": run_id,
            "BROKE_HARNESS_EVENTS_FILE": str(events),
            "BROKE_HARNESS_REALPATHS_FILE": str(realpaths),
            "BROKE_HARNESS_ALLOWED_PATHS": str(root),
            "BROKE_HARNESS_ARTIFACT_DIR": str(artifacts),
            "BROKE_HARNESS_GOVERNOR_STATE": str(state / "governor.json"),
            "BROKE_HARNESS_INTERVENTION_FILE": str(state / "intervention.json"),
        }

    def _run_minimal_strict_bwrap(self, workdir, command):
        return subprocess.run(
            [
                "bwrap",
                "--unshare-all",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "--tmpfs",
                "/tmp",
                "--ro-bind",
                "/usr",
                "/usr",
                "--ro-bind-try",
                "/bin",
                "/bin",
                "--ro-bind-try",
                "/lib",
                "/lib",
                "--ro-bind-try",
                "/lib64",
                "/lib64",
                "--ro-bind-try",
                "/etc",
                "/etc",
                "--bind",
                str(workdir),
                str(workdir),
                "--chdir",
                str(workdir),
                "--",
                "/bin/bash",
                "-lc",
                command,
            ],
            capture_output=True,
            text=True,
        )

    def test_proxy_maps_anthropic_model_ids_to_current_lane_backend(self):
        proxy = load_proxy_module()
        root = pathlib.Path(self.tempdir.name)
        proxy.DEPLOYMENTS = root / ".deployments.json"
        proxy.MAPPING = root / ".mapping.json"
        proxy.ROTATION_POLICY = root / ".rotation.json"
        proxy.KEY_STATE = root / ".key_state.json"
        proxy.MODEL_POLICY = root / ".model_policy.json"
        proxy.MODEL_STATE = root / ".model_state.json"

        mapping = {
            "sonnet": {
                "provider": "groq",
                "model": "meta-llama/llama-4-scout-17b-16e-instruct",
                "label": "Groq/Llama-4-Scout",
                "key": "GROQ_API_KEY",
            }
        }
        proxy.MAPPING.write_text(json.dumps(mapping, indent=2))
        proxy.DEPLOYMENTS.write_text(json.dumps({
            "Groq/Llama-4-Scout": [
                {"provider": "groq", "key_name": "GROQ_API_KEY", "internal_model_name": "groq/meta-llama/llama-4-scout-17b-16e-instruct"}
            ]
        }, indent=2))

        policy, model_policy, slot, groups, _state = proxy.prepare_candidates("claude-sonnet-4-6")
        self.assertEqual(slot, "sonnet")
        self.assertEqual(groups[0]["label"], "Groq/Llama-4-Scout")

    def test_proxy_maps_new_claude_slot_aliases_to_current_lane_backend(self):
        proxy = load_proxy_module()
        root = pathlib.Path(self.tempdir.name)
        proxy.DEPLOYMENTS = root / ".deployments.json"
        proxy.MAPPING = root / ".mapping.json"
        proxy.ROTATION_POLICY = root / ".rotation.json"
        proxy.KEY_STATE = root / ".key_state.json"
        proxy.MODEL_POLICY = root / ".model_policy.json"
        proxy.MODEL_STATE = root / ".model_state.json"

        mapping = {
            "opus": {
                "provider": "openrouter",
                "model": "nvidia/nemotron-3-super-120b-a12b:free",
                "label": "OR/Nemotron-3-Super",
                "key": "OPENROUTER_API_KEY",
            },
            "custom": {
                "provider": "openrouter",
                "model": "nvidia/nemotron-3-nano-30b-a3b:free",
                "label": "OR/Nemotron-3-Nano",
                "key": "OPENROUTER_API_KEY",
            },
        }
        proxy.MAPPING.write_text(json.dumps(mapping, indent=2))
        proxy.DEPLOYMENTS.write_text(json.dumps({
            "OR/Nemotron-3-Super": [
                {"provider": "openrouter", "key_name": "OPENROUTER_API_KEY", "internal_model_name": "openrouter/nvidia/nemotron-3-super-120b-a12b:free"}
            ],
            "OR/Nemotron-3-Nano": [
                {"provider": "openrouter", "key_name": "OPENROUTER_API_KEY", "internal_model_name": "openrouter/nvidia/nemotron-3-nano-30b-a3b:free"}
            ],
        }, indent=2))

        _policy, _model_policy, slot_opus, groups_opus, _state = proxy.prepare_candidates("claude-opus-1m")
        self.assertEqual(slot_opus, "opus")
        self.assertEqual(groups_opus[0]["label"], "OR/Nemotron-3-Super")

        _policy, _model_policy, slot_custom, groups_custom, _state = proxy.prepare_candidates("custom")
        self.assertEqual(slot_custom, "custom")
        self.assertEqual(groups_custom[0]["label"], "OR/Nemotron-3-Nano")

    def test_proxy_maps_codex_model_ids_to_current_lane_backend(self):
        proxy = load_proxy_module()
        root = pathlib.Path(self.tempdir.name)
        proxy.DEPLOYMENTS = root / ".deployments.json"
        proxy.MAPPING = root / ".mapping.json"
        proxy.ROTATION_POLICY = root / ".rotation.json"
        proxy.KEY_STATE = root / ".key_state.json"
        proxy.MODEL_POLICY = root / ".model_policy.json"
        proxy.MODEL_STATE = root / ".model_state.json"

        mapping = {
            "gpt54": {
                "provider": "groq",
                "model": "moonshotai/kimi-k2-instruct",
                "label": "Groq/Kimi-K2",
                "key": "GROQ_API_KEY",
            }
        }
        proxy.MAPPING.write_text(json.dumps(mapping, indent=2))
        proxy.DEPLOYMENTS.write_text(json.dumps({
            "Groq/Kimi-K2": [
                {"provider": "groq", "key_name": "GROQ_API_KEY", "internal_model_name": "groq/moonshotai/kimi-k2-instruct"}
            ]
        }, indent=2))

        policy, model_policy, slot, groups, _state = proxy.prepare_candidates("gpt-5.4")
        self.assertEqual(slot, "gpt54")
        self.assertEqual(groups[0]["label"], "Groq/Kimi-K2")

    def test_proxy_maps_active_backend_model_ids_to_current_lane_backend(self):
        proxy = load_proxy_module()
        root = pathlib.Path(self.tempdir.name)
        proxy.DEPLOYMENTS = root / ".deployments.json"
        proxy.MAPPING = root / ".mapping.json"
        proxy.ROTATION_POLICY = root / ".rotation.json"
        proxy.KEY_STATE = root / ".key_state.json"
        proxy.MODEL_POLICY = root / ".model_policy.json"
        proxy.MODEL_STATE = root / ".model_state.json"

        mapping = {
            "sonnet": {
                "provider": "openrouter",
                "model": "stepfun/step-3.5-flash:free",
                "label": "OR/Step-3.5",
                "key": "OPENROUTER_API_KEY",
            }
        }
        proxy.MAPPING.write_text(json.dumps(mapping, indent=2))
        proxy.DEPLOYMENTS.write_text(json.dumps({
            "OR/Step-3.5": [
                {"provider": "openrouter", "key_name": "OPENROUTER_API_KEY", "internal_model_name": "openrouter/stepfun/step-3.5-flash:free"}
            ]
        }, indent=2))

        policy, model_policy, slot, groups, _state = proxy.prepare_candidates("stepfun/step-3.5-flash:free")
        self.assertEqual(slot, "sonnet")
        self.assertEqual(groups[0]["label"], "OR/Step-3.5")

    def test_proxy_rejects_unknown_model_labels(self):
        proxy = load_proxy_module()
        root = pathlib.Path(self.tempdir.name)
        proxy.DEPLOYMENTS = root / ".deployments.json"
        proxy.MAPPING = root / ".mapping.json"
        proxy.ROTATION_POLICY = root / ".rotation.json"
        proxy.KEY_STATE = root / ".key_state.json"
        proxy.MODEL_POLICY = root / ".model_policy.json"
        proxy.MODEL_STATE = root / ".model_state.json"

        proxy.MAPPING.write_text(json.dumps(self.mod.load(), indent=2))
        proxy.DEPLOYMENTS.write_text(json.dumps({"OR/Qwen-3.6+": [{"provider": "openrouter", "key_name": "OPENROUTER_API_KEY", "internal_model_name": "openrouter/qwen/qwen3.6-plus:free"}]}, indent=2))

        policy, model_policy, slot, groups, _state = proxy.prepare_candidates("totally-unknown-model")
        self.assertIsNone(policy)
        self.assertIsNone(groups)

    def test_proxy_client_auth_rejects_missing_token(self):
        proxy = load_proxy_module()
        proxy.CLIENT_TOKEN = "expected-token"
        proxy.AUTH_FAILURES.clear()

        fake = type("FakeHandler", (), {})()
        fake.path = "/v1/models"
        fake.client_address = ("127.0.0.1", 12345)
        fake.headers = {}

        allowed, reason = proxy.ProxyHandler._client_authorized(fake)
        self.assertFalse(allowed)
        self.assertEqual(reason, "missing_or_invalid_client_token")

    def test_proxy_client_auth_accepts_profile_bound_token(self):
        proxy = load_proxy_module()
        root = pathlib.Path(self.tempdir.name)
        proxy.CLIENT_BINDINGS = root / ".client_bindings.json"
        proxy.CLIENT_TOKEN = "expected-token"
        proxy.AUTH_FAILURES.clear()
        proxy.CLIENT_BINDINGS.write_text(json.dumps({
            "tokens": {
                "bound-token": {"profile": "app", "name": "App"},
            }
        }, indent=2))

        fake = type("FakeHandler", (), {})()
        fake.path = "/v1/models"
        fake.client_address = ("127.0.0.1", 12345)
        fake.headers = {"Authorization": "Bearer bound-token"}
        fake._presented_client_token = lambda: proxy.ProxyHandler._presented_client_token(fake)

        allowed, reason = proxy.ProxyHandler._client_authorized(fake)
        self.assertTrue(allowed)
        self.assertEqual(reason, "bound_client_token_ok")

    def test_proxy_auth_throttles_repeated_failures(self):
        proxy = load_proxy_module()
        proxy.CLIENT_TOKEN = "expected-token"
        proxy.AUTH_FAILURES.clear()

        fake = type("FakeHandler", (), {})()
        fake.path = "/v1/models"
        fake.client_address = ("127.0.0.1", 12345)
        fake.headers = {}

        for _ in range(proxy.AUTH_MAX_FAILURES):
            allowed, reason = proxy.ProxyHandler._client_authorized(fake)
            self.assertFalse(allowed)
        allowed, reason = proxy.ProxyHandler._client_authorized(fake)
        self.assertFalse(allowed)
        self.assertEqual(reason, "auth_rate_limited")

    def test_proxy_rejects_oversized_request_body(self):
        proxy = load_proxy_module()

        fake = type("FakeHandler", (), {})()
        fake.headers = {"Content-Length": str(proxy.MAX_REQUEST_BYTES + 1)}
        fake.rfile = io.BytesIO(b"{}")
        captured = {}

        def send_proxy_error(status, message):
            captured["status"] = status
            captured["message"] = message

        fake._send_proxy_error = send_proxy_error

        body = proxy.ProxyHandler._read_request_body(fake)
        self.assertIsNone(body)
        self.assertEqual(captured["status"], 413)
        self.assertIn("request_too_large", captured["message"])

    def test_proxy_forward_once_strips_client_auth_and_injects_internal_auth(self):
        proxy = load_proxy_module()
        proxy.INTERNAL_TOKEN = "internal-token"

        fake = type("FakeHandler", (), {})()
        fake.server = type("Server", (), {"upstream_base": "http://127.0.0.1:4001"})()
        fake.path = "/v1/chat/completions"
        fake.command = "POST"
        fake.headers = {
            "Authorization": "Bearer client-token",
            "x-api-key": "client-key",
            "api-key": "client-key-2",
            "Content-Type": "application/json",
            "Content-Length": "2",
        }

        with patch.object(proxy.http.client, "HTTPConnection", FakeHTTPConnection):
            outcome = proxy.ProxyHandler._forward_once(fake, b"{}")

        self.assertEqual(outcome["status"], 200)
        sent = FakeHTTPConnection.last_request
        self.assertEqual(sent["path"], "/v1/chat/completions")
        self.assertEqual(sent["headers"]["Authorization"], "Bearer internal-token")
        self.assertNotIn("x-api-key", {k.lower(): v for k, v in sent["headers"].items()})
        self.assertNotIn("api-key", {k.lower(): v for k, v in sent["headers"].items()})
        self.assertNotIn("Content-Length", sent["headers"])

    def test_proxy_selects_profile_mapping_from_header(self):
        proxy = load_proxy_module()
        root = pathlib.Path(self.tempdir.name)
        proxy.TEAMS = root / ".teams.json"
        proxy.PROFILES = root / ".profiles.json"
        proxy.CLIENT_BINDINGS = root / ".client_bindings.json"
        proxy.MAPPING = root / ".mapping.json"
        proxy.MAPPING.write_text(json.dumps(self.mod.load(), indent=2))
        proxy.TEAMS.write_text(json.dumps({
            "app-team": {
                "mode": 0,
                "slots": {
                    "sonnet": {
                        "provider": "groq",
                        "model": "moonshotai/kimi-k2-instruct",
                        "label": "Groq/Kimi-K2",
                        "key": "GROQ_API_KEY",
                    }
                },
            }
        }, indent=2))
        proxy.PROFILES.write_text(json.dumps({
            "app": {
                "team": "app-team",
                "description": "App profile",
                "access": {"allowed_slots": ["sonnet"], "rpm": 0, "tpm": 0},
            }
        }, indent=2))

        fake = type("FakeHandler", (), {})()
        fake.headers = {"X-Broke-Profile": "app"}
        fake._selected_profile_name = lambda: proxy.ProxyHandler._selected_profile_name(fake)

        mapping, profile_name, source = proxy.ProxyHandler._request_mapping(fake)
        self.assertEqual(profile_name, "app")
        self.assertEqual(source, "header")
        self.assertEqual(mapping["sonnet"]["label"], "Groq/Kimi-K2")

    def test_proxy_rejects_conflicting_bound_profile_header(self):
        proxy = load_proxy_module()
        root = pathlib.Path(self.tempdir.name)
        proxy.CLIENT_BINDINGS = root / ".client_bindings.json"
        proxy.CLIENT_BINDINGS.write_text(json.dumps({
            "tokens": {
                "bound-token": {"profile": "app", "name": "App"},
            }
        }, indent=2))

        fake = type("FakeHandler", (), {})()
        fake.headers = {
            "Authorization": "Bearer bound-token",
            "X-Broke-Profile": "other-app",
        }
        fake._presented_client_token = lambda: proxy.ProxyHandler._presented_client_token(fake)

        profile_name, source = proxy.ProxyHandler._selected_profile_name(fake)
        self.assertIsNone(profile_name)
        self.assertEqual(source, "bound_token_profile_mismatch")

    def test_proxy_request_returns_503_when_direct_upstream_is_unreachable(self):
        proxy = load_proxy_module()

        fake = type("FakeHandler", (), {})()
        fake.path = "/v1/models"
        fake.headers = {}
        fake.client_address = ("127.0.0.1", 12345)

        captured = {}

        def authorized():
            return True, "ok"

        def read_body():
            return b""

        def forward_once(_body):
            raise OSError("connection refused")

        def send_proxy_error(status, message):
            captured["status"] = status
            captured["message"] = message

        fake._client_authorized = authorized
        fake._read_request_body = read_body
        fake._forward_once = forward_once
        fake._send_proxy_error = send_proxy_error

        proxy.ProxyHandler._proxy_request(fake)
        self.assertEqual(captured["status"], 503)
        self.assertIn("upstream_unreachable", captured["message"])

    def test_proxy_redacts_key_names_in_rotation_log_events(self):
        proxy = load_proxy_module()
        event = proxy.redact_event({"event": "request_ok", "key_name": "OPENROUTER_API_KEY"})
        self.assertNotIn("key_name", event)
        self.assertTrue(event["key_ref"].startswith("key_"))

    def test_harness_shim_classifies_commands(self):
        shim = load_harness_shim_module()
        self.assertEqual(shim.command_classification("pytest", ["-q"]), "verification:test")
        self.assertEqual(shim.command_classification("npm", ["test"]), "verification:task")
        self.assertEqual(shim.command_classification("git", ["status"]), "vcs")
        self.assertEqual(shim.command_classification("python3", ["script.py"]), "runtime")

    def test_harness_shim_marks_runtime_commands_as_mutating(self):
        shim = load_harness_shim_module()
        self.assertTrue(shim.command_is_mutating("python3", ["script.py"], "runtime"))
        self.assertTrue(shim.command_is_mutating("git", ["commit", "-m", "x"], "vcs"))
        self.assertFalse(shim.command_is_mutating("pytest", ["-q"], "verification:test"))

    def test_harness_governor_requires_verification_after_failed_test(self):
        shim = load_harness_shim_module()
        state = shim.default_governor_state()
        state = shim.update_governor_state(state, "pytest", ["-q"], "verification:test", 1, "cmd1")
        self.assertTrue(state["verification_required"])
        self.assertTrue(state["verification_only_mode"])
        self.assertEqual(state["intervention_reason"], "verification_failed")
        self.assertIn("pytest -q", state["next_action"])

    def test_harness_governor_flags_suspicious_verification(self):
        shim = load_harness_shim_module()
        state = shim.default_governor_state()
        state = shim.update_governor_state(
            state,
            "pytest",
            ["--collect-only"],
            "verification:test",
            0,
            "cmdsuspicious",
            duration_ms=40,
        )
        self.assertTrue(state["verification_required"])
        self.assertTrue(state["verification_only_mode"])
        self.assertEqual(state["intervention_reason"], "suspicious_verification")
        self.assertIn("non-executing pytest command", state["last_verification_reason"])

    def test_harness_governor_denies_mutating_command_when_verification_required(self):
        shim = load_harness_shim_module()
        state = shim.default_governor_state()
        state["verification_required"] = True
        state["verification_only_mode"] = True
        state["intervention_reason"] = "verification_failed"
        denied, reason = shim.governor_denies_command(state, "python3", ["script.py"], "runtime")
        self.assertTrue(denied)
        self.assertEqual(reason, "verification_failed")
        denied_non_mutating, _ = shim.governor_denies_command(state, "git", ["status"], "vcs")
        self.assertTrue(denied_non_mutating)

    def test_harness_governor_clears_intervention_after_passing_verification(self):
        shim = load_harness_shim_module()
        state = shim.default_governor_state()
        state["verification_required"] = True
        state["verification_only_mode"] = True
        state["intervention_reason"] = "verification_failed"
        state["next_action"] = "Run pytest -q"
        next_state = shim.update_governor_state(state, "pytest", ["-q"], "verification:test", 0, "cmd2")
        self.assertFalse(next_state["verification_required"])
        self.assertFalse(next_state["verification_only_mode"])
        self.assertEqual(next_state["writes_since_verification"], 0)
        self.assertEqual(next_state["next_action"], "")

    def test_harness_governor_requires_checkpoint_after_stale_mutation_sequence(self):
        shim = load_harness_shim_module()
        state = shim.default_governor_state()
        for idx in range(3):
            state = shim.update_governor_state(state, "python3", [f"step{idx}.py"], "runtime", 0, f"cmd{idx}")
        self.assertTrue(state["verification_required"])
        self.assertTrue(state["verification_only_mode"])
        self.assertEqual(state["intervention_reason"], "verification_stale")

    def test_harness_governor_escalates_high_risk_shell_eval_faster(self):
        shim = load_harness_shim_module()
        state = shim.default_governor_state()
        state = shim.update_governor_state(state, "bash", ["-lc", "echo hi > out"], "runtime", 0, "cmd1")
        state = shim.update_governor_state(state, "bash", ["-lc", "echo hi2 > out2"], "runtime", 0, "cmd2")
        self.assertTrue(state["verification_required"])
        self.assertEqual(state["intervention_reason"], "high_risk_mutation_sequence")
        self.assertGreaterEqual(state["risk_score"], 4)

    def test_harness_shim_denies_cwd_outside_allowed_paths(self):
        shim = load_harness_shim_module()
        self.assertTrue(shim.cwd_allowed("/tmp/work", ["/tmp"]))
        self.assertFalse(shim.cwd_allowed("/etc", ["/tmp"]))

    def moved_test_harness_shim_classifies_shell_escape_surfaces_as_runtime(self):
        shim = load_harness_shim_module()
        self.assertEqual(shim.command_classification("bash", ["-lc", "echo hi"]), "runtime")
        self.assertEqual(shim.command_classification("sh", ["-c", "touch x"]), "runtime")
        self.assertEqual(shim.command_classification("env", ["python3", "-c", "print(1)"]), "runtime")
        self.assertTrue(shim.command_is_mutating("bash", ["-lc", "echo hi > out"], "runtime"))
        self.assertEqual(shim.command_escape_surface("bash", ["-lc", "echo hi"]), "shell_eval")
        self.assertEqual(shim.command_escape_surface("python3", ["-c", "print(1)"]), "python_inline_or_module")
        self.assertEqual(shim.command_escape_surface("node", ["-e", "console.log(1)"]), "node_eval")
        self.assertEqual(shim.command_escape_surface("env", ["python3", "-c", "print(1)"]), "env_exec")

    def moved_test_harness_shim_integration_captures_mutation_provenance_for_shell_eval(self):
        root = pathlib.Path(self.tempdir.name) / "shim-run"
        root.mkdir(parents=True)
        env = os.environ.copy()
        env.update(self._build_harness_env(root))
        env["BROKE_HARNESS_ALLOWED_PATHS"] = str(root)
        realpaths = root / "realpaths.json"
        realpaths.write_text(json.dumps({"bash": shutil.which("bash") or "/bin/bash"}))
        shim_path = REPO_ROOT / "bin" / "_harness_shim.py"
        shim_exec = root / "bash"
        shim_exec.symlink_to(shim_path)
        target = root / "out.txt"
        proc = subprocess.run(
            [str(shim_exec), "-lc", f"printf 'hello' > {shlex.quote(str(target))}"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertEqual(target.read_text(), "hello")
        events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines() if line.strip()]
        completed = next(evt for evt in events if evt["event_type"] == "command.completed")
        self.assertEqual(completed["payload"]["mutation_counts"]["created"], 1)
        artifact = pathlib.Path(completed["artifact_refs"][0])
        artifact_payload = json.loads(artifact.read_text())
        self.assertIn("mutation_provenance", artifact_payload)
        self.assertEqual(artifact_payload["mutation_provenance"]["created"][0]["path"], "out.txt")

    def test_pty_harness_reads_new_intervention_once(self):
        pty_harness = load_pty_harness_module()
        intervention_file = pathlib.Path(self.tempdir.name) / "intervention.json"
        intervention_file.write_text(json.dumps({"command_id": "cmd1", "status": "active", "notice": "stop now"}))
        payload, seen = pty_harness.read_intervention(intervention_file, "")
        self.assertEqual(payload["notice"], "stop now")
        self.assertEqual(seen, "active:cmd1")
        payload_again, seen_again = pty_harness.read_intervention(intervention_file, seen)
        self.assertIsNone(payload_again)
        self.assertEqual(seen_again, "active:cmd1")

    def moved_test_pty_harness_ignores_invalid_intervention_json(self):
        pty_harness = load_pty_harness_module()
        intervention_file = pathlib.Path(self.tempdir.name) / "intervention.json"
        intervention_file.write_text("{bad json")
        payload, seen = pty_harness.read_intervention(intervention_file, "")
        self.assertIsNone(payload)
        self.assertEqual(seen, "")

    def moved_test_pty_harness_ignores_invalid_control_json(self):
        pty_harness = load_pty_harness_module()
        control_file = pathlib.Path(self.tempdir.name) / "control.json"
        control_file.write_text("{bad json")
        payload, seen = pty_harness.read_control(control_file, "")
        self.assertIsNone(payload)
        self.assertEqual(seen, "")

    def moved_test_pty_harness_deduplicates_control_marker(self):
        pty_harness = load_pty_harness_module()
        control_file = pathlib.Path(self.tempdir.name) / "control.json"
        control_file.write_text(json.dumps({"command_id": "op1", "action": "interrupt"}))
        payload, seen = pty_harness.read_control(control_file, "")
        self.assertEqual(payload["action"], "interrupt")
        payload_again, seen_again = pty_harness.read_control(control_file, seen)
        self.assertIsNone(payload_again)
        self.assertEqual(seen_again, "op1:interrupt")

    def moved_test_pty_harness_rejects_control_for_mismatched_session(self):
        pty_harness = load_pty_harness_module()
        self.assertFalse(
            pty_harness.control_matches_session(
                {"expected_supervisor_pid": 999, "expected_child_pid": 123},
                supervisor_pid=1000,
                child_pid=123,
            )
        )
        self.assertFalse(
            pty_harness.control_matches_session(
                {"expected_supervisor_pid": 1000, "expected_child_pid": 124},
                supervisor_pid=1000,
                child_pid=123,
            )
        )
        self.assertTrue(
            pty_harness.control_matches_session(
                {"expected_supervisor_pid": 1000, "expected_child_pid": 123},
                supervisor_pid=1000,
                child_pid=123,
            )
        )

    def moved_test_pty_harness_prefers_process_group_signal(self):
        pty_harness = load_pty_harness_module()
        with patch.object(pty_harness.os, "getpgid", return_value=4321), \
             patch.object(pty_harness.os, "killpg") as killpg, \
             patch.object(pty_harness.os, "kill") as kill:
            target = pty_harness.signal_child_tree(1234, 15)
        self.assertEqual(target, "process_group")
        killpg.assert_called_once_with(4321, 15)
        kill.assert_not_called()

    def moved_test_pty_harness_falls_back_to_process_signal(self):
        pty_harness = load_pty_harness_module()
        with patch.object(pty_harness.os, "getpgid", side_effect=OSError()), \
             patch.object(pty_harness.os, "kill", return_value=None) as kill:
            target = pty_harness.signal_child_tree(1234, 2)
        self.assertEqual(target, "process")
        kill.assert_called_once_with(1234, 2)

    def moved_test_pty_harness_kill_escalates_when_child_tree_survives(self):
        pty_harness = load_pty_harness_module()
        with patch.object(pty_harness, "signal_child_tree", side_effect=["process_group", "process_group", "missing", "process_group"]) as signal_tree, \
             patch.object(pty_harness.time, "sleep", return_value=None), \
             patch.object(pty_harness.time, "time", side_effect=[0.0, 0.02, 0.04]):
            target = pty_harness.terminate_child_tree(1234, grace_seconds=0.1)
        self.assertEqual(target, "process_group")
        self.assertEqual(signal_tree.call_args_list[0].args, (1234, pty_harness.signal.SIGTERM))

    def moved_test_pty_harness_kill_escalates_to_sigkill_after_grace(self):
        pty_harness = load_pty_harness_module()
        with patch.object(pty_harness, "signal_child_tree", side_effect=["process_group", "process_group", "process_group", "process_group"]) as signal_tree, \
             patch.object(pty_harness.time, "sleep", return_value=None), \
             patch.object(pty_harness.time, "time", side_effect=[0.0, 0.02, 0.12]):
            target = pty_harness.terminate_child_tree(1234, grace_seconds=0.1)
        self.assertEqual(target, "process_group_escalated")
        self.assertEqual(signal_tree.call_args_list[0].args, (1234, pty_harness.signal.SIGTERM))
        self.assertEqual(signal_tree.call_args_list[-1].args, (1234, pty_harness.signal.SIGKILL))

    def moved_test_pty_harness_terminate_child_tree_kills_real_process_group(self):
        pty_harness = load_pty_harness_module()
        proc = subprocess.Popen(
            [
                "/bin/bash",
                "-lc",
                'trap "" TERM; (trap "" TERM; sleep 30) & child=$!; echo $child > "$0"; wait',
                str(pathlib.Path(self.tempdir.name) / "child.pid"),
            ],
            preexec_fn=os.setsid,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            time_limit = time.time() + 2
            while time.time() < time_limit and proc.poll() is None:
                child_file = pathlib.Path(self.tempdir.name) / "child.pid"
                if child_file.exists():
                    break
                time.sleep(0.05)
            target = pty_harness.terminate_child_tree(proc.pid, grace_seconds=0.2)
            proc.wait(timeout=3)
            self.assertIn(target, {"process_group", "process_group_escalated"})
            self.assertIsNotNone(proc.returncode)
        finally:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass

    @unittest.skipUnless(shutil.which("bwrap"), "bwrap unavailable")
    def moved_test_strict_bwrap_blocks_filesystem_escape_to_unbound_path(self):
        workdir = pathlib.Path(self.tempdir.name) / "work"
        workdir.mkdir()
        secret_dir = pathlib.Path(self.tempdir.name) / "secret"
        secret_dir.mkdir()
        secret_file = secret_dir / "secret.txt"
        secret_file.write_text("top-secret")
        proc = self._run_minimal_strict_bwrap(
            workdir,
            f'test ! -e {shlex.quote(str(secret_file))}',
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)

    @unittest.skipUnless(shutil.which("bwrap"), "bwrap unavailable")
    def moved_test_strict_bwrap_blocks_arbitrary_network(self):
        workdir = pathlib.Path(self.tempdir.name) / "net"
        workdir.mkdir()
        cmd = (
            "python3 -c \"import socket,sys; "
            "s=socket.socket(); s.settimeout(1); "
            "rc=s.connect_ex(('1.1.1.1',80)); "
            "sys.exit(1 if rc == 0 else 0)\""
        )
        proc = self._run_minimal_strict_bwrap(workdir, cmd)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)

    def moved_test_dashboard_collect_snapshot_includes_runs_and_counts(self):
        dashboard = load_dashboard_module()
        root = pathlib.Path(self.tempdir.name)
        dashboard.HARNESS_RUNS = root / ".harness_runs.json"
        dashboard.HARNESS_ACTIVE_RUN = root / ".harness_active_run.json"
        dashboard.HARNESS_RUN_ROOT = root / ".runtime" / "harness"
        dashboard.PROFILES = root / ".profiles.json"
        dashboard.CLIENT_BINDINGS = root / ".client_bindings.json"
        run_id = "run_demo"
        (dashboard.HARNESS_RUN_ROOT / run_id / "state").mkdir(parents=True)
        (dashboard.HARNESS_RUN_ROOT / run_id / "events.jsonl").write_text(
            json.dumps({"timestamp": "2026-04-05T00:00:00+00:00", "event_type": "run.registered"}) + "\n"
        )
        (dashboard.HARNESS_RUN_ROOT / run_id / "state" / "governor.json").write_text(
            json.dumps({"verification_only_mode": True, "writes_since_verification": 2})
        )
        (dashboard.HARNESS_RUN_ROOT / run_id / "state" / "intervention.json").write_text(
            json.dumps({"status": "active", "notice": "Run tests", "next_action": "pytest -q"})
        )
        (dashboard.HARNESS_RUN_ROOT / run_id / "state" / "session.json").write_text(
            json.dumps({"status": "running", "child_pid": 12345})
        )
        (dashboard.HARNESS_RUN_ROOT / run_id / "artifacts").mkdir(parents=True)
        (dashboard.HARNESS_RUN_ROOT / run_id / "artifacts" / "pty-output.log").write_text("agent output\n")
        dashboard.HARNESS_RUNS.write_text(json.dumps({"runs": {run_id: {"run_id": run_id, "provider": "claude", "policy_profile": "balanced", "status": "running", "created_at": "2026-04-05T00:00:00+00:00"}}}))
        dashboard.HARNESS_ACTIVE_RUN.write_text(json.dumps({"run_id": run_id}))
        dashboard.PROFILES.write_text(json.dumps({"app": {"team": "demo"}}))
        dashboard.CLIENT_BINDINGS.write_text(json.dumps({"tokens": {"tok": {"profile": "app"}}}))
        with patch.object(dashboard, "gateway_status", return_value={"live": True, "ready": True, "health_models": 3, "port": 4000, "error": ""}), \
             patch.object(dashboard, "session_is_live", return_value=True):
            snapshot = dashboard.collect_snapshot()
        self.assertEqual(snapshot["summary"]["active_runs"], 1)
        self.assertEqual(snapshot["summary"]["blocked_runs"], 1)
        self.assertEqual(snapshot["summary"]["attention_runs"], 1)
        self.assertEqual(snapshot["summary"]["recent_states"][0]["label"], "Paused for proof")
        self.assertEqual(snapshot["profiles"]["count"], 1)
        self.assertEqual(snapshot["client_tokens"]["count"], 1)
        self.assertTrue(snapshot["harness"]["runs"][0]["is_active"])
        self.assertEqual(snapshot["harness"]["runs"][0]["intervention"]["notice"], "Run tests")
        self.assertEqual(snapshot["harness"]["runs"][0]["session"]["child_pid"], 12345)
        self.assertIn("agent output", snapshot["harness"]["runs"][0]["output_tail"])
        self.assertTrue(snapshot["harness"]["runs"][0]["is_live"])
        self.assertEqual(snapshot["harness"]["runs"][0]["derived_status"], "running")

    def moved_test_dashboard_collect_snapshot_marks_stale_running_record_as_not_active(self):
        dashboard = load_dashboard_module()
        root = pathlib.Path(self.tempdir.name)
        dashboard.HARNESS_RUNS = root / ".harness_runs.json"
        dashboard.HARNESS_ACTIVE_RUN = root / ".harness_active_run.json"
        dashboard.HARNESS_RUN_ROOT = root / ".runtime" / "harness"
        dashboard.PROFILES = root / ".profiles.json"
        dashboard.CLIENT_BINDINGS = root / ".client_bindings.json"
        run_id = "run_stale"
        (dashboard.HARNESS_RUN_ROOT / run_id / "state").mkdir(parents=True)
        (dashboard.HARNESS_RUN_ROOT / run_id / "state" / "session.json").write_text(
            json.dumps({"status": "running", "child_pid": 99999})
        )
        dashboard.HARNESS_RUNS.write_text(json.dumps({"runs": {run_id: {"run_id": run_id, "provider": "claude", "policy_profile": "balanced", "status": "running", "created_at": "2026-04-05T00:00:00+00:00"}}}))
        dashboard.HARNESS_ACTIVE_RUN.write_text(json.dumps({}))
        dashboard.PROFILES.write_text(json.dumps({}))
        dashboard.CLIENT_BINDINGS.write_text(json.dumps({"tokens": {}}))
        with patch.object(dashboard, "gateway_status", return_value={"live": True, "ready": True, "health_models": 1, "port": 4000, "error": ""}), \
             patch.object(dashboard, "session_is_live", return_value=False):
            snapshot = dashboard.collect_snapshot()
        self.assertEqual(snapshot["summary"]["active_runs"], 0)
        self.assertEqual(snapshot["summary"]["recent_states"][0]["label"], "Stale record")
        self.assertEqual(snapshot["harness"]["runs"][0]["derived_status"], "stale")

    def moved_test_dashboard_collect_snapshot_marks_failed_launch_state(self):
        dashboard = load_dashboard_module()
        root = pathlib.Path(self.tempdir.name)
        dashboard.HARNESS_RUNS = root / ".harness_runs.json"
        dashboard.HARNESS_ACTIVE_RUN = root / ".harness_active_run.json"
        dashboard.HARNESS_RUN_ROOT = root / ".runtime" / "harness"
        dashboard.PROFILES = root / ".profiles.json"
        dashboard.CLIENT_BINDINGS = root / ".client_bindings.json"
        run_id = "run_failed"
        (dashboard.HARNESS_RUN_ROOT / run_id / "state").mkdir(parents=True)
        dashboard.HARNESS_RUNS.write_text(json.dumps({"runs": {run_id: {"run_id": run_id, "provider": "claude", "policy_profile": "balanced", "status": "failed_launch", "created_at": "2026-04-05T00:00:00+00:00"}}}))
        dashboard.HARNESS_ACTIVE_RUN.write_text(json.dumps({}))
        dashboard.PROFILES.write_text(json.dumps({}))
        dashboard.CLIENT_BINDINGS.write_text(json.dumps({"tokens": {}}))
        with patch.object(dashboard, "gateway_status", return_value={"live": True, "ready": True, "health_models": 1, "port": 4000, "error": ""}):
            snapshot = dashboard.collect_snapshot()
        self.assertEqual(snapshot["summary"]["recent_states"][0]["label"], "Failed launch")

    def moved_test_dashboard_override_run_intervention_force_and_clear(self):
        dashboard = load_dashboard_module()
        root = pathlib.Path(self.tempdir.name)
        dashboard.HARNESS_RUN_ROOT = root / ".runtime" / "harness"
        run_id = "run_demo"
        state_dir = dashboard.HARNESS_RUN_ROOT / run_id / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "governor.json").write_text(
            json.dumps({"last_command_id": "cmd-1", "verification_required": False, "verification_only_mode": False})
        )

        forced = dashboard.override_run_intervention(run_id, "force_verify")
        self.assertTrue(forced["ok"])
        forced_governor = json.loads((state_dir / "governor.json").read_text())
        forced_intervention = json.loads((state_dir / "intervention.json").read_text())
        self.assertTrue(forced_governor["verification_required"])
        self.assertTrue(forced_governor["verification_only_mode"])
        self.assertEqual(forced_intervention["status"], "active")

        cleared = dashboard.override_run_intervention(run_id, "clear")
        self.assertTrue(cleared["ok"])
        cleared_governor = json.loads((state_dir / "governor.json").read_text())
        cleared_intervention = json.loads((state_dir / "intervention.json").read_text())
        self.assertFalse(cleared_governor["verification_required"])
        self.assertFalse(cleared_governor["verification_only_mode"])
        self.assertEqual(cleared_intervention["status"], "resolved")

    def moved_test_dashboard_operator_run_action_writes_control_file(self):
        dashboard = load_dashboard_module()
        root = pathlib.Path(self.tempdir.name)
        dashboard.HARNESS_RUN_ROOT = root / ".runtime" / "harness"
        run_id = "run_demo"
        state_dir = dashboard.HARNESS_RUN_ROOT / run_id / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "session.json").write_text(json.dumps({"status": "running", "child_pid": 4321}))
        with patch.object(dashboard, "session_is_live", return_value=True):
            result = dashboard.operator_run_action(run_id, "interrupt")
        self.assertTrue(result["ok"])
        control = json.loads((state_dir / "control.json").read_text())
        self.assertEqual(control["action"], "interrupt")
        self.assertEqual(control["expected_child_pid"], 4321)

    def moved_test_dashboard_operator_run_action_rejects_dead_session_controls(self):
        dashboard = load_dashboard_module()
        root = pathlib.Path(self.tempdir.name)
        dashboard.HARNESS_RUN_ROOT = root / ".runtime" / "harness"
        run_id = "run_demo"
        state_dir = dashboard.HARNESS_RUN_ROOT / run_id / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "session.json").write_text(json.dumps({"status": "completed", "child_pid": 4321, "exit_code": 0}))
        with patch.object(dashboard, "session_is_live", return_value=False):
            result = dashboard.operator_run_action(run_id, "kill")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "run_session_not_live")
        self.assertFalse((state_dir / "control.json").exists())

    def moved_test_dashboard_launch_agent_builds_harness_command(self):
        dashboard = load_dashboard_module()
        with patch.object(dashboard, "spawn_terminal_command", return_value={"ok": True, "terminal": "alacritty"}) as mocked:
            result = dashboard.launch_agent("codex", "balanced", "strict", 'exec --json "hello"')
        self.assertTrue(result["ok"])
        command, title = mocked.call_args[0]
        self.assertIn("harness run", command)
        self.assertIn("--provider codex", command)
        self.assertIn("--policy balanced", command)
        self.assertIn("--sandbox strict", command)
        self.assertIn("exec --json hello", command)
        self.assertIn("codex", title)

    def moved_test_dashboard_launch_agent_builds_plain_launch_command_when_harness_off(self):
        dashboard = load_dashboard_module()
        with patch.object(dashboard, "spawn_terminal_command", return_value={"ok": True, "terminal": "alacritty"}) as mocked:
            result = dashboard.launch_agent("claude", "off", "normal", "")
        self.assertTrue(result["ok"])
        command, title = mocked.call_args[0]
        self.assertIn("sandbox set normal", command)
        self.assertIn("launch claude", command)
        self.assertNotIn("harness run", command)
        self.assertEqual(title, "BrokeLLM claude")

    def moved_test_dashboard_reconcile_runs_parses_mapping_output(self):
        dashboard = load_dashboard_module()
        fake = subprocess.CompletedProcess(
            args=["python3"],
            returncode=0,
            stdout=json.dumps({"changed": [{"run_id": "r1", "status": "abandoned"}]}),
            stderr="",
        )
        with patch.object(dashboard.subprocess, "run", return_value=fake):
            result = dashboard.reconcile_runs()
        self.assertTrue(result["ok"])
        self.assertEqual(result["changed"][0]["run_id"], "r1")

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
        answers = iter(["0", "11"])
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
        answers = iter(["0", "11"])
        try:
            builtins.input = lambda _prompt="": next(answers)
            self.capture(self.mod.cmd_swap)
        finally:
            builtins.input = original_input

        health_payload = {
            "healthy_endpoints": [{"model": "openai/gpt-4o-mini"}],
            "unhealthy_endpoints": [],
        }
        env_path = self.mod.DIR / ".env"
        env_path.write_text("GITHUB_TOKEN=test-key\n")

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

    def moved_test_mapping_reconcile_marks_stale_running_run_abandoned(self):
        record = self.mod._register_harness_run("claude", "balanced", "medium", "normal", str(self.mod.DIR), [str(self.mod.DIR)])
        run_id = record["run_id"]
        self.mod.HARNESS_RUN_ROOT.joinpath(run_id, "state").mkdir(parents=True, exist_ok=True)
        self.mod.HARNESS_RUN_ROOT.joinpath(run_id, "state", "session.json").write_text(
            json.dumps({"status": "running", "child_pid": 999999})
        )
        with patch.object(self.mod, "_pid_is_live", return_value=False):
            result = self.mod._reconcile_harness_runs()
        self.assertEqual(result["changed"][0]["status"], "abandoned")
        saved = json.loads(self.mod.HARNESS_RUNS.read_text())
        self.assertEqual(saved["runs"][run_id]["status"], "abandoned")

    def moved_test_mapping_reconcile_marks_dead_completed_session_completed(self):
        record = self.mod._register_harness_run("codex", "balanced", "medium", "normal", str(self.mod.DIR), [str(self.mod.DIR)])
        run_id = record["run_id"]
        self.mod.HARNESS_RUN_ROOT.joinpath(run_id, "state").mkdir(parents=True, exist_ok=True)
        self.mod.HARNESS_RUN_ROOT.joinpath(run_id, "state", "session.json").write_text(
            json.dumps({"status": "completed", "child_pid": 999999, "exit_code": 0})
        )
        with patch.object(self.mod, "_pid_is_live", return_value=False):
            result = self.mod._reconcile_harness_runs()
        change = next(item for item in result["changed"] if item["run_id"] == run_id)
        self.assertEqual(change["status"], "completed")
        saved = json.loads(self.mod.HARNESS_RUNS.read_text())
        self.assertEqual(saved["runs"][run_id]["status"], "completed")

    def moved_test_mapping_reconcile_marks_missing_session_failed_launch(self):
        record = self.mod._register_harness_run("claude", "balanced", "medium", "normal", str(self.mod.DIR), [str(self.mod.DIR)])
        run_id = record["run_id"]
        with patch.object(self.mod, "_pid_is_live", return_value=False):
            result = self.mod._reconcile_harness_runs()
        change = next(item for item in result["changed"] if item["run_id"] == run_id)
        self.assertEqual(change["status"], "failed_launch")
        saved = json.loads(self.mod.HARNESS_RUNS.read_text())
        self.assertEqual(saved["runs"][run_id]["status"], "failed_launch")

    def moved_test_mapping_reconcile_clears_active_pointer_for_dead_run(self):
        record = self.mod._register_harness_run("claude", "balanced", "medium", "normal", str(self.mod.DIR), [str(self.mod.DIR)])
        run_id = record["run_id"]
        self.mod.HARNESS_RUN_ROOT.joinpath(run_id, "state").mkdir(parents=True, exist_ok=True)
        self.mod.HARNESS_RUN_ROOT.joinpath(run_id, "state", "session.json").write_text(
            json.dumps({"status": "running", "child_pid": 999999})
        )
        with patch.object(self.mod, "_pid_is_live", return_value=False):
            result = self.mod._reconcile_harness_runs()
        self.assertEqual(result["active_run"], {})
        self.assertEqual(json.loads(self.mod.HARNESS_ACTIVE_RUN.read_text()), {})

    def moved_test_mapping_reconcile_is_idempotent_after_first_repair(self):
        record = self.mod._register_harness_run("claude", "balanced", "medium", "normal", str(self.mod.DIR), [str(self.mod.DIR)])
        run_id = record["run_id"]
        self.mod.HARNESS_RUN_ROOT.joinpath(run_id, "state").mkdir(parents=True, exist_ok=True)
        self.mod.HARNESS_RUN_ROOT.joinpath(run_id, "state", "session.json").write_text(
            json.dumps({"status": "running", "child_pid": 999999})
        )
        with patch.object(self.mod, "_pid_is_live", return_value=False):
            first = self.mod._reconcile_harness_runs()
            second = self.mod._reconcile_harness_runs()
        self.assertEqual(len(first["changed"]), 1)
        self.assertEqual(second["changed"], [])

    def test_install_uses_python_module_pip(self):
        install_sh = (REPO_ROOT / "install.sh").read_text()
        requirements_lock = (REPO_ROOT / "requirements.lock").read_text()
        requirements_txt = (REPO_ROOT / "requirements.txt").read_text()
        self.assertIn('pip_args=(-m pip install --require-hashes -r "$LOCKFILE" --quiet)', install_sh)
        self.assertIn('"$PY" -m pip download --require-hashes -r "$LOCKFILE" -d "$WHEEL_DIR" --quiet', install_sh)
        self.assertIn("litellm[proxy]==1.83.0", requirements_txt)
        self.assertIn("litellm==1.83.0", requirements_lock)
        self.assertIn('chmod 600 "$DIR/.env"', install_sh)

    def test_strict_bwrap_overlays_absolute_path_shims_for_escape_prone_tools(self):
        broke_sh = (REPO_ROOT / "bin" / "broke").read_text()
        self.assertIn('for tool in git pytest npm pnpm pip python python3 node go cargo make sh bash env; do', broke_sh)
        self.assertIn('args+=(--bind "$shim_path" "$real")', broke_sh)

    def moved_test_harness_common_read_json_returns_default_on_partial_json(self):
        common = load_harness_common_module()
        path = pathlib.Path(self.tempdir.name) / "partial.json"
        path.write_text("{bad json")
        self.assertEqual(common.read_json(path, {"fallback": True}), {"fallback": True})

    def moved_test_harness_common_atomic_write_json_writes_complete_json(self):
        common = load_harness_common_module()
        path = pathlib.Path(self.tempdir.name) / "state.json"
        common.atomic_write_json(path, {"ok": True, "n": 3})
        loaded = json.loads(path.read_text())
        self.assertEqual(loaded, {"ok": True, "n": 3})
        self.assertTrue(path.read_text().endswith("\n"))

    def test_preflight_detects_pythonpath_pollution(self):
        with patch.object(self.mod, "_parse_lock_versions", return_value={"litellm": "1.83.0"}), \
             patch.object(self.mod, "_parse_requirements_txt", return_value={"litellm": "1.83.0"}), \
             patch.object(self.mod, "_installed_versions", return_value={"litellm": "1.83.0"}), \
             patch.object(self.mod, "_unexpected_pth_files", return_value=[]), \
             patch.object(self.mod, "_bad_runtime_permissions", return_value=[]), \
             patch.dict(os.environ, {"PYTHONPATH": "/tmp/pwn"}, clear=False):
            self.assertFalse(self.mod.cmd_preflight(quiet=True))

    def test_preflight_warns_on_shared_runtime_drift_by_default(self):
        with patch.object(self.mod, "_parse_lock_versions", return_value={"litellm": "1.83.0", "attrs": "26.1.0"}), \
             patch.object(self.mod, "_parse_requirements_txt", return_value={"litellm": "1.83.0"}), \
             patch.object(self.mod, "_installed_versions", return_value={"litellm": "1.83.0", "attrs": "25.4.0"}), \
             patch.object(self.mod, "_unexpected_pth_files", return_value=[pathlib.Path("weird.pth")]), \
             patch.object(self.mod, "_bad_runtime_permissions", return_value=[]), \
             patch.dict(os.environ, {}, clear=False):
            self.assertTrue(self.mod.cmd_preflight(quiet=True))

    def test_nspkg_pth_files_are_allowlisted(self):
        with patch.object(
            self.mod,
            "_site_pth_files",
            return_value=[
                pathlib.Path("google_generativeai-0.8.6-py3.13-nspkg.pth"),
                pathlib.Path("zope.interface-5.4.0-nspkg.pth"),
            ],
        ):
            self.assertEqual(self.mod._unexpected_pth_files(), [])

    def test_preflight_fails_on_bad_harness_shim_dir(self):
        shim_dir = self.mod.HARNESS_RUN_ROOT / "run_test" / "shims"
        shim_dir.mkdir(parents=True)
        (shim_dir / "git").write_text("not-a-symlink\n")
        with patch.object(self.mod, "_parse_lock_versions", return_value={"litellm": "1.83.0"}), \
             patch.object(self.mod, "_parse_requirements_txt", return_value={"litellm": "1.83.0"}), \
             patch.object(self.mod, "_installed_versions", return_value={"litellm": "1.83.0"}), \
             patch.object(self.mod, "_unexpected_pth_files", return_value=[]), \
             patch.object(self.mod, "_bad_runtime_permissions", return_value=[]), \
             patch.dict(os.environ, {}, clear=False):
            self.assertFalse(self.mod.cmd_preflight(quiet=True))

    def test_harness_verdict_retries_on_correctness_failures(self):
        cfg = self.mod._default_harness_config()
        cfg["mode"] = "balanced"
        summary = self.mod._harness_verdict(
            cfg,
            {"ok": [], "warn": [], "fail": []},
            {"ok": [], "warn": [], "fail": ["sonnet: missing fields: key"]},
            role_verdicts={"worker": None, "verifier": "RETRY_BROAD", "adversary": None},
            risk="normal",
            retries=0,
        )
        self.assertEqual(summary["verdict"], "RETRY_NARROW")
        self.assertIn("correctness", summary["categories"])

    def test_harness_verdict_blocks_on_integrity_failure(self):
        cfg = self.mod._default_harness_config()
        cfg["mode"] = "throughput"
        summary = self.mod._harness_verdict(
            cfg,
            {"ok": [], "warn": [], "fail": ["PYTHONPATH is set; launch-time import path pollution is not allowed"]},
            {"ok": [], "warn": [], "fail": []},
            role_verdicts={},
            risk="normal",
            retries=0,
        )
        self.assertEqual(summary["verdict"], "BLOCK")
        self.assertIn("integrity", summary["categories"])

    def test_harness_verdict_flags_evidence_gap_when_diff_has_no_tests(self):
        cfg = self.mod._default_harness_config()
        cfg["mode"] = "balanced"
        cfg["profiles"]["balanced"]["retry_on"] = ["correctness", "verification", "suspicious_tests", "evidence"]
        summary = self.mod._harness_verdict(
            cfg,
            {"ok": [], "warn": [], "fail": []},
            {"ok": [], "warn": [], "fail": []},
            role_verdicts={},
            risk="normal",
            retries=0,
            evidence_summary={"diff_present": True, "tests_present": False, "commands_present": True, "policy_events_present": False},
        )
        self.assertIn("evidence", summary["categories"])
        self.assertEqual(summary["verdict"], "RETRY_NARROW")

    def test_harness_verdict_retries_when_review_lane_is_degraded(self):
        cfg = self.mod._default_harness_config()
        cfg["mode"] = "balanced"
        summary = self.mod._harness_verdict(
            cfg,
            {"ok": [], "warn": [], "fail": []},
            {"ok": [], "warn": [], "fail": []},
            role_verdicts={},
            risk="normal",
            retries=0,
            evidence_summary={"diff_present": False, "tests_present": True, "commands_present": True, "policy_events_present": False},
            lane_states={
                "worker": self.mod._default_harness_lane("worker"),
                "verifier": {**self.mod._default_harness_lane("verifier"), "health": "degraded", "degraded_reason": "timeout"},
                "adversary": self.mod._default_harness_lane("adversary"),
            },
        )
        self.assertIn("review_degraded", summary["categories"])
        self.assertEqual(summary["verdict"], "RETRY_NARROW")

    def test_broke_help_mentions_gemini_acp(self):
        broke_sh = (REPO_ROOT / "bin" / "broke").read_text()
        self.assertIn("broke gemini-acp [args...]", broke_sh)


    def test_harness_evaluate_populates_cache_layers(self):
        argv = [
            "mapping.py",
            "harness",
            "evaluate",
            "--worker",
            "ACCEPT",
            "--task",
            "Fix fallback routing",
            "--diff",
            "bin/_mapping.py changed",
            "--tests",
            "python3 -m unittest",
            "--commands",
            "broke validate",
        ]
        with patch.object(self.mod, "_preflight_findings", return_value={"ok": [], "warn": [], "fail": []}), \
             patch.object(self.mod, "_validate_findings", return_value={"ok": [], "warn": [], "fail": []}), \
             patch.object(self.mod.sys, "argv", argv):
            out = self.capture(self.mod.cmd_harness, "evaluate", worker="ACCEPT")

        contracts = json.loads(self.mod.HARNESS_PROMPT_CONTRACTS.read_text())
        prefixes = json.loads(self.mod.HARNESS_PREFIX_CACHE.read_text())
        evidence = json.loads(self.mod.HARNESS_EVIDENCE_CACHE.read_text())
        reviews = json.loads(self.mod.HARNESS_REVIEW_CACHE.read_text())

        self.assertIn("prompt.worker.base.v1", contracts["contracts"])
        self.assertGreaterEqual(len(prefixes["prefixes"]), 3)
        self.assertGreaterEqual(len(evidence["artifacts"]), 5)
        self.assertEqual(len(evidence["checkpoints"]), 1)
        self.assertIn("reused final verdict : no", out)
        self.assertEqual(len(reviews["results"]), 1)
        self.assertEqual(len(reviews["verdicts"]), 1)
        self.assertIn("contributions", reviews)
        checkpoint = next(iter(evidence["checkpoints"].values()))
        self.assertEqual(checkpoint["evidence_contract_version"], "v2")
        self.assertEqual(len(checkpoint["observation_hashes"]), 6)
        self.assertEqual(len(checkpoint["inference_hashes"]), 1)

    def test_harness_evaluate_records_lane_state_and_contributions(self):
        cfg = self.mod._default_harness_config()
        cfg["mode"] = "balanced"
        self.mod._save_harness_config(cfg)
        argv = [
            "mapping.py",
            "harness",
            "evaluate",
            "--worker",
            "ACCEPT",
            "--verifier-health",
            "degraded",
            "--verifier-error",
            "rate_limited",
            "--task",
            "Fix fallback routing",
            "--diff",
            "bin/_mapping.py changed",
            "--tests",
            "python3 -m unittest",
            "--commands",
            "broke validate",
        ]
        with patch.object(self.mod, "_preflight_findings", return_value={"ok": [], "warn": [], "fail": []}), \
             patch.object(self.mod, "_validate_findings", return_value={"ok": [], "warn": [], "fail": []}), \
             patch.object(self.mod.sys, "argv", argv):
            self.capture(self.mod.cmd_harness, "evaluate", worker="ACCEPT")

        state = json.loads(self.mod.HARNESS_STATE.read_text())
        reviews = json.loads(self.mod.HARNESS_REVIEW_CACHE.read_text())
        self.assertEqual(state["lanes"]["worker"]["last_verdict"], "ACCEPT")
        self.assertEqual(state["lanes"]["verifier"]["health"], "degraded")
        self.assertEqual(state["lanes"]["verifier"]["degraded_reason"], "rate_limited")
        self.assertIn("review_degraded", state["last_verdict"]["categories"])
        self.assertEqual(len(reviews["contributions"]), 3)
        self.assertIn("verdict_contributions", state["last_verdict"])

    def test_harness_checklist_command_prints_implemented_items(self):
        out = self.capture(self.mod.cmd_harness, "checklist")
        self.assertIn("Persistent lane instances", out)
        self.assertIn("Degraded review-lane policy", out)
        self.assertIn("Observation / inference split", out)

    def test_harness_status_prints_runtime_registry(self):
        cfg = self.mod._default_harness_config()
        cfg["mode"] = "balanced"
        self.mod._save_harness_config(cfg)
        out = self.capture(self.mod.cmd_harness, "status")
        self.assertIn("GeminiNativeAcpRuntime", out)
        self.assertIn("ClaudeAgentAcpShimRuntime", out)
        self.assertIn("CodexAcpShimRuntime", out)

    def test_harness_evaluate_reuses_cached_role_and_final_verdict(self):
        first_argv = [
            "mapping.py",
            "harness",
            "evaluate",
            "--verifier",
            "RETRY_BROAD",
            "--task",
            "Fix fallback routing",
            "--diff",
            "bin/_mapping.py changed",
            "--tests",
            "python3 -m unittest",
        ]
        second_argv = [
            "mapping.py",
            "harness",
            "evaluate",
            "--task",
            "Fix fallback routing",
            "--diff",
            "bin/_mapping.py changed",
            "--tests",
            "python3 -m unittest",
        ]
        with patch.object(self.mod, "_preflight_findings", return_value={"ok": [], "warn": [], "fail": []}), \
             patch.object(self.mod, "_validate_findings", return_value={"ok": [], "warn": [], "fail": []}), \
             patch.object(self.mod.sys, "argv", first_argv):
            self.capture(self.mod.cmd_harness, "evaluate", verifier="RETRY_BROAD")

        with patch.object(self.mod, "_preflight_findings", return_value={"ok": [], "warn": [], "fail": []}), \
             patch.object(self.mod, "_validate_findings", return_value={"ok": [], "warn": [], "fail": []}), \
             patch.object(self.mod.sys, "argv", second_argv):
            out = self.capture(self.mod.cmd_harness, "evaluate")

        state = json.loads(self.mod.HARNESS_STATE.read_text())
        self.assertEqual(state["last_verdict"]["role_verdicts"]["verifier"], "RETRY_BROAD")
        self.assertTrue(state["last_verdict"]["reused_final_verdict"])
        self.assertIn("reused final verdict : yes", out)

    def test_harness_run_register_creates_active_run_and_ledger(self):
        argv = [
            "mapping.py",
            "harness",
            "run-register",
            "--provider",
            "claude",
            "--policy",
            "balanced",
            "--risk",
            "medium",
            "--sandbox",
            "strict",
            "--workspace",
            str(self.mod.DIR),
            "--allowed-paths",
            f"{self.mod.DIR}:{self.mod.DIR / 'bin'}",
        ]
        with patch.object(self.mod.sys, "argv", argv):
            out = self.capture(self.mod.cmd_harness, "run-register", risk="medium")

        record = json.loads(out.strip())
        active = json.loads(self.mod.HARNESS_ACTIVE_RUN.read_text())
        runs = json.loads(self.mod.HARNESS_RUNS.read_text())
        events_file = self.mod.HARNESS_RUN_ROOT / record["run_id"] / "events.jsonl"

        self.assertEqual(active["run_id"], record["run_id"])
        self.assertEqual(runs["runs"][record["run_id"]]["policy_profile"], "balanced")
        self.assertTrue(events_file.exists())
        self.assertIn('"event_type": "run.registered"', events_file.read_text())

    def test_harness_run_register_records_provider_direct_worker_lane(self):
        argv = [
            "mapping.py",
            "harness",
            "run-register",
            "--provider",
            "codex",
            "--policy",
            "high_assurance",
            "--risk",
            "high",
            "--sandbox",
            "strict",
            "--workspace",
            str(self.mod.DIR),
            "--allowed-paths",
            str(self.mod.DIR),
            "--worker-route",
            "provider_direct",
            "--credential-source",
            "provider_managed",
            "--elevated",
        ]
        with patch.object(self.mod.sys, "argv", argv):
            out = self.capture(self.mod.cmd_harness, "run-register", risk="high")

        record = json.loads(out.strip())
        self.assertEqual(record["worker_route"], "provider_direct")
        self.assertEqual(record["worker_credential_source"], "provider_managed")
        self.assertTrue(record["elevated"])

    def test_harness_run_register_records_client_direct_worker_lane(self):
        argv = [
            "mapping.py",
            "harness",
            "run-register",
            "--provider",
            "gemini",
            "--policy",
            "balanced",
            "--risk",
            "medium",
            "--sandbox",
            "normal",
            "--workspace",
            str(self.mod.DIR),
            "--allowed-paths",
            str(self.mod.DIR),
            "--worker-route",
            "client_direct",
            "--credential-source",
            "provider_managed",
        ]
        with patch.object(self.mod.sys, "argv", argv):
            out = self.capture(self.mod.cmd_harness, "run-register", risk="medium")

        record = json.loads(out.strip())
        self.assertEqual(record["worker_route"], "client_direct")
        self.assertEqual(record["worker_credential_source"], "provider_managed")
        self.assertFalse(record["elevated"])

    def test_gemini_env_name_is_consistent(self):
        broke_sh = (REPO_ROOT / "bin" / "broke").read_text()
        env_template = (REPO_ROOT / ".env.template").read_text()
        self.assertIn("GEMINI_API_KEY", broke_sh)
        self.assertIn("GEMINI_API_KEY", env_template)
        self.assertNotIn("GOOGLE_AI_STUDIO_API_KEY", broke_sh)

    def test_broke_script_auto_registers_harness_when_mode_enabled(self):
        broke_sh = (REPO_ROOT / "bin" / "broke").read_text()
        self.assertIn('configured_harness_mode()', broke_sh)
        self.assertIn('auto_register_harness_if_enabled "$p"', broke_sh)
        self.assertIn('auto_register_harness_if_enabled "$target"', broke_sh)
        self.assertIn('mode="$(get_claude_env_export "BROKE_HARNESS_MODE")"', broke_sh)
        self.assertIn('[ "$mode" = "off" ] && return 0', broke_sh)
        self.assertIn('"$provider" = "gemini"', broke_sh)
        self.assertIn('run_harness_supervised_env_command()', broke_sh)
        self.assertIn('python3 "$DIR/bin/_pty_harness.py" -- "$@"', broke_sh)
        self.assertIn('python3 "$DIR/bin/_dashboard.py" "$dash_port"', broke_sh)
        self.assertIn('BROKE_DASHBOARD_GATEWAY_PORT="$gateway_port"', broke_sh)

    def test_config_emits_multiple_deployments_when_provider_has_multiple_keys(self):
        env_path = self.mod.DIR / ".env"
        env_path.write_text(
            "\n".join(
                [
                    "OPENROUTER_API_KEY=or-1",
                    "OPENROUTER_API_KEY_2=or-2",
                    "GROQ_API_KEY=groq-1",
                    "GROQ_API_KEY_2=groq-2",
                    "CEREBRAS_API_KEY=cer-1",
                    "CEREBRAS_API_KEY_2=cer-2",
                    "GITHUB_TOKEN=gh-1",
                    "GITHUB_TOKEN_2=gh-2",
                    "GEMINI_API_KEY=gem-1",
                    "GEMINI_API_KEY_2=gem-2",
                    "HF_TOKEN=hf-1",
                    "HF_TOKEN_2=hf-2",
                ]
            )
            + "\n"
        )

        mapping = {
            "sonnet": {
                "provider": "openrouter",
                "model": "qwen/qwen3.6-plus:free",
                "label": "OR/Qwen-3.6+",
                "key": "OPENROUTER_API_KEY",
            },
            "opus": {
                "provider": "cerebras",
                "model": "qwen-3-235b-a22b-instruct-2507",
                "label": "Cerebras/Qwen-3-235B",
                "key": "CEREBRAS_API_KEY",
            },
            "haiku": {
                "provider": "groq",
                "model": "groq/compound",
                "label": "Groq/Compound",
                "key": "GROQ_API_KEY",
                "pinned": False,
            },
            "default": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "label": "GitHub/GPT-4o-mini",
                "key": "GITHUB_TOKEN",
                "api_base": "https://models.inference.ai.azure.com",
                "pinned": False,
            },
            "subagent": {
                "provider": "gemini",
                "model": "gemini-2.0-flash",
                "label": "Gemini/2.0-Flash",
                "key": "GEMINI_API_KEY",
            },
            "_lane_fallback_targets": {
                "sonnet": [
                    {
                        "provider": "huggingface",
                        "model": "meta-llama/Llama-3.1-8B-Instruct",
                        "label": "HF/Llama-3.1-8B",
                        "key": "HF_TOKEN",
                    }
                ]
            },
        }
        self.write_mapping(mapping)

        self.capture(self.mod.cmd_config)
        config = json.loads(self.mod.CONFIG.read_text())
        deployments = config["model_list"]
        deployment_map = json.loads(self.mod.DEPLOYMENTS.read_text())

        def key_refs(label):
            return sorted(
                item["litellm_params"]["api_key"]
                for item in deployments
                if item["model_info"]["base_model"] == label
            )

        self.assertEqual(
            key_refs("OR/Qwen-3.6+"),
            ["os.environ/OPENROUTER_API_KEY", "os.environ/OPENROUTER_API_KEY_2"],
        )
        self.assertEqual(
            key_refs("Cerebras/Qwen-3-235B"),
            ["os.environ/CEREBRAS_API_KEY", "os.environ/CEREBRAS_API_KEY_2"],
        )
        self.assertEqual(
            key_refs("Groq/Compound"),
            ["os.environ/GROQ_API_KEY", "os.environ/GROQ_API_KEY_2"],
        )
        self.assertEqual(
            key_refs("GitHub/GPT-4o-mini"),
            ["os.environ/GITHUB_TOKEN", "os.environ/GITHUB_TOKEN_2"],
        )
        self.assertEqual(
            key_refs("Gemini/2.0-Flash"),
            ["os.environ/GEMINI_API_KEY", "os.environ/GEMINI_API_KEY_2"],
        )
        self.assertEqual(
            key_refs("HF/Llama-3.1-8B"),
            ["os.environ/HF_TOKEN", "os.environ/HF_TOKEN_2"],
        )
        self.assertEqual(
            [item["key_name"] for item in deployment_map["OR/Qwen-3.6+"]],
            ["OPENROUTER_API_KEY", "OPENROUTER_API_KEY_2"],
        )

    def test_config_includes_team_models_for_profile_routing(self):
        self.capture(self.mod.cmd_team_save, "demo", "1")
        teams = json.loads(self.mod.TEAMS.read_text())
        teams["app-team"] = {
            "mode": 0,
            "slots": {
                "sonnet": {
                    "provider": "groq",
                    "model": "moonshotai/kimi-k2-instruct",
                    "label": "Groq/Kimi-K2",
                    "key": "GROQ_API_KEY",
                }
            },
        }
        self.mod.TEAMS.write_text(json.dumps(teams, indent=2))
        self.capture(self.mod.cmd_config)
        deployments = json.loads(self.mod.DEPLOYMENTS.read_text())
        self.assertIn("Groq/Kimi-K2", deployments)

    def test_key_policy_updates_generation_without_touching_mapping(self):
        before = self.mod.load()
        self.capture(self.mod.cmd_key_policy, "openrouter", mode="round_robin", cooldown="60", retries="2", order="OPENROUTER_API_KEY_2,OPENROUTER_API_KEY")
        policy = json.loads(self.mod.ROTATION_POLICY.read_text())
        self.assertEqual(policy["generation"], 2)
        self.assertEqual(policy["providers"]["openrouter"]["mode"], "round_robin")
        self.assertEqual(policy["providers"]["openrouter"]["order"], ["OPENROUTER_API_KEY_2", "OPENROUTER_API_KEY"])
        self.assertEqual(before, self.load_mapping())

    def test_key_state_manual_override_is_recorded(self):
        self.capture(self.mod.cmd_key_state, "set", "OPENROUTER_API_KEY_2", "blocked")
        state = json.loads(self.mod.KEY_STATE.read_text())
        self.assertEqual(state["keys"]["OPENROUTER_API_KEY_2"]["status"], "blocked")
        self.assertEqual(state["keys"]["OPENROUTER_API_KEY_2"]["last_reason"], "manual_set")

    def test_key_state_manual_cooldown_uses_provider_policy_duration(self):
        self.capture(self.mod.cmd_key_policy, "openrouter", cooldown="45")
        self.capture(self.mod.cmd_key_state, "set", "OPENROUTER_API_KEY", "cooldown")
        state = json.loads(self.mod.KEY_STATE.read_text())
        info = state["keys"]["OPENROUTER_API_KEY"]
        self.assertEqual(info["status"], "cooldown")
        self.assertGreater(info["cooldown_until"], info["updated_at"])

    def test_model_policy_updates_generation_without_touching_mapping(self):
        before = self.mod.load()
        self.capture(self.mod.cmd_model_policy, "sonnet", mode="round_robin", cooldown="90", retries="3", order="GitHub/GPT-4o-mini,Cerebras/GPT-OSS-120B")
        policy = json.loads(self.mod.MODEL_POLICY.read_text())
        self.assertEqual(policy["generation"], 2)
        self.assertEqual(policy["lanes"]["sonnet"]["mode"], "round_robin")
        self.assertEqual(policy["lanes"]["sonnet"]["order"], ["GitHub/GPT-4o-mini", "Cerebras/GPT-OSS-120B"])
        self.assertEqual(before, self.load_mapping())

    def test_model_state_manual_cooldown_uses_lane_policy_duration(self):
        self.capture(self.mod.cmd_model_policy, "sonnet", cooldown="75", order="OR/Qwen-3.6+,Cerebras/GPT-OSS-120B")
        self.capture(self.mod.cmd_model_state, "set", "Cerebras/GPT-OSS-120B", "cooldown")
        state = json.loads(self.mod.MODEL_STATE.read_text())
        info = state["models"]["Cerebras/GPT-OSS-120B"]
        self.assertEqual(info["status"], "cooldown")
        self.assertGreater(info["cooldown_until"], info["updated_at"])

    def test_default_mapping_includes_codex_slots(self):
        for slot in [
            "gpt54",
            "gpt54mini",
            "gpt53codex",
            "gpt52codex",
            "gpt52",
            "gpt51codexmax",
            "gpt51codexmini",
        ]:
            self.assertIn(slot, self.mod.VALID_SLOTS)
            self.assertIn(slot, self.mod.DEFAULT_MAPPING)

    def test_default_mapping_includes_current_claude_slots(self):
        for slot in ["sonnet", "opus", "haiku", "custom", "subagent"]:
            self.assertIn(slot, self.mod.VALID_SLOTS)
            self.assertIn(slot, self.mod.DEFAULT_MAPPING)

    def test_config_writes_claude_runtime_models_as_backend_ids(self):
        self.capture(self.mod.cmd_config)
        exports = self.mod._load_claude_env_exports()
        mapping = self.mod.load()
        self.assertEqual(exports["ANTHROPIC_SMALL_FAST_MODEL"], mapping["haiku"]["model"])
        self.assertEqual(exports["ANTHROPIC_DEFAULT_SONNET_MODEL"], mapping["sonnet"]["model"])
        self.assertEqual(exports["ANTHROPIC_DEFAULT_OPUS_MODEL"], mapping["opus"]["model"])
        self.assertEqual(exports["ANTHROPIC_DEFAULT_HAIKU_MODEL"], mapping["haiku"]["model"])
        self.assertEqual(exports["ANTHROPIC_CUSTOM_MODEL_OPTION"], mapping["custom"]["model"])
        self.assertEqual(exports["ANTHROPIC_CUSTOM_MODEL_OPTION_NAME"], "Custom")
        self.assertEqual(exports["CLAUDE_CODE_SUBAGENT_MODEL"], mapping["subagent"]["model"])

    def test_swap_claude_menu_uses_current_claude_slot_order(self):
        original_input = builtins.input
        answers = iter(["x"])
        try:
            builtins.input = lambda _prompt="": next(answers)
            out = self.capture(self.mod.cmd_swap, "claude")
        finally:
            builtins.input = original_input

        self.assertIn("Default         [runtime]", out)
        self.assertIn("Sonnet (1M)", out)
        self.assertIn("[opus]", out)
        self.assertIn("Custom", out)

    def test_codex_wrapper_uses_custom_provider_responses_path(self):
        broke_sh = (REPO_ROOT / "bin" / "broke").read_text()
        socket_bridge = (REPO_ROOT / "bin" / "_socket_bridge.py").read_text()
        self.assertIn("PROVIDERS=(claude codex gemini)", broke_sh)
        self.assertIn("sanitize_client_env claude", broke_sh)
        self.assertIn("sanitize_client_env codex", broke_sh)
        self.assertIn("sanitize_client_env gemini", broke_sh)
        self.assertNotIn('set -a; source "$DIR/.env"; set +a', broke_sh)
        self.assertIn('python3 "$DIR/bin/_mapping.py" preflight --quiet', broke_sh)
        self.assertIn('env -i "${litellm_env[@]}" litellm', broke_sh)
        self.assertIn('env -i "${proxy_env[@]}" python3 "$DIR/bin/_proxy.py"', broke_sh)
        self.assertIn("unset OPENAI_API_KEY OPENAI_BASE_URL OPENAI_API_BASE", broke_sh)
        self.assertIn("unset CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX", broke_sh)
        self.assertIn("unset GEMINI_API_KEY_AUTH_MECHANISM GOOGLE_GEMINI_BASE_URL", broke_sh)
        self.assertIn('append_env_pair "$1" "BROKE_CLIENT_TOKEN" "$broke_client_token"', broke_sh)
        self.assertIn('append_env_pair "$1" "BROKE_CODEX_API_KEY" "$broke_client_token"', broke_sh)
        self.assertIn('BROKE_HARNESS_MODE', broke_sh)
        self.assertIn('broke harness', broke_sh)
        self.assertIn('broke harness run', broke_sh)
        self.assertIn('Broke ACP front-door is intended for harness mode', broke_sh)
        self.assertIn("or pass --force if you explicitly want unharnessed ACP access", broke_sh)
        self.assertIn('BROKE_HARNESS_RUN_ID', broke_sh)
        self.assertIn('BROKE_HARNESS_WORKER_ROUTE', broke_sh)
        self.assertIn('provider_direct', broke_sh)
        self.assertIn('client_direct', broke_sh)
        self.assertIn('credential_lease.issued', broke_sh)
        self.assertIn('surface_route.changed', broke_sh)
        self.assertIn('launch_named_provider', broke_sh)
        self.assertIn('broke launch <p> [args...]', broke_sh)
        self.assertIn('broke c|x|g [args...]', broke_sh)
        self.assertIn('launch)', broke_sh)
        self.assertIn('  c)', broke_sh)
        self.assertIn('  x)', broke_sh)
        self.assertIn('  g)', broke_sh)
        self.assertIn('claude|codex|gemini)', broke_sh)
        self.assertIn('broke claude [args...]', broke_sh)
        self.assertIn('broke codex [args...]', broke_sh)
        self.assertIn('broke gemini [args...]', broke_sh)
        self.assertIn('authority.expansion_denied', broke_sh)
        self.assertIn('_harness_shim.py', broke_sh)
        self.assertNotIn('sed -i "s|^export ${name}=.*|export ${name}=\\"${value}\\"|" "$env_claude"', broke_sh)
        self.assertIn('model_provider="broke"', broke_sh)
        self.assertIn('base_url=\\"$GATEWAY/v1\\"', broke_sh)
        self.assertIn('wire_api=\\"responses\\"', broke_sh)
        self.assertIn('env_key=\\"BROKE_CODEX_API_KEY\\"', broke_sh)
        self.assertIn('model="$(get_slot_label gpt54)"', broke_sh)
        self.assertIn('append_env_pair "$1" "ANTHROPIC_API_KEY" "$broke_client_token"', broke_sh)
        self.assertIn('GATEWAY="http://localhost:$PORT"', broke_sh)
        self.assertIn('nohup env -i "${litellm_env[@]}" litellm --config "$CONFIG" --host 127.0.0.1 --port "$INTERNAL_PORT"', broke_sh)
        self.assertIn('nohup env -i "${proxy_env[@]}" python3 "$DIR/bin/_proxy.py" "$PORT" "$INTERNAL_PORT"', broke_sh)
        self.assertIn('BROKE_INTERNAL_MASTER_KEY', broke_sh)
        self.assertIn('append_env_pair litellm_env "LITELLM_MASTER_KEY" "$broke_internal_master_key"', broke_sh)
        self.assertIn('bwrap', broke_sh)
        self.assertIn('broke sandbox', broke_sh)
        self.assertIn('BROKE_PROXY_UNIX_SOCKET', broke_sh)
        self.assertIn('LAUNCH_AUDIT_LOG', broke_sh)
        self.assertIn('sandbox_network_policy', broke_sh)
        self.assertIn('local-only', broke_sh)
        self.assertIn('strict mode denies network for $client', broke_sh)
        self.assertIn('shift 3; exec "$@"', broke_sh)
        self.assertNotIn("SSH_AUTH_SOCK", broke_sh)
        self.assertNotIn("DBUS_SESSION_BUS_ADDRESS", broke_sh)
        self.assertNotIn("DISPLAY", broke_sh)
        self.assertNotIn('--bind-try "$HOME/.local" "$HOME/.local"', broke_sh)
        self.assertNotIn('--bind-try "$HOME/.config" "$HOME/.config"', broke_sh)
        self.assertNotIn('--bind-try "$HOME/.cache" "$HOME/.cache"', broke_sh)
        self.assertNotIn('--bind "$DIR" "$DIR"', broke_sh)
        self.assertIn('--ro-bind "$DIR/bin" "$DIR/bin"', broke_sh)
        self.assertIn("validate_harness_shims", broke_sh)
        self.assertIn("os.O_EXCL", broke_sh)
        self.assertIn("refusing unsafe .env.claude path", broke_sh)
        self.assertIn("secret_surface", broke_sh)
        self.assertIn("IDLE_TIMEOUT_SECONDS = 30", socket_bridge)
        self.assertIn("MAX_CONCURRENT_CLIENTS = 8", socket_bridge)
        self.assertIn("BoundedSemaphore", socket_bridge)

    def test_readme_reports_verified_codex_path(self):
        readme = (REPO_ROOT / "README.md").read_text()
        self.assertIn("**Codex CLI** | ✅ Verified", readme)
        self.assertIn("model_provider=\"broke\"", readme)
        self.assertIn("wire_api=\"responses\"", readme)
        self.assertNotIn("not currently supported through BrokeLLM", readme)
        self.assertIn("Local Security", readme)
        self.assertIn("broke model-policy", readme)
        self.assertIn("sanitized client env", readme)
        self.assertIn("Claude, Codex, and Gemini", readme)
        self.assertIn("requirements.lock", readme)
        self.assertIn("vendor/wheels", readme)
        self.assertIn("broke sandbox", readme)
        self.assertIn("broke harness", readme)
        self.assertIn("harness mode", readme)
        self.assertIn("throughput", readme)
        self.assertIn("Launch preflight", readme)
        self.assertIn("local-only", readme)
        self.assertIn(".launch_audit.log", readme)
        self.assertIn("docs/harness/CORE.md", readme)
        self.assertIn("docs/harness/CODE.md", readme)
        self.assertIn("docs/harness/GSD.md", readme)
        self.assertIn("provider_direct", readme)
        self.assertIn("invalid_model", readme)
        self.assertIn("file locking", readme)
        self.assertIn("rate-limits repeated invalid auth attempts", readme)
        self.assertIn("client-specific state directories", readme)
        self.assertIn("## System Structure", readme)
        self.assertIn("governed execution system", readme)
        self.assertIn("Evidence Binding", readme)
        self.assertIn("a simple harness", readme)
        self.assertIn("Codex-style lanes", readme)
        self.assertIn("gpt54", readme)

    def test_harness_spec_docs_exist(self):
        core = (REPO_ROOT / "docs" / "harness" / "CORE.md").read_text()
        code = (REPO_ROOT / "docs" / "harness" / "CODE.md").read_text()
        gsd = (REPO_ROOT / "docs" / "harness" / "GSD.md").read_text()
        pty = (REPO_ROOT / "docs" / "harness" / "PTY-HARDENING.md").read_text()
        index = (REPO_ROOT / "docs" / "harness" / "README.md").read_text()
        self.assertIn("Run Contract", core)
        self.assertIn("Code profile", code)
        self.assertIn("GSD overlay", gsd)
        self.assertIn("PTY supervisor", pty)
        self.assertIn("Signal Semantics", pty)
        self.assertIn("Transport Split", pty)
        self.assertIn("Run channel", pty)
        self.assertIn("Terminal State", pty)
        self.assertIn("stdin detached", pty)
        self.assertIn("Execution control surface", core)
        self.assertIn("Coding Bullshit Taxonomy", code)
        self.assertIn("Upstream Translation", gsd)
        self.assertIn("Dependency direction", index)
        self.assertIn("PTY Supervisor Contract", index)
        self.assertIn("Doctrine Resolution", core)
        self.assertIn("brownfield_audit", code)
        self.assertIn("brownfield_strict", gsd)
        self.assertIn("Selection Model", index)

    def test_socket_bridge_declares_timeout_and_concurrency_limit(self):
        bridge = load_socket_bridge_module()
        self.assertEqual(bridge.IDLE_TIMEOUT_SECONDS, 30)
        self.assertEqual(bridge.MAX_CONCURRENT_CLIENTS, 8)

    def test_validate_reports_expected_sections(self):
        findings = {
            "ok": ["sonnet: all required fields present", "openrouter: provider 'openrouter' recognised", "OPENROUTER_API_KEY — set", "no fallback chains defined (ok)", "sonnet: pinned alias"],
            "warn": [],
            "fail": [],
        }
        with patch.object(self.mod, "_validate_findings", return_value=findings):
            out = self.capture(self.mod.cmd_validate)
        self.assertIn("[slot fields]", out)
        self.assertIn("[api keys]", out)

    def test_team_save_load_and_delete_round_trip(self):
        self.capture(self.mod.cmd_team_save, "demo", "1")
        teams = json.loads(self.mod.TEAMS.read_text())
        self.assertIn("demo", teams)
        out = self.capture(self.mod.cmd_team_load, "demo")
        self.assertIn("Team 'demo' loaded", out)
        self.capture(self.mod.cmd_team_delete, "demo")
        teams = json.loads(self.mod.TEAMS.read_text())
        self.assertNotIn("demo", teams)

    def test_profile_new_load_and_delete_round_trip(self):
        self.capture(self.mod.cmd_team_save, "demo", "1")
        self.capture(self.mod.cmd_profile_new, "app", "demo", description="App profile", allowed_slots=["sonnet"], rpm="5", tpm="10")
        profiles = json.loads(self.mod.PROFILES.read_text())
        self.assertIn("app", profiles)
        out = self.capture(self.mod.cmd_profile_load, "app")
        self.assertIn("Profile 'app' active", out)
        self.capture(self.mod.cmd_profile_delete, "app")
        profiles = json.loads(self.mod.PROFILES.read_text())
        self.assertNotIn("app", profiles)

    def test_client_token_bind_list_and_revoke_round_trip(self):
        self.capture(self.mod.cmd_team_save, "demo", "1")
        self.capture(self.mod.cmd_profile_new, "app", "demo", description="App profile", allowed_slots=["sonnet"], rpm="5", tpm="10")
        bind_out = self.capture(self.mod.cmd_client_token_bind, "app", token="bound-token", name="Spektz")
        binding = json.loads(bind_out.strip())
        self.assertEqual(binding["token"], "bound-token")
        listed = self.capture(self.mod.cmd_client_token_list)
        self.assertIn("Spektz", listed)
        self.capture(self.mod.cmd_client_token_revoke, "bound-token")
        listed_after = self.capture(self.mod.cmd_client_token_list)
        self.assertNotIn("Spektz", listed_after)

    def test_models_and_swap_render_provider_separately_from_model_id(self):
        models_out = self.capture(self.mod.cmd_models)
        self.assertIn("OR", models_out)
        self.assertIn("qwen/qwen3.6-plus:free", models_out)
        self.assertNotIn("openrouter/qwen/qwen3.6-plus:free", models_out)
        self.assertIn("GitHub", models_out)
        self.assertIn("gpt-4o-mini", models_out)

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
        self.mod.CLIENT_BINDINGS.write_text(json.dumps({
            "tokens": {
                "bound-token": {"profile": "app", "name": "Spektz", "created_at": 1},
            }
        }, indent=2))

        export_path = self.mod.DIR / "broke-export.json"
        self.capture(self.mod.cmd_export, export_path)

        self.mod.TEAMS.unlink()
        self.mod.PROFILES.unlink()
        self.mod.CLIENT_BINDINGS.unlink()

        self.capture(self.mod.cmd_import, export_path)

        restored_teams = json.loads(self.mod.TEAMS.read_text())
        restored_profiles = json.loads(self.mod.PROFILES.read_text())
        restored_bindings = json.loads(self.mod.CLIENT_BINDINGS.read_text())
        self.assertEqual(restored_teams, teams)
        self.assertEqual(restored_profiles, profiles)
        self.assertIn("bound-token", restored_bindings["tokens"])

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

    def test_direct_fallback_policy_uses_real_backend_targets(self):
        self.capture(self.mod.cmd_fallback, "opus", "cerebras/gpt-oss-120b", "openrouter/z-ai/glm-4.5-air:free")

        mapping = self.load_mapping()
        self.assertEqual([entry["label"] for entry in mapping["_lane_fallback_targets"]["opus"]], ["Cerebras/GPT-OSS-120B", "OR/GLM-4.5"])
        self.assertNotIn("opus", mapping.get("_fallbacks", {}))

        policy_out = self.capture(self.mod.cmd_fallback_policy)
        self.assertIn("broke fallback policy  [live mapping]", policy_out)
        self.assertIn("opus", policy_out)
        self.assertIn("Cerebras/GPT-OSS-120B → OR/GLM-4.5 [direct]", policy_out)

    def test_interactive_fallback_picker_accepts_backend_numbers(self):
        original_input = builtins.input
        answers = iter(["6", "4", ""])
        try:
            builtins.input = lambda _prompt="": next(answers)
            self.capture(self.mod.cmd_fallback, "sonnet")
        finally:
            builtins.input = original_input

        mapping = self.load_mapping()
        self.assertEqual(
            [entry["label"] for entry in mapping["_lane_fallback_targets"]["sonnet"]],
            ["Cerebras/GPT-OSS-120B", "OR/GLM-4.5"],
        )

    def test_team_fallback_policy_can_show_all_teams_or_one_team(self):
        self.capture(self.mod.cmd_fallback, "sonnet", "cerebras/gpt-oss-120b", "openrouter/z-ai/glm-4.5-air:free")
        self.capture(self.mod.cmd_team_save, "work")
        self.capture(self.mod.cmd_team_save, "prod")

        all_teams_out = self.capture(self.mod.cmd_fallback_policy, show_teams=True)
        self.assertIn("[team: work]", all_teams_out)
        self.assertIn("[team: prod]", all_teams_out)
        self.assertIn("Cerebras/GPT-OSS-120B → OR/GLM-4.5 [direct]", all_teams_out)

        one_team_out = self.capture(self.mod.cmd_fallback_policy, team_name="work", show_teams=True)
        self.assertIn("[team: work]", one_team_out)
        self.assertNotIn("[team: prod]", one_team_out)


if __name__ == "__main__":
    unittest.main()
