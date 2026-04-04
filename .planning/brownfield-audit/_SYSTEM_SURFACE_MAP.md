# BrokeLLM System Surface Map

**Generated:** 2026-04-04 during Phase 1 — Repo Discovery & Ground Truth Bootstrap
**Status:** DRAFT — to be completed by downstream phases

## Codebase Statistics

- **Core files:** 3 (bin/broke = 1421 lines Bash, bin/_mapping.py = 3104 lines Python, bin/_proxy.py = 800 lines Python)
- **Support files:** 4 (bin/_harness_common.py, bin/_harness_shim.py, bin/_fs_common.py, bin/_socket_bridge.py)
- **Total lines:** ~5325 core + ~300 support + extensive state/data files
- **Test files:** 1 (tests/test_mapping.py = ~1000 lines)

---

## A. CLI Command Surfaces

### Gateway Lifecycle
| Command | Dispatch | Python Entry | Notes |
|---------|----------|--------------|-------|
| `broke start` | bin/broke:start_gateway() | bin/_mapping.py:cmd_config(), bin/_proxy.py | Spawns LiteLLM + _proxy.py as nohup bg processes |
| `broke stop` | bin/broke:stop_gateway() | N/A (kill by port) | Uses lsof + pkill |
| `broke restart` | bin/broke:restart_gateway() | N/A | pkill then start_gateway |
| `broke status` | bin/broke:status (inline) | N/A (curl checks) | Checks :4000/:4001, curl liveliness/readiness |

### Routing
| Command | Dispatch | Python Entry | Notes |
|---------|----------|--------------|-------|
| `broke list` | bin/broke:list → _mapping.py | bin/_mapping.py:cmd_list() | Reads .mapping.json, displays slots |
| `broke models` | bin/broke:models → _mapping.py | bin/_mapping.py:cmd_models() | Displays BACKENDS_DATA constant |
| `broke swap` | bin/broke:swap (interactive) | bin/_mapping.py:cmd_swap() | **FREEZE GATED** — checks .freeze file |
| `broke fallback <slot>` | bin/broke:fallback → _mapping.py | bin/_mapping.py:cmd_fallback() | Rebuilds config, restarts gateway |
| `broke fallback policy` | bin/broke:fallback policy → _mapping.py | bin/_mapping.py:cmd_fallback_policy() | Read-only display |
| `broke swap <team>` | bin/broke:swap <arg> → _mapping.py | bin/_mapping.py:cmd_team_load() | Loads team, restarts gateway |

### Observability
| Command | Dispatch | Python Entry | Notes |
|---------|----------|--------------|-------|
| `broke doctor` | bin/broke:doctor → _mapping.py | bin/_mapping.py:cmd_doctor() | Full health check across 7 domains |
| `broke validate` | bin/broke:validate → _mapping.py | bin/_mapping.py:cmd_validate() | Config validation — 5 sections |
| `broke explain <slot>` | bin/broke:explain → _mapping.py | bin/_mapping.py:cmd_explain() | Full resolution path + health |
| `broke route <slot>` | bin/broke:route → _mapping.py | bin/_mapping.py:cmd_route() | Dry-run route resolution |
| `broke metrics` | bin/broke:metrics → _mapping.py | bin/_mapping.py:cmd_metrics() | Parses Litellm Prometheus metrics |
| `broke probe <slot>` | bin/broke:probe → _mapping.py | bin/_mapping.py:cmd_probe() | Live test request to proxy |

### Key/Model Policy
| Command | Dispatch | Python Entry | Notes |
|---------|----------|--------------|-------|
| `broke key-policy` | bin/broke:key-policy → _mapping.py | bin/_mapping.py:cmd_key_policy() | Show/set key rotation per provider |
| `broke key-state` | bin/broke:key-state → _mapping.py | bin/_mapping.py:cmd_key_state() | Show/set key health status |
| `broke model-policy` | bin/broke:model-policy → _mapping.py | bin/_mapping.py:cmd_model_policy() | Show/set per-lane model policy |
| `broke model-state` | bin/broke:model-state → _mapping.py | bin/_mapping.py:cmd_model_state() | Show/set per-model health status |

### Team/Profile
| Command | Dispatch | Python Entry | Notes |
|---------|----------|--------------|-------|
| `broke team save` | bin/broke:team save → _mapping.py | bin/_mapping.py:cmd_team_save() | Saves slots+fallbacks+access |
| `broke team load` | bin/broke:team load → _mapping.py | bin/_mapping.py:cmd_team_load() | **FREEZE GATED** — checks .freeze |
| `broke team list` | bin/broke:team list → _mapping.py | bin/_mapping.py:cmd_team_list() | Read-only |
| `broke team delete` | bin/broke:team delete → _mapping.py | bin/_mapping.py:cmd_team_delete() | Read-only |
| `broke team fallback` | bin/broke:team fallback → _mapping.py | bin/_mapping.py:cmd_team_fallback() | Backend-scoped fallback chains |
| `broke team access` | bin/broke:team access → _mapping.py | bin/_mapping.py:cmd_team_access() | Slot/rpm/tpm access restrictions |
| `broke profile new` | bin/broke:profile new → _mapping.py | bin/_mapping.py:cmd_profile_new() | Client profiles (refs team) |
| `broke profile load` | bin/broke:profile load → _mapping.py | bin/_mapping.py:cmd_profile_load() | **FREEZE GATED** — checks .freeze |
| `broke profile list` | bin/broke:profile list → _mapping.py | bin/_mapping.py:cmd_profile_list() | Read-only |
| `broke profile delete` | bin/broke:profile delete → _mapping.py | bin/_mapping.py:cmd_profile_delete() | Read-only |

### Sandbox
| Command | Dispatch | Python Entry | Notes |
|---------|----------|--------------|-------|
| `broke sandbox` | bin/broke:sandbox (inline) | N/A | Reads .sandbox-profile |
| `broke sandbox set <p>` | bin/broke:sandbox set → set_sandbox_profile() | N/A (bash) | Validates normal/hardened/strict |

### Harness
| Command | Dispatch | Python Entry | Notes |
|---------|----------|--------------|-------|
| `broke harness` | bin/broke:harness (inline) | bin/_mapping.py:cmd_harness() status | Shows mode/verdict/cache |
| `broke harness run` | bin/broke:harness run (bash) | bin/_mapping.py:_register_harness_run() | **ELEVATION GATED** — provider_direct requires --elevated |
| `broke harness set` | bin/broke:harness set → _mapping.py | bin/_mapping.py:cmd_harness() set | Sets harness mode |
| `broke harness evaluate` | bin/broke:harness evaluate → _mapping.py | bin/_mapping.py:cmd_harness() evaluate | Verdict evaluation |

### Snapshot/Freeze
| Command | Dispatch | Python Entry | Notes |
|---------|----------|--------------|-------|
| `broke snapshot save` | bin/broke:snapshot save → _mapping.py | bin/_mapping.py:cmd_snapshot_save() | .snapshots/ timestamped JSON |
| `broke snapshot list` | bin/broke:snapshot list → _mapping.py | bin/_mapping.py:cmd_snapshot_list() | Read-only, shows active marker |
| `broke snapshot restore` | bin/broke:snapshot restore → _mapping.py | bin/_mapping.py:cmd_snapshot_restore() | **FREEZE GATED** — checks .freeze |
| `broke freeze` | bin/broke:freeze (inline) | N/A (bash touch/rm) | Creates/removes .freeze sentinel |
| `broke freeze on` | bin/broke:freeze on (inline) | N/A (bash touch) | |
| `broke freeze off` | bin/broke:freeze off (inline) | N/A (bash rm) | |

### Provider/Other
| Command | Dispatch | Python Entry | Notes |
|---------|----------|--------------|-------|
| `broke provider` | bin/broke:provider → cmd_provider() | N/A (bash) | Shows current provider |
| `broke provider list` | bin/broke:provider list → cmd_provider() | N/A (bash) | Shows path availability |
| `broke provider swap` | bin/broke:provider swap → cmd_provider() | N/A (bash) | Sets .provider file |
| `broke mode` | bin/broke:mode (inline) | set_claude_env_export() | Sets BROKE_MODE in .env.claude |
| `broke init` | bin/broke:init → _mapping.py | bin/_mapping.py:cmd_init() | Creates initial state files |
| `broke export` | bin/broke:export → _mapping.py | bin/_mapping.py:cmd_export() | Teams+profiles export |
| `broke import` | bin/broke:import → _mapping.py | bin/_mapping.py:cmd_import() | Teams+profiles import |

---

## B. Runtime Control Surfaces

### Mapping State
- **Source:** `.mapping.json` — slot-to-backend assignments
- **Writers:** cmd_swap(), cmd_team_load(), cmd_snapshot_restore()
- **Consumers:** cmd_config(), cmd_list(), cmd_explain(), cmd_route(), cmd_validate(), cmd_doctor()
- **Persistence:** JSON, chmod 0o600, fcntl file locking
- **Trust boundary:** Single source of truth for routing

### Deployments State
- **Source:** `.deployments.json` — generated map of internal model names to keys/providers
- **Writers:** cmd_config() only
- **Consumers:** _proxy.py (key rotation, model resolution)
- **Persistence:** JSON, chmod 0o600, fcntl file locking

### Health State
- **Source:** LiteLLM `/health` endpoint (runtime, not persisted)
- **Consumers:** _fetch_health_index(), _entry_health_status(), cmd_doctor()
- **Note:** NOT persisted between runs — derived from LiteLLM runtime

### Key State
- **Source:** `.key_state.json` — per-key health (healthy/cooldown/blocked/auth_failed)
- **Writers:** cmd_key_state(), _proxy.py (runtime key health tracking)
- **Consumers:** cmd_doctor(), cmd_key_state(), _proxy.py (key selection)

### Model State
- **Source:** `.model_state.json` — per-model health
- **Writers:** cmd_model_state(), _proxy.py (runtime model health tracking)
- **Consumers:** cmd_doctor(), cmd_model_state(), _proxy.py

### Freeze State
- **Source:** `.freeze` — sentinel file (existence matters, contents empty)
- **Writers:** cmd_freeze (bash touch/rm)
- **Gates:** swap, team load, profile load, snapshot restore
- **Note:** **NOT checked before all mutation surfaces** — only swap/team-load/profile-load/snapshot-restore. Freeze does NOT block: profile delete, team save, team delete, sandbox set, key-policy, key-state, model-policy, model-state, harness commands

### Snapshot State
- **Source:** `.snapshots/` directory — timestamped JSON files of .mapping.json
- **Writers:** cmd_snapshot_save()
- **Restorers:** cmd_snapshot_restore() (calls cmd_config)
- **Note:** Only saves mapping (slots), NOT teams/profiles/key-state/model-state/freeze state

### Harness State
- **Sources:** `.harness_active_run.json`, `.harness_runs.json`, `.harness_evidence_cache.json`, `.harness_prefix_cache.json`, `.harness_prompt_contracts.json`, `.harness_review_cache.json`, `.harness_state.json`
- **Writers:** _register_harness_run(), _complete_harness_run(), _store_harness_artifact()
- **Consumers:** cmd_harness(), _harness_verdict(), _resolve_harness_prefix()
- **Ledger:** `.runtime/harness/<run_id>/events.jsonl` — append-only SHA-hash-linked event log

### Sandbox Profile State
- **Source:** `.sandbox-profile` — text file (normal/hardened/strict)
- **Writers:** `set_sandbox_profile()` (bash)
- **Consumers:** `get_sandbox_profile()`, `run_client_command()`, `sandbox_network_policy()`

---

## C. Integration Surfaces

### LiteLLM
- **Config generated by:** bin/_mapping.py:cmd_config()
- **Launch:** bin/broke:start_gateway() via `litellm --config config.json --host 127.0.0.1 --port 4001`
- **Auth:** LITELLM_MASTER_KEY (broke-internal-*)

### BrokeLLM Proxy
- **Source:** bin/_proxy.py (800 lines Python)
- **Launch:** bin/broke:start_gateway() via `python3 _proxy.py`
- **Auth:** BROKE_CLIENT_TOKEN for client reqs, BROKE_INTERNAL_MASTER_KEY for proxy-to-LiteLLM
- **Port:** `:4000` (HTTP), Unix socket at `.runtime/proxy.sock` (for strict sandbox bridge)

### Providers (6 in BACKENDS_DATA)
- **openrouter:** Free-tier models, multi-key support confirmed in code
- **groq:** Fast inference, multi-key support
- **cerebras:** High-throughput, multi-key support
- **openai (GitHub Models):** Uses GITHUB_TOKEN, api_base → models.inference.ai.azure.com
- **gemini:** HTTP endpoint, multi-key support
- **huggingface:** Free inference API, multi-key support

### Clients (3 providers)
- **claude:** Verified — uses BROKE_CLIENT_TOKEN + ANTHROPIC_AUTH_TOKEN + ANTHROPIC_BASE_URL
- **codex:** Verified — custom broke provider via Responses API wire_api
- **gemini:** Endpoint works, CLI path not reliable (documented in README)

### Sandbox/Isolation
- **normal:** env -i with selective pass-through keys, child-process-only secret injection
- **hardened:** Same + umask 077
- **strict:** bwrap with --unshare-all, --clearenv, --die-with-parent, Unix socket bridge for Claude/Codex, denies Gemini entirely

---

## D. Trust Surfaces (Preliminary — To Be Adjudicated)

| Surface | Source of Truth | Status |
|---------|-----------------|--------|
| Routing truth | `.mapping.json` + _entry_identity() helpers | Mapped — awaiting adjudication |
| Health truth | LiteLLM /health endpoint | Mapped — transient, not persisted |
| Key policy truth | `.rotation.json` | Mapped |
| Key state truth | `.key_state.json` | Mapped |
| Model policy truth | `.model_policy.json` | Mapped |
| Model state truth | `.model_state.json` | Mapped |
| Fallback resolution truth | `.mapping.json` (_lane_fallback_targets, _backend_fallbacks, _fallbacks) | Mapped — MULTI-LEVEL |
| Harness verdict truth | `.harness_state.json` + harness events | Mapped |
| Credential isolation truth | BROKE_* tokens, env injection paths | Mapped |
| Sandbox/runtime boundary truth | `.sandbox-profile` + bwrap setup | Mapped |
| Execution alignment truth | .mapping.json → .deployments.json → config.json → LiteLLM | Mapped — MULTI-STEP chain |
| Launch preflight integrity truth | _preflight_findings() | Mapped |
| Snapshot/restore truth | `.snapshots/` | Mapped |
| Freeze enforcement truth | `.freeze` sentinel | Mapped |
| Supply-chain truth | requirements.txt, requirements.lock, .pth.allowlist | Mapped |

---

## Runtime Probe Results (Phase 1 Execution)

### Command Response Summary
- `broke status`: Gateway running on :4000, proxy live, provider=codex, sandbox=normal
- `broke doctor`: Pre-flight found 2 failures (package drift, harness shim integrity 0o775), 2 warnings, 40+ ok
- `broke list`: 5 active slots, fallback chain on sonnet only
- `broke explain sonnet`: openrouter/stepfun/step-3.5-flash:free, health=gateway-not-reachable (doctor says otherwise — **SUSPECTED DIVERGENCE**)
- `broke route sonnet`: Same backend as explain — consistent at this point
- `broke validate`: 19/21 passed, 2 warnings (floating alias, inactive backend fallback)
- `broke key-policy`: 6 providers, openrouter round_robin with multi-key ORDER
- `broke key-state`: 3 keys tracked, all healthy
- `broke model-policy`: sonnet lane = OR/Step-3.5 → Cerebras/GPT-OSS-120B
- `broke metrics`: Shows 100% failure rate for active models (billing/payment issues, not routing bugs)
- `broke harness`: mode=off, last_verdict=ACCEPT, cache populated from prior runs

### Safe Kill Test Feasibility (Phase 1)

| Kill Test | Status | Finding |
|-----------|--------|---------|
| KT-05 Fallback failure path | FEASIBLE (partial) | Fallback chain defined for sonnet only; cannot verify runtime failover without live traffic + inducing failure |
| KT-06 Floating alias drift | FEASIBLE (partial) | `default` slot confirmed floating (Groq/Compound); validate warns about floating |
| KT-07 Execution mismatch | FEASIBLE (partial) | explain and route agree on sonnet → OR/Step-3.5; provider is codex. Full alignment requires intercepting actual request to LiteLLM (not possible without running traffic) |
| KT-08 Provider-direct without elevation | CONFIRMED | Denied with "provider_direct worker runs require --elevated"; event appended to harness ledger ("authority.expansion_denied") |

### Notable Findings
1. **HARN-001**: Harness shim integrity failure — `.runtime/harness/run_test/shims` is mode 0o775 instead of 0o700
2. **DRIFT-001**: Runtime package drift vs lockfile (aiohttp, anyio, attrs, boto3, botocore) — warns not fails (strict_preflight env var would escalate)
3. **DRIFT-002**: Two unexpected .pth files (zope.interface, google_generativeai nspkg)
4. **HEALTH-001**: Doctor shows `/health` unreachable for single models (step-3.5, zai-glm-4.7 = payment required)
5. **METRICS-001**: All models showing 100% failure rate (billing issue, not routing)
6. **FROZEN-001**: 4 mutation commands are freeze-gated (swap, team-load, profile-load, snapshot-restore); 8+ other mutation commands are NOT freeze-gated despite README implying "freeze blocks forbidden mutations"
7. **SNAPSHOT-001**: Snapshots only persist mapping (slots+fallbacks), NOT teams/profiles/key-state/model-state/freeze state
8. **PROVIDER-001**: Current provider is codex; `broke provider list` shows claude, codex (active), gemini all installed
9. **GATEWAY-001**: Gateway running on :4000 but `_entry_health_status()` fails with "gateway not reachable" in explain/route — health check in doctor works fine, health check in explain does not
10. **KT-08-001**: Provider-direct denial happens at bash level (bin/broke line 1239) before Python — preflight fails but then harness run is denied correctly

---

## Mutation Surface Inventory

Every code path that can change state:
1. `cmd_swap()` → writes .mapping.json
2. `cmd_team_save()` → writes .teams.json
3. `cmd_team_load()` → writes .mapping.json, .env.claude
4. `cmd_team_delete()` → writes .teams.json
5. `cmd_team_fallback()` → writes .teams.json
6. `cmd_team_access()` → writes .teams.json
7. `cmd_profile_new()` → writes .profiles.json
8. `cmd_profile_load()` → writes .mapping.json
9. `cmd_profile_delete()` → writes .profiles.json
10. `cmd_fallback()` → writes .mapping.json
11. `cmd_key_policy()` → writes .rotation.json
12. `cmd_key_state()` → writes .key_state.json
13. `cmd_model_policy()` → writes .model_policy.json
14. `cmd_model_state()` → writes .model_state.json
15. `cmd_snapshot_save()` → writes .snapshots/
16. `cmd_snapshot_restore()` → writes .mapping.json
17. `cmd_config()` → writes config.json, .deployments.json, .env.claude
18. `cmd_harness() set` → writes .harness.json
19. `_save_harness_config()` → writes .harness.json
20. `_save_harness_state()` → writes .harness_state.json
21. `_save_harness_runs()` → writes .harness_runs.json
22. `_save_harness_active_run()` → writes .harness_active_run.json
23. `set_provider()` → writes .provider file (bash)
24. `set_sandbox_profile()` → writes .sandbox-profile (bash)
25. `set_claude_env_export()` → writes .env.claude (bash/python hybrid)
26. `cmd_freeze on/off` → writes/removes .freeze (bash)
27. `harden_runtime_files()` → changes file permissions (bash)
28. `_proxy.py` → atomic writes of key_state, model_state, rotation logs

---

## Authority Expansion Paths

Code paths that can escalate privileges or bypass boundaries:
1. `provider_direct` worker route with `--elevated` flag → bypasses broke_router for direct provider calls
2. `append_provider_direct_auth()` → injects provider API keys into client environment
3. `_proxy.py` key selection → bypasses LiteLLM routing when multiple per-provider keys exist
4. `worker_route_mode()` → switches from broke_router to provider_direct based on harness run state
5. `BROKE_CLIENT_TOKEN` → when empty, client requests may bypass auth on non-health endpoints

---

**To be completed by:** Phase 2 (claim extraction), Phase 3 (truth surface adjudication), Phase 4 (function inventory)
