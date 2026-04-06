# Phase 7: Final Truth Adjudication & Remediation Plan - Plan

## Goal

Produce final `VALID | CONDITIONAL | INVALID` adjudication for every explicitly listed final truth domain, write those final judgments into `TRUTH.yaml`, and produce an ordered remediation plan grounded in the existing risk and invariant evidence.

## Requirement Coverage

This phase covers:

- `FINAL-01`
- `REM-01`
- `REM-02`

## Outputs

This phase must produce:

- updated `.planning/brownfield-audit/TRUTH.yaml` with final domain adjudication
- `.planning/brownfield-audit/REMEDIATION_PLAN.md`

## Domain Set

The requirement text says “18 truth domains” but explicitly lists 17. This phase will adjudicate the 17 listed domains and document that count mismatch rather than fabricating an extra domain.

Final truth domains to adjudicate:

1. `routing`
2. `fallback_resolution`
3. `observability`
4. `execution_alignment`
5. `key_orchestration`
6. `model_orchestration`
7. `harness_authority`
8. `credential_isolation`
9. `sandbox_runtime_boundary`
10. `supply_chain`
11. `install_bootstrap`
12. `snapshot_restore`
13. `freeze_enforcement`
14. `client_integrations`
15. `provider_integrations`
16. `truth_boundary_consistency`
17. `overall`

## Execution Strategy

### Task 1: Build final truth-domain adjudication

Update `TRUTH.yaml` so it contains a Phase 7 final adjudication section with:

- domain id/name
- final verdict
- rationale
- supporting evidence refs
- dependent provisional truth surfaces
- dominant risks

Adjudication rules:

- preserve `INVALID` where direct contradiction already exists
- preserve `CONDITIONAL` where proof gaps remain material
- only upgrade to `VALID` where evidence is strong and contradictions are absent

### Task 2: Build remediation plan

Create `REMEDIATION_PLAN.md` ordered by the required remediation buckets:

1. security-critical
2. authority-critical
3. truth-critical
4. runtime-critical
5. install/usability-critical
6. documentation-critical

Each remediation item must include:

- issue
- root cause
- required invariant
- enforcement surface
- change type needed

### Task 3: Cross-check consistency

Verify that:

- every final truth domain is supported by existing evidence
- every remediation item points back to a risk and invariant
- the final truth section does not silently contradict Phase 6 risk severity without explanation

## Verification Plan

Before execution is considered complete, verify:

1. `FINAL-01`, `REM-01`, and `REM-02` are all present in the plan
2. all 17 explicitly listed final domains are present
3. `TRUTH.yaml` contains final domain adjudication
4. `REMEDIATION_PLAN.md` exists and contains the required fields
5. Phase 8 work is explicitly guarded

## Risks

### Risk 1: upgrading weakly proven domains too aggressively

Mitigation:

- keep proof-gap-heavy domains `CONDITIONAL`
- reserve `VALID` for strong, contradiction-free evidence only

### Risk 2: collapsing remediation priorities into a flat issue list

Mitigation:

- enforce the required remediation ordering buckets
- tie ordering to the existing risk register

### Risk 3: silently masking the requirements count mismatch

Mitigation:

- document the 17-vs-18 inconsistency explicitly in both plan and execution artifact

## Exit Criteria

Phase 7 is complete when:

- `TRUTH.yaml` includes final domain adjudication for all 17 explicitly listed domains
- every final domain has rationale and evidence refs
- `REMEDIATION_PLAN.md` exists and is ordered by the required buckets
- each remediation item includes issue, root cause, required invariant, enforcement surface, and change type
- Phase 8 remains unconsumed

## Phase Boundary

Phase 7 does not:

- implement remediations
- rewrite the risk register
- assemble final artifact completeness verification
- produce the executive summary bundle

Those remain in Phase 8 or later follow-on work.

## Notes

- this plan is produced manually because the external GSD runtime remains broken locally
- the final adjudication must remain evidence-bound to Phases 3 through 6
