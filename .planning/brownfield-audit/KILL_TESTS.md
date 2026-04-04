# BrokeLLM Kill Tests

**Generated:** 2026-04-04  
**Phase:** 5  
**Method:** Manual phase execution fallback

## Test Schema

Each kill test includes:

- kill test id
- target invariants
- adversarial procedure
- expected safe behavior
- failure class if broken
- executability

## Kill Tests

### KT-01 — Truth Split Attack

**Target invariants**

- INV-01.1
- INV-01.2
- INV-02.1
- INV-09.2

**Adversarial procedure**

1. mutate mapping/config/deployments coherence so route identity sources diverge
2. run `broke route`, `broke explain`, and `broke doctor`
3. compare selected backend identity and fallback output

**Expected safe behavior**

- either surfaces remain aligned
- or the system detects the disagreement and fails closed / flags drift loudly

**Failure class if broken**

- OBSERVABILITY_MISMATCH
- STATE_DRIFT

**Executability**

- state-mutating
- currently deferred
- executable in repo state: yes, but not safe for read-only phases

**Current status**

- partially implied by prior route/explain checks
- not fully executed

### KT-02 — Policy Race

**Target invariants**

- INV-03.1
- INV-03.2

**Adversarial procedure**

1. start request A under current policy generation
2. mutate key/model policy generation during request A
3. start request B
4. compare which generations actually govern A vs B

**Expected safe behavior**

- A stays on its original generation
- B picks up the new generation

**Failure class if broken**

- EXECUTION_DIVERGENCE
- STATE_DRIFT

**Executability**

- state-mutating
- concurrency-dependent
- currently deferred

### KT-03 — Harness Bypass

**Target invariants**

- INV-04.2
- INV-05.1

**Adversarial procedure**

1. launch a harness-governed run
2. attempt a direct provider call outside the permitted lane or mediated tool path
3. inspect whether it is blocked or logged

**Expected safe behavior**

- direct bypass attempt is denied or produces a durable violation record

**Failure class if broken**

- BOUNDARY_VIOLATION
- AUTHORITY_LEAK

**Executability**

- credential-dependent
- partially executable
- currently deferred for strong proof

### KT-04 — Env Leak

**Target invariants**

- INV-05.1

**Adversarial procedure**

1. launch a client under the mediated path
2. spawn a subprocess inside that environment
3. attempt to read provider credentials or unintended auth env vars

**Expected safe behavior**

- unauthorized provider credentials are inaccessible

**Failure class if broken**

- AUTHORITY_LEAK
- SECURITY_ISOLATION_FAILURE

**Executability**

- adversarial subprocess probe
- currently deferred

### KT-05 — Fallback Failure Path

**Target invariants**

- INV-01.1
- INV-01.3

**Adversarial procedure**

1. identify a lane with a configured fallback chain
2. make the primary backend fail
3. observe actual fallback choice

**Expected safe behavior**

- fallback order matches declared chain
- next viable backend is chosen deterministically

**Failure class if broken**

- EXECUTION_DIVERGENCE
- STATE_DRIFT

**Executability**

- partially executable
- requires induced upstream failure or equivalent fault injection
- deferred for full proof

**Current status**

- partial feasibility reviewed in Phase 1

### KT-06 — Floating Alias Drift

**Target invariants**

- INV-01.2

**Adversarial procedure**

1. place a slot on a floating alias / non-pinned backend
2. run validation and route/explain surfaces
3. confirm drift risk is surfaced

**Expected safe behavior**

- system warns clearly about floating alias risk

**Failure class if broken**

- DOC_TRUTH_GAP
- STATE_DRIFT

**Executability**

- safe/read-only or low-mutation depending on setup
- executable in current repo state

**Current status**

- partially exercised in earlier phases

### KT-07 — Execution Mismatch

**Target invariants**

- INV-01.1
- INV-02.2
- INV-02.1

**Adversarial procedure**

1. force a known slot selection through route/explain
2. intercept or observe the actual request forwarded by the proxy/LiteLLM chain
3. compare actual execution target to declared route target

**Expected safe behavior**

- actual executed backend matches declared control-plane route

**Failure class if broken**

- EXECUTION_DIVERGENCE
- OBSERVABILITY_MISMATCH

**Executability**

- runtime probe
- partially executable
- stronger proof deferred until request interception path is available

### KT-08 — Provider-Direct Worker Authority Expansion

**Target invariants**

- INV-04.1
- INV-05.1

**Adversarial procedure**

1. attempt `broke harness run --worker-route provider_direct` without `--elevated`
2. inspect denial and ledger event
3. rerun with `--elevated`
4. inspect lane behavior and resulting authority path

**Expected safe behavior**

- non-elevated provider-direct worker run is denied and logged
- elevated path is explicit rather than ambient

**Failure class if broken**

- AUTHORITY_LEAK
- BOUNDARY_VIOLATION

**Executability**

- executable in current repo state

**Current status**

- partially confirmed in Phase 1

### KT-09 — Freeze Enforcement

**Target invariants**

- INV-08.1

**Adversarial procedure**

1. turn freeze on
2. attempt all mutation surfaces, not just swap/team-load/profile-load/snapshot-restore
3. record which writes are still allowed

**Expected safe behavior**

- either all expected mutations are blocked
- or documented scope matches actual behavior exactly

**Failure class if broken**

- BOUNDARY_VIOLATION
- PERSISTENCE_TRUTH_GAP

**Executability**

- state-mutating
- executable in repo state
- currently deferred for controlled destructive pass

### KT-10 — Snapshot Truth

**Target invariants**

- INV-08.2

**Adversarial procedure**

1. save a snapshot
2. mutate teams, profiles, key/model state, and freeze in addition to mapping
3. restore snapshot
4. inspect which state actually rolled back

**Expected safe behavior**

- actual restore scope matches declared snapshot promise

**Failure class if broken**

- PERSISTENCE_TRUTH_GAP
- DOC_TRUTH_GAP

**Executability**

- state-mutating
- executable in repo state
- deferred for controlled destructive pass

### KT-11 — Strict Sandbox Escape Probe

**Target invariants**

- INV-06.1
- INV-06.2

**Adversarial procedure**

1. launch a supported strict-mode client
2. attempt filesystem and env access outside intended strict boundary
3. attempt network behavior outside allowed posture

**Expected safe behavior**

- access is denied outside approved strict surfaces

**Failure class if broken**

- SANDBOX_ENFORCEMENT_FAILURE
- SECURITY_ISOLATION_FAILURE

**Executability**

- hostile runtime probe
- currently deferred

### KT-12 — State Manipulation Sanity

**Target invariants**

- INV-03.2
- INV-05.2
- INV-08.3

**Adversarial procedure**

1. feed invalid or conflicting key/model/profile state transitions
2. exercise manual state-set paths and invalid references
3. inspect whether state is rejected, normalized, or silently accepted

**Expected safe behavior**

- invalid state transitions or references are rejected or normalized consistently

**Failure class if broken**

- STATE_DRIFT
- SECURITY_ISOLATION_FAILURE

**Executability**

- executable in repo state
- partly state-mutating

### KT-13 — Harness Verdict Enforcement Reality Check

**Target invariants**

- INV-04.2

**Adversarial procedure**

1. drive harness evaluation to `BLOCK`, `RETRY_NARROW`, and `ESCALATE`
2. inspect whether runtime behavior actually changes in line with the verdict

**Expected safe behavior**

- blocked work stops
- retry verdicts re-enter the intended path
- escalation requires stronger authority path

**Failure class if broken**

- BOUNDARY_VIOLATION
- OBSERVABILITY_MISMATCH

**Executability**

- partially executable
- deeper end-to-end proof deferred

### KT-14 — Launch Preflight Integrity Break

**Target invariants**

- INV-07.1
- INV-07.2
- INV-09.1
- INV-09.2

**Adversarial procedure**

1. introduce lock/runtime drift, shim-integrity drift, or other launch-integrity breakage
2. run preflight/doctor and attempt launch
3. inspect whether the system blocks or warns appropriately

**Expected safe behavior**

- serious integrity breaks are surfaced clearly and, where required, block protected flows

**Failure class if broken**

- SUPPLY_CHAIN_GAP
- INSTALL_BOOTSTRAP_GAP
- SECURITY_ISOLATION_FAILURE

**Executability**

- executable in repo state
- may require temporary state mutation

## Kill Test To Invariant Mapping Summary

| Kill Test | Invariants |
|---|---|
| KT-01 | INV-01.1, INV-01.2, INV-02.1, INV-09.2 |
| KT-02 | INV-03.1, INV-03.2 |
| KT-03 | INV-04.2, INV-05.1 |
| KT-04 | INV-05.1 |
| KT-05 | INV-01.1, INV-01.3 |
| KT-06 | INV-01.2 |
| KT-07 | INV-01.1, INV-02.1, INV-02.2 |
| KT-08 | INV-04.1, INV-05.1 |
| KT-09 | INV-08.1 |
| KT-10 | INV-08.2 |
| KT-11 | INV-06.1, INV-06.2 |
| KT-12 | INV-03.2, INV-05.2, INV-08.3 |
| KT-13 | INV-04.2 |
| KT-14 | INV-07.1, INV-07.2, INV-09.1, INV-09.2 |

## Executability Summary

### Executable or partially executable now

- KT-06
- KT-08
- KT-12
- KT-14
- partial KT-05
- partial KT-07
- partial KT-13

### Deferred because they are destructive, concurrency-heavy, or hostile runtime probes

- KT-01
- KT-02
- KT-03
- KT-04
- KT-09
- KT-10
- KT-11

## Conclusion

Phase 5 result:

- invariants now define what the system must maintain
- kill tests now define how to try to break those invariants
- later phases can classify drift and risk against a concrete enforcement model instead of vague expectations
