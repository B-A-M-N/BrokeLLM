#!/usr/bin/env python3
"""Local-only BrokeLLM dashboard server."""

from __future__ import annotations

import json
import os
import pathlib
import shlex
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

DIR = pathlib.Path(__file__).parent.parent
BIN_DIR = DIR / "bin"
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))

from _run_channel import read_messages

HARNESS_RUNS = DIR / ".harness_runs.json"
HARNESS_ACTIVE_RUN = DIR / ".harness_active_run.json"
HARNESS_RUN_ROOT = DIR / ".runtime" / "harness"
HARNESS_STATE = DIR / ".harness_state.json"
PROFILES = DIR / ".profiles.json"
CLIENT_BINDINGS = DIR / ".client_bindings.json"
ASSET_ROOT = DIR / "docs" / "assets"
BROKE_BIN = DIR / "bin" / "broke"


def read_json(path, default):
    path = pathlib.Path(path)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def is_loopback(addr):
    return addr in {"127.0.0.1", "::1", "localhost", ""}


def gateway_status(port=4000):
    base = f"http://127.0.0.1:{port}"
    status = {"port": port, "live": False, "ready": False, "health_models": 0, "error": ""}
    try:
        urllib.request.urlopen(f"{base}/health/liveliness", timeout=1.5)
        status["live"] = True
    except Exception as exc:
        status["error"] = str(exc)
        return status
    try:
        urllib.request.urlopen(f"{base}/health/readiness", timeout=1.5)
        status["ready"] = True
    except Exception:
        pass
    try:
        payload = json.loads(urllib.request.urlopen(f"{base}/health", timeout=2).read())
        status["health_models"] = len(payload.get("healthy_endpoints", []))
    except Exception:
        pass
    return status


def recent_events(run_id, limit=12):
    events_file = HARNESS_RUN_ROOT / run_id / "events.jsonl"
    if not events_file.exists():
        return []
    rows = []
    for raw in events_file.read_text().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            rows.append(json.loads(raw))
        except Exception:
            continue
    return rows[-limit:]


def run_state(run_id):
    events = recent_events(run_id)
    run_dir = HARNESS_RUN_ROOT / run_id
    messages = read_messages(run_dir / "channel.jsonl", limit=50)
    session = read_json(run_dir / "state" / "session.json", {})
    return {
        "governor": read_json(run_dir / "state" / "governor.json", {}),
        "intervention": read_json(run_dir / "state" / "intervention.json", {}),
        "session": session,
        "recent_events": events,
        "output_tail": output_tail(run_dir / "artifacts" / "pty-output.log"),
        "provenance": recent_provenance(run_dir, events),
        "control_facts": recent_control_facts(messages, events),
        "machine_messages": messages,
        "acp_summary": summarize_acp(session, messages),
    }


def output_tail(path, limit=5000):
    path = pathlib.Path(path)
    if not path.exists():
        return ""
    try:
        data = path.read_bytes()
    except Exception:
        return ""
    return data[-limit:].decode("utf-8", errors="replace")


def recent_provenance(run_dir, events, limit=3):
    items = []
    seen = set()
    for evt in reversed(events or []):
        for ref in reversed(evt.get("artifact_refs", []) or []):
            path = pathlib.Path(ref)
            if not path.exists() or path in seen:
                continue
            seen.add(path)
            payload = read_json(path, {})
            provenance = payload.get("mutation_provenance")
            if provenance:
                items.append(
                    {
                        "path": str(path),
                        "command_id": payload.get("command_id", ""),
                        "argv": payload.get("argv", []),
                        "mutation_provenance": provenance,
                    }
                )
            if len(items) >= limit:
                return items
    return items


def recent_control_facts(messages, events, limit=6):
    items = []
    for msg in reversed(messages or []):
        if msg.get("channel") != "control":
            continue
        payload = msg.get("payload") or {}
        items.append(
            {
                "msg_seq": msg.get("msg_seq"),
                "timestamp": msg.get("timestamp"),
                "kind": msg.get("kind"),
                "command_id": payload.get("command_id", ""),
                "target": payload.get("target", ""),
                "signal": payload.get("signal", ""),
                "exit_code": payload.get("exit_code", ""),
                "reason": payload.get("reason", ""),
                "supervisor_pid": payload.get("supervisor_pid", ""),
                "child_pid": payload.get("child_pid", ""),
                "child_pgid": payload.get("child_pgid", ""),
                "source": "channel",
            }
        )
        if len(items) >= limit:
            return items
    for evt in reversed(events or []):
        if not str(evt.get("event_type", "")).startswith("session."):
            continue
        payload = evt.get("payload") or {}
        if evt.get("event_type") not in {
            "session.operator_interrupt",
            "session.operator_kill",
            "session.operator_resume",
            "session.interrupted",
            "session.resumed",
            "session.completed",
            "session.operator_ignored",
        }:
            continue
        items.append(
            {
                "event_seq": evt.get("event_seq"),
                "msg_seq": "",
                "timestamp": evt.get("timestamp"),
                "kind": evt.get("event_type"),
                "command_id": payload.get("command_id", ""),
                "target": payload.get("target", ""),
                "signal": payload.get("signal", ""),
                "exit_code": payload.get("exit_code", ""),
                "reason": payload.get("reason", ""),
                "supervisor_pid": payload.get("supervisor_pid", ""),
                "child_pid": payload.get("child_pid", ""),
                "child_pgid": payload.get("child_pgid", ""),
                "source": "events_fallback",
            }
        )
        if len(items) >= limit:
            return items
    return items


def session_is_live(session):
    pid = session.get("child_pid")
    if not pid:
        return False
    try:
        pid = int(pid)
    except Exception:
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def derive_run_status(record, session):
    recorded = str(record.get("status", "") or "").strip() or "unknown"
    session_status = str(session.get("status", "") or "").strip()
    if session_is_live(session):
        return "running"
    if session_status == "completed" or session.get("exit_code") is not None:
        return "completed"
    if recorded == "running":
        return "stale"
    return recorded


def human_run_state(run):
    gov = run.get("governor") or {}
    intervention = run.get("intervention") or {}
    session = run.get("session") or {}
    derived_status = run.get("derived_status") or run.get("status")
    if session.get("transport") == "acp" and session.get("status") == "degraded":
        return {
            "tone": "warn",
            "label": "ACP degraded",
            "summary": session.get("degraded_reason") or "Gemini ACP hit a protocol or upstream reliability problem.",
        }
    if derived_status == "stale":
        return {
            "tone": "",
            "label": "Stale record",
            "summary": "This ledger entry is still marked running, but there is no live supervised session behind it.",
        }
    if derived_status == "failed_launch":
        return {
            "tone": "bad",
            "label": "Failed launch",
            "summary": "The run was registered but no durable session state was established.",
        }
    if gov.get("verification_only_mode"):
        return {
            "tone": "warn",
            "label": "Paused for proof",
            "summary": "BrokeLLM stopped this agent until it runs a real check that passes.",
        }
    if intervention.get("status") == "active":
        return {
            "tone": "bad",
            "label": "Needs attention",
            "summary": intervention.get("notice") or "The harness wants a human or a verification step.",
        }
    if derived_status == "running":
        return {
            "tone": "ok",
            "label": "Running",
            "summary": "The run is active and the harness is not blocking it.",
        }
    return {
        "tone": "",
        "label": derived_status or "Unknown",
        "summary": "This run is not actively doing work.",
    }


def recommended_operator_action(run):
    gov = run.get("governor") or {}
    intervention = run.get("intervention") or {}
    session = run.get("session") or {}
    if session.get("transport") == "acp" and session.get("status") == "degraded":
        return f"Inspect ACP failure: {session.get('degraded_reason') or 'protocol degradation'}"
    if session.get("transport") == "acp" and run.get("is_live") and session.get("last_request_method") == "session/prompt":
        return "Cancel current ACP prompt"
    if session.get("stdin_attached") is False and run.get("is_live"):
        return "Reattach operator input"
    if gov.get("verification_only_mode"):
        return intervention.get("next_action") or "Run a passing verification step"
    if intervention.get("status") == "active":
        return intervention.get("next_action") or "Inspect intervention and decide whether to clear or verify"
    if run.get("derived_status") == "stale":
        return "Reconcile or inspect stale run state"
    if run.get("derived_status") == "failed_launch":
        return "Inspect launch failure evidence"
    if run.get("is_live"):
        return "Monitor"
    return "No immediate action"


def write_json(path, payload):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    try:
        path.chmod(0o600)
    except Exception:
        pass


def override_run_intervention(run_id, action):
    run_dir = HARNESS_RUN_ROOT / run_id
    governor_file = run_dir / "state" / "governor.json"
    intervention_file = run_dir / "state" / "intervention.json"
    governor = read_json(governor_file, {})
    if not governor and action != "force_verify":
        return {"ok": False, "error": "run_state_not_found"}
    if action == "clear":
        governor["verification_required"] = False
        governor["verification_only_mode"] = False
        governor["intervention_reason"] = ""
        governor["intervention_notice"] = ""
        governor["next_action"] = ""
        write_json(governor_file, governor)
        write_json(
            intervention_file,
            {
                "run_id": run_id,
                "command_id": governor.get("last_command_id", ""),
                "status": "resolved",
                "notice": "Operator cleared the intervention.",
                "next_action": "Continue the session carefully.",
            },
        )
        return {"ok": True, "action": action}
    if action == "force_verify":
        governor.setdefault("writes_since_verification", 0)
        governor.setdefault("commands_since_verification", 0)
        governor["verification_required"] = True
        governor["verification_only_mode"] = True
        governor["intervention_reason"] = "operator_forced_verification"
        governor["intervention_notice"] = "Operator requires a verification step before more work."
        governor["next_action"] = "Run a passing test or verification task now."
        write_json(governor_file, governor)
        write_json(
            intervention_file,
            {
                "run_id": run_id,
                "command_id": governor.get("last_command_id", ""),
                "status": "active",
                "reason": "operator_forced_verification",
                "notice": governor["intervention_notice"],
                "next_action": governor["next_action"],
            },
        )
        return {"ok": True, "action": action}
    return {"ok": False, "error": "unknown_action"}


def write_control_action(run_dir, action, session=None, extra=None):
    control_file = run_dir / "state" / "control.json"
    session = session or {}
    payload = {
        "command_id": f"op_{int(time.time() * 1000)}",
        "action": action,
        "requested_at": int(time.time()),
        "expected_child_pid": session.get("child_pid"),
        "expected_supervisor_pid": session.get("supervisor_pid"),
    }
    if extra:
        payload.update(extra)
    write_json(
        control_file,
        payload,
    )


def operator_run_action(run_id, action):
    run_dir = HARNESS_RUN_ROOT / run_id
    session = read_json(run_dir / "state" / "session.json", {})
    is_acp = session.get("transport") == "acp"
    if action in {"force_verify", "clear"}:
        return override_run_intervention(run_id, action)
    if is_acp and action == "cancel_prompt":
        if not session_is_live(session):
            return {"ok": False, "error": "run_session_not_live"}
        write_control_action(
            run_dir,
            "cancel_prompt",
            session=session,
            extra={"expected_session_id": session.get("acp_session_id", "")},
        )
        return {"ok": True, "action": action}
    if is_acp and action == "kill":
        if not session_is_live(session):
            return {"ok": False, "error": "run_session_not_live"}
        try:
            os.kill(int(session.get("child_pid")), signal.SIGTERM)
        except Exception as exc:
            return {"ok": False, "error": f"kill_failed:{exc}"}
        write_control_action(run_dir, "kill", session=session)
        return {"ok": True, "action": action}
    if is_acp and action in {"interrupt", "resume", "reattach"}:
        return {"ok": False, "error": "unsupported_for_acp_transport"}
    if action == "reattach":
        if not session_is_live(session):
            return {"ok": False, "error": "run_session_not_live"}
        write_control_action(run_dir, "reattach", session=session)
        return {"ok": True, "action": action}
    if action == "resume":
        if not session_is_live(session):
            return {"ok": False, "error": "run_session_not_live"}
        result = override_run_intervention(run_id, "clear")
        write_control_action(run_dir, "resume", session=session)
        result["action"] = action
        return result
    if action in {"interrupt", "kill"}:
        if not session_is_live(session):
            return {"ok": False, "error": "run_session_not_live"}
        write_control_action(run_dir, action, session=session)
        return {"ok": True, "action": action}
    return {"ok": False, "error": "unknown_action"}


def reconcile_runs():
    cmd = [sys.executable, str(DIR / "bin" / "_mapping.py"), "harness", "reconcile"]
    try:
        proc = subprocess.run(cmd, cwd=str(DIR), capture_output=True, text=True, check=False)
    except Exception as exc:
        return {"ok": False, "error": f"reconcile_failed:{exc}"}
    if proc.returncode != 0:
        return {"ok": False, "error": (proc.stderr or proc.stdout or "reconcile_failed").strip()}
    try:
        payload = json.loads(proc.stdout or "{}")
    except Exception:
        return {"ok": False, "error": "reconcile_invalid_output"}
    payload["ok"] = True
    return payload


def available_terminal():
    for name in ("alacritty", "kitty", "gnome-terminal", "xterm"):
        path = shutil.which(name)
        if path:
            return name, path
    return None, ""


def spawn_terminal_command(command, title):
    term_name, term_path = available_terminal()
    if not term_path:
        return {"ok": False, "error": "no_terminal_emulator_found"}
    if term_name == "alacritty":
        argv = [term_path, "--title", title, "-e", "/bin/bash", "-lc", command]
    elif term_name == "kitty":
        argv = [term_path, "--title", title, "/bin/bash", "-lc", command]
    elif term_name == "gnome-terminal":
        argv = [term_path, "--title", title, "--", "/bin/bash", "-lc", command]
    else:
        argv = [term_path, "-T", title, "-e", "/bin/bash", "-lc", command]
    try:
        subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except Exception as exc:
        return {"ok": False, "error": f"launch_failed:{exc}"}
    return {"ok": True, "terminal": term_name}


def launch_agent(provider, harness_policy="balanced", sandbox_profile="normal", extra_args=""):
    provider = str(provider or "").strip()
    harness_policy = str(harness_policy or "balanced").strip()
    sandbox_profile = str(sandbox_profile or "normal").strip()
    extra_args = str(extra_args or "").strip()
    if provider not in {"claude", "codex", "gemini", "gemini-acp"}:
        return {"ok": False, "error": "invalid_provider"}
    if harness_policy not in {"off", "throughput", "balanced", "high_assurance"}:
        return {"ok": False, "error": "invalid_harness_policy"}
    if sandbox_profile not in {"normal", "hardened", "strict"}:
        return {"ok": False, "error": "invalid_sandbox_profile"}
    try:
        parsed_args = shlex.split(extra_args) if extra_args else []
    except ValueError as exc:
        return {"ok": False, "error": f"invalid_args:{exc}"}
    launch_verb = "gemini-acp" if provider == "gemini-acp" else "launch"
    launch_target = [] if provider == "gemini-acp" else [provider]
    if harness_policy == "off":
        cmd = [str(BROKE_BIN), "sandbox", "set", sandbox_profile, "&&", str(BROKE_BIN), launch_verb, *launch_target, *parsed_args]
        title = f"BrokeLLM {provider}"
    else:
        cmd = [
            str(BROKE_BIN),
            "sandbox",
            "set",
            sandbox_profile,
            "&&",
            str(BROKE_BIN),
            "harness",
            "run",
            "--provider",
            "gemini" if provider == "gemini-acp" else provider,
            "--policy",
            harness_policy,
            "--sandbox",
            sandbox_profile,
            "--",
            *([] if provider != "gemini-acp" else ["python3", str(DIR / "bin" / "_gemini_acp.py")]),
            *parsed_args,
        ]
        title = f"BrokeLLM {provider} [{harness_policy}]"
    return spawn_terminal_command(shlex.join(cmd), title)


def summarize_acp(session, messages):
    if (session or {}).get("transport") != "acp":
        return {}
    relevant = [msg for msg in (messages or []) if str(msg.get("kind", "")).startswith("acp.")]
    capabilities = dict((session or {}).get("capabilities") or {})
    quarantine_count = int((session or {}).get("quarantine_count") or len((session or {}).get("quarantined_results") or []))
    return {
        "session_id": session.get("acp_session_id", ""),
        "initialized": bool(session.get("initialized")),
        "degraded_reason": session.get("degraded_reason", ""),
        "last_request_method": session.get("last_request_method", ""),
        "last_notification_kind": session.get("last_notification_kind", ""),
        "message_count": len(relevant),
        "failure_count": session.get("failure_count", 0),
        "cancel_supported": bool(session.get("cancel_supported")),
        "active_prompt": session.get("active_prompt", {}),
        "quarantine_count": quarantine_count,
        "late_result_policy": capabilities.get("late_result_policy", session.get("late_result_policy", "")),
        "supports_transport_cancel": bool(capabilities.get("supports_transport_cancel")),
        "supports_live_interrupt": bool(capabilities.get("supports_live_interrupt")),
        "supports_native_session_resume": bool(capabilities.get("supports_native_session_resume")),
        "supports_tool_roundtrip": bool(capabilities.get("supports_tool_roundtrip")),
        "cancel_kind": capabilities.get("cancel_kind", session.get("cancel_kind", "")),
    }


def harness_runs_snapshot(limit=20):
    runs = read_json(HARNESS_RUNS, {"runs": {}}).get("runs", {})
    active = read_json(HARNESS_ACTIVE_RUN, {})
    ordered = sorted(runs.values(), key=lambda item: item.get("created_at", ""), reverse=True)
    out = []
    for record in ordered[:limit]:
        run_id = record.get("run_id", "")
        state = run_state(run_id) if run_id else {"governor": {}, "intervention": {}, "recent_events": []}
        session = dict(state["session"] or {})
        if record.get("transport") == "acp" or record.get("acp_session_id"):
            session.setdefault("transport", "acp")
            session.setdefault("child_pid", record.get("acp_pid"))
            session.setdefault("acp_pid", record.get("acp_pid"))
            session.setdefault("acp_session_id", record.get("acp_session_id", ""))
            session.setdefault("initialized", record.get("acp_initialized", False))
            session.setdefault("status", record.get("acp_status", session.get("status", "")))
            session.setdefault("degraded_reason", record.get("acp_degraded_reason", ""))
            session.setdefault("last_request_method", record.get("acp_last_request_method", ""))
            session.setdefault("last_notification_kind", record.get("acp_last_notification_kind", ""))
            session.setdefault("failure_count", record.get("acp_failure_count", 0))
            session.setdefault("cancel_supported", record.get("acp_cancel_supported", False))
            session.setdefault("quarantine_count", record.get("acp_quarantine_count", 0))
            session.setdefault("late_result_policy", record.get("acp_late_result_policy", ""))
        enriched = dict(record)
        enriched["is_active"] = active.get("run_id") == run_id
        enriched["governor"] = state["governor"]
        enriched["intervention"] = state["intervention"]
        enriched["session"] = session
        enriched["recent_events"] = state["recent_events"]
        enriched["output_tail"] = state["output_tail"]
        enriched["provenance"] = state["provenance"]
        enriched["control_facts"] = state["control_facts"]
        enriched["machine_messages"] = state["machine_messages"]
        enriched["acp_summary"] = summarize_acp(session, state["machine_messages"])
        enriched["is_live"] = session_is_live(session)
        enriched["derived_status"] = derive_run_status(record, session)
        enriched["recommended_action"] = recommended_operator_action(enriched)
        out.append(enriched)
    return {"active": active, "runs": out}


def collect_snapshot(port=4000):
    profiles = read_json(PROFILES, {})
    bindings = read_json(CLIENT_BINDINGS, {"tokens": {}})
    harness_state = read_json(HARNESS_STATE, {})
    harness = harness_runs_snapshot()
    recent = harness["runs"][:6]
    lane_state = harness_state.get("lanes", {})
    checklist = harness_state.get("checklist", {"items": []})
    last_verdict = harness_state.get("last_verdict") or {}
    return {
        "timestamp": int(time.time()),
        "gateway": gateway_status(port=port),
        "harness": harness,
        "review_lanes": lane_state,
        "checklist": checklist,
        "last_verdict": last_verdict,
        "summary": {
            "active_runs": sum(1 for run in harness["runs"] if run.get("is_live")),
            "blocked_runs": sum(1 for run in harness["runs"] if (run.get("governor") or {}).get("verification_only_mode")),
            "attention_runs": sum(1 for run in harness["runs"] if (run.get("intervention") or {}).get("status") == "active"),
            "degraded_review_lanes": sum(1 for lane in lane_state.values() if (lane or {}).get("health") in {"degraded", "failed"}),
            "implemented_checklist_items": sum(1 for item in checklist.get("items", []) if item.get("implemented")),
            "total_checklist_items": len(checklist.get("items", [])),
            "last_verdict": last_verdict.get("verdict", ""),
            "last_verdict_categories": len(last_verdict.get("categories", []) or []),
            "recent_states": [human_run_state(run) for run in recent],
            "banner": system_banner(gateway_status(port=port), harness["runs"]),
        },
        "profiles": {
            "count": len(profiles),
            "names": sorted(profiles.keys()),
        },
        "client_tokens": {
            "count": len(bindings.get("tokens", {})),
        },
    }


def system_banner(gateway, runs):
    if not gateway.get("live"):
        return {"tone": "bad", "label": "Gateway offline", "summary": "The router is not responding. Client traffic and run mediation are at risk."}
    blocked = [run for run in runs if (run.get("governor") or {}).get("verification_only_mode")]
    if blocked:
        return {"tone": "warn", "label": "Operator attention required", "summary": f"{len(blocked)} run(s) are blocked pending verification or intervention."}
    active = [run for run in runs if run.get("is_live")]
    if active:
        return {"tone": "ok", "label": "System online", "summary": f"{len(active)} active run(s). Gateway and harness are currently operational."}
    return {"tone": "", "label": "System idle", "summary": "Gateway is available. No active harness runs are currently doing work."}


HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>BrokeLLM Dashboard</title>
  <style>
    :root { color-scheme: dark; --bg:#040404; --bg2:#0b0b0d; --panel:#0d0d10; --panel2:#121217; --panel3:#18181e; --ink:#f7f7f8; --muted:#b7b7c0; --accent:#8f0f1f; --accent2:#c1122f; --line:#2c2d33; --ok:#8ce0ba; --warn:#f0b45c; --bad:#ff6f7d; --white:#ffffff; }
    * { box-sizing:border-box; }
    body { margin:0; font-family: "Avenir Next", "Segoe UI", sans-serif; background:radial-gradient(circle at top, rgba(143,15,31,.18) 0%, #070708 18%, var(--bg) 52%, #020202 100%); color:var(--ink); }
    header { padding:24px; border-bottom:1px solid rgba(193,18,47,.22); background:linear-gradient(180deg, rgba(11,11,13,.96), rgba(4,4,4,.94)); position:sticky; top:0; backdrop-filter: blur(8px); z-index:3; }
    h1 { margin:0; font-size:30px; letter-spacing:.08em; text-transform:uppercase; }
    .sub { color:var(--muted); margin-top:6px; line-height:1.5; }
    main { padding:24px; display:grid; grid-template-columns: 380px 1fr; gap:20px; }
    .panel { background:linear-gradient(180deg, rgba(18,18,23,.96), rgba(10,10,12,.98)); border:1px solid rgba(193,18,47,.18); border-radius:18px; padding:18px; box-shadow:0 18px 48px rgba(0,0,0,.34); }
    .panel h2 { margin:0 0 14px; font-size:13px; letter-spacing:.18em; text-transform:uppercase; color:var(--white); }
    .metric { display:flex; justify-content:space-between; gap:12px; padding:9px 0; border-bottom:1px solid rgba(255,255,255,.06); }
    .metric:last-child { border-bottom:0; }
    .run { margin-bottom:14px; padding:18px; border:1px solid rgba(255,255,255,.08); border-radius:16px; background:linear-gradient(180deg, rgba(18,18,23,.96), rgba(8,8,10,.98)); }
    .run.active { border-color:rgba(193,18,47,.72); box-shadow:0 0 0 1px rgba(193,18,47,.18), inset 0 0 42px rgba(143,15,31,.08); }
    .badge { display:inline-block; font-size:11px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; padding:4px 8px; border-radius:999px; background:#1b1b22; color:#ececf0; margin-right:6px; margin-bottom:6px; border:1px solid rgba(255,255,255,.06); }
    .status-pill { display:inline-flex; align-items:center; gap:8px; border-radius:999px; padding:6px 10px; font-size:12px; font-weight:800; letter-spacing:.08em; text-transform:uppercase; background:#16161c; border:1px solid rgba(255,255,255,.08); }
    .ok { color:var(--ok); } .warn { color:var(--warn); } .bad { color:var(--bad); }
    .lead { font-size:15px; line-height:1.6; color:#f0f0f3; margin-bottom:12px; }
    pre { white-space:pre-wrap; word-break:break-word; font-size:12px; color:#e3e4e8; background:#09090c; padding:10px; border-radius:10px; border:1px solid rgba(255,255,255,.08); }
    .events { max-height:220px; overflow:auto; }
    .actions { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
    button { appearance:none; border:1px solid rgba(255,255,255,.08); border-radius:10px; padding:10px 12px; background:linear-gradient(180deg, var(--accent2), var(--accent)); color:white; font-weight:800; letter-spacing:.02em; cursor:pointer; }
    button.secondary { background:linear-gradient(180deg, #1d1d24, #111116); color:#f4f5f8; }
    button.ghost { background:transparent; color:#f4f5f8; border-color:rgba(255,255,255,.12); }
    button:disabled { opacity:.55; cursor:not-allowed; }
    .explain { color:var(--muted); font-size:13px; line-height:1.45; margin:10px 0 0; }
    .cards { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:14px; }
    .mini { background:linear-gradient(180deg, rgba(24,24,30,.88), rgba(12,12,16,.88)); border:1px solid rgba(255,255,255,.08); border-radius:14px; padding:12px; }
    .mini strong { display:block; font-size:22px; margin-top:4px; }
    .hero { position:relative; min-height:220px; overflow:hidden; padding:28px; margin-bottom:20px; border-radius:22px; border:1px solid rgba(193,18,47,.28); background:linear-gradient(135deg, rgba(4,4,4,.96), rgba(13,13,16,.82)); box-shadow:0 20px 60px rgba(0,0,0,.4); }
    .hero:before { content:""; position:absolute; inset:0; background-image:linear-gradient(90deg, rgba(4,4,4,.96), rgba(4,4,4,.72), rgba(4,4,4,.38)), url('/assets/brokellm-live-operations.png'); background-size:cover; background-position:center; filter:saturate(.55) contrast(1.08) brightness(.72); }
    .hero > * { position:relative; z-index:1; }
    .hero h2 { margin:0 0 10px; font-size:36px; line-height:1.03; max-width:760px; color:var(--white); }
    .hero p { max-width:720px; margin:0; color:#e9e9ee; line-height:1.6; }
    .banner { margin-top:16px; padding:14px 16px; border-radius:14px; background:rgba(10,10,12,.78); border:1px solid rgba(255,255,255,.08); max-width:760px; }
    .banner strong { display:block; font-size:14px; letter-spacing:.08em; text-transform:uppercase; margin-bottom:6px; }
    .glossary { display:grid; gap:10px; margin-top:12px; }
    .term { padding:12px; border-radius:14px; border:1px solid rgba(255,255,255,.06); background:linear-gradient(180deg, rgba(24,24,30,.74), rgba(12,12,16,.74)); }
    .term strong { display:block; color:var(--white); margin-bottom:4px; }
    .eyebrow { display:inline-block; margin-bottom:10px; padding:5px 9px; border-radius:999px; border:1px solid rgba(255,255,255,.1); background:rgba(143,15,31,.28); color:#fff; font-size:11px; font-weight:800; letter-spacing:.12em; text-transform:uppercase; }
    .command { margin-top:12px; color:#d6d6dc; font-size:13px; }
    .section-title { display:flex; justify-content:space-between; align-items:center; gap:12px; }
    .toolbar { display:flex; gap:8px; flex-wrap:wrap; }
    .workspace { display:grid; grid-template-columns: 320px 1fr; gap:16px; min-height:720px; }
    .run-list { display:grid; gap:10px; align-content:start; max-height:980px; overflow:auto; padding-right:4px; }
    .run-item { padding:14px; border-radius:14px; border:1px solid rgba(255,255,255,.08); background:linear-gradient(180deg, rgba(18,18,23,.96), rgba(8,8,10,.98)); cursor:pointer; }
    .run-item.selected { border-color:rgba(193,18,47,.72); box-shadow:0 0 0 1px rgba(193,18,47,.18), inset 0 0 30px rgba(143,15,31,.08); }
    .detail { min-height:720px; }
    .detail-empty { height:100%; display:grid; place-items:center; color:var(--muted); border:1px dashed rgba(255,255,255,.12); border-radius:16px; }
    .filters { display:flex; flex-wrap:wrap; gap:8px; }
    .chip { padding:8px 10px; border-radius:999px; border:1px solid rgba(255,255,255,.08); background:#141419; color:#f3f4f7; cursor:pointer; font-size:12px; font-weight:800; letter-spacing:.06em; text-transform:uppercase; }
    .chip.active { border-color:rgba(193,18,47,.7); background:rgba(143,15,31,.26); }
    .field-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
    .field { display:grid; gap:6px; margin-bottom:10px; }
    .field label { font-size:12px; color:#d9dae0; letter-spacing:.06em; text-transform:uppercase; font-weight:700; }
    input, select { width:100%; border-radius:10px; border:1px solid rgba(255,255,255,.1); background:#09090c; color:#f7f7f8; padding:11px 12px; font:inherit; }
    .launch-actions { display:flex; gap:8px; flex-wrap:wrap; }
    .launch-status { margin-top:10px; color:#d9dae0; min-height:20px; }
    @media (max-width: 1240px) { main { grid-template-columns: 1fr; } .workspace { grid-template-columns:1fr; } }
    @media (max-width: 760px) { .cards { grid-template-columns:1fr; } .hero h2 { font-size:26px; } }
  </style>
</head>
<body>
  <header>
    <h1>BrokeLLM Dashboard</h1>
    <div class="sub" id="stamp">Connecting...</div>
  </header>
  <div style="padding:24px 24px 0;">
    <section class="hero">
      <div class="eyebrow">Operator Console</div>
      <h2>Control active runs, inspect harness state, and force verification when an agent starts drifting.</h2>
      <p>BrokeLLM is acting as the runtime boundary here. This dashboard is the control surface: health, run state, intervention status, and operator actions in one place.</p>
      <div class="command">Launch with <strong>`broke dashboard`</strong>. Runs update live.</div>
      <div class="banner" id="banner"></div>
    </section>
  </div>
  <main>
    <section class="panel">
      <h2>System Status</h2>
      <div id="overview"></div>
      <div style="height:16px;"></div>
      <h2>Launch Agent</h2>
      <div class="field-grid">
        <div class="field">
          <label for="launch-provider">Provider</label>
          <select id="launch-provider">
            <option value="claude">Claude</option>
            <option value="codex">Codex</option>
            <option value="gemini">Gemini</option>
            <option value="gemini-acp">Gemini ACP</option>
          </select>
        </div>
        <div class="field">
          <label for="launch-harness">Harness</label>
          <select id="launch-harness">
            <option value="balanced">Balanced</option>
            <option value="throughput">Throughput</option>
            <option value="high_assurance">High Assurance</option>
            <option value="off">Off</option>
          </select>
        </div>
      </div>
      <div class="field-grid">
        <div class="field">
          <label for="launch-sandbox">Sandbox</label>
          <select id="launch-sandbox">
            <option value="normal">Normal</option>
            <option value="hardened">Hardened</option>
            <option value="strict">Strict</option>
          </select>
        </div>
        <div class="field">
          <label for="launch-args">Extra Args</label>
          <input id="launch-args" placeholder="Optional CLI args" />
        </div>
      </div>
      <div class="launch-actions">
        <button onclick="launchAgent()">Launch Session</button>
        <button class="ghost" onclick="reconcileRuns()">Reconcile Stale Runs</button>
      </div>
      <div class="launch-status" id="launch-status"></div>
      <div class="glossary">
        <div class="term">
          <strong>Paused for proof</strong>
          The harness is blocking further edits until this run passes a real verification step.
        </div>
        <div class="term">
          <strong>Needs attention</strong>
          The run hit a policy condition that needs human review or a verification pass.
        </div>
        <div class="term">
          <strong>Running</strong>
          The run is active and not currently blocked by the harness.
        </div>
      </div>
    </section>
    <section class="panel">
      <div class="section-title">
        <h2 style="margin:0;">Runs And Controls</h2>
        <div class="filters" id="filters"></div>
      </div>
      <div class="workspace">
        <div class="run-list" id="run-list"></div>
        <div class="detail" id="run-detail"></div>
      </div>
    </section>
  </main>
  <script>
    let selectedRunId = null;
    let currentFilter = 'all';
    function esc(v){ return String(v ?? "").replace(/[&<>]/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[s])); }
    async function act(runId, action){
      const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/action`, {
        method:'POST',
        headers:{'content-type':'application/json'},
        body: JSON.stringify({action})
      });
      const payload = await res.json();
      if(!payload.ok){ alert(payload.error || 'Action failed'); }
    }
    async function launchAgent(){
      const provider = document.getElementById('launch-provider').value;
      const harness = document.getElementById('launch-harness').value;
      const sandbox = document.getElementById('launch-sandbox').value;
      const args = document.getElementById('launch-args').value;
      const res = await fetch('/api/launch', {
        method:'POST',
        headers:{'content-type':'application/json'},
        body: JSON.stringify({provider, harness_policy: harness, sandbox_profile: sandbox, args})
      });
      const payload = await res.json();
      const el = document.getElementById('launch-status');
      if(payload.ok){
        el.innerHTML = `<span class="ok">Launch requested.</span> Opened in ${esc(payload.terminal || 'terminal')} for ${esc(provider)}.`;
      } else {
        el.innerHTML = `<span class="bad">Launch failed.</span> ${esc(payload.error || 'unknown error')}`;
      }
    }
    async function reconcileRuns(){
      const res = await fetch('/api/reconcile', {method:'POST'});
      const payload = await res.json();
      const el = document.getElementById('launch-status');
      if(payload.ok){
        const count = (payload.changed || []).length;
        el.innerHTML = `<span class="ok">Reconciled ${count} stale run(s).</span>`;
      } else {
        el.innerHTML = `<span class="bad">Reconcile failed.</span> ${esc(payload.error || 'unknown error')}`;
      }
    }
    function runMatchesFilter(run){
      const gov = run.governor || {};
      const intervention = run.intervention || {};
      if(currentFilter === 'all') return true;
      if(currentFilter === 'active') return !!run.is_live;
      if(currentFilter === 'blocked') return !!gov.verification_only_mode;
      if(currentFilter === 'attention') return intervention.status === 'active';
      if(currentFilter === 'stale') return run.derived_status === 'stale';
      if(currentFilter === 'claude' || currentFilter === 'codex' || currentFilter === 'gemini') return run.provider === currentFilter;
      if(currentFilter === 'gemini-acp') return (run.session || {}).transport === 'acp';
      return true;
    }
    function renderFilters(runs){
      const counts = {
        all: runs.length,
        active: runs.filter(r => r.is_live).length,
        blocked: runs.filter(r => (r.governor || {}).verification_only_mode).length,
        attention: runs.filter(r => (r.intervention || {}).status === 'active').length,
        stale: runs.filter(r => r.derived_status === 'stale').length,
        claude: runs.filter(r => r.provider === 'claude').length,
        codex: runs.filter(r => r.provider === 'codex').length,
        gemini: runs.filter(r => r.provider === 'gemini').length,
        'gemini-acp': runs.filter(r => (r.session || {}).transport === 'acp').length
      };
      const items = [
        ['all','All'],
        ['active','Active'],
        ['blocked','Blocked'],
        ['attention','Attention'],
        ['stale','Stale'],
        ['claude','Claude'],
        ['codex','Codex'],
        ['gemini','Gemini'],
        ['gemini-acp','Gemini ACP']
      ];
      document.getElementById('filters').innerHTML = items.map(([key,label]) =>
        `<button class="chip ${currentFilter === key ? 'active' : ''}" onclick="setFilter('${key}')">${label} ${counts[key] ?? 0}</button>`
      ).join('');
    }
    function setFilter(value){
      currentFilter = value;
      window.__lastData && render(window.__lastData);
    }
    function selectRun(runId){
      selectedRunId = runId;
      window.__lastData && render(window.__lastData);
    }
    function renderRunList(runs){
      const filtered = runs.filter(runMatchesFilter);
      if(filtered.length && !filtered.some(r => r.run_id === selectedRunId)){
        selectedRunId = filtered[0].run_id;
      }
      if(!filtered.length){
        selectedRunId = null;
      }
      document.getElementById('run-list').innerHTML = filtered.length ? filtered.map(run => {
        const gov = run.governor || {};
        const intervention = run.intervention || {};
        const tone = gov.verification_only_mode ? 'warn' : (intervention.status === 'active' ? 'bad' : (run.is_live ? 'ok' : ''));
        const label = gov.verification_only_mode ? 'Paused for proof' : (intervention.status === 'active' ? 'Needs attention' : (run.is_live ? 'Running' : (run.derived_status || run.status || 'Unknown')));
        return `
          <div class="run-item ${selectedRunId === run.run_id ? 'selected' : ''}" onclick="selectRun('${esc(run.run_id)}')">
            <div style="display:flex; justify-content:space-between; gap:10px; align-items:flex-start;">
              <strong>${esc(run.run_id)}</strong>
              <span class="status-pill ${tone}">${esc(label)}</span>
            </div>
            <div class="sub">Provider: ${esc(run.provider)}${(run.session || {}).transport === 'acp' ? ' · ACP' : ''} · Policy: ${esc(run.policy_profile)}</div>
            <div class="sub">Session: ${esc((run.session || {}).status || run.derived_status || run.status || 'unknown')}</div>
            <div class="sub">Next: ${esc(run.recommended_action || 'Monitor')}</div>
          </div>
        `;
      }).join('') : '<div class="detail-empty">No runs match the current filter.</div>';
      return filtered;
    }
    function renderRunDetail(run){
      if(!run){
        document.getElementById('run-detail').innerHTML = '<div class="detail-empty">Select a run to inspect details and operate it.</div>';
        return;
      }
      const intervention = run.intervention || {};
      const gov = run.governor || {};
      const session = run.session || {};
      const provenance = run.provenance || [];
      const controlFacts = run.control_facts || [];
      const machineMessages = run.machine_messages || [];
      const acp = run.acp_summary || {};
      const isAcp = session.transport === 'acp';
      const activeIntervention = intervention.status === 'active';
      const state = gov.verification_only_mode ? { tone: 'warn', label: 'Paused for proof', summary: 'Further edits are blocked until this run passes verification.' }
        : activeIntervention ? { tone: 'bad', label: 'Needs attention', summary: intervention.notice || 'This run needs review or verification.' }
        : run.is_live ? { tone: 'ok', label: 'Running', summary: 'The run is active and currently clear to continue.' }
        : run.derived_status === 'stale' ? { tone: '', label: 'Stale record', summary: 'The ledger still says this run was open, but there is no live supervised session attached to it now.' }
        : { tone: '', label: run.derived_status || run.status || 'Unknown', summary: 'This run is not currently active.' };
      const events = (run.recent_events || []).map(evt => `${evt.timestamp}  ${evt.event_type}`).join("\\n");
      document.getElementById('run-detail').innerHTML = `
        <div class="run ${run.is_active ? 'active' : ''}">
          <div style="display:flex; justify-content:space-between; gap:12px; align-items:flex-start;">
            <div>
              <strong style="font-size:20px;">${esc(run.run_id)}</strong>
              ${run.is_active ? '<span class="badge">active now</span>' : ''}
            </div>
            <div class="status-pill ${state.tone}">${esc(state.label)}</div>
          </div>
          <div class="lead" style="margin-top:12px;">${esc(state.summary)}</div>
          <div class="warn" style="margin-top:10px; margin-bottom:10px;"><strong>Recommended operator action:</strong> ${esc(run.recommended_action || 'Monitor')}</div>
          <div class="metric"><span>Provider</span><strong>${esc(run.provider)}</strong></div>
          <div class="metric"><span>Transport</span><strong>${esc(session.transport || 'pty')}</strong></div>
          <div class="metric"><span>Harness policy</span><strong>${esc(run.policy_profile || '-')}</strong></div>
          <div class="metric"><span>Worker route</span><strong>${esc(run.worker_route || '-')}</strong></div>
          <div class="metric"><span>Sandbox</span><strong>${esc(run.sandbox_profile || '-')}</strong></div>
          <div class="metric"><span>Session status</span><strong>${esc(session.status || run.derived_status || run.status || 'unknown')}</strong></div>
          <div class="metric"><span>Live session</span><strong>${run.is_live ? 'Yes' : 'No'}</strong></div>
          <div class="metric"><span>Child PID</span><strong>${esc(session.child_pid || '-')}</strong></div>
          <div class="metric"><span>Child PGID</span><strong>${esc(session.child_pgid || '-')}</strong></div>
          <div class="metric"><span>Supervisor PID</span><strong>${esc(session.supervisor_pid || '-')}</strong></div>
          <div class="metric"><span>Child SID</span><strong>${esc(session.child_sid || '-')}</strong></div>
          <div class="metric"><span>Foreground PGID</span><strong>${esc(session.foreground_pgid || '-')}</strong></div>
          <div class="metric"><span>Input attached</span><strong>${session.stdin_attached === false ? 'No' : 'Yes'}</strong></div>
          <div class="metric"><span>Window size</span><strong>${session.winsize && session.winsize.rows ? `${session.winsize.rows}x${session.winsize.cols}` : '-'}</strong></div>
          ${session.transport === 'acp' ? `<div class="metric"><span>ACP session</span><strong>${esc(session.acp_session_id || '-')}</strong></div>` : ''}
          ${session.transport === 'acp' ? `<div class="metric"><span>ACP health</span><strong class="${session.status === 'degraded' ? 'warn' : 'ok'}">${esc(session.status || '-')}</strong></div>` : ''}
          ${session.transport === 'acp' ? `<div class="metric"><span>Degraded reason</span><strong>${esc(session.degraded_reason || '-')}</strong></div>` : ''}
          ${session.transport === 'acp' ? `<div class="metric"><span>ACP failures</span><strong>${esc(acp.failure_count || 0)}</strong></div>` : ''}
          ${session.transport === 'acp' ? `<div class="metric"><span>Quarantined late results</span><strong>${esc(acp.quarantine_count || 0)}</strong></div>` : ''}
          ${session.transport === 'acp' ? `<div class="metric"><span>Cancel kind</span><strong>${esc(acp.cancel_kind || '-')}</strong></div>` : ''}
          <div class="metric"><span>Writes since verification</span><strong>${gov.writes_since_verification ?? 0}</strong></div>
          <div class="metric"><span>Total commands since verification</span><strong>${gov.commands_since_verification ?? 0}</strong></div>
          <div style="margin:12px 0 10px;">
            <span class="badge">${esc(run.provider || '')}</span>
            <span class="badge">${esc(run.worker_route || '')}</span>
            <span class="badge">${esc(run.sandbox_profile || '')}</span>
            ${gov.verification_only_mode ? '<span class="badge bad">verification-only</span>' : '<span class="badge">normal work allowed</span>'}
          </div>
          ${intervention.notice ? `<div class="${activeIntervention ? 'bad':'ok'}" style="margin-bottom:8px;"><strong>${activeIntervention ? 'Intervention' : 'Resolved'}:</strong> ${esc(intervention.notice)}</div>` : '<div class="ok" style="margin-bottom:8px;"><strong>No active intervention.</strong> Harness is not blocking this run.</div>'}
          ${intervention.next_action ? `<div class="warn" style="margin-bottom:8px;"><strong>Required next step:</strong> ${esc(intervention.next_action)}</div>` : ''}
          <div class="actions">
            ${isAcp ? `<button class="secondary" ${run.is_live ? '' : 'disabled'} onclick="act('${esc(run.run_id)}','cancel_prompt')">Cancel Prompt</button>` : `<button class="secondary" onclick="act('${esc(run.run_id)}','interrupt')">Interrupt</button>
            <button class="secondary" onclick="act('${esc(run.run_id)}','resume')">Resume</button>
            <button class="secondary" onclick="act('${esc(run.run_id)}','reattach')">Reattach</button>`}
            <button class="secondary" onclick="act('${esc(run.run_id)}','kill')">Kill</button>
            <button class="secondary" onclick="act('${esc(run.run_id)}','force_verify')">Require verification now</button>
            <button ${activeIntervention ? '' : 'disabled'} onclick="act('${esc(run.run_id)}','clear')">Operator clear</button>
          </div>
          <div class="explain">${isAcp ? '<strong>Cancel Prompt</strong> asks Gemini ACP to cancel the active session prompt without throwing away session identity. <strong>Kill</strong> terminates the ACP process if it is still live.' : '<strong>Interrupt</strong> sends a stop signal to the run. <strong>Resume</strong> clears the current intervention and reopens the session. <strong>Kill</strong> terminates the supervised child process.'}</div>
          <div style="margin-top:14px;"><strong>Live output</strong></div>
          <div class="events" style="margin-top:8px;"><pre>${esc(run.output_tail || 'No PTY output captured yet')}</pre></div>
          <div style="margin-top:14px;"><strong>Mutation provenance</strong></div>
          <div class="events" style="margin-top:8px;"><pre>${esc(provenance.length ? provenance.map(item => {
            const mp = item.mutation_provenance || {};
            return [
              `command: ${item.command_id}`,
              `argv: ${(item.argv || []).join(' ')}`,
              `created: ${(mp.created || []).map(x => x.path).join(', ') || '-'}`,
              `modified: ${(mp.modified || []).map(x => x.path).join(', ') || '-'}`,
              `deleted: ${(mp.deleted || []).map(x => x.path).join(', ') || '-'}`,
              `artifact: ${item.path}`
            ].join('\\n');
          }).join('\\n\\n') : 'No mutation provenance artifacts captured yet')}</pre></div>
          <div style="margin-top:14px;"><strong>Control facts</strong></div>
          <div class="events" style="margin-top:8px;"><pre>${esc(controlFacts.length ? controlFacts.map(item => {
            return [
              `seq: ${item.msg_seq || item.event_seq || '-'}`,
              `time: ${item.timestamp || '-'}`,
              `kind: ${item.kind || '-'}`,
              `command: ${item.command_id || '-'}`,
              `target: ${item.target || '-'}`,
              `signal: ${item.signal || '-'}`,
              `exit: ${item.exit_code || '-'}`,
              `reason: ${item.reason || '-'}`,
              `source: ${item.source || '-'}`,
              `supervisor: ${item.supervisor_pid || '-'}`,
              `child: ${item.child_pid || '-'}`,
              `pgid: ${item.child_pgid || '-'}`
            ].join('\\n');
          }).join('\\n\\n') : 'No control events captured yet')}</pre></div>
          <div style="margin-top:14px;"><strong>Machine message channel</strong></div>
          <div class="events" style="margin-top:8px;"><pre>${esc(machineMessages.length ? machineMessages.map(item => {
            return [
              `seq: ${item.msg_seq || '-'}`,
              `channel: ${item.channel || '-'}`,
              `kind: ${item.kind || '-'}`,
              `time: ${item.timestamp || '-'}`,
              `payload: ${JSON.stringify(item.payload || {})}`
            ].join('\\n');
          }).join('\\n\\n') : 'No structured machine messages captured yet')}</pre></div>
          ${session.transport === 'acp' ? `<div style="margin-top:14px;"><strong>ACP summary</strong></div>
          <div class="events" style="margin-top:8px;"><pre>${esc([
            `initialized: ${acp.initialized ? 'yes' : 'no'}`,
            `session_id: ${acp.session_id || '-'}`,
            `last_request: ${acp.last_request_method || '-'}`,
            `last_notification: ${acp.last_notification_kind || '-'}`,
            `message_count: ${acp.message_count || 0}`,
            `failure_count: ${acp.failure_count || 0}`,
            `quarantine_count: ${acp.quarantine_count || 0}`,
            `cancel_supported: ${acp.cancel_supported ? 'yes' : 'no'}`,
            `supports_transport_cancel: ${acp.supports_transport_cancel ? 'yes' : 'no'}`,
            `supports_live_interrupt: ${acp.supports_live_interrupt ? 'yes' : 'no'}`,
            `supports_native_session_resume: ${acp.supports_native_session_resume ? 'yes' : 'no'}`,
            `supports_tool_roundtrip: ${acp.supports_tool_roundtrip ? 'yes' : 'no'}`,
            `cancel_kind: ${acp.cancel_kind || '-'}`,
            `late_result_policy: ${acp.late_result_policy || '-'}`,
            `active_prompt: ${(acp.active_prompt || {}).session_id || '-'}`,
            `degraded_reason: ${acp.degraded_reason || '-'}`
          ].join('\\n'))}</pre></div>` : ''}
          <div style="margin-top:14px;"><strong>Event ledger</strong></div>
          <div class="events" style="margin-top:8px;"><pre>${esc(events || 'No events yet')}</pre></div>
        </div>
      `;
    }
    function render(data){
      window.__lastData = data;
      document.getElementById('stamp').textContent = "Updated " + new Date(data.timestamp * 1000).toLocaleTimeString();
      const g = data.gateway || {};
      const s = data.summary || {};
      const reviewLanes = data.review_lanes || {};
      const lastVerdict = data.last_verdict || {};
      const checklist = (data.checklist || {}).items || [];
      const banner = s.banner || {label:'', summary:'', tone:''};
      const laneSummary = Object.entries(reviewLanes).map(([name, lane]) => `${name}:${(lane || {}).health || 'healthy'}`).join(' · ') || 'none';
      const checklistSummary = checklist.length ? checklist.map(item => `${item.implemented ? '✓' : ' '} ${item.label || item.id}`).join('\n') : 'No checklist loaded';
      const contributionSummary = Object.entries(lastVerdict.verdict_contributions || {}).map(([name, item]) =>
        `${name}: ${item.recommended_verdict || '-'} · ${item.lane_health || 'healthy'} · ${item.source || 'missing'}`
      ).join('\n') || 'No lane contributions recorded';
      document.getElementById('banner').innerHTML = `<strong class="${banner.tone}">${esc(banner.label)}</strong><div>${esc(banner.summary)}</div>`;
      const states = s.recent_states || [];
      const topState = states.length ? states[0] : {label:'Idle', summary:'No harness runs have been recorded yet.', tone:''};
      document.getElementById('overview').innerHTML = `
        <div class="lead"><strong class="${topState.tone}">${esc(topState.label)}</strong> ${esc(topState.summary)}</div>
        <div class="cards">
          <div class="mini"><div class="sub">Active runs</div><strong>${s.active_runs ?? 0}</strong></div>
          <div class="mini"><div class="sub">Attention required</div><strong class="${(s.attention_runs ?? 0) ? 'bad':''}">${s.attention_runs ?? 0}</strong></div>
          <div class="mini"><div class="sub">Verification locked</div><strong class="${(s.blocked_runs ?? 0) ? 'warn':''}">${s.blocked_runs ?? 0}</strong></div>
          <div class="mini"><div class="sub">Lane degraded</div><strong class="${(s.degraded_review_lanes ?? 0) ? 'warn':''}">${s.degraded_review_lanes ?? 0}</strong></div>
          <div class="mini"><div class="sub">Checklist</div><strong>${s.implemented_checklist_items ?? 0}/${s.total_checklist_items ?? 0}</strong></div>
          <div class="mini"><div class="sub">Last verdict</div><strong>${esc(s.last_verdict || '-')}</strong></div>
        </div>
        <div class="metric"><span>Gateway live</span><strong class="${g.live ? 'ok':'bad'}">${g.live ? 'Online' : 'Offline'}</strong></div>
        <div class="metric"><span>Gateway ready</span><strong class="${g.ready ? 'ok':'warn'}">${g.ready ? 'Ready' : 'Starting'}</strong></div>
        <div class="metric"><span>Healthy routed models</span><strong>${g.health_models ?? 0}</strong></div>
        <div class="metric"><span>Saved app profiles</span><strong>${data.profiles.count}</strong></div>
        <div class="metric"><span>Bound client tokens</span><strong>${data.client_tokens.count}</strong></div>
        <div class="metric"><span>Tracked harness runs</span><strong>${(data.harness.runs || []).length}</strong></div>
        <div class="metric"><span>Review lanes</span><strong>${esc(laneSummary)}</strong></div>
        <div class="metric"><span>Evidence contract</span><strong>${esc(lastVerdict.evidence_contract_version || '-')}</strong></div>
        <div style="margin-top:14px;"><strong>Last lane contributions</strong></div>
        <div class="events" style="margin-top:8px;"><pre>${esc(contributionSummary)}</pre></div>
        <div style="margin-top:14px;"><strong>Implementation checklist</strong></div>
        <div class="events" style="margin-top:8px;"><pre>${esc(checklistSummary)}</pre></div>
        <div class="explain">This panel is a health and control summary. The run cards on the right are where you intervene.</div>
      `;
      const runs = data.harness.runs || [];
      renderFilters(runs);
      const filtered = renderRunList(runs);
      const selected = filtered.find(run => run.run_id === selectedRunId) || null;
      renderRunDetail(selected);
    }
    async function boot(){
      const res = await fetch('/api/overview');
      render(await res.json());
      const es = new EventSource('/events');
      es.onmessage = (evt) => render(JSON.parse(evt.data));
    }
    boot();
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    port = 4000

    def _reject_non_local(self):
        if is_loopback(self.client_address[0]):
            return False
        self.send_response(403)
        self.end_headers()
        return True

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return {}
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode())
        except Exception:
            return {}

    def do_GET(self):
        if self._reject_non_local():
            return
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path.startswith("/assets/"):
            rel = pathlib.Path(unquote(parsed.path[len("/assets/") :]))
            asset = (ASSET_ROOT / rel).resolve()
            if not str(asset).startswith(str(ASSET_ROOT.resolve())) or not asset.exists() or not asset.is_file():
                self._send_json({"error": "not_found"}, status=404)
                return
            body = asset.read_bytes()
            content_type = "image/png" if asset.suffix.lower() == ".png" else "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/overview":
            self._send_json(collect_snapshot(port=self.port))
            return
        if parsed.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            last = None
            try:
                while True:
                    payload = collect_snapshot(port=self.port)
                    current = json.dumps(payload, sort_keys=True)
                    if current != last:
                        self.wfile.write(f"data: {current}\n\n".encode())
                        self.wfile.flush()
                        last = current
                    time.sleep(1.0)
            except (BrokenPipeError, ConnectionResetError):
                return
        self._send_json({"error": "not_found"}, status=404)

    def do_POST(self):
        if self._reject_non_local():
            return
        parsed = urlparse(self.path)
        if parsed.path == "/api/launch":
            payload = self._read_json_body()
            result = launch_agent(
                payload.get("provider", ""),
                payload.get("harness_policy", "balanced"),
                payload.get("sandbox_profile", "normal"),
                payload.get("args", ""),
            )
            self._send_json(result, status=200 if result.get("ok") else 400)
            return
        if parsed.path == "/api/reconcile":
            result = reconcile_runs()
            self._send_json(result, status=200 if result.get("ok") else 400)
            return
        if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/action"):
            run_id = parsed.path[len("/api/runs/") : -len("/action")].strip("/")
            payload = self._read_json_body()
            action = str(payload.get("action", "")).strip()
            result = operator_run_action(run_id, action)
            self._send_json(result, status=200 if result.get("ok") else 400)
            return
        self._send_json({"error": "not_found"}, status=404)

    def log_message(self, fmt, *args):
        return


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 4010
    Handler.port = int(os.environ.get("BROKE_DASHBOARD_GATEWAY_PORT", "4000"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"[dashboard] http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
