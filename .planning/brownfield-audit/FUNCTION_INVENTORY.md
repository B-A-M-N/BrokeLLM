# BrokeLLM Function Inventory

**Generated:** 2026-04-04  
**Phase:** 4  
**Method:** Manual phase execution fallback

## Scope

This artifact traces the major function families required by:

- `FUNC-01`
- `FUNC-02`
- `TEST-01`
- `TEST-02`
- `TEST-03`

It is intentionally grouped by meaningful runtime responsibility rather than every helper function.

## Function Family Schema

Each family records:

- purpose
- owned files/functions
- inputs consumed
- state mutated
- invariants assumed
- truth role (`source-of-truth` or `consumer-only` or `mixed`)
- fail-open/fail-closed posture
- test coverage
- bypassability
- notable gaps

## Function Families

### 1. Wrapper Command Dispatch And Gateway Lifecycle

**Purpose**

- provide the top-level `broke` UX
- dispatch commands
- start, stop, restart, and inspect the local runtime

**Owned files/functions**

- `bin/broke`
- `start_gateway`
- `stop_gateway`
- `restart_gateway`
- `cmd_provider`

**Inputs consumed**

- CLI args
- `.env`
- `.env.claude`
- provider selection state
- sandbox profile state

**State mutated**

- runtime gateway processes
- secret/token files
- `.env.claude`
- launch audit log

**Invariants assumed**

- generated config and deployment files are coherent before startup
- proxy and LiteLLM ports remain available
- provider/client env shaping is applied before launch

**Truth role**

- mixed
- owns launch behavior
- consumes routing/config truth from `_mapping.py`

**Fail-open / fail-closed**

- mixed
- startup generally fails closed when required files or commands are missing
- some operational checks are advisory rather than fully blocking

**Test coverage**

- indirect but meaningful
- README/install/wrapper path assertions in `tests/test_mapping.py`
- no full end-to-end lifecycle integration suite

**Bypassability**

- medium
- users can bypass wrapper orchestration by invoking subcomponents directly

**Notable gaps**

- no integration test covering full `start -> route -> request -> stop` lifecycle
- process management correctness is mostly inferred, not fully exercised

### 2. Mapping Resolution And Route Identity

**Purpose**

- treat `.mapping.json` as the live routing state
- normalize route identity, pin state, and backend catalog linkage

**Owned files/functions**

- `bin/_mapping.py`
- `_entry_identity`
- `_backend_catalog_entry`
- `_entry_pin_state`
- `load`
- `_slots`
- `cmd_list`
- `cmd_route`
- `cmd_explain`

**Inputs consumed**

- `.mapping.json`
- backend catalog constants

**State mutated**

- none on read paths
- `.mapping.json` on mutation paths that feed this family

**Invariants assumed**

- one slot maps to one canonical backend entry
- route identity should be stable across route/explain/doctor/validate surfaces

**Truth role**

- source-of-truth for route identity interpretation

**Fail-open / fail-closed**

- mostly fail-closed for missing slots and malformed entries
- downstream truth can still become misleading if consumers diverge

**Test coverage**

- strong nominal coverage
- route/explain/doctor consistency test exists
- swap persistence tests exist

**Bypassability**

- low if consumers use shared helpers
- higher if future commands compare labels/raw fields directly

**Notable gaps**

- execution alignment beyond dry-run surfaces is deferred

### 3. Fallback Selection And Fallback Policy Display

**Purpose**

- resolve multi-level fallback chains
- support direct lane, backend-scoped, and team-scoped fallback state

**Owned files/functions**

- `bin/_mapping.py`
- `_effective_fallback_chain`
- `_display_fallback_chain`
- `_resolve_backend_target`
- `_pick_fallback_targets_interactively`
- `cmd_fallback`
- `cmd_team_fallback`
- `cmd_fallback_policy`

**Inputs consumed**

- `.mapping.json`
- `.teams.json`
- slot identities
- backend labels/provider-model tokens

**State mutated**

- `.mapping.json`
- `.teams.json`
- regenerated config through `cmd_config`

**Invariants assumed**

- no self-referential or circular fallback chain should survive validation
- display and route surfaces should resolve the same chain

**Truth role**

- mixed
- source-of-truth for active fallback interpretation
- consumes underlying mapping/team state

**Fail-open / fail-closed**

- mostly fail-closed on unknown fallback targets
- live failover behavior itself remains only partially proven

**Test coverage**

- nominal coverage exists for direct backend targets, interactive picker, and team-policy display
- no live runtime failover test

**Bypassability**

- medium
- fallback state can exist correctly in config while real runtime failover remains untested

**Notable gaps**

- no adversarial failover execution under induced upstream failure

### 4. Health Normalization And Doctor Aggregation

**Purpose**

- normalize gateway and upstream health
- aggregate preflight, key/model state, gateway readiness, and harness summary

**Owned files/functions**

- `bin/_mapping.py`
- `_fetch_health_index`
- `_entry_health_status`
- `cmd_doctor`

**Inputs consumed**

- LiteLLM `/health`
- routing state
- key/model policy and state
- harness state
- preflight findings

**State mutated**

- none

**Invariants assumed**

- doctor, route, and explain should agree on health interpretation

**Truth role**

- consumer-only for health source
- source-of-truth aggregator for the doctor surface itself

**Fail-open / fail-closed**

- mixed
- can surface warnings/failures without stopping runtime

**Test coverage**

- nominal route/explain/doctor consistency test exists
- no broad matrix of upstream health edge cases

**Bypassability**

- high concern
- this family is already implicated in an observed truth split

**Notable gaps**

- current runtime evidence shows `doctor` and `route/explain` disagree on health
- this is one of the most important Phase 5 invariant families

### 5. Validation And Launch Preflight

**Purpose**

- check mapping validity, provider presence, fallback sanity, package drift, permissions, and shim integrity before trust is granted

**Owned files/functions**

- `bin/_mapping.py`
- `_validate_findings`
- `_preflight_findings`
- `_bad_runtime_permissions`
- `_bad_harness_shim_dirs`
- `cmd_validate`
- `cmd_preflight`

**Inputs consumed**

- mapping/config files
- env values
- requirements and lock files
- runtime filesystem state

**State mutated**

- none

**Invariants assumed**

- runtime state files should be protected
- shim dirs should match integrity expectations
- dependency/runtime drift should be visible

**Truth role**

- source-of-truth for preflight/validation findings

**Fail-open / fail-closed**

- mixed
- some conditions fail the check
- others remain warnings, even when operationally meaningful

**Test coverage**

- good targeted nominal coverage
- preflight drift, shim failure, and validate output tests exist

**Bypassability**

- medium
- direct process invocation can bypass wrapper-level gating

**Notable gaps**

- warnings vs failures may still be too permissive for some serious drift

### 6. Policy And State Persistence

**Purpose**

- store and retrieve key/model policy and state, teams, profiles, harness config, and related runtime state

**Owned files/functions**

- `bin/_mapping.py`
- `_atomic_write_json`
- `_read_json`
- `_load_rotation_policy`
- `_save_rotation_policy`
- `_load_key_state`
- `_save_key_state`
- `_load_model_policy`
- `_save_model_policy`
- `_load_model_state`
- `_save_model_state`
- `_load_teams`
- `_save_teams`
- `_load_profiles`
- `_save_profiles`
- harness load/save helpers
- `bin/_fs_common.py::locked_file`

**Inputs consumed**

- local JSON state files

**State mutated**

- all primary persistent control-plane JSON files

**Invariants assumed**

- atomic write + file locking preserves coherence
- generation tracking separates old vs new policy epochs

**Truth role**

- source-of-truth owners for persisted control-plane state

**Fail-open / fail-closed**

- mostly fail-closed on malformed/missing file paths through defaulting or explicit exceptions
- logical last-writer-wins races are still a design concern across processes

**Test coverage**

- good nominal coverage for key/model policy, key/model state, export/import, team/profile CRUD

**Bypassability**

- medium
- direct file edits can bypass command-level invariants

**Notable gaps**

- no full concurrent multi-process race test

### 7. Team, Profile, Snapshot, And Freeze Controls

**Purpose**

- persist reusable routing/access presets
- save and restore mapping snapshots
- gate certain mutations behind freeze state

**Owned files/functions**

- `bin/_mapping.py`
- `cmd_team_save`
- `cmd_team_load`
- `cmd_team_list`
- `cmd_team_delete`
- `cmd_team_access`
- `cmd_profile_new`
- `cmd_profile_load`
- `cmd_profile_list`
- `cmd_profile_delete`
- `cmd_snapshot_save`
- `cmd_snapshot_list`
- `cmd_snapshot_restore`
- `bin/broke` freeze toggles

**Inputs consumed**

- team/profile state
- mapping state
- freeze sentinel

**State mutated**

- `.teams.json`
- `.profiles.json`
- `.snapshots/*`
- `.mapping.json`
- `.freeze`

**Invariants assumed**

- profile references should resolve to existing teams
- snapshot restore should regenerate effective config
- freeze should block protected mutation paths

**Truth role**

- source-of-truth for team/profile/snapshot persistence
- partial/weak truth for freeze enforcement breadth

**Fail-open / fail-closed**

- mixed
- profile/team load fail closed when targets are missing
- freeze enforcement is incomplete across mutation surfaces

**Test coverage**

- strong nominal CRUD/export/import/snapshot round-trip coverage
- limited freeze enforcement coverage

**Bypassability**

- high for freeze expectations
- medium for snapshot scope expectations

**Notable gaps**

- snapshot captures mapping only, not full state
- freeze does not guard many mutation surfaces

### 8. Proxy Auth Enforcement, Candidate Selection, And Forwarding

**Purpose**

- enforce client token auth
- rate-limit repeated invalid auth
- map client model labels to routed lanes
- choose provider/key/model candidates
- forward to LiteLLM

**Owned files/functions**

- `bin/_proxy.py`
- `_client_authorized`
- `_read_request_body`
- `prepare_candidates`
- `resolve_requested_model`
- `ordered_deployments`
- `ordered_models`
- `classify_error`
- `_forward_once`
- `_proxy_request`
- update/mark state helpers

**Inputs consumed**

- client HTTP requests
- deployments mapping
- route mapping
- key/model policy and state
- auth tokens

**State mutated**

- rotation log
- key/model state
- provider/lane usage tracking

**Invariants assumed**

- unknown model ids should fail closed
- client auth must not pass through blindly
- internal auth must be injected on upstream forwarding

**Truth role**

- source-of-truth for request-time execution choice after config generation

**Fail-open / fail-closed**

- generally strong fail-closed posture on unknown model and auth failures
- forwarding correctness still not fully proven end-to-end

**Test coverage**

- good nominal direct unit coverage for auth rejection, rate limiting, body size limits, model-label mapping, and forwarding header behavior
- still largely mock-backed

**Bypassability**

- medium
- runtime forwarding path is critical and still not tested under full live upstream behavior

**Notable gaps**

- no broad live upstream matrix
- no end-to-end request interception proving exact selected upstream target

### 9. Harness Orchestration, Verdicts, Checkpoints, And Ledger

**Purpose**

- manage harness config/state/cache
- register runs
- evaluate verdicts
- append ledger events
- cache prompt/evidence/review layers

**Owned files/functions**

- `bin/_mapping.py`
- `_harness_verdict`
- `_register_harness_run`
- `_complete_harness_run`
- `_append_harness_event`
- `_resolve_harness_prefix`
- `_build_harness_evidence_packet`
- `cmd_harness`
- `bin/_harness_common.py::append_event`

**Inputs consumed**

- harness config/state files
- preflight findings
- validate findings
- role verdict inputs
- runtime metadata

**State mutated**

- harness config/state
- harness cache files
- harness run tracking
- append-only event logs

**Invariants assumed**

- deterministic findings outrank role opinion
- authority expansion requires elevation
- cached reviews should only be reused on matching evidence

**Truth role**

- source-of-truth for harness state and verdict records

**Fail-open / fail-closed**

- mixed
- some boundary failures block
- harness mode off or partial proof can still yield permissive summaries

**Test coverage**

- solid nominal coverage for verdict categories, cache reuse, run registration, and provider-direct elevation gating

**Bypassability**

- medium to high
- current harness is real, but not all work necessarily flows through it

**Notable gaps**

- no broader end-to-end mediated-agent run verification
- no deep replay integrity audit yet

### 10. Sandbox Setup, Env Scrubbing, Secret Injection, And Client Launch

**Purpose**

- decide sandbox profile
- shape child env
- generate scoped secret files
- launch Claude/Codex/Gemini under the selected boundary

**Owned files/functions**

- `bin/broke`
- `get_sandbox_profile`
- `set_sandbox_profile`
- `set_claude_env_export`
- `ensure_secret_file`
- `run_client_command`
- strict `bwrap` and socket-bridge path
- `bin/_socket_bridge.py`
- `bin/_harness_shim.py`

**Inputs consumed**

- client choice
- sandbox profile
- env vars and secret files
- provider route selection

**State mutated**

- `.sandbox-profile`
- `.env.claude`
- secret token files
- launch audit log

**Invariants assumed**

- provider creds remain scoped
- strict mode narrows filesystem and network surface
- unsupported combinations like strict Gemini are denied

**Truth role**

- source-of-truth for launched client runtime boundary

**Fail-open / fail-closed**

- mixed
- provider-direct without elevation fails closed
- some compatibility and isolation guarantees remain partially runtime-proven

**Test coverage**

- moderate nominal coverage via shell assertions and shim tests
- little live runtime isolation proof

**Bypassability**

- high if clients are launched outside the wrapper
- lower when using the intended wrapper path

**Notable gaps**

- no adversarial subprocess env leak probe in-repo
- no strict sandbox escape test yet

### 11. Install / Bootstrap

**Purpose**

- bootstrap dependencies, env file, command symlink, and default state

**Owned files/functions**

- `install.sh`
- `bin/_mapping.py::cmd_init`

**Inputs consumed**

- Python interpreter
- requirements/lock files
- `.env.template`

**State mutated**

- dependency install state
- linked `broke` command
- `.env`
- initialized state files

**Invariants assumed**

- lockfile and requirements stay coherent
- bootstrap should leave the repo in a runnable default state

**Truth role**

- source-of-truth for install/bootstrap behavior

**Fail-open / fail-closed**

- mostly fail-closed due shell `set -e` style behavior

**Test coverage**

- light-to-moderate
- mostly assertion-based rather than executed installer integration

**Bypassability**

- medium
- users can bypass bootstrap and create custom partial setups

**Notable gaps**

- no full installer execution test in isolated environment

## Test Strategy Review

### Overall Posture

The repository has one large primary test file:

- `tests/test_mapping.py`

Coverage style is:

- mostly unit and command-surface regression tests
- some direct proxy tests
- many fake/mock-backed runtime paths
- very little full integration or adversarial runtime proof

### Nominal vs Adversarial Coverage

**Nominally covered well**

- route/explain identity consistency
- swap and fallback configuration
- key/model policy and manual state operations
- team/profile CRUD and import/export
- harness verdict/cache behavior
- proxy auth rejection and invalid-model rejection
- snapshot round-trip basics
- README/install/documentation regressions

**Partially adversarial**

- provider-direct worker denial without elevation
- invalid client auth throttling
- oversized proxy body rejection
- preflight shim-integrity failure
- floating alias warnings

**Still largely unproven adversarially**

- live fallback failover
- policy generation race behavior
- true execution alignment through forwarded upstream requests
- strict sandbox escape resistance
- credential leak resistance from launched child processes
- freeze protection breadth
- snapshot full-state expectations

### Mock / Fake Usage Review

Mocks and fakes are concentrated around:

- proxy HTTP forwarding
- health response emulation
- harness role evaluation inputs

This is useful for deterministic regression checks, but it hides real risk in:

- upstream transport behavior
- exact request forwarding semantics under failure
- multi-process runtime interactions
- auth and env behavior in real child processes

Conclusion:

- mock-heavy tests are valid for nominal correctness
- they are not sufficient for strong runtime or adversarial claims

## Domain Coverage Judgment

| Domain | Judgment | Notes |
|---|---|---|
| Routing | Moderate | Strong dry-run and config coverage; little live failover proof |
| Policy | Moderate | Good key/model policy tests; race/isolation still deferred |
| Harness | Moderate | Verdict/cache/run-registration covered; end-to-end mediation still thin |
| Security | Moderate | Strong auth rejection and unknown-model fail-closed checks; env-leak proof missing |
| Sandbox | Weak | Mostly code/test assertions, not hostile runtime probing |
| Execution Alignment | Weak | Route/explain agreement exists; actual forwarded target proof still partial |
| Install/Bootstrap | Weak to Moderate | Installer assertions exist; no full isolated execution run |
| Snapshot/Freeze | Weak | Snapshot round-trip tested, but scope and freeze breadth remain problematic |
| Client | Moderate | Codex strongest, Claude partial, Gemini CLI intentionally unreliable |
| Provider | Weak to Moderate | Catalog and some runtime doctor evidence exist; broad provider path proof is thin |

## Core Claims With Weak Or No Meaningful Coverage

- full execution alignment from route choice to actual upstream request
- live fallback activation under upstream failure
- credential isolation against child-process probing
- strict sandbox isolation under hostile conditions
- freeze enforcing all expected mutation boundaries
- snapshot/restore covering more than mapping state

## Phase 5 Handoff Gaps

These are the highest-value gaps to convert into invariants and kill tests next:

1. health normalization divergence across doctor vs route/explain
2. execution alignment beyond dry-run surfaces
3. freeze enforcement breadth
4. snapshot truth scope
5. credential isolation under subprocess probing
6. strict sandbox escape resistance
7. policy generation isolation under concurrent requests

## Conclusion

Phase 4 result:

- the major function families are now grouped and classified
- the current test strategy is useful but not strong enough to justify aggressive runtime claims
- the highest-risk areas for Phase 5 are now concrete enough to become formal invariants and kill tests
