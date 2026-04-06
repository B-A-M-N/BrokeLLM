import importlib.util
import json
import os
import pathlib
import shlex
import shutil
import signal
import struct
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_module(name, relpath):
    path = REPO_ROOT / relpath
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_mapping_module():
    return _load_module("broke_mapping_hostile_test", "bin/_mapping.py")


def load_harness_shim_module():
    return _load_module("broke_harness_shim_hostile_test", "bin/_harness_shim.py")


def load_pty_harness_module():
    return _load_module("broke_pty_harness_hostile_test", "bin/_pty_harness.py")


def load_dashboard_module():
    return _load_module("broke_dashboard_hostile_test", "bin/_dashboard.py")


def load_harness_common_module():
    return _load_module("broke_harness_common_hostile_test", "bin/_harness_common.py")


def load_run_channel_module():
    return _load_module("broke_run_channel_hostile_test", "bin/_run_channel.py")


class HostileRuntimeTestCase(unittest.TestCase):
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

    def test_harness_shim_classifies_shell_escape_surfaces_as_runtime(self):
        shim = load_harness_shim_module()
        self.assertEqual(shim.command_classification("bash", ["-lc", "echo hi"]), "runtime")
        self.assertEqual(shim.command_classification("sh", ["-c", "touch x"]), "runtime")
        self.assertEqual(shim.command_classification("env", ["python3", "-c", "print(1)"]), "runtime")
        self.assertTrue(shim.command_is_mutating("bash", ["-lc", "echo hi > out"], "runtime"))
        self.assertEqual(shim.command_escape_surface("bash", ["-lc", "echo hi"]), "shell_eval")
        self.assertEqual(shim.command_escape_surface("python3", ["-c", "print(1)"]), "python_inline_or_module")
        self.assertEqual(shim.command_escape_surface("node", ["-e", "console.log(1)"]), "node_eval")
        self.assertEqual(shim.command_escape_surface("env", ["python3", "-c", "print(1)"]), "env_exec")

    def test_harness_shim_integration_captures_mutation_provenance_for_shell_eval(self):
        root = pathlib.Path(self.tempdir.name) / "shim-run"
        root.mkdir(parents=True)
        env = os.environ.copy()
        env.update(self._build_harness_env(root))
        env["BROKE_HARNESS_ALLOWED_PATHS"] = str(root)
        (root / "realpaths.json").write_text(json.dumps({"bash": shutil.which("bash") or "/bin/bash"}))
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
        self.assertIn("process_lineage", completed["payload"])
        artifact = pathlib.Path(completed["artifact_refs"][0])
        artifact_payload = json.loads(artifact.read_text())
        self.assertIn("mutation_provenance", artifact_payload)
        self.assertIn("process_lineage", artifact_payload)
        self.assertEqual(artifact_payload["mutation_provenance"]["created"][0]["path"], "out.txt")

    def test_pty_harness_ignores_invalid_intervention_json(self):
        pty_harness = load_pty_harness_module()
        intervention_file = pathlib.Path(self.tempdir.name) / "intervention.json"
        intervention_file.write_text("{bad json")
        payload, seen = pty_harness.read_intervention(intervention_file, "")
        self.assertIsNone(payload)
        self.assertEqual(seen, "")

    def test_pty_harness_ignores_invalid_control_json(self):
        pty_harness = load_pty_harness_module()
        control_file = pathlib.Path(self.tempdir.name) / "control.json"
        control_file.write_text("{bad json")
        payload, seen = pty_harness.read_control(control_file, "")
        self.assertIsNone(payload)
        self.assertEqual(seen, "")

    def test_pty_harness_deduplicates_control_marker(self):
        pty_harness = load_pty_harness_module()
        control_file = pathlib.Path(self.tempdir.name) / "control.json"
        control_file.write_text(json.dumps({"command_id": "op1", "action": "interrupt"}))
        payload, seen = pty_harness.read_control(control_file, "")
        self.assertEqual(payload["action"], "interrupt")
        payload_again, seen_again = pty_harness.read_control(control_file, seen)
        self.assertIsNone(payload_again)
        self.assertEqual(seen_again, "op1:interrupt")

    def test_pty_harness_rejects_control_for_mismatched_session(self):
        pty_harness = load_pty_harness_module()
        self.assertFalse(pty_harness.control_matches_session({"expected_supervisor_pid": 999, "expected_child_pid": 123}, supervisor_pid=1000, child_pid=123))
        self.assertFalse(pty_harness.control_matches_session({"expected_supervisor_pid": 1000, "expected_child_pid": 124}, supervisor_pid=1000, child_pid=123))
        self.assertTrue(pty_harness.control_matches_session({"expected_supervisor_pid": 1000, "expected_child_pid": 123}, supervisor_pid=1000, child_pid=123))

    def test_pty_harness_prefers_process_group_signal(self):
        pty_harness = load_pty_harness_module()
        with patch.object(pty_harness.os, "getpgid", return_value=4321), patch.object(pty_harness.os, "killpg") as killpg, patch.object(pty_harness.os, "kill") as kill:
            target = pty_harness.signal_child_tree(1234, 15)
        self.assertEqual(target, "process_group")
        killpg.assert_called_once_with(4321, 15)
        kill.assert_not_called()

    def test_pty_harness_falls_back_to_process_signal(self):
        pty_harness = load_pty_harness_module()
        with patch.object(pty_harness.os, "getpgid", side_effect=OSError()), patch.object(pty_harness.os, "kill", return_value=None) as kill:
            target = pty_harness.signal_child_tree(1234, 2)
        self.assertEqual(target, "process")
        kill.assert_called_once_with(1234, 2)

    def test_pty_harness_kill_escalates_when_child_tree_survives(self):
        pty_harness = load_pty_harness_module()
        with patch.object(pty_harness, "signal_child_tree", side_effect=["process_group", "process_group", "missing", "process_group"]) as signal_tree, patch.object(pty_harness.time, "sleep", return_value=None), patch.object(pty_harness.time, "time", side_effect=[0.0, 0.02, 0.04]):
            target = pty_harness.terminate_child_tree(1234, grace_seconds=0.1)
        self.assertEqual(target, "process_group")
        self.assertEqual(signal_tree.call_args_list[0].args, (1234, pty_harness.signal.SIGTERM))

    def test_pty_harness_kill_escalates_to_sigkill_after_grace(self):
        pty_harness = load_pty_harness_module()
        with patch.object(pty_harness, "signal_child_tree", side_effect=["process_group", "process_group", "process_group", "process_group"]) as signal_tree, patch.object(pty_harness.time, "sleep", return_value=None), patch.object(pty_harness.time, "time", side_effect=[0.0, 0.02, 0.12]):
            target = pty_harness.terminate_child_tree(1234, grace_seconds=0.1)
        self.assertEqual(target, "process_group_escalated")
        self.assertEqual(signal_tree.call_args_list[0].args, (1234, pty_harness.signal.SIGTERM))
        self.assertEqual(signal_tree.call_args_list[-1].args, (1234, pty_harness.signal.SIGKILL))

    def test_pty_harness_terminate_child_tree_kills_real_process_group(self):
        pty_harness = load_pty_harness_module()
        proc = subprocess.Popen(
            ["/bin/bash", "-lc", 'trap "" TERM; (trap "" TERM; sleep 30) & child=$!; echo $child > "$0"; wait', str(pathlib.Path(self.tempdir.name) / "child.pid")],
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

    def test_pty_harness_sync_winsize_copies_terminal_size(self):
        pty_harness = load_pty_harness_module()
        with patch.object(pty_harness.os, "isatty", return_value=True), \
             patch.object(pty_harness.fcntl, "ioctl", side_effect=[
                 struct.pack("HHHH", 40, 120, 0, 0),
                 None,
             ]) as ioctl:
            winsize = pty_harness.sync_winsize(0, 99)
        self.assertEqual(winsize["rows"], 40)
        self.assertEqual(winsize["cols"], 120)
        self.assertEqual(ioctl.call_args_list[1].args[0], 99)

    def test_pty_harness_foreground_helpers(self):
        pty_harness = load_pty_harness_module()
        with patch.object(pty_harness.os, "isatty", return_value=True), \
             patch.object(pty_harness.os, "tcgetpgrp", return_value=2222), \
             patch.object(pty_harness.os, "tcsetpgrp", return_value=None) as setpgrp:
            before = pty_harness.foreground_pgid(0)
            result = pty_harness.reclaim_terminal(0, 3333)
        self.assertEqual(before, 2222)
        self.assertTrue(result["changed"])
        setpgrp.assert_called_once_with(0, 3333)

    def test_pty_harness_installs_terminal_signal_guards(self):
        pty_harness = load_pty_harness_module()
        with patch.object(pty_harness.signal, "getsignal", side_effect=["a", "b"]), \
             patch.object(pty_harness.signal, "signal") as sigfn:
            previous = pty_harness.install_supervisor_signal_guards()
        self.assertEqual(previous[pty_harness.signal.SIGTTOU], "a")
        self.assertEqual(previous[pty_harness.signal.SIGTTIN], "b")
        sigfn.assert_any_call(pty_harness.signal.SIGTTOU, pty_harness.signal.SIG_IGN)
        sigfn.assert_any_call(pty_harness.signal.SIGTTIN, pty_harness.signal.SIG_IGN)

    @unittest.skipUnless(shutil.which("bwrap"), "bwrap unavailable")
    def test_strict_bwrap_blocks_filesystem_escape_to_unbound_path(self):
        workdir = pathlib.Path(self.tempdir.name) / "work"
        workdir.mkdir()
        secret_dir = pathlib.Path(self.tempdir.name) / "secret"
        secret_dir.mkdir()
        secret_file = secret_dir / "secret.txt"
        secret_file.write_text("top-secret")
        proc = self._run_minimal_strict_bwrap(workdir, f'test ! -e {shlex.quote(str(secret_file))}')
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)

    @unittest.skipUnless(shutil.which("bwrap"), "bwrap unavailable")
    def test_strict_bwrap_blocks_arbitrary_network(self):
        workdir = pathlib.Path(self.tempdir.name) / "net"
        workdir.mkdir()
        cmd = "python3 -c \"import socket,sys; s=socket.socket(); s.settimeout(1); rc=s.connect_ex(('1.1.1.1',80)); sys.exit(1 if rc == 0 else 0)\""
        proc = self._run_minimal_strict_bwrap(workdir, cmd)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)

    def test_dashboard_operator_run_action_rejects_dead_session_controls(self):
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

    def test_mapping_reconcile_marks_stale_running_run_abandoned(self):
        record = self.mod._register_harness_run("claude", "balanced", "medium", "normal", str(self.mod.DIR), [str(self.mod.DIR)])
        run_id = record["run_id"]
        self.mod.HARNESS_RUN_ROOT.joinpath(run_id, "state").mkdir(parents=True, exist_ok=True)
        self.mod.HARNESS_RUN_ROOT.joinpath(run_id, "state", "session.json").write_text(json.dumps({"status": "running", "child_pid": 999999}))
        with patch.object(self.mod, "_pid_is_live", return_value=False):
            result = self.mod._reconcile_harness_runs()
        self.assertEqual(result["changed"][0]["status"], "abandoned")
        saved = json.loads(self.mod.HARNESS_RUNS.read_text())
        self.assertEqual(saved["runs"][run_id]["status"], "abandoned")

    def test_mapping_reconcile_marks_dead_completed_session_completed(self):
        record = self.mod._register_harness_run("codex", "balanced", "medium", "normal", str(self.mod.DIR), [str(self.mod.DIR)])
        run_id = record["run_id"]
        self.mod.HARNESS_RUN_ROOT.joinpath(run_id, "state").mkdir(parents=True, exist_ok=True)
        self.mod.HARNESS_RUN_ROOT.joinpath(run_id, "state", "session.json").write_text(json.dumps({"status": "completed", "child_pid": 999999, "exit_code": 0}))
        with patch.object(self.mod, "_pid_is_live", return_value=False):
            result = self.mod._reconcile_harness_runs()
        change = next(item for item in result["changed"] if item["run_id"] == run_id)
        self.assertEqual(change["status"], "completed")
        saved = json.loads(self.mod.HARNESS_RUNS.read_text())
        self.assertEqual(saved["runs"][run_id]["status"], "completed")

    def test_mapping_reconcile_marks_missing_session_failed_launch(self):
        record = self.mod._register_harness_run("claude", "balanced", "medium", "normal", str(self.mod.DIR), [str(self.mod.DIR)])
        run_id = record["run_id"]
        with patch.object(self.mod, "_pid_is_live", return_value=False):
            result = self.mod._reconcile_harness_runs()
        change = next(item for item in result["changed"] if item["run_id"] == run_id)
        self.assertEqual(change["status"], "failed_launch")
        saved = json.loads(self.mod.HARNESS_RUNS.read_text())
        self.assertEqual(saved["runs"][run_id]["status"], "failed_launch")

    def test_mapping_reconcile_clears_active_pointer_for_dead_run(self):
        record = self.mod._register_harness_run("claude", "balanced", "medium", "normal", str(self.mod.DIR), [str(self.mod.DIR)])
        run_id = record["run_id"]
        self.mod.HARNESS_RUN_ROOT.joinpath(run_id, "state").mkdir(parents=True, exist_ok=True)
        self.mod.HARNESS_RUN_ROOT.joinpath(run_id, "state", "session.json").write_text(json.dumps({"status": "running", "child_pid": 999999}))
        with patch.object(self.mod, "_pid_is_live", return_value=False):
            result = self.mod._reconcile_harness_runs()
        self.assertEqual(result["active_run"], {})
        self.assertEqual(json.loads(self.mod.HARNESS_ACTIVE_RUN.read_text()), {})

    def test_mapping_reconcile_is_idempotent_after_first_repair(self):
        record = self.mod._register_harness_run("claude", "balanced", "medium", "normal", str(self.mod.DIR), [str(self.mod.DIR)])
        run_id = record["run_id"]
        self.mod.HARNESS_RUN_ROOT.joinpath(run_id, "state").mkdir(parents=True, exist_ok=True)
        self.mod.HARNESS_RUN_ROOT.joinpath(run_id, "state", "session.json").write_text(json.dumps({"status": "running", "child_pid": 999999}))
        with patch.object(self.mod, "_pid_is_live", return_value=False):
            first = self.mod._reconcile_harness_runs()
            second = self.mod._reconcile_harness_runs()
        self.assertEqual(len(first["changed"]), 1)
        self.assertEqual(second["changed"], [])

    def test_harness_common_read_json_returns_default_on_partial_json(self):
        common = load_harness_common_module()
        path = pathlib.Path(self.tempdir.name) / "partial.json"
        path.write_text("{bad json")
        self.assertEqual(common.read_json(path, {"fallback": True}), {"fallback": True})

    def test_harness_common_atomic_write_json_writes_complete_json(self):
        common = load_harness_common_module()
        path = pathlib.Path(self.tempdir.name) / "state.json"
        common.atomic_write_json(path, {"ok": True, "n": 3})
        loaded = json.loads(path.read_text())
        self.assertEqual(loaded, {"ok": True, "n": 3})
        self.assertTrue(path.read_text().endswith("\n"))

    def test_harness_common_append_event_assigns_monotonic_event_seq(self):
        common = load_harness_common_module()
        path = pathlib.Path(self.tempdir.name) / "events.jsonl"
        first = common.append_event(path, "run_demo", "session.started", "runtime_control", "pty_supervisor", "pty")
        second = common.append_event(path, "run_demo", "session.operator_interrupt", "runtime_control", "pty_supervisor", "pty")
        self.assertEqual(first["event_seq"], 1)
        self.assertEqual(second["event_seq"], 2)

    def test_run_channel_assigns_monotonic_message_seq(self):
        channel = load_run_channel_module()
        path = pathlib.Path(self.tempdir.name) / "channel.jsonl"
        first = channel.append_message(path, "run_demo", "control", "session.started", {"child_pid": 1})
        second = channel.append_message(path, "run_demo", "control", "session.operator_interrupt", {"child_pid": 1})
        rows = channel.read_messages(path)
        self.assertEqual(first["msg_seq"], 1)
        self.assertEqual(second["msg_seq"], 2)
        self.assertEqual(rows[-1]["kind"], "session.operator_interrupt")
