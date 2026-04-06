# Phase 8: Artifact Assembly & Summary - Plan

## Goal

Assemble the final brownfield audit deliverable set under `.planning/brownfield-audit/`, normalize the remaining artifact naming mismatch, produce an explicit completeness verification artifact, and write the executive audit summary.

## Requirement Coverage

This phase covers:

- `ART-01`
- `ART-02`
- `ART-03`
- `ART-04`
- `ART-05`
- `ART-06`
- `ART-07`
- `ART-08`
- `ART-09`
- `ART-10`
- `ART-11`
- `ART-12`

## Outputs

This phase must ensure the final directory contains:

- `TRUTH.yaml`
- `SYSTEM_SURFACE_MAP.md`
- `FEATURE_INVENTORY.yaml`
- `FUNCTION_INVENTORY.md`
- `INTEGRATION_MATRIX.yaml`
- `INVARIANTS.md`
- `KILL_TESTS.md`
- `VERIFICATION.md`
- `DRIFT_MAP.yaml`
- `RISK_REGISTER.yaml`
- `REMEDIATION_PLAN.md`
- `SUMMARY.md`

## Execution Strategy

### Task 1: Normalize the system surface map deliverable

Create `SYSTEM_SURFACE_MAP.md` from the existing draft surface map content, preserving the relevant command, runtime, integration, and trust-surface documentation while removing the underscore-prefixed draft-only framing.

### Task 2: Produce verification artifact

Create `VERIFICATION.md` that:

- checks all `ART-01..12`
- confirms file existence and non-empty status
- confirms final adjudication is present in `TRUTH.yaml`
- confirms remediation output exists
- records any remaining known limitations

### Task 3: Produce executive summary

Create `SUMMARY.md` that summarizes:

- overall audit result
- strongest valid domains
- invalid domains
- highest-risk conditional domains
- top remediation priorities

## Verification Plan

Before execution is considered complete, verify:

1. all `ART-01..12` are present in the plan
2. all 12 required deliverable filenames exist under `.planning/brownfield-audit/`
3. each required file is non-empty
4. `VERIFICATION.md` contains an explicit completeness check
5. `SUMMARY.md` reflects Phase 7 final adjudication rather than provisional Phase 3-only state

## Risks

### Risk 1: treating `_SYSTEM_SURFACE_MAP.md` as good enough without normalizing the required artifact name

Mitigation:

- produce the required `SYSTEM_SURFACE_MAP.md` explicitly

### Risk 2: verification that only checks filenames but not artifact substance

Mitigation:

- require final-truth and remediation presence checks, not just file existence

### Risk 3: summary drifting from final adjudication

Mitigation:

- derive summary directly from final domain verdicts and risk register

## Exit Criteria

Phase 8 is complete when:

- all 12 required deliverables exist under `.planning/brownfield-audit/`
- all 12 required deliverables are non-empty
- `VERIFICATION.md` confirms completeness and known limits
- `SUMMARY.md` reflects the final audit result

## Phase Boundary

Phase 8 does not:

- implement remediations
- rerun deferred runtime kill tests
- revise completed earlier-phase artifacts except for deliverable normalization

## Notes

- this plan is produced manually because the external GSD runtime remains broken locally
- `_SYSTEM_SURFACE_MAP.md` should be treated as the upstream draft source for the required final `SYSTEM_SURFACE_MAP.md`
