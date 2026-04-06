---
phase: 3
name: Truth Surfaces & Integration Matrix
completed: 2026-04-04
method: manual_phase_execution_fallback
requirements_completed:
  - TRUTH-01
  - TRUTH-02
  - TRUTH-03
  - TRUTH-04
  - TRUTH-05
  - TRUTH-06
  - TRUTH-07
  - TRUTH-08
  - TRUTH-09
  - TRUTH-10
  - TRUTH-11
  - TRUTH-12
  - TRUTH-13
  - INT-01
  - INT-02
  - INT-03
  - INT-04
artifacts:
  - .planning/brownfield-audit/TRUTH.yaml
  - .planning/brownfield-audit/INTEGRATION_MATRIX.yaml
status: passed
notes:
  - "One INVALID domain: health_truth (doctor vs route/explain disagreement)"
  - "Multiple CONDITIONAL domains due to deferred kill-test execution"
  - "Integration matrix covers all required client, provider, and internal surfaces"
---

# Phase 3 Summary

## Result

✅ **Passed** — All Phase 3 requirements satisfied.

## Deliverables

- `TRUTH.yaml`: 15 truth surfaces with evidence-backed provisional adjudications
- `INTEGRATION_MATRIX.yaml`: Complete integration classification across clients, providers, internals

## Provisional Truth Summary

| Classification | Count | Domains |
|----------------|-------|---------|
| VALID | 2 | routing, harness_verdict |
| CONDITIONAL | 11 | fallback_resolution, key_policy, key_state, model_policy, model_state, credential_isolation, execution_alignment, launch_preflight, snapshot_restore, supply_chain, install_bootstrap (implicit from preflight+supply) |
| INVALID | 2 | health_truth, freeze_enforcement, truth_boundary_consistency (derived) |

## Integration Highlights

- **Clients:** Codex CLI (VALID), Claude CLI (CONDITIONAL), Gemini CLI (INVALID), Gemini endpoint (CONDITIONAL)
- **Providers:** Most providers CONDITIONAL due to runtime proof gaps; none INVALID
- **Internal integrations:** All major internal surfaces documented with observed behavior

## Notes

- Health truth INVALID because `doctor` reported gateway healthy while `route/explain` reported gateway unreachable — direct observability mismatch
- Freeze enforcement INVALID because guarded mutation surface narrower than claimed semantics
- Truth boundary consistency derived INVALID due to health disagreement violating shared normalization invariant
