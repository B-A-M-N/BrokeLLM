import builtins
import importlib.util
import io
import json
import os
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
        self.mod.SNAPSHOTS = root / ".snapshots"
        self.mod.FREEZE = root / ".freeze"
        self.mod.ROTATION_POLICY = root / ".rotation.json"
        self.mod.KEY_STATE = root / ".key_state.json"
        self.mod.ROTATION_LOG = root / ".rotation.log"
        self.mod.MODEL_POLICY = root / ".model_policy.json"
        self.mod.MODEL_STATE = root / ".model_state.json"
        self.mod.HARNESS_CONFIG = root / ".harness.json"
        self.mod.HARNESS_STATE = root / ".harness_state.json"
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

    def test_harness_shim_denies_cwd_outside_allowed_paths(self):
        shim = load_harness_shim_module()
        self.assertTrue(shim.cwd_allowed("/tmp/work", ["/tmp"]))
        self.assertFalse(shim.cwd_allowed("/etc", ["/tmp"]))

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

    def test_install_uses_python_module_pip(self):
        install_sh = (REPO_ROOT / "install.sh").read_text()
        requirements_lock = (REPO_ROOT / "requirements.lock").read_text()
        requirements_txt = (REPO_ROOT / "requirements.txt").read_text()
        self.assertIn('pip_args=(-m pip install --require-hashes -r "$LOCKFILE" --quiet)', install_sh)
        self.assertIn('"$PY" -m pip download --require-hashes -r "$LOCKFILE" -d "$WHEEL_DIR" --quiet', install_sh)
        self.assertIn("litellm[proxy]==1.83.0", requirements_txt)
        self.assertIn("litellm==1.83.0", requirements_lock)
        self.assertIn('chmod 600 "$DIR/.env"', install_sh)

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

    def test_gemini_env_name_is_consistent(self):
        broke_sh = (REPO_ROOT / "bin" / "broke").read_text()
        env_template = (REPO_ROOT / ".env.template").read_text()
        self.assertIn("GEMINI_API_KEY", broke_sh)
        self.assertIn("GEMINI_API_KEY", env_template)
        self.assertNotIn("GOOGLE_AI_STUDIO_API_KEY", broke_sh)

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
        self.assertIn('BROKE_HARNESS_RUN_ID', broke_sh)
        self.assertIn('BROKE_HARNESS_WORKER_ROUTE', broke_sh)
        self.assertIn('provider_direct', broke_sh)
        self.assertIn('credential_lease.issued', broke_sh)
        self.assertIn('authority.expansion_denied', broke_sh)
        self.assertIn('_harness_shim.py', broke_sh)
        self.assertNotIn('sed -i "s|^export ${name}=.*|export ${name}=\\"${value}\\"|" "$env_claude"', broke_sh)
        self.assertIn('model_provider="broke"', broke_sh)
        self.assertIn('base_url=\\"$GATEWAY/v1\\"', broke_sh)
        self.assertIn('wire_api=\\"responses\\"', broke_sh)
        self.assertIn('env_key=\\"BROKE_CODEX_API_KEY\\"', broke_sh)
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

    def test_harness_spec_docs_exist(self):
        core = (REPO_ROOT / "docs" / "harness" / "CORE.md").read_text()
        code = (REPO_ROOT / "docs" / "harness" / "CODE.md").read_text()
        gsd = (REPO_ROOT / "docs" / "harness" / "GSD.md").read_text()
        index = (REPO_ROOT / "docs" / "harness" / "README.md").read_text()
        self.assertIn("Run Contract", core)
        self.assertIn("Code profile", code)
        self.assertIn("GSD overlay", gsd)
        self.assertIn("Execution control surface", core)
        self.assertIn("Coding Bullshit Taxonomy", code)
        self.assertIn("Upstream Translation", gsd)
        self.assertIn("Dependency direction", index)
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
