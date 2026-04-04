# Phase 1: Repo Discovery & Ground Truth Bootstrap — CONTEXT.md

## Audit Posture

- Hostile, brownfield audit
- Evidence over declaration
- Runtime over docs
- No wrapper-only verification
- Deep function tracing down to actual mutation/enforcement logic

## Discovery Constraints

- Non-destructive during Phase 1
- Do not mutate `.mapping.json`, `.deployments.json`, snapshots, freeze state, or runtime config
- No stateful destructive probes
- Do not trust passing tests without invariant coverage
- Do not trust docs without code evidence

## Discovery Scope

- Deep function tracing plus top-level boundary audit
- Do not stop at CLI wrappers — trace through: command dispatch, resolver/normalization logic, persistence readers/writers, proxy request path, policy application path, harness launch path, env scrubbing/secret injection path, sandbox setup path, ledger/audit write path
- Audit all code equally; do not prioritize by feature family during discovery
- Runtime probes must capture observed behavior, command exit status, error modes, and whether behavior is documentation-backed, code-backed, and runtime-backed

## Runtime Probes & Kill Tests

### Probe Commitments

- Full `broke` command runtime probe pass — execute every surfaced command, capture exit status, observed output, error modes
- Match observed behavior against declared behavior in docs
- Capture code-backed and runtime-backed evidence for every surface

### Safe Discovery-Time Kill Tests

- KT-05 fallback failure path
- KT-06 floating alias drift
- KT-07 execution mismatch
- KT-08 provider-direct worker authority expansion

### Deferred Destructive Kill Tests

- KT-01 mapping/config drift split
- KT-02 policy race
- KT-09 freeze enforcement
- KT-10 snapshot truth
- KT-11 strict sandbox escape probe
- KT-14 launch preflight integrity break

### Kill Test Completion Rule

- A kill test is not considered complete merely because its non-destructive subset ran.
- Phase 1 performs kill-test feasibility review and safe read-only execution where possible.
- Destructive or state-mutating kill tests are explicitly deferred to the destructive verification phase.

## Priority Concerns

- Security isolation: credential leakage, sandbox escape, secret injection boundaries
- Truth-boundary splits: divergence across route/explain/doctor/runtime behavior
- Harness authority: block semantics, elevation gating, provider-direct authority expansion

## Phase Boundary Rule

- Phase 1 discovers and maps. Later phases adjudicate.
- Phase 1 is prohibited from final VALID/CONDITIONAL/INVALID classification except for obvious invalid/dead surfaces discovered directly during tracing.
- Truth adjudication is reserved for verification phases.
- Suspected drift may be recorded during discovery, but final truth classification is deferred.

## Output Contract

This file serves as the operating contract for downstream phases. Phase 1 produces:

1. Updated CONTEXT.md with full discovery findings
2. SYSTEM_SURFACE_MAP.md skeleton under `.planning/brownfield-audit/`
3. Subsequent phases use this file to know: what was traced, what was probed, what was deferred, what boundaries exist

## Discovery Findings Summary

### System Map
- 3 core files: bin/broke (1421 lines Bash), bin/_mapping.py (3104 lines Python), bin/_proxy.py (800 lines Python)
- 4 support files: bin/_harness_common.py, bin/_harness_shim.py, bin/_fs_common.py, bin/_socket_bridge.py
- 1 test file: tests/test_mapping.py (~1000 lines)
- 12+ state files, 7+ harness state files, 4 harness cache files
- All CLI command surfaces traced to bash dispatch and Python entries

### Notable Findings (Suspected Drift — Defer Adjudication)
1. **HARN-001**: Harness shim dir `.runtime/harness/run_test/shims` mode 0o775 (expected 0o700) — preflight FAIL
2. **HEALTH-001**: Doctor can reach /health, but explain/route _entry_health_status() fails with "gateway not reachable" — **SUSPECTED DRIFT** between doctor health check and explain health check paths
3. **FROZEN-001**: Only 4 mutation commands freeze-gated (swap, team-load, profile-load, snapshot-restore). 8+ other mutation commands NOT frozen: key-policy, key-state, model-policy, model-state, sandbox set, profile new/delete, team save/delete/access, fallback, harness set
4. **SNAPSHOT-001**: Snapshots only save .mapping.json — do NOT persist teams, profiles, key-state, model-state, freeze state
5. **KT-07-001**: Explain and route agree on sonnet → OR/Step-3.5 (aligned at this point). Full alignment check requires live request interception
6. **KT-08-001**: Provider-direct without --elevated confirmed denied at bash level (bin/broke:1239) before Python. Harness event "authority.expansion_denied" appended to ledger
7. **DRIFT-001**: Runtime package drift (aiohttp, anyio, attrs, boto3, botocore) — warned, not failed (BROKE_PREFLIGHT_STRICT env would escalate)
8. **METRICS-001**: All models 100% failure rate (billing/payment issues, not routing)

### Kill Test Feasibility
| Test | Result |
|------|--------|
| KT-05 | Feasible (partial — fallback chain defined, cannot verify runtime failover without live traffic) |
| KT-06 | Feasible (partial — default slot confirmed floating, validate warns) |
| KT-07 | Feasible (partial — explain/route agree, but cannot intercept actual request) |
| KT-08 | **CONFIRMED** — denied correctly, ledger evidence written |

### Deferred (from Kill Test List)
KT-01, KT-02, KT-09, KT-10, KT-11, KT-14 — all require state mutation

## Requirements for This Phase

- DISC-01: Complete
- DISC-02: Complete
- DISC-03: Complete
- DISC-04: Complete
- DISC-05: Complete
- DISC-06: Complete
- DISC-07: Complete

## Downstream Phase Guidance

### Phase 2 — Claim Extraction
- README claims: verify every capability listed (routing, harness, security, sandbox, supply chain, client support)
- ARCHITECTURE.md claims: truth boundary is `_entry_identity()` in bin/_mapping.py
- Key discrepancy to investigate: FROZEN-001 — README implies freeze blocks mutations but only 4 of 14+ mutation surfaces check .freeze file
- Key discrepancy to investigate: HEALTH-001 — doctor health check works but explain health check fails
- Key discrepancy to investigate: METRICS-001 — 100% failure despite doctor showing "healthy" endpoints

### Phase 3 — Truth Surfaces
- Routing truth: `.mapping.json` is single source, consumed by many surfaces — verify no command invents own view
- Health truth: Two different health check paths exist (doctor vs explain) — reconcile
- Execution alignment: `.mapping.json` → `_entry_identity()` → config.json → LiteLLM — verify each step
- Freeze enforcement: Document which surfaces ARE and ARE NOT freeze-gated

### Phase 4 — Function/Tests
- test_mapping.py: audit test coverage against all 12 feature families
- Verify tests cover adversarial cases or only nominal
- Function tracing priority: _preflight_findings(), _proxy.py auth path, _proxy.py key selection, _harness_shim policy checks

---

*Context created: 2026-04-04 during /gsd:discuss-phase 1*
*Updated: 2026-04-04 after decision review*
*Executed: 2026-04-04 — Phase 1 complete (discovery + runtime probes + safe kill tests)*
