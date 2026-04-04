# Phase 5: Invariants Definition & Kill Test Design - Research

**Generated:** 2026-04-04  
**Status:** Ready for planning  
**Method:** Manual fallback research because the local `get-shit-done` execution path still delegates into a broken runtime missing `pg`

## Research Objective

Answer: what must be understood to plan Phase 5 well?

Phase 5 is where the audit stops describing what exists and starts defining what must never be violated.

It must:

1. define the hard invariants for routing, truth boundaries, policy, harness, security, sandbox, supply chain, state, and install/bootstrap,
2. design all 14 kill tests as concrete adversarial procedures,
3. map kill tests back to the invariants they verify,
4. classify which kill tests are executable in the current repo state.

This phase is the bridge between descriptive audit work and enforcement-oriented audit work.

## Strong Inputs Already Available

Phase 5 can now stand on:

- `.planning/brownfield-audit/TRUTH.yaml`
- `.planning/brownfield-audit/INTEGRATION_MATRIX.yaml`
- `.planning/brownfield-audit/FUNCTION_INVENTORY.md`
- `.planning/brownfield-audit/_SYSTEM_SURFACE_MAP.md`
- `.planning/phases/01-CONTEXT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`

That means invariants should not be invented from intuition. They should be derived from:

- already-mapped truth surfaces
- already-observed drift
- already-traced function families

## Invariant Families Required

The requirements already partition the invariant space correctly:

- routing invariants
- truth-boundary invariants
- policy invariants
- harness invariants
- security invariants
- sandbox invariants
- supply-chain invariants
- state invariants
- install/bootstrap invariants

The key planning implication is that each invariant should be written as:

1. a clear required property
2. a justification/evidence basis
3. a related failure mode if broken
4. the kill tests that verify it

Without that structure, the invariant list will become prose instead of an enforceable specification.

## Kill Test Baseline

From earlier phases, the current audit already references or implies:

- KT-01 mapping/config drift split
- KT-02 policy race
- KT-05 fallback failure path
- KT-06 floating alias drift
- KT-07 execution mismatch
- KT-08 provider-direct worker authority expansion
- KT-09 freeze enforcement
- KT-10 snapshot truth
- KT-11 strict sandbox escape probe
- KT-14 launch preflight integrity break

That leaves additional tests to round out the full 14. Phase 5 should not invent them randomly; it should fill the invariant coverage gaps left by current truth and function findings.

## Most Important Gaps Driving Invariant Design

From Phase 3 and Phase 4, the highest-value unresolved areas are:

1. health normalization divergence
2. execution alignment beyond dry-run surfaces
3. freeze enforcement breadth
4. snapshot truth scope
5. credential isolation against subprocess probing
6. strict sandbox isolation under hostile conditions
7. generation isolation for key/model policy updates
8. live fallback behavior under upstream failure

These should drive the strongest invariants and the earliest kill tests.

## Planning Implications

### A. Invariants should be grouped by domain, not by file

That means:

- routing invariants may reference multiple files
- harness invariants may span `bin/broke`, `_mapping.py`, and `_harness_*`
- sandbox invariants may span launch code and bridge code

This matters because the invariant is about system behavior, not source layout.

### B. Kill tests need executability classification

Each kill test should state:

- whether it is safe/read-only
- whether it mutates runtime state
- whether it requires live credentials
- whether it is executable in the current repo state

This is mandatory because earlier phases already discovered that some tests are only partially feasible or deferred.

### C. Phase 5 should not run the full kill test suite

This phase designs and classifies the kill tests. It does not need to execute all of them.

Execution belongs later when the audit reaches runtime-heavy and remediation-linked work.

### D. Kill tests should map to the real failure taxonomy

Each test should be able to expose one or more categories such as:

- boundary violation
- state drift
- authority leak
- observability mismatch
- execution divergence
- security isolation failure
- sandbox enforcement failure

That keeps Phase 6 drift/risk work grounded.

## Recommended Output Shape

This phase should produce:

- `INVARIANTS.md`
- `KILL_TESTS.md`

And both artifacts should be tightly linked:

- invariants should reference kill tests
- kill tests should reference invariants

## Conclusion

Phase 5 should be planned as an enforcement-specification phase.

The best execution shape is:

1. derive invariant families from current truth and function findings,
2. define concrete invariants with explicit failure modes,
3. design all 14 kill tests as adversarial procedures,
4. classify executability in the current repo state.
