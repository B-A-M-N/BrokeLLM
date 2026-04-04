# Phase 4: Function Inventory & Test Review - Plan

**Phase:** 4  
**Name:** Function Inventory & Test Review  
**Goal:** Trace every meaningful function family to determine inputs, state mutations, invariants, fail-closed behavior, test coverage, and bypassability. Audit repository test strategy for nominal vs adversarial coverage.

## Phase Requirements

- FUNC-01
- FUNC-02
- TEST-01
- TEST-02
- TEST-03

## Success Criteria

1. All major function families are traced with inputs consumed, state mutated, invariants assumed, source-of-truth vs consumer-only role, fail open/closed posture, test coverage, and bypassability
2. `FUNCTION_INVENTORY.md` is complete
3. Repository test strategy is audited for nominal vs adversarial coverage
4. Mock usage is evaluated for whether it hides real risk
5. Test coverage judgment is produced for each major domain: routing, policy, harness, security, sandbox, execution alignment, install/bootstrap, snapshot/freeze, client, provider

## Execution Strategy

Phase 4 should execute as an implementation-traceability phase.

It should reuse:

- prior truth and feature artifacts
- the surfaced function-family list from requirements
- the existing test suite as the primary evidence base for coverage claims

It should avoid:

- full invariant design from Phase 5
- final risk/remediation ranking from later phases
- pretending mocked coverage is equivalent to live runtime proof

## Planning Assumption

The output for this phase should be one consolidated artifact:

- `FUNCTION_INVENTORY.md`

That artifact should include both:

- function family records
- the test strategy review and domain coverage judgment

This keeps `FUNC-*` and `TEST-*` evidence tied together rather than split across disconnected notes.

## Plan

### Plan 4.1 — Define Function Family Inventory Schema

**Objective:** Establish the structure for each function-family record before tracing implementation details.

**Inputs:**

- `.planning/ROADMAP.md`
- `.planning/REQUIREMENTS.md`
- `.planning/brownfield-audit/TRUTH.yaml`
- `.planning/brownfield-audit/FEATURE_INVENTORY.yaml`

**Tasks:**

1. define the record schema for a function family
2. map the requirement-listed families into a practical grouping for this repo
3. decide which file/function clusters own each family

**Outputs:**

- section skeleton for `FUNCTION_INVENTORY.md`

**Verification:**

- all `FUNC-01` family categories are represented
- each family schema has fields for inputs, mutation, invariants, fail-open/closed, test coverage, and bypassability

### Plan 4.2 — Trace Core Function Families

**Objective:** Populate the function family inventory from the actual code paths.

**Primary file groups:**

- `bin/broke`
- `bin/_mapping.py`
- `bin/_proxy.py`
- `bin/_harness_shim.py`
- `bin/_harness_common.py`
- `bin/_socket_bridge.py`
- `bin/_fs_common.py`
- `install.sh`

**Tasks:**

1. trace command dispatch and gateway lifecycle families
2. trace mapping, fallback, route, explain, doctor, validate, and preflight families
3. trace policy/state persistence families
4. trace proxy auth, candidate selection, and forwarding families
5. trace harness orchestration, verdict, ledger, and checkpoint families
6. trace sandbox, secret injection, env scrubbing, and install/bootstrap families

**Outputs:**

- populated function family sections in `FUNCTION_INVENTORY.md`

**Verification:**

- each family states whether it is a source-of-truth owner or consumer
- each family states fail-open/fail-closed posture where meaningful
- bypassability is addressed explicitly, not omitted

### Plan 4.3 — Audit Test Strategy Against Families And Domains

**Objective:** Determine what the repository tests actually prove, and what they do not.

**Inputs:**

- `tests/test_mapping.py`
- function family inventory from Plan 4.2
- prior truth and integration artifacts

**Tasks:**

1. map tests to function families
2. classify coverage as:
   - nominal
   - adversarial
   - untested
3. identify core claims and domains with no meaningful coverage
4. evaluate mock/fake usage for hidden risk
5. produce domain-level judgments for:
   - routing
   - policy
   - harness
   - security
   - sandbox
   - execution alignment
   - install/bootstrap
   - snapshot/freeze
   - client
   - provider

**Outputs:**

- test strategy review section in `FUNCTION_INVENTORY.md`

**Verification:**

- all `TEST-01`, `TEST-02`, and `TEST-03` requirements are covered
- domain coverage judgments are conservative and evidence-backed

### Plan 4.4 — Record Gaps For Phase 5

**Objective:** Capture the unresolved family-level and testing gaps that should feed invariants and kill-test design.

**Tasks:**

1. identify families with unclear invariants or ambiguous fail-open/fail-closed behavior
2. identify families whose behavior is only mock-tested
3. identify bypassable or weakly enforced areas
4. append explicit handoff notes for Phase 5

**Priority areas:**

- health normalization
- proxy forwarding
- execution alignment
- freeze enforcement
- snapshot scope
- credential isolation
- sandbox mediation

**Outputs:**

- gap and handoff section in `FUNCTION_INVENTORY.md`

**Verification:**

- major unresolved gaps from Phase 3 are connected to concrete function families

## Risks And Controls

### Risk 1: family grouping becomes too fine-grained and unreadable

**Control:** group by meaningful runtime responsibility, not by every helper function

### Risk 2: test coverage is overstated because mocks exist

**Control:** distinguish nominal mock-backed coverage from adversarial or runtime-backed proof

### Risk 3: fail-open/fail-closed judgment becomes speculative

**Control:** only state a posture where code path and observed behavior support it; otherwise mark as mixed or unclear

### Risk 4: Phase 4 duplicates Phase 3 truth work without deepening it

**Control:** keep this artifact anchored on function families and tests, not just truth-surface summaries

## Deliverables

- `.planning/brownfield-audit/FUNCTION_INVENTORY.md`
- phase-local research and plan artifacts for Phase 4

## Exit Criteria

Phase 4 is complete when:

1. the major function families are all represented in `FUNCTION_INVENTORY.md`
2. each family includes inputs, mutation, invariants, truth role, fail-open/closed notes, test coverage, and bypassability
3. the repository test strategy is audited by family and by domain
4. mock-risk and uncovered-claim gaps are explicitly recorded for later phases

## Verification Loop

Before closing the phase plan:

1. verify `FUNC-01` families are all represented
2. verify `FUNC-02` required fields appear in every family record template
3. verify `TEST-01..03` are all covered by explicit plan items
4. fail the plan if `FUNCTION_INVENTORY.md` would only be a file list without behavioral classification

## Notes

- `gsd-tools.cjs` remains unavailable in this environment because the local delegated runtime cannot load `pg`
- this Phase 4 plan was produced manually so execution can continue without waiting on the external GSD runtime
