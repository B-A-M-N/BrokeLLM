#!/usr/bin/env python3
"""Broke-owned ACP front door."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from pathlib import Path

BIN_DIR = Path(__file__).resolve().parent
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))

from _acp_lane import ACP_LANE_EVENTS, ACP_LANE_METHODS, default_runtime_registry
from _acp_runtime import ACPRuntimeError, RuntimeRegistry
from _harness_common import atomic_write_json, iso_now, read_json


class ACPGateway:
    def __init__(self, sessions_root=None, registry_config=None):
        self.sessions_root = Path(sessions_root or Path.cwd() / ".runtime" / "acp" / "sessions")
        self.sessions_root.mkdir(parents=True, exist_ok=True)
        self.registry = RuntimeRegistry(registry_config or default_runtime_registry(), sessions_root=self.sessions_root)
        self._output_lock = threading.Lock()

    def session_path(self, session_id):
        return self.sessions_root / f"{session_id}.json"

    def load_session_record(self, session_id):
        record = read_json(self.session_path(session_id), {})
        if not record:
            raise ACPRuntimeError(f"unknown session: {session_id}")
        return record

    def save_session_record(self, record):
        atomic_write_json(self.session_path(record["session_id"]), record)

    def emit(self, payload, outstream=sys.stdout):
        with self._output_lock:
            outstream.write(json.dumps(payload) + "\n")
            outstream.flush()

    def notify(self, method, params, outstream=sys.stdout):
        self.emit({"method": method, "params": params}, outstream=outstream)

    def event_callback(self, outstream):
        def _cb(event_type, payload):
            self.notify(event_type, payload, outstream=outstream)
        return _cb

    def handle_call(self, message, outstream=sys.stdout):
        request_id = message.get("id")
        method = message.get("method")
        params = message.get("params") or {}
        try:
            result = self._dispatch(method, params, outstream=outstream)
            if request_id is not None:
                self.emit({"id": request_id, "result": result}, outstream=outstream)
        except Exception as exc:
            if request_id is not None:
                self.emit({"id": request_id, "error": {"code": -32000, "message": str(exc)}}, outstream=outstream)

    def _dispatch(self, method, params, outstream=sys.stdout):
        if method == "initialize":
            return {
                "name": "BrokeLLM ACP",
                "version": "1",
                "methods": ACP_LANE_METHODS,
                "events": ACP_LANE_EVENTS,
                "providers": sorted(default_runtime_registry().keys()),
                "hardening": {
                    "startup_canary_required": True,
                    "watchdog_enabled": True,
                    "fail_closed_on_unknown_runtime": True,
                },
            }
        if method == "newSession":
            provider = str(params.get("provider", "gemini")).strip().lower()
            runtime = self.registry.for_provider(provider)
            session = runtime.new_session(
                cwd=params.get("cwd") or os.getcwd(),
                model=params.get("model"),
                mode=params.get("mode"),
                metadata=params,
            )
            session["gateway_created_at"] = iso_now()
            self.save_session_record(session)
            self.notify("session.started", {"sessionId": session["session_id"], "provider": provider}, outstream=outstream)
            return session
        if method == "loadSession":
            session_id = params.get("sessionId", "")
            record = self.load_session_record(session_id)
            runtime = self.registry.for_provider(record.get("provider"))
            session = runtime.load_session(record)
            self.save_session_record(session)
            self.notify("session.loaded", {"sessionId": session["session_id"], "provider": session.get("provider")}, outstream=outstream)
            return session
        if method == "getSessionState":
            session_id = params.get("sessionId", "")
            record = self.load_session_record(session_id)
            runtime = self.registry.for_provider(record.get("provider"))
            return runtime.get_session_state(session_id)
        if method == "prompt":
            session_id = params.get("sessionId", "")
            prompt = params.get("prompt", "")
            role = params.get("laneRole", "worker")
            record = self.load_session_record(session_id)
            runtime = self.registry.for_provider(record.get("provider"))
            result = runtime.prompt(session_id, prompt, event_cb=self.event_callback(outstream), timeout=float(params.get("timeout", 180.0)))
            session_state = result["session"]
            session_state["updated_at"] = iso_now()
            self.save_session_record(session_state)
            lane_result = dict(result["laneResult"])
            lane_result["lane_role"] = role
            return {
                "sessionId": session_id,
                "turnId": result.get("turnId", ""),
                "outputText": result.get("outputText", ""),
                "laneResult": lane_result,
                "session": session_state,
            }
        if method == "cancel":
            session_id = params.get("sessionId", "")
            record = self.load_session_record(session_id)
            runtime = self.registry.for_provider(record.get("provider"))
            result = runtime.cancel(session_id)
            state = runtime.get_session_state(session_id)
            self.save_session_record(state)
            self.notify("lane.cancelled", {"sessionId": session_id, "provider": record.get("provider")}, outstream=outstream)
            return result
        if method == "setSessionMode":
            session_id = params.get("sessionId", "")
            record = self.load_session_record(session_id)
            record["mode"] = params.get("mode", record.get("mode", "default"))
            record["updated_at"] = iso_now()
            self.save_session_record(record)
            return record
        if method == "closeSession":
            session_id = params.get("sessionId", "")
            record = self.load_session_record(session_id)
            runtime = self.registry.for_provider(record.get("provider"))
            result = runtime.close(session_id)
            record["status"] = "closed"
            record["updated_at"] = iso_now()
            self.save_session_record(record)
            return result
        if method == "heartbeat":
            session_id = params.get("sessionId", "")
            if session_id:
                record = self.load_session_record(session_id)
                runtime = self.registry.for_provider(record.get("provider"))
                state = runtime.get_session_state(session_id)
                self.save_session_record(state)
                return {
                    "ok": True,
                    "timestamp": iso_now(),
                    "sessionId": session_id,
                    "watchdog": state.get("transport_health", {}),
                    "capabilities": state.get("capabilities", {}),
                }
            return {"ok": True, "timestamp": iso_now()}
        raise ACPRuntimeError(f"unknown method: {method}")

    def serve_forever(self, instream=sys.stdin, outstream=sys.stdout):
        for raw in instream:
            raw = raw.strip()
            if not raw:
                continue
            try:
                message = json.loads(raw)
            except Exception as exc:
                self.emit({"error": {"code": -32700, "message": f"invalid json: {exc}"}}, outstream=outstream)
                continue
            threading.Thread(target=self.handle_call, args=(message, outstream), daemon=True).start()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run BrokeLLM's ACP front door on stdio")
    parser.add_argument("--sessions-root", default=str(Path.cwd() / ".runtime" / "acp" / "sessions"))
    args = parser.parse_args(argv)
    gateway = ACPGateway(sessions_root=args.sessions_root)
    gateway.serve_forever()


if __name__ == "__main__":
    main()
