# Phase 6: Drift Analysis & Failure Classification & Risk Register - Plan

## Goal

Identify all required drift classes between declared and observed BrokeLLM behavior, classify every evidenced issue into the required failure taxonomy, and build the risk register without overreaching into final truth adjudication or remediation execution.

## Requirement Coverage

This phase covers:

- `DRIFT-01`
- `DRIFT-02`
- `DRIFT-03`
- `DRIFT-04`
- `DRIFT-05`
- `DRIFT-06`
- `DRIFT-07`
- `DRIFT-08`
- `DRIFT-09`
- `DRIFT-10`
- `FAIL-01`
- `RISK-01`

## Outputs

This phase must produce:

- `.planning/brownfield-audit/DRIFT_MAP.yaml`
- `.planning/brownfield-audit/RISK_REGISTER.yaml`

## Execution Strategy

Phase 6 should execute in three ordered tasks.

### Task 1: Build the drift map

Create `DRIFT_MAP.yaml` with all ten required drift classes:

1. README vs code drift
2. command surface vs implementation drift
3. test suite vs actual behavior drift
4. route/explain/doctor drift
5. policy truth vs request behavior drift
6. harness doctrine vs enforcement drift
7. sandbox claim vs actual isolation drift
8. install docs vs reality drift
9. client compatibility claim vs real path drift
10. provider support claim vs actual maintained integration drift

For each drift class, record:

- requirement ref
- status
- issues
- declared surface
- observed surface
- evidence refs
- severity
- exploitability
- user impact
- failure classes
- recommended fix direction

### Task 2: Normalize failure classification

For every issue in the drift map, assign one or more failure classes from the required taxonomy.

Minimum expectation:

- every confirmed drift gets at least one failure class
- every proof gap that materially downgrades trust gets `TEST_COVERAGE_GAP` or a more specific class where supported
- categories must remain evidence-bound, not speculative

### Task 3: Build the risk register

Create `RISK_REGISTER.yaml` that consolidates the issues into a durable risk ledger.

Each risk entry should include:

- risk id
- title
- source drift refs
- evidence refs
- severity
- exploitability
- user impact
- affected truth surfaces
- implicated invariants
- failure classes
- current confidence
- recommended next-phase handling

## Verification Plan

Before execution is considered complete, verify:

1. `DRIFT-01..10` all appear explicitly in the plan or produced drift map
2. `FAIL-01` is satisfied by explicit use of the required taxonomy
3. `RISK-01` is satisfied by a concrete risk register schema
4. both required output files exist and are non-empty
5. Phase 7 work is explicitly guarded

## Risks

### Risk 1: inventing drift without evidence

Mitigation:

- only use issues already evidenced in claims, truth, function, integration, and kill-test artifacts
- label missing runtime proof as proof gaps, not confirmed failures

### Risk 2: collapsing distinct drifts into one generic bucket

Mitigation:

- preserve requirement-by-requirement drift classes
- allow one issue to appear in multiple classes when the evidence supports it

### Risk 3: drifting into final adjudication

Mitigation:

- keep classifications at drift/risk level
- reserve final `VALID | CONDITIONAL | INVALID` domain adjudication for Phase 7

## Exit Criteria

Phase 6 is complete when:

- `DRIFT_MAP.yaml` exists and covers all `DRIFT-01..10`
- every identified issue has one or more failure classes
- `RISK_REGISTER.yaml` exists and includes all identified material issues
- the artifacts clearly distinguish confirmed drifts from proof gaps
- later-phase work is not preempted

## Phase Boundary

Phase 6 does not:

- execute remediation
- revise final truth verdicts
- run the deferred kill-test suite
- assemble the final summary bundle

Those remain in Phases 7 and 8.

## Notes

- this plan is produced manually because the local external GSD runtime remains unavailable
- Phase 6 should treat earlier artifacts as authoritative inputs unless a concrete inconsistency is discovered during synthesis
