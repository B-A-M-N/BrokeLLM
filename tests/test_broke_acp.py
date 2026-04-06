import importlib.util
import io
import pathlib
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "bin" / "_broke_acp.py"


def load_module():
    spec = importlib.util.spec_from_file_location("broke_acp_gateway_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeRuntime:
    provider = "fake"

    def __init__(self, sessions_root=None):
        self.sessions = {}

    def new_session(self, cwd=None, model=None, mode=None, metadata=None):
        session = {
            "session_id": "fake-session",
            "provider": "fake",
            "runtime_binding": "cli_adapter",
            "runtime_name": "FakeRuntime",
            "cwd": cwd,
            "model": model,
            "mode": mode,
            "status": "ready",
            "updated_at": "now",
            "capabilities": {
                "runtime_name": "FakeRuntime",
                "runtime_binding": "cli_adapter",
                "supports_streaming": True,
                "supports_cancel": True,
                "cancel_kind": "signal",
                "session_persistence": "live_runtime",
                "startup_canary": "passed",
                "startup_checked_at": "now",
                "runtime_version": "test",
            },
            "transport_health": {
                "last_event_at": "now",
                "heartbeat_timeout_sec": 45,
                "watchdog_state": "healthy",
            },
        }
        self.sessions["fake-session"] = session
        return dict(session)

    def load_session(self, session_record):
        self.sessions[session_record["session_id"]] = dict(session_record)
        return dict(session_record)

    def get_session_state(self, session_id):
        return dict(self.sessions[session_id])

    def prompt(self, session_id, prompt, event_cb=None, timeout=180.0):
        if event_cb:
            event_cb("turn.started", {"turnId": "turn-1"})
            event_cb("turn.completed", {"turnId": "turn-1", "result": {"summary": "done"}})
        session = dict(self.sessions[session_id])
        session["last_prompt"] = prompt
        self.sessions[session_id] = session
        return {
            "session": session,
            "turnId": "turn-1",
            "outputText": "done",
            "laneResult": {
                "lane_role": "worker",
                "status": "completed",
                "summary": "done",
                "findings": [],
                "objections": [],
                "recommended_verdict": None,
                "confidence": None,
                "evidence_refs": [],
                "provider_metadata": {"provider": "fake", "runtime_binding": "cli_adapter"},
                "degraded": False,
                "degraded_reason": "",
            },
        }

    def cancel(self, session_id):
        return {"session_id": session_id, "cancelled": True, "cancel_kind": "signal"}

    def close(self, session_id):
        return {"session_id": session_id, "closed": True}


class BrokeACPGatewayTestCase(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.old_map = dict(self.mod.RuntimeRegistry.__dict__.get("__test_runtime_map__", {}))
        self.mod.RuntimeRegistry.for_provider = self.fake_for_provider
        self.runtime = FakeRuntime()

    def tearDown(self):
        self.tmpdir.cleanup()

    def fake_for_provider(self, provider):
        if provider != "fake":
            raise self.mod.ACPRuntimeError(f"unknown provider runtime: {provider}")
        return self.runtime

    def test_gateway_new_session_and_prompt_round_trip(self):
        gateway = self.mod.ACPGateway(sessions_root=self.tmpdir.name, registry_config={"fake": {"runtime_class": "FakeRuntime"}})
        out = io.StringIO()
        new_session = gateway._dispatch("newSession", {"provider": "fake", "cwd": "/tmp"}, outstream=out)
        self.assertEqual(new_session["session_id"], "fake-session")
        prompt = gateway._dispatch("prompt", {"sessionId": "fake-session", "prompt": "hi", "laneRole": "verifier"}, outstream=out)
        self.assertEqual(prompt["turnId"], "turn-1")
        self.assertEqual(prompt["outputText"], "done")
        self.assertEqual(prompt["laneResult"]["lane_role"], "verifier")
        emitted = out.getvalue()
        self.assertIn('"method": "session.started"', emitted)
        self.assertIn('"method": "turn.started"', emitted)
        self.assertIn('"method": "turn.completed"', emitted)

    def test_initialize_and_session_heartbeat_surface_hardening_state(self):
        gateway = self.mod.ACPGateway(sessions_root=self.tmpdir.name, registry_config={"fake": {"runtime_class": "FakeRuntime"}})
        init = gateway._dispatch("initialize", {}, outstream=io.StringIO())
        self.assertTrue(init["hardening"]["startup_canary_required"])
        self.assertTrue(init["hardening"]["watchdog_enabled"])
        gateway._dispatch("newSession", {"provider": "fake", "cwd": "/tmp"}, outstream=io.StringIO())
        heartbeat = gateway._dispatch("heartbeat", {"sessionId": "fake-session"}, outstream=io.StringIO())
        self.assertEqual(heartbeat["watchdog"]["watchdog_state"], "healthy")
        self.assertEqual(heartbeat["capabilities"]["startup_canary"], "passed")


if __name__ == "__main__":
    unittest.main()
