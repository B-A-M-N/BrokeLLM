import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_dashboard_module():
    dashboard_path = REPO_ROOT / "bin" / "_dashboard.py"
    spec = importlib.util.spec_from_file_location("broke_dashboard_test_split", dashboard_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DashboardTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tempdir.name)
        self.dashboard = load_dashboard_module()
        self.dashboard.HARNESS_RUNS = self.root / ".harness_runs.json"
        self.dashboard.HARNESS_ACTIVE_RUN = self.root / ".harness_active_run.json"
        self.dashboard.HARNESS_RUN_ROOT = self.root / ".runtime" / "harness"
        self.dashboard.HARNESS_STATE = self.root / ".harness_state.json"
        self.dashboard.PROFILES = self.root / ".profiles.json"
        self.dashboard.CLIENT_BINDINGS = self.root / ".client_bindings.json"

    def tearDown(self):
        self.tempdir.cleanup()

    def test_dashboard_collect_snapshot_includes_runs_and_counts(self):
        run_id = "run_demo"
        (self.dashboard.HARNESS_RUN_ROOT / run_id / "state").mkdir(parents=True)
        (self.dashboard.HARNESS_RUN_ROOT / run_id / "events.jsonl").write_text(
            json.dumps({"event_seq": 1, "timestamp": "2026-04-05T00:00:00+00:00", "event_type": "run.registered"}) + "\n"
        )
        (self.dashboard.HARNESS_RUN_ROOT / run_id / "state" / "governor.json").write_text(
            json.dumps({"verification_only_mode": True, "writes_since_verification": 2})
        )
        (self.dashboard.HARNESS_RUN_ROOT / run_id / "state" / "intervention.json").write_text(
            json.dumps({"status": "active", "notice": "Run tests", "next_action": "pytest -q"})
        )
        (self.dashboard.HARNESS_RUN_ROOT / run_id / "state" / "session.json").write_text(
            json.dumps({"status": "running", "child_pid": 12345})
        )
        (self.dashboard.HARNESS_RUN_ROOT / run_id / "artifacts").mkdir(parents=True)
        (self.dashboard.HARNESS_RUN_ROOT / run_id / "artifacts" / "pty-output.log").write_text("agent output\n")
        self.dashboard.HARNESS_RUNS.write_text(json.dumps({"runs": {run_id: {"run_id": run_id, "provider": "claude", "policy_profile": "balanced", "status": "running", "created_at": "2026-04-05T00:00:00+00:00"}}}))
        self.dashboard.HARNESS_ACTIVE_RUN.write_text(json.dumps({"run_id": run_id}))
        self.dashboard.PROFILES.write_text(json.dumps({"app": {"team": "demo"}}))
        self.dashboard.CLIENT_BINDINGS.write_text(json.dumps({"tokens": {"tok": {"profile": "app"}}}))
        with patch.object(self.dashboard, "gateway_status", return_value={"live": True, "ready": True, "health_models": 3, "port": 4000, "error": ""}), \
             patch.object(self.dashboard, "session_is_live", return_value=True):
            snapshot = self.dashboard.collect_snapshot()
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

    def test_dashboard_collect_snapshot_surfaces_control_facts(self):
        run_id = "run_control"
        (self.dashboard.HARNESS_RUN_ROOT / run_id / "state").mkdir(parents=True)
        (self.dashboard.HARNESS_RUN_ROOT / run_id / "events.jsonl").write_text(
            json.dumps({"event_seq": 1, "timestamp": "2026-04-05T00:00:00+00:00", "event_type": "run.registered", "payload": {}, "artifact_refs": []}) + "\n"
        )
        (self.dashboard.HARNESS_RUN_ROOT / run_id / "channel.jsonl").write_text(
            json.dumps({"run_id": run_id, "channel": "control", "msg_seq": 2, "timestamp": "2026-04-05T00:00:01+00:00", "kind": "session.operator_interrupt", "payload": {"command_id": "op1", "target": "process_group", "supervisor_pid": 11, "child_pid": 22, "child_pgid": 33}, "integrity": {"prev_hash": None, "hash": "abc"}}) + "\n"
        )
        (self.dashboard.HARNESS_RUN_ROOT / run_id / "state" / "session.json").write_text(
            json.dumps({"status": "running", "child_pid": 22, "child_pgid": 33, "supervisor_pid": 11})
        )
        self.dashboard.HARNESS_RUNS.write_text(json.dumps({"runs": {run_id: {"run_id": run_id, "provider": "claude", "policy_profile": "balanced", "status": "running", "created_at": "2026-04-05T00:00:00+00:00"}}}))
        self.dashboard.HARNESS_ACTIVE_RUN.write_text(json.dumps({"run_id": run_id}))
        self.dashboard.PROFILES.write_text(json.dumps({}))
        self.dashboard.CLIENT_BINDINGS.write_text(json.dumps({"tokens": {}}))
        with patch.object(self.dashboard, "gateway_status", return_value={"live": True, "ready": True, "health_models": 1, "port": 4000, "error": ""}), \
             patch.object(self.dashboard, "session_is_live", return_value=True):
            snapshot = self.dashboard.collect_snapshot()
        fact = snapshot["harness"]["runs"][0]["control_facts"][0]
        self.assertEqual(fact["msg_seq"], 2)
        self.assertEqual(fact["target"], "process_group")
        self.assertEqual(fact["child_pgid"], 33)
        self.assertEqual(fact["source"], "channel")
        self.assertEqual(snapshot["harness"]["runs"][0]["machine_messages"][0]["kind"], "session.operator_interrupt")

    def test_dashboard_collect_snapshot_surfaces_acp_summary(self):
        run_id = "run_acp"
        state_dir = self.dashboard.HARNESS_RUN_ROOT / run_id / "state"
        state_dir.mkdir(parents=True)
        (self.dashboard.HARNESS_RUN_ROOT / run_id / "channel.jsonl").write_text(
            json.dumps({"run_id": run_id, "channel": "event", "msg_seq": 1, "timestamp": "2026-04-05T00:00:00+00:00", "kind": "acp.request", "payload": {"method": "session/prompt"}, "integrity": {"prev_hash": None, "hash": "a"}}) + "\n" +
            json.dumps({"run_id": run_id, "channel": "event", "msg_seq": 2, "timestamp": "2026-04-05T00:00:01+00:00", "kind": "acp.notification", "payload": {"kind": "session/update"}, "integrity": {"prev_hash": "a", "hash": "b"}}) + "\n"
        )
        (state_dir / "session.json").write_text(
            json.dumps({
                "status": "degraded",
                "transport": "acp",
                "child_pid": 2222,
                "acp_session_id": "sess-1",
                "initialized": True,
                "last_request_method": "session/prompt",
                "last_notification_kind": "session/update",
                "degraded_reason": "upstream_rate_limited",
                "quarantine_count": 2,
                "capabilities": {
                    "supports_transport_cancel": False,
                    "supports_live_interrupt": False,
                    "supports_native_session_resume": True,
                    "supports_tool_roundtrip": False,
                    "cancel_kind": "logical",
                    "late_result_policy": "quarantine",
                },
            })
        )
        self.dashboard.HARNESS_RUNS.write_text(json.dumps({"runs": {run_id: {"run_id": run_id, "provider": "gemini", "policy_profile": "balanced", "status": "running", "created_at": "2026-04-05T00:00:00+00:00"}}}))
        self.dashboard.HARNESS_ACTIVE_RUN.write_text(json.dumps({}))
        self.dashboard.PROFILES.write_text(json.dumps({}))
        self.dashboard.CLIENT_BINDINGS.write_text(json.dumps({"tokens": {}}))
        with patch.object(self.dashboard, "gateway_status", return_value={"live": True, "ready": True, "health_models": 1, "port": 4000, "error": ""}), \
             patch.object(self.dashboard, "session_is_live", return_value=True):
            snapshot = self.dashboard.collect_snapshot()
        run = snapshot["harness"]["runs"][0]
        self.assertEqual(run["acp_summary"]["session_id"], "sess-1")
        self.assertEqual(run["acp_summary"]["degraded_reason"], "upstream_rate_limited")
        self.assertEqual(run["acp_summary"]["quarantine_count"], 2)
        self.assertFalse(run["acp_summary"]["supports_transport_cancel"])
        self.assertEqual(run["acp_summary"]["late_result_policy"], "quarantine")
        self.assertEqual(run["recommended_action"], "Inspect ACP failure: upstream_rate_limited")

    def test_dashboard_collect_snapshot_surfaces_review_lanes_and_checklist(self):
        self.dashboard.HARNESS_RUNS.write_text(json.dumps({"runs": {}}))
        self.dashboard.HARNESS_ACTIVE_RUN.write_text(json.dumps({}))
        self.dashboard.HARNESS_STATE.write_text(json.dumps({
            "lanes": {
                "worker": {"health": "healthy"},
                "verifier": {"health": "degraded"},
                "adversary": {"health": "healthy"},
            },
            "checklist": {"items": [{"id": "a", "implemented": True}, {"id": "b", "implemented": True}, {"id": "c", "implemented": False}]},
        }))
        self.dashboard.PROFILES.write_text(json.dumps({}))
        self.dashboard.CLIENT_BINDINGS.write_text(json.dumps({"tokens": {}}))
        with patch.object(self.dashboard, "gateway_status", return_value={"live": True, "ready": True, "health_models": 1, "port": 4000, "error": ""}):
            snapshot = self.dashboard.collect_snapshot()
        self.assertEqual(snapshot["summary"]["degraded_review_lanes"], 1)
        self.assertEqual(snapshot["summary"]["implemented_checklist_items"], 2)
        self.assertEqual(snapshot["summary"]["total_checklist_items"], 3)
        self.assertEqual(snapshot["review_lanes"]["verifier"]["health"], "degraded")

    def test_dashboard_collect_snapshot_uses_ledger_bound_acp_identity(self):
        run_id = "run_acp_ledger"
        (self.dashboard.HARNESS_RUN_ROOT / run_id / "state").mkdir(parents=True)
        self.dashboard.HARNESS_RUNS.write_text(json.dumps({"runs": {
            run_id: {
                "run_id": run_id,
                "provider": "gemini",
                "policy_profile": "balanced",
                "status": "running",
                "created_at": "2026-04-05T00:00:00+00:00",
                "transport": "acp",
                "acp_pid": 3333,
                "acp_session_id": "sess-ledger",
                "acp_initialized": True,
                "acp_status": "running",
                "acp_last_request_method": "session/prompt",
                "acp_failure_count": 2,
                "acp_cancel_supported": True,
            }
        }}))
        self.dashboard.HARNESS_ACTIVE_RUN.write_text(json.dumps({}))
        self.dashboard.PROFILES.write_text(json.dumps({}))
        self.dashboard.CLIENT_BINDINGS.write_text(json.dumps({"tokens": {}}))
        with patch.object(self.dashboard, "gateway_status", return_value={"live": True, "ready": True, "health_models": 1, "port": 4000, "error": ""}), \
             patch.object(self.dashboard, "session_is_live", return_value=True):
            snapshot = self.dashboard.collect_snapshot()
        run = snapshot["harness"]["runs"][0]
        self.assertEqual(run["session"]["acp_session_id"], "sess-ledger")
        self.assertEqual(run["acp_summary"]["failure_count"], 2)
        self.assertEqual(run["recommended_action"], "Cancel current ACP prompt")

    def test_dashboard_collect_snapshot_marks_stale_running_record_as_not_active(self):
        run_id = "run_stale"
        (self.dashboard.HARNESS_RUN_ROOT / run_id / "state").mkdir(parents=True)
        (self.dashboard.HARNESS_RUN_ROOT / run_id / "state" / "session.json").write_text(
            json.dumps({"status": "running", "child_pid": 99999})
        )
        self.dashboard.HARNESS_RUNS.write_text(json.dumps({"runs": {run_id: {"run_id": run_id, "provider": "claude", "policy_profile": "balanced", "status": "running", "created_at": "2026-04-05T00:00:00+00:00"}}}))
        self.dashboard.HARNESS_ACTIVE_RUN.write_text(json.dumps({}))
        self.dashboard.PROFILES.write_text(json.dumps({}))
        self.dashboard.CLIENT_BINDINGS.write_text(json.dumps({"tokens": {}}))
        with patch.object(self.dashboard, "gateway_status", return_value={"live": True, "ready": True, "health_models": 1, "port": 4000, "error": ""}), \
             patch.object(self.dashboard, "session_is_live", return_value=False):
            snapshot = self.dashboard.collect_snapshot()
        self.assertEqual(snapshot["summary"]["active_runs"], 0)
        self.assertEqual(snapshot["summary"]["recent_states"][0]["label"], "Stale record")
        self.assertEqual(snapshot["harness"]["runs"][0]["derived_status"], "stale")

    def test_dashboard_collect_snapshot_marks_failed_launch_state(self):
        run_id = "run_failed"
        (self.dashboard.HARNESS_RUN_ROOT / run_id / "state").mkdir(parents=True)
        self.dashboard.HARNESS_RUNS.write_text(json.dumps({"runs": {run_id: {"run_id": run_id, "provider": "claude", "policy_profile": "balanced", "status": "failed_launch", "created_at": "2026-04-05T00:00:00+00:00"}}}))
        self.dashboard.HARNESS_ACTIVE_RUN.write_text(json.dumps({}))
        self.dashboard.PROFILES.write_text(json.dumps({}))
        self.dashboard.CLIENT_BINDINGS.write_text(json.dumps({"tokens": {}}))
        with patch.object(self.dashboard, "gateway_status", return_value={"live": True, "ready": True, "health_models": 1, "port": 4000, "error": ""}):
            snapshot = self.dashboard.collect_snapshot()
        self.assertEqual(snapshot["summary"]["recent_states"][0]["label"], "Failed launch")

    def test_dashboard_collect_snapshot_summarizes_multiple_run_states(self):
        active_id = "run_active"
        blocked_id = "run_blocked"
        attention_id = "run_attention"
        for run_id in (active_id, blocked_id, attention_id):
            (self.dashboard.HARNESS_RUN_ROOT / run_id / "state").mkdir(parents=True)
        (self.dashboard.HARNESS_RUN_ROOT / active_id / "state" / "session.json").write_text(json.dumps({"status": "running", "child_pid": 1001}))
        (self.dashboard.HARNESS_RUN_ROOT / blocked_id / "state" / "session.json").write_text(json.dumps({"status": "running", "child_pid": 1002}))
        (self.dashboard.HARNESS_RUN_ROOT / attention_id / "state" / "session.json").write_text(json.dumps({"status": "running", "child_pid": 1003}))
        (self.dashboard.HARNESS_RUN_ROOT / blocked_id / "state" / "governor.json").write_text(json.dumps({"verification_only_mode": True}))
        (self.dashboard.HARNESS_RUN_ROOT / attention_id / "state" / "intervention.json").write_text(json.dumps({"status": "active", "notice": "Need proof"}))
        self.dashboard.HARNESS_RUNS.write_text(json.dumps({"runs": {
            active_id: {"run_id": active_id, "provider": "claude", "policy_profile": "balanced", "status": "running", "created_at": "2026-04-05T00:00:00+00:00"},
            blocked_id: {"run_id": blocked_id, "provider": "codex", "policy_profile": "high_assurance", "status": "running", "created_at": "2026-04-05T00:00:01+00:00"},
            attention_id: {"run_id": attention_id, "provider": "gemini", "policy_profile": "balanced", "status": "running", "created_at": "2026-04-05T00:00:02+00:00"},
        }}))
        self.dashboard.HARNESS_ACTIVE_RUN.write_text(json.dumps({"run_id": active_id}))
        self.dashboard.PROFILES.write_text(json.dumps({}))
        self.dashboard.CLIENT_BINDINGS.write_text(json.dumps({"tokens": {}}))
        with patch.object(self.dashboard, "gateway_status", return_value={"live": True, "ready": True, "health_models": 3, "port": 4000, "error": ""}), \
             patch.object(self.dashboard, "session_is_live", side_effect=lambda session: session.get("child_pid") in {1001, 1002, 1003}):
            snapshot = self.dashboard.collect_snapshot()
        self.assertEqual(snapshot["summary"]["active_runs"], 3)
        self.assertEqual(snapshot["summary"]["blocked_runs"], 1)
        self.assertEqual(snapshot["summary"]["attention_runs"], 1)
        runs = {run["run_id"]: run for run in snapshot["harness"]["runs"]}
        actions = {run["run_id"]: run["recommended_action"] for run in snapshot["harness"]["runs"]}
        self.assertEqual(actions[blocked_id], "Run a passing verification step")
        self.assertIn("Need proof", runs[attention_id]["intervention"].get("notice", ""))

    def test_dashboard_override_run_intervention_force_and_clear(self):
        run_id = "run_demo"
        state_dir = self.dashboard.HARNESS_RUN_ROOT / run_id / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "governor.json").write_text(
            json.dumps({"last_command_id": "cmd-1", "verification_required": False, "verification_only_mode": False})
        )

        forced = self.dashboard.override_run_intervention(run_id, "force_verify")
        self.assertTrue(forced["ok"])
        forced_governor = json.loads((state_dir / "governor.json").read_text())
        forced_intervention = json.loads((state_dir / "intervention.json").read_text())
        self.assertTrue(forced_governor["verification_required"])
        self.assertTrue(forced_governor["verification_only_mode"])
        self.assertEqual(forced_intervention["status"], "active")

        cleared = self.dashboard.override_run_intervention(run_id, "clear")
        self.assertTrue(cleared["ok"])
        cleared_governor = json.loads((state_dir / "governor.json").read_text())
        cleared_intervention = json.loads((state_dir / "intervention.json").read_text())
        self.assertFalse(cleared_governor["verification_required"])
        self.assertFalse(cleared_governor["verification_only_mode"])
        self.assertEqual(cleared_intervention["status"], "resolved")

    def test_dashboard_operator_run_action_writes_control_file(self):
        run_id = "run_demo"
        state_dir = self.dashboard.HARNESS_RUN_ROOT / run_id / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "session.json").write_text(json.dumps({"status": "running", "child_pid": 4321}))
        with patch.object(self.dashboard, "session_is_live", return_value=True):
            result = self.dashboard.operator_run_action(run_id, "interrupt")
        self.assertTrue(result["ok"])
        control = json.loads((state_dir / "control.json").read_text())
        self.assertEqual(control["action"], "interrupt")
        self.assertEqual(control["expected_child_pid"], 4321)

    def test_dashboard_operator_run_action_writes_reattach_control_file(self):
        run_id = "run_demo"
        state_dir = self.dashboard.HARNESS_RUN_ROOT / run_id / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "session.json").write_text(json.dumps({"status": "running", "child_pid": 4321, "supervisor_pid": 8765}))
        with patch.object(self.dashboard, "session_is_live", return_value=True):
            result = self.dashboard.operator_run_action(run_id, "reattach")
        self.assertTrue(result["ok"])
        control = json.loads((state_dir / "control.json").read_text())
        self.assertEqual(control["action"], "reattach")
        self.assertEqual(control["expected_supervisor_pid"], 8765)

    def test_dashboard_operator_run_action_writes_acp_cancel_control_file(self):
        run_id = "run_acp"
        state_dir = self.dashboard.HARNESS_RUN_ROOT / run_id / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "session.json").write_text(json.dumps({"status": "running", "transport": "acp", "child_pid": 4321, "supervisor_pid": 8765, "acp_session_id": "sess-1"}))
        with patch.object(self.dashboard, "session_is_live", return_value=True):
            result = self.dashboard.operator_run_action(run_id, "cancel_prompt")
        self.assertTrue(result["ok"])
        control = json.loads((state_dir / "control.json").read_text())
        self.assertEqual(control["action"], "cancel_prompt")
        self.assertEqual(control["expected_session_id"], "sess-1")

    def test_dashboard_operator_run_action_rejects_interrupt_for_acp(self):
        run_id = "run_acp"
        state_dir = self.dashboard.HARNESS_RUN_ROOT / run_id / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "session.json").write_text(json.dumps({"status": "running", "transport": "acp", "child_pid": 4321}))
        with patch.object(self.dashboard, "session_is_live", return_value=True):
            result = self.dashboard.operator_run_action(run_id, "interrupt")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "unsupported_for_acp_transport")

    def test_dashboard_launch_agent_builds_harness_command(self):
        with patch.object(self.dashboard, "spawn_terminal_command", return_value={"ok": True, "terminal": "alacritty"}) as mocked:
            result = self.dashboard.launch_agent("codex", "balanced", "strict", 'exec --json "hello"')
        self.assertTrue(result["ok"])
        command, title = mocked.call_args[0]
        self.assertIn("harness run", command)
        self.assertIn("--provider codex", command)
        self.assertIn("--policy balanced", command)
        self.assertIn("--sandbox strict", command)
        self.assertIn("exec --json hello", command)
        self.assertIn("codex", title)

    def test_dashboard_launch_agent_builds_plain_launch_command_when_harness_off(self):
        with patch.object(self.dashboard, "spawn_terminal_command", return_value={"ok": True, "terminal": "alacritty"}) as mocked:
            result = self.dashboard.launch_agent("claude", "off", "normal", "")
        self.assertTrue(result["ok"])
        command, title = mocked.call_args[0]
        self.assertIn("sandbox set normal", command)
        self.assertIn("launch claude", command)
        self.assertNotIn("harness run", command)
        self.assertEqual(title, "BrokeLLM claude")

    def test_dashboard_launch_agent_builds_gemini_acp_command(self):
        with patch.object(self.dashboard, "spawn_terminal_command", return_value={"ok": True, "terminal": "alacritty"}) as mocked:
            result = self.dashboard.launch_agent("gemini-acp", "balanced", "normal", "prompt --text hello --json")
        self.assertTrue(result["ok"])
        command, title = mocked.call_args[0]
        self.assertIn("--provider gemini", command)
        self.assertIn("python3", command)
        self.assertIn("_gemini_acp.py", command)
        self.assertIn("prompt --text hello --json", command)
        self.assertIn("gemini-acp", title)

    def test_dashboard_reconcile_runs_parses_mapping_output(self):
        fake = subprocess.CompletedProcess(
            args=["python3"],
            returncode=0,
            stdout=json.dumps({"changed": [{"run_id": "r1", "status": "abandoned"}]}),
            stderr="",
        )
        with patch.object(self.dashboard.subprocess, "run", return_value=fake):
            result = self.dashboard.reconcile_runs()
        self.assertTrue(result["ok"])
        self.assertEqual(result["changed"][0]["run_id"], "r1")


if __name__ == "__main__":
    unittest.main()
