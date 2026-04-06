#!/usr/bin/env python3
"""Runtime bindings for BrokeLLM's ACP facade."""

from __future__ import annotations

import json
import os
import queue
import shlex
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request

BIN_DIR = Path(__file__).resolve().parent
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))

from _acp_lane import canonical_lane_result, default_runtime_registry, normalize_provider_output
from _harness_common import atomic_write_json, iso_now, read_json


class ACPRuntimeError(RuntimeError):
    pass


class BaseRuntime:
    provider = "unknown"
    runtime_binding = "headless_adapter"
    runtime_name = "BaseRuntime"
    default_heartbeat_timeout_sec = 45
    cancel_kind = "unknown"
    supports_streaming = False
    supports_cancel = False
    supports_transport_cancel = False
    supports_live_interrupt = False
    supports_native_session_resume = False
    supports_tool_roundtrip = False
    session_persistence = "logical_lane"
    late_result_policy = "quarantine"

    def __init__(self, sessions_root=None):
        self.sessions_root = Path(sessions_root or Path.cwd() / ".runtime" / "acp" / "sessions")
        self.sessions_root.mkdir(parents=True, exist_ok=True)
        self._sessions = {}
        self._lock = threading.Lock()

    def new_session(self, cwd=None, model=None, mode=None, metadata=None):
        raise NotImplementedError

    def load_session(self, session_record):
        return session_record

    def prompt(self, session_id, prompt, event_cb=None, timeout=180.0):
        raise NotImplementedError

    def cancel(self, session_id):
        raise NotImplementedError

    def close(self, session_id):
        session = self._sessions.pop(session_id, None)
        if session:
            self._shutdown_process(session)
        return {"session_id": session_id, "closed": True}

    def get_session_state(self, session_id):
        session = self._sessions.get(session_id)
        if session is None:
            session = read_json(self._session_path(session_id), {})
        self._refresh_watchdog(session)
        return self._public_session_state(session)

    def _new_session_record(self, cwd=None, model=None, mode=None, metadata=None):
        session_id = str(uuid.uuid4())
        record = {
            "session_id": session_id,
            "provider": self.provider,
            "runtime_binding": self.runtime_binding,
            "runtime_name": self.runtime_name,
            "cwd": cwd or os.getcwd(),
            "model": model,
            "mode": mode or "default",
            "metadata": metadata or {},
            "transport": self.runtime_name,
            "status": "created",
            "degraded": False,
            "degraded_reason": "",
            "created_at": iso_now(),
            "updated_at": iso_now(),
            "warnings": [],
            "last_prompt": "",
            "last_turn_id": "",
            "last_output_text": "",
            "capabilities": {
                "runtime_name": self.runtime_name,
                "runtime_binding": self.runtime_binding,
                "supports_streaming": self.supports_streaming,
                "supports_cancel": self.supports_cancel,
                "supports_transport_cancel": self.supports_transport_cancel,
                "supports_live_interrupt": self.supports_live_interrupt,
                "supports_native_session_resume": self.supports_native_session_resume,
                "supports_tool_roundtrip": self.supports_tool_roundtrip,
                "cancel_kind": self.cancel_kind,
                "session_persistence": self.session_persistence,
                "late_result_policy": self.late_result_policy,
                "startup_canary": "pending",
                "startup_checked_at": None,
                "runtime_version": "",
            },
            "transport_health": {
                "last_event_at": iso_now(),
                "heartbeat_timeout_sec": self.default_heartbeat_timeout_sec,
                "watchdog_state": "healthy",
            },
            "turn_generation": 0,
            "completed_turn_ids": [],
            "quarantined_results": [],
            "quarantine_count": 0,
        }
        return record

    def _public_session_state(self, session):
        session = dict(session or {})
        for key in ("proc", "stdout_thread", "stderr_thread", "requests", "active_turn", "lock", "initialized"):
            session.pop(key, None)
        return session

    def _session_path(self, session_id):
        return self.sessions_root / f"{session_id}.json"

    def _persist_session(self, session):
        self._refresh_watchdog(session)
        session["updated_at"] = iso_now()
        atomic_write_json(self._session_path(session["session_id"]), self._public_session_state(session))

    def _emit(self, event_cb, event_type, session, payload=None):
        self._touch_transport(session)
        if not event_cb:
            return
        merged = {"sessionId": session["session_id"], "provider": session.get("provider", self.provider)}
        if payload:
            merged.update(payload)
        event_cb(event_type, merged)

    def _mark_warning(self, session, warning):
        warnings = list(session.get("warnings", []))
        warnings.append({"timestamp": iso_now(), "warning": str(warning)})
        session["warnings"] = warnings[-20:]
        self._persist_session(session)

    def _touch_transport(self, session):
        health = session.setdefault("transport_health", {})
        health["last_event_at"] = iso_now()
        if health.get("watchdog_state") == "stale":
            health["watchdog_state"] = "healthy"

    def _refresh_watchdog(self, session):
        if not isinstance(session, dict):
            return
        health = session.setdefault("transport_health", {})
        timeout = int(health.get("heartbeat_timeout_sec") or self.default_heartbeat_timeout_sec)
        health.setdefault("heartbeat_timeout_sec", timeout)
        last_event = str(health.get("last_event_at") or "")
        if not last_event:
            health["last_event_at"] = iso_now()
            health["watchdog_state"] = "healthy"
            return
        try:
            last_ts = datetime.fromisoformat(last_event).astimezone(timezone.utc).timestamp()
        except Exception:
            health["watchdog_state"] = "unknown"
            return
        if time.time() - last_ts > timeout:
            health["watchdog_state"] = "stale"
        else:
            health["watchdog_state"] = "healthy"

    def _mark_startup_canary(self, session, status, reason=""):
        caps = session.setdefault("capabilities", {})
        caps["startup_canary"] = status
        caps["startup_checked_at"] = iso_now()
        if reason:
            session["degraded"] = True
            session["degraded_reason"] = reason
        self._persist_session(session)

    def _degraded_result(self, role, text, reason):
        result = canonical_lane_result(role, provider=self.provider, runtime_binding=self.runtime_binding)
        result["status"] = "failed"
        result["summary"] = text or reason
        result["degraded"] = True
        result["degraded_reason"] = reason
        return result

    def _begin_turn(self, session, turn_id, prompt, event_cb=None, **extra):
        generation = int(session.get("turn_generation") or 0) + 1
        session["turn_generation"] = generation
        turn = {
            "turn_id": turn_id,
            "generation": generation,
            "prompt": prompt,
            "done": threading.Event(),
            "error": "",
            "event_cb": event_cb,
        }
        turn.update(extra)
        session["active_turn"] = turn
        session["active_turn_generation"] = generation
        session["last_prompt"] = prompt
        session["last_turn_id"] = turn_id
        return turn

    def _mark_turn_completed(self, session, turn=None, remote_turn_id=""):
        completed = list(session.get("completed_turn_ids", []))
        if turn and turn.get("turn_id"):
            completed.append(str(turn["turn_id"]))
        if remote_turn_id:
            completed.append(str(remote_turn_id))
        deduped = []
        seen = set()
        for item in completed:
            if not item or item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        session["completed_turn_ids"] = deduped[-50:]
        if turn and session.get("active_turn") is turn:
            session["active_turn"] = None

    def _record_quarantined_result(self, session, reason, payload=None, turn_id="", remote_turn_id="", generation=None):
        rows = list(session.get("quarantined_results", []))
        rendered = ""
        if payload is not None:
            try:
                rendered = json.dumps(payload, ensure_ascii=True)[:400]
            except Exception:
                rendered = str(payload)[:400]
        rows.append(
            {
                "timestamp": iso_now(),
                "reason": str(reason),
                "turn_id": str(turn_id or ""),
                "remote_turn_id": str(remote_turn_id or ""),
                "generation": generation,
                "payload": rendered,
            }
        )
        session["quarantined_results"] = rows[-20:]
        session["quarantine_count"] = int(session.get("quarantine_count") or 0) + 1
        self._persist_session(session)

    def _shutdown_process(self, session):
        proc = session.get("proc")
        if not proc:
            return
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
        try:
            proc.wait(timeout=3)
        except Exception:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        session["proc"] = None
        session["status"] = "stopped"
        self._persist_session(session)


class HeadlessAdapterRuntime(BaseRuntime):
    runtime_binding = "headless_adapter"
    runtime_name = "HeadlessAdapterRuntime"
    cancel_kind = "logical"
    supports_streaming = True
    supports_cancel = True
    supports_transport_cancel = False
    supports_live_interrupt = False
    supports_native_session_resume = True
    supports_tool_roundtrip = False
    session_persistence = "logical_lane"
    api_base_env = ""
    api_key_env = ""
    default_api_base = ""
    default_model = ""

    def new_session(self, cwd=None, model=None, mode=None, metadata=None):
        session = self._new_session_record(cwd=cwd, model=model, mode=mode, metadata=metadata)
        session["history"] = []
        session["active_turn"] = None
        session["lock"] = threading.RLock()
        session["status"] = "ready"
        self._sessions[session["session_id"]] = session
        self._mark_startup_canary(session, "passed")
        self._persist_session(session)
        return self._public_session_state(session)

    def load_session(self, session_record):
        session = dict(session_record or {})
        session.setdefault("provider", self.provider)
        session.setdefault("runtime_binding", self.runtime_binding)
        session.setdefault("runtime_name", self.runtime_name)
        session.setdefault("history", [])
        session["active_turn"] = None
        session["lock"] = threading.RLock()
        self._sessions[session["session_id"]] = session
        self._refresh_watchdog(session)
        return self._public_session_state(session)

    def prompt(self, session_id, prompt, event_cb=None, timeout=180.0):
        session = self._sessions.get(session_id)
        if not session:
            raise ACPRuntimeError(f"unknown session: {session_id}")
        with session["lock"]:
            if session.get("active_turn") and not session["active_turn"]["done"].is_set():
                raise ACPRuntimeError("session already has an active prompt")
            turn_id = f"turn-{int(time.time() * 1000)}"
            active = self._begin_turn(
                session,
                turn_id,
                prompt,
                event_cb=event_cb,
                cancelled=False,
                raw_payload=None,
                text="",
            )
            self._persist_session(session)
            self._emit(event_cb, "turn.started", session, {"turnId": turn_id, "prompt": prompt})
            thread = threading.Thread(target=self._run_headless_turn, args=(session, active), daemon=True)
            thread.start()
        if not active["done"].wait(timeout):
            self.cancel(session_id)
            result = self._degraded_result("worker", "", f"{self.provider}_prompt_timeout")
            self._mark_turn_completed(session, turn=active)
            self._emit(event_cb, "lane.timeout", session, {"turnId": turn_id, "reason": result["degraded_reason"]})
            self._emit(event_cb, "turn.completed", session, {"turnId": turn_id, "result": result})
            return {"session": self._public_session_state(session), "turnId": turn_id, "laneResult": result, "outputText": ""}

        if active.get("cancelled"):
            result = self._degraded_result("worker", "", "cancelled")
            result["status"] = "cancelled"
            self._mark_turn_completed(session, turn=active)
            self._emit(event_cb, "lane.cancelled", session, {"turnId": turn_id})
            self._emit(event_cb, "turn.completed", session, {"turnId": turn_id, "result": result})
            return {"session": self._public_session_state(session), "turnId": turn_id, "laneResult": result, "outputText": ""}

        payload = active.get("raw_payload")
        text = active.get("text", "")
        if active.get("error"):
            session["degraded"] = True
            session["degraded_reason"] = active["error"]
            result = self._degraded_result("worker", text, active["error"])
            self._emit(event_cb, "lane.degraded", session, {"turnId": turn_id, "reason": active["error"]})
        else:
            parsed = self._coerce_lane_payload(text, payload)
            result = normalize_provider_output(
                "worker",
                parsed,
                provider=self.provider,
                runtime_binding=self.runtime_binding,
            )
        session["last_output_text"] = text
        self._mark_turn_completed(session, turn=active)
        self._persist_session(session)
        self._emit(event_cb, "turn.completed", session, {"turnId": turn_id, "result": result})
        return {"session": self._public_session_state(session), "turnId": turn_id, "laneResult": result, "outputText": text}

    def cancel(self, session_id):
        session = self._sessions.get(session_id)
        if not session:
            raise ACPRuntimeError(f"unknown session: {session_id}")
        active = session.get("active_turn")
        if active and not active["done"].is_set():
            active["cancelled"] = True
            active["error"] = "cancelled"
            active["done"].set()
        session["status"] = "interrupted"
        self._persist_session(session)
        return {"session_id": session_id, "cancelled": active is not None, "cancel_kind": self.cancel_kind}

    def _run_headless_turn(self, session, active):
        try:
            payload = self._request_completion(session, active["prompt"], active=active)
            text = self._extract_text(payload)
            if active.get("cancelled") or session.get("active_turn") is not active:
                self._record_quarantined_result(
                    session,
                    "late_result_after_cancel_or_turn_replacement",
                    payload=payload,
                    turn_id=active.get("turn_id", ""),
                    generation=active.get("generation"),
                )
            else:
                active["raw_payload"] = payload
                active["text"] = text
                session["history"] = list(session.get("history", [])) + [
                    {"role": "user", "content": active["prompt"]},
                    {"role": "assistant", "content": text},
                ]
        except Exception as exc:
            if not active.get("cancelled"):
                active["error"] = str(exc)
        finally:
            active["done"].set()

    def _coerce_lane_payload(self, text, payload):
        stripped = str(text or "").strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        return {
            "summary": stripped,
            "provider_metadata": {
                "provider": self.provider,
                "runtime_binding": self.runtime_binding,
                "raw_payload_kind": type(payload).__name__,
            },
        }

    def _resolve_model(self, session):
        model = str(session.get("model") or os.environ.get(f"BROKE_{self.provider.upper()}_MODEL", "") or self.default_model).strip()
        if not model:
            raise ACPRuntimeError(f"{self.provider}_model_not_configured")
        return model

    def _resolve_api_base(self):
        api_base = str(os.environ.get(self.api_base_env, "") or self.default_api_base).strip().rstrip("/")
        if not api_base:
            raise ACPRuntimeError(f"{self.provider}_api_base_not_configured")
        return api_base

    def _resolve_headers(self):
        headers = {"Content-Type": "application/json"}
        key_name = self.api_key_env
        token = str(os.environ.get(key_name, "")).strip() if key_name else ""
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _request_completion(self, session, prompt, active=None):
        payload = {
            "model": self._resolve_model(session),
            "messages": list(session.get("history", [])) + [{"role": "user", "content": prompt}],
            "stream": True,
        }
        req = urllib_request.Request(
            self._resolve_api_base() + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._resolve_headers(),
            method="POST",
        )
        try:
            with urllib_request.urlopen(req, timeout=90) as resp:
                if "text/event-stream" in str(resp.headers.get("Content-Type", "")):
                    return self._read_sse_stream(resp, session, active)
                return json.loads(resp.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:400]
            raise ACPRuntimeError(f"http_{exc.code}:{body}") from exc
        except urllib_error.URLError as exc:
            raise ACPRuntimeError(f"transport_error:{exc.reason}") from exc

    def _extract_text(self, payload):
        if not isinstance(payload, dict):
            return str(payload)
        choices = payload.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            content = message.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(item.get("text", ""))
                if parts:
                    return "".join(parts)
        output = payload.get("output") or []
        if output:
            parts = []
            for item in output:
                if isinstance(item, dict):
                    for content in item.get("content", []) or []:
                        if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                            parts.append(content.get("text", ""))
            if parts:
                return "".join(parts)
        return json.dumps(payload, ensure_ascii=True)

    def _read_sse_stream(self, resp, session, active):
        final_payload = {}
        deltas = []
        for raw in resp:
            if active and active.get("cancelled"):
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line or line.startswith(":") or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                payload = json.loads(data)
            except Exception:
                continue
            final_payload = payload
            delta = self._extract_delta_text(payload)
            if delta:
                deltas.append(delta)
                if active is not None:
                    active["text"] = "".join(deltas)
                self._emit(
                    active.get("event_cb") if active else None,
                    "turn.delta",
                    session,
                    {"turnId": active.get("turn_id", "") if active else "", "delta": delta},
                )
        if deltas and isinstance(final_payload, dict):
            final_payload.setdefault("choices", [{"message": {"content": "".join(deltas)}}])
        return final_payload

    def _extract_delta_text(self, payload):
        if not isinstance(payload, dict):
            return ""
        choices = payload.get("choices") or []
        if not choices:
            return ""
        delta = choices[0].get("delta") or {}
        content = delta.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") in {"text", "output_text"}:
                    parts.append(item.get("text", ""))
            return "".join(parts)
        return ""


class ExternalAcpShimRuntime(BaseRuntime):
    runtime_binding = "cli_adapter"
    runtime_name = "ExternalAcpShimRuntime"
    supports_streaming = True
    supports_cancel = True
    session_persistence = "live_runtime"
    default_cancel_kind = "shim_transport"
    shim_command_env = ""
    default_shim_command = ""
    init_method_aliases = ("initialize",)
    new_session_method_aliases = ("newSession", "session/new")
    load_session_method_aliases = ("loadSession", "session/load")
    prompt_method_aliases = ("prompt", "session/prompt")
    cancel_method_aliases = ("cancel", "session/cancel")
    state_method_aliases = ("getSessionState", "session/get")
    set_mode_method_aliases = ("setSessionMode", "session/setMode")
    close_method_aliases = ("closeSession", "session/close")
    legacy_runtime_class_name = ""

    def new_session(self, cwd=None, model=None, mode=None, metadata=None):
        session = self._new_session_record(cwd=cwd, model=model, mode=mode, metadata=metadata)
        session.update(
            {
                "transport": self.runtime_name,
                "remote_session_id": "",
                "proc": None,
                "stdout_thread": None,
                "stderr_thread": None,
                "requests": {},
                "next_request_id": 1,
                "active_turn": None,
                "initialized": False,
                "lock": threading.RLock(),
            }
        )
        self._sessions[session["session_id"]] = session
        self._ensure_process(session)
        response = self._request_with_aliases(
            session,
            self.new_session_method_aliases,
            {"cwd": session.get("cwd") or os.getcwd(), "model": session.get("model"), "mode": session.get("mode"), "metadata": session.get("metadata", {})},
            timeout=30,
        )
        self._merge_remote_session(session, response)
        self._persist_session(session)
        return self._public_session_state(session)

    def load_session(self, session_record):
        session = dict(session_record or {})
        session.setdefault("provider", self.provider)
        session.setdefault("runtime_binding", self.runtime_binding)
        session.setdefault("runtime_name", self.runtime_name)
        session.setdefault("transport", self.runtime_name)
        session.setdefault("remote_session_id", session.get("metadata", {}).get("remote_session_id", ""))
        session["proc"] = None
        session["stdout_thread"] = None
        session["stderr_thread"] = None
        session["requests"] = {}
        session["next_request_id"] = 1
        session["active_turn"] = None
        session["initialized"] = False
        session["lock"] = threading.RLock()
        self._sessions[session["session_id"]] = session
        self._ensure_process(session)
        remote_session_id = session.get("remote_session_id") or session.get("metadata", {}).get("remote_session_id", "")
        if remote_session_id:
            response = self._request_with_aliases(
                session,
                self.load_session_method_aliases,
                {"sessionId": remote_session_id},
                timeout=30,
            )
            self._merge_remote_session(session, response)
            self._persist_session(session)
        return self._public_session_state(session)

    def _command(self, session):
        raw = str(os.environ.get(self.shim_command_env, "")).strip() or self.default_shim_command
        if not raw:
            raise ACPRuntimeError(f"{self.provider}_acp_shim_not_configured")
        return shlex.split(raw)

    def _ensure_process(self, session):
        proc = session.get("proc")
        if proc and proc.poll() is None:
            return
        try:
            proc = subprocess.Popen(
                self._command(session),
                cwd=session.get("cwd") or os.getcwd(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
        except FileNotFoundError as exc:
            raise ACPRuntimeError(f"{self.provider}_acp_shim_not_found:{exc.filename}") from exc
        session["proc"] = proc
        session["status"] = "running"
        session["started_at"] = iso_now()
        session["stdout_thread"] = threading.Thread(target=self._stdout_loop, args=(session,), daemon=True)
        session["stderr_thread"] = threading.Thread(target=self._stderr_loop, args=(session,), daemon=True)
        session["stdout_thread"].start()
        session["stderr_thread"].start()
        self._request_with_aliases(
            session,
            self.init_method_aliases,
            {
                "protocolVersion": "2025-03-26",
                "clientInfo": {"name": "broke-acp", "version": "1"},
                "capabilities": {},
            },
            timeout=15,
        )
        session["initialized"] = True
        self._mark_startup_canary(session, "passed")
        self._persist_session(session)

    def _stdout_loop(self, session):
        proc = session["proc"]
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            self._handle_stdout_line(session, line.rstrip())
        active = session.get("active_turn")
        if active and not active["done"].is_set():
            active["error"] = active.get("error") or f"{self.provider}_acp_shim_exited"
            active["done"].set()

    def _stderr_loop(self, session):
        proc = session["proc"]
        while True:
            line = proc.stderr.readline()
            if not line:
                break
            self._mark_warning(session, line.rstrip())

    def _send_request(self, session, method, params, timeout=30):
        with session["lock"]:
            request_id = session["next_request_id"]
            session["next_request_id"] += 1
            waiter = queue.Queue(maxsize=1)
            session["requests"][request_id] = waiter
            payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
            try:
                session["proc"].stdin.write(json.dumps(payload) + "\n")
                session["proc"].stdin.flush()
            except Exception as exc:
                session["requests"].pop(request_id, None)
                raise ACPRuntimeError(f"{self.provider}_acp_write_failed:{exc}") from exc
        try:
            response = waiter.get(timeout=timeout)
        except queue.Empty as exc:
            session["requests"].pop(request_id, None)
            raise ACPRuntimeError(f"{self.provider}_acp_request_timed_out:{method}") from exc
        if "error" in response:
            code = response["error"].get("code")
            message = response["error"].get("message", f"{self.provider}_acp_request_failed:{method}")
            raise ACPRuntimeError(f"{code}:{message}")
        return response.get("result", {})

    def _request_with_aliases(self, session, methods, params, timeout=30):
        last_error = None
        for method in methods:
            try:
                return self._send_request(session, method, params, timeout=timeout)
            except ACPRuntimeError as exc:
                last_error = exc
                text = str(exc).lower()
                if "unknown method" in text or "method not found" in text or "-32601" in text:
                    continue
                raise
        raise last_error or ACPRuntimeError(f"{self.provider}_acp_request_failed")

    def _extract_remote_session_id(self, payload):
        if not isinstance(payload, dict):
            return ""
        for key in ("sessionId", "session_id"):
            value = str(payload.get(key, "")).strip()
            if value:
                return value
        session = payload.get("session")
        if isinstance(session, dict):
            for key in ("id", "sessionId", "session_id"):
                value = str(session.get(key, "")).strip()
                if value:
                    return value
        return ""

    def _extract_delta(self, params):
        for key in ("delta", "text", "content"):
            value = params.get(key)
            if isinstance(value, str) and value:
                return value
        return ""

    def _handle_stdout_line(self, session, line):
        try:
            payload = json.loads(line)
        except Exception:
            self._mark_warning(session, f"unparsed_stdout:{line[:200]}")
            return
        if "id" in payload:
            waiter = session["requests"].pop(payload["id"], None)
            if waiter:
                waiter.put(payload)
            return
        method = str(payload.get("method", "")).replace("/", ".")
        params = payload.get("params", {}) or {}
        remote_session_id = self._extract_remote_session_id(params)
        if remote_session_id:
            session["remote_session_id"] = remote_session_id
            session.setdefault("metadata", {})["remote_session_id"] = remote_session_id
        if method == "lane.degraded":
            session["degraded"] = True
            session["degraded_reason"] = str(params.get("reason", "") or f"{self.provider}_shim_degraded")
            self._persist_session(session)
            return
        active = session.get("active_turn")
        if method in {"turn.delta", "turn.completed"} and not active:
            self._record_quarantined_result(
                session,
                "late_result_without_active_turn",
                payload=payload,
                remote_turn_id=str(params.get("turnId", "") or ""),
            )
            return
        if not active:
            return
        remote_turn_id = str(params.get("turnId", "") or "")
        if remote_turn_id and remote_turn_id in set(session.get("completed_turn_ids", [])):
            self._record_quarantined_result(
                session,
                "duplicate_completed_turn",
                payload=payload,
                turn_id=active.get("turn_id", ""),
                remote_turn_id=remote_turn_id,
                generation=active.get("generation"),
            )
            return
        if remote_turn_id and active.get("remote_turn_id") and active.get("remote_turn_id") != remote_turn_id:
            self._record_quarantined_result(
                session,
                "stale_turn_result_generation_mismatch",
                payload=payload,
                turn_id=active.get("turn_id", ""),
                remote_turn_id=remote_turn_id,
                generation=active.get("generation"),
            )
            return
        if method == "turn.delta":
            delta = self._extract_delta(params)
            if delta:
                if remote_turn_id and not active.get("remote_turn_id"):
                    active["remote_turn_id"] = remote_turn_id
                active["text_parts"].append(delta)
                self._emit(active.get("event_cb"), "turn.delta", session, {"turnId": active.get("turn_id", ""), "delta": delta})
        elif method == "turn.completed":
            result = params.get("result") if isinstance(params.get("result"), dict) else {}
            active["remote_turn_id"] = remote_turn_id or active.get("remote_turn_id", "")
            if result:
                active["result_payload"] = result
                if not active.get("final_text"):
                    active["final_text"] = str(result.get("summary", "") or params.get("outputText", ""))
            active["done"].set()

    def _merge_remote_session(self, session, response):
        remote_session_id = self._extract_remote_session_id(response)
        if remote_session_id:
            session["remote_session_id"] = remote_session_id
            session.setdefault("metadata", {})["remote_session_id"] = remote_session_id
        if isinstance(response, dict):
            caps = response.get("capabilities")
            if isinstance(caps, dict):
                merged = dict(session.get("capabilities", {}))
                merged.update(caps)
                session["capabilities"] = merged
            mode = response.get("mode")
            if isinstance(mode, str) and mode:
                session["mode"] = mode
            model = response.get("model")
            if isinstance(model, str) and model:
                session["model"] = model
        session["status"] = "ready"

    def prompt(self, session_id, prompt, event_cb=None, timeout=240.0):
        session = self._sessions.get(session_id)
        if not session:
            raise ACPRuntimeError(f"unknown session: {session_id}")
        with session["lock"]:
            self._ensure_process(session)
            if session.get("active_turn") and not session["active_turn"]["done"].is_set():
                raise ACPRuntimeError("session already has an active prompt")
            turn_id = f"turn-{int(time.time() * 1000)}"
            active = self._begin_turn(
                session,
                turn_id,
                prompt,
                event_cb=event_cb,
                text_parts=[],
                result_payload=None,
                final_text="",
                remote_turn_id="",
            )
            self._persist_session(session)
            self._emit(event_cb, "turn.started", session, {"turnId": turn_id, "prompt": prompt})
        try:
            response = self._request_with_aliases(
                session,
                self.prompt_method_aliases,
                {"sessionId": session.get("remote_session_id"), "prompt": prompt},
                timeout=timeout,
            )
        except ACPRuntimeError as exc:
            active["error"] = str(exc)
            response = {}
        text = str(response.get("outputText", "") or "".join(active["text_parts"]) or active.get("final_text", ""))
        lane_payload = response.get("laneResult") if isinstance(response.get("laneResult"), dict) else response.get("result")
        if isinstance(lane_payload, dict):
            result = normalize_provider_output("worker", lane_payload, provider=self.provider, runtime_binding=self.runtime_binding)
            text = text or str(result.get("summary", ""))
        else:
            result = canonical_lane_result("worker", provider=self.provider, runtime_binding=self.runtime_binding)
            result["summary"] = text
        if active.get("error"):
            result["status"] = "failed"
            result["degraded"] = True
            result["degraded_reason"] = active["error"]
            session["degraded"] = True
            session["degraded_reason"] = active["error"]
            self._emit(event_cb, "lane.degraded", session, {"turnId": turn_id, "reason": active["error"]})
        remote_turn_id = str(response.get("turnId", "") or active.get("remote_turn_id", ""))
        if remote_turn_id:
            result.setdefault("provider_metadata", {})["remote_turn_id"] = remote_turn_id
        session["last_output_text"] = text
        self._mark_turn_completed(session, turn=active, remote_turn_id=remote_turn_id)
        self._persist_session(session)
        self._emit(event_cb, "turn.completed", session, {"turnId": turn_id, "result": result})
        return {"session": self._public_session_state(session), "turnId": turn_id, "laneResult": result, "outputText": text}

    def cancel(self, session_id):
        session = self._sessions.get(session_id)
        if not session:
            raise ACPRuntimeError(f"unknown session: {session_id}")
        active = session.get("active_turn")
        try:
            self._request_with_aliases(
                session,
                self.cancel_method_aliases,
                {"sessionId": session.get("remote_session_id"), "turnId": active.get("remote_turn_id", "") if active else ""},
                timeout=15,
            )
        except Exception:
            pass
        if active and not active["done"].is_set():
            active["error"] = "cancelled"
            active["done"].set()
        session["status"] = "interrupted"
        self._persist_session(session)
        return {"session_id": session_id, "cancelled": True, "cancel_kind": self.cancel_kind}

    def get_session_state(self, session_id):
        session = self._sessions.get(session_id)
        if session is None:
            session = read_json(self._session_path(session_id), {})
        if session and session.get("proc") and session.get("remote_session_id"):
            try:
                response = self._request_with_aliases(
                    session,
                    self.state_method_aliases,
                    {"sessionId": session.get("remote_session_id")},
                    timeout=10,
                )
                self._merge_remote_session(session, response)
            except Exception:
                pass
        self._refresh_watchdog(session)
        return self._public_session_state(session)

    def close(self, session_id):
        session = self._sessions.get(session_id)
        if session and session.get("remote_session_id"):
            try:
                self._request_with_aliases(
                    session,
                    self.close_method_aliases,
                    {"sessionId": session.get("remote_session_id")},
                    timeout=10,
                )
            except Exception:
                pass
        return super().close(session_id)


class ClaudeAgentAcpShimRuntime(ExternalAcpShimRuntime):
    provider = "claude"
    runtime_name = "ClaudeAgentAcpShimRuntime"
    cancel_kind = "shim_transport"
    supports_transport_cancel = True
    supports_live_interrupt = False
    supports_native_session_resume = True
    supports_tool_roundtrip = True
    shim_command_env = "BROKE_CLAUDE_ACP_SHIM"
    default_shim_command = "claude-agent-acp"
    legacy_runtime_class_name = "ClaudeCliAdapterRuntime"


class CodexAcpShimRuntime(ExternalAcpShimRuntime):
    provider = "codex"
    runtime_name = "CodexAcpShimRuntime"
    cancel_kind = "shim_transport"
    supports_transport_cancel = True
    supports_live_interrupt = False
    supports_native_session_resume = True
    supports_tool_roundtrip = True
    shim_command_env = "BROKE_CODEX_ACP_SHIM"
    default_shim_command = "codex-acp"
    legacy_runtime_class_name = "CodexCliAdapterRuntime"


class ClaudeCliAdapterRuntime(BaseRuntime):
    provider = "claude"
    runtime_binding = "cli_adapter"
    runtime_name = "ClaudeCliAdapterRuntime"
    cancel_kind = "signal"
    supports_streaming = True
    supports_cancel = True
    supports_transport_cancel = True
    supports_live_interrupt = True
    supports_native_session_resume = True
    supports_tool_roundtrip = True
    session_persistence = "live_runtime"

    def new_session(self, cwd=None, model=None, mode=None, metadata=None):
        session = self._new_session_record(cwd=cwd, model=model, mode=mode, metadata=metadata)
        session.update(
            {
                "transport": "claude_stream_json",
                "proc": None,
                "stdout_thread": None,
                "stderr_thread": None,
                "active_turn": None,
                "lock": threading.RLock(),
            }
        )
        self._sessions[session["session_id"]] = session
        self._persist_session(session)
        return self._public_session_state(session)

    def load_session(self, session_record):
        session = dict(session_record or {})
        session.setdefault("provider", self.provider)
        session.setdefault("runtime_binding", self.runtime_binding)
        session.setdefault("runtime_name", self.runtime_name)
        session.setdefault("transport", "claude_stream_json")
        session["proc"] = None
        session["stdout_thread"] = None
        session["stderr_thread"] = None
        session["active_turn"] = None
        session["lock"] = threading.RLock()
        self._sessions[session["session_id"]] = session
        return self._public_session_state(session)

    def _command(self, session):
        cmd = [
            os.environ.get("BROKE_CLAUDE_BIN", "claude"),
            "-p",
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-partial-messages",
            "--replay-user-messages",
            "--session-id",
            session["session_id"],
        ]
        if session.get("model"):
            cmd.extend(["--model", session["model"]])
        return cmd

    def _ensure_process(self, session):
        proc = session.get("proc")
        if proc and proc.poll() is None:
            return
        proc = subprocess.Popen(
            self._command(session),
            cwd=session.get("cwd") or os.getcwd(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        session["proc"] = proc
        session["status"] = "running"
        session["started_at"] = iso_now()
        session["stdout_thread"] = threading.Thread(target=self._stdout_loop, args=(session,), daemon=True)
        session["stderr_thread"] = threading.Thread(target=self._stderr_loop, args=(session,), daemon=True)
        session["stdout_thread"].start()
        session["stderr_thread"].start()
        self._persist_session(session)

    def _stdout_loop(self, session):
        proc = session["proc"]
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            self._handle_stdout_line(session, line.rstrip())
        active = session.get("active_turn")
        if active and not active["done"].is_set():
            active["error"] = active.get("error") or "claude_process_exited"
            active["done"].set()

    def _stderr_loop(self, session):
        proc = session["proc"]
        while True:
            line = proc.stderr.readline()
            if not line:
                break
            self._mark_warning(session, line.rstrip())

    def _handle_stdout_line(self, session, line):
        try:
            payload = json.loads(line)
        except Exception:
            self._mark_warning(session, f"unparsed_stdout:{line[:200]}")
            return
        if payload.get("session_id"):
            session["session_id"] = payload["session_id"]
        if payload.get("type") == "system" and payload.get("subtype") == "init":
            session["status"] = "ready"
            session["claude_model"] = payload.get("model")
            self._mark_startup_canary(session, "passed")
            self._persist_session(session)
            return
        if payload.get("type") == "rate_limit_event":
            session["degraded"] = True
            session["degraded_reason"] = "upstream_rate_limit"
            self._persist_session(session)
            return
        active = session.get("active_turn")
        if payload.get("type") in {"assistant", "result"} and not active:
            self._record_quarantined_result(
                session,
                "late_result_without_active_turn",
                payload=payload,
            )
            return
        if not active:
            return
        if payload.get("type") == "assistant":
            active["assistant_messages"].append(payload)
            for block in payload.get("message", {}).get("content", []) or []:
                if block.get("type") == "text":
                    text = block.get("text", "")
                    active["text_parts"].append(text)
                    if text:
                        self._emit(active.get("event_cb"), "turn.delta", session, {"turnId": active.get("turn_id", ""), "delta": text})
        if payload.get("type") == "result":
            active["result_payload"] = payload
            text = payload.get("result") or "".join(active["text_parts"]).strip()
            active["final_text"] = text
            if payload.get("is_error"):
                active["error"] = payload.get("error") or payload.get("result") or "claude_prompt_failed"
            active["done"].set()

    def prompt(self, session_id, prompt, event_cb=None, timeout=180.0):
        session = self._sessions.get(session_id)
        if not session:
            raise ACPRuntimeError(f"unknown session: {session_id}")
        with session["lock"]:
            self._ensure_process(session)
            if session.get("active_turn") and not session["active_turn"]["done"].is_set():
                raise ACPRuntimeError("session already has an active prompt")
            turn_id = f"turn-{int(time.time() * 1000)}"
            active = self._begin_turn(
                session,
                turn_id,
                prompt,
                event_cb=event_cb,
                assistant_messages=[],
                text_parts=[],
                result_payload=None,
                final_text="",
            )
            self._persist_session(session)
            self._emit(event_cb, "turn.started", session, {"turnId": turn_id, "prompt": prompt})
            message = {"type": "user", "message": {"role": "user", "content": prompt}}
            try:
                session["proc"].stdin.write(json.dumps(message) + "\n")
                session["proc"].stdin.flush()
            except Exception as exc:
                session["active_turn"] = None
                raise ACPRuntimeError(f"failed to write to claude session: {exc}") from exc
        if not active["done"].wait(timeout):
            self.cancel(session_id)
            result = self._degraded_result("worker", "", "claude_prompt_timeout")
            self._mark_turn_completed(session, turn=active)
            self._emit(event_cb, "lane.timeout", session, {"turnId": turn_id, "reason": "claude_prompt_timeout"})
            self._emit(event_cb, "turn.completed", session, {"turnId": turn_id, "result": result})
            return {"session": self._public_session_state(session), "turnId": turn_id, "laneResult": result, "outputText": ""}

        text = active.get("final_text", "")
        error = active.get("error", "")
        result = canonical_lane_result("worker", provider=self.provider, runtime_binding=self.runtime_binding)
        result["summary"] = text
        if error:
            result["status"] = "failed"
            result["degraded"] = True
            result["degraded_reason"] = error
            session["degraded"] = True
            session["degraded_reason"] = error
            self._emit(event_cb, "lane.degraded", session, {"turnId": turn_id, "reason": error})
        session["last_output_text"] = text
        self._mark_turn_completed(session, turn=active)
        self._persist_session(session)
        self._emit(event_cb, "turn.completed", session, {"turnId": turn_id, "result": result})
        return {"session": self._public_session_state(session), "turnId": turn_id, "laneResult": result, "outputText": text}

    def cancel(self, session_id):
        session = self._sessions.get(session_id)
        if not session:
            raise ACPRuntimeError(f"unknown session: {session_id}")
        proc = session.get("proc")
        active = session.get("active_turn")
        if proc and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGINT)
            except Exception:
                try:
                    proc.send_signal(signal.SIGINT)
                except Exception:
                    pass
        if active and not active["done"].is_set():
            active["error"] = "cancelled"
            active["final_text"] = ""
            active["done"].set()
        session["status"] = "interrupted"
        self._persist_session(session)
        return {"session_id": session_id, "cancelled": True, "cancel_kind": self.cancel_kind}


class CodexCliAdapterRuntime(BaseRuntime):
    provider = "codex"
    runtime_binding = "cli_adapter"
    runtime_name = "CodexCliAdapterRuntime"
    cancel_kind = "turn_interrupt"
    supports_streaming = True
    supports_cancel = True
    supports_transport_cancel = True
    supports_live_interrupt = True
    supports_native_session_resume = True
    supports_tool_roundtrip = True
    session_persistence = "live_runtime"

    def new_session(self, cwd=None, model=None, mode=None, metadata=None):
        session = self._new_session_record(cwd=cwd, model=model, mode=mode, metadata=metadata)
        session.update(
            {
                "transport": "codex_app_server",
                "thread_id": "",
                "proc": None,
                "stdout_thread": None,
                "stderr_thread": None,
                "requests": {},
                "next_request_id": 1,
                "active_turn": None,
                "initialized": False,
                "lock": threading.RLock(),
            }
        )
        self._sessions[session["session_id"]] = session
        self._ensure_process(session)
        self._ensure_thread(session)
        self._persist_session(session)
        return self._public_session_state(session)

    def load_session(self, session_record):
        session = dict(session_record or {})
        session.setdefault("provider", self.provider)
        session.setdefault("runtime_binding", self.runtime_binding)
        session.setdefault("runtime_name", self.runtime_name)
        session.setdefault("transport", "codex_app_server")
        session.setdefault("thread_id", "")
        session["proc"] = None
        session["stdout_thread"] = None
        session["stderr_thread"] = None
        session["requests"] = {}
        session["next_request_id"] = 1
        session["active_turn"] = None
        session["initialized"] = False
        session["lock"] = threading.RLock()
        self._sessions[session["session_id"]] = session
        self._ensure_process(session)
        self._ensure_thread(session, resume=bool(session.get("thread_id")))
        return self._public_session_state(session)

    def _command(self, session):
        cmd = [os.environ.get("BROKE_CODEX_BIN", "codex"), "app-server"]
        if session.get("model"):
            cmd.extend(["-c", f'model="{session["model"]}"'])
        return cmd

    def _ensure_process(self, session):
        proc = session.get("proc")
        if proc and proc.poll() is None:
            return
        proc = subprocess.Popen(
            self._command(session),
            cwd=session.get("cwd") or os.getcwd(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        session["proc"] = proc
        session["status"] = "running"
        session["stdout_thread"] = threading.Thread(target=self._stdout_loop, args=(session,), daemon=True)
        session["stderr_thread"] = threading.Thread(target=self._stderr_loop, args=(session,), daemon=True)
        session["stdout_thread"].start()
        session["stderr_thread"].start()
        self._send_request(session, "initialize", {"clientInfo": {"name": "broke-acp", "version": "1"}, "capabilities": {}}, timeout=10)
        session["initialized"] = True
        self._mark_startup_canary(session, "passed")
        self._persist_session(session)

    def _ensure_thread(self, session, resume=False):
        if resume and session.get("thread_id"):
            response = self._send_request(session, "thread/resume", {"threadId": session["thread_id"]}, timeout=15)
        else:
            response = self._send_request(session, "thread/start", {"cwd": session.get("cwd") or os.getcwd()}, timeout=15)
        thread = response.get("thread", {})
        session["thread_id"] = thread.get("id") or session.get("thread_id", "")
        session["status"] = "ready"
        self._persist_session(session)

    def _stdout_loop(self, session):
        proc = session["proc"]
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            self._handle_stdout_line(session, line.rstrip())
        active = session.get("active_turn")
        if active and not active["done"].is_set():
            active["error"] = active.get("error") or "codex_process_exited"
            active["done"].set()

    def _stderr_loop(self, session):
        proc = session["proc"]
        while True:
            line = proc.stderr.readline()
            if not line:
                break
            self._mark_warning(session, line.rstrip())

    def _send_request(self, session, method, params, timeout=30):
        with session["lock"]:
            request_id = session["next_request_id"]
            session["next_request_id"] += 1
            waiter = queue.Queue(maxsize=1)
            session["requests"][request_id] = waiter
            payload = {"id": request_id, "method": method, "params": params}
            session["proc"].stdin.write(json.dumps(payload) + "\n")
            session["proc"].stdin.flush()
        try:
            response = waiter.get(timeout=timeout)
        except queue.Empty as exc:
            session["requests"].pop(request_id, None)
            raise ACPRuntimeError(f"codex request timed out: {method}") from exc
        if "error" in response:
            raise ACPRuntimeError(response["error"].get("message", f"codex request failed: {method}"))
        return response.get("result", {})

    def _handle_stdout_line(self, session, line):
        try:
            payload = json.loads(line)
        except Exception:
            self._mark_warning(session, f"unparsed_stdout:{line[:200]}")
            return
        if "id" in payload:
            waiter = session["requests"].pop(payload["id"], None)
            if waiter:
                waiter.put(payload)
            return
        method = payload.get("method")
        params = payload.get("params", {})
        if method == "thread/started":
            thread = params.get("thread", {})
            if thread.get("id"):
                session["thread_id"] = thread["id"]
                self._persist_session(session)
            return
        if method == "mcpServer/startupStatus/updated":
            if params.get("status") == "failed":
                self._mark_warning(session, f"mcp_startup_failed:{params.get('name')}:{params.get('error')}")
            return
        active = session.get("active_turn")
        if method in {"item/agentMessage/delta", "turn/completed"} and not active:
            self._record_quarantined_result(
                session,
                "late_result_without_active_turn",
                payload=payload,
                remote_turn_id=str((params.get("turn") or {}).get("id", "") or params.get("turnId", "")),
            )
            return
        if not active:
            return
        if method == "item/agentMessage/delta":
            delta = params.get("delta", "")
            if delta:
                active["text_parts"].append(delta)
                self._emit(active.get("event_cb"), "turn.delta", session, {"turnId": active.get("turn_id", ""), "delta": delta})
        elif method == "item/completed":
            item = params.get("item", {})
            if item.get("type") == "agentMessage" and item.get("text"):
                active["completed_messages"].append(item.get("text", ""))
        elif method == "turn/completed":
            turn = params.get("turn", {})
            remote_turn_id = str(turn.get("id", "") or "")
            if remote_turn_id and remote_turn_id in set(session.get("completed_turn_ids", [])):
                self._record_quarantined_result(
                    session,
                    "duplicate_completed_turn",
                    payload=payload,
                    turn_id=active.get("turn_id", ""),
                    remote_turn_id=remote_turn_id,
                    generation=active.get("generation"),
                )
                return
            active["status"] = turn.get("status", "completed")
            active["remote_turn_id"] = remote_turn_id or active.get("remote_turn_id", "")
            active["final_text"] = "".join(active["text_parts"]) or "\n".join(active["completed_messages"]).strip()
            if turn.get("error"):
                active["error"] = str(turn["error"])
            active["done"].set()

    def prompt(self, session_id, prompt, event_cb=None, timeout=240.0):
        session = self._sessions.get(session_id)
        if not session:
            raise ACPRuntimeError(f"unknown session: {session_id}")
        with session["lock"]:
            self._ensure_process(session)
            if not session.get("thread_id"):
                self._ensure_thread(session)
            if session.get("active_turn") and not session["active_turn"]["done"].is_set():
                raise ACPRuntimeError("session already has an active prompt")
            turn = self._begin_turn(
                session,
                "",
                prompt,
                event_cb=event_cb,
                text_parts=[],
                completed_messages=[],
                final_text="",
                status="inProgress",
                remote_turn_id="",
            )
            result = self._send_request(
                session,
                "turn/start",
                {"threadId": session["thread_id"], "input": [{"type": "text", "text": prompt}]},
                timeout=30,
            )
            turn_id = result.get("turn", {}).get("id", "")
            turn["turn_id"] = turn_id
            turn["remote_turn_id"] = turn_id
            session["last_turn_id"] = turn_id
            self._persist_session(session)
            self._emit(event_cb, "turn.started", session, {"turnId": turn_id, "prompt": prompt})
        if not turn["done"].wait(timeout):
            self.cancel(session_id)
            result = self._degraded_result("worker", "", "codex_prompt_timeout")
            self._mark_turn_completed(session, turn=turn, remote_turn_id=turn.get("remote_turn_id", ""))
            self._emit(event_cb, "lane.timeout", session, {"turnId": turn_id, "reason": "codex_prompt_timeout"})
            self._emit(event_cb, "turn.completed", session, {"turnId": turn_id, "result": result})
            return {"session": self._public_session_state(session), "turnId": turn_id, "laneResult": result, "outputText": ""}
        text = turn.get("final_text", "")
        error = turn.get("error", "")
        result = canonical_lane_result("worker", provider=self.provider, runtime_binding=self.runtime_binding)
        result["summary"] = text
        if error:
            result["status"] = "failed"
            result["degraded"] = True
            result["degraded_reason"] = error
            session["degraded"] = True
            session["degraded_reason"] = error
            self._emit(event_cb, "lane.degraded", session, {"turnId": turn_id, "reason": error})
        session["last_output_text"] = text
        self._mark_turn_completed(session, turn=turn, remote_turn_id=turn.get("remote_turn_id", ""))
        self._persist_session(session)
        self._emit(event_cb, "turn.completed", session, {"turnId": turn_id, "result": result})
        return {"session": self._public_session_state(session), "turnId": turn_id, "laneResult": result, "outputText": text}

    def cancel(self, session_id):
        session = self._sessions.get(session_id)
        if not session:
            raise ACPRuntimeError(f"unknown session: {session_id}")
        active = session.get("active_turn")
        if active and active.get("turn_id"):
            try:
                self._send_request(
                    session,
                    "turn/interrupt",
                    {"threadId": session.get("thread_id", ""), "turnId": active["turn_id"]},
                    timeout=10,
                )
            except Exception:
                pass
        if active and not active["done"].is_set():
            active["error"] = "cancelled"
            active["done"].set()
        session["status"] = "interrupted"
        self._persist_session(session)
        return {"session_id": session_id, "cancelled": True, "cancel_kind": self.cancel_kind}


class GeminiNativeAcpRuntime(HeadlessAdapterRuntime):
    provider = "gemini"
    runtime_binding = "native_acp"
    runtime_name = "GeminiNativeAcpRuntime"
    cancel_kind = "native_transport"
    supports_transport_cancel = True
    supports_live_interrupt = True
    supports_native_session_resume = True
    supports_tool_roundtrip = True
    session_persistence = "live_runtime"


class OpenRouterHeadlessRuntime(HeadlessAdapterRuntime):
    provider = "openrouter"
    runtime_name = "OpenRouterHeadlessRuntime"
    api_base_env = "BROKE_OPENROUTER_API_BASE"
    api_key_env = "OPENROUTER_API_KEY"
    default_api_base = "https://openrouter.ai/api/v1"
    default_model = "qwen/qwen3.6-plus:free"

    def _resolve_headers(self):
        headers = super()._resolve_headers()
        headers.setdefault("HTTP-Referer", "https://github.com/B-A-M-N/BrokeLLM")
        headers.setdefault("X-Title", "BrokeLLM")
        return headers


class GroqHeadlessRuntime(HeadlessAdapterRuntime):
    provider = "groq"
    runtime_name = "GroqHeadlessRuntime"
    api_base_env = "BROKE_GROQ_API_BASE"
    api_key_env = "GROQ_API_KEY"
    default_api_base = "https://api.groq.com/openai/v1"
    default_model = "moonshotai/kimi-k2-instruct"


class CerebrasHeadlessRuntime(HeadlessAdapterRuntime):
    provider = "cerebras"
    runtime_name = "CerebrasHeadlessRuntime"
    api_base_env = "BROKE_CEREBRAS_API_BASE"
    api_key_env = "CEREBRAS_API_KEY"
    default_api_base = "https://api.cerebras.ai/v1"
    default_model = "qwen-3-235b-a22b-instruct-2507"


class LocalHeadlessRuntime(HeadlessAdapterRuntime):
    provider = "local"
    runtime_name = "LocalHeadlessRuntime"
    api_base_env = "BROKE_LOCAL_API_BASE"
    api_key_env = "BROKE_LOCAL_API_KEY"
    default_api_base = "http://127.0.0.1:11434/v1"

    def _resolve_headers(self):
        headers = {"Content-Type": "application/json"}
        token = str(os.environ.get(self.api_key_env, "")).strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers


RUNTIME_CLASS_MAP = {
    "GeminiNativeAcpRuntime": GeminiNativeAcpRuntime,
    "ClaudeAgentAcpShimRuntime": ClaudeAgentAcpShimRuntime,
    "CodexAcpShimRuntime": CodexAcpShimRuntime,
    "ClaudeCliAdapterRuntime": ClaudeCliAdapterRuntime,
    "CodexCliAdapterRuntime": CodexCliAdapterRuntime,
    "OpenRouterHeadlessRuntime": OpenRouterHeadlessRuntime,
    "GroqHeadlessRuntime": GroqHeadlessRuntime,
    "CerebrasHeadlessRuntime": CerebrasHeadlessRuntime,
    "LocalHeadlessRuntime": LocalHeadlessRuntime,
}


class RuntimeRegistry:
    def __init__(self, config=None, sessions_root=None):
        self.config = config or default_runtime_registry()
        self.sessions_root = Path(sessions_root or Path.cwd() / ".runtime" / "acp" / "sessions")
        self._instances = {}

    def for_provider(self, provider):
        provider = str(provider or "").strip().lower()
        runtime_cfg = self.config.get(provider)
        if not runtime_cfg:
            raise ACPRuntimeError(f"unknown provider runtime: {provider}")
        runtime_class_name = runtime_cfg.get("runtime_class")
        runtime_cls = RUNTIME_CLASS_MAP.get(runtime_class_name)
        if runtime_cls is None:
            raise ACPRuntimeError(f"unresolved runtime class: {runtime_class_name}")
        instance = self._instances.get(provider)
        if instance is None:
            instance = runtime_cls(self.sessions_root)
            self._instances[provider] = instance
        return instance
