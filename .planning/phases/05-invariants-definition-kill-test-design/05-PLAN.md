# Phase 5: Invariants Definition & Kill Test Design - Plan

**Phase:** 5  
**Name:** Invariants Definition & Kill Test Design  
**Goal:** Define all hard invariants the system must maintain, design all 14 kill tests, and map which kill tests are executable in current repo state.

## Phase Requirements

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

## Success Criteria

1. All routing invariants are defined and documented
2. All truth-boundary invariants are defined and documented
3. All policy invariants are defined and documented
4. All harness invariants are defined and documented
5. All security, sandbox, supply-chain, state, and install/bootstrap invariants are defined
6. `INVARIANTS.md` is complete
7. All 14 kill tests (KT-01 through KT-14) are designed with concrete adversarial procedures
8. `KILL_TESTS.md` is complete with kill test to invariant mapping and executability classification

## Execution Strategy

Phase 5 should execute as a formal enforcement-specification phase.

It should reuse:

- provisional truth classifications from Phase 3
- function and test gaps from Phase 4
- known drift candidates and deferred proof gaps from earlier phases

It should avoid:

- final drift/risk classification from Phase 6
- final truth adjudication from Phase 7
- running the full kill test suite now

## Planning Assumption

The Phase 5 outputs should be two linked artifacts:

- `INVARIANTS.md`
- `KILL_TESTS.md`

`INVARIANTS.md` defines what must remain true.

`KILL_TESTS.md` defines how to try to break those invariants.

The artifacts should cross-reference one another rather than being written independently.

## Plan

### Plan 5.1 — Define Invariant Schema And Domain Buckets

**Objective:** Establish the structure and domain grouping for the invariant catalog.

**Inputs:**

- `.planning/ROADMAP.md`
- `.planning/REQUIREMENTS.md`
- `.planning/brownfield-audit/TRUTH.yaml`
- `.planning/brownfield-audit/FUNCTION_INVENTORY.md`

**Tasks:**

1. define the invariant record schema
2. group invariants by the required `INV-*` domains
3. connect major truth-surface failures and function gaps to the correct invariant families

**Outputs:**

- invariant catalog skeleton in `INVARIANTS.md`

**Verification:**

- all `INV-01` through `INV-09` domains are represented
- each invariant record includes required property, rationale, and related failure mode

### Plan 5.2 — Populate Hard Invariants

**Objective:** Write the concrete invariants the system must maintain.

**Required families:**

- routing
- truth boundary
- policy
- harness
- security
- sandbox
- supply chain
- state
- install/bootstrap

**Tasks:**

1. define routing invariants such as route=explain and deterministic fallback ordering
2. define truth-boundary invariants for shared normalization and disagreement detection
3. define policy generation and state-transition invariants
4. define harness authority and verdict invariants
5. define security and credential isolation invariants
6. define sandbox, supply-chain, state, and install/bootstrap invariants

**Outputs:**

- populated `INVARIANTS.md`

**Verification:**

- every `INV-*` requirement is covered
- invariants are system-behavior statements, not implementation trivia

### Plan 5.3 — Design All 14 Kill Tests

**Objective:** Produce the full kill-test catalog as concrete adversarial procedures.

**Tasks:**

1. define KT-01 through KT-14
2. specify:
   - target invariant(s)
   - adversarial procedure
   - expected safe behavior
   - expected failure classification if broken
3. classify each test as:
   - read-only safe
   - state-mutating
   - credential-dependent
   - currently executable or deferred

**Outputs:**

- `KILL_TESTS.md`

**Verification:**

- all 14 tests are present
- each test maps back to one or more invariants
- each test has executability classification

### Plan 5.4 — Map Kill Tests To Current Repo Reality

**Objective:** Make the kill-test set usable by later phases by grounding it in current repo conditions.

**Tasks:**

1. mark which tests are already partially probed from earlier phases
2. mark which require live credentials or induced upstream failure
3. mark which require destructive/state-mutating execution
4. record prerequisites and blockers

**Priority tests to ground carefully:**

- KT-01 mapping/config drift split
- KT-02 policy race
- KT-05 fallback failure path
- KT-07 execution mismatch
- KT-08 provider-direct worker authority expansion
- KT-09 freeze enforcement
- KT-10 snapshot truth
- KT-11 strict sandbox escape probe
- KT-14 launch preflight integrity break

**Outputs:**

- executability and prerequisite notes embedded in `KILL_TESTS.md`

**Verification:**

- `KILL-03` is fully covered
- no kill test is left without a current-state executability judgment

## Risks And Controls

### Risk 1: invariants become vague slogans

**Control:** require each invariant to state a concrete required property, rationale, and break condition

### Risk 2: kill tests do not actually map to invariants

**Control:** require explicit invariant references on every kill test entry

### Risk 3: tests are designed without regard to current repo reality

**Control:** classify executability, state mutation, and credential requirements for every kill test

### Risk 4: Phase 5 drifts into running or remediating tests

**Control:** keep this phase focused on design/specification, not execution or fixes

## Deliverables

- `.planning/brownfield-audit/INVARIANTS.md`
- `.planning/brownfield-audit/KILL_TESTS.md`
- phase-local research and plan artifacts for Phase 5

## Exit Criteria

Phase 5 is complete when:

1. all required invariant families are defined
2. all 14 kill tests are designed
3. kill tests are mapped to invariants
4. executability is classified for each kill test
5. the outputs are strong enough for Phase 6 drift/risk analysis and later runtime execution work

## Verification Loop

Before closing the phase plan:

1. verify all `INV-*` requirements map to explicit invariant sections
2. verify all `KILL-*` requirements map to explicit kill-test sections
3. verify `KT-01..KT-14` all exist in the design
4. fail the plan if either artifact would remain a high-level outline without concrete procedures

## Notes

- `gsd-tools.cjs` remains unavailable in this environment because the local delegated runtime cannot load `pg`
- this Phase 5 plan was produced manually so execution can continue without waiting on the external GSD runtime
