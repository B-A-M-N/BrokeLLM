# Phase 8: Artifact Assembly & Summary - Research

## Research Question

What must be understood to plan Phase 8 well?

Phase 8 is not a new discovery phase. It is the audit assembly and completeness phase. Its job is to normalize the final deliverable set, verify internal consistency, and produce the audit summary without changing the meaning of prior evidence.

## Existing Deliverable State

Before Phase 8, the brownfield audit directory already contains:

- `TRUTH.yaml`
- `_SYSTEM_SURFACE_MAP.md`
- `FEATURE_INVENTORY.yaml`
- `FUNCTION_INVENTORY.md`
- `INTEGRATION_MATRIX.yaml`
- `INVARIANTS.md`
- `KILL_TESTS.md`
- `DRIFT_MAP.yaml`
- `RISK_REGISTER.yaml`
- `REMEDIATION_PLAN.md`
- `CLAIMS.yaml`

Required missing or mismatched items are:

- `SYSTEM_SURFACE_MAP.md`
  - required name is missing
  - only `_SYSTEM_SURFACE_MAP.md` currently exists
- `VERIFICATION.md`
- `SUMMARY.md`

## Phase 8 Responsibilities

Phase 8 must:

1. normalize the deliverable name mismatch
2. create verification output proving the deliverable set is complete and internally consistent
3. create the executive audit summary

It should not reopen domain adjudication or rewrite prior findings unless a material inconsistency is discovered during assembly.

## Important Assembly Constraint

The required artifact list in `REQUIREMENTS.md` is the source of truth for completeness. Phase 8 should verify against:

- `ART-01` through `ART-12`

That means the directory must end with these named files:

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

## How Verification Should Work

Phase 8 verification should prove:

1. all required files exist
2. each file is non-empty
3. final adjudication exists in `TRUTH.yaml`
4. remediation ordering exists in `REMEDIATION_PLAN.md`
5. drift and risk artifacts exist
6. the surface map naming is normalized

## Summary Expectations

`SUMMARY.md` should be concise and decision-oriented. It should include:

- overall audit result
- strongest `VALID` areas
- strongest `INVALID` areas
- most consequential `CONDITIONAL` areas
- top remediation priorities

## Planning Implication

A good Phase 8 plan must prove:

1. all `ART-01..12` are covered
2. the naming mismatch for `SYSTEM_SURFACE_MAP.md` is resolved explicitly
3. the verification artifact has a concrete completeness checklist
4. the summary artifact is based on final truth and risk artifacts, not fresh discovery
