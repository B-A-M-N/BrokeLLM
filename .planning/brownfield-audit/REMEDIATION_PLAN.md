# BrokeLLM Remediation Plan

**Generated:** 2026-04-04  
**Phase:** 7  
**Method:** Manual phase execution fallback

This remediation plan is ordered by the required buckets:

1. security-critical
2. authority-critical
3. truth-critical
4. runtime-critical
5. install/usability-critical
6. documentation-critical

Each item is grounded in the existing risk and invariant evidence. This is a remediation plan, not a fix phase.

## Security-Critical

### REM-SEC-01 — Prove or harden credential-lane isolation against subprocess/env-leak paths

- **Issue:** credential isolation is designed but not adversarially proven against env-leak and bypass attempts
- **Root cause:** lane design exists, but direct leak and bypass proof was deferred
- **Required invariant:** `INV-05.1 Scoped Credential Injection`
- **Enforcement surface:** runtime guard, harness launch path, kill-test coverage
- **Change type needed:** `test` + `runtime guard`
- **Evidence:** `RISK-007`, `KT-03`, `KT-04`, `KT-08`

### REM-SEC-02 — Add live strict-mode escape-resistance evidence or tighten strict claims

- **Issue:** strict sandbox claims exceed current live proof depth
- **Root cause:** hardening work exists, but no executed escape probe backs the strongest isolation claim
- **Required invariant:** `INV-06.1 Strict Boundary Narrowing`, `INV-06.2 Unsupported Strict Clients Must Be Denied`
- **Enforcement surface:** sandbox runtime, kill-test coverage, docs
- **Change type needed:** `test` + `runtime guard` + `docs correction`
- **Evidence:** `RISK-008`, `KT-11`

## Authority-Critical

### REM-AUTH-01 — Make freeze semantics match the mutation boundary or narrow the feature claim

- **Issue:** freeze overclaims broad control-plane protection while guarding only a narrow mutation subset
- **Root cause:** `.freeze` is wired to selected commands rather than a comprehensive mutation layer
- **Required invariant:** `INV-08.1 Freeze Must Match Its Implied Boundary`
- **Enforcement surface:** command dispatch layer, mutation guard layer, docs
- **Change type needed:** `code` + `runtime guard` + `docs correction`
- **Evidence:** `RISK-002`, `DRIFT-01`, `DRIFT-02`

### REM-AUTH-02 — Prove non-advisory harness verdict semantics

- **Issue:** harness doctrine is stronger than directly demonstrated runtime enforcement breadth
- **Root cause:** some authority boundaries are proven, but full verdict-effect coverage is incomplete
- **Required invariant:** `INV-04.2 Verdict Semantics Must Be Real`
- **Enforcement surface:** harness runtime, verdict engine tests, ledger assertions
- **Change type needed:** `test` + `runtime guard`
- **Evidence:** `RISK-006`, `KT-13`

## Truth-Critical

### REM-TRUTH-01 — Unify doctor/route/explain health interpretation

- **Issue:** health truth split across major control-plane surfaces
- **Root cause:** health normalization or surface consumption paths diverge
- **Required invariant:** `INV-02.1 Shared Normalization Boundary`, `INV-02.2 Health Agreement Across Surfaces`
- **Enforcement surface:** `_fetch_health_index`, `_entry_health_status`, command consumers, regression tests
- **Change type needed:** `code` + `test`
- **Evidence:** `RISK-001`, `DRIFT-04`

### REM-TRUTH-02 — Correct snapshot scope semantics or widen snapshot coverage

- **Issue:** snapshot/restore is narrower than the state-control semantics suggest
- **Root cause:** snapshot payload captures mapping state rather than full control-plane state
- **Required invariant:** `INV-08.2 Snapshot Restore Scope Must Be Truthful`
- **Enforcement surface:** snapshot format, restore flow, docs
- **Change type needed:** `code` or `docs correction`
- **Evidence:** `RISK-003`, `DRIFT-01`

## Runtime-Critical

### REM-RUN-01 — Prove end-to-end execution alignment

- **Issue:** actual forwarded request target is still not fully runtime-proven against route/explain
- **Root cause:** execution path is partially unit-tested but lacks stronger interception-grade runtime verification
- **Required invariant:** `INV-01.1 Route/Explain Consistency`, `INV-02.1 Shared Normalization Boundary`
- **Enforcement surface:** proxy forwarding tests, request interception, runtime verification
- **Change type needed:** `test`
- **Evidence:** `RISK-004`, `KT-07`

### REM-RUN-02 — Prove generation isolation for live key/model policy mutation

- **Issue:** key/model policy generation isolation under concurrent requests remains unproven
- **Root cause:** persistence/generation counters exist without strong concurrent execution evidence
- **Required invariant:** `INV-03.1 Generation Isolation`, `INV-03.2 State Transition Sanity`
- **Enforcement surface:** proxy request handling, state transition tests, runtime concurrency harness
- **Change type needed:** `test` + `runtime guard`
- **Evidence:** `RISK-005`, `KT-02`

### REM-RUN-03 — Tighten or prove broad client/provider support semantics

- **Issue:** client/provider breadth exceeds uniform proof depth
- **Root cause:** catalog presence and compatibility claims outpace fresh runtime proof for several integrations
- **Required invariant:** `INV-01.1`, `INV-05.2`
- **Enforcement surface:** integration tests, compatibility docs, provider/client support policy
- **Change type needed:** `test` + `docs correction`
- **Evidence:** `RISK-010`, `DRIFT-09`, `DRIFT-10`

## Install/Usability-Critical

### REM-INSTALL-01 — Restore runtime alignment with the hash-locked baseline

- **Issue:** observed runtime package drift and unexpected `.pth` files weaken the trusted baseline
- **Root cause:** local environment deviates from the locked install intent
- **Required invariant:** `INV-07.1 Hash-Bound Install Path`, `INV-07.2 Runtime Drift Must Be Detectable`, `INV-09.1 Bootstrap Must Produce A Runnable Baseline`
- **Enforcement surface:** install/bootstrap flow, preflight, operator docs
- **Change type needed:** `runtime guard` + `docs correction`
- **Evidence:** `RISK-009`, `DRIFT-08`

### REM-INSTALL-02 — Rebalance preflight warning vs failure severity

- **Issue:** some meaningful drift is surfaced but not elevated enough to stop unsafe trust assumptions
- **Root cause:** preflight findings classify certain conditions as warnings even when they materially affect trust
- **Required invariant:** `INV-09.1 Bootstrap Must Produce A Runnable Baseline`
- **Enforcement surface:** preflight classification logic
- **Change type needed:** `code` + `test`
- **Evidence:** `DRIFT-02`

## Documentation-Critical

### REM-DOC-01 — Narrow README/state-control language around freeze and snapshot semantics

- **Issue:** user-facing language overstates what freeze and snapshot currently protect
- **Root cause:** docs describe the conceptual feature more broadly than the enforced boundary
- **Required invariant:** `INV-08.1`, `INV-08.2`
- **Enforcement surface:** README and user docs
- **Change type needed:** `docs correction`
- **Evidence:** `RISK-002`, `RISK-003`

### REM-DOC-02 — Make uneven client/provider support explicit at the point of claim

- **Issue:** broad compatibility/support language can be read as more uniform than the evidence supports
- **Root cause:** support breadth is described faster than proof depth is distinguished
- **Required invariant:** `INV-01.1`, `INV-05.2`
- **Enforcement surface:** README, integration docs, provider/client tables
- **Change type needed:** `docs correction`
- **Evidence:** `RISK-010`
