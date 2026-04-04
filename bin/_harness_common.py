#!/usr/bin/env python3
"""Shared harness event helpers."""

from __future__ import annotations

import json
import os
import pathlib
import time
from datetime import datetime, timezone

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


def iso_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(text):
    import hashlib

    return hashlib.sha256(text.encode()).hexdigest()


def canonical_json(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def append_event(path, run_id, event_type, phase, actor_kind, actor_id, payload=None, artifact_refs=None):
    payload = payload or {}
    artifact_refs = artifact_refs or []
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    previous_hash = ""
    with path.open("a+", encoding="utf-8") as fh:
        if fcntl is not None:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        fh.seek(0)
        lines = [line for line in fh.read().splitlines() if line.strip()]
        if lines:
            try:
                previous_hash = json.loads(lines[-1]).get("event_hash", "")
            except Exception:
                previous_hash = ""
        event = {
            "event_id": f"evt_{sha256_text(f'{run_id}:{event_type}:{time.time()}')[:12]}",
            "run_id": run_id,
            "timestamp": iso_now(),
            "event_type": event_type,
            "phase": phase,
            "actor": {"kind": actor_kind, "id": actor_id},
            "payload": payload,
            "artifact_refs": artifact_refs,
            "prev_event_hash": previous_hash or None,
        }
        event["event_hash"] = sha256_text(
            canonical_json(
                {
                    "prev_event_hash": previous_hash,
                    "event": {
                        "run_id": run_id,
                        "timestamp": event["timestamp"],
                        "event_type": event_type,
                        "phase": phase,
                        "actor": event["actor"],
                        "payload": payload,
                        "artifact_refs": artifact_refs,
                    },
                }
            )
        )
        fh.seek(0, os.SEEK_END)
        fh.write(json.dumps(event) + "\n")
        fh.flush()
        if fcntl is not None:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    try:
        path.chmod(0o600)
    except Exception:
        pass
    return event
