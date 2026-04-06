#!/usr/bin/env python3
"""BrokeLLM mapping helpers — used by broke CLI."""

import fnmatch
import hashlib
import importlib.metadata
import json
import os
import pathlib
import re
import secrets
import site
import stat
import time
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

BIN_DIR = pathlib.Path(__file__).resolve().parent
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))

from _acp_lane import default_runtime_registry as _default_runtime_registry
from _fs_common import locked_file as _locked_file
from _harness_common import append_event as _append_shared_event
from _harness_common import canonical_json as _canonical_json
from _harness_common import sha256_text as _sha256_text

DIR = pathlib.Path(__file__).parent.parent
REQUIREMENTS = DIR / "requirements.txt"
LOCKFILE = DIR / "requirements.lock"
PTH_ALLOWLIST = DIR / ".pth.allowlist"
MAPPING  = DIR / ".mapping.json"
BACKENDS = DIR / ".backends.json"
CONFIG   = DIR / "config.json"
DEPLOYMENTS = DIR / ".deployments.json"
TEAMS    = DIR / ".teams.json"
PROFILES  = DIR / ".profiles.json"
CLIENT_BINDINGS = DIR / ".client_bindings.json"
SNAPSHOTS = DIR / ".snapshots"
FREEZE    = DIR / ".freeze"
ROTATION_POLICY = DIR / ".rotation.json"
KEY_STATE = DIR / ".key_state.json"
ROTATION_LOG = DIR / ".rotation.log"
MODEL_POLICY = DIR / ".model_policy.json"
MODEL_STATE = DIR / ".model_state.json"
HARNESS_CONFIG = DIR / ".harness.json"
HARNESS_STATE = DIR / ".harness_state.json"
HARNESS_PROMPT_CONTRACTS = DIR / ".harness_prompt_contracts.json"
HARNESS_PREFIX_CACHE = DIR / ".harness_prefix_cache.json"
HARNESS_EVIDENCE_CACHE = DIR / ".harness_evidence_cache.json"
HARNESS_REVIEW_CACHE = DIR / ".harness_review_cache.json"
HARNESS_RUNS = DIR / ".harness_runs.json"
HARNESS_ACTIVE_RUN = DIR / ".harness_active_run.json"
HARNESS_RUN_ROOT = DIR / ".runtime" / "harness"
CLIENT_TOKEN_FILE = DIR / ".broke_client_token"
INTERNAL_TOKEN_FILE = DIR / ".broke_internal_token"
ENV_FILE = DIR / ".env"
CLAUDE_ENV_FILE = DIR / ".env.claude"
LAUNCH_AUDIT_LOG = DIR / ".launch_audit.log"
SANDBOX_PROFILE_FILE = DIR / ".sandbox-profile"
PROXY_SOCKET = DIR / ".runtime" / "proxy.sock"

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

DEFAULT_MAPPING = {
    "sonnet":  {"provider":"openrouter","model":"qwen/qwen3.6-plus:free","label":"OR/Qwen-3.6+","key":"OPENROUTER_API_KEY"},
    "opus":    {"provider":"openrouter","model":"nvidia/nemotron-3-super-120b-a12b:free","label":"OR/Nemotron-3-Super","key":"OPENROUTER_API_KEY"},
    "haiku":   {"provider":"openrouter","model":"stepfun/step-3.5-flash:free","label":"OR/Step-3.5","key":"OPENROUTER_API_KEY"},
    "custom":  {"provider":"openrouter","model":"nvidia/nemotron-3-nano-30b-a3b:free","label":"OR/Nemotron-3-Nano","key":"OPENROUTER_API_KEY"},
    "subagent":{"provider":"openrouter","model":"z-ai/glm-4.5-air:free","label":"OR/GLM-4.5","key":"OPENROUTER_API_KEY"},
    "gpt54": {"provider":"openrouter","model":"qwen/qwen3.6-plus:free","label":"OR/Qwen-3.6+","key":"OPENROUTER_API_KEY"},
    "gpt54mini": {"provider":"openrouter","model":"stepfun/step-3.5-flash:free","label":"OR/Step-3.5","key":"OPENROUTER_API_KEY"},
    "gpt53codex": {"provider":"groq","model":"moonshotai/kimi-k2-instruct","label":"Groq/Kimi-K2","key":"GROQ_API_KEY"},
    "gpt52codex": {"provider":"openrouter","model":"z-ai/glm-4.5-air:free","label":"OR/GLM-4.5","key":"OPENROUTER_API_KEY"},
    "gpt52": {"provider":"openrouter","model":"nvidia/nemotron-3-super-120b-a12b:free","label":"OR/Nemotron-3-Super","key":"OPENROUTER_API_KEY"},
    "gpt51codexmax": {"provider":"groq","model":"moonshotai/kimi-k2-instruct","label":"Groq/Kimi-K2","key":"GROQ_API_KEY"},
    "gpt51codexmini": {"provider":"groq","model":"meta-llama/llama-4-scout-17b-16e-instruct","label":"Groq/Llama-4-Scout","key":"GROQ_API_KEY"},
}

SLOT_DISPLAY_NAMES = {
    "sonnet": "Sonnet (1M)",
    "opus": "Opus (1M)",
    "haiku": "Haiku",
    "custom": "Custom",
    "subagent": "Subagent",
    "gpt54": "GPT-5.4",
    "gpt54mini": "GPT-5.4 Mini",
    "gpt53codex": "GPT-5.3 Codex",
    "gpt52codex": "GPT-5.2 Codex",
    "gpt52": "GPT-5.2",
    "gpt51codexmax": "GPT-5.1 Codex Max",
    "gpt51codexmini": "GPT-5.1 Codex Mini",
}

# pinned=False → floating alias; may drift when upstream updates their default.
# These are flagged so users know to watch for silent breakage.
BACKENDS_DATA = [
  {"provider":"openrouter","model":"qwen/qwen3.6-plus:free",                    "label":"OR/Qwen-3.6+",        "key":"OPENROUTER_API_KEY",  "pinned":True},
  {"provider":"openrouter","model":"nvidia/nemotron-3-super-120b-a12b:free",    "label":"OR/Nemotron-3-Super", "key":"OPENROUTER_API_KEY",  "pinned":True},
  {"provider":"openrouter","model":"nvidia/nemotron-3-nano-30b-a3b:free",       "label":"OR/Nemotron-3-Nano",  "key":"OPENROUTER_API_KEY",  "pinned":True},
  {"provider":"openrouter","model":"stepfun/step-3.5-flash:free",               "label":"OR/Step-3.5",         "key":"OPENROUTER_API_KEY",  "pinned":True},
  {"provider":"openrouter","model":"z-ai/glm-4.5-air:free",                     "label":"OR/GLM-4.5",          "key":"OPENROUTER_API_KEY",  "pinned":True},
  {"provider":"cerebras",  "model":"qwen-3-235b-a22b-instruct-2507",            "label":"Cerebras/Qwen-3-235B","key":"CEREBRAS_API_KEY",    "pinned":True},
  {"provider":"cerebras",  "model":"gpt-oss-120b",                              "label":"Cerebras/GPT-OSS-120B","key":"CEREBRAS_API_KEY",   "pinned":False},
  {"provider":"cerebras",  "model":"zai-glm-4.7",                               "label":"Cerebras/GLM-4.7",    "key":"CEREBRAS_API_KEY",    "pinned":True},
  {"provider":"groq",      "model":"meta-llama/llama-4-scout-17b-16e-instruct", "label":"Groq/Llama-4-Scout",  "key":"GROQ_API_KEY",        "pinned":True},
  {"provider":"groq",      "model":"moonshotai/kimi-k2-instruct",               "label":"Groq/Kimi-K2",        "key":"GROQ_API_KEY",        "pinned":True},
  {"provider":"groq",      "model":"groq/compound",                             "label":"Groq/Compound",       "key":"GROQ_API_KEY",        "pinned":False},
  {"provider":"openai",    "model":"gpt-4o-mini",                               "label":"GitHub/GPT-4o-mini",  "key":"GITHUB_TOKEN",        "pinned":False, "api_base":"https://models.inference.ai.azure.com"},
  {"provider":"openai",    "model":"mistral-ai/codestral-2501",                 "label":"GitHub/Codestral-2501","key":"GITHUB_TOKEN",        "pinned":True,  "api_base":"https://models.inference.ai.azure.com"},
  {"provider":"openai",    "model":"mistral-ai/mistral-medium-2505",            "label":"GitHub/Mistral-Medium","key":"GITHUB_TOKEN",        "pinned":True,  "api_base":"https://models.inference.ai.azure.com"},
  {"provider":"gemini",    "model":"gemini-2.0-flash",                          "label":"Gemini/2.0-Flash",    "key":"GEMINI_API_KEY",      "pinned":True},
  {"provider":"gemini",    "model":"gemini-2.5-flash-preview-04-17",            "label":"Gemini/2.5-Flash",    "key":"GEMINI_API_KEY",      "pinned":True},
  {"provider":"gemini",    "model":"gemini-3.0-flash",                          "label":"Gemini/3.0-Flash",    "key":"GEMINI_API_KEY",      "pinned":True},
  {"provider":"huggingface","model":"meta-llama/Llama-3.1-8B-Instruct",         "label":"HF/Llama-3.1-8B",    "key":"HF_TOKEN",            "pinned":True},
  {"provider":"huggingface","model":"Qwen/Qwen2.5-72B-Instruct",                "label":"HF/Qwen2.5-72B",     "key":"HF_TOKEN",            "pinned":True},
  {"provider":"huggingface","model":"mistralai/Mistral-7B-Instruct-v0.3",       "label":"HF/Mistral-7B",      "key":"HF_TOKEN",            "pinned":True},
]

SAFE_PTH_PATTERNS = [
    "distutils-precedence.pth",
    "coloredlogs.pth",
    "pytest-cov.pth",
    "init_cov_core.pth",
    "__editable__.*.pth",
    "*-nspkg.pth",
    "*.nspkg.pth",
]
STRICT_PREFLIGHT_ENV = "BROKE_PREFLIGHT_STRICT"
HARNESS_MODES = ["off", "throughput", "balanced", "high_assurance"]
HARNESS_VERDICTS = ["ACCEPT", "ACCEPT_WITH_WARNINGS", "RETRY_NARROW", "RETRY_BROAD", "ESCALATE", "BLOCK"]
HARNESS_REVIEW_ROLES = ["worker", "verifier", "adversary"]
HARNESS_LANE_HEALTH = ["healthy", "degraded", "failed"]
HARNESS_IMPLEMENTATION_CHECKLIST = [
    {
        "id": "lane_instances",
        "label": "Persistent lane instances",
        "detail": "Durable worker/verifier/adversary records with identity, health, binding, and last contribution.",
    },
    {
        "id": "lane_sessions",
        "label": "Lane session continuity",
        "detail": "Per-lane logical session state that survives across ephemeral review calls.",
    },
    {
        "id": "evidence_classes",
        "label": "Normalized evidence classes",
        "detail": "Task, diff, tests, commands, policy events, and retry history stored as typed observation artifacts.",
    },
    {
        "id": "observation_inference_split",
        "label": "Observation / inference split",
        "detail": "Evidence packets separate direct observations from derived summaries so model lanes do not consume mixed truth levels.",
    },
    {
        "id": "verdict_contributions",
        "label": "Verdict contribution records",
        "detail": "Each role writes a durable contribution object instead of only a final summarized verdict.",
    },
    {
        "id": "degraded_lane_policy",
        "label": "Degraded review-lane policy",
        "detail": "Timeouts, provider failures, and missing lane outputs are explicit categories in verdict algebra.",
    },
    {
        "id": "operator_checklist",
        "label": "Operator checklist surface",
        "detail": "Harness exposes the implementation checklist directly so the control plane shows what is meant to be true.",
    },
]


def _entry_identity(entry):
    """Canonical provider/model identity used across config, health, and drift checks."""
    provider = entry.get("provider", "")
    model = entry.get("model", "")
    if provider and model:
        return f"{provider}/{model}"
    if model and "/" in model:
        return model
    return ""


def _backend_catalog_entry(entry):
    """Resolve an entry back to the static backend catalog when possible."""
    identity = _entry_identity(entry)
    api_base = entry.get("api_base")
    for backend in BACKENDS_DATA:
        if _entry_identity(backend) != identity:
            continue
        if backend.get("api_base") == api_base:
            return backend
        if "api_base" not in backend and api_base is None:
            return backend
    return None


def _entry_pin_state(entry):
    """Return True/False when known, else None when the entry cannot be classified."""
    if "pinned" in entry:
        return bool(entry["pinned"])
    backend = _backend_catalog_entry(entry)
    if backend is None:
        return None
    return bool(backend.get("pinned", True))


def _fetch_health_index(port=4000, timeout=5):
    """Return normalized healthy/unhealthy model identities from LiteLLM /health."""
    resp = urllib.request.urlopen(f"http://localhost:{port}/health", timeout=timeout)
    data = json.loads(resp.read())
    healthy = {_entry_identity(ep) for ep in data.get("healthy_endpoints", []) if _entry_identity(ep)}
    unhealthy = {_entry_identity(ep) for ep in data.get("unhealthy_endpoints", []) if _entry_identity(ep)}
    return {"healthy": healthy, "unhealthy": unhealthy}


def _entry_health_status(entry, port=4000, timeout=5):
    """Return normalized health status string for an entry."""
    identity = _entry_identity(entry)
    health = _fetch_health_index(port=port, timeout=timeout)
    if identity in health["healthy"]:
        return "OK"
    if identity in health["unhealthy"]:
        return "UNHEALTHY"
    return "unknown (not yet health-checked)"


def _provider_display_name(provider):
    names = {
        "openrouter": "OR",
        "openai": "GitHub",
        "cerebras": "Cerebras",
        "groq": "Groq",
        "gemini": "Gemini",
        "huggingface": "HF",
    }
    return names.get(provider, provider)


def _clone_entry(entry):
    fields = ("provider", "model", "label", "key", "api_base", "pinned")
    return {k: entry[k] for k in fields if k in entry}


def _load_env_values():
    env_vals = {}
    env_path = ENV_FILE
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env_vals[k.strip()] = v.strip()
    for k, v in os.environ.items():
        if v:
            env_vals[k] = v
    return env_vals


def _load_claude_env_exports():
    exports = {}
    if not CLAUDE_ENV_FILE.exists():
        return exports
    for raw_line in CLAUDE_ENV_FILE.read_text().splitlines():
        line = raw_line.strip()
        if not line.startswith("export ") or "=" not in line:
            continue
        name, value = line[len("export "):].split("=", 1)
        exports[name.strip()] = value.strip().strip('"').strip("'")
    return exports


def _proxy_auth_headers():
    env_vals = _load_env_values()
    token = env_vals.get("BROKE_CLIENT_TOKEN", "")
    if not token and CLIENT_TOKEN_FILE.exists():
        token = CLIENT_TOKEN_FILE.read_text().strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _parse_requirements_txt(path=REQUIREMENTS):
    if not path.exists():
        return {}
    expected = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            continue
        name, version = line.split("==", 1)
        expected[name.split("[", 1)[0].strip().lower().replace("_", "-")] = version.strip()
    return expected


def _parse_lock_versions(path=LOCKFILE):
    if not path.exists():
        return {}
    locked = {}
    pattern = re.compile(r"^([A-Za-z0-9._-]+)==([^\s\\]+)")
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        m = pattern.match(line)
        if not m:
            continue
        locked[m.group(1).lower().replace("_", "-")] = m.group(2)
    return locked


def _installed_versions(package_names):
    versions = {}
    for name in package_names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def _site_pth_files():
    seen = []
    paths = []
    getter = getattr(site, "getsitepackages", None)
    if getter is not None:
        try:
            values = getter()
            if isinstance(values, str):
                paths.append(values)
            else:
                paths.extend(values)
        except Exception:
            pass
    user_site = getattr(site, "getusersitepackages", None)
    if user_site is not None:
        try:
            value = user_site()
            if value:
                paths.append(value)
        except Exception:
            pass
    deduped = []
    for path in paths:
        p = pathlib.Path(path)
        if p.exists() and p not in deduped:
            deduped.append(p)
    for base in deduped:
        seen.extend(sorted(base.glob("*.pth")))
    return seen


def _load_pth_allowlist():
    patterns = list(SAFE_PTH_PATTERNS)
    if PTH_ALLOWLIST.exists():
        for raw_line in PTH_ALLOWLIST.read_text().splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(line)
    return patterns


def _unexpected_pth_files():
    allowed = _load_pth_allowlist()
    unexpected = []
    for path in _site_pth_files():
        if any(fnmatch.fnmatch(path.name, pattern) for pattern in allowed):
            continue
        unexpected.append(path)
    return unexpected


def _runtime_secret_files():
    return [
        ROTATION_POLICY,
        KEY_STATE,
        MODEL_POLICY,
        MODEL_STATE,
        DEPLOYMENTS,
        ROTATION_LOG,
        ENV_FILE,
        CLAUDE_ENV_FILE,
        HARNESS_PROMPT_CONTRACTS,
        HARNESS_PREFIX_CACHE,
        HARNESS_EVIDENCE_CACHE,
        HARNESS_REVIEW_CACHE,
        HARNESS_RUNS,
        HARNESS_ACTIVE_RUN,
        CLIENT_TOKEN_FILE,
        INTERNAL_TOKEN_FILE,
        LAUNCH_AUDIT_LOG,
        SANDBOX_PROFILE_FILE,
    ]


def _bad_runtime_permissions():
    bad = []
    for path in _runtime_secret_files():
        if not path.exists():
            continue
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode != 0o600:
            bad.append((path, mode))
    return bad


def _bad_harness_shim_dirs():
    bad = []
    shim_target = (DIR / "bin" / "_harness_shim.py").resolve()
    root = HARNESS_RUN_ROOT
    if not root.exists():
        return bad
    for shim_dir in root.glob("*/shims"):
        try:
            mode = stat.S_IMODE(shim_dir.stat().st_mode)
        except FileNotFoundError:
            continue
        if mode != 0o700:
            bad.append(f"{shim_dir}: mode {oct(mode)}")
            continue
        for entry in shim_dir.iterdir():
            if not entry.is_symlink():
                bad.append(f"{entry}: not a symlink")
                break
            try:
                if entry.resolve() != shim_target:
                    bad.append(f"{entry}: unexpected target {entry.resolve()}")
                    break
            except FileNotFoundError:
                bad.append(f"{entry}: broken symlink")
                break
    return bad


def _preflight_findings():
    findings = {"ok": [], "warn": [], "fail": []}
    strict_preflight = os.environ.get(STRICT_PREFLIGHT_ENV, "").lower() in {"1", "true", "yes", "strict"}
    locked = _parse_lock_versions()
    pinned = _parse_requirements_txt()

    if not REQUIREMENTS.exists():
        findings["fail"].append(f"missing requirements file: {REQUIREMENTS.name}")
    else:
        findings["ok"].append(f"requirements file present: {REQUIREMENTS.name}")

    if not LOCKFILE.exists():
        findings["fail"].append(f"missing lockfile: {LOCKFILE.name}")
    else:
        findings["ok"].append(f"lockfile present: {LOCKFILE.name}")

    expected_litellm = pinned.get("litellm")
    if expected_litellm:
        actual_litellm = _installed_versions(["litellm"]).get("litellm")
        if actual_litellm != expected_litellm:
            findings["fail"].append(f"litellm version mismatch: expected {expected_litellm}, found {actual_litellm or 'missing'}")
        else:
            findings["ok"].append(f"litellm version pinned at {actual_litellm}")
    else:
        findings["fail"].append("requirements.txt does not pin litellm exactly")

    if locked:
        installed = _installed_versions(list(locked.keys()))
        mismatches = []
        missing = []
        for name, expected in locked.items():
            actual = installed.get(name)
            if actual is None:
                missing.append(name)
            elif actual != expected:
                mismatches.append((name, expected, actual))
        if missing:
            findings["fail"].append(f"lockfile packages missing from runtime: {', '.join(missing[:8])}" + (" ..." if len(missing) > 8 else ""))
        elif mismatches:
            sample = ", ".join(f"{name}={actual} (want {expected})" for name, expected, actual in mismatches[:5])
            bucket = "fail" if strict_preflight else "warn"
            findings[bucket].append(f"runtime package drift vs lockfile: {sample}" + (" ..." if len(mismatches) > 5 else ""))
        else:
            findings["ok"].append(f"runtime package set matches {LOCKFILE.name}")

    unexpected_pth = _unexpected_pth_files()
    if unexpected_pth:
        bucket = "fail" if strict_preflight else "warn"
        findings[bucket].append("unexpected .pth files present: " + ", ".join(path.name for path in unexpected_pth[:6]) + (" ..." if len(unexpected_pth) > 6 else ""))
    else:
        findings["ok"].append("no unexpected .pth files detected")

    if os.environ.get("PYTHONPATH"):
        findings["fail"].append("PYTHONPATH is set; launch-time import path pollution is not allowed")
    else:
        findings["ok"].append("PYTHONPATH is not set")

    bad_perms = _bad_runtime_permissions()
    if bad_perms:
        sample = ", ".join(f"{path.name}={oct(mode)}" for path, mode in bad_perms[:6])
        findings["fail"].append(f"runtime file permissions must be 600: {sample}" + (" ..." if len(bad_perms) > 6 else ""))
    else:
        findings["ok"].append("runtime secret/state file permissions are 600")

    if PROXY_SOCKET.exists():
        findings["ok"].append(f"proxy unix socket present: {PROXY_SOCKET}")

    bad_shims = _bad_harness_shim_dirs()
    if bad_shims:
        findings["fail"].append("harness shim directory integrity failure: " + "; ".join(bad_shims[:4]) + (" ..." if len(bad_shims) > 4 else ""))
    elif HARNESS_RUN_ROOT.exists():
        findings["ok"].append("harness shim directories are 700 with expected symlink targets")

    return findings


def _validate_findings():
    findings = {"ok": [], "warn": [], "fail": []}
    m = load()
    slots = _slots(m)
    fallbacks_map = m.get("_fallbacks", {})
    backend_fallbacks = m.get("_backend_fallbacks", {})
    lane_fallback_targets = m.get("_lane_fallback_targets", {})

    required = {"provider", "model", "label", "key"}
    for slot, entry in slots.items():
        missing = required - set(entry.keys())
        if missing:
            findings["fail"].append(f"{slot}: missing fields: {', '.join(sorted(missing))}")
        else:
            findings["ok"].append(f"{slot}: all required fields present")

    valid_providers = {"openrouter", "cerebras", "groq", "openai", "gemini", "huggingface"}
    for slot, entry in slots.items():
        prov = entry.get("provider", "")
        if prov not in valid_providers:
            findings["warn"].append(f"{slot}: unknown provider '{prov}'")
        else:
            findings["ok"].append(f"{slot}: provider '{prov}' recognised")

    env_vals = _load_env_values()
    seen = set()
    for slot, entry in slots.items():
        key = entry.get("key", "")
        if not key:
            findings["fail"].append(f"{slot}: no api key field")
            continue
        if key in seen:
            continue
        seen.add(key)
        val = env_vals.get(key, "")
        if not val:
            findings["fail"].append(f"{key} — not set")
        elif "XXXXX" in val:
            findings["warn"].append(f"{key} — placeholder not filled in")
        else:
            findings["ok"].append(f"{key} — set")

    effective_fallbacks = {}
    if not fallbacks_map and not backend_fallbacks and not lane_fallback_targets:
        findings["ok"].append("no fallback chains defined (ok)")
    else:
        source_slots_by_identity = {_entry_identity(entry): slot for slot, entry in slots.items()}
        for slot in slots:
            fb_chain, _scope, _source_key = _effective_fallback_chain(m, slot, slots)
            if fb_chain:
                effective_fallbacks[slot] = fb_chain

        for slot, targets in lane_fallback_targets.items():
            if slot not in slots:
                findings["warn"].append(f"lane fallback '{slot}' is saved but slot is not active in this mapping")
                continue
            for target in targets:
                missing = {"provider", "model", "label", "key"} - set(target.keys())
                if missing:
                    findings["fail"].append(f"{slot}: direct fallback target missing fields: {', '.join(sorted(missing))}")
                else:
                    findings["ok"].append(f"{slot}: direct fallback target '{target['label']}' valid")

        for source_identity, _fb_chain in backend_fallbacks.items():
            slot = source_slots_by_identity.get(source_identity)
            if slot is None:
                findings["warn"].append(f"backend fallback '{source_identity}' is saved but not active in this mapping")
            else:
                findings["ok"].append(f"{slot}: backend-scoped fallback policy active")

        def _has_cycle(start, current, visited):
            for fb in effective_fallbacks.get(current, []):
                if isinstance(fb, dict):
                    continue
                if fb == start:
                    return True
                if fb not in visited:
                    visited.add(fb)
                    if _has_cycle(start, fb, visited):
                        return True
            return False

        for slot, fb_chain in effective_fallbacks.items():
            if slot not in slots:
                findings["fail"].append(f"source slot '{slot}' not in active mapping")
                continue
            for fb in fb_chain:
                if isinstance(fb, dict):
                    continue
                if fb == slot:
                    findings["fail"].append(f"{slot} → '{fb}': self-referential fallback")
                elif fb not in slots:
                    findings["fail"].append(f"{slot} → '{fb}': target slot not configured")
                else:
                    findings["ok"].append(f"{slot} → {fb}: valid")
            if _has_cycle(slot, slot, {slot}):
                findings["warn"].append(f"{slot}: circular fallback chain detected")

    for slot, entry in slots.items():
        pin_state = _entry_pin_state(entry)
        if pin_state is False:
            findings["warn"].append(f"{slot}: floating alias '{entry['label']}' — may drift on upstream changes")
        elif pin_state is None:
            findings["warn"].append(f"{slot}: pin state for '{entry['label']}' is unknown")
        else:
            findings["ok"].append(f"{slot}: pinned alias")

    return findings


def cmd_preflight(quiet=False):
    findings = _preflight_findings()
    failed = bool(findings["fail"])
    if not quiet:
        print("\n  broke preflight")
        print("  " + "─" * 58)
        print("\n  [integrity]")
        for msg in findings["ok"]:
            print(f"  ✓  {msg}")
        for msg in findings["warn"]:
            print(f"  ⚠  {msg}")
        for msg in findings["fail"]:
            print(f"  ✗  {msg}")
        print()
    return not failed


def _print_findings_section(title, findings, ok_cb, warn_cb, fail_cb):
    print(f"\n  [{title}]")
    for msg in findings["ok"]:
        ok_cb(msg)
    for msg in findings["warn"]:
        warn_cb(msg)
    for msg in findings["fail"]:
        fail_cb(msg)


def _normalise_role_verdict(value):
    if not value:
        return None
    normalized = str(value).strip().upper()
    return normalized if normalized in HARNESS_VERDICTS else None


def _harness_verdict(config, preflight_findings, validate_findings, role_verdicts=None, risk="normal", retries=0, evidence_summary=None, lane_states=None):
    role_verdicts = role_verdicts or {}
    evidence_summary = evidence_summary or {}
    lane_states = lane_states or {}
    mode = config.get("mode", "off")
    if mode == "off":
        return {
            "mode": mode,
            "verdict": "ACCEPT",
            "reasons": ["harness mode is off"],
            "categories": [],
            "role_verdicts": role_verdicts,
            "lane_health": {role: (lane_states.get(role, {}) or {}).get("health", "healthy") for role in HARNESS_REVIEW_ROLES},
            "risk": risk,
            "retries": retries,
        }

    profile = config["profiles"].get(mode, config["profiles"]["balanced"])
    categories = []
    reasons = []

    if preflight_findings["fail"]:
        categories.append("integrity")
        reasons.extend(preflight_findings["fail"])

    validate_failures = list(validate_findings["fail"])
    validate_warnings = list(validate_findings["warn"])

    boundary_markers = ("not set", "PYTHONPATH", "permissions", "self-referential", "target slot not configured")
    if any(any(marker in msg for marker in boundary_markers) for msg in validate_failures + reasons):
        categories.append("boundary")

    if validate_failures:
        categories.append("correctness")
        reasons.extend(validate_failures[:8])

    suspicious_markers = ("floating alias", "circular fallback", "placeholder")
    if any(any(marker in msg for marker in suspicious_markers) for msg in validate_warnings):
        categories.append("suspicious_tests")

    if validate_warnings:
        categories.append("quality")

    if evidence_summary.get("diff_present") and not evidence_summary.get("tests_present"):
        categories.append("evidence")
        reasons.append("diff evidence present without test evidence")
    if evidence_summary.get("diff_present") and not evidence_summary.get("commands_present"):
        categories.append("evidence")
        reasons.append("diff evidence present without command trace evidence")
    if evidence_summary.get("policy_events_present") and evidence_summary.get("policy_event_lines", 0) >= 3 and not evidence_summary.get("tests_present"):
        categories.append("verification")
        reasons.append("policy activity present without matching verification evidence")

    if role_verdicts.get("worker") == "BLOCK":
        categories.append("fabrication")
        reasons.append("worker role returned BLOCK")
    if role_verdicts.get("verifier") in {"RETRY_BROAD", "ESCALATE", "BLOCK"}:
        categories.append("verification")
        reasons.append(f"verifier returned {role_verdicts['verifier']}")
    if role_verdicts.get("adversary") in {"ESCALATE", "BLOCK"}:
        categories.append("fabrication")
        reasons.append(f"adversary returned {role_verdicts['adversary']}")

    degraded_roles = []
    for role in HARNESS_REVIEW_ROLES:
        lane = lane_states.get(role, {}) or {}
        if lane.get("health") in {"degraded", "failed"}:
            degraded_roles.append(role)
            categories.append("review_degraded")
            reasons.append(f"{role} lane health is {lane.get('health')}: {lane.get('degraded_reason') or 'no reason recorded'}")

    categories = list(dict.fromkeys(categories))
    block_on = set(profile.get("block_on", []))
    retry_on = set(profile.get("retry_on", []))
    escalate_after = int(profile.get("escalate_after_retries", 2))

    if any(category in block_on for category in categories):
        verdict = "BLOCK"
    elif any(category in retry_on for category in categories):
        if retries >= escalate_after:
            verdict = "ESCALATE"
        elif risk in {"high", "release", "security"} or mode == "high_assurance":
            verdict = "RETRY_BROAD"
        else:
            verdict = "RETRY_NARROW"
    elif categories:
        if risk in {"high", "release", "security"} and ("quality" in categories or "suspicious_tests" in categories):
            verdict = "ACCEPT_WITH_WARNINGS"
        else:
            verdict = "ACCEPT_WITH_WARNINGS"
    else:
        verdict = "ACCEPT"

    return {
        "mode": mode,
        "verdict": verdict,
        "reasons": reasons[:12],
        "categories": categories,
        "role_verdicts": role_verdicts,
        "lane_health": {role: (lane_states.get(role, {}) or {}).get("health", "healthy") for role in HARNESS_REVIEW_ROLES},
        "degraded_roles": degraded_roles,
        "risk": risk,
        "retries": retries,
    }


def _atomic_write_text(path, text):
    with _locked_file(path, exclusive=True):
        tmp = path.with_name(f"{path.name}.tmp")
        tmp.write_text(text)
        tmp.replace(path)
        try:
            path.chmod(0o600)
        except Exception:
            pass


def _atomic_write_json(path, data):
    _atomic_write_text(path, json.dumps(data, indent=2) + "\n")


def _read_json(path, default):
    if not path.exists():
        return default
    with _locked_file(path, exclusive=False):
        try:
            return json.loads(path.read_text())
        except Exception:
            return default


def _key_pool_names(base_key, env_vals):
    keys = []
    if env_vals.get(base_key):
        keys.append(base_key)
    suffix_re = re.compile(rf"^{re.escape(base_key)}_(\d+)$")
    extras = []
    for name, value in env_vals.items():
        if not value:
            continue
        m = suffix_re.match(name)
        if m:
            extras.append((int(m.group(1)), name))
    extras.sort()
    keys.extend(name for _idx, name in extras)
    return keys or [base_key]


def _provider_rotation_defaults(env_vals=None):
    if env_vals is None:
        env_vals = _load_env_values()
    providers = {}
    seen = set()
    for backend in BACKENDS_DATA:
        key_name = backend["key"]
        if key_name in seen:
            continue
        seen.add(key_name)
        pool = _key_pool_names(key_name, env_vals)
        providers[backend["provider"]] = {
            "mode": "rotate_on_rate_limit",
            "order": pool,
            "cooldown_seconds": 300,
            "max_retries": max(1, len(pool)),
        }
    return providers


def _load_rotation_policy():
    policy = _read_json(ROTATION_POLICY, {})
    if "generation" not in policy:
        policy["generation"] = 1
    if "providers" not in policy:
        policy["providers"] = _provider_rotation_defaults()
    return policy


def _save_rotation_policy(policy):
    _atomic_write_json(ROTATION_POLICY, policy)


def _load_key_state():
    state = _read_json(KEY_STATE, {})
    if "keys" not in state:
        state["keys"] = {}
    if "providers" not in state:
        state["providers"] = {}
    return state


def _save_key_state(state):
    _atomic_write_json(KEY_STATE, state)


def _load_model_policy():
    policy = _read_json(MODEL_POLICY, {})
    if "generation" not in policy:
        policy["generation"] = 1
    if "lanes" not in policy:
        policy["lanes"] = {}
    return policy


def _save_model_policy(policy):
    _atomic_write_json(MODEL_POLICY, policy)


def _load_model_state():
    state = _read_json(MODEL_STATE, {})
    if "models" not in state:
        state["models"] = {}
    if "lanes" not in state:
        state["lanes"] = {}
    return state


def _save_model_state(state):
    _atomic_write_json(MODEL_STATE, state)


def _default_harness_config():
    return {
        "mode": "off",
        "generation": 1,
        "runtime_registry": _default_runtime_registry(),
        "profiles": {
            "throughput": {
                "block_on": ["integrity", "boundary", "fabrication"],
                "retry_on": ["correctness", "verification", "review_degraded"],
                "escalate_after_retries": 3,
            },
            "balanced": {
                "block_on": ["integrity", "boundary", "fabrication"],
                "retry_on": ["correctness", "verification", "suspicious_tests", "review_degraded"],
                "escalate_after_retries": 2,
            },
            "high_assurance": {
                "block_on": ["integrity", "boundary", "fabrication", "verification"],
                "retry_on": ["correctness", "suspicious_tests", "quality", "review_degraded"],
                "escalate_after_retries": 1,
            },
        },
    }


def _load_harness_config():
    cfg = _read_json(HARNESS_CONFIG, {})
    defaults = _default_harness_config()
    for key, value in defaults.items():
        if key not in cfg:
            cfg[key] = value
    if "runtime_registry" not in cfg:
        cfg["runtime_registry"] = _default_runtime_registry()
    claude_exports = _load_claude_env_exports()
    env_mode = os.environ.get("BROKE_HARNESS_MODE") or claude_exports.get("BROKE_HARNESS_MODE")
    if env_mode:
        normalized = env_mode.strip().lower()
        if normalized in HARNESS_MODES:
            cfg["mode"] = normalized
    if cfg.get("mode") not in HARNESS_MODES:
        cfg["mode"] = "off"
    return cfg


def _save_harness_config(cfg):
    _atomic_write_json(HARNESS_CONFIG, cfg)


def _default_harness_lane(role):
    return {
        "lane_id": f"lane.{role}.v1",
        "role": role,
        "runtime_binding": "ephemeral_review",
        "session_id": f"session.{role}.v1",
        "status": "idle",
        "health": "healthy",
        "degraded_reason": "",
        "last_review_request_hash": "",
        "last_review_result_id": "",
        "last_contribution_id": "",
        "last_verdict": None,
        "review_count": 0,
        "reuse_count": 0,
        "failure_count": 0,
        "updated_at": None,
    }


def _default_harness_checklist_state():
    return {
        "items": [
            {
                "id": item["id"],
                "label": item["label"],
                "detail": item["detail"],
                "implemented": True,
            }
            for item in HARNESS_IMPLEMENTATION_CHECKLIST
        ]
    }


def _load_harness_state():
    state = _read_json(HARNESS_STATE, {})
    state.setdefault("evaluations", [])
    state.setdefault("last_verdict", None)
    lanes = state.setdefault("lanes", {})
    for role in HARNESS_REVIEW_ROLES:
        current = lanes.get(role, {})
        merged = _default_harness_lane(role)
        if isinstance(current, dict):
            merged.update(current)
        lanes[role] = merged
    state.setdefault("checklist", _default_harness_checklist_state())
    return state


def _save_harness_state(state):
    _atomic_write_json(HARNESS_STATE, state)


def _load_harness_runs():
    data = _read_json(HARNESS_RUNS, {})
    data.setdefault("runs", {})
    return data


def _save_harness_runs(data):
    _atomic_write_json(HARNESS_RUNS, data)


def _load_harness_active_run():
    return _read_json(HARNESS_ACTIVE_RUN, {})


def _save_harness_active_run(data):
    _atomic_write_json(HARNESS_ACTIVE_RUN, data)


def _iso_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _new_run_id():
    seed = f"{time.time()}:{os.getpid()}:{DIR}"
    return f"run_{int(time.time())}_{_sha256_text(seed)[:10]}"


def _harness_run_dir(run_id):
    return HARNESS_RUN_ROOT / run_id


def _append_harness_event(run_id, event_type, phase, actor_kind, actor_id, payload=None, artifact_refs=None):
    run_dir = _harness_run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    events_path = run_dir / "events.jsonl"
    return _append_shared_event(
        events_path,
        run_id,
        event_type,
        phase,
        actor_kind,
        actor_id,
        payload=payload,
        artifact_refs=artifact_refs,
    )


def _register_harness_run(provider, policy_profile, risk_tier, sandbox_profile, workspace_root, allowed_paths, worker_route="broke_router", credential_source="broke_managed", elevated=False):
    runs = _load_harness_runs()
    run_id = _new_run_id()
    record = {
        "run_id": run_id,
        "runtime_mode": "harness",
        "provider": provider,
        "policy_profile": policy_profile,
        "risk_tier": risk_tier,
        "sandbox_profile": sandbox_profile,
        "workspace_root": workspace_root,
        "allowed_paths": allowed_paths,
        "worker_route": worker_route,
        "worker_credential_source": credential_source,
        "elevated": bool(elevated),
        "created_at": _iso_now(),
        "status": "running",
        "last_verdict": None,
        "last_checkpoint_id": None,
    }
    runs["runs"][run_id] = record
    _save_harness_runs(runs)
    _save_harness_active_run({"run_id": run_id, "workspace_root": workspace_root, "policy_profile": policy_profile})
    _append_harness_event(
        run_id,
        "run.registered",
        "registration",
        "harness_controller",
        "broke",
        payload={
            "provider": provider,
            "policy_profile": policy_profile,
            "risk_tier": risk_tier,
            "sandbox_profile": sandbox_profile,
            "workspace_root": workspace_root,
            "allowed_paths": allowed_paths,
            "worker_route": worker_route,
            "worker_credential_source": credential_source,
            "elevated": bool(elevated),
        },
    )
    return record


def _complete_harness_run(run_id, verdict=None, categories=None, checkpoint_id=None):
    runs = _load_harness_runs()
    record = runs.get("runs", {}).get(run_id)
    if not record:
        return None
    record["status"] = "completed"
    record["completed_at"] = _iso_now()
    if verdict is not None:
        record["last_verdict"] = verdict
    if checkpoint_id is not None:
        record["last_checkpoint_id"] = checkpoint_id
    runs["runs"][run_id] = record
    _save_harness_runs(runs)
    active = _load_harness_active_run()
    if active.get("run_id") == run_id:
        _save_harness_active_run({})
    _append_harness_event(
        run_id,
        "run.completed",
        "completion",
        "harness_controller",
        "broke",
        payload={"verdict": verdict, "categories": categories or [], "checkpoint_id": checkpoint_id},
    )
    return record


def _pid_is_live(pid):
    try:
        pid_int = int(pid)
    except Exception:
        return False
    if pid_int <= 0:
        return False
    try:
        os.kill(pid_int, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _reconcile_harness_runs():
    runs = _load_harness_runs()
    active = _load_harness_active_run()
    changed = []
    now = _iso_now()
    for run_id, record in list(runs.get("runs", {}).items()):
        if record.get("status") != "running":
            continue
        run_dir = HARNESS_RUN_ROOT / run_id
        session = _read_json(run_dir / "state" / "session.json", {})
        if not session:
            record["status"] = "failed_launch"
            record["completed_at"] = record.get("completed_at") or now
            reason = "missing_session_state"
            runs["runs"][run_id] = record
            _append_harness_event(
                run_id,
                "run.reconciled",
                "reconciliation",
                "harness_controller",
                "broke",
                payload={"reason": reason, "status": record["status"]},
            )
            changed.append({"run_id": run_id, "status": record["status"], "reason": reason})
            if active.get("run_id") == run_id:
                active = {}
            continue
        pid = session.get("child_pid")
        session_status = session.get("status")
        if _pid_is_live(pid):
            continue
        if session_status == "completed" or session.get("exit_code") is not None:
            record["status"] = "completed"
            record["completed_at"] = record.get("completed_at") or now
            reason = "session_completed"
        else:
            record["status"] = "abandoned"
            record["completed_at"] = record.get("completed_at") or now
            reason = "stale_without_live_session"
        runs["runs"][run_id] = record
        _append_harness_event(
            run_id,
            "run.reconciled",
            "reconciliation",
            "harness_controller",
            "broke",
            payload={"reason": reason, "status": record["status"]},
        )
        changed.append({"run_id": run_id, "status": record["status"], "reason": reason})
        if active.get("run_id") == run_id:
            active = {}
    if changed:
        _save_harness_runs(runs)
        _save_harness_active_run(active)
    return {"changed": changed, "active_run": active}


def _sha256_obj(data):
    return _sha256_text(_canonical_json(data))


def _default_harness_prompt_contracts():
    contracts = [
        {
            "contract_id": "prompt.worker.base.v1",
            "kind": "role_base",
            "role": "worker",
            "version": "1",
            "content": (
                "Worker role. Solve the task under policy constraints. "
                "Do not overclaim completion. Report only supported progress."
            ),
        },
        {
            "contract_id": "prompt.verifier.base.v1",
            "kind": "role_base",
            "role": "verifier",
            "version": "1",
            "content": (
                "Verifier role. Check whether the evidence supports the claimed result. "
                "Prefer insufficiency over optimism when evidence is weak."
            ),
        },
        {
            "contract_id": "prompt.adversary.base.v1",
            "kind": "role_base",
            "role": "adversary",
            "version": "1",
            "content": (
                "Adversary role. Search for the strongest falsification path, bogus test, "
                "or unsupported claim still consistent with the evidence."
            ),
        },
        {
            "contract_id": "policy.throughput.v1",
            "kind": "policy_overlay",
            "name": "throughput",
            "version": "1",
            "content": "Throughput policy. Block integrity violations. Retry correctness problems. Tolerate minor quality issues.",
        },
        {
            "contract_id": "policy.balanced.v1",
            "kind": "policy_overlay",
            "name": "balanced",
            "version": "1",
            "content": "Balanced policy. Block integrity and boundary violations. Retry correctness, verification, and suspicious patterns.",
        },
        {
            "contract_id": "policy.high_assurance.v1",
            "kind": "policy_overlay",
            "name": "high_assurance",
            "version": "1",
            "content": "High assurance policy. Require stronger evidence, stricter verification, and faster escalation on repeated weak retries.",
        },
        {
            "contract_id": "schema.review_output.v1",
            "kind": "schema_contract",
            "name": "review_output",
            "version": "1",
            "content": "Structured output schema: verdict, confidence, supportedness, reasons.",
        },
        {
            "contract_id": "taxonomy.verdicts.v1",
            "kind": "taxonomy_contract",
            "name": "verdicts",
            "version": "1",
            "content": "Verdicts: ACCEPT, ACCEPT_WITH_WARNINGS, RETRY_NARROW, RETRY_BROAD, ESCALATE, BLOCK.",
        },
    ]
    rendered = {}
    for contract in contracts:
        payload = dict(contract)
        payload["content_hash"] = _sha256_obj(
            {
                "kind": payload["kind"],
                "name": payload.get("name", payload.get("role")),
                "version": payload["version"],
                "content": payload["content"],
            }
        )
        rendered[payload["contract_id"]] = payload
    return {"contracts": rendered}


def _load_harness_prompt_contracts():
    data = _read_json(HARNESS_PROMPT_CONTRACTS, {})
    defaults = _default_harness_prompt_contracts()["contracts"]
    contracts = data.get("contracts", {})
    for contract_id, payload in defaults.items():
        contracts.setdefault(contract_id, payload)
    data["contracts"] = contracts
    return data


def _save_harness_prompt_contracts(data):
    _atomic_write_json(HARNESS_PROMPT_CONTRACTS, data)


def _load_harness_prefix_cache():
    data = _read_json(HARNESS_PREFIX_CACHE, {})
    data.setdefault("prefixes", {})
    return data


def _save_harness_prefix_cache(data):
    _atomic_write_json(HARNESS_PREFIX_CACHE, data)


def _load_harness_evidence_cache():
    data = _read_json(HARNESS_EVIDENCE_CACHE, {})
    data.setdefault("artifacts", {})
    data.setdefault("checkpoints", {})
    return data


def _save_harness_evidence_cache(data):
    _atomic_write_json(HARNESS_EVIDENCE_CACHE, data)


def _load_harness_review_cache():
    data = _read_json(HARNESS_REVIEW_CACHE, {})
    data.setdefault("requests", {})
    data.setdefault("results", {})
    data.setdefault("verdicts", {})
    data.setdefault("contributions", {})
    return data


def _save_harness_review_cache(data):
    _atomic_write_json(HARNESS_REVIEW_CACHE, data)


def _resolve_harness_prefix(role, mode, model_family="generic"):
    contracts = _load_harness_prompt_contracts()["contracts"]
    prefix_cache = _load_harness_prefix_cache()
    profile_name = mode if mode in {"throughput", "balanced", "high_assurance"} else "balanced"
    component_ids = [
        f"prompt.{role}.base.v1",
        f"policy.{profile_name}.v1",
        "schema.review_output.v1",
        "taxonomy.verdicts.v1",
    ]
    components = [contracts[contract_id] for contract_id in component_ids]
    rendered_prefix = "\n\n".join(component["content"] for component in components)
    payload = {
        "role": role,
        "compose_strategy_version": "1",
        "model_family": model_family,
        "component_contract_ids": component_ids,
        "component_hashes": [component["content_hash"] for component in components],
        "rendered_prefix": rendered_prefix,
    }
    prefix_hash = _sha256_obj(payload)
    prefix_cache["prefixes"][prefix_hash] = {
        "prefix_id": f"prefix.{role}.{profile_name}.v1",
        "role": role,
        "model_family": model_family,
        "resolved_prefix_hash": prefix_hash,
        "component_contract_ids": component_ids,
        "component_hashes": payload["component_hashes"],
        "semantic_fingerprint": {
            "role_version": "1",
            "policy_version": "1",
            "schema_version": "1",
            "taxonomy_version": "1",
        },
        "rendered_text": rendered_prefix,
    }
    _save_harness_prompt_contracts({"contracts": contracts})
    _save_harness_prefix_cache(prefix_cache)
    return prefix_cache["prefixes"][prefix_hash]


def _store_harness_artifact(cache, kind, content, normalization_version="1", metadata=None):
    metadata = metadata or {}
    payload = {
        "kind": kind,
        "normalization_version": normalization_version,
        "content": content,
        "metadata": metadata,
    }
    artifact_hash = _sha256_obj(payload)
    cache["artifacts"][artifact_hash] = {
        "artifact_id": f"{kind}.{artifact_hash[:12]}",
        "kind": kind,
        "normalization_version": normalization_version,
        "content_hash": artifact_hash,
        "content": content,
        "metadata": metadata,
    }
    return artifact_hash


def _typed_observation(name, text, observed_kind, observation_class):
    body = str(text or "").strip()
    return {
        "name": name,
        "kind": observed_kind,
        "observation_class": observation_class,
        "present": bool(body),
        "line_count": len([line for line in body.splitlines() if line.strip()]),
        "body": body,
    }


def _build_harness_evidence_summary(task="", diff="", tests="", commands="", policy_events="", retry_summary=""):
    return {
        "task_present": bool(task.strip()),
        "diff_present": bool(diff.strip()),
        "tests_present": bool(tests.strip()),
        "commands_present": bool(commands.strip()),
        "policy_events_present": bool(policy_events.strip()),
        "retry_summary_present": bool(retry_summary.strip()),
        "diff_lines": len([line for line in diff.splitlines() if line.strip()]),
        "test_lines": len([line for line in tests.splitlines() if line.strip()]),
        "command_lines": len([line for line in commands.splitlines() if line.strip()]),
        "policy_event_lines": len([line for line in policy_events.splitlines() if line.strip()]),
    }


def _build_harness_evidence_packet(task="", diff="", tests="", commands="", policy_events="", retry_summary="", checkpoint_kind="completion_proposal"):
    evidence_cache = _load_harness_evidence_cache()
    observations = [
        _typed_observation("task", task, "task_statement", "observation"),
        _typed_observation("diff", diff, "diff_summary", "observation"),
        _typed_observation("tests", tests, "test_result_summary", "observation"),
        _typed_observation("commands", commands, "command_trace_summary", "observation"),
        _typed_observation("policy_events", policy_events, "policy_event_summary", "observation"),
        _typed_observation("retry_summary", retry_summary, "retry_summary", "observation"),
    ]
    evidence_summary = _build_harness_evidence_summary(
        task=task,
        diff=diff,
        tests=tests,
        commands=commands,
        policy_events=policy_events,
        retry_summary=retry_summary,
    )
    observation_hashes = []
    task_hash = ""
    for observation in observations:
        artifact_hash = _store_harness_artifact(
            evidence_cache,
            observation["kind"],
            {observation["name"]: observation["body"]},
            metadata={
                "observation_class": observation["observation_class"],
                "present": observation["present"],
                "line_count": observation["line_count"],
            },
        )
        observation_hashes.append(artifact_hash)
        if observation["name"] == "task":
            task_hash = artifact_hash
    summary_hash = _store_harness_artifact(
        evidence_cache,
        "evidence_summary",
        evidence_summary,
        metadata={"observation_class": "inference", "derived_from": observation_hashes},
    )
    artifact_hashes = observation_hashes + [summary_hash]
    checkpoint_payload = {
        "checkpoint_kind": checkpoint_kind,
        "task_packet_hash": task_hash,
        "artifact_hashes": artifact_hashes,
        "observation_hashes": observation_hashes,
        "inference_hashes": [summary_hash],
        "evidence_contract_version": "v2",
        "evidence_summary": evidence_summary,
    }
    checkpoint_hash = _sha256_obj(checkpoint_payload)
    evidence_cache["checkpoints"][checkpoint_hash] = checkpoint_payload
    _save_harness_evidence_cache(evidence_cache)
    return {
        "task_packet_hash": task_hash,
        "artifact_hashes": artifact_hashes,
        "observation_hashes": observation_hashes,
        "inference_hashes": [summary_hash],
        "checkpoint_evidence_hash": checkpoint_hash,
        "checkpoint_kind": checkpoint_kind,
        "evidence_contract_version": "v2",
        "evidence_summary": evidence_summary,
    }


def _review_request(role, prefix_hash, evidence_packet, role_input=None, packet_builder_version="v1"):
    payload = {
        "role": role,
        "resolved_prefix_hash": prefix_hash,
        "packet_builder_version": f"{role}_packet_{packet_builder_version}",
        "task_packet_hash": evidence_packet["task_packet_hash"],
        "evidence_hashes": evidence_packet["artifact_hashes"],
        "observation_hashes": evidence_packet.get("observation_hashes", []),
        "inference_hashes": evidence_packet.get("inference_hashes", []),
        "evidence_contract_version": evidence_packet.get("evidence_contract_version", "v1"),
    }
    if role_input is not None:
        payload["role_input"] = role_input
    review_request_hash = _sha256_obj(payload)
    request = dict(payload)
    request["review_request_hash"] = review_request_hash
    request["review_request_id"] = f"reviewreq.{role}.{review_request_hash[:12]}"
    return request


def _normalise_lane_health(value):
    if not value:
        return "healthy"
    normalized = str(value).strip().lower()
    return normalized if normalized in HARNESS_LANE_HEALTH else None


def _lane_contribution(role, lane_state, request_hash, result_payload=None, source="missing", lane_health="healthy", lane_error=""):
    parsed = (result_payload or {}).get("parsed_output", {}) if isinstance(result_payload, dict) else {}
    payload = {
        "role": role,
        "lane_id": lane_state.get("lane_id", f"lane.{role}.v1"),
        "session_id": lane_state.get("session_id", f"session.{role}.v1"),
        "review_request_hash": request_hash,
        "source": source,
        "lane_health": lane_health,
        "lane_error": lane_error,
        "recommended_verdict": parsed.get("recommended_verdict"),
        "confidence": parsed.get("confidence"),
        "supportedness": parsed.get("supportedness"),
    }
    contribution_hash = _sha256_obj(payload)
    payload["contribution_id"] = f"contrib.{role}.{contribution_hash[:12]}"
    payload["contribution_hash"] = contribution_hash
    return payload


def _resolve_backend_target(token, slots):
    """Resolve a fallback target token to a backend entry.

    Accepts:
    - active slot names (legacy shorthand)
    - backend labels like `Cerebras/GPT-OSS-120B`
    - canonical provider/model identities like `cerebras/gpt-oss-120b`
    """
    if token in slots:
        return _clone_entry(slots[token])

    for backend in BACKENDS_DATA:
        if token == backend.get("label"):
            return _clone_entry(backend)
        if token == _entry_identity(backend):
            return _clone_entry(backend)

    return None



def _pick_fallback_targets_interactively(slots, prompt_title):
    print(f"\n  {prompt_title}\n")
    print("  Available backend targets:\n")
    for i, backend in enumerate(BACKENDS_DATA):
        pin = "" if backend.get("pinned", True) else " ⚠"
        print(f"  {i})  {_provider_display_name(backend['provider'])} :: {backend['model']}  ({backend['label']}){pin}")
    print("\n  Build fallback chain in order.")
    print("  Enter backend numbers one at a time.")
    print("  Press Enter on an empty line when done.")
    print("  Type x to clear the chain.\n")

    resolved = []
    seen = set()
    while True:
        choice = input(f"  Fallback #{len(resolved)+1} > ").strip()
        if choice == "":
            break
        if choice.lower() == "x" and not resolved:
            return []
        try:
            idx = int(choice)
        except ValueError:
            print("  [broke] Enter a backend number, blank to finish, or x to clear.\n")
            continue
        if idx < 0 or idx >= len(BACKENDS_DATA):
            print("  [broke] Backend number out of range.\n")
            continue
        backend = _clone_entry(BACKENDS_DATA[idx])
        identity = _entry_identity(backend)
        if identity in seen:
            print("  [broke] That backend is already in the chain.\n")
            continue
        seen.add(identity)
        resolved.append(backend)
        print(f"  + {backend['label']}")
    print()
    return resolved


def _effective_fallback_chain(mapping, slot, slots=None):
    """Resolve the active fallback chain for a slot.

    Direct lane targets win over legacy lane/backend/slot fallbacks.
    Returns (targets, scope, source_key) where targets may be backend entries or slot names.
    """
    if slots is None:
        slots = _slots(mapping)
    entry = slots.get(slot)
    if not entry:
        return [], None, None

    lane_targets = mapping.get("_lane_fallback_targets", {})
    if slot in lane_targets:
        return list(lane_targets[slot]), "direct", slot

    backend_fallbacks = mapping.get("_backend_fallbacks", {})
    source_identity = _entry_identity(entry)
    lane_key = f"{slot}|{source_identity}"
    if lane_key in backend_fallbacks:
        return list(backend_fallbacks[lane_key]), "lane", lane_key
    if source_identity in backend_fallbacks:
        return list(backend_fallbacks[source_identity]), "backend", source_identity

    slot_fallbacks = mapping.get("_fallbacks", {})
    if slot in slot_fallbacks:
        return list(slot_fallbacks[slot]), "slot", slot

    return [], None, None


def _display_fallback_chain(mapping, slot, slots=None):
    if slots is None:
        slots = _slots(mapping)
    fb_slots, scope, _source_key = _effective_fallback_chain(mapping, slot, slots)
    scope_suffix = " [direct]" if scope == "direct" else (" [lane]" if scope == "lane" else (" [backend]" if scope == "backend" else (" [slot]" if scope == "slot" else "")))
    if not fb_slots:
        return "—"
    if scope == "direct":
        return " → ".join(entry.get("label", "<unknown>") for entry in fb_slots) + scope_suffix
    if scope in ("lane", "backend"):
        rendered = []
        for fb in fb_slots:
            if fb in slots:
                rendered.append(slots[fb]["label"])
            else:
                rendered.append(f"<missing slot: {fb}>")
        return " → ".join(rendered) + scope_suffix
    return " → ".join(fb_slots) + scope_suffix


def cmd_init():
    if not MAPPING.exists() or MAPPING.stat().st_size == 0:
        with open(MAPPING, "w") as f:
            json.dump(DEFAULT_MAPPING, f, indent=2)
        try:
            MAPPING.chmod(0o600)
        except Exception:
            pass
        with open(BACKENDS, "w") as f:
            json.dump(BACKENDS_DATA, f, indent=2)
        try:
            BACKENDS.chmod(0o600)
        except Exception:
            pass
    if not ROTATION_POLICY.exists():
        _save_rotation_policy(_load_rotation_policy())
    if not KEY_STATE.exists():
        _save_key_state(_load_key_state())
    if not MODEL_POLICY.exists():
        _save_model_policy(_load_model_policy())
    if not MODEL_STATE.exists():
        _save_model_state(_load_model_state())
    if not HARNESS_CONFIG.exists():
        _save_harness_config(_load_harness_config())
    if not HARNESS_STATE.exists():
        _save_harness_state(_load_harness_state())
    if not HARNESS_PROMPT_CONTRACTS.exists():
        _save_harness_prompt_contracts(_load_harness_prompt_contracts())
    if not HARNESS_PREFIX_CACHE.exists():
        _save_harness_prefix_cache(_load_harness_prefix_cache())
    if not HARNESS_EVIDENCE_CACHE.exists():
        _save_harness_evidence_cache(_load_harness_evidence_cache())
    if not HARNESS_REVIEW_CACHE.exists():
        _save_harness_review_cache(_load_harness_review_cache())
    if not HARNESS_RUNS.exists():
        _save_harness_runs(_load_harness_runs())
    if not HARNESS_ACTIVE_RUN.exists():
        _save_harness_active_run(_load_harness_active_run())

def load():
    with open(MAPPING) as f:
        mapping = json.load(f)
    changed = False
    for slot in VALID_SLOTS:
        if slot in mapping:
            continue
        default = DEFAULT_MAPPING.get(slot)
        if default is None:
            continue
        mapping[slot] = dict(default)
        changed = True
    if changed:
        _atomic_write_json(MAPPING, mapping)
    return mapping

def _slots(m):
    """Return only slot entries, excluding internal keys like _fallbacks."""
    return {k: v for k, v in m.items() if not k.startswith("_")}


def _slot_display_name(slot):
    return SLOT_DISPLAY_NAMES.get(slot, slot)

def cmd_config():
    m = load()
    slots = _slots(m)
    lane_targets = m.get("_lane_fallback_targets", {})
    access = m.get("_access", {})
    allowed_slots = access.get("allowed_slots")   # None = all allowed
    rpm_limit     = access.get("rpm", 0)          # 0 = unlimited
    tpm_limit     = access.get("tpm", 0)

    cfg = {
        "model_list": [],
        "litellm_settings": {
            "drop_params": True,
            "num_retries": 3,
            "request_timeout": 60,
            "success_callback": ["prometheus"],
            "failure_callback": ["prometheus"],
        },
        "router_settings": {
            "routing_strategy": "simple-shuffle",
            "enable_pre_call_checks": True,
            "set_verbose": False,
            "allowed_fails": 3,
            "cooldown_time": 60,
            "disable_cooldowns": False,
        },
        "general_settings": {
            "health_check_interval": 300,
        }
    }
    env_vals = _load_env_values()
    env_lines = []
    deployments = set()
    deployment_map = {}

    def _add_model_entry(entry):
        label = entry["label"]
        for idx, key_name in enumerate(_key_pool_names(entry["key"], env_vals), start=1):
            dedupe_key = (label, key_name, entry.get("api_base"))
            if dedupe_key in deployments:
                continue
            internal_model_name = f"{label}@@{key_name}"
            params = {
                "model": f"{entry['provider']}/{entry['model']}",
                "api_key": f"os.environ/{key_name}"
            }
            if "api_base" in entry:
                params["api_base"] = entry["api_base"]
            model_entry = {
                "model_name": internal_model_name,
                "litellm_params": params,
                "model_info": {
                    "base_model": label,
                    "description": f"{entry['provider']} · {entry['model']} · {key_name}"
                }
            }
            if rpm_limit:
                model_entry["rpm"] = rpm_limit
            if tpm_limit:
                model_entry["tpm"] = tpm_limit
            cfg["model_list"].append(model_entry)
            deployments.add(dedupe_key)
            deployment_map.setdefault(label, []).append({
                "internal_model_name": internal_model_name,
                "label": label,
                "provider": entry["provider"],
                "model": entry["model"],
                "key_name": key_name,
                "key_index": idx,
                "api_base": entry.get("api_base"),
                "pinned": entry.get("pinned"),
            })

    for source_mapping in _all_config_mappings():
        for entry in _slots(source_mapping).values():
            _add_model_entry(entry)
        for targets in source_mapping.get("_lane_fallback_targets", {}).values():
            for entry in targets:
                _add_model_entry(entry)

    for claude_name, entry in slots.items():
        # Enforce slot access policy only for the active client env exports.
        if allowed_slots is not None and claude_name not in allowed_slots:
            continue
        label = entry["label"]
        model_id = entry["model"]

        if claude_name == "sonnet":
            env_lines.append(f'export ANTHROPIC_DEFAULT_SONNET_MODEL="{model_id}"')
            env_lines.append(f'export ANTHROPIC_DEFAULT_SONNET_MODEL_NAME="Sonnet"')
            env_lines.append(f'export ANTHROPIC_DEFAULT_SONNET_MODEL_DESCRIPTION="{label} · free"')
        elif claude_name == "opus":
            env_lines.append(f'export ANTHROPIC_DEFAULT_OPUS_MODEL="{model_id}"')
            env_lines.append(f'export ANTHROPIC_DEFAULT_OPUS_MODEL_NAME="Opus"')
            env_lines.append(f'export ANTHROPIC_DEFAULT_OPUS_MODEL_DESCRIPTION="{label} · free"')
        elif claude_name == "haiku":
            env_lines.append(f'export ANTHROPIC_SMALL_FAST_MODEL="{model_id}"')
            env_lines.append(f'export ANTHROPIC_DEFAULT_HAIKU_MODEL="{model_id}"')
            env_lines.append(f'export ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME="Haiku"')
            env_lines.append(f'export ANTHROPIC_DEFAULT_HAIKU_MODEL_DESCRIPTION="{label} · free"')
        elif claude_name == "custom":
            env_lines.append(f'export ANTHROPIC_CUSTOM_MODEL_OPTION="{model_id}"')
            env_lines.append(f'export ANTHROPIC_CUSTOM_MODEL_OPTION_NAME="Custom"')
            env_lines.append(f'export ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION="{label} · free"')
        elif claude_name == "subagent":
            env_lines.append(f'export CLAUDE_CODE_SUBAGENT_MODEL="{model_id}"')

    fb_list = []
    for slot in VALID_SLOTS:
        if slot not in slots:
            continue
        fb_targets, scope, _source_key = _effective_fallback_chain(m, slot, slots)
        label = slots[slot]["label"]
        if scope == "direct":
            fb_labels = [entry["label"] for entry in fb_targets if "label" in entry]
        else:
            fb_labels = [slots[fb]["label"] for fb in fb_targets if fb in slots]
        if fb_labels:
            fb_list.append({label: fb_labels})
    if fb_list:
        cfg["router_settings"]["fallbacks"] = fb_list

    with open(CONFIG, "w") as f:
        json.dump(cfg, f, indent=2)
    _atomic_write_json(DEPLOYMENTS, deployment_map)

    _atomic_write_text(DIR / ".env.claude", "\n".join(env_lines) + "\n")

def cmd_list():
    m = load()
    slots = _slots(m)
    print("\n  BrokeLLM Active Routing")
    print("  " + "─" * 60)
    print(f"  {'Slot':<12} {'Backend':<35} {'Fallbacks'}")
    print("  " + "─" * 60)
    for claude in VALID_SLOTS:
        if claude not in slots:
            continue
        e = slots[claude]
        fbs = _display_fallback_chain(m, claude, slots)
        print(f"  {claude:<12} {e['label']:<35} {fbs}")
    print("  " + "─" * 60)
    print("  swap: broke swap\n")

def cmd_models():
    print("\n  Available Gateway Backends")
    print("  " + "─" * 78)
    print(f"  {'#':>3}  {'Provider':<10} {'Model':<48} {'Pin'}")
    print("  " + "─" * 78)
    for i, b in enumerate(BACKENDS_DATA):
        pin = "✓" if b.get("pinned", True) else "⚠ floating"
        print(f"  {i:>3})  {_provider_display_name(b['provider']):<10} {b['model']:<48} {pin}")
    print("  " + "─" * 78)
    print("  ⚠ floating = alias may drift when upstream changes their default\n")

def cmd_swap(provider="claude"):
    m = load()
    slots = _slots(m)
    backends = BACKENDS_DATA

    if provider == "codex":
        family_slots = CODEX_SLOTS
        family_label = "Codex"
    elif provider == "claude":
        family_slots = CLAUDE_SLOTS + SEMANTIC_SLOTS
        family_label = "Claude"
    else:
        family_slots = VALID_SLOTS
        family_label = provider.capitalize()

    print(f"\n  Remap a {family_label} slot to a backend:\n")
    if provider == "claude":
        print("  Default         [runtime] → Claude's built-in tier default")
        print()
    displayable = [(slot, slots[slot]) for slot in family_slots if slot in slots]
    for i, (slot, entry) in enumerate(displayable):
        print(f"  {i})  {_slot_display_name(slot):<14} [{slot}] → {entry['label']}")
    print("  x)  cancel\n")
    slot_input = input("  Pick slot > ").strip()
    if slot_input == "x":
        return
    try:
        idx = int(slot_input)
        target = displayable[idx][0]
    except (ValueError, IndexError):
        print("  [broke] invalid selection")
        return

    print("\n  Available backends:\n")
    for i, b in enumerate(backends):
        pin = "" if b.get("pinned", True) else " ⚠"
        print(f"  {i})  {_provider_display_name(b['provider'])} :: {b['model']}  ({b['label']}){pin}")
    print()
    choice = int(input("  Pick backend > ").strip())
    b = backends[choice]
    entry = {"provider": b["provider"], "model": b["model"], "label": b["label"], "key": b["key"], "pinned": b.get("pinned")}
    if "api_base" in b:
        entry["api_base"] = b["api_base"]
    m[target] = entry
    with open(MAPPING, "w") as f:
        json.dump(m, f, indent=2)
    with open(BACKENDS, "w") as f:
        json.dump(backends, f, indent=2)
    pin_warn = "  ⚠  floating alias — may drift on upstream updates" if not b.get("pinned", True) else ""
    print(f"\n  [{target}] → {b['provider']}/{b['model']} ({b['label']}){pin_warn}")
    cmd_config()


def cmd_swap_many(provider, *assignments):
    m = load()
    slots = _slots(m)

    provider_key = (provider or "").strip().lower()
    if provider_key == "codex":
        family_slots = set(CODEX_SLOTS)
    elif provider_key == "claude":
        family_slots = set(CLAUDE_SLOTS + SEMANTIC_SLOTS)
    elif provider_key == "all":
        family_slots = set(VALID_SLOTS)
    else:
        print("\n  [broke] Usage: broke swap-many <claude|codex|all> <slot=target> [slot=target ...]\n")
        sys.exit(1)

    displayable = [slot for slot in VALID_SLOTS if slot in slots and slot in family_slots]
    index_map = {str(i): slot for i, slot in enumerate(displayable)}

    if not assignments:
        print("\n  [broke] swap-many targets")
        print("  " + "─" * 62)
        print(f"  scope: {provider_key}")
        for i, slot in enumerate(displayable):
            print(f"  {i}) {_slot_display_name(slot):<14} [{slot}] → {slots[slot]['label']}")
        print("\n  Usage: broke swap-many <claude|codex|all> <slot=target> [slot=target ...]")
        print("  slot can be: slot name, numeric index from list above, or 'all'")
        sys.exit(1)

    updates = []
    for item in assignments:
        token = (item or "").strip()
        if "=" not in token:
            print(f"\n  [broke] Invalid assignment '{token}'. Expected format: <slot=target>\n")
            sys.exit(1)
        slot_token, target_token = token.split("=", 1)
        slot_token = slot_token.strip()
        target_token = target_token.strip()
        if not slot_token or not target_token:
            print(f"\n  [broke] Invalid assignment '{token}'. Expected format: <slot=target>\n")
            sys.exit(1)
        target = _resolve_backend_target(target_token, slots)
        if target is None:
            print(f"\n  [broke] Unknown backend target '{target_token}'. Use a backend label or provider/model.\n")
            sys.exit(1)

        resolved_slots = []
        if slot_token.lower() == "all":
            resolved_slots = list(displayable)
        elif slot_token in index_map:
            resolved_slots = [index_map[slot_token]]
        else:
            if slot_token not in VALID_SLOTS:
                print(f"\n  [broke] Unknown slot '{slot_token}'. Valid: {', '.join(VALID_SLOTS)}\n")
                sys.exit(1)
            if slot_token not in family_slots:
                print(f"\n  [broke] Slot '{slot_token}' is outside '{provider_key}' scope.\n")
                sys.exit(1)
            resolved_slots = [slot_token]

        for slot in resolved_slots:
            updates.append((slot, target))

    deduped_updates = []
    seen = set()
    for slot, target in updates:
        key = (slot, target.get("label", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped_updates.append((slot, target))

    for slot, target in deduped_updates:
        m[slot] = target

    _atomic_write_json(MAPPING, m)
    _atomic_write_json(BACKENDS, BACKENDS_DATA)
    cmd_config()

    print("\n  broke swap-many")
    print("  " + "─" * 62)
    print(f"  scope: {provider_key}")
    for slot, target in deduped_updates:
        pin_warn = "  ⚠ floating alias" if not target.get("pinned", True) else ""
        print(f"  {slot:<12} → {target['label']:<25} ({target['provider']}/{target['model']}){pin_warn}")
    print()


def _family_slots_for_provider(provider):
    provider_key = (provider or "").strip().lower()
    if provider_key == "codex":
        return provider_key, list(CODEX_SLOTS)
    if provider_key == "claude":
        return provider_key, list(CLAUDE_SLOTS + SEMANTIC_SLOTS)
    if provider_key == "all":
        return provider_key, list(VALID_SLOTS)
    return None, None


def cmd_swap_many_interactive(provider):
    m = load()
    slots = _slots(m)
    provider_key, family_order = _family_slots_for_provider(provider)
    if provider_key is None:
        print("\n  [broke] Usage: broke swap many [claude|codex|all] <slot=target> [slot=target ...]\n")
        sys.exit(1)

    displayable = [slot for slot in family_order if slot in slots]
    if not displayable:
        print(f"\n  [broke] No slots available for scope '{provider_key}'.\n")
        sys.exit(1)

    print(f"\n  Remap multiple {provider_key} slots to one backend:\n")
    for i, slot in enumerate(displayable):
        print(f"  {i})  {_slot_display_name(slot):<14} [{slot}] → {slots[slot]['label']}")
    print("  all) all listed slots")
    print("  x)   cancel\n")

    picked = input("  Pick slots (e.g. 0,2,4 or all) > ").strip().lower()
    if picked == "x":
        return

    selected_slots = []
    if picked == "all":
        selected_slots = list(displayable)
    else:
        raw_items = [p.strip() for p in picked.split(",") if p.strip()]
        if not raw_items:
            print("  [broke] no slots selected")
            return
        seen = set()
        for item in raw_items:
            try:
                idx = int(item)
            except ValueError:
                print(f"  [broke] invalid slot index: {item}")
                return
            if idx < 0 or idx >= len(displayable):
                print(f"  [broke] slot index out of range: {item}")
                return
            slot = displayable[idx]
            if slot not in seen:
                seen.add(slot)
                selected_slots.append(slot)

    print("\n  Available backends:\n")
    for i, b in enumerate(BACKENDS_DATA):
        pin = "" if b.get("pinned", True) else " ⚠"
        print(f"  {i})  {_provider_display_name(b['provider'])} :: {b['model']}  ({b['label']}){pin}")
    print("  x)  cancel\n")

    slot_targets = {}
    for slot in selected_slots:
        current_label = slots[slot]["label"]
        choice = input(f"  Pick backend for {slot} (current: {current_label}, Enter=keep) > ").strip().lower()
        if choice == "x":
            return
        if choice == "":
            slot_targets[slot] = _clone_entry(slots[slot])
            continue
        try:
            backend_idx = int(choice)
            backend = BACKENDS_DATA[backend_idx]
        except (ValueError, IndexError):
            print(f"  [broke] invalid backend selection for {slot}")
            return
        slot_targets[slot] = _clone_entry(backend)

    for slot in selected_slots:
        m[slot] = slot_targets[slot]

    _atomic_write_json(MAPPING, m)
    _atomic_write_json(BACKENDS, BACKENDS_DATA)
    cmd_config()

    print("\n  swap-many applied")
    print("  " + "─" * 62)
    print(f"  scope   : {provider_key}")
    for slot in selected_slots:
        target = slot_targets[slot]
        pin_warn = "  ⚠ floating alias" if not target.get("pinned", True) else ""
        print(f"  {slot:<12} → {target['label']:<25} ({target['provider']}/{target['model']}){pin_warn}")
    print()

def cmd_metrics(port=4000, raw=False):
    try:
        req = urllib.request.Request(f"http://localhost:{port}/metrics", headers=_proxy_auth_headers())
        resp = urllib.request.urlopen(req, timeout=10)
        text = resp.read().decode()
    except Exception as e:
        print(f"\n  [broke] Could not reach gateway metrics: {e}\n")
        sys.exit(1)

    if raw:
        print(text)
        return

    success, failure = {}, {}
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        m = re.match(r'litellm_deployment_successful_responses[^{]*\{[^}]*litellm_model_name="([^"]+)"[^}]*\}\s+([\d.]+)', line)
        if m:
            success[m.group(1)] = success.get(m.group(1), 0) + float(m.group(2))
            continue
        m = re.match(r'litellm_deployment_failure_responses[^{]*\{[^}]*litellm_model_name="([^"]+)"[^}]*\}\s+([\d.]+)', line)
        if m:
            failure[m.group(1)] = failure.get(m.group(1), 0) + float(m.group(2))

    all_models = set(success) | set(failure)
    if not all_models:
        print("\n  No request metrics yet — send some traffic first.\n")
        print("  (raw output: broke metrics --raw)\n")
        return

    print("\n  BrokeLLM Gateway Metrics")
    print("  " + "─" * 55)
    print(f"  {'Model':<28} {'OK':>6} {'Fail':>6} {'Error%':>8}")
    print("  " + "─" * 55)
    for model in sorted(all_models):
        ok   = int(success.get(model, 0))
        fail = int(failure.get(model, 0))
        total = ok + fail
        pct  = f"{fail/total*100:.0f}%" if total > 0 else "—"
        print(f"  {model:<28} {ok:>6} {fail:>6} {pct:>8}")
    print()


# ── Teams ─────────────────────────────────────────────────────────────

def _load_teams():
    if not TEAMS.exists():
        return {}
    with open(TEAMS) as f:
        return json.load(f)

def _save_teams(teams):
    with open(TEAMS, "w") as f:
        json.dump(teams, f, indent=2)

def cmd_team_save(name, mode="1"):
    m = load()
    slots = _slots(m)
    fallbacks = m.get("_fallbacks", {})
    backend_fallbacks = m.get("_backend_fallbacks", {})
    lane_fallback_targets = m.get("_lane_fallback_targets", {})
    access    = m.get("_access", {})
    teams = _load_teams()
    mode_int = 1 if str(mode).lower() in ("1", "cli") else 0
    teams[name] = {"mode": mode_int, "slots": slots, "fallbacks": fallbacks, "backend_fallbacks": backend_fallbacks, "lane_fallback_targets": lane_fallback_targets, "access": access}
    _save_teams(teams)
    mode_label = "CLI agent" if mode_int == 1 else "app router"
    print(f"\n  Team '{name}' saved  [mode {mode_int} · {mode_label}]:")
    allowed = access.get("allowed_slots")
    for slot in VALID_SLOTS:
        if slot not in slots:
            continue
        if allowed is not None and slot not in allowed:
            continue
        fbs = _display_fallback_chain(m, slot, slots)
        print(f"    {slot:<12} → {slots[slot]['label']}  (fallbacks: {fbs})")
    if allowed is not None:
        print(f"  access: slots={allowed}  rpm={access.get('rpm',0) or '∞'}  tpm={access.get('tpm',0) or '∞'}")
    print()

def cmd_team_load(name):
    teams = _load_teams()
    if name not in teams:
        print(f"\n  [broke] No team named '{name}'.")
        if teams:
            print(f"  Available: {', '.join(teams)}")
        else:
            print("  No teams saved yet. Use: broke team save <name>")
        print()
        sys.exit(1)
    team = teams[name]
    # support old format (plain mapping dict)
    if "slots" in team:
        slots, mode = team["slots"], team.get("mode", 1)
        fallbacks   = team.get("fallbacks", {})
        backend_fallbacks = team.get("backend_fallbacks", {})
        lane_fallback_targets = team.get("lane_fallback_targets", {})
    else:
        slots, mode, fallbacks, backend_fallbacks, lane_fallback_targets = team, 1, {}, {}, {}

    access = team.get("access", {})
    mapping = dict(slots)
    if fallbacks:
        mapping["_fallbacks"] = fallbacks
    if backend_fallbacks:
        mapping["_backend_fallbacks"] = backend_fallbacks
    if lane_fallback_targets:
        mapping["_lane_fallback_targets"] = lane_fallback_targets
    if access:
        mapping["_access"] = access
    with open(MAPPING, "w") as f:
        json.dump(mapping, f, indent=2)
    cmd_config()

    env_path = DIR / ".env.claude"
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    lines = [l for l in lines if not l.startswith("export BROKE_MODE=")]
    lines.append(f'export BROKE_MODE="{mode}"')
    env_path.write_text("\n".join(lines) + "\n")

    mode_label = "CLI agent" if int(mode) == 1 else "app router"
    print(f"\n  Team '{name}' loaded  [mode {mode} · {mode_label}]:")
    effective_mapping = dict(slots)
    if fallbacks:
        effective_mapping["_fallbacks"] = fallbacks
    if backend_fallbacks:
        effective_mapping["_backend_fallbacks"] = backend_fallbacks
    if lane_fallback_targets:
        effective_mapping["_lane_fallback_targets"] = lane_fallback_targets
    for slot in VALID_SLOTS:
        if slot in slots:
            fbs = _display_fallback_chain(effective_mapping, slot, slots)
            print(f"    {slot:<12} → {slots[slot]['label']}  (fallbacks: {fbs})")
    print()

def cmd_team_list():
    teams = _load_teams()
    if not teams:
        print("\n  No teams saved. Use: broke team save <name>\n")
        return
    active = _slots(load())
    print("\n  Saved Teams")
    print("  " + "─" * 60)
    for name, team in teams.items():
        if "slots" in team:
            slots, mode = team["slots"], team.get("mode", 1)
            fallbacks   = team.get("fallbacks", {})
            backend_fallbacks = team.get("backend_fallbacks", {})
            lane_fallback_targets = team.get("lane_fallback_targets", {})
            access      = team.get("access", {})
        else:
            slots, mode, fallbacks, backend_fallbacks, lane_fallback_targets, access = team, 1, {}, {}, {}, {}
        mode_label    = "CLI agent" if int(mode) == 1 else "app router"
        allowed_slots = access.get("allowed_slots")
        rpm           = access.get("rpm", 0)
        tpm           = access.get("tpm", 0)
        print(f"\n  [{name}]  mode {mode} · {mode_label}", end="")
        if allowed_slots or rpm or tpm:
            parts = []
            if allowed_slots: parts.append(f"slots={','.join(allowed_slots)}")
            if rpm:           parts.append(f"rpm={rpm}")
            if tpm:           parts.append(f"tpm={tpm}")
            print(f"  │  access: {', '.join(parts)}", end="")
        print()
        effective_mapping = dict(slots)
        if fallbacks:
            effective_mapping["_fallbacks"] = fallbacks
        if backend_fallbacks:
            effective_mapping["_backend_fallbacks"] = backend_fallbacks
        if lane_fallback_targets:
            effective_mapping["_lane_fallback_targets"] = lane_fallback_targets
        for slot in VALID_SLOTS:
            if slot not in slots:
                continue
            if allowed_slots is not None and slot not in allowed_slots:
                print(f"    ✗ {slot:<12} {slots[slot]['label']:<25} (blocked by access policy)")
                continue
            marker = "→" if active.get(slot, {}).get("label") == slots[slot]["label"] else " "
            fbs = _display_fallback_chain(effective_mapping, slot, slots)
            print(f"    {marker} {slot:<12} {slots[slot]['label']:<25} fallbacks: {fbs}")
    print()

def cmd_team_delete(name):
    teams = _load_teams()
    if name not in teams:
        print(f"\n  [broke] No team named '{name}'.\n")
        sys.exit(1)
    del teams[name]
    _save_teams(teams)
    print(f"\n  Team '{name}' deleted.\n")

def cmd_team_fallback(team_name, slot, *fb_slots):
    teams = _load_teams()
    if team_name not in teams:
        print(f"\n  [broke] No team named '{team_name}'.")
        if teams:
            print(f"  Available: {', '.join(teams)}")
        print()
        sys.exit(1)
    team = teams[team_name]
    # normalise to new format
    if "slots" not in team:
        team = {"mode": 1, "slots": team, "fallbacks": {}, "backend_fallbacks": {}, "lane_fallback_targets": {}}
    if "lane_fallback_targets" not in team:
        team["lane_fallback_targets"] = {}
    if slot not in VALID_SLOTS:
        print(f"\n  [broke] Invalid slot '{slot}'. Valid: {', '.join(VALID_SLOTS)}\n")
        sys.exit(1)

    entry = team["slots"].get(slot)
    if not entry:
        print(f"\n  [broke] Slot '{slot}' not configured in team '{team_name}'.\n")
        sys.exit(1)

    if fb_slots:
        resolved = []
        for token in fb_slots:
            target = _resolve_backend_target(token, team["slots"])
            if target is None:
                print(f"\n  [broke] Unknown fallback target '{token}'. Use a slot name, backend label, or provider/model.\n")
                sys.exit(1)
            resolved.append(target)
    else:
        resolved = _pick_fallback_targets_interactively(team["slots"], f"Set fallback chain for team '{team_name}' slot '{slot}'")

    if resolved:
        team["lane_fallback_targets"][slot] = resolved
    else:
        team["lane_fallback_targets"].pop(slot, None)
    teams[team_name] = team
    _save_teams(teams)
    chain = " → ".join(target["label"] for target in resolved) if resolved else "(cleared)"
    print(f"\n  [{team_name}] {slot} direct fallback chain ({entry['label']}): {chain}\n")


def cmd_team_access(team_name, allowed_slots=None, rpm=None, tpm=None):
    """Set access policy on a team: which slots are exposed and rate limits."""
    teams = _load_teams()
    if team_name not in teams:
        print(f"\n  [broke] No team named '{team_name}'.\n")
        sys.exit(1)
    team = teams[team_name]
    if "slots" not in team:
        team = {"mode": 1, "slots": team, "fallbacks": {}, "access": {}}
    if "access" not in team:
        team["access"] = {}

    if allowed_slots is not None:
        bad = [s for s in allowed_slots if s not in VALID_SLOTS]
        if bad:
            print(f"\n  [broke] Invalid slots: {bad}. Valid: {VALID_SLOTS}\n")
            sys.exit(1)
        team["access"]["allowed_slots"] = allowed_slots
    if rpm is not None:
        team["access"]["rpm"] = int(rpm)
    if tpm is not None:
        team["access"]["tpm"] = int(tpm)

    teams[team_name] = team
    _save_teams(teams)
    a = team["access"]
    print(f"\n  [{team_name}] access policy updated:")
    print(f"    allowed slots : {a.get('allowed_slots') or 'all'}")
    print(f"    rpm limit     : {a.get('rpm', 0) or '∞'}")
    print(f"    tpm limit     : {a.get('tpm', 0) or '∞'}")
    print()


def cmd_key_policy(provider=None, mode=None, cooldown=None, retries=None, order=None):
    policy = _load_rotation_policy()
    providers = policy.setdefault("providers", {})
    env_vals = _load_env_values()

    if provider is None and mode is None and cooldown is None and retries is None and order is None:
        print("\n  broke key-policy")
        print("  " + "─" * 78)
        print(f"  generation: {policy.get('generation', 1)}\n")
        for name in sorted(providers):
            cfg = providers[name]
            print(f"  [{name}]")
            print(f"    mode             : {cfg.get('mode', 'rotate_on_rate_limit')}")
            print(f"    cooldown_seconds : {cfg.get('cooldown_seconds', 300)}")
            print(f"    max_retries      : {cfg.get('max_retries', 1)}")
            print(f"    order            : {', '.join(cfg.get('order', [])) or '—'}")
        print()
        return

    if provider is None:
        print("\n  [broke] Provider is required when updating key policy.\n")
        sys.exit(1)

    if provider not in {b["provider"] for b in BACKENDS_DATA}:
        print(f"\n  [broke] Unknown provider '{provider}'.\n")
        sys.exit(1)

    cfg = providers.setdefault(provider, _provider_rotation_defaults(env_vals).get(provider, {
        "mode": "rotate_on_rate_limit",
        "order": [],
        "cooldown_seconds": 300,
        "max_retries": 1,
    }))
    if mode is not None:
        cfg["mode"] = mode
    if cooldown is not None:
        cfg["cooldown_seconds"] = int(cooldown)
    if retries is not None:
        cfg["max_retries"] = int(retries)
    if order is not None:
        cfg["order"] = [item.strip() for item in order.split(",") if item.strip()]

    policy["generation"] = int(policy.get("generation", 1)) + 1
    _save_rotation_policy(policy)
    print(f"\n  [{provider}] key policy updated")
    print(f"    generation       : {policy['generation']}")
    print(f"    mode             : {cfg.get('mode')}")
    print(f"    cooldown_seconds : {cfg.get('cooldown_seconds')}")
    print(f"    max_retries      : {cfg.get('max_retries')}")
    print(f"    order            : {', '.join(cfg.get('order', [])) or '—'}\n")


def cmd_key_state(action=None, key_name=None, status=None):
    state = _load_key_state()
    keys = state.setdefault("keys", {})

    if action in (None, "show"):
        print("\n  broke key-state")
        print("  " + "─" * 78)
        if not keys:
            print("  no key state recorded yet\n")
            return
        for name in sorted(keys):
            info = keys[name]
            print(f"  [{name}]")
            print(f"    status         : {info.get('status', 'healthy')}")
            print(f"    last_reason    : {info.get('last_reason', '—')}")
            print(f"    cooldown_until : {info.get('cooldown_until', 0)}")
            print(f"    updated_at     : {info.get('updated_at', '—')}")
            print(f"    failures       : {info.get('failures', 0)}")
            print(f"    generation     : {info.get('generation', '—')}")
        print()
        return

    if action != "set" or not key_name or not status:
        print("\n  [broke] Usage: broke key-state [show] | broke key-state set <KEY_NAME> <healthy|cooldown|blocked|auth_failed> [cooldown_seconds]\n")
        sys.exit(1)

    if status not in {"healthy", "cooldown", "blocked", "auth_failed"}:
        print(f"\n  [broke] Invalid key status '{status}'.\n")
        sys.exit(1)

    import time
    policy = _load_rotation_policy()
    cooldown_seconds = 0
    if status == "cooldown":
        for provider, cfg in policy.get("providers", {}).items():
            order = cfg.get("order", [])
            if key_name in order:
                cooldown_seconds = int(cfg.get("cooldown_seconds", 300))
                break
    keys[key_name] = {
        **keys.get(key_name, {}),
        "status": status,
        "last_reason": "manual_set",
        "cooldown_until": (int(time.time()) + cooldown_seconds) if status == "cooldown" else 0,
        "updated_at": int(time.time()),
        "generation": policy.get("generation", 1),
    }
    _save_key_state(state)
    print(f"\n  [{key_name}] state set to {status}\n")


def cmd_model_policy(slot=None, mode=None, cooldown=None, retries=None, order=None):
    policy = _load_model_policy()
    lanes = policy.setdefault("lanes", {})
    m = load()
    slots = _slots(m)

    if slot is None and mode is None and cooldown is None and retries is None and order is None:
        print("\n  broke model-policy")
        print("  " + "─" * 78)
        print(f"  generation: {policy.get('generation', 1)}\n")
        for lane in VALID_SLOTS:
            cfg = lanes.get(lane)
            if not cfg:
                continue
            print(f"  [{lane}]")
            print(f"    mode             : {cfg.get('mode', 'priority_order')}")
            print(f"    cooldown_seconds : {cfg.get('cooldown_seconds', 300)}")
            print(f"    max_retries      : {cfg.get('max_retries', 1)}")
            print(f"    order            : {', '.join(cfg.get('order', [])) or '—'}")
        print()
        return

    if slot not in VALID_SLOTS:
        print(f"\n  [broke] Invalid slot '{slot}'. Valid: {', '.join(VALID_SLOTS)}\n")
        sys.exit(1)

    cfg = lanes.setdefault(slot, {
        "mode": "priority_order",
        "order": [slots[slot]["label"]] if slot in slots else [],
        "cooldown_seconds": 300,
        "max_retries": 2,
    })
    if mode is not None:
        cfg["mode"] = mode
    if cooldown is not None:
        cfg["cooldown_seconds"] = int(cooldown)
    if retries is not None:
        cfg["max_retries"] = int(retries)
    if order is not None:
        resolved = []
        for token in [item.strip() for item in order.split(",") if item.strip()]:
            target = _resolve_backend_target(token, slots)
            if target is None:
                print(f"\n  [broke] Unknown model target '{token}'. Use a backend label or provider/model.\n")
                sys.exit(1)
            resolved.append(target["label"])
        cfg["order"] = resolved

    policy["generation"] = int(policy.get("generation", 1)) + 1
    _save_model_policy(policy)
    print(f"\n  [{slot}] model policy updated")
    print(f"    generation       : {policy['generation']}")
    print(f"    mode             : {cfg.get('mode')}")
    print(f"    cooldown_seconds : {cfg.get('cooldown_seconds')}")
    print(f"    max_retries      : {cfg.get('max_retries')}")
    print(f"    order            : {', '.join(cfg.get('order', [])) or '—'}\n")


def cmd_model_state(action=None, model_label=None, status=None):
    state = _load_model_state()
    models = state.setdefault("models", {})

    if action in (None, "show"):
        print("\n  broke model-state")
        print("  " + "─" * 78)
        if not models:
            print("  no model state recorded yet\n")
            return
        for name in sorted(models):
            info = models[name]
            print(f"  [{name}]")
            print(f"    status         : {info.get('status', 'healthy')}")
            print(f"    last_reason    : {info.get('last_reason', '—')}")
            print(f"    cooldown_until : {info.get('cooldown_until', 0)}")
            print(f"    updated_at     : {info.get('updated_at', '—')}")
            print(f"    failures       : {info.get('failures', 0)}")
            print(f"    generation     : {info.get('generation', '—')}")
        print()
        return

    if action != "set" or not model_label or not status:
        print("\n  [broke] Usage: broke model-state [show] | broke model-state set <MODEL_LABEL> <healthy|cooldown|blocked|incompatible>\n")
        sys.exit(1)

    if status not in {"healthy", "cooldown", "blocked", "incompatible"}:
        print(f"\n  [broke] Invalid model status '{status}'.\n")
        sys.exit(1)

    import time
    policy = _load_model_policy()
    cooldown_seconds = 0
    if status == "cooldown":
        for _lane, cfg in policy.get("lanes", {}).items():
            if model_label in cfg.get("order", []):
                cooldown_seconds = int(cfg.get("cooldown_seconds", 300))
                break
    models[model_label] = {
        **models.get(model_label, {}),
        "status": status,
        "last_reason": "manual_set",
        "cooldown_until": (int(time.time()) + cooldown_seconds) if status == "cooldown" else 0,
        "updated_at": int(time.time()),
        "generation": policy.get("generation", 1),
    }
    _save_model_state(state)
    print(f"\n  [{model_label}] state set to {status}\n")


# ── Profiles ──────────────────────────────────────────────────────────
# A profile = client identity. References a team for routing config,
# can restrict slot access further and carry a description.

def _load_profiles():
    if not PROFILES.exists():
        return {}
    with open(PROFILES) as f:
        return json.load(f)

def _save_profiles(profiles):
    with open(PROFILES, "w") as f:
        json.dump(profiles, f, indent=2)


def _load_client_bindings():
    if not CLIENT_BINDINGS.exists():
        return {"tokens": {}}
    with open(CLIENT_BINDINGS) as f:
        data = json.load(f)
    if "tokens" not in data:
        data["tokens"] = {}
    return data


def _save_client_bindings(data):
    with open(CLIENT_BINDINGS, "w") as f:
        json.dump(data, f, indent=2)


def _generate_client_token():
    return "broke-app-" + secrets.token_urlsafe(24)


def cmd_client_token_bind(profile_name, token=None, name=""):
    profiles = _load_profiles()
    if profile_name not in profiles:
        print(f"\n  [broke] No profile named '{profile_name}'.\n")
        sys.exit(1)
    bindings = _load_client_bindings()
    token_value = token or _generate_client_token()
    bindings["tokens"][token_value] = {
        "profile": profile_name,
        "name": name or profile_name,
        "created_at": int(time.time()),
    }
    _save_client_bindings(bindings)
    print(json.dumps({
        "token": token_value,
        "profile": profile_name,
        "name": bindings["tokens"][token_value]["name"],
    }))


def cmd_client_token_list():
    bindings = _load_client_bindings()
    print("\n  Bound Client Tokens")
    print("  " + "─" * 60)
    if not bindings.get("tokens"):
        print("\n  (none)\n")
        return
    for token, info in sorted(bindings["tokens"].items(), key=lambda item: item[1].get("created_at", 0)):
        preview = token[:14] + "..." if len(token) > 17 else token
        print(f"\n  {preview}")
        print(f"    profile : {info.get('profile', 'unknown')}")
        print(f"    name    : {info.get('name', '—')}")
    print()


def cmd_client_token_revoke(token):
    bindings = _load_client_bindings()
    if token not in bindings.get("tokens", {}):
        print(f"\n  [broke] Unknown client token.\n")
        sys.exit(1)
    del bindings["tokens"][token]
    _save_client_bindings(bindings)
    print("\n  Client token revoked.\n")

def cmd_profile_new(name, team_name, description="", allowed_slots=None, rpm="0", tpm="0"):
    teams = _load_teams()
    if team_name not in teams:
        print(f"\n  [broke] No team named '{team_name}'.")
        if teams:
            print(f"  Available teams: {', '.join(teams)}")
        print()
        sys.exit(1)
    profiles = _load_profiles()
    profiles[name] = {
        "team": team_name,
        "description": description,
        "access": {
            "allowed_slots": allowed_slots,
            "rpm": int(rpm),
            "tpm": int(tpm),
        }
    }
    _save_profiles(profiles)
    print(f"\n  Profile '{name}' created:")
    print(f"    team          : {team_name}")
    print(f"    description   : {description or '—'}")
    print(f"    allowed slots : {allowed_slots or 'all from team'}")
    print(f"    rpm limit     : {int(rpm) or '∞'}")
    print(f"    tpm limit     : {int(tpm) or '∞'}")
    print()

def cmd_profile_load(name):
    profiles = _load_profiles()
    if name not in profiles:
        print(f"\n  [broke] No profile named '{name}'.")
        if profiles:
            print(f"  Available: {', '.join(profiles)}")
        else:
            print("  No profiles yet. Use: broke profile new <name> <team>")
        print()
        sys.exit(1)
    p = profiles[name]
    teams = _load_teams()
    team_name = p["team"]
    if team_name not in teams:
        print(f"\n  [broke] Profile '{name}' references team '{team_name}' which no longer exists.\n")
        sys.exit(1)

    # Load team first
    cmd_team_load(team_name)

    # Then apply profile's access policy on top (overrides team access)
    m = load()
    pa = p.get("access", {})
    if pa.get("allowed_slots") or pa.get("rpm") or pa.get("tpm"):
        m["_access"] = pa
        with open(MAPPING, "w") as f:
            json.dump(m, f, indent=2)
        cmd_config()

    print(f"  Profile '{name}' active  [{p.get('description') or team_name}]")
    a = p.get("access", {})
    print(f"    allowed slots : {a.get('allowed_slots') or 'all from team'}")
    print(f"    rpm limit     : {a.get('rpm', 0) or '∞'}")
    print(f"    tpm limit     : {a.get('tpm', 0) or '∞'}")
    print()

def cmd_profile_list():
    profiles = _load_profiles()
    if not profiles:
        print("\n  No profiles. Use: broke profile new <name> <team>\n")
        return
    print("\n  Client Profiles")
    print("  " + "─" * 60)
    for name, p in profiles.items():
        a = p.get("access", {})
        slots_str = ", ".join(a.get("allowed_slots") or []) or "all"
        rpm_str   = str(a.get("rpm", 0)) if a.get("rpm") else "∞"
        tpm_str   = str(a.get("tpm", 0)) if a.get("tpm") else "∞"
        print(f"\n  [{name}]  → team: {p['team']}")
        if p.get("description"):
            print(f"    {p['description']}")
        print(f"    slots: {slots_str}   rpm: {rpm_str}   tpm: {tpm_str}")
    print()

def cmd_profile_delete(name):
    profiles = _load_profiles()
    if name not in profiles:
        print(f"\n  [broke] No profile named '{name}'.\n")
        sys.exit(1)
    del profiles[name]
    _save_profiles(profiles)
    print(f"\n  Profile '{name}' deleted.\n")


def cmd_fallback(slot, *fb_slots):
    """Set direct backend fallback chain on the live mapping without requiring a team."""
    if slot not in VALID_SLOTS:
        print(f"\n  [broke] Invalid slot '{slot}'. Valid: {', '.join(VALID_SLOTS)}\n")
        sys.exit(1)
    m = load()
    slots = _slots(m)
    if slot not in slots:
        print(f"\n  [broke] Slot '{slot}' not configured.\n")
        sys.exit(1)

    if fb_slots:
        resolved = []
        for token in fb_slots:
            target = _resolve_backend_target(token, slots)
            if target is None:
                print(f"\n  [broke] Unknown fallback target '{token}'. Use a slot name, backend label, or provider/model.\n")
                sys.exit(1)
            resolved.append(target)
    else:
        resolved = _pick_fallback_targets_interactively(slots, f"Set fallback chain for slot '{slot}'")

    lane_targets = m.get("_lane_fallback_targets", {})
    if resolved:
        lane_targets[slot] = resolved
    else:
        lane_targets.pop(slot, None)
    m["_lane_fallback_targets"] = lane_targets
    with open(MAPPING, "w") as f:
        json.dump(m, f, indent=2)
    cmd_config()
    chain = " → ".join(target["label"] for target in resolved) if resolved else "(cleared)"
    print(f"\n  [{slot}] direct fallback chain ({slots[slot]['label']}): {chain}\n")


def _team_mapping(team_name):
    teams = _load_teams()
    if team_name not in teams:
        print(f"\n  [broke] No team named '{team_name}'.")
        if teams:
            print(f"  Available: {', '.join(teams)}")
        print()
        sys.exit(1)
    team = teams[team_name]
    if "slots" in team:
        slots = team["slots"]
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


def _all_config_mappings():
    mappings = [load()]
    teams = _load_teams()
    for name in teams:
        mappings.append(_team_mapping(name))
    return mappings


def _print_fallback_policy(title, mapping):
    slots = _slots(mapping)
    print(f"\n  {title}")
    print("  " + "─" * 78)
    print(f"  {'Slot':<12} {'Backend':<25} {'Fallback Policy'}")
    print("  " + "─" * 78)
    any_rows = False
    for slot in VALID_SLOTS:
        if slot not in slots:
            continue
        any_rows = True
        entry = slots[slot]
        print(f"  {slot:<12} {entry['label']:<25} {_display_fallback_chain(mapping, slot, slots)}")
    if not any_rows:
        print("  (no configured slots)")
    print()


def cmd_fallback_policy(team_name=None, show_teams=False):
    if show_teams:
        teams = _load_teams()
        if team_name:
            _print_fallback_policy(f"broke fallback policy  [team: {team_name}]", _team_mapping(team_name))
            return
        if not teams:
            print("\n  No teams saved. Use: broke team save <name>\n")
            return
        for name in teams:
            _print_fallback_policy(f"broke fallback policy  [team: {name}]", _team_mapping(name))
        return

    _print_fallback_policy("broke fallback policy  [live mapping]", load())


def cmd_doctor(port=4000):
    oks = warns = fails = 0
    def _ok(msg):   nonlocal oks;   oks   += 1; print(f"  ✓  {msg}")
    def _warn(msg): nonlocal warns; warns += 1; print(f"  ⚠  {msg}")
    def _fail(msg): nonlocal fails; fails += 1; print(f"  ✗  {msg}")

    print("\n  broke doctor")
    print("  " + "─" * 58)

    preflight = _preflight_findings()
    _print_findings_section("preflight integrity", preflight, _ok, _warn, _fail)

    # ── harness ───────────────────────────────────────────────
    print("\n  [harness]")
    harness_cfg = _load_harness_config()
    harness_state = _load_harness_state()
    _ok(f"mode={harness_cfg.get('mode', 'off')} generation={harness_cfg.get('generation', 1)}")
    last_verdict = harness_state.get("last_verdict")
    if last_verdict:
        verdict = last_verdict.get("verdict", "unknown")
        if verdict in {"BLOCK", "ESCALATE"}:
            _warn(f"last verdict={verdict} categories={','.join(last_verdict.get('categories', [])) or 'none'}")
        else:
            _ok(f"last verdict={verdict}")
    else:
        _ok("no prior harness evaluations recorded")

    # ── env vars ───────────────────────────────────────────────
    print("\n  [env vars]")
    env_vals = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env_vals[k.strip()] = v.strip()

    m = load()
    slots = _slots(m)
    needed = {entry["key"] for entry in slots.values()}
    for key in sorted(needed):
        val = env_vals.get(key) or os.environ.get(key, "")
        if not val:
            _fail(f"{key} — not set")
        elif "XXXXX" in val:
            _warn(f"{key} — placeholder not filled in")
        else:
            _ok(f"{key} — set")

    # ── key rotation ───────────────────────────────────────────
    print("\n  [key rotation]")
    policy = _load_rotation_policy()
    state = _load_key_state().get("keys", {})
    _ok(f"policy generation {policy.get('generation', 1)} loaded")
    for provider in sorted(policy.get("providers", {})):
        cfg = policy["providers"][provider]
        _ok(f"{provider}: mode={cfg.get('mode')} cooldown={cfg.get('cooldown_seconds', 300)}s retries={cfg.get('max_retries', 1)}")
    for key_name, info in sorted(state.items()):
        status = info.get("status", "healthy")
        reason = info.get("last_reason", "—")
        if status in {"blocked", "auth_failed"}:
            _warn(f"{key_name}: {status} ({reason})")
        elif status == "cooldown":
            _warn(f"{key_name}: cooldown ({reason}) until {info.get('cooldown_until', 0)}")
        else:
            _ok(f"{key_name}: healthy")

    # ── model orchestration ────────────────────────────────────
    print("\n  [model orchestration]")
    model_policy = _load_model_policy()
    model_state = _load_model_state().get("models", {})
    _ok(f"model policy generation {model_policy.get('generation', 1)} loaded")
    for lane in VALID_SLOTS:
        cfg = model_policy.get("lanes", {}).get(lane)
        if cfg:
            _ok(f"{lane}: mode={cfg.get('mode')} cooldown={cfg.get('cooldown_seconds', 300)}s retries={cfg.get('max_retries', 1)}")
    for label, info in sorted(model_state.items()):
        status = info.get("status", "healthy")
        reason = info.get("last_reason", "—")
        if status in {"blocked", "incompatible"}:
            _warn(f"{label}: {status} ({reason})")
        elif status == "cooldown":
            _warn(f"{label}: cooldown ({reason}) until {info.get('cooldown_until', 0)}")
        else:
            _ok(f"{label}: healthy")

    # ── gateway ────────────────────────────────────────────────
    print("\n  [gateway]")
    base = f"http://localhost:{port}"
    gateway_up = False

    try:
        urllib.request.urlopen(f"{base}/health/liveliness", timeout=3)
        _ok("liveliness — proxy is up")
        gateway_up = True
    except Exception as e:
        _fail(f"liveliness — proxy not reachable ({e})")

    if gateway_up:
        try:
            urllib.request.urlopen(f"{base}/health/readiness", timeout=3)
            _ok("readiness — proxy ready to serve")
        except Exception as e:
            _warn(f"readiness — {e}")

    # ── upstream models ────────────────────────────────────────
    print("\n  [upstream models]")
    if not gateway_up:
        _warn("skipped — gateway not reachable")
    else:
        try:
            resp = urllib.request.urlopen(f"{base}/health", timeout=30)
            data = json.loads(resp.read())
            for ep in data.get("healthy_endpoints", []):
                _ok(ep.get("model", "?"))
            for ep in data.get("unhealthy_endpoints", []):
                err = str(ep.get("error", ""))[:72]
                _fail(f"{ep.get('model','?')} — {err}")
        except Exception as e:
            _warn(f"could not reach /health — {e}")

    # ── lane config ────────────────────────────────────────────
    print("\n  [lane config]")
    access = m.get("_access", {})
    allowed = access.get("allowed_slots")
    for slot in VALID_SLOTS:
        if slot not in slots:
            continue
        if allowed is not None and slot not in allowed:
            _warn(f"{slot:<12} blocked by access policy")
            continue
        entry = slots[slot]
        fbs = _display_fallback_chain(m, slot, slots).replace("—", "none")
        pinned = _entry_pin_state(entry)
        if pinned is False:
            _warn(f"{slot:<12} {entry['label']:<26} fallbacks: {fbs}  floating alias")
        elif pinned is None:
            _warn(f"{slot:<12} {entry['label']:<26} fallbacks: {fbs}  pin state unknown")
        else:
            _ok(f"{slot:<12} {entry['label']:<26} fallbacks: {fbs}")

    # ── harness verdict ───────────────────────────────────────
    validate_findings = _validate_findings()
    harness_summary = _harness_verdict(harness_cfg, preflight, validate_findings)
    print("\n  [harness verdict]")
    verdict = harness_summary["verdict"]
    if verdict in {"BLOCK", "ESCALATE"}:
        _warn(f"{verdict}  ({', '.join(harness_summary['categories']) or 'no categories'})")
    elif verdict.startswith("RETRY"):
        _warn(f"{verdict}  ({', '.join(harness_summary['categories']) or 'no categories'})")
    elif verdict == "ACCEPT_WITH_WARNINGS":
        _warn(f"{verdict}  ({', '.join(harness_summary['categories']) or 'no categories'})")
    else:
        _ok(verdict)

    # ── summary ────────────────────────────────────────────────
    print()
    total = oks + warns + fails
    status = "✓ all good" if fails == 0 and warns == 0 else ("✗ issues found" if fails > 0 else "⚠ warnings")
    print(f"  {status}  —  {oks}/{total} passed", end="")
    if warns: print(f", {warns} warning(s)", end="")
    if fails: print(f", {fails} failure(s)", end="")
    print("\n")


def cmd_export(path):
    """Export teams + profiles to a shareable JSON file (no secrets)."""
    data = {
        "broke_export": True,
        "teams":    _load_teams(),
        "profiles": _load_profiles(),
        "client_bindings": _load_client_bindings(),
    }
    out = pathlib.Path(path)
    out.write_text(json.dumps(data, indent=2))
    t = len(data["teams"])
    p = len(data["profiles"])
    print(f"\n  Exported {t} team(s) + {p} profile(s) → {out}\n")

def cmd_import(path, overwrite=False):
    """Import teams + profiles from an exported JSON file."""
    src = pathlib.Path(path)
    if not src.exists():
        print(f"\n  [broke] File not found: {path}\n")
        sys.exit(1)
    data = json.loads(src.read_text())
    if not data.get("broke_export"):
        print(f"\n  [broke] Not a valid BrokeLLM export file.\n")
        sys.exit(1)

    teams    = _load_teams()
    profiles = _load_profiles()
    bindings = _load_client_bindings()
    imported_t = imported_p = skipped_t = skipped_p = 0
    imported_b = skipped_b = 0

    for name, team in data.get("teams", {}).items():
        if name in teams and not overwrite:
            skipped_t += 1
        else:
            teams[name] = team
            imported_t += 1
    for name, profile in data.get("profiles", {}).items():
        if name in profiles and not overwrite:
            skipped_p += 1
        else:
            profiles[name] = profile
            imported_p += 1
    for token, binding in data.get("client_bindings", {}).get("tokens", {}).items():
        if token in bindings.get("tokens", {}) and not overwrite:
            skipped_b += 1
        else:
            bindings.setdefault("tokens", {})[token] = binding
            imported_b += 1

    _save_teams(teams)
    _save_profiles(profiles)
    _save_client_bindings(bindings)
    print(f"\n  Imported: {imported_t} team(s), {imported_p} profile(s), {imported_b} client token binding(s)")
    if skipped_t or skipped_p or skipped_b:
        print(f"  Skipped (already exist): {skipped_t} team(s), {skipped_p} profile(s), {skipped_b} client token binding(s)")
        print(f"  Use --overwrite to replace existing.")
    print()


# ── Explain ───────────────────────────────────────────────────────────

def cmd_explain(slot, port=4000):
    """Show full resolution path and health for a slot."""
    import os
    if slot not in VALID_SLOTS:
        print(f"\n  [broke] Unknown slot '{slot}'. Valid: {', '.join(VALID_SLOTS)}\n")
        sys.exit(1)
    m = load()
    slots = _slots(m)
    if slot not in slots:
        print(f"\n  [broke] Slot '{slot}' not configured.\n")
        sys.exit(1)

    entry = slots[slot]
    fb_chain, fb_scope, _fb_source_key = _effective_fallback_chain(m, slot, slots)

    access = m.get("_access", {})
    allowed = access.get("allowed_slots")
    blocked = allowed is not None and slot not in allowed

    print(f"\n  broke explain  [{slot}]")
    print("  " + "─" * 58)
    if blocked:
        print(f"\n  [BLOCKED]  slot '{slot}' is excluded by the active access policy")
        print(f"             requests to this slot will be rejected at the gateway")
    print(f"\n  slot          : {slot}")
    print(f"  selected      : {entry['label']}")
    print(f"  backend       : {entry['provider']}/{entry['model']}")

    if fb_chain:
        scope_label = "direct" if fb_scope == "direct" else ("lane" if fb_scope == "lane" else ("backend" if fb_scope == "backend" else "slot"))
        print(f"  fallback chain ({scope_label}-scoped):")
        for i, fb in enumerate(fb_chain):
            if fb_scope == "direct":
                print(f"    {i+1}. {fb['label']}  ({fb['provider']}/{fb['model']})")
            else:
                fb_label = slots[fb]["label"] if fb in slots else f"<missing slot: {fb}>"
                print(f"    {i+1}. {fb} → {fb_label}")
    else:
        print(f"  fallback chain: none")

    print(f"\n  resolution path:")
    print(f"    - client requested  : {slot}")
    print(f"    - mapped to         : {entry['label']}")

    env_path = DIR / ".env"
    env_vals = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env_vals[k.strip()] = v.strip()
    key = entry.get("key", "")
    key_set = bool(env_vals.get(key) or os.environ.get(key, ""))
    print(f"    - api key ({key:<22}): {'set' if key_set else 'MISSING'}")

    try:
        health = _entry_health_status(entry, port=port)
        print(f"    - health            : {health}")
        print(f"    - fallback triggered: no (static resolution)")
    except Exception:
        print(f"    - health            : gateway not reachable")

    if FREEZE.exists():
        print(f"\n  [FROZEN]  swap is currently blocked")

    print()


# ── Route (dry-run) ───────────────────────────────────────────────────

def cmd_route(slot, port=4000):
    """Dry-run: show what would be selected without calling."""
    if slot not in VALID_SLOTS:
        print(f"\n  [broke] Unknown slot '{slot}'. Valid: {', '.join(VALID_SLOTS)}\n")
        sys.exit(1)
    m = load()
    slots = _slots(m)
    if slot not in slots:
        print(f"\n  [broke] Slot '{slot}' not configured.\n")
        sys.exit(1)

    entry = slots[slot]
    fb_chain, _fb_scope, _fb_source_key = _effective_fallback_chain(m, slot, slots)

    access = m.get("_access", {})
    allowed = access.get("allowed_slots")
    blocked = allowed is not None and slot not in allowed

    print(f"\n  broke route  (dry-run)  [{slot}]")
    print("  " + "─" * 58)
    if blocked:
        print(f"\n  [BLOCKED]  slot '{slot}' is excluded by the active access policy")
        print(f"             this request would be rejected at the gateway")
    print(f"\n  would route to:")
    print(f"    primary       : {entry['label']}  ({entry['provider']}/{entry['model']})")
    for i, fb in enumerate(fb_chain):
        if _fb_scope == "direct":
            print(f"    fallback {i+1:<5}: {fb['label']}  ({fb['provider']}/{fb['model']})")
        elif fb in slots:
            fe = slots[fb]
            print(f"    fallback {i+1:<5}: {fe['label']}  ({fe['provider']}/{fe['model']})")
        else:
            print(f"    fallback {i+1:<5}: <missing slot: {fb}>")

    provider = entry.get("provider", "")
    model    = entry.get("model", "")
    latency  = "fast" if provider in ("cerebras", "groq") else "medium"
    cost     = "free" if ":free" in model or provider == "huggingface" else "paid"
    print(f"\n  latency tier  : {latency}")
    print(f"  cost tier     : {cost}")

    try:
        health = _entry_health_status(entry, port=port)
        print(f"  health        : {health}")
    except Exception:
        print(f"  health        : gateway not reachable")

    print()


# ── Validate ──────────────────────────────────────────────────────────

def cmd_validate():
    """Pre-flight hard validation of the current config."""
    oks = warns = fails = 0
    def _ok(msg):   nonlocal oks;   oks   += 1; print(f"  ✓  {msg}")
    def _warn(msg): nonlocal warns; warns += 1; print(f"  ⚠  {msg}")
    def _fail(msg): nonlocal fails; fails += 1; print(f"  ✗  {msg}")

    print("\n  broke validate  (pre-flight)")
    print("  " + "─" * 58)
    findings = _validate_findings()
    grouped = {
        "slot fields": {"ok": [m for m in findings["ok"] if "all required fields present" in m], "warn": [], "fail": [m for m in findings["fail"] if "missing fields" in m]},
        "provider format": {"ok": [m for m in findings["ok"] if "provider '" in m], "warn": [m for m in findings["warn"] if "unknown provider" in m], "fail": []},
        "api keys": {"ok": [m for m in findings["ok"] if " — set" in m], "warn": [m for m in findings["warn"] if "placeholder" in m], "fail": [m for m in findings["fail"] if " — not set" in m or "no api key field" in m]},
        "fallback chains": {
            "ok": [m for m in findings["ok"] if "fallback" in m or "→" in m or "no fallback chains defined" in m],
            "warn": [m for m in findings["warn"] if "fallback" in m or "circular fallback" in m],
            "fail": [m for m in findings["fail"] if "target slot not configured" in m or "self-referential fallback" in m or "direct fallback target missing fields" in m or "source slot" in m],
        },
        "alias stability": {
            "ok": [m for m in findings["ok"] if "pinned alias" in m],
            "warn": [m for m in findings["warn"] if "floating alias" in m or "pin state" in m],
            "fail": [],
        },
    }

    for title, section in grouped.items():
        _print_findings_section(title, section, _ok, _warn, _fail)

    # Summary
    total = oks + warns + fails
    status = "✓ config is valid" if fails == 0 and warns == 0 else ("✗ validation failed" if fails > 0 else "⚠ valid with warnings")
    print(f"\n  {status}  —  {oks}/{total} passed", end="")
    if warns: print(f", {warns} warning(s)", end="")
    if fails: print(f", {fails} failure(s)", end="")
    print("\n")
    if fails > 0:
        sys.exit(1)


# ── Snapshots ─────────────────────────────────────────────────────────

def _ensure_snapshots():
    SNAPSHOTS.mkdir(exist_ok=True)

def cmd_snapshot_save():
    import datetime
    _ensure_snapshots()
    m = load()
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    snap_file = SNAPSHOTS / f"{ts}.json"
    with open(snap_file, "w") as f:
        json.dump(m, f, indent=2)
    print(f"\n  Snapshot saved: {ts}")
    snaps = sorted(SNAPSHOTS.glob("*.json"))
    if len(snaps) > 20:
        for old in snaps[:-20]:
            old.unlink()
    print(f"  restore with: broke snapshot restore 0\n")

def cmd_snapshot_list():
    _ensure_snapshots()
    snaps = sorted(SNAPSHOTS.glob("*.json"), reverse=True)
    if not snaps:
        print("\n  No snapshots. Use: broke snapshot save\n")
        return
    print("\n  Saved Snapshots")
    print("  " + "─" * 66)
    active = load()
    for i, snap in enumerate(snaps):
        data = json.loads(snap.read_text())
        slot_info = "  ".join(
            f"{k}→{v['label']}" for k, v in _slots(data).items() if k in VALID_SLOTS
        )
        marker = "→" if data == active else " "
        print(f"  {marker} {i})  {snap.stem}  {slot_info}")
    print()

def cmd_snapshot_restore(snapshot_id):
    _ensure_snapshots()
    snaps = sorted(SNAPSHOTS.glob("*.json"), reverse=True)
    if not snaps:
        print("\n  No snapshots available.\n")
        sys.exit(1)
    target = None
    try:
        idx = int(snapshot_id)
        if 0 <= idx < len(snaps):
            target = snaps[idx]
    except (ValueError, TypeError):
        for snap in snaps:
            if snap.stem == snapshot_id:
                target = snap
                break
    if target is None:
        print(f"\n  [broke] Snapshot '{snapshot_id}' not found. Run: broke snapshot list\n")
        sys.exit(1)
    data = json.loads(target.read_text())
    with open(MAPPING, "w") as f:
        json.dump(data, f, indent=2)
    cmd_config()
    print(f"\n  Restored snapshot: {target.stem}\n")


# ── Probe ─────────────────────────────────────────────────────────────

def cmd_probe(slot, port=4000):
    """Send a tiny live test request to verify a slot works end-to-end."""
    import time
    if slot not in VALID_SLOTS:
        print(f"\n  [broke] Unknown slot '{slot}'. Valid: {', '.join(VALID_SLOTS)}\n")
        sys.exit(1)
    m = load()
    slots = _slots(m)
    if slot not in slots:
        print(f"\n  [broke] Slot '{slot}' not configured.\n")
        sys.exit(1)

    entry = slots[slot]
    label = entry["label"]

    print(f"\n  broke probe  [{slot}]  →  {label}")
    print("  " + "─" * 58)
    print(f"  sending test request (non-streaming)...")

    payload = json.dumps({
        "model": label,
        "messages": [{"role": "user", "content": "Reply with exactly the word: ok"}],
        "max_tokens": 8,
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        f"http://localhost:{port}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json", **_proxy_auth_headers()},
        method="POST",
    )

    start = time.time()
    failed = False
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        elapsed = time.time() - start
        data = json.loads(resp.read())
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        usage   = data.get("usage", {})
        print(f"  ✓ status      : 200 OK")
        print(f"  ✓ latency     : {elapsed:.2f}s")
        print(f"  ✓ response    : {repr(content)}")
        if usage:
            print(f"  ✓ tokens      : {usage.get('prompt_tokens',0)} in / {usage.get('completion_tokens',0)} out")
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start
        body = e.read().decode()[:200]
        print(f"  ✗ HTTP {e.code}     : {body}")
        print(f"  ✗ latency     : {elapsed:.2f}s")
        failed = True
    except Exception as e:
        elapsed = time.time() - start
        print(f"  ✗ error       : {e}")
        print(f"  ✗ latency     : {elapsed:.2f}s")
        failed = True
    print()
    if failed:
        sys.exit(1)


def cmd_harness(action=None, value=None, worker=None, verifier=None, adversary=None, risk="normal", retries="0"):
    cfg = _load_harness_config()
    state = _load_harness_state()
    prompt_contracts = _load_harness_prompt_contracts()
    prefix_cache = _load_harness_prefix_cache()
    evidence_cache = _load_harness_evidence_cache()
    review_cache = _load_harness_review_cache()

    if action in (None, "", "status"):
        print("\n  broke harness")
        print("  " + "─" * 58)
        print(f"\n  mode        : {cfg.get('mode', 'off')}")
        print(f"  generation  : {cfg.get('generation', 1)}")
        profile = cfg.get("profiles", {}).get(cfg.get("mode", "off"))
        if profile:
            print(f"  block on    : {', '.join(profile.get('block_on', [])) or 'none'}")
            print(f"  retry on    : {', '.join(profile.get('retry_on', [])) or 'none'}")
        registry = cfg.get("runtime_registry", {})
        if registry:
            print("\n  runtimes:")
            for provider in ("gemini", "claude", "codex", "openrouter", "groq", "cerebras", "local"):
                runtime = registry.get(provider)
                if not runtime:
                    continue
                print(
                    f"    {provider:<10} {runtime.get('binding_kind', 'unknown'):<16} "
                    f"{runtime.get('runtime_class', 'unknown')}"
                )
        last = state.get("last_verdict")
        if last:
            print(f"  last verdict: {last.get('verdict', 'unknown')}")
            print(f"  categories  : {', '.join(last.get('categories', [])) or 'none'}")
            print(f"  risk        : {last.get('risk', 'normal')}")
            print(f"  retries     : {last.get('retries', 0)}")
            if last.get("checkpoint_evidence_hash"):
                print(f"  checkpoint  : {last['checkpoint_evidence_hash'][:12]}")
        else:
            print("  last verdict: none")
        print("\n  cache:")
        print(f"    contracts : {len(prompt_contracts.get('contracts', {}))}")
        print(f"    prefixes  : {len(prefix_cache.get('prefixes', {}))}")
        print(f"    evidence  : {len(evidence_cache.get('artifacts', {}))} artifacts / {len(evidence_cache.get('checkpoints', {}))} checkpoints")
        print(f"    reviews   : {len(review_cache.get('results', {}))} role results / {len(review_cache.get('verdicts', {}))} verdicts")
        print("\n  lanes:")
        for role in HARNESS_REVIEW_ROLES:
            lane = state.get("lanes", {}).get(role, {})
            print(
                f"    {role:<10} {lane.get('health', 'healthy'):<8} "
                f"status={lane.get('status', 'idle'):<10} "
                f"reviews={lane.get('review_count', 0):<3} "
                f"reused={lane.get('reuse_count', 0):<3}"
            )
        checklist_items = state.get("checklist", {}).get("items", [])
        if checklist_items:
            completed = sum(1 for item in checklist_items if item.get("implemented"))
            print(f"\n  checklist   : {completed}/{len(checklist_items)} implemented")
        active_run = _load_harness_active_run()
        runs = _load_harness_runs().get("runs", {})
        if active_run.get("run_id"):
            run = runs.get(active_run["run_id"], {})
            print("\n  runtime:")
            print(f"    active run : {active_run['run_id']}")
            if run:
                print(f"    provider   : {run.get('provider', 'unknown')}")
                print(f"    policy     : {run.get('policy_profile', 'unknown')}")
                print(f"    sandbox    : {run.get('sandbox_profile', 'unknown')}")
                print(f"    worker     : {run.get('worker_route', 'broke_router')} / {run.get('worker_credential_source', 'broke_managed')}")
                print(f"    workspace  : {run.get('workspace_root', 'unknown')}")
        elif runs:
            latest = max(runs.values(), key=lambda item: item.get("created_at", ""))
            print("\n  runtime:")
            print("    active run : none")
            print(f"    last run   : {latest.get('run_id', 'unknown')} ({latest.get('status', 'unknown')})")
        print()
        return

    if action == "checklist":
        checklist = state.get("checklist", _default_harness_checklist_state())
        print("\n  broke harness checklist")
        print("  " + "─" * 58)
        for item in checklist.get("items", []):
            mark = "✓" if item.get("implemented") else " "
            print(f"\n  [{mark}] {item.get('label', item.get('id', 'item'))}")
            print(f"      {item.get('detail', '')}")
        print()
        return

    if action == "run-register":
        provider = sys.argv[sys.argv.index("--provider")+1] if "--provider" in sys.argv else "claude"
        policy_profile = sys.argv[sys.argv.index("--policy")+1] if "--policy" in sys.argv else cfg.get("mode", "off")
        sandbox_profile = sys.argv[sys.argv.index("--sandbox")+1] if "--sandbox" in sys.argv else "normal"
        workspace_root = sys.argv[sys.argv.index("--workspace")+1] if "--workspace" in sys.argv else str(DIR)
        worker_route = sys.argv[sys.argv.index("--worker-route")+1] if "--worker-route" in sys.argv else "broke_router"
        credential_source = sys.argv[sys.argv.index("--credential-source")+1] if "--credential-source" in sys.argv else ("provider_managed" if worker_route == "provider_direct" else "broke_managed")
        elevated = "--elevated" in sys.argv
        allowed_paths = []
        if "--allowed-paths" in sys.argv:
            allowed_paths = [p for p in sys.argv[sys.argv.index("--allowed-paths")+1].split(":") if p]
        if not allowed_paths:
            allowed_paths = [workspace_root, str(DIR)]
        record = _register_harness_run(
            provider,
            policy_profile,
            risk,
            sandbox_profile,
            workspace_root,
            allowed_paths,
            worker_route=worker_route,
            credential_source=credential_source,
            elevated=elevated,
        )
        print(json.dumps(record))
        return

    if action == "event":
        run_id = sys.argv[sys.argv.index("--run-id")+1] if "--run-id" in sys.argv else ""
        event_type = sys.argv[sys.argv.index("--event-type")+1] if "--event-type" in sys.argv else ""
        phase = sys.argv[sys.argv.index("--phase")+1] if "--phase" in sys.argv else "runtime"
        actor_kind = sys.argv[sys.argv.index("--actor-kind")+1] if "--actor-kind" in sys.argv else "harness_controller"
        actor_id = sys.argv[sys.argv.index("--actor-id")+1] if "--actor-id" in sys.argv else "broke"
        payload = json.loads(sys.argv[sys.argv.index("--payload")+1]) if "--payload" in sys.argv else {}
        artifact_refs = json.loads(sys.argv[sys.argv.index("--artifact-refs")+1]) if "--artifact-refs" in sys.argv else []
        if not run_id or not event_type:
            print("\n  [broke] harness event requires --run-id and --event-type\n")
            sys.exit(1)
        event = _append_harness_event(run_id, event_type, phase, actor_kind, actor_id, payload=payload, artifact_refs=artifact_refs)
        print(json.dumps(event))
        return

    if action == "complete":
        run_id = sys.argv[sys.argv.index("--run-id")+1] if "--run-id" in sys.argv else ""
        verdict = sys.argv[sys.argv.index("--verdict")+1] if "--verdict" in sys.argv else None
        checkpoint_id = sys.argv[sys.argv.index("--checkpoint-id")+1] if "--checkpoint-id" in sys.argv else None
        categories = json.loads(sys.argv[sys.argv.index("--categories")+1]) if "--categories" in sys.argv else []
        if not run_id:
            print("\n  [broke] harness complete requires --run-id\n")
            sys.exit(1)
        record = _complete_harness_run(run_id, verdict=verdict, categories=categories, checkpoint_id=checkpoint_id)
        if record is None:
            print(f"\n  [broke] unknown run id: {run_id}\n")
            sys.exit(1)
        print(json.dumps(record))
        return

    if action == "reconcile":
        result = _reconcile_harness_runs()
        print(json.dumps(result))
        return

    if action == "set":
        target = (value or "").strip().lower()
        if target not in HARNESS_MODES:
            print(f"\n  [broke] Invalid harness mode '{value}'. Valid: {', '.join(HARNESS_MODES)}\n")
            sys.exit(1)
        if cfg.get("mode") != target:
            cfg["mode"] = target
            cfg["generation"] = int(cfg.get("generation", 1)) + 1
            _save_harness_config(cfg)
        print(f"\n  [harness] mode set to {target}\n")
        return

    if action == "evaluate":
        task = sys.argv[sys.argv.index("--task")+1] if "--task" in sys.argv else ""
        diff = sys.argv[sys.argv.index("--diff")+1] if "--diff" in sys.argv else ""
        tests = sys.argv[sys.argv.index("--tests")+1] if "--tests" in sys.argv else ""
        commands = sys.argv[sys.argv.index("--commands")+1] if "--commands" in sys.argv else ""
        policy_events = sys.argv[sys.argv.index("--policy-events")+1] if "--policy-events" in sys.argv else ""
        retry_summary = sys.argv[sys.argv.index("--retry-summary")+1] if "--retry-summary" in sys.argv else ""
        checkpoint_kind = sys.argv[sys.argv.index("--checkpoint-kind")+1] if "--checkpoint-kind" in sys.argv else "completion_proposal"
        model_family = sys.argv[sys.argv.index("--model-family")+1] if "--model-family" in sys.argv else "generic"
        lane_health = {
            "worker": _normalise_lane_health(sys.argv[sys.argv.index("--worker-health")+1] if "--worker-health" in sys.argv else "healthy"),
            "verifier": _normalise_lane_health(sys.argv[sys.argv.index("--verifier-health")+1] if "--verifier-health" in sys.argv else "healthy"),
            "adversary": _normalise_lane_health(sys.argv[sys.argv.index("--adversary-health")+1] if "--adversary-health" in sys.argv else "healthy"),
        }
        lane_errors = {
            "worker": sys.argv[sys.argv.index("--worker-error")+1] if "--worker-error" in sys.argv else "",
            "verifier": sys.argv[sys.argv.index("--verifier-error")+1] if "--verifier-error" in sys.argv else "",
            "adversary": sys.argv[sys.argv.index("--adversary-error")+1] if "--adversary-error" in sys.argv else "",
        }
        role_verdicts = {
            "worker": _normalise_role_verdict(worker),
            "verifier": _normalise_role_verdict(verifier),
            "adversary": _normalise_role_verdict(adversary),
        }
        invalid = []
        for name, raw_value in {"worker": worker, "verifier": verifier, "adversary": adversary}.items():
            if raw_value is not None and role_verdicts[name] is None:
                invalid.append(name)
        for name, value in lane_health.items():
            if value is None:
                invalid.append(f"{name}-health")
        if invalid:
            print(f"\n  [broke] Invalid harness role input(s): {', '.join(invalid)}. Verdicts: {', '.join(HARNESS_VERDICTS)}. Lane health: {', '.join(HARNESS_LANE_HEALTH)}\n")
            sys.exit(1)
        evidence_packet = _build_harness_evidence_packet(
            task=task,
            diff=diff,
            tests=tests,
            commands=commands,
            policy_events=policy_events,
            retry_summary=retry_summary,
            checkpoint_kind=checkpoint_kind,
        )
        explicit_roles = {name for name, verdict in role_verdicts.items() if verdict}
        lane_states = state.get("lanes", {})
        contributions = {}
        reused_roles = []
        for role_name in HARNESS_REVIEW_ROLES:
            lane = lane_states.setdefault(role_name, _default_harness_lane(role_name))
            prefix = _resolve_harness_prefix(role_name, cfg.get("mode", "off"), model_family=model_family)
            request = _review_request(
                role_name,
                prefix["resolved_prefix_hash"],
                evidence_packet,
                role_input=role_verdicts.get(role_name) if role_name in explicit_roles else None,
            )
            review_cache["requests"][request["review_request_hash"]] = request
            lane["last_review_request_hash"] = request["review_request_hash"]
            lane["status"] = "evaluating"
            lane["updated_at"] = _iso_now()
            if role_name in explicit_roles:
                result_payload = {
                    "review_result_id": f"reviewres.{role_name}.{request['review_request_hash'][:12]}",
                    "role": role_name,
                    "review_request_hash": request["review_request_hash"],
                    "prompt_contract_fingerprint": prefix["semantic_fingerprint"],
                    "parsed_output": {
                        "recommended_verdict": role_verdicts[role_name],
                        "confidence": 1.0,
                        "supportedness": "manual",
                    },
                }
                review_cache["results"][request["review_request_hash"]] = result_payload
                lane["reuse_count"] = int(lane.get("reuse_count", 0) or 0)
                source = "explicit"
            elif request["review_request_hash"] in review_cache["results"]:
                cached = review_cache["results"][request["review_request_hash"]]
                role_verdicts[role_name] = cached.get("parsed_output", {}).get("recommended_verdict")
                if role_verdicts[role_name]:
                    reused_roles.append(role_name)
                result_payload = cached
                lane["reuse_count"] = int(lane.get("reuse_count", 0) or 0) + 1
                source = "cached"
            else:
                result_payload = None
                source = "missing"

            lane["review_count"] = int(lane.get("review_count", 0) or 0) + 1
            lane["health"] = lane_health[role_name]
            lane["degraded_reason"] = lane_errors[role_name] if lane_health[role_name] in {"degraded", "failed"} else ""
            if lane["health"] in {"degraded", "failed"}:
                lane["failure_count"] = int(lane.get("failure_count", 0) or 0) + 1
            lane["status"] = "reviewed" if result_payload else "missing_result"
            contribution = _lane_contribution(
                role_name,
                lane,
                request["review_request_hash"],
                result_payload=result_payload,
                source=source,
                lane_health=lane["health"],
                lane_error=lane["degraded_reason"],
            )
            lane["last_contribution_id"] = contribution["contribution_id"]
            lane["last_review_result_id"] = (result_payload or {}).get("review_result_id", "")
            lane["last_verdict"] = contribution.get("recommended_verdict")
            lane["updated_at"] = _iso_now()
            contributions[role_name] = contribution
            review_cache["contributions"][contribution["contribution_hash"]] = contribution

        if not explicit_roles and evidence_packet["checkpoint_evidence_hash"] in review_cache["verdicts"]:
            summary = dict(review_cache["verdicts"][evidence_packet["checkpoint_evidence_hash"]])
            summary["reused_final_verdict"] = True
            summary["reused_roles"] = reused_roles
            summary["verdict_contributions"] = contributions
            state["last_verdict"] = summary
            state["last_checkpoint_evidence_hash"] = evidence_packet["checkpoint_evidence_hash"]
            state["evaluations"].append(summary)
            state["evaluations"] = state["evaluations"][-20:]
            _save_harness_review_cache(review_cache)
            _save_harness_state(state)
            print("\n  broke harness evaluate")
            print("  " + "─" * 58)
            print(f"\n  mode       : {summary['mode']}")
            print(f"  verdict    : {summary['verdict']}")
            print(f"  categories : {', '.join(summary['categories']) or 'none'}")
            print(f"  risk       : {summary['risk']}")
            print(f"  retries    : {summary['retries']}")
            print(f"  checkpoint : {summary['checkpoint_evidence_hash'][:12]}")
            print(f"  reused final verdict : yes")
            if summary.get("reused_roles"):
                print(f"  reused roles: {', '.join(summary['reused_roles'])}")
            if summary["reasons"]:
                print("\n  reasons:")
                for idx, reason in enumerate(summary["reasons"], start=1):
                    print(f"    {idx}. {reason}")
            print()
            return

        preflight = _preflight_findings()
        validate = _validate_findings()
        summary = _harness_verdict(
            cfg,
            preflight,
            validate,
            role_verdicts=role_verdicts,
            risk=risk,
            retries=int(retries or "0"),
            evidence_summary=evidence_packet.get("evidence_summary", {}),
            lane_states=lane_states,
        )
        summary["checkpoint_evidence_hash"] = evidence_packet["checkpoint_evidence_hash"]
        summary["task_packet_hash"] = evidence_packet["task_packet_hash"]
        summary["evidence_summary"] = evidence_packet.get("evidence_summary", {})
        summary["evidence_contract_version"] = evidence_packet.get("evidence_contract_version", "v1")
        summary["observation_hashes"] = evidence_packet.get("observation_hashes", [])
        summary["inference_hashes"] = evidence_packet.get("inference_hashes", [])
        summary["verdict_contributions"] = contributions
        summary["reused_final_verdict"] = False
        summary["reused_roles"] = reused_roles
        state["last_verdict"] = summary
        state["last_checkpoint_evidence_hash"] = evidence_packet["checkpoint_evidence_hash"]
        state["evaluations"].append(summary)
        state["evaluations"] = state["evaluations"][-20:]
        review_cache["verdicts"][evidence_packet["checkpoint_evidence_hash"]] = summary
        _save_harness_review_cache(review_cache)
        _save_harness_state(state)
        print("\n  broke harness evaluate")
        print("  " + "─" * 58)
        print(f"\n  mode       : {summary['mode']}")
        print(f"  verdict    : {summary['verdict']}")
        print(f"  categories : {', '.join(summary['categories']) or 'none'}")
        print(f"  risk       : {summary['risk']}")
        print(f"  retries    : {summary['retries']}")
        print(f"  checkpoint : {summary['checkpoint_evidence_hash'][:12]}")
        print(f"  reused final verdict : no")
        rendered_roles = ", ".join(f"{k}={v}" for k, v in summary["role_verdicts"].items() if v)
        if rendered_roles:
            print(f"  roles      : {rendered_roles}")
        if reused_roles:
            print(f"  reused roles: {', '.join(reused_roles)}")
        if summary["reasons"]:
            print("\n  reasons:")
            for idx, reason in enumerate(summary["reasons"], start=1):
                print(f"    {idx}. {reason}")
        print()
        return

    print("\n  Usage: broke harness [status|checklist|set <off|throughput|balanced|high_assurance>|evaluate [--worker V] [--verifier V] [--adversary V] [--worker-health H] [--verifier-health H] [--adversary-health H] [--worker-error E] [--verifier-error E] [--adversary-error E] [--risk R] [--retries N] [--task T] [--diff D] [--tests T] [--commands C] [--policy-events P] [--retry-summary S] [--checkpoint-kind K] [--model-family F]]\n")
    sys.exit(1)


if __name__ == "__main__":
    cmd  = sys.argv[1] if len(sys.argv) > 1 else "config"
    arg  = sys.argv[2] if len(sys.argv) > 2 else None
    arg2 = sys.argv[3] if len(sys.argv) > 3 else None
    args = sys.argv[2:]
    dispatch = {
        "init":             cmd_init,
        "config":           cmd_config,
        "list":             cmd_list,
        "models":           cmd_models,
        "swap":             lambda: cmd_swap(arg or "claude"),
        "swap-many":        lambda: cmd_swap_many(arg, *sys.argv[3:]),
        "swap-many-interactive": lambda: cmd_swap_many_interactive(arg),
        "metrics":          lambda: cmd_metrics(raw="--raw" in sys.argv),
        "team-save":        lambda: cmd_team_save(arg, arg2 if arg2 is not None else "1"),
        "team-load":        lambda: cmd_team_load(arg),
        "team-list":        cmd_team_list,
        "team-delete":      lambda: cmd_team_delete(arg),
        "team-fallback":    lambda: cmd_team_fallback(arg, arg2, *sys.argv[4:]),
        # team-access: broke team access <team> [--slots s1,s2] [--rpm N] [--tpm N]
        "team-access":      lambda: cmd_team_access(
                                arg,
                                allowed_slots=[s.strip() for s in arg2.split(",")] if arg2 and not arg2.startswith("--") else (
                                    [s.strip() for s in sys.argv[sys.argv.index("--slots")+1].split(",")]
                                    if "--slots" in sys.argv else None
                                ),
                                rpm=sys.argv[sys.argv.index("--rpm")+1] if "--rpm" in sys.argv else None,
                                tpm=sys.argv[sys.argv.index("--tpm")+1] if "--tpm" in sys.argv else None,
                            ),
        "profile-new":      lambda: cmd_profile_new(
                                arg, arg2 or "",
                                description=" ".join(sys.argv[4:]) if len(sys.argv) > 4 and not sys.argv[4].startswith("--") else
                                            (sys.argv[sys.argv.index("--desc")+1] if "--desc" in sys.argv else ""),
                                allowed_slots=[s.strip() for s in sys.argv[sys.argv.index("--slots")+1].split(",")]
                                              if "--slots" in sys.argv else None,
                                rpm=sys.argv[sys.argv.index("--rpm")+1] if "--rpm" in sys.argv else "0",
                                tpm=sys.argv[sys.argv.index("--tpm")+1] if "--tpm" in sys.argv else "0",
                            ),
        "profile-load":     lambda: cmd_profile_load(arg),
        "profile-list":     cmd_profile_list,
        "profile-delete":   lambda: cmd_profile_delete(arg),
        "client-token-bind": lambda: cmd_client_token_bind(
                                arg,
                                token=sys.argv[sys.argv.index("--token")+1] if "--token" in sys.argv else None,
                                name=sys.argv[sys.argv.index("--name")+1] if "--name" in sys.argv else "",
                            ),
        "client-token-list": cmd_client_token_list,
        "client-token-revoke": lambda: cmd_client_token_revoke(arg),
        "export":           lambda: cmd_export(arg or "broke-config.json"),
        "import":           lambda: cmd_import(arg or "broke-config.json", overwrite="--overwrite" in sys.argv),
        "fallback":         lambda: cmd_fallback(arg, *sys.argv[3:]),
        "fallback-policy":  lambda: cmd_fallback_policy(
                                team_name=(sys.argv[sys.argv.index("--team")+1]
                                           if "--team" in sys.argv and len(sys.argv) > sys.argv.index("--team")+1 and not sys.argv[sys.argv.index("--team")+1].startswith("--")
                                           else None),
                                show_teams="--team" in sys.argv,
                            ),
        "key-policy":       lambda: cmd_key_policy(
                                provider=arg if arg and not arg.startswith("--") else None,
                                mode=sys.argv[sys.argv.index("--mode")+1] if "--mode" in sys.argv else None,
                                cooldown=sys.argv[sys.argv.index("--cooldown")+1] if "--cooldown" in sys.argv else None,
                                retries=sys.argv[sys.argv.index("--retries")+1] if "--retries" in sys.argv else None,
                                order=sys.argv[sys.argv.index("--order")+1] if "--order" in sys.argv else None,
                            ),
        "key-state":        lambda: cmd_key_state(
                                action=arg,
                                key_name=arg2,
                                status=sys.argv[4] if len(sys.argv) > 4 else None,
                            ),
        "model-policy":     lambda: cmd_model_policy(
                                slot=arg if arg and not arg.startswith("--") else None,
                                mode=sys.argv[sys.argv.index("--mode")+1] if "--mode" in sys.argv else None,
                                cooldown=sys.argv[sys.argv.index("--cooldown")+1] if "--cooldown" in sys.argv else None,
                                retries=sys.argv[sys.argv.index("--retries")+1] if "--retries" in sys.argv else None,
                                order=sys.argv[sys.argv.index("--order")+1] if "--order" in sys.argv else None,
                            ),
        "model-state":      lambda: cmd_model_state(
                                action=arg,
                                model_label=arg2,
                                status=sys.argv[4] if len(sys.argv) > 4 else None,
                            ),
        "harness":          lambda: cmd_harness(
                                action=arg,
                                value=arg2,
                                worker=sys.argv[sys.argv.index("--worker")+1] if "--worker" in sys.argv else None,
                                verifier=sys.argv[sys.argv.index("--verifier")+1] if "--verifier" in sys.argv else None,
                                adversary=sys.argv[sys.argv.index("--adversary")+1] if "--adversary" in sys.argv else None,
                                risk=sys.argv[sys.argv.index("--risk")+1] if "--risk" in sys.argv else "normal",
                                retries=sys.argv[sys.argv.index("--retries")+1] if "--retries" in sys.argv else "0",
                            ),
        "preflight":        lambda: sys.exit(0 if cmd_preflight(quiet="--quiet" in sys.argv) else 1),
        "doctor":           lambda: cmd_doctor(),
        "explain":          lambda: cmd_explain(arg),
        "route":            lambda: cmd_route(arg),
        "validate":         cmd_validate,
        "snapshot-save":    cmd_snapshot_save,
        "snapshot-list":    cmd_snapshot_list,
        "snapshot-restore": lambda: cmd_snapshot_restore(arg),
        "probe":            lambda: cmd_probe(arg),
    }
    fn = dispatch.get(cmd)
    if fn is None:
        print(f"\n  [broke] Unknown internal command: '{cmd}'\n", file=sys.stderr)
        sys.exit(1)
    fn()
SENSITIVE_FILES = {
    MAPPING,
    BACKENDS,
    CONFIG,
    DEPLOYMENTS,
    TEAMS,
    PROFILES,
    ROTATION_POLICY,
    KEY_STATE,
    ROTATION_LOG,
    MODEL_POLICY,
    MODEL_STATE,
    HARNESS_CONFIG,
    HARNESS_STATE,
    HARNESS_PROMPT_CONTRACTS,
    HARNESS_PREFIX_CACHE,
    HARNESS_EVIDENCE_CACHE,
    HARNESS_REVIEW_CACHE,
    HARNESS_RUNS,
    HARNESS_ACTIVE_RUN,
}
