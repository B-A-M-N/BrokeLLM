#!/usr/bin/env python3
"""BrokeLLM mapping helpers — used by broke CLI."""

import json, sys, pathlib, urllib.request, urllib.error, re

DIR = pathlib.Path(__file__).parent.parent
MAPPING  = DIR / ".mapping.json"
BACKENDS = DIR / ".backends.json"
CONFIG   = DIR / "config.json"
TEAMS    = DIR / ".teams.json"
PROFILES  = DIR / ".profiles.json"
SNAPSHOTS = DIR / ".snapshots"
FREEZE    = DIR / ".freeze"

VALID_SLOTS = ["sonnet", "opus", "haiku", "default", "subagent"]

DEFAULT_MAPPING = {
    "sonnet":  {"provider":"openrouter","model":"qwen/qwen3.6-plus:free","label":"OR/Qwen-3.6+","key":"OPENROUTER_API_KEY"},
    "opus":    {"provider":"openrouter","model":"nvidia/nemotron-3-super-120b-a12b:free","label":"OR/Nemotron-3-Super","key":"OPENROUTER_API_KEY"},
    "haiku":   {"provider":"openrouter","model":"stepfun/step-3.5-flash:free","label":"OR/Step-3.5","key":"OPENROUTER_API_KEY"},
    "default": {"provider":"openrouter","model":"qwen/qwen3.6-plus:free","label":"OR/Qwen-3.6+","key":"OPENROUTER_API_KEY"},
    "subagent":{"provider":"openrouter","model":"z-ai/glm-4.5-air:free","label":"OR/GLM-4.5","key":"OPENROUTER_API_KEY"}
}

# pinned=False → floating alias; may drift when upstream updates their default.
# These are flagged so users know to watch for silent breakage.
BACKENDS_DATA = [
  {"provider":"openrouter","model":"qwen/qwen3.6-plus:free",                    "label":"OR/Qwen-3.6+",        "key":"OPENROUTER_API_KEY",  "pinned":True},
  {"provider":"openrouter","model":"nvidia/nemotron-3-super-120b-a12b:free",    "label":"OR/Nemotron-3-Super", "key":"OPENROUTER_API_KEY",  "pinned":True},
  {"provider":"openrouter","model":"nvidia/nemotron-3-nano-30b-a3b:free",       "label":"OR/Nemotron-3-Nano",  "key":"OPENROUTER_API_KEY",  "pinned":True},
  {"provider":"openrouter","model":"stepfun/step-3.5-flash:free",               "label":"OR/Step-3.5",         "key":"OPENROUTER_API_KEY",  "pinned":True},
  {"provider":"openrouter","model":"z-ai/glm-4.5-air:free",                     "label":"OR/GLM-4.5",          "key":"OPENROUTER_API_KEY",  "pinned":True},
  {"provider":"openrouter","model":"meta-llama/llama-4-scout-17b-16e-instruct", "label":"OR/Llama-4-Scout",    "key":"OPENROUTER_API_KEY",  "pinned":True},
  {"provider":"openrouter","model":"moonshotai/kimi-k2-instruct",               "label":"OR/Kimi-K2",          "key":"OPENROUTER_API_KEY",  "pinned":True},
  {"provider":"openrouter","model":"groq/compound",                             "label":"OR/Groq-Compound",    "key":"OPENROUTER_API_KEY",  "pinned":False},
  {"provider":"openrouter","model":"openai/gpt-4o-mini",                        "label":"OR/GPT-4o-mini",      "key":"OPENROUTER_API_KEY",  "pinned":False},
  {"provider":"openrouter","model":"mistral-ai/codestral-2501",                 "label":"OR/Codestral-2501",   "key":"OPENROUTER_API_KEY",  "pinned":True},
  {"provider":"openrouter","model":"mistral-ai/mistral-medium-2505",            "label":"OR/Mistral-Medium",   "key":"OPENROUTER_API_KEY",  "pinned":True},
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


def cmd_init():
    if not MAPPING.exists() or MAPPING.stat().st_size == 0:
        with open(MAPPING, "w") as f:
            json.dump(DEFAULT_MAPPING, f, indent=2)
        with open(BACKENDS, "w") as f:
            json.dump(BACKENDS_DATA, f, indent=2)

def load():
    with open(MAPPING) as f:
        return json.load(f)

def _slots(m):
    """Return only slot entries, excluding internal keys like _fallbacks."""
    return {k: v for k, v in m.items() if not k.startswith("_")}

def cmd_config():
    m = load()
    slots = _slots(m)
    fallbacks_map = m.get("_fallbacks", {})
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
    env_lines = []

    for claude_name, entry in slots.items():
        # Enforce slot access policy
        if allowed_slots is not None and claude_name not in allowed_slots:
            continue
        label = entry["label"]
        params = {
            "model": f"{entry['provider']}/{entry['model']}",
            "api_key": f"os.environ/{entry['key']}"
        }
        if "api_base" in entry:
            params["api_base"] = entry["api_base"]
        model_entry = {
            "model_name": label,
            "litellm_params": params,
            "model_info": {
                "base_model": label,
                "description": f"{entry['provider']} · {entry['model']}"
            }
        }
        if rpm_limit:
            model_entry["rpm"] = rpm_limit
        if tpm_limit:
            model_entry["tpm"] = tpm_limit
        cfg["model_list"].append(model_entry)

        if claude_name == "sonnet":
            env_lines.append(f'export ANTHROPIC_DEFAULT_SONNET_MODEL="{label}"')
            env_lines.append(f'export ANTHROPIC_DEFAULT_SONNET_MODEL_NAME="Sonnet"')
            env_lines.append(f'export ANTHROPIC_DEFAULT_SONNET_MODEL_DESCRIPTION="{label} · free"')
        elif claude_name == "opus-1m":
            env_lines.append(f'export ANTHROPIC_DEFAULT_OPUS_MODEL="{label}"')
            env_lines.append(f'export ANTHROPIC_DEFAULT_OPUS_MODEL_NAME="Opus"')
            env_lines.append(f'export ANTHROPIC_DEFAULT_OPUS_MODEL_DESCRIPTION="{label} · free"')
        elif claude_name == "haiku":
            env_lines.append(f'export ANTHROPIC_DEFAULT_HAIKU_MODEL="{label}"')
            env_lines.append(f'export ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME="Haiku"')
            env_lines.append(f'export ANTHROPIC_DEFAULT_HAIKU_MODEL_DESCRIPTION="{label} · free"')
        elif claude_name == "opus":
            env_lines.append(f'export ANTHROPIC_DEFAULT_OPUS_MODEL="{label}"')
            env_lines.append(f'export ANTHROPIC_DEFAULT_OPUS_MODEL_NAME="Opus"')
            env_lines.append(f'export ANTHROPIC_DEFAULT_OPUS_MODEL_DESCRIPTION="{label} · free"')
            env_lines.append(f'export ANTHROPIC_CUSTOM_MODEL_OPTION="{label}"')
            env_lines.append(f'export ANTHROPIC_CUSTOM_MODEL_OPTION_NAME="Opus"')
            env_lines.append(f'export ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION="{label} · free"')
        elif claude_name == "subagent":
            env_lines.append(f'export CLAUDE_CODE_SUBAGENT_MODEL="{label}"')

    # Fallbacks: use per-team chains if defined, else skip (let retries handle it)
    if fallbacks_map:
        fb_list = []
        for slot, fb_slots in fallbacks_map.items():
            if slot not in slots:
                continue
            label = slots[slot]["label"]
            fb_labels = [slots[fb]["label"] for fb in fb_slots if fb in slots]
            if fb_labels:
                fb_list.append({label: fb_labels})
        if fb_list:
            cfg["router_settings"]["fallbacks"] = fb_list

    with open(CONFIG, "w") as f:
        json.dump(cfg, f, indent=2)

    with open(DIR / ".env.claude", "w") as f:
        f.write("\n".join(env_lines) + "\n")

def cmd_list():
    m = load()
    slots = _slots(m)
    fallbacks_map = m.get("_fallbacks", {})
    print("\n  BrokeLLM Active Routing")
    print("  " + "─" * 60)
    print(f"  {'Slot':<12} {'Backend':<35} {'Fallbacks'}")
    print("  " + "─" * 60)
    for claude in VALID_SLOTS:
        if claude not in slots:
            continue
        e = slots[claude]
        fbs = " → ".join(fallbacks_map.get(claude, [])) or "—"
        print(f"  {claude:<12} {e['label']:<35} {fbs}")
    print("  " + "─" * 60)
    print("  swap: broke swap\n")

def cmd_models():
    print("\n  Available Gateway Backends")
    print("  " + "─" * 70)
    print(f"  {'#':>3}  {'Provider/Model':<48} {'Label':<22} {'Pin'}")
    print("  " + "─" * 70)
    for i, b in enumerate(BACKENDS_DATA):
        pin = "✓" if b.get("pinned", True) else "⚠ floating"
        print(f"  {i:>3})  {b['provider']}/{b['model']:<46} ({b['label']:<20}) {pin}")
    print("  " + "─" * 70)
    print("  ⚠ floating = alias may drift when upstream changes their default\n")

def cmd_swap():
    m = load()
    slots = _slots(m)
    backends = BACKENDS_DATA

    print("\n  Remap a Claude model to a backend:\n")
    models = VALID_SLOTS
    for i, claude in enumerate(models):
        if claude in slots:
            print(f"  {i})  {claude:<12} → {slots[claude]['label']}")
    print("  x)  cancel\n")
    slot = input("  Pick Claude model > ").strip()
    if slot == "x": return
    target = models[int(slot)]

    print("\n  Available backends:\n")
    for i, b in enumerate(backends):
        pin = "" if b.get("pinned", True) else " ⚠"
        print(f"  {i})  {b['provider']}/{b['model']}  ({b['label']}){pin}")
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

def cmd_metrics(port=4000, raw=False):
    try:
        resp = urllib.request.urlopen(f"http://localhost:{port}/metrics", timeout=10)
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
    access    = m.get("_access", {})
    teams = _load_teams()
    mode_int = 1 if str(mode).lower() in ("1", "cli") else 0
    teams[name] = {"mode": mode_int, "slots": slots, "fallbacks": fallbacks, "access": access}
    _save_teams(teams)
    mode_label = "CLI agent" if mode_int == 1 else "app router"
    print(f"\n  Team '{name}' saved  [mode {mode_int} · {mode_label}]:")
    allowed = access.get("allowed_slots")
    for slot in VALID_SLOTS:
        if slot not in slots:
            continue
        if allowed is not None and slot not in allowed:
            continue
        fbs = " → ".join(fallbacks.get(slot, [])) or "—"
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
    else:
        slots, mode, fallbacks = team, 1, {}

    access = team.get("access", {})
    mapping = dict(slots)
    if fallbacks:
        mapping["_fallbacks"] = fallbacks
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
    for slot in VALID_SLOTS:
        if slot in slots:
            fbs = " → ".join(fallbacks.get(slot, [])) or "—"
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
            access      = team.get("access", {})
        else:
            slots, mode, fallbacks, access = team, 1, {}, {}
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
        for slot in VALID_SLOTS:
            if slot not in slots:
                continue
            if allowed_slots is not None and slot not in allowed_slots:
                print(f"    ✗ {slot:<12} {slots[slot]['label']:<25} (blocked by access policy)")
                continue
            marker = "→" if active.get(slot, {}).get("label") == slots[slot]["label"] else " "
            fbs = " → ".join(fallbacks.get(slot, [])) or "—"
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
        team = {"mode": 1, "slots": team, "fallbacks": {}}
    if "fallbacks" not in team:
        team["fallbacks"] = {}

    for s in [slot] + list(fb_slots):
        if s not in VALID_SLOTS:
            print(f"\n  [broke] Invalid slot '{s}'. Valid: {', '.join(VALID_SLOTS)}\n")
            sys.exit(1)

    team["fallbacks"][slot] = list(fb_slots)
    teams[team_name] = team
    _save_teams(teams)
    chain = " → ".join(fb_slots) if fb_slots else "(cleared)"
    print(f"\n  [{team_name}] {slot} fallback chain: {chain}\n")


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
    """Set fallback chain on the live mapping without requiring a team."""
    if slot not in VALID_SLOTS:
        print(f"\n  [broke] Invalid slot '{slot}'. Valid: {', '.join(VALID_SLOTS)}\n")
        sys.exit(1)
    for fb in fb_slots:
        if fb not in VALID_SLOTS:
            print(f"\n  [broke] Invalid slot '{fb}'. Valid: {', '.join(VALID_SLOTS)}\n")
            sys.exit(1)
    m = load()
    fbs = m.get("_fallbacks", {})
    if fb_slots:
        fbs[slot] = list(fb_slots)
    else:
        fbs.pop(slot, None)
    m["_fallbacks"] = fbs
    with open(MAPPING, "w") as f:
        json.dump(m, f, indent=2)
    cmd_config()
    chain = " → ".join(fb_slots) if fb_slots else "(cleared)"
    print(f"\n  [{slot}] fallback chain: {chain}\n")


def cmd_doctor(port=4000):
    import os
    env_path = DIR / ".env"

    oks = warns = fails = 0
    def _ok(msg):   nonlocal oks;   oks   += 1; print(f"  ✓  {msg}")
    def _warn(msg): nonlocal warns; warns += 1; print(f"  ⚠  {msg}")
    def _fail(msg): nonlocal fails; fails += 1; print(f"  ✗  {msg}")

    print("\n  broke doctor")
    print("  " + "─" * 58)

    # ── env vars ───────────────────────────────────────────────
    print("\n  [env vars]")
    env_vals = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
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
    fallbacks_map = m.get("_fallbacks", {})
    access = m.get("_access", {})
    allowed = access.get("allowed_slots")
    for slot in VALID_SLOTS:
        if slot not in slots:
            continue
        if allowed is not None and slot not in allowed:
            _warn(f"{slot:<12} blocked by access policy")
            continue
        entry = slots[slot]
        fbs = " → ".join(fallbacks_map.get(slot, [])) or "none"
        pinned = _entry_pin_state(entry)
        if pinned is False:
            _warn(f"{slot:<12} {entry['label']:<26} fallbacks: {fbs}  floating alias")
        elif pinned is None:
            _warn(f"{slot:<12} {entry['label']:<26} fallbacks: {fbs}  pin state unknown")
        else:
            _ok(f"{slot:<12} {entry['label']:<26} fallbacks: {fbs}")

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
    imported_t = imported_p = skipped_t = skipped_p = 0

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

    _save_teams(teams)
    _save_profiles(profiles)
    print(f"\n  Imported: {imported_t} team(s), {imported_p} profile(s)")
    if skipped_t or skipped_p:
        print(f"  Skipped (already exist): {skipped_t} team(s), {skipped_p} profile(s)")
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
    fallbacks_map = m.get("_fallbacks", {})
    fb_chain = fallbacks_map.get(slot, [])

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
        print(f"  fallback chain:")
        for i, fb in enumerate(fb_chain):
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
    fallbacks_map = m.get("_fallbacks", {})
    fb_chain = fallbacks_map.get(slot, [])

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
        if fb in slots:
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
    import os
    m = load()
    slots = _slots(m)
    fallbacks_map = m.get("_fallbacks", {})

    oks = warns = fails = 0
    def _ok(msg):   nonlocal oks;   oks   += 1; print(f"  ✓  {msg}")
    def _warn(msg): nonlocal warns; warns += 1; print(f"  ⚠  {msg}")
    def _fail(msg): nonlocal fails; fails += 1; print(f"  ✗  {msg}")

    print("\n  broke validate  (pre-flight)")
    print("  " + "─" * 58)

    # 1. Required fields
    print("\n  [slot fields]")
    REQUIRED = {"provider", "model", "label", "key"}
    for slot, entry in slots.items():
        missing = REQUIRED - set(entry.keys())
        if missing:
            _fail(f"{slot}: missing fields: {', '.join(sorted(missing))}")
        else:
            _ok(f"{slot}: all required fields present")

    # 2. Known providers
    print("\n  [provider format]")
    VALID_PROVIDERS = {"openrouter", "cerebras", "groq", "openai", "gemini", "huggingface"}
    for slot, entry in slots.items():
        prov = entry.get("provider", "")
        if prov not in VALID_PROVIDERS:
            _warn(f"{slot}: unknown provider '{prov}'")
        else:
            _ok(f"{slot}: provider '{prov}' recognised")

    # 3. Env vars
    print("\n  [api keys]")
    env_path = DIR / ".env"
    env_vals = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env_vals[k.strip()] = v.strip()
    seen = set()
    for slot, entry in slots.items():
        key = entry.get("key", "")
        if not key:
            _fail(f"{slot}: no api key field")
            continue
        if key in seen:
            continue
        seen.add(key)
        val = env_vals.get(key) or os.environ.get(key, "")
        if not val:
            _fail(f"{key} — not set")
        elif "XXXXX" in val:
            _warn(f"{key} — placeholder not filled in")
        else:
            _ok(f"{key} — set")

    # 4. Fallback chain validity + circular detection
    print("\n  [fallback chains]")
    if not fallbacks_map:
        _ok("no fallback chains defined (ok)")
    else:
        def _has_cycle(start, current, visited):
            for fb in fallbacks_map.get(current, []):
                if fb == start:
                    return True
                if fb not in visited:
                    visited.add(fb)
                    if _has_cycle(start, fb, visited):
                        return True
            return False

        for slot, fb_chain in fallbacks_map.items():
            if slot not in slots:
                _fail(f"source slot '{slot}' not in active mapping")
                continue
            for fb in fb_chain:
                if fb == slot:
                    _fail(f"{slot} → '{fb}': self-referential fallback")
                elif fb not in slots:
                    _fail(f"{slot} → '{fb}': target slot not configured")
                else:
                    _ok(f"{slot} → {fb}: valid")
            if _has_cycle(slot, slot, {slot}):
                _warn(f"{slot}: circular fallback chain detected")

    # 5. Alias stability
    print("\n  [alias stability]")
    for slot, entry in slots.items():
        pin_state = _entry_pin_state(entry)
        if pin_state is False:
            _warn(f"{slot}: floating alias '{entry['label']}' — may drift on upstream changes")
        elif pin_state is None:
            _warn(f"{slot}: pin state for '{entry['label']}' is unknown")
        else:
            _ok(f"{slot}: pinned alias")

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
        headers={"Content-Type": "application/json", "Authorization": "Bearer dummy"},
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
        "swap":             cmd_swap,
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
        "export":           lambda: cmd_export(arg or "broke-config.json"),
        "import":           lambda: cmd_import(arg or "broke-config.json", overwrite="--overwrite" in sys.argv),
        "fallback":         lambda: cmd_fallback(arg, *sys.argv[3:]),
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
