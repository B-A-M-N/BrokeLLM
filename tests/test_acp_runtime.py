import importlib.util
import pathlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "bin" / "_acp_runtime.py"


def load_module():
    spec = importlib.util.spec_from_file_location("broke_acp_runtime_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ACPRuntimeTestCase(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_runtime_registry_resolves_real_classes(self):
        registry = self.mod.RuntimeRegistry(sessions_root=self.tmpdir.name)
        self.assertEqual(registry.for_provider("claude").runtime_name, "ClaudeAgentAcpShimRuntime")
        self.assertEqual(registry.for_provider("codex").runtime_name, "CodexAcpShimRuntime")
        self.assertEqual(registry.for_provider("openrouter").runtime_name, "OpenRouterHeadlessRuntime")

    def test_external_shim_delta_emits_turn_delta_event(self):
        runtime = self.mod.CodexAcpShimRuntime(self.tmpdir.name)
        state = runtime._new_session_record()
        seen = []
        state.update({"remote_session_id": "remote-1", "requests": {}, "next_request_id": 1, "active_turn": None, "lock": self.mod.threading.RLock()})
        runtime._sessions[state["session_id"]] = state
        turn = {
            "turn_id": "turn-1",
            "done": self.mod.threading.Event(),
            "text_parts": [],
            "final_text": "",
            "error": "",
            "event_cb": lambda event, payload: seen.append((event, payload)),
        }
        state["active_turn"] = turn
        runtime._handle_stdout_line(state, '{"method":"turn.delta","params":{"sessionId":"remote-1","delta":"OK"}}')
        self.assertEqual(seen[0][0], "turn.delta")
        self.assertEqual(seen[0][1]["delta"], "OK")

    def test_external_shim_new_session_tracks_remote_session_id(self):
        runtime = self.mod.ClaudeAgentAcpShimRuntime(self.tmpdir.name)
        runtime._ensure_process = lambda session: session.update({"initialized": True, "status": "running"})
        runtime._request_with_aliases = lambda session, methods, params, timeout=30: {"sessionId": "remote-42", "mode": "default"}
        state = runtime.new_session(cwd="/tmp")
        self.assertEqual(state["remote_session_id"], "remote-42")
        self.assertEqual(state["metadata"]["remote_session_id"], "remote-42")
        self.assertEqual(state["status"], "ready")
        self.assertEqual(state["capabilities"]["startup_canary"], "pending")
        self.assertTrue(state["capabilities"]["supports_transport_cancel"])
        self.assertTrue(state["capabilities"]["supports_native_session_resume"])
        self.assertTrue(state["capabilities"]["supports_tool_roundtrip"])

    def test_external_shim_late_completion_is_quarantined(self):
        runtime = self.mod.CodexAcpShimRuntime(self.tmpdir.name)
        state = runtime._new_session_record()
        state.update({"remote_session_id": "remote-1", "requests": {}, "next_request_id": 1, "active_turn": None, "lock": self.mod.threading.RLock()})
        runtime._sessions[state["session_id"]] = state
        runtime._handle_stdout_line(state, '{"method":"turn.completed","params":{"sessionId":"remote-1","turnId":"r1","result":{"summary":"late"}}}')
        self.assertEqual(state["quarantine_count"], 1)
        self.assertEqual(state["quarantined_results"][0]["reason"], "late_result_without_active_turn")

    def test_external_shim_duplicate_completion_is_quarantined(self):
        runtime = self.mod.CodexAcpShimRuntime(self.tmpdir.name)
        state = runtime._new_session_record()
        state.update({"remote_session_id": "remote-1", "requests": {}, "next_request_id": 1, "active_turn": None, "lock": self.mod.threading.RLock(), "completed_turn_ids": ["r1"]})
        turn = {
            "turn_id": "turn-1",
            "generation": 1,
            "done": self.mod.threading.Event(),
            "text_parts": [],
            "final_text": "",
            "error": "",
            "remote_turn_id": "r1",
            "event_cb": None,
        }
        state["active_turn"] = turn
        runtime._sessions[state["session_id"]] = state
        runtime._handle_stdout_line(state, '{"method":"turn.completed","params":{"sessionId":"remote-1","turnId":"r1","result":{"summary":"dup"}}}')
        self.assertEqual(state["quarantine_count"], 1)
        self.assertEqual(state["quarantined_results"][0]["reason"], "duplicate_completed_turn")

    def test_claude_stdout_parser_finalizes_result(self):
        runtime = self.mod.ClaudeCliAdapterRuntime(self.tmpdir.name)
        state = runtime.new_session()
        session = runtime._sessions[state["session_id"]]
        done = self.mod.threading.Event()
        session["active_turn"] = {
            "turn_id": "turn-1",
            "done": done,
            "assistant_messages": [],
            "text_parts": [],
            "result_payload": None,
            "final_text": "",
            "error": "",
        }
        runtime._handle_stdout_line(session, '{"type":"assistant","message":{"content":[{"type":"text","text":"hello"}]}}')
        runtime._handle_stdout_line(session, '{"type":"result","result":"hello","is_error":false}')
        self.assertTrue(done.is_set())
        self.assertEqual(session["active_turn"]["final_text"], "hello")

    def test_codex_notification_parser_collects_delta_and_completion(self):
        runtime = self.mod.CodexCliAdapterRuntime(self.tmpdir.name)
        state = runtime._new_session_record()
        state.update({"thread_id": "thread-1", "requests": {}, "next_request_id": 1, "active_turn": None, "lock": self.mod.threading.RLock()})
        runtime._sessions[state["session_id"]] = state
        turn = {
            "turn_id": "turn-1",
            "done": self.mod.threading.Event(),
            "text_parts": [],
            "completed_messages": [],
            "final_text": "",
            "error": "",
            "status": "inProgress",
        }
        state["active_turn"] = turn
        runtime._handle_stdout_line(state, '{"method":"item/agentMessage/delta","params":{"threadId":"thread-1","turnId":"turn-1","itemId":"msg-1","delta":"OK"}}')
        runtime._handle_stdout_line(state, '{"method":"turn/completed","params":{"threadId":"thread-1","turn":{"id":"turn-1","status":"completed","error":null}}}')
        self.assertTrue(turn["done"].is_set())
        self.assertEqual(turn["final_text"], "OK")

    def test_codex_delta_emits_turn_delta_event(self):
        runtime = self.mod.CodexCliAdapterRuntime(self.tmpdir.name)
        state = runtime._new_session_record()
        seen = []
        state.update({"thread_id": "thread-1", "requests": {}, "next_request_id": 1, "active_turn": None, "lock": self.mod.threading.RLock()})
        runtime._sessions[state["session_id"]] = state
        turn = {
            "turn_id": "turn-1",
            "done": self.mod.threading.Event(),
            "text_parts": [],
            "completed_messages": [],
            "final_text": "",
            "error": "",
            "status": "inProgress",
            "event_cb": lambda event, payload: seen.append((event, payload)),
        }
        state["active_turn"] = turn
        runtime._handle_stdout_line(state, '{"method":"item/agentMessage/delta","params":{"threadId":"thread-1","turnId":"turn-1","itemId":"msg-1","delta":"OK"}}')
        self.assertEqual(seen[0][0], "turn.delta")
        self.assertEqual(seen[0][1]["delta"], "OK")

    def test_headless_runtime_persists_history_and_normalizes_lane_result(self):
        runtime = self.mod.OpenRouterHeadlessRuntime(self.tmpdir.name)
        runtime._request_completion = lambda session, prompt, active=None: {
            "choices": [{"message": {"content": '{"summary":"done","recommended_verdict":"ACCEPT","confidence":0.8}'}}]
        }
        state = runtime.new_session()
        self.assertEqual(state["capabilities"]["startup_canary"], "passed")
        self.assertEqual(state["capabilities"]["session_persistence"], "logical_lane")
        self.assertEqual(state["capabilities"]["cancel_kind"], "logical")
        self.assertFalse(state["capabilities"]["supports_transport_cancel"])
        self.assertFalse(state["capabilities"]["supports_live_interrupt"])
        self.assertTrue(state["capabilities"]["supports_native_session_resume"])
        self.assertEqual(state["capabilities"]["late_result_policy"], "quarantine")
        result = runtime.prompt(state["session_id"], "check this")
        self.assertEqual(result["laneResult"]["summary"], "done")
        self.assertEqual(result["laneResult"]["recommended_verdict"], "ACCEPT")
        persisted = runtime.get_session_state(state["session_id"])
        self.assertEqual(len(persisted["history"]), 2)
        self.assertEqual(persisted["history"][0]["role"], "user")
        self.assertEqual(persisted["transport_health"]["watchdog_state"], "healthy")

    def test_headless_stream_emits_turn_delta(self):
        runtime = self.mod.OpenRouterHeadlessRuntime(self.tmpdir.name)
        seen = []

        def fake_request(session, prompt, active=None):
            if active and active.get("event_cb"):
                runtime._emit(active["event_cb"], "turn.delta", session, {"turnId": active["turn_id"], "delta": "O"})
                runtime._emit(active["event_cb"], "turn.delta", session, {"turnId": active["turn_id"], "delta": "K"})
            return {"choices": [{"message": {"content": "OK"}}]}

        runtime._request_completion = fake_request
        state = runtime.new_session()
        runtime.prompt(state["session_id"], "stream", event_cb=lambda event, payload: seen.append((event, payload)))
        deltas = [payload["delta"] for event, payload in seen if event == "turn.delta"]
        self.assertEqual(deltas, ["O", "K"])

    def test_headless_runtime_cancel_marks_active_turn_cancelled(self):
        runtime = self.mod.GroqHeadlessRuntime(self.tmpdir.name)

        def slow_response(session, prompt, active=None):
            self.mod.time.sleep(0.3)
            return {"choices": [{"message": {"content": "later"}}]}

        runtime._request_completion = slow_response
        state = runtime.new_session()
        holder = {}

        def run_prompt():
            holder["result"] = runtime.prompt(state["session_id"], "long", timeout=2)

        thread = self.mod.threading.Thread(target=run_prompt)
        thread.start()
        self.mod.time.sleep(0.05)
        runtime.cancel(state["session_id"])
        thread.join()
        self.assertEqual(holder["result"]["laneResult"]["status"], "cancelled")
        self.mod.time.sleep(0.35)
        persisted = runtime.get_session_state(state["session_id"])
        self.assertEqual(persisted["quarantine_count"], 1)
        self.assertEqual(persisted["quarantined_results"][0]["reason"], "late_result_after_cancel_or_turn_replacement")
        self.assertEqual(persisted["history"], [])

    def test_watchdog_marks_session_stale_after_timeout(self):
        runtime = self.mod.OpenRouterHeadlessRuntime(self.tmpdir.name)
        state = runtime.new_session()
        session = runtime._sessions[state["session_id"]]
        session["transport_health"]["heartbeat_timeout_sec"] = 1
        session["transport_health"]["last_event_at"] = (
            datetime.now(timezone.utc) - timedelta(seconds=5)
        ).isoformat()
        stale = runtime.get_session_state(state["session_id"])
        self.assertEqual(stale["transport_health"]["watchdog_state"], "stale")

    def test_cancel_returns_backend_cancel_kind(self):
        runtime = self.mod.GroqHeadlessRuntime(self.tmpdir.name)
        state = runtime.new_session()
        result = runtime.cancel(state["session_id"])
        self.assertEqual(result["cancel_kind"], "logical")


if __name__ == "__main__":
    unittest.main()
