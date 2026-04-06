---
phase: 5
name: Invariants Definition & Kill Test Design
completed: 2026-04-04
method: manual_phase_execution_fallback
requirements_completed:
  - KILL-01
  - KILL-02
  - KILL-03
  - INV-01
  - INV-02
  - INV-03
  - INV-04
  - INV-05
  - INV-06
  - INV-07
  - INV-08
  - INV-09
artifacts:
  - .planning/brownfield-audit/INVARIANTS.md
  - .planning/brownfield-audit/KILL_TESTS.md
status: passed
notes:
  - "14 kill tests designed; executability classified; execution deferred to runtime phases"
  - "20+ invariants defined across 9 families; mapped to kill tests for verification"
---

# Phase 5 Summary

## Result

✅ **Passed** — All Phase 5 requirements satisfied.

## Deliverables

- `INVARIANTS.md`: 20+ invariants across 9 families (routing, truth boundary, policy, harness, security, sandbox, supply chain, state, install/bootstrap)
- `KILL_TESTS.md`: 14 kill tests (KT-01..KT-14) with adversarial procedures, target invariants, and executability classification

## Invariant Coverage By Family

| Family | Invariants | Key Properties |
|--------|------------|----------------|
| Routing | 3 | route/explain consistency, canonical identity, floating alias drift |
| Truth Boundary | 2 | shared normalization, boundary enforceability |
| Policy | 3 | generation isolation, request coupling, rotation cooldown |
| Harness | 2 | verdict determinism, authority expansion denial |
| Security | 5 | no global env export, no secret leakage, fail-closed unknown model, rate limiting, scoped injection |
| Sandbox | 4 | strict filesystem, network posture, local bridge exclusivity, blocked clients |
| Supply Chain | 3 | hash-bound install, offline wheel mirror, reproducible baseline |
| State | 3 | freeze block integrity, snapshot restore correctness, team/profile persistence |
| Install/Bootstrap | 3 | runnable system, prerequisite coherence, default state |

## Kill Test Highlights

KT-01–KT-14 cover:
- Truth consistency attacks (KT-01)
- Concurrent policy races (KT-02)
- Credential/proxy env leaks (KT-03, KT-04)
- Harness authority escalation (KT-06, KT-08)
- Fallback failover correctness (KT-05)
- Execution alignment forward-path (KT-07)
- Sandbox escape (KT-11 strict mode)
- Freeze enforcement breadth (KT-09)
- Snapshot truth scope (KT-10)
- Preflight integrity break (KT-14)

## Executability Status

| Status | Count | Tests |
|--------|-------|-------|
| Safe/read-only | 3 | KT-01, KT-05, KT-06 |
| State-mutating (safe in repo) | 6 | KT-07, KT-09, KT-10, KT-12, KT-13, KT-14 |
| Requires live credentials | 2 | KT-02, KT-11 |
| Currently deferred (unsafe/blocked) | 3 | KT-02 (race), KT-03 (leak), KT-04 (sandbox escape), KT-08 (elevation) |

## Notes

- Phase 5 intentionally stopped at design; kill test execution belongs to later runtime verification phases (outside current Scope)
- The 14-test design is derived from truth surface findings and function-family gaps from Phases 3–4
- Some tests (KT-02 policy race, KT-11 strict sandbox escape) remain marked as requiring live credentials and environment hardening
