#!/usr/bin/env python3
"""Structured per-run message channel helpers."""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

from _harness_common import atomic_write_json, canonical_json, read_json, sha256_text


def iso_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def append_message(path, run_id, channel, kind, payload=None):
    payload = payload or {}
    path = pathlib.Path(path)
    if not str(path):
        return {}
    if path.name in {"", "."}:
        return {}
    state_file = path.with_suffix(".state.json")
    state = read_json(state_file, {"last_seq": 0, "last_hash": ""})
    seq = int(state.get("last_seq", 0) or 0) + 1
    prev_hash = str(state.get("last_hash", "") or "")
    message = {
        "run_id": run_id,
        "channel": channel,
        "msg_seq": seq,
        "timestamp": iso_now(),
        "kind": kind,
        "payload": payload,
        "integrity": {"prev_hash": prev_hash or None},
    }
    message_hash = sha256_text(
        canonical_json(
            {
                "run_id": run_id,
                "channel": channel,
                "msg_seq": seq,
                "timestamp": message["timestamp"],
                "kind": kind,
                "payload": payload,
                "prev_hash": prev_hash,
            }
        )
    )
    message["integrity"]["hash"] = message_hash
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(message) + "\n")
    atomic_write_json(state_file, {"last_seq": seq, "last_hash": message_hash})
    try:
        path.chmod(0o600)
    except Exception:
        pass
    return message


def read_messages(path, limit=50, channel=None):
    path = pathlib.Path(path)
    if path.name in {"", "."}:
        return []
    if not path.exists():
        return []
    rows = []
    for raw in path.read_text().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except Exception:
            continue
        if channel and row.get("channel") != channel:
            continue
        rows.append(row)
    return rows[-limit:]
