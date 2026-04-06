# Phase 7: Final Truth Adjudication & Remediation Plan - Research

## Research Question

What must be understood to plan Phase 7 well?

Phase 7 is where the audit stops producing provisional component findings and turns them into final domain judgments with an ordered remediation program. It should not rediscover the system or rerun the audit. It should synthesize the existing evidence into:

- final truth-domain adjudications
- rationale with evidence references
- remediation ordering and enforcement surfaces

## Inputs This Phase Depends On

Phase 7 stands on:

- `.planning/brownfield-audit/TRUTH.yaml`
- `.planning/brownfield-audit/INTEGRATION_MATRIX.yaml`
- `.planning/brownfield-audit/FUNCTION_INVENTORY.md`
- `.planning/brownfield-audit/INVARIANTS.md`
- `.planning/brownfield-audit/KILL_TESTS.md`
- `.planning/brownfield-audit/DRIFT_MAP.yaml`
- `.planning/brownfield-audit/RISK_REGISTER.yaml`

These are sufficient to adjudicate final truth domains if the phase is careful about aggregation.

## Important Requirement Inconsistency

`FINAL-01` says “all 18 truth domains,” but the requirement text and roadmap enumerate only 17:

1. routing
2. fallback_resolution
3. observability
4. execution_alignment
5. key_orchestration
6. model_orchestration
7. harness_authority
8. credential_isolation
9. sandbox_runtime_boundary
10. supply_chain
11. install_bootstrap
12. snapshot_restore
13. freeze_enforcement
14. client_integrations
15. provider_integrations
16. truth_boundary_consistency
17. overall

Phase 7 should preserve the explicitly enumerated list rather than inventing an 18th domain silently. The inconsistency should be noted in the artifact.

## How Final Domain Adjudication Should Work

Phase 7 should not copy the Phase 3 provisional truth surfaces directly. It should aggregate them into the Phase 7 domain list.

Recommended aggregation:

- `routing` ← `routing_truth`
- `fallback_resolution` ← `fallback_resolution_truth`
- `observability` ← `health_truth` plus doctor/route/explain consistency evidence
- `execution_alignment` ← `execution_alignment_truth`
- `key_orchestration` ← `key_policy_truth` + `key_state_truth`
- `model_orchestration` ← `model_policy_truth` + `model_state_truth`
- `harness_authority` ← `harness_verdict_truth` + authority-expansion evidence
- `credential_isolation` ← `credential_isolation_truth`
- `sandbox_runtime_boundary` ← `sandbox_runtime_boundary_truth`
- `supply_chain` ← `supply_chain_truth`
- `install_bootstrap` ← `launch_preflight_integrity_truth` + supply-chain/install posture
- `snapshot_restore` ← `snapshot_restore_truth`
- `freeze_enforcement` ← `freeze_enforcement_truth`
- `client_integrations` ← client section of `INTEGRATION_MATRIX.yaml`
- `provider_integrations` ← provider section of `INTEGRATION_MATRIX.yaml`
- `truth_boundary_consistency` ← route/doctor/explain and other shared-normalization evidence
- `overall` ← aggregate of domain severity and invalidity burden

## Expected Final Judgments From Existing Evidence

Phase 7 should not pre-commit blindly, but current evidence strongly suggests:

- `routing` can remain `VALID`
- `health_truth` already forces at least `observability` or `truth_boundary_consistency` to `INVALID`
- `freeze_enforcement` should remain `INVALID`
- many security/harness/execution domains should remain `CONDITIONAL` because proof is partial rather than absent-by-design

The key distinction:

- confirmed contradiction → `INVALID`
- meaningful but incomplete proof → `CONDITIONAL`
- strong, consistent, evidenced behavior → `VALID`

## Remediation Plan Requirements

Remediation must be ordered by:

1. security-critical
2. authority-critical
3. truth-critical
4. runtime-critical
5. install/usability-critical
6. documentation-critical

Each item must include:

- issue
- root cause
- required invariant
- enforcement surface
- change type needed

This means remediation items should map directly to:

- risks
- invalid or conditional domain judgments
- implicated invariants

## What Phase 7 Should Not Do

Phase 7 should not:

- implement fixes
- rerun deferred kill tests
- assemble the final summary bundle
- change earlier evidence artifacts except to write final truth values into `TRUTH.yaml`

Those belong to later execution or assembly work.

## Planning Implication

A good Phase 7 plan must prove:

1. `FINAL-01`, `REM-01`, and `REM-02` are all explicitly covered
2. the domain-aggregation method is defined
3. the 17-vs-18 domain-count inconsistency is recorded
4. remediation ordering follows the required severity grouping
5. Phase 8 artifact assembly work is explicitly guarded
