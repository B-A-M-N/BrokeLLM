#!/usr/bin/python3
"""Harness command shim for mediated CLI-agent execution."""

import json
import os
import pathlib
import subprocess
import sys
import time

BIN_DIR = pathlib.Path(__file__).resolve().parent
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))

from _harness_common import append_event, sha256_text


def command_classification(name, argv):
    if name in {"pytest", "go", "cargo", "make"}:
        return "verification:test"
    if name in {"npm", "pnpm"} and any(token in argv for token in {"test", "lint", "build"}):
        return "verification:task"
    if name in {"git"}:
        return "vcs"
    if name in {"pip", "python", "python3", "node"}:
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


def main():
    run_id = os.environ.get("BROKE_HARNESS_RUN_ID", "")
    events_file = pathlib.Path(os.environ.get("BROKE_HARNESS_EVENTS_FILE", ""))
    realpaths_file = pathlib.Path(os.environ.get("BROKE_HARNESS_REALPATHS_FILE", ""))
    allowed_paths = [p for p in os.environ.get("BROKE_HARNESS_ALLOWED_PATHS", "").split(":") if p]
    artifact_dir = pathlib.Path(os.environ.get("BROKE_HARNESS_ARTIFACT_DIR", "."))
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
        },
    )

    start = time.time()
    proc = subprocess.run(argv)
    duration_ms = int((time.time() - start) * 1000)

    artifact_refs = []
    if classification.startswith("verification"):
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact = artifact_dir / f"{command_id}.json"
        artifact.write_text(
            json.dumps(
                {
                    "command_id": command_id,
                    "argv": [name, *sys.argv[1:]],
                    "cwd": cwd,
                    "exit_code": proc.returncode,
                    "duration_ms": duration_ms,
                },
                indent=2,
            )
            + "\n"
        )
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
        },
        artifact_refs=artifact_refs,
    )
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
