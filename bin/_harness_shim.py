#!/usr/bin/python3
"""Harness command shim for mediated CLI-agent execution."""

import json
import os
import pathlib
import subprocess
import sys
import time
import hashlib

BIN_DIR = pathlib.Path(__file__).resolve().parent
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))

from _harness_common import append_event, atomic_write_json, read_json, sha256_text
from _run_channel import append_message

MAX_PROVENANCE_FILES = 256
MAX_PROVENANCE_FILE_BYTES = 1024 * 1024


def proc_lineage(pid):
    info = {"pid": pid}
    status = pathlib.Path(f"/proc/{pid}/status")
    exe = pathlib.Path(f"/proc/{pid}/exe")
    comm = pathlib.Path(f"/proc/{pid}/comm")
    try:
        for line in status.read_text().splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            value = value.strip()
            if key == "PPid":
                info["ppid"] = int(value)
            elif key == "Tgid":
                info["tgid"] = int(value)
            elif key in {"NSpgid", "Pgid"}:
                info["pgid"] = int(value.split()[0])
            elif key in {"NSsid", "Sid"}:
                info["sid"] = int(value.split()[0])
    except Exception:
        pass
    try:
        info["exe"] = os.path.realpath(exe)
    except Exception:
        info["exe"] = ""
    try:
        info["comm"] = comm.read_text().strip()
    except Exception:
        info["comm"] = ""
    return info


def command_classification(name, argv):
    if name in {"pytest", "go", "cargo", "make"}:
        return "verification:test"
    if name in {"npm", "pnpm"} and any(token in argv for token in {"test", "lint", "build"}):
        return "verification:task"
    if name in {"git"}:
        return "vcs"
    if name in {"pip", "python", "python3", "node", "sh", "bash", "env"}:
        return "runtime"
    return "tool"


def cwd_allowed(cwd, allowed_paths):
    if not allowed_paths:
        return True
    cwd = os.path.realpath(cwd)
    for allowed in allowed_paths:
        root = os.path.realpath(allowed)
        if cwd == root or cwd.startswith(root + os.sep):
            return True
    return False


def default_governor_state():
    return {
        "command_count": 0,
        "commands_since_verification": 0,
        "writes_since_verification": 0,
        "risk_score": 0,
        "last_verification_ok": None,
        "last_verification_reason": "",
        "verification_required": False,
        "verification_only_mode": False,
        "intervention_reason": "",
        "intervention_notice": "",
        "next_action": "",
        "last_command_id": "",
        "last_classification": "",
        "last_mutation_counts": {"created": 0, "modified": 0, "deleted": 0},
    }


def is_verification_command(classification):
    return classification.startswith("verification")


def command_is_mutating(name, argv, classification):
    args = list(argv)
    if is_verification_command(classification):
        return False
    if name == "git":
        sub = args[0] if args else ""
        return sub in {
            "add", "apply", "am", "commit", "merge", "rebase", "cherry-pick",
            "checkout", "switch", "restore", "reset", "clean", "mv", "rm",
        }
    if name in {"python", "python3", "node", "pip", "sh", "bash", "env"}:
        return True
    if name in {"npm", "pnpm", "go", "cargo", "make"}:
        return classification != "verification:task" and classification != "verification:test"
    return classification in {"runtime", "tool"}


def command_escape_surface(name, argv):
    args = list(argv)
    if name in {"python", "python3"} and any(token in args for token in {"-c", "-m"}):
        return "python_inline_or_module"
    if name == "node" and any(token in args for token in {"-e", "--eval"}):
        return "node_eval"
    if name in {"sh", "bash"} and any(token in args for token in {"-c", "-lc"}):
        return "shell_eval"
    if name == "env" and args:
        return "env_exec"
    return ""


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def snapshot_workspace(root):
    root = pathlib.Path(root)
    if not root.exists() or not root.is_dir():
        return {}
    out = {}
    count = 0
    for path in sorted(root.rglob("*")):
        if count >= MAX_PROVENANCE_FILES:
            break
        try:
            if not path.is_file() or path.is_symlink():
                continue
            rel = path.relative_to(root).as_posix()
            if rel.startswith(".git/") or rel.startswith(".runtime/"):
                continue
            stat = path.stat()
            if stat.st_size > MAX_PROVENANCE_FILE_BYTES:
                out[rel] = {"size": stat.st_size, "sha256": None, "truncated": True}
            else:
                out[rel] = {"size": stat.st_size, "sha256": file_sha256(path), "truncated": False}
            count += 1
        except Exception:
            continue
    return out


def diff_workspace(before, after):
    before = before or {}
    after = after or {}
    changes = {"created": [], "modified": [], "deleted": []}
    for rel, meta in after.items():
        if rel not in before:
            changes["created"].append({"path": rel, **meta})
        elif before[rel].get("sha256") != meta.get("sha256") or before[rel].get("size") != meta.get("size"):
            changes["modified"].append({"path": rel, "before": before[rel], "after": meta})
    for rel, meta in before.items():
        if rel not in after:
            changes["deleted"].append({"path": rel, **meta})
    return changes


def governor_should_intervene(state):
    if state.get("last_verification_ok") is False and state.get("writes_since_verification", 0) >= 1:
        return True, "verification_failed"
    if state.get("risk_score", 0) >= 4 and state.get("writes_since_verification", 0) >= 1:
        return True, "high_risk_mutation_sequence"
    if state.get("writes_since_verification", 0) >= 3:
        return True, "verification_stale"
    if state.get("commands_since_verification", 0) >= 8 and state.get("writes_since_verification", 0) >= 1:
        return True, "checkpoint_required"
    return False, ""


def governor_denies_command(state, name, argv, classification):
    if not state.get("verification_required"):
        return False, ""
    if is_verification_command(classification):
        return False, ""
    if state.get("verification_only_mode"):
        return True, state.get("intervention_reason", "verification_required")
    if command_is_mutating(name, argv, classification):
        return True, state.get("intervention_reason", "verification_required")
    return False, ""


def governor_notice(reason):
    if reason == "verification_failed":
        return "verification failed; run a passing verification command before more mutating work"
    if reason == "high_risk_mutation_sequence":
        return "high-risk mutating activity detected; checkpoint with a real verification step before more work"
    if reason == "verification_stale":
        return "too many mutating commands without verification; run tests or a verification task before more mutating work"
    if reason == "checkpoint_required":
        return "checkpoint required; run a verification command before more mutating work"
    if reason == "suspicious_verification":
        return "verification looked suspicious; run a substantive test or verification task before more mutating work"
    return "verification required before more mutating work"


def governor_next_action(reason):
    if reason == "verification_failed":
        return "Run a passing test command such as `pytest -q` or `npm test` before resuming edits."
    if reason == "high_risk_mutation_sequence":
        return "Run a substantive verification command now. Prefer a regression test that exercises the code you just changed."
    if reason == "verification_stale":
        return "Run a verification command now, then continue implementation only after it passes."
    if reason == "checkpoint_required":
        return "Checkpoint with a verification command before additional work."
    if reason == "suspicious_verification":
        return "Run a substantive verification command that actually executes tests."
    return "Run a verification command before continuing."


def suspicious_verification(name, argv, exit_code, duration_ms):
    if exit_code != 0:
        return False, ""
    args = list(argv)
    if name == "pytest" and any(token in args for token in {"--collect-only", "--fixtures"}):
        return True, "non-executing pytest command"
    if name in {"npm", "pnpm"} and any(token in args for token in {"lint", "build"}) and duration_ms < 800:
        return True, "verification task completed suspiciously fast"
    return False, ""


def intervention_payload(command_id, reason, state):
    return {
        "command_id": command_id,
        "status": "active",
        "reason": reason,
        "notice": governor_notice(reason),
        "next_action": state.get("next_action") or governor_next_action(reason),
        "writes_since_verification": state.get("writes_since_verification", 0),
        "commands_since_verification": state.get("commands_since_verification", 0),
        "last_verification_reason": state.get("last_verification_reason", ""),
    }


def update_governor_state(state, name, argv, classification, exit_code, command_id, duration_ms=0, mutation_counts=None):
    next_state = dict(state)
    next_state["command_count"] = int(next_state.get("command_count", 0)) + 1
    next_state["last_command_id"] = command_id
    next_state["last_classification"] = classification
    next_state["last_mutation_counts"] = mutation_counts or {"created": 0, "modified": 0, "deleted": 0}
    if is_verification_command(classification):
        suspicious, suspicious_reason = suspicious_verification(name, argv, exit_code, duration_ms)
        next_state["commands_since_verification"] = 0
        next_state["writes_since_verification"] = 0
        next_state["risk_score"] = 0
        next_state["last_verification_ok"] = exit_code == 0 and not suspicious
        next_state["last_verification_reason"] = suspicious_reason
        if exit_code == 0 and not suspicious:
            next_state["verification_required"] = False
            next_state["verification_only_mode"] = False
            next_state["intervention_reason"] = ""
            next_state["intervention_notice"] = ""
            next_state["next_action"] = ""
        else:
            next_state["verification_required"] = True
            next_state["verification_only_mode"] = True
            next_state["intervention_reason"] = "suspicious_verification" if suspicious else "verification_failed"
            next_state["intervention_notice"] = governor_notice(next_state["intervention_reason"])
            next_state["next_action"] = governor_next_action(next_state["intervention_reason"])
        return next_state

    next_state["commands_since_verification"] = int(next_state.get("commands_since_verification", 0)) + 1
    if command_is_mutating(name, argv, classification):
        next_state["writes_since_verification"] = int(next_state.get("writes_since_verification", 0)) + 1
        if command_escape_surface(name, argv):
            next_state["risk_score"] = int(next_state.get("risk_score", 0)) + 2
        else:
            next_state["risk_score"] = int(next_state.get("risk_score", 0)) + 1
    intervene, reason = governor_should_intervene(next_state)
    if intervene:
        next_state["verification_required"] = True
        next_state["verification_only_mode"] = True
        next_state["intervention_reason"] = reason
        next_state["intervention_notice"] = governor_notice(reason)
        next_state["next_action"] = governor_next_action(reason)
    return next_state


def main():
    run_id = os.environ.get("BROKE_HARNESS_RUN_ID", "")
    channel_file = pathlib.Path(os.environ.get("BROKE_HARNESS_CHANNEL_FILE", ""))
    events_file = pathlib.Path(os.environ.get("BROKE_HARNESS_EVENTS_FILE", ""))
    realpaths_file = pathlib.Path(os.environ.get("BROKE_HARNESS_REALPATHS_FILE", ""))
    allowed_paths = [p for p in os.environ.get("BROKE_HARNESS_ALLOWED_PATHS", "").split(":") if p]
    artifact_dir = pathlib.Path(os.environ.get("BROKE_HARNESS_ARTIFACT_DIR", "."))
    governor_state_file = pathlib.Path(os.environ.get("BROKE_HARNESS_GOVERNOR_STATE", ""))
    intervention_file = pathlib.Path(os.environ.get("BROKE_HARNESS_INTERVENTION_FILE", ""))
    name = pathlib.Path(sys.argv[0]).name

    if not run_id or not events_file or not realpaths_file.exists():
        print(f"[harness-shim] missing harness runtime for {name}", file=sys.stderr)
        return 127

    realpaths = json.loads(realpaths_file.read_text())
    real_cmd = realpaths.get(name)
    if not real_cmd:
        print(f"[harness-shim] no real command configured for {name}", file=sys.stderr)
        return 127

    cwd = os.getcwd()
    argv = [real_cmd, *sys.argv[1:]]
    classification = command_classification(name, sys.argv[1:])
    command_id = f"cmd_{sha256_text(f'{run_id}:{name}:{time.time()}')[:10]}"
    shim_lineage = {
        "shim_pid": os.getpid(),
        "shim_ppid": os.getppid(),
        "shim_pgid": os.getpgid(0),
        "shim_sid": os.getsid(0),
        "real_cmd": real_cmd,
    }
    governor_state = read_json(governor_state_file, default_governor_state()) if governor_state_file else default_governor_state()
    had_intervention = bool(governor_state.get("verification_required"))

    if not cwd_allowed(cwd, allowed_paths):
        append_event(
            events_file,
            run_id,
            "policy.denied",
            "worker_execution",
            "command_shim",
            name,
            payload={
                "command_id": command_id,
                "argv": [name, *sys.argv[1:]],
                "cwd": cwd,
                "classification": classification,
                "reason": "cwd outside allowed_paths",
            },
        )
        print(f"[harness] denied {name}: cwd outside allowed paths", file=sys.stderr)
        return 126

    denied, deny_reason = governor_denies_command(governor_state, name, sys.argv[1:], classification)
    if denied:
        notice = governor_notice(deny_reason)
        if intervention_file:
            intervention_file.parent.mkdir(parents=True, exist_ok=True)
            intervention_file.write_text(
                json.dumps(
                    {
                        "run_id": run_id,
                        "command_id": command_id,
                        "status": "active",
                        "reason": deny_reason,
                        "notice": notice,
                        "next_action": governor_next_action(deny_reason),
                    },
                    indent=2,
                )
                + "\n"
            )
            try:
                intervention_file.chmod(0o600)
            except Exception:
                pass
        append_event(
            events_file,
            run_id,
            "policy.intervention",
            "worker_execution",
            "command_shim",
            name,
            payload={
                "command_id": command_id,
                "argv": [name, *sys.argv[1:]],
                "cwd": cwd,
                "classification": classification,
                "reason": deny_reason,
                "notice": notice,
            },
        )
        print(f"[harness] intervention: {notice}", file=sys.stderr)
        return 125

    append_event(
        events_file,
        run_id,
        "command.started",
        "worker_execution",
        "command_shim",
        name,
        payload={
            "command_id": command_id,
            "argv": [name, *sys.argv[1:]],
            "cwd": cwd,
            "classification": classification,
            "process_lineage": {"shim": shim_lineage},
        },
    )
    if channel_file:
        append_message(
            channel_file,
            run_id,
            "event",
            "command.started",
            {
                "command_id": command_id,
                "argv": [name, *sys.argv[1:]],
                "cwd": cwd,
                "classification": classification,
                "process_lineage": {"shim": shim_lineage},
            },
        )
    escape_surface = command_escape_surface(name, sys.argv[1:])
    if escape_surface:
        append_event(
            events_file,
            run_id,
            "command.escape_surface",
            "worker_execution",
            "command_shim",
            name,
            payload={
                "command_id": command_id,
                "argv": [name, *sys.argv[1:]],
                "cwd": cwd,
                "escape_surface": escape_surface,
            },
        )

    provenance_before = snapshot_workspace(cwd) if command_is_mutating(name, sys.argv[1:], classification) else None
    start = time.time()
    proc = subprocess.Popen(argv)
    child_lineage = proc_lineage(proc.pid)
    proc.wait()
    duration_ms = int((time.time() - start) * 1000)
    provenance_after = snapshot_workspace(cwd) if provenance_before is not None else None

    artifact_refs = []
    mutation_changes = diff_workspace(provenance_before, provenance_after) if provenance_before is not None else None
    mutation_counts = {
        "created": len(mutation_changes["created"]) if mutation_changes else 0,
        "modified": len(mutation_changes["modified"]) if mutation_changes else 0,
        "deleted": len(mutation_changes["deleted"]) if mutation_changes else 0,
    }
    if classification.startswith("verification") or mutation_changes is not None:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact = artifact_dir / f"{command_id}.json"
        payload = {
            "command_id": command_id,
            "argv": [name, *sys.argv[1:]],
            "cwd": cwd,
            "exit_code": proc.returncode,
            "duration_ms": duration_ms,
            "process_lineage": {"shim": shim_lineage, "child": child_lineage},
        }
        if mutation_changes is not None:
            payload["mutation_provenance"] = mutation_changes
        artifact.write_text(json.dumps(payload, indent=2) + "\n")
        try:
            artifact.chmod(0o600)
        except Exception:
            pass
        artifact_refs.append(str(artifact))

    append_event(
        events_file,
        run_id,
        "command.completed",
        "worker_execution",
        "command_shim",
        name,
        payload={
            "command_id": command_id,
            "argv": [name, *sys.argv[1:]],
            "cwd": cwd,
            "exit_code": proc.returncode,
            "duration_ms": duration_ms,
            "classification": classification,
            "policy_decision": "allowed",
            "process_lineage": {"shim": shim_lineage, "child": child_lineage},
            "mutation_counts": mutation_counts,
        },
        artifact_refs=artifact_refs,
    )
    if channel_file:
        append_message(
            channel_file,
            run_id,
            "event",
            "command.completed",
            {
                "command_id": command_id,
                "argv": [name, *sys.argv[1:]],
                "cwd": cwd,
                "exit_code": proc.returncode,
                "duration_ms": duration_ms,
                "classification": classification,
                "process_lineage": {"shim": shim_lineage, "child": child_lineage},
                "mutation_counts": mutation_counts,
                "artifact_refs": artifact_refs,
            },
        )
    if governor_state_file:
        next_state = update_governor_state(governor_state, name, sys.argv[1:], classification, proc.returncode, command_id, duration_ms, mutation_counts=mutation_counts)
        atomic_write_json(governor_state_file, next_state)
        if next_state.get("verification_required") and next_state.get("intervention_reason") and next_state.get("intervention_reason") != governor_state.get("intervention_reason"):
            payload = intervention_payload(command_id, next_state["intervention_reason"], next_state)
            append_event(
                events_file,
                run_id,
                "policy.intervention",
                "worker_execution",
                "policy_engine",
                "governor",
                payload=payload,
            )
            if intervention_file:
                intervention_file.parent.mkdir(parents=True, exist_ok=True)
                intervention_file.write_text(json.dumps({"run_id": run_id, **payload}, indent=2) + "\n")
                try:
                    intervention_file.chmod(0o600)
                except Exception:
                    pass
            print(f"[harness] checkpoint: {payload['notice']}", file=sys.stderr)
        elif had_intervention and not next_state.get("verification_required") and intervention_file:
            intervention_file.parent.mkdir(parents=True, exist_ok=True)
            intervention_file.write_text(
                json.dumps(
                    {
                        "run_id": run_id,
                        "command_id": command_id,
                        "status": "resolved",
                        "notice": "verification passed; runtime restrictions cleared",
                        "next_action": "Continue the session. Mutating commands are allowed again.",
                    },
                    indent=2,
                )
                + "\n"
            )
            try:
                intervention_file.chmod(0o600)
            except Exception:
                pass
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
