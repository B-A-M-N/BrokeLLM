#!/usr/bin/env python3
"""BrokeLLM runtime proxy with live key rotation policy."""

import copy
import http.client
import json
import os
import pathlib
import socketserver
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

BIN_DIR = pathlib.Path(__file__).resolve().parent
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))

from _fs_common import locked_file

DIR = pathlib.Path(__file__).parent.parent
DEPLOYMENTS = DIR / ".deployments.json"
ROTATION_POLICY = DIR / ".rotation.json"
KEY_STATE = DIR / ".key_state.json"
ROTATION_LOG = DIR / ".rotation.log"
MAPPING = DIR / ".mapping.json"
TEAMS = DIR / ".teams.json"
PROFILES = DIR / ".profiles.json"
CLIENT_BINDINGS = DIR / ".client_bindings.json"
MODEL_POLICY = DIR / ".model_policy.json"
MODEL_STATE = DIR / ".model_state.json"

CLAUDE_SLOTS = ["sonnet", "opus", "haiku", "custom"]
SEMANTIC_SLOTS = ["subagent"]
CODEX_SLOTS = [
    "gpt54",
    "gpt54mini",
    "gpt53codex",
    "gpt52codex",
    "gpt52",
    "gpt51codexmax",
    "gpt51codexmini",
]
VALID_SLOTS = CLAUDE_SLOTS + SEMANTIC_SLOTS + CODEX_SLOTS

EXCLUDED_RESPONSE_HEADERS = {
    "connection",
    "content-length",
    "date",
    "server",
    "transfer-encoding",
}

STATE_LOCK = threading.Lock()
CLIENT_TOKEN = os.environ.get("BROKE_CLIENT_TOKEN", "")
INTERNAL_TOKEN = os.environ.get("BROKE_INTERNAL_MASTER_KEY", "")
PROXY_UNIX_SOCKET = os.environ.get("BROKE_PROXY_UNIX_SOCKET", "")
LOCAL_ONLY_PATH_PREFIXES = ("/health",)
MAX_REQUEST_BYTES = 1024 * 1024
AUTH_WINDOW_SECONDS = 60
AUTH_MAX_FAILURES = 20
AUTH_FAILURES = {}
AUTH_LOCK = threading.Lock()


def read_json(path, default):
    if not path.exists():
        return default
    with locked_file(path, exclusive=False):
        try:
            return json.loads(path.read_text())
        except Exception:
            return default


def atomic_write_json(path, data):
    with locked_file(path, exclusive=True):
        tmp = path.with_name(f"{path.name}.tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n")
        tmp.replace(path)
        try:
            path.chmod(0o600)
        except Exception:
            pass

def load_deployments():
    return read_json(DEPLOYMENTS, {})


def load_mapping():
    return read_json(MAPPING, {})


def load_teams():
    return read_json(TEAMS, {})


def load_profiles():
    return read_json(PROFILES, {})


def load_client_bindings():
    data = read_json(CLIENT_BINDINGS, {"tokens": {}})
    if "tokens" not in data:
        data["tokens"] = {}
    return data


def load_policy():
    policy = read_json(ROTATION_POLICY, {})
    if "generation" not in policy:
        policy["generation"] = 1
    if "providers" not in policy:
        policy["providers"] = {}
    return policy


def load_state():
    state = read_json(KEY_STATE, {})
    if "keys" not in state:
        state["keys"] = {}
    if "providers" not in state:
        state["providers"] = {}
    return state


def load_model_policy():
    policy = read_json(MODEL_POLICY, {})
    if "generation" not in policy:
        policy["generation"] = 1
    if "lanes" not in policy:
        policy["lanes"] = {}
    return policy


def load_model_state():
    state = read_json(MODEL_STATE, {})
    if "models" not in state:
        state["models"] = {}
    if "lanes" not in state:
        state["lanes"] = {}
    return state


def slot_allowed(slot, mapping):
    access = mapping.get("_access", {})
    allowed_slots = access.get("allowed_slots")
    if allowed_slots is None:
        return True
    return slot in allowed_slots


def team_mapping(team_name, teams=None):
    teams = teams or load_teams()
    if team_name not in teams:
        return None
    team = teams[team_name]
    if "slots" in team:
        slots = team.get("slots", {})
        fallbacks = team.get("fallbacks", {})
        backend_fallbacks = team.get("backend_fallbacks", {})
        lane_fallback_targets = team.get("lane_fallback_targets", {})
        access = team.get("access", {})
    else:
        slots, fallbacks, backend_fallbacks, lane_fallback_targets, access = team, {}, {}, {}, {}
    mapping = dict(slots)
    if fallbacks:
        mapping["_fallbacks"] = fallbacks
    if backend_fallbacks:
        mapping["_backend_fallbacks"] = backend_fallbacks
    if lane_fallback_targets:
        mapping["_lane_fallback_targets"] = lane_fallback_targets
    if access:
        mapping["_access"] = access
    return mapping


def effective_mapping_for_profile(profile_name, profiles=None, teams=None):
    profiles = profiles or load_profiles()
    teams = teams or load_teams()
    profile = profiles.get(profile_name)
    if not profile:
        return None
    mapping = team_mapping(profile.get("team", ""), teams=teams)
    if mapping is None:
        return None
    access = profile.get("access", {})
    if access:
        merged_access = dict(mapping.get("_access", {}))
        merged_access.update(access)
        mapping["_access"] = merged_access
    return mapping


def log_event(event):
    event = redact_event(event)
    with ROTATION_LOG.open("a") as f:
        f.write(json.dumps(event) + "\n")
    try:
        ROTATION_LOG.chmod(0o600)
    except Exception:
        pass


def now_ts():
    return int(time.time())


def _key_ref(name):
    if not name:
        return ""
    import hashlib

    return f"key_{hashlib.sha256(str(name).encode()).hexdigest()[:10]}"


def redact_event(event):
    if not isinstance(event, dict):
        return event
    redacted = {}
    for key, value in event.items():
        if key == "key_name":
            redacted["key_ref"] = _key_ref(value)
            continue
        redacted[key] = value
    return redacted


def _prune_auth_failures(ts):
    stale_before = ts - AUTH_WINDOW_SECONDS
    expired = [addr for addr, info in AUTH_FAILURES.items() if info.get("reset_at", 0) <= stale_before]
    for addr in expired:
        AUTH_FAILURES.pop(addr, None)


def _record_auth_failure(addr):
    ts = now_ts()
    with AUTH_LOCK:
        _prune_auth_failures(ts)
        entry = AUTH_FAILURES.get(addr)
        if not entry or entry.get("reset_at", 0) <= ts:
            entry = {"count": 0, "reset_at": ts + AUTH_WINDOW_SECONDS}
        entry["count"] += 1
        AUTH_FAILURES[addr] = entry
        return entry["count"] > AUTH_MAX_FAILURES


def _clear_auth_failures(addr):
    with AUTH_LOCK:
        AUTH_FAILURES.pop(addr, None)


def is_loopback(addr):
    if isinstance(addr, tuple):
        addr = addr[0]
    if not isinstance(addr, str):
        return True
    return addr in {"127.0.0.1", "::1", "localhost", ""}


def normalize_key_state(state):
    ts = now_ts()
    changed = False
    for key_name, info in state.get("keys", {}).items():
        if info.get("status") == "cooldown" and info.get("cooldown_until", 0) <= ts:
            info["status"] = "healthy"
            info["last_reason"] = "cooldown_expired"
            info["updated_at"] = ts
            changed = True
    return changed


def normalize_model_state(state):
    ts = now_ts()
    changed = False
    for label, info in state.get("models", {}).items():
        if info.get("status") == "cooldown" and info.get("cooldown_until", 0) <= ts:
            info["status"] = "healthy"
            info["last_reason"] = "cooldown_expired"
            info["updated_at"] = ts
            changed = True
    return changed


def key_available(info):
    status = info.get("status", "healthy")
    if status in {"blocked", "auth_failed"}:
        return False
    if status == "cooldown" and info.get("cooldown_until", 0) > now_ts():
        return False
    return True


def model_available(info):
    status = info.get("status", "healthy")
    if status in {"blocked", "incompatible"}:
        return False
    if status == "cooldown" and info.get("cooldown_until", 0) > now_ts():
        return False
    return True


def provider_policy(policy, provider, deployments):
    cfg = policy.get("providers", {}).get(provider, {})
    order = cfg.get("order") or [d["key_name"] for d in deployments]
    return {
        "mode": cfg.get("mode", "rotate_on_rate_limit"),
        "order": order,
        "cooldown_seconds": int(cfg.get("cooldown_seconds", 300)),
        "max_retries": max(1, int(cfg.get("max_retries", max(1, len(deployments))))),
    }


def infer_slot(model_label, mapping):
    for slot in VALID_SLOTS:
        entry = mapping.get(slot)
        if entry and entry.get("label") == model_label:
            return slot
    return None


def infer_slot_from_active_mapping_identity(model_label, mapping):
    if not model_label:
        return None
    normalized = str(model_label).strip().lower()
    for slot in VALID_SLOTS:
        entry = mapping.get(slot)
        if not entry:
            continue
        model = str(entry.get("model", "")).strip().lower()
        if model and normalized == model:
            return slot
        provider = str(entry.get("provider", "")).strip().lower()
        if provider and model and normalized == f"{provider}/{model}":
            return slot
    return None


def infer_slot_from_client_model(model_label):
    if not model_label:
        return None
    normalized = str(model_label).strip().lower()
    codex_slot_aliases = {
        "gpt54": "gpt54",
        "gpt-5.4": "gpt54",
        "gpt54mini": "gpt54mini",
        "gpt-5.4-mini": "gpt54mini",
        "gpt53codex": "gpt53codex",
        "gpt-5.3-codex": "gpt53codex",
        "gpt52codex": "gpt52codex",
        "gpt-5.2-codex": "gpt52codex",
        "gpt52": "gpt52",
        "gpt-5.2": "gpt52",
        "gpt51codexmax": "gpt51codexmax",
        "gpt-5.1-codex-max": "gpt51codexmax",
        "gpt51codexmini": "gpt51codexmini",
        "gpt-5.1-codex-mini": "gpt51codexmini",
    }
    if normalized in codex_slot_aliases:
        return codex_slot_aliases[normalized]
    if normalized.startswith("claude-sonnet") or "sonnet" in normalized:
        return "sonnet"
    if normalized.startswith("claude-opus") or "opus" in normalized:
        return "opus"
    if normalized.startswith("claude-haiku") or "haiku" in normalized:
        return "haiku"
    if normalized == "custom" or normalized.startswith("claude-custom"):
        return "custom"
    if normalized == "subagent":
        return "subagent"
    return None


def resolve_requested_model(model_label, deployments_map, mapping):
    if not model_label:
        return None, None
    if model_label in deployments_map:
        slot = infer_slot(model_label, mapping)
        if slot and not slot_allowed(slot, mapping):
            return None, None
        return model_label, slot
    slot = infer_slot(model_label, mapping)
    if slot and mapping.get(slot) and slot_allowed(slot, mapping):
        label = mapping[slot].get("label")
        if label in deployments_map:
            return label, slot
    slot = infer_slot_from_client_model(model_label)
    if slot and mapping.get(slot) and slot_allowed(slot, mapping):
        label = mapping[slot].get("label")
        if label in deployments_map:
            return label, slot
    slot = infer_slot_from_active_mapping_identity(model_label, mapping)
    if slot and mapping.get(slot) and slot_allowed(slot, mapping):
        label = mapping[slot].get("label")
        if label in deployments_map:
            return label, slot
    return None, None


def lane_model_policy(model_policy, slot, current_label):
    cfg = model_policy.get("lanes", {}).get(slot, {})
    order = list(cfg.get("order") or [current_label])
    if current_label not in order:
        order.insert(0, current_label)
    return {
        "mode": cfg.get("mode", "priority_order"),
        "order": order,
        "cooldown_seconds": int(cfg.get("cooldown_seconds", 300)),
        "max_retries": max(1, int(cfg.get("max_retries", max(1, len(order))))),
    }


def ordered_deployments(provider, deployments, policy_cfg, state):
    by_key = {d["key_name"]: d for d in deployments}
    ordered = [by_key[key] for key in policy_cfg["order"] if key in by_key]
    ordered.extend(d for d in deployments if d["key_name"] not in policy_cfg["order"])

    available = []
    unavailable = []
    for dep in ordered:
        info = state["keys"].get(dep["key_name"], {})
        if key_available(info):
            available.append(dep)
        else:
            unavailable.append(dep)

    mode = policy_cfg["mode"]
    provider_state = state["providers"].setdefault(provider, {})
    if mode == "round_robin" and available:
        idx = provider_state.get("round_robin_index", 0) % len(available)
        available = available[idx:] + available[:idx]
        provider_state["round_robin_index"] = (idx + 1) % len(available)
    elif mode == "sticky":
        sticky_key = provider_state.get("sticky_key")
        if sticky_key:
            available.sort(key=lambda dep: dep["key_name"] != sticky_key)
    elif mode == "manual_pin":
        pinned = policy_cfg["order"][:1]
        available = [dep for dep in available if dep["key_name"] in pinned]

    return available + unavailable


def ordered_models(slot, current_label, deployments_map, model_policy, model_state):
    policy_cfg = lane_model_policy(model_policy, slot, current_label)
    ordered = [label for label in policy_cfg["order"] if label in deployments_map]
    ordered.extend(label for label in deployments_map if label not in ordered)

    available = []
    unavailable = []
    for label in ordered:
        info = model_state["models"].get(label, {})
        if model_available(info):
            available.append(label)
        else:
            unavailable.append(label)

    mode = policy_cfg["mode"]
    lane_state = model_state["lanes"].setdefault(slot, {})
    if mode == "round_robin" and available:
        idx = lane_state.get("round_robin_index", 0) % len(available)
        available = available[idx:] + available[:idx]
        lane_state["round_robin_index"] = (idx + 1) % len(available)
    elif mode == "sticky":
        sticky_label = lane_state.get("sticky_label")
        if sticky_label:
            available.sort(key=lambda label: label != sticky_label)
    elif mode == "manual_pin":
        pinned = policy_cfg["order"][:1]
        available = [label for label in available if label in pinned]

    return policy_cfg, available + unavailable


def update_key_status(key_name, generation, status, reason, cooldown_seconds=0):
    with STATE_LOCK:
        state = load_state()
        normalize_key_state(state)
        info = state["keys"].setdefault(key_name, {})
        info["status"] = status
        info["last_reason"] = reason
        info["updated_at"] = now_ts()
        info["generation"] = generation
        info["failures"] = int(info.get("failures", 0)) + (0 if status == "healthy" else 1)
        info["cooldown_until"] = now_ts() + cooldown_seconds if status == "cooldown" else 0
        atomic_write_json(KEY_STATE, state)


def update_model_status(model_label, generation, status, reason, cooldown_seconds=0):
    with STATE_LOCK:
        state = load_model_state()
        normalize_model_state(state)
        info = state["models"].setdefault(model_label, {})
        info["status"] = status
        info["last_reason"] = reason
        info["updated_at"] = now_ts()
        info["generation"] = generation
        info["failures"] = int(info.get("failures", 0)) + (0 if status == "healthy" else 1)
        info["cooldown_until"] = now_ts() + cooldown_seconds if status == "cooldown" else 0
        atomic_write_json(MODEL_STATE, state)


def mark_provider_use(provider, key_name):
    with STATE_LOCK:
        state = load_state()
        normalize_key_state(state)
        info = state["providers"].setdefault(provider, {})
        info["last_key"] = key_name
        info["last_used_at"] = now_ts()
        if info.get("sticky_key") != key_name:
            info["sticky_key"] = key_name
        atomic_write_json(KEY_STATE, state)


def mark_lane_model_use(slot, model_label):
    with STATE_LOCK:
        state = load_model_state()
        normalize_model_state(state)
        lane = state["lanes"].setdefault(slot, {})
        lane["last_model"] = model_label
        lane["last_used_at"] = now_ts()
        if lane.get("sticky_label") != model_label:
            lane["sticky_label"] = model_label
        atomic_write_json(MODEL_STATE, state)


def prepare_candidates(model_label, mapping=None):
    deployments_map = load_deployments()
    mapping = mapping or load_mapping()
    resolved_label, slot = resolve_requested_model(model_label, deployments_map, mapping)
    if resolved_label is None:
        return None, None, None, None, None
    model_label = resolved_label
    model_policy = load_model_policy()
    model_state = load_model_state()
    with STATE_LOCK:
        if normalize_model_state(model_state):
            atomic_write_json(MODEL_STATE, model_state)
    model_policy_cfg = None
    model_candidates = [model_label]
    if slot:
        model_policy_cfg, model_candidates = ordered_models(slot, model_label, deployments_map, model_policy, model_state)
        model_candidates = model_candidates[: model_policy_cfg["max_retries"]]

    policy = load_policy()
    state = load_state()
    with STATE_LOCK:
        if normalize_key_state(state):
            atomic_write_json(KEY_STATE, state)
    candidate_groups = []
    for label in model_candidates:
        deployments = deployments_map.get(label, [])
        if not deployments:
            continue
        provider = deployments[0]["provider"]
        policy_cfg = provider_policy(policy, provider, deployments)
        key_candidates = ordered_deployments(provider, deployments, policy_cfg, state)[: policy_cfg["max_retries"]]
        candidate_groups.append({
            "label": label,
            "provider": provider,
            "model_policy": model_policy_cfg,
            "key_policy": policy_cfg,
            "deployments": key_candidates,
        })
    if not candidate_groups:
        return None, None, None, None, None
    return policy, model_policy, slot, candidate_groups, state


def classify_error(status_code, body_text):
    if status_code == 429:
        return "rate_limit"
    if status_code in (401, 403):
        return "auth_failure"
    if status_code >= 500:
        return "upstream_error"
    if "timeout" in body_text.lower():
        return "timeout"
    return "http_error"


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _presented_client_token(self):
        auth = self.headers.get("Authorization", "")
        x_api_key = self.headers.get("x-api-key", "") or self.headers.get("api-key", "")
        if auth.startswith("Bearer "):
            return auth[len("Bearer "):]
        return x_api_key

    def _selected_profile_name(self):
        requested_profile = (self.headers.get("X-Broke-Profile", "") or "").strip()
        token = ProxyHandler._presented_client_token(self)
        bindings = load_client_bindings().get("tokens", {})
        bound = bindings.get(token, {})
        bound_profile = str(bound.get("profile", "")).strip()
        if bound_profile and requested_profile and requested_profile != bound_profile:
            return None, "bound_token_profile_mismatch"
        if requested_profile:
            return requested_profile, "header"
        if bound_profile:
            return bound_profile, "token_binding"
        return "", "default"

    def _request_mapping(self):
        profile_name, source = ProxyHandler._selected_profile_name(self)
        if not profile_name:
            if source == "bound_token_profile_mismatch":
                return None, None, source
            return load_mapping(), "", source
        mapping = effective_mapping_for_profile(profile_name)
        if mapping is None:
            return None, profile_name, "unknown_profile"
        return mapping, profile_name, source

    def _filter_models_outcome(self, outcome, mapping, profile_name=""):
        if outcome.get("status") != 200:
            return outcome
        try:
            payload = json.loads(outcome["body"].decode())
        except Exception:
            return outcome
        data = payload.get("data")
        if not isinstance(data, list):
            return outcome
        allowed_labels = {
            entry.get("label")
            for slot, entry in mapping.items()
            if not slot.startswith("_") and slot_allowed(slot, mapping)
        }
        payload["data"] = [item for item in data if item.get("id") in allowed_labels]
        filtered_body = json.dumps(payload).encode()
        headers = [(k, v) for k, v in outcome["headers"] if k.lower() != "content-length"]
        return {
            "status": outcome["status"],
            "reason": outcome["reason"],
            "headers": headers,
            "body": filtered_body,
            "profile_name": profile_name,
        }

    def _client_authorized(self):
        if any(self.path.startswith(prefix) for prefix in LOCAL_ONLY_PATH_PREFIXES):
            return is_loopback(self.client_address[0]), "local_health_only"

        if not is_loopback(self.client_address[0]):
            throttled = _record_auth_failure(self.client_address[0] or "")
            return False, "auth_rate_limited" if throttled else "non_local_client"

        if not CLIENT_TOKEN:
            _clear_auth_failures(self.client_address[0] or "")
            return True, "no_client_token_configured"

        presented = ProxyHandler._presented_client_token(self)
        bindings = load_client_bindings().get("tokens", {})
        if presented and presented in bindings:
            _clear_auth_failures(self.client_address[0] or "")
            return True, "bound_client_token_ok"
        if presented and presented == CLIENT_TOKEN:
            _clear_auth_failures(self.client_address[0] or "")
            return True, "client_token_ok"
        throttled = _record_auth_failure(self.client_address[0] or "")
        return False, "auth_rate_limited" if throttled else "missing_or_invalid_client_token"

    def _proxy_request(self):
        authorized, reason = self._client_authorized()
        if not authorized:
            status = 429 if reason == "auth_rate_limited" else 401
            return self._send_proxy_error(status, reason)
        request_mapping, request_profile, profile_source = ProxyHandler._request_mapping(self)
        if request_mapping is None:
            status = 401 if profile_source == "bound_token_profile_mismatch" else 400
            return self._send_proxy_error(status, profile_source if profile_source != "unknown_profile" else f"unknown_profile: '{request_profile}'")

        body = self._read_request_body()
        if body is None:
            return

        payload = None
        model_label = None
        content_type = self.headers.get("Content-Type", "")
        transfer_encoding = self.headers.get("Transfer-Encoding", "")
        declared_length = self.headers.get("Content-Length", "")
        body_size = len(body) if body is not None else 0
        parse_ok = False
        if body and "json" in content_type:
            try:
                payload = json.loads(body.decode())
                model_label = payload.get("model")
                parse_ok = True
            except Exception:
                payload = None
                parse_ok = False

        if self.path.startswith("/v1/responses"):
            log_event({
                "ts": now_ts(),
                "event": "request_body",
                "path": self.path,
                "content_type": content_type,
                "transfer_encoding": transfer_encoding,
                "declared_content_length": declared_length,
                "received_body_bytes": body_size,
                "json_parse_ok": parse_ok,
            })
            if body and "json" in content_type and not parse_ok:
                return self._send_proxy_error(
                    400,
                    "invalid_json_from_client: request body could not be parsed as JSON before routing",
                )

        policy = model_policy = slot = candidate_groups = state = None
        if model_label:
            policy, model_policy, slot, candidate_groups, state = prepare_candidates(model_label, mapping=request_mapping)

        if model_label and not candidate_groups:
            return self._send_proxy_error(
                400,
                f"invalid_model: '{model_label}' is not mapped by BrokeLLM; call /v1/models to inspect available routed models",
            )

        if not candidate_groups:
            try:
                outcome = self._forward_once(body)
            except OSError as exc:
                return self._send_proxy_error(503, f"upstream_unreachable: {exc}")
            if self.path == "/v1/models":
                outcome = self._filter_models_outcome(outcome, request_mapping, request_profile)
            return self._send_outcome(outcome, 0, "", 0, [])

        generation = policy.get("generation", 1)
        model_generation = model_policy.get("generation", 1) if model_policy else 1
        errors = []
        log_event({
            "ts": now_ts(),
            "event": "policy_apply",
            "model": model_label,
            "slot": slot,
            "generation": generation,
            "model_generation": model_generation,
            "path": self.path,
        })
        model_attempt = 0
        for group in candidate_groups:
            model_attempt += 1
            selected_label = group["label"]
            provider = group["provider"]
            key_policy = group["key_policy"]
            key_candidates = group["deployments"]
            log_event({
                "ts": now_ts(),
                "event": "model_apply",
                "requested_model": model_label,
                "selected_model": selected_label,
                "slot": slot,
                "provider": provider,
                "generation": generation,
                "model_generation": model_generation,
                "path": self.path,
                "attempt": model_attempt,
            })
            for key_attempt, candidate in enumerate(key_candidates, start=1):
                request_payload = copy.deepcopy(payload)
                request_payload["model"] = candidate["internal_model_name"]
                request_body = json.dumps(request_payload).encode()
                try:
                    outcome = self._forward_once(
                        request_body,
                        extra_headers={
                            "X-Broke-Policy-Generation": str(generation),
                            "X-Broke-Model-Policy-Generation": str(model_generation),
                            "X-Broke-Key-Used": candidate["key_name"],
                            "X-Broke-Model-Used": selected_label,
                        },
                        dry_run=False,
                    )
                except OSError as exc:
                    errors.append({"model": selected_label, "key_ref": _key_ref(candidate["key_name"]), "status": 503, "reason": "upstream_unreachable"})
                    log_event({
                        "ts": now_ts(),
                        "event": "key_skip",
                        "model": selected_label,
                        "provider": provider,
                        "key_name": candidate["key_name"],
                        "generation": generation,
                        "model_generation": model_generation,
                        "attempt": key_attempt,
                        "path": self.path,
                        "http_status": 503,
                        "reason": f"upstream_unreachable:{exc}",
                    })
                    continue

                status = outcome["status"]
                if 200 <= status < 400:
                    mark_provider_use(provider, candidate["key_name"])
                    if slot:
                        mark_lane_model_use(slot, selected_label)
                    update_key_status(candidate["key_name"], generation, "healthy", "request_ok", 0)
                    update_model_status(selected_label, model_generation, "healthy", "request_ok", 0)
                    log_event({
                        "ts": now_ts(),
                        "event": "request_ok",
                        "requested_model": model_label,
                        "selected_model": selected_label,
                        "provider": provider,
                        "key_name": candidate["key_name"],
                        "generation": generation,
                        "model_generation": model_generation,
                        "attempt": key_attempt,
                        "path": self.path,
                    })
                    return self._send_outcome(outcome, generation, _key_ref(candidate["key_name"]), key_attempt, errors, selected_label, model_generation)

                body_text = outcome["body"][:500].decode(errors="ignore")
                reason = classify_error(status, body_text)
                errors.append({"model": selected_label, "key_ref": _key_ref(candidate["key_name"]), "status": status, "reason": reason})

                if reason == "rate_limit":
                    update_key_status(candidate["key_name"], generation, "cooldown", "429", key_policy["cooldown_seconds"])
                elif reason == "auth_failure":
                    update_key_status(candidate["key_name"], generation, "auth_failed", str(status), 0)
                else:
                    update_key_status(candidate["key_name"], generation, "healthy", reason, 0)

                log_event({
                    "ts": now_ts(),
                    "event": "key_skip",
                    "model": selected_label,
                    "provider": provider,
                    "key_name": candidate["key_name"],
                    "generation": generation,
                    "model_generation": model_generation,
                    "attempt": key_attempt,
                    "path": self.path,
                    "http_status": status,
                    "reason": reason,
                })

                model_reason = "incompatible" if ("unsupported" in body_text.lower() or "property '" in body_text.lower()) else None
                if model_reason == "incompatible":
                    update_model_status(selected_label, model_generation, "incompatible", reason, 0)
                    log_event({
                        "ts": now_ts(),
                        "event": "model_skip",
                        "requested_model": model_label,
                        "selected_model": selected_label,
                        "slot": slot,
                        "provider": provider,
                        "generation": generation,
                        "model_generation": model_generation,
                        "path": self.path,
                        "http_status": status,
                        "reason": reason,
                    })
                    break
            else:
                continue
            if errors and errors[-1].get("reason") == "auth_failure":
                continue
            if errors and errors[-1].get("reason") != "rate_limit":
                update_model_status(selected_label, model_generation, "cooldown", errors[-1]["reason"], group["model_policy"]["cooldown_seconds"] if group["model_policy"] else 300)

        return self._send_last_error(generation, model_generation, errors)

    def _forward_once(self, body, extra_headers=None, dry_run=False):
        upstream = urlsplit(self.server.upstream_base)
        conn = http.client.HTTPConnection(upstream.hostname, upstream.port, timeout=60)
        path = self.path
        # Strip hop-by-hop/request-framing headers before forwarding.
        # We send a concrete bytes body, so upstream framing must be recalculated.
        strip_headers = {
            "authorization",
            "x-api-key",
            "api-key",
            "content-length",
            "transfer-encoding",
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailer",
            "upgrade",
            "expect",
        }
        headers = {k: v for k, v in self.headers.items() if k.lower() not in strip_headers}
        headers["Host"] = upstream.netloc
        if INTERNAL_TOKEN:
            headers["Authorization"] = f"Bearer {INTERNAL_TOKEN}"
        if extra_headers:
            headers.update(extra_headers)
        conn.request(self.command, path, body=body, headers=headers)
        resp = conn.getresponse()
        response_body = resp.read()
        outcome = {
            "status": resp.status,
            "reason": resp.reason,
            "headers": resp.getheaders(),
            "body": response_body,
        }
        conn.close()
        return outcome

    def _send_outcome(self, outcome, generation, key_name, attempt, errors, model_label="", model_generation=0):
        self.send_response(outcome["status"], outcome["reason"])
        for header, value in outcome["headers"]:
            if header.lower() in EXCLUDED_RESPONSE_HEADERS:
                continue
            self.send_header(header, value)
        self.send_header("Content-Length", str(len(outcome["body"])))
        self.send_header("X-Broke-Policy-Generation", str(generation))
        self.send_header("X-Broke-Model-Policy-Generation", str(model_generation))
        self.send_header("X-Broke-Key-Used", key_name)
        self.send_header("X-Broke-Model-Used", model_label)
        self.send_header("X-Broke-Rotation-Attempt", str(attempt))
        if errors:
            self.send_header("X-Broke-Rotation-Trace", json.dumps(errors))
        self.end_headers()
        self.wfile.write(outcome["body"])

    def _send_last_error(self, generation, model_generation, errors):
        payload = {
            "error": {
                "message": "All model/key orchestration attempts failed",
                "generation": generation,
                "model_generation": model_generation,
                "attempts": errors,
            }
        }
        body = json.dumps(payload).encode()
        self.send_response(429)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Broke-Policy-Generation", str(generation))
        self.send_header("X-Broke-Model-Policy-Generation", str(model_generation))
        self.send_header("X-Broke-Rotation-Trace", json.dumps(errors))
        self.end_headers()
        self.wfile.write(body)

    def _send_proxy_error(self, status, message):
        body = json.dumps({"error": {"message": message}}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_request_body(self):
        transfer_encoding = (self.headers.get("Transfer-Encoding", "") or "").lower()
        if "chunked" in transfer_encoding:
            chunks = []
            total = 0
            while True:
                size_line = self.rfile.readline(65537)
                if not size_line:
                    self._send_proxy_error(400, "invalid_chunked_body: missing_chunk_size")
                    return None
                try:
                    size_token = size_line.strip().split(b";", 1)[0]
                    chunk_size = int(size_token, 16)
                except Exception:
                    self._send_proxy_error(400, "invalid_chunked_body: bad_chunk_size")
                    return None
                if chunk_size < 0:
                    self._send_proxy_error(400, "invalid_chunked_body: negative_chunk_size")
                    return None
                if chunk_size == 0:
                    # Consume trailer headers (if any) until blank line.
                    while True:
                        trailer = self.rfile.readline(65537)
                        if not trailer or trailer in (b"\r\n", b"\n"):
                            break
                    break
                total += chunk_size
                if total > MAX_REQUEST_BYTES:
                    self._send_proxy_error(413, f"request_too_large: limit is {MAX_REQUEST_BYTES} bytes")
                    return None
                chunk = self.rfile.read(chunk_size)
                if not chunk or len(chunk) != chunk_size:
                    self._send_proxy_error(400, f"incomplete_request_body: expected_chunk={chunk_size} received={len(chunk) if chunk else 0}")
                    return None
                # Consume the CRLF after each chunk.
                crlf = self.rfile.read(2)
                if crlf != b"\r\n":
                    self._send_proxy_error(400, "invalid_chunked_body: missing_chunk_terminator")
                    return None
                chunks.append(chunk)
            return b"".join(chunks)

        if "Content-Length" not in self.headers:
            return b""
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_proxy_error(400, "invalid_content_length")
            return None
        if size < 0:
            self._send_proxy_error(400, "invalid_content_length")
            return None
        if size > MAX_REQUEST_BYTES:
            self._send_proxy_error(413, f"request_too_large: limit is {MAX_REQUEST_BYTES} bytes")
            return None
        # BaseHTTPRequestHandler input streams can yield short reads; keep
        # reading until we have the full declared body or hit EOF.
        chunks = []
        remaining = size
        while remaining > 0:
            chunk = self.rfile.read(remaining)
            if not chunk:
                self._send_proxy_error(400, f"incomplete_request_body: expected={size} received={size - remaining}")
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def do_GET(self):
        self._proxy_request()

    def do_POST(self):
        self._proxy_request()

    def do_PUT(self):
        self._proxy_request()

    def do_PATCH(self):
        self._proxy_request()

    def do_DELETE(self):
        self._proxy_request()

    def log_message(self, fmt, *args):
        return


class ThreadingUnixHTTPServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True

    def server_bind(self):
        if os.path.exists(self.server_address):
            os.unlink(self.server_address)
        super().server_bind()
        try:
            os.chmod(self.server_address, 0o600)
        except Exception:
            pass
        self.server_name = "localhost"
        self.server_port = 0


def main():
    listen_port = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
    upstream_port = int(sys.argv[2]) if len(sys.argv) > 2 else 4001
    server = ThreadingHTTPServer(("127.0.0.1", listen_port), ProxyHandler)
    server.upstream_base = f"http://127.0.0.1:{upstream_port}"
    unix_server = None
    if PROXY_UNIX_SOCKET:
        unix_server = ThreadingUnixHTTPServer(PROXY_UNIX_SOCKET, ProxyHandler)
        unix_server.upstream_base = server.upstream_base
        threading.Thread(target=unix_server.serve_forever, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if unix_server is not None:
            unix_server.shutdown()
            unix_server.server_close()
            try:
                os.unlink(PROXY_UNIX_SOCKET)
            except OSError:
                pass


if __name__ == "__main__":
    main()
