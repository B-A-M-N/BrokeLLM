# Kill Test Execution Record

**Generated:** 2026-04-04  
**Milestone:** v1 Audit — Runtime Evidence Supplement  
**Scope:** Executable kill tests performed after phase artifact reconstruction

## Overview

This document records actual kill test execution outcomes. The Phase 5 artifact (`KILL_TESTS.md`) defined 14 kill tests but did not execute them. This execution record fills that gap for tests that are safe to run in the current environment.

## Executable Kill Tests Summary

| Kill Test | Status | Executed | Outcome |
|-----------|--------|----------|---------|
| KT-06 | ✅ pass | 2026-04-04 | Floating alias drift warning exists? **FAIL — no warning** |
| KT-08 | ✅ pass | 2026-04-04 | Provider-direct without elevation denied? **PASS** |

## Detailed Results

### KT-06 — Floating Alias Drift

**Target invariants**
- INV-01.2: Canonical Route Identity

**Adversarial procedure**
1. Identify slots with non-pinned backends (floating aliases)
2. Run `broke route` and `broke explain` on those slots
3. Check for drift warnings

**Execution**

- **Floating alias found:** `default` slot (no `pinned: true` in mapping)
- **Command:** `broke route default`
- **Output:** Shows routing without any drift warning
- **Command:** `broke explain default`
- **Output:** Shows selected backend and fallback chain without warning

**Expected safe behavior**
- System warns clearly about floating alias risk

**Observed behavior**
- No warning surfaced in either `route` or `explain` output

**Verdict:** **FAIL** ❌

**Evidence**
```
$ broke route default
  would route to:
    primary       : Groq/Compound  (groq/groq/compound)
    ...
    health        : gateway not reachable

$ broke explain default
  slot          : default
  selected      : Groq/Compound
  backend       : groq/groq/compound
  ...
```
(no drift warning present)

**Failure class**
- DOC_TRUTH_GAP (warning documentation exists but not delivered)
- STATE_DRIFT (floating alias risk not surfaced consistently)

---

### KT-08 — Provider-Direct Worker Authority Expansion

**Target invariants**
- INV-04.1: Verdict Determinism
- INV-05.1: No Global Env Export

**Adversarial procedure**
1. Attempt `broke harness run --worker-route provider_direct` without `--elevated`
2. Inspect denial message and log
3. Optionally retry with `--elevated`

**Execution**

- **Command:** `broke harness run --worker-route provider_direct`
- **Output:** `[harness] provider_direct worker runs require --elevated`
- **Exit code:** Non-zero (command aborted)

**Expected safe behavior**
- Non-elevated provider-direct worker run is denied
- Denial is explicit and logged

**Observed behavior**
- Clear denial message
- No runner launched
- Authority boundary enforced

**Verdict:** **PASS** ✅

**Evidence**
```
$ broke harness run --worker-route provider_direct
[harness] provider_direct worker runs require --elevated
```

**Notes**
- Partially confirms INV-04.2 (authority expansion denial) as observed in Phase 1
- Denial is immediate and user-visible, satisfying deterministic enforcement

---

## Deferred Tests (Not Executed)

| Kill Test | Reason for Deferral |
|-----------|---------------------|
| KT-01 | State-mutating; requires deliberate truth split setup; destructive coordination across multiple surfaces |
| KT-02 | Concurrency-dependent; requires live policy mutations during concurrent requests; heavy |
| KT-03 | Adversarial subprocess probe; requires credential setup and hostile environment inspection |
| KT-04 | Env-leak probing; requires sandbox escape-style testing; currently beyond safe scope |
| KT-05 | Requires induced upstream failure; fault injection setup needed |
| KT-07 | Requires request interception to observe actual forwarded target; instrumentation path not yet available |
| KT-09 | State-mutating; freeze enforcement breadth testing; destructive across mutation surfaces |
| KT-10 | State-mutating; snapshot scope testing; destructive restore operations |
| KT-11 | Strict sandbox escape probe; hostile runtime testing; currently unsafe |
| KT-12 | ⚠️ Could be executed next: state manipulation sanity (non-destructive variants possible) |
| KT-13 | Partially executable; needs deeper harness verdict enforcement probing |
| KT-14 | ⚠️ Could be executed next: launch preflight integrity break (requires tampering) |

## Execution Environment

- **Repository:** `/home/bamn/BrokeLLM`
- **CLI:** `broke` (bash wrapper → Python modules)
- **State files present:** `.mapping.json`, `.key_state.json`, `.model_state.json`, `.rotation.json`, `.sandbox-profile`
- **Runtime:** No active gateway (observed health: "gateway not reachable")
- **Harness state:** mode=off, generation=1, last verdict=ACCEPT
- **Preflight issues observed:** package drift vs lockfile, unexpected .pth files, harness shim integrity failure

## Implications for Final Truth

These execution results provide **runtime evidence** that overrides or confirms provisional Phase 3 classifications:

- **KT-06 FAIL** → Floating alias drift risk is **not being surfaced** as expected. This confirms documentation truth gap (DOC_TRUTH_GAP) around floating alias warnings.
- **KT-08 PASS** → Authority expansion denial is working as designed, confirming VALID classification for harness_verdict_truth on the expansion-denial path.

**Note:** KT-06 contradicts any claim that the system currently warns about floating alias risk. That warning either:
- was removed, or
- never implemented, or
- lives in a different surface not exercised by `route`/`explain`

This is a **concrete drift finding**, not a theoretical gap.

---

## Next Kill Test Candidates

For additional execution, prioritize:

1. **KT-12** (State Manipulation Sanity) — can test invalid state transitions without destroying working state
2. **KT-14** (Launch Preflight Integrity Break) — could intentionally tamper with requirements/drift to verify blocking behavior
3. **KT-05** (Fallback Failure Path) — with controlled upstream simulation or temporary config mutation

These would strengthen evidence for state and install/bootstrap domains.
