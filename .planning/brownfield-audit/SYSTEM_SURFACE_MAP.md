# BrokeLLM System Surface Map

**Generated:** 2026-04-04  
**Phase:** 8  
**Method:** Normalized from the Phase 1 draft surface map

This artifact is the normalized deliverable form of the earlier draft `_SYSTEM_SURFACE_MAP.md`. It documents the system surfaces required by `ART-02`.

## A. CLI Command Surfaces

### Gateway Lifecycle

- `broke start`
  - dispatch: `bin/broke:start_gateway()`
  - downstream: `bin/_mapping.py::cmd_config()`, `bin/_proxy.py`
- `broke stop`
  - dispatch: `bin/broke:stop_gateway()`
- `broke restart`
  - dispatch: `bin/broke:restart_gateway()`
- `broke status`
  - dispatch: inline in `bin/broke`

### Routing And Resolution

- `broke list`
- `broke models`
- `broke route <slot>`
- `broke explain <slot>`
- `broke swap`
- `broke fallback <slot>`
- `broke fallback policy`

Primary Python surface:

- `bin/_mapping.py`
  - `cmd_list`
  - `cmd_models`
  - `cmd_route`
  - `cmd_explain`
  - `cmd_swap`
  - `cmd_fallback`
  - `cmd_fallback_policy`

### Observability

- `broke doctor`
- `broke validate`
- `broke probe <slot>`
- `broke metrics`

Primary Python surface:

- `bin/_mapping.py`
  - `cmd_doctor`
  - `cmd_validate`
  - `cmd_probe`
  - `cmd_metrics`

### Key And Model Policy

- `broke key-policy`
- `broke key-state`
- `broke model-policy`
- `broke model-state`

Primary Python surface:

- `bin/_mapping.py`
  - `cmd_key_policy`
  - `cmd_key_state`
  - `cmd_model_policy`
  - `cmd_model_state`

### Team, Profile, Snapshot, Freeze

- `broke team save|load|list|delete|fallback|access`
- `broke profile new|load|list|delete`
- `broke snapshot save|list|restore`
- `broke freeze`

Primary Python surface:

- `bin/_mapping.py`
  - `cmd_team_save`
  - `cmd_team_load`
  - `cmd_team_list`
  - `cmd_team_delete`
  - `cmd_team_fallback`
  - `cmd_team_access`
  - `cmd_profile_new`
  - `cmd_profile_load`
  - `cmd_profile_list`
  - `cmd_profile_delete`
  - `cmd_snapshot_save`
  - `cmd_snapshot_list`
  - `cmd_snapshot_restore`

### Harness And Sandbox

- `broke harness`
- `broke harness set`
- `broke harness evaluate`
- `broke harness run`
- `broke sandbox`
- `broke sandbox set <profile>`

Primary surfaces:

- `bin/broke`
- `bin/_mapping.py::cmd_harness`
- `bin/_harness_common.py`
- `bin/_harness_shim.py`
- `bin/_socket_bridge.py`

### Provider / Bootstrap / Transfer

- `broke provider`
- `broke provider list`
- `broke provider swap`
- `broke init`
- `broke export`
- `broke import`
- `broke mode`

## B. Runtime Control Surfaces

### Routing State

- `.mapping.json`
  - live slot-to-backend routing state
  - consumed by route/explain/doctor/config/validate

### Generated Deployment State

- `.deployments.json`
  - generated internal deployment map used by proxy request-time selection

### Health State

- LiteLLM `/health`
  - transient runtime-only health source

### Policy And State Files

- `.rotation.json`
- `.key_state.json`
- `.model_policy.json`
- `.model_state.json`

### Team / Profile / Snapshot / Freeze State

- `.teams.json`
- `.profiles.json`
- `.snapshots/`
- `.freeze`

### Harness State

- `.harness_state.json`
- `.harness_runs.json`
- `.harness_active_run.json`
- `.harness_prompt_contracts.json`
- `.harness_prefix_cache.json`
- `.harness_evidence_cache.json`
- `.harness_review_cache.json`
- `.runtime/harness/<run_id>/events.jsonl`

### Sandbox Profile

- `.sandbox-profile`

## C. Integration Surfaces

### Internal

- wrapper to config generation
- wrapper to proxy
- proxy to LiteLLM
- harness launcher to client runtime
- sandbox runner and local socket bridge

### Client Integrations

- Claude CLI
- Codex CLI
- Gemini CLI
- Gemini endpoint

### Provider Integrations

- OpenRouter
- Groq
- Cerebras
- GitHub Models
- Gemini
- Hugging Face

## D. Trust Surfaces

The audit traced these truth surfaces:

- routing_truth
- health_truth
- key_policy_truth
- key_state_truth
- model_policy_truth
- model_state_truth
- fallback_resolution_truth
- harness_verdict_truth
- credential_isolation_truth
- sandbox_runtime_boundary_truth
- execution_alignment_truth
- launch_preflight_integrity_truth
- snapshot_restore_truth
- freeze_enforcement_truth
- supply_chain_truth

## E. Important Boundary Notes

- freeze is not a universal mutation guard
- snapshot restore is mapping-scoped, not full-state restore
- execution alignment and strict sandbox claims remain only partially proven
- health truth currently shows a known split between `doctor` and `route/explain`
