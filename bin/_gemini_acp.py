#!/usr/bin/env python3
"""Strict Gemini ACP adapter for BrokeLLM.

This module treats Gemini ACP as the authoritative machine interface for
Gemini-backed node execution. PTY remains an operator/debug surface only.
"""

from __future__ import annotations

import argparse
import json
import os
import pty
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

BIN_DIR = Path(__file__).resolve().parent
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))

from _harness_common import append_event, atomic_write_json, canonical_json, iso_now, read_json
from _run_channel import append_message

PROTOCOL_VERSION = 1


class ACPError(RuntimeError):
    pass


def _emit_harness_event(event_type, payload):
    run_id = os.environ.get("BROKE_HARNESS_RUN_ID", "")
    events_file = os.environ.get("BROKE_HARNESS_EVENTS_FILE", "")
    if not run_id or not events_file:
        return
    append_event(
        events_file,
        run_id,
        event_type,
        "runtime_control",
        "gemini_acp",
        "broke",
        payload=payload,
    )


def _emit_channel(kind, payload, channel="control"):
    run_id = os.environ.get("BROKE_HARNESS_RUN_ID", "")
    channel_file = os.environ.get("BROKE_HARNESS_CHANNEL_FILE", "")
    if not run_id or not channel_file:
        return
    append_message(channel_file, run_id, channel, kind, payload)


class GeminiACPAdapter:
    def __init__(self, argv=None, cwd=None, timeout=45.0, state_file=None, use_pty=None):
        self.argv = argv or ["gemini", "--acp"]
        self.cwd = cwd or os.getcwd()
        self.timeout = timeout
        self.use_pty = self._resolve_use_pty(use_pty)
        self.state_file = Path(state_file) if state_file else None
        self.proc = None
        self._reader_thread = None
        self._stderr_thread = None
        self._stop = threading.Event()
        self._responses = {}
        self._notifications = queue.Queue()
        self._errors = queue.Queue()
        self._next_id = 1
        self._write_lock = threading.Lock()
        self._persist_lock = threading.Lock()
        self._pty_master = None
        self._pty_slave = None
        self._state = {
            "status": "created",
            "transport": "acp",
            "cwd": self.cwd,
            "argv": list(self.argv),
            "launch_mode": "pty" if self.use_pty else "pipe",
            "protocol_version": PROTOCOL_VERSION,
            "session_id": "",
            "initialized": False,
            "stream_corruption": False,
            "last_request_id": 0,
            "last_request_method": "",
            "last_notification_kind": "",
            "started_at": None,
            "updated_at": None,
            "stderr_tail": [],
            "failure_count": 0,
            "failure_reasons": [],
            "last_error": "",
            "cancel_supported": True,
            "initialize_attempts": 0,
            "initialize_failures": 0,
            "quarantined": False,
            "quarantine_reason": "",
            "quarantined_at": None,
            "auth_required": False,
        }
        self._load_persisted_state()
        self.session_file = Path(os.environ.get("BROKE_HARNESS_SESSION_FILE", "")).resolve() if os.environ.get("BROKE_HARNESS_SESSION_FILE") else None
        self.control_file = Path(os.environ.get("BROKE_HARNESS_CONTROL_FILE", "")).resolve() if os.environ.get("BROKE_HARNESS_CONTROL_FILE") else None
        self.runs_file = Path(os.environ.get("BROKE_HARNESS_RUNS_FILE", "")).resolve() if os.environ.get("BROKE_HARNESS_RUNS_FILE") else None
        self.run_id = os.environ.get("BROKE_HARNESS_RUN_ID", "")
        self._last_control_marker = ""
        self._bound_session_id = str(self._state.get("session_id", "") or "")
        self._active_prompt = None
        self._cancel_context = None

    def _resolve_use_pty(self, use_pty):
        if use_pty is not None:
            return bool(use_pty)
        raw = str(os.environ.get("BROKE_GEMINI_ACP_USE_PTY", "")).strip().lower()
        return raw in {"1", "true", "yes", "on"}

    def _load_persisted_state(self):
        if not self.state_file or not self.state_file.exists():
            return
        persisted = read_json(self.state_file, {})
        if not persisted:
            return
        for key in (
            "session_id",
            "session_state",
            "initialize_result",
            "initialized",
            "last_notification_kind",
            "last_request_method",
            "failure_count",
            "failure_reasons",
            "degraded_reason",
            "last_error",
            "stderr_tail",
            "last_prompt_result",
            "last_prompt_text",
            "stream_corruption",
            "initialize_attempts",
            "initialize_failures",
            "quarantined",
            "quarantine_reason",
            "quarantined_at",
            "auth_required",
        ):
            if key in persisted:
                self._state[key] = persisted[key]

    def _update_harness_ledger(self):
        if not self.runs_file or not self.run_id:
            return
        payload = read_json(self.runs_file, {"runs": {}})
        runs = payload.setdefault("runs", {})
        record = runs.get(self.run_id)
        if not isinstance(record, dict):
            return
        record.update(
            {
                "transport": "acp",
                "acp_pid": self._state.get("pid"),
                "acp_session_id": self._state.get("session_id", ""),
                "acp_initialized": self._state.get("initialized", False),
                "acp_status": self._state.get("status", ""),
                "acp_degraded_reason": self._state.get("degraded_reason", ""),
                "acp_last_request_method": self._state.get("last_request_method", ""),
                "acp_last_notification_kind": self._state.get("last_notification_kind", ""),
                "acp_failure_count": self._state.get("failure_count", 0),
                "acp_cancel_supported": True,
                "acp_launch_mode": self._state.get("launch_mode", "pipe"),
                "acp_quarantined": self._state.get("quarantined", False),
                "acp_quarantine_reason": self._state.get("quarantine_reason", ""),
                "updated_at": self._state.get("updated_at"),
            }
        )
        runs[self.run_id] = record
        atomic_write_json(self.runs_file, payload)

    def _persist_state(self):
        with self._persist_lock:
            self._state["updated_at"] = iso_now()
            if not self.state_file:
                pass
            else:
                self.state_file.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_json(self.state_file, self._state)
            self._persist_session()
            self._update_harness_ledger()

    def _persist_session(self):
        if not self.session_file:
            return
        payload = {
            "status": self._state.get("status", ""),
            "transport": "acp",
            "child_pid": self._state.get("pid"),
            "supervisor_pid": os.getpid(),
            "acp_pid": self._state.get("pid"),
            "acp_session_id": self._state.get("session_id", ""),
            "initialized": self._state.get("initialized", False),
            "stream_corruption": self._state.get("stream_corruption", False),
            "last_request_id": self._state.get("last_request_id", 0),
            "last_request_method": self._state.get("last_request_method", ""),
            "last_notification_kind": self._state.get("last_notification_kind", ""),
            "started_at": self._state.get("started_at"),
            "updated_at": self._state.get("updated_at"),
            "exit_code": self._state.get("exit_code"),
            "degraded_reason": self._state.get("degraded_reason", ""),
            "stderr_tail": self._state.get("stderr_tail", []),
            "failure_count": self._state.get("failure_count", 0),
            "failure_reasons": self._state.get("failure_reasons", []),
            "last_error": self._state.get("last_error", ""),
            "cancel_supported": True,
            "launch_mode": self._state.get("launch_mode", "pipe"),
            "initialize_attempts": self._state.get("initialize_attempts", 0),
            "initialize_failures": self._state.get("initialize_failures", 0),
            "quarantined": self._state.get("quarantined", False),
            "quarantine_reason": self._state.get("quarantine_reason", ""),
            "auth_required": self._state.get("auth_required", False),
            "active_prompt": self._active_prompt or {},
        }
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.session_file, payload)

    def _record_failure(self, reason, degrade_immediately=False):
        reason = str(reason or "acp_failure").strip() or "acp_failure"
        reasons = list(self._state.get("failure_reasons", []))
        reasons.append({"reason": reason, "timestamp": iso_now()})
        self._state["failure_reasons"] = reasons[-12:]
        self._state["failure_count"] = int(self._state.get("failure_count", 0) or 0) + 1
        self._state["last_error"] = reason
        if degrade_immediately or self._state["failure_count"] >= 2:
            self._state["status"] = "degraded"
            if degrade_immediately:
                self._state["degraded_reason"] = reason
            else:
                self._state["degraded_reason"] = f"repeated_acp_failures:{reason}"
        self._persist_state()

    def _note_initialize_failure(self, reason):
        self._state["initialize_failures"] = int(self._state.get("initialize_failures", 0) or 0) + 1
        if self._state["initialize_failures"] >= 2:
            self._state["quarantined"] = True
            self._state["status"] = "degraded"
            self._state["quarantine_reason"] = str(reason)
            self._state["quarantined_at"] = iso_now()
        self._persist_state()

    def _clear_quarantine_on_success(self):
        self._state["quarantined"] = False
        self._state["quarantine_reason"] = ""
        self._state["quarantined_at"] = None
        self._state["initialize_failures"] = 0
        self._state["auth_required"] = False
        self._persist_state()

    def _stderr_implies_auth_required(self, line):
        lowered = str(line or "").lower()
        needles = (
            "login",
            "log in",
            "authenticate",
            "authentication",
            "open this url",
            "google account",
            "sign in",
            "browser",
            "reauthorize",
            "authorization required",
        )
        return any(token in lowered for token in needles)

    def _push_stderr(self, line):
        tail = list(self._state.get("stderr_tail", []))
        tail.append(line)
        self._state["stderr_tail"] = tail[-40:]
        lowered = line.lower()
        if "429" in lowered:
            self._state["status"] = "degraded"
            self._state["degraded_reason"] = "upstream_rate_limited"
            self._record_failure("upstream_rate_limited", degrade_immediately=True)
        elif "ask_user" in lowered or "exit_plan_mode" in lowered:
            self._state["status"] = "degraded"
            self._state["degraded_reason"] = "host_interaction_gap"
            self._record_failure("host_interaction_gap", degrade_immediately=True)
        elif self._stderr_implies_auth_required(line):
            self._state["status"] = "degraded"
            self._state["degraded_reason"] = "auth_required"
            self._state["auth_required"] = True
            self._record_failure("auth_required", degrade_immediately=True)
        elif "timed out" in lowered and "tool" in lowered:
            self._state["status"] = "degraded"
            self._state["degraded_reason"] = "tool_timeout"
            self._record_failure("tool_timeout", degrade_immediately=True)
        else:
            self._persist_state()

    def _read_control(self):
        if not self.control_file or not self.control_file.exists():
            return None
        payload = read_json(self.control_file, {})
        command_id = str(payload.get("command_id", "")).strip()
        action = str(payload.get("action", "")).strip()
        marker = f"{command_id}:{action}"
        if not command_id or not action or marker == self._last_control_marker:
            return None
        expected_supervisor = payload.get("expected_supervisor_pid")
        expected_child = payload.get("expected_child_pid")
        if expected_supervisor not in (None, "", os.getpid()):
            return None
        if self.proc is not None and expected_child not in (None, "", self.proc.pid):
            return None
        self._last_control_marker = marker
        return payload

    def _note_session_binding(self):
        session_id = str(self._state.get("session_id", "") or "")
        if not session_id or session_id == self._bound_session_id:
            return
        self._bound_session_id = session_id
        _emit_harness_event("acp.session_bound", {"session_id": session_id})
        _emit_channel("acp.session_bound", {"session_id": session_id}, channel="event")

    def _send_cancel_request(self, session_id, command_id, reason="operator_cancel_prompt"):
        if not session_id:
            raise ACPError("ACP cancel requested without a bound session")
        request_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": request_id, "method": "session/cancel", "params": {"sessionId": session_id}}
        self._cancel_context = {
            "request_id": request_id,
            "session_id": session_id,
            "command_id": command_id,
            "requested_at": iso_now(),
            "reason": reason,
        }
        self._persist_state()
        _emit_harness_event("acp.cancel_requested", {"id": request_id, "session_id": session_id, "command_id": command_id, "reason": reason})
        _emit_channel("session.operator_cancel_prompt", {"id": request_id, "session_id": session_id, "command_id": command_id, "reason": reason})
        self._send(payload)
        return request_id

    def _consume_cancel_response(self):
        if not self._cancel_context:
            return
        request_id = self._cancel_context.get("request_id")
        if request_id not in self._responses:
            return
        message = self._responses.pop(request_id)
        if "error" in message:
            self._record_failure(message["error"].get("message", "cancel_request_failed"))
            _emit_channel("acp.cancel_response", {"message": message, "ok": False}, channel="event")
            self._cancel_context = None
            return
        _emit_harness_event("acp.cancel_completed", {"session_id": self._cancel_context.get("session_id"), "command_id": self._cancel_context.get("command_id")})
        _emit_channel("acp.cancel_response", {"message": message, "ok": True}, channel="event")
        self._state["last_operator_action"] = "cancel_prompt"
        self._state["last_operator_action_id"] = self._cancel_context.get("command_id", "")
        self._persist_state()
        self._cancel_context = None

    def _reader_loop(self):
        if self.use_pty:
            assert self._pty_master is not None
            try:
                with os.fdopen(self._pty_master, "r", buffering=1, errors="replace") as stream:
                    self._pty_master = None
                    for raw in stream:
                        line = raw.strip()
                        if not line:
                            continue
                        try:
                            message = json.loads(line)
                        except Exception:
                            self._state["stream_corruption"] = True
                            self._state["status"] = "degraded"
                            self._state["degraded_reason"] = "stdout_non_json"
                            self._persist_state()
                            self._record_failure("stdout_non_json", degrade_immediately=True)
                            payload = {"line": line[:500], "reason": "stdout_non_json"}
                            _emit_harness_event("acp.stream_corruption", payload)
                            _emit_channel("acp.stream_corruption", payload)
                            self._errors.put(ACPError(f"non-JSON stdout contamination: {line[:200]}"))
                            continue
                        if "id" in message:
                            self._responses[message["id"]] = message
                        else:
                            kind = str(message.get("method", "notification"))
                            self._state["last_notification_kind"] = kind
                            self._persist_state()
                            self._notifications.put(message)
                            _emit_harness_event("acp.notification", {"kind": kind})
                            _emit_channel("acp.notification", {"kind": kind, "message": message}, channel="event")
            except OSError:
                return
        else:
            assert self.proc is not None and self.proc.stdout is not None
            try:
                for raw in self.proc.stdout:
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        message = json.loads(line)
                    except Exception:
                        self._state["stream_corruption"] = True
                        self._state["status"] = "degraded"
                        self._state["degraded_reason"] = "stdout_non_json"
                        self._persist_state()
                        self._record_failure("stdout_non_json", degrade_immediately=True)
                        payload = {"line": line[:500], "reason": "stdout_non_json"}
                        _emit_harness_event("acp.stream_corruption", payload)
                        _emit_channel("acp.stream_corruption", payload)
                        self._errors.put(ACPError(f"non-JSON stdout contamination: {line[:200]}"))
                        continue
                    if "id" in message:
                        self._responses[message["id"]] = message
                    else:
                        kind = str(message.get("method", "notification"))
                        self._state["last_notification_kind"] = kind
                        self._persist_state()
                        self._notifications.put(message)
                        _emit_harness_event("acp.notification", {"kind": kind})
                        _emit_channel("acp.notification", {"kind": kind, "message": message}, channel="event")
            except ValueError:
                return

    def _stderr_loop(self):
        if self.use_pty:
            return
        assert self.proc is not None and self.proc.stderr is not None
        try:
            for raw in self.proc.stderr:
                line = raw.rstrip("\n")
                if not line:
                    continue
                self._push_stderr(line)
                _emit_harness_event("acp.stderr", {"line": line[:500]})
        except ValueError:
            return

    def start(self):
        if self.proc is not None:
            return
        self._stop.clear()
        if self.use_pty:
            master_fd, slave_fd = pty.openpty()
            self._pty_master = master_fd
            self._pty_slave = slave_fd
            self.proc = subprocess.Popen(
                self.argv,
                cwd=self.cwd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
            os.close(slave_fd)
            self._pty_slave = None
        else:
            self.proc = subprocess.Popen(
                self.argv,
                cwd=self.cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
        self._state["status"] = "running"
        self._state["started_at"] = iso_now()
        self._state["pid"] = self.proc.pid
        self._state["launch_mode"] = "pty" if self.use_pty else "pipe"
        self._persist_state()
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._stderr_thread = threading.Thread(target=self._stderr_loop, daemon=True)
        self._reader_thread.start()
        if not self.use_pty:
            self._stderr_thread.start()
        _emit_harness_event("acp.started", {"pid": self.proc.pid, "argv": self.argv})
        _emit_channel("acp.started", {"pid": self.proc.pid, "argv": self.argv})

    def close(self):
        if self.proc is None:
            return
        self._stop.set()
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=2)
        for stream_name in ("stdin", "stdout", "stderr"):
            stream = getattr(self.proc, stream_name, None)
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
        self._state["status"] = "completed"
        self._state["exit_code"] = self.proc.returncode
        self._persist_state()
        _emit_harness_event("acp.completed", {"exit_code": self.proc.returncode})
        _emit_channel("acp.completed", {"exit_code": self.proc.returncode})
        if self._pty_master is not None:
            try:
                os.close(self._pty_master)
            except OSError:
                pass
            self._pty_master = None
        if self._pty_slave is not None:
            try:
                os.close(self._pty_slave)
            except OSError:
                pass
            self._pty_slave = None
        for thread in (self._reader_thread, self._stderr_thread):
            if thread is not None and thread.is_alive():
                thread.join(timeout=1.0)
        self._reader_thread = None
        self._stderr_thread = None
        self.proc = None

    def _send(self, payload):
        if not self.proc:
            raise ACPError("ACP process is not running")
        raw = canonical_json(payload) + "\n"
        with self._write_lock:
            if self.use_pty and self._pty_master is not None:
                os.write(self._pty_master, raw.encode("utf-8"))
            else:
                assert self.proc.stdin is not None
                self.proc.stdin.write(raw)
                self.proc.stdin.flush()

    def restart(self, reason="restart"):
        _emit_harness_event("acp.restart", {"reason": reason})
        _emit_channel("acp.restart", {"reason": reason}, channel="event")
        if self.proc is not None:
            self.close()
        self._responses = {}
        self._notifications = queue.Queue()
        self._errors = queue.Queue()
        self._active_prompt = None
        self._cancel_context = None
        self.start()

    def request(self, method, params=None, timeout=None):
        self.start()
        request_id = self._next_id
        self._next_id += 1
        timeout = self.timeout if timeout is None else timeout
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
        self._state["last_request_id"] = request_id
        self._state["last_request_method"] = method
        self._persist_state()
        _emit_harness_event("acp.request", {"id": request_id, "method": method})
        _emit_channel("acp.request", {"id": request_id, "method": method, "params": params or {}}, channel="event")
        if method == "session/prompt":
            session_id = str((params or {}).get("sessionId", "") or self._state.get("session_id", ""))
            self._active_prompt = {
                "request_id": request_id,
                "session_id": session_id,
                "text": ((params or {}).get("prompt") or [{}])[0].get("text", ""),
                "started_at": iso_now(),
                "cancel_requested": False,
            }
            self._persist_state()
        self._send(payload)
        deadline = time.time() + timeout
        while time.time() < deadline:
            control = self._read_control()
            if control is not None and method == "session/prompt":
                action = control.get("action")
                if action == "cancel_prompt" and self._active_prompt and not self._active_prompt.get("cancel_requested"):
                    expected_session_id = str(control.get("expected_session_id", "") or "")
                    active_session_id = str(self._active_prompt.get("session_id", "") or (params or {}).get("sessionId", ""))
                    if expected_session_id and expected_session_id != active_session_id:
                        continue
                    self._active_prompt["cancel_requested"] = True
                    self._active_prompt["cancel_requested_at"] = iso_now()
                    self._persist_state()
                    self._send_cancel_request(
                        active_session_id,
                        control.get("command_id", ""),
                    )
                elif action == "kill" and self.proc is not None and self.proc.poll() is None:
                    self.proc.terminate()
            self._consume_cancel_response()
            if request_id in self._responses:
                message = self._responses.pop(request_id)
                _emit_channel("acp.response", {"id": request_id, "method": method, "message": message}, channel="event")
                if "error" in message:
                    error_message = message["error"].get("message", "ACP request failed")
                    if method == "session/prompt" and self._active_prompt and self._active_prompt.get("cancel_requested"):
                        lowered = error_message.lower()
                        if "cancel" in lowered or "abort" in lowered or "interrupt" in lowered:
                            result = {
                                "canceled": True,
                                "sessionId": self._active_prompt.get("session_id", ""),
                                "error": message["error"],
                            }
                            self._state["last_prompt_result"] = result
                            self._persist_state()
                            self._active_prompt = None
                            self._cancel_context = None
                            return result
                    self._active_prompt = None
                    self._record_failure(error_message)
                    raise ACPError(error_message)
                if method == "session/prompt":
                    self._active_prompt = None
                    self._cancel_context = None
                return message.get("result", {})
            try:
                err = self._errors.get_nowait()
                self._active_prompt = None
                self._record_failure(str(err), degrade_immediately=True)
                raise err
            except queue.Empty:
                pass
            if self.proc and self.proc.poll() is not None:
                error = ACPError(f"ACP process exited unexpectedly with code {self.proc.returncode}")
                self._active_prompt = None
                self._record_failure(str(error))
                raise error
            time.sleep(0.05)
        error = ACPError(f"ACP request timed out: {method}")
        if method == "initialize":
            if self._state.get("auth_required"):
                error = ACPError("ACP initialize blocked: auth_required")
        self._active_prompt = None
        self._record_failure(str(error))
        raise error

    def initialize(self):
        if self._state.get("quarantined"):
            raise ACPError(f"ACP initialize refused: quarantined:{self._state.get('quarantine_reason', 'unknown')}")
        payload = {
            "protocolVersion": PROTOCOL_VERSION,
            "clientInfo": {"name": "BrokeLLM", "version": "1"},
            "clientCapabilities": {
                "auth": {"terminal": False},
                "fs": {"readTextFile": False, "writeTextFile": False},
                "terminal": False,
            },
        }
        last_error = None
        for attempt in range(3):
            self._state["initialize_attempts"] = int(self._state.get("initialize_attempts", 0) or 0) + 1
            self._persist_state()
            try:
                result = self.request("initialize", payload, timeout=max(self.timeout, 30.0) + (attempt * 10.0))
                self._state["initialized"] = True
                self._state["initialize_result"] = result
                self._state["status"] = "ready"
                self._clear_quarantine_on_success()
                self._persist_state()
                return result
            except ACPError as exc:
                last_error = exc
                reason = str(exc)
                self._note_initialize_failure(reason)
                if "auth_required" in reason:
                    raise
                if attempt == 2:
                    raise
                self.restart(reason=f"initialize_retry_{attempt + 1}")
                time.sleep(0.2 * (attempt + 1))
        raise last_error or ACPError("ACP initialize failed")

    def new_session(self, cwd=None, mcp_servers=None):
        result = self.request("session/new", {"cwd": cwd or self.cwd, "mcpServers": mcp_servers or []})
        self._state["session_id"] = result.get("sessionId", "")
        self._state["session_state"] = result
        self._persist_state()
        self._note_session_binding()
        return result

    def load_session(self, session_id, cwd=None, mcp_servers=None):
        result = self.request(
            "session/load",
            {"sessionId": session_id, "cwd": cwd or self.cwd, "mcpServers": mcp_servers or []},
        )
        self._state["session_id"] = session_id
        self._state["session_state"] = result
        self._persist_state()
        self._note_session_binding()
        return result

    def prompt(self, session_id, text, message_id=None):
        result = self.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "messageId": message_id,
                "prompt": [{"type": "text", "text": text}],
            },
            timeout=max(self.timeout, 120.0),
        )
        self._state["last_prompt_text"] = text
        self._state["last_prompt_result"] = result
        self._persist_state()
        return result

    def cancel(self, session_id):
        return self.request("session/cancel", {"sessionId": session_id})

    def set_session_mode(self, session_id, mode_id):
        return self.request("session/set_mode", {"sessionId": session_id, "modeId": mode_id})


def build_parser():
    parser = argparse.ArgumentParser(description="Gemini ACP adapter for BrokeLLM")
    parser.add_argument("--cwd", default=os.getcwd())
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--state-file", default="")
    parser.add_argument("--pty", action="store_true", dest="use_pty")
    parser.add_argument("--json", action="store_true", dest="as_json")
    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("initialize")

    sess = sub.add_parser("new-session")
    sess.add_argument("--mode", default="")

    load = sub.add_parser("load-session")
    load.add_argument("--session-id", required=True)

    prompt = sub.add_parser("prompt")
    prompt.add_argument("--session-id", default="")
    prompt.add_argument("--load-session", action="store_true")
    prompt.add_argument("--text", required=True)
    prompt.add_argument("--message-id", default="")
    prompt.add_argument("--mode", default="")

    cancel = sub.add_parser("cancel")
    cancel.add_argument("--session-id", required=True)

    mode = sub.add_parser("set-mode")
    mode.add_argument("--session-id", required=True)
    mode.add_argument("--mode-id", required=True)
    return parser


def _print(result, as_json=False):
    if as_json:
        print(json.dumps(result, indent=2))
        return
    print(canonical_json(result))


def main(argv=None):
    args = build_parser().parse_args(argv)
    state_file = args.state_file or os.environ.get("BROKE_GEMINI_ACP_STATE_FILE", "")
    adapter = GeminiACPAdapter(cwd=args.cwd, timeout=args.timeout, state_file=state_file or None, use_pty=args.use_pty)
    try:
        initialize = adapter.initialize()
        if args.action == "initialize":
            _print({"ok": True, "initialize": initialize}, args.as_json)
            return 0
        if args.action == "new-session":
            result = adapter.new_session()
            if args.mode:
                adapter.set_session_mode(result["sessionId"], args.mode)
            _print({"ok": True, "initialize": initialize, "session": result}, args.as_json)
            return 0
        if args.action == "load-session":
            result = adapter.load_session(args.session_id)
            _print({"ok": True, "initialize": initialize, "session": result}, args.as_json)
            return 0
        if args.action == "prompt":
            session_id = args.session_id
            session = None
            if session_id:
                if args.load_session:
                    session = adapter.load_session(session_id)
            elif args.load_session and adapter._state.get("session_id"):
                session_id = adapter._state["session_id"]
                session = adapter.load_session(session_id)
            else:
                session = adapter.new_session()
                session_id = session["sessionId"]
            if args.mode:
                adapter.set_session_mode(session_id, args.mode)
            result = adapter.prompt(session_id, args.text, args.message_id or None)
            _print(
                {"ok": True, "initialize": initialize, "session": session or {"sessionId": session_id}, "prompt": result},
                args.as_json,
            )
            return 0
        if args.action == "cancel":
            result = adapter.cancel(args.session_id)
            _print({"ok": True, "initialize": initialize, "cancel": result}, args.as_json)
            return 0
        if args.action == "set-mode":
            result = adapter.set_session_mode(args.session_id, args.mode_id)
            _print({"ok": True, "initialize": initialize, "mode": result}, args.as_json)
            return 0
        raise ACPError(f"unknown action: {args.action}")
    except ACPError as exc:
        _emit_harness_event("acp.failed", {"error": str(exc)})
        _emit_channel("acp.failed", {"error": str(exc)})
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    finally:
        adapter.close()


if __name__ == "__main__":
    raise SystemExit(main())
