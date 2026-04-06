import importlib.util
import io
import json
import os
import pathlib
import shutil
import tempfile
import unittest
from unittest.mock import patch


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "bin" / "_gemini_acp.py"


def load_module():
    spec = importlib.util.spec_from_file_location("broke_gemini_acp_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeStdout:
    def __init__(self, lines):
        self._lines = list(lines)

    def __iter__(self):
        return iter(self._lines)


class FakeStderr(FakeStdout):
    pass


class FakeStdin:
    def __init__(self):
        self.writes = []

    def write(self, raw):
        self.writes.append(raw)

    def flush(self):
        return None


class FakeProc:
    def __init__(self, stdout_lines=None, stderr_lines=None):
        self.stdin = FakeStdin()
        self.stdout = FakeStdout(stdout_lines or [])
        self.stderr = FakeStderr(stderr_lines or [])
        self.pid = 4321
        self.returncode = 0
        self._polled = None

    def poll(self):
        return self._polled

    def terminate(self):
        self._polled = 0
        self.returncode = 0

    def wait(self, timeout=None):
        self._polled = 0
        self.returncode = 0
        return 0

    def kill(self):
        self._polled = -9
        self.returncode = -9


class GeminiACPTestCase(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tempdir.name)
        self._env_backup = {
            key: os.environ.get(key)
            for key in (
                "BROKE_HARNESS_SESSION_FILE",
                "BROKE_HARNESS_CONTROL_FILE",
                "BROKE_HARNESS_RUNS_FILE",
                "BROKE_HARNESS_RUN_ID",
            )
        }

    def tearDown(self):
        for key, value in self._env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tempdir.cleanup()

    def test_adapter_detects_stdout_corruption(self):
        proc = FakeProc(stdout_lines=["plain text contamination\n"])
        os.environ["BROKE_HARNESS_SESSION_FILE"] = str(self.root / "session.json")
        adapter = self.mod.GeminiACPAdapter(state_file=self.root / "state.json")
        adapter.proc = proc
        adapter._reader_loop()
        state = json.loads((self.root / "state.json").read_text())
        session = json.loads((self.root / "session.json").read_text())
        self.assertTrue(state["stream_corruption"])
        self.assertEqual(state["status"], "degraded")
        self.assertEqual(session["transport"], "acp")
        self.assertTrue(session["stream_corruption"])

    def test_adapter_request_writes_ndjson_and_returns_result(self):
        response = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": 1}}) + "\n"
        proc = FakeProc(stdout_lines=[response])
        adapter = self.mod.GeminiACPAdapter(state_file=self.root / "state.json")
        with patch.object(self.mod.subprocess, "Popen", return_value=proc), \
             patch.object(self.mod.threading.Thread, "start", lambda self: None):
            adapter.start()
            adapter._responses[1] = {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": 1}}
            result = adapter.request("initialize", {"protocolVersion": 1}, timeout=0.1)
        self.assertEqual(result["protocolVersion"], 1)
        self.assertIn('"method":"initialize"', proc.stdin.writes[0])

    def test_main_prompt_creates_session_and_prints_json(self):
        adapter = self.mod.GeminiACPAdapter(state_file=self.root / "state.json")
        with patch.object(self.mod, "GeminiACPAdapter", return_value=adapter):
            adapter.initialize = lambda: {"protocolVersion": 1}
            adapter.new_session = lambda: {"sessionId": "sess-1"}
            adapter.prompt = lambda session_id, text, message_id=None: {"sessionId": session_id, "text": text}
            adapter.close = lambda: None
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                rc = self.mod.main(["--json", "prompt", "--text", "hello"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["session"]["sessionId"], "sess-1")

    def test_main_prompt_loads_persisted_session_when_requested(self):
        state_file = self.root / "state.json"
        state_file.write_text(json.dumps({"session_id": "sess-persisted"}))
        adapter = self.mod.GeminiACPAdapter(state_file=state_file)
        with patch.object(self.mod, "GeminiACPAdapter", return_value=adapter):
            adapter.initialize = lambda: {"protocolVersion": 1}
            adapter.load_session = lambda session_id: {"sessionId": session_id, "loaded": True}
            adapter.prompt = lambda session_id, text, message_id=None: {"sessionId": session_id, "text": text}
            adapter.close = lambda: None
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                rc = self.mod.main(["--json", "--state-file", str(state_file), "prompt", "--load-session", "--text", "hello"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["session"]["sessionId"], "sess-persisted")

    def test_adapter_marks_rate_limit_stderr_as_degraded(self):
        proc = FakeProc(stderr_lines=["429 Too Many Requests\n"])
        os.environ["BROKE_HARNESS_SESSION_FILE"] = str(self.root / "session.json")
        adapter = self.mod.GeminiACPAdapter(state_file=self.root / "state.json")
        adapter.proc = proc
        adapter._stderr_loop()
        state = json.loads((self.root / "state.json").read_text())
        self.assertEqual(state["status"], "degraded")
        self.assertEqual(state["degraded_reason"], "upstream_rate_limited")

    def test_adapter_marks_auth_prompt_as_degraded(self):
        proc = FakeProc(stderr_lines=["Please login with your Google account in a browser\n"])
        os.environ["BROKE_HARNESS_SESSION_FILE"] = str(self.root / "session.json")
        adapter = self.mod.GeminiACPAdapter(state_file=self.root / "state.json")
        adapter.proc = proc
        adapter._stderr_loop()
        state = json.loads((self.root / "state.json").read_text())
        self.assertEqual(state["status"], "degraded")
        self.assertEqual(state["degraded_reason"], "auth_required")
        self.assertTrue(state["auth_required"])

    def test_adapter_repeated_request_failures_degrade_run(self):
        adapter = self.mod.GeminiACPAdapter(state_file=self.root / "state.json")
        adapter._record_failure("first_failure")
        self.assertEqual(adapter._state["failure_count"], 1)
        self.assertNotEqual(adapter._state["status"], "degraded")
        adapter._record_failure("second_failure")
        self.assertEqual(adapter._state["failure_count"], 2)
        self.assertEqual(adapter._state["status"], "degraded")
        self.assertEqual(adapter._state["degraded_reason"], "repeated_acp_failures:second_failure")

    def test_initialize_retries_then_succeeds(self):
        adapter = self.mod.GeminiACPAdapter(state_file=self.root / "state.json")
        attempts = {"count": 0}
        restarts = []

        def fake_request(method, params=None, timeout=None):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise self.mod.ACPError("ACP request timed out: initialize")
            return {"protocolVersion": 1, "agentCapabilities": {}}

        adapter.request = fake_request
        adapter.restart = lambda reason="restart": restarts.append(reason)
        result = adapter.initialize()
        self.assertEqual(result["protocolVersion"], 1)
        self.assertEqual(attempts["count"], 3)
        self.assertEqual(len(restarts), 2)
        self.assertFalse(adapter._state["quarantined"])
        self.assertEqual(adapter._state["initialize_failures"], 0)

    def test_initialize_quarantines_after_repeated_failure(self):
        adapter = self.mod.GeminiACPAdapter(state_file=self.root / "state.json")
        adapter.request = lambda method, params=None, timeout=None: (_ for _ in ()).throw(self.mod.ACPError("ACP request timed out: initialize"))
        adapter.restart = lambda reason="restart": None
        with self.assertRaises(self.mod.ACPError):
            adapter.initialize()
        self.assertTrue(adapter._state["quarantined"])
        self.assertIn("timed out", adapter._state["quarantine_reason"])

    def test_initialize_refuses_when_quarantined(self):
        adapter = self.mod.GeminiACPAdapter(state_file=self.root / "state.json")
        adapter._state["quarantined"] = True
        adapter._state["quarantine_reason"] = "previous_timeout"
        with self.assertRaises(self.mod.ACPError) as ctx:
            adapter.initialize()
        self.assertIn("quarantined", str(ctx.exception))

    def test_adapter_persists_acp_identity_into_harness_ledger(self):
        runs_file = self.root / ".harness_runs.json"
        runs_file.write_text(json.dumps({"runs": {"run_acp": {"run_id": "run_acp", "provider": "gemini", "status": "running"}}}))
        os.environ["BROKE_HARNESS_RUN_ID"] = "run_acp"
        os.environ["BROKE_HARNESS_RUNS_FILE"] = str(runs_file)
        os.environ["BROKE_HARNESS_SESSION_FILE"] = str(self.root / "session.json")
        adapter = self.mod.GeminiACPAdapter(state_file=self.root / "state.json")
        adapter._state["pid"] = 4321
        adapter._state["session_id"] = "sess-42"
        adapter._state["initialized"] = True
        adapter._state["status"] = "running"
        adapter._persist_state()
        runs = json.loads(runs_file.read_text())
        record = runs["runs"]["run_acp"]
        self.assertEqual(record["transport"], "acp")
        self.assertEqual(record["acp_session_id"], "sess-42")
        self.assertEqual(record["acp_pid"], 4321)
        self.assertTrue(record["acp_initialized"])

    def test_adapter_control_cancel_marks_prompt_canceled(self):
        adapter = self.mod.GeminiACPAdapter(state_file=self.root / "state.json")
        adapter.proc = FakeProc()
        adapter._state["session_id"] = "sess-1"
        os.environ["BROKE_HARNESS_CONTROL_FILE"] = str(self.root / "control.json")
        adapter.control_file = self.root / "control.json"
        sent = []

        def fake_send(payload):
            sent.append(payload)
            if payload["method"] == "session/cancel":
                adapter._responses[payload["id"]] = {"jsonrpc": "2.0", "id": payload["id"], "result": {"canceled": True}}
                adapter._responses[1] = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {"message": "Prompt canceled by operator"},
                }

        control_path = pathlib.Path(os.environ["BROKE_HARNESS_CONTROL_FILE"])
        adapter._send = fake_send
        original_sleep = self.mod.time.sleep

        def fake_sleep(_seconds):
            if not control_path.exists():
                control_path.write_text(json.dumps({"command_id": "op1", "action": "cancel_prompt"}))
            original_sleep(0)

        with patch.object(self.mod.time, "sleep", side_effect=fake_sleep):
            result = adapter.prompt("sess-1", "hello")
        self.assertTrue(result["canceled"])
        self.assertEqual(sent[1]["method"], "session/cancel")

    @unittest.skipUnless(shutil.which("gemini"), "Gemini CLI not available")
    def test_real_gemini_acp_initialize_smoke(self):
        adapter = self.mod.GeminiACPAdapter(state_file=self.root / "real-state.json", timeout=20.0)
        try:
            result = adapter.initialize()
            self.assertEqual(result["protocolVersion"], 1)
            self.assertIn("agentCapabilities", result)
        finally:
            adapter.close()

    @unittest.skipUnless(shutil.which("gemini"), "Gemini CLI not available")
    def test_real_gemini_acp_multi_turn_and_load_session_continuity(self):
        first_state = self.root / "real-state-1.json"
        second_state = self.root / "real-state-2.json"
        first = self.mod.GeminiACPAdapter(state_file=first_state, timeout=30.0)
        second = None
        try:
            first.initialize()
            session = first.new_session()
            session_id = session["sessionId"]
            first_turn = first.prompt(session_id, "Reply with the single token ONE.")
            self.assertIsInstance(first_turn, dict)
            last_error = None
            for attempt in range(2):
                second = self.mod.GeminiACPAdapter(state_file=second_state, timeout=45.0)
                try:
                    second.initialize()
                    loaded = second.load_session(session_id)
                    self.assertEqual(session_id, loaded.get("sessionId", session_id))
                    second_turn = second.prompt(session_id, "Reply with the single token TWO.")
                    self.assertIsInstance(second_turn, dict)
                    last_error = None
                    break
                except self.mod.ACPError as exc:
                    last_error = exc
                    second.close()
                    second = None
                    if "timed out" not in str(exc).lower() or attempt == 1:
                        raise
            if last_error is not None:
                raise last_error
        finally:
            first.close()
            if second is not None:
                second.close()
