# STATE.md

**Project:** BrokeLLM Brownfield Audit
**Current Phase:** Phase 6 (Drift Analysis & Failure Classification & Risk Register)
**Status:** Phase 6 executed manually; ready to plan Phase 7

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-04)

**Core value:** Evidence over declaration — every claimed capability must be traced to code, tests, and runtime behavior; unverifiable claims must be downgraded, proven claims validated, and gaps documented with structured remediation.
**Current focus:** Phase 7: Final Truth Adjudication & Remediation Plan

## Workflow Settings

- Mode: interactive
- Granularity: standard
- Parallelization: true
- Commit docs: true
- Model profile: quality
- Research: true
- Plan check: true
- Verifier: true
- Nyquist validation: true

## Phase Status

| Phase | Name | Status |
|-------|------|--------|
| 1 | Repo Discovery & Ground Truth Bootstrap | Complete |
| 2 | Claim Extraction & Feature Inventory | Complete |
| 3 | Truth Surfaces & Integration Matrix | Complete |
| 4 | Function Inventory & Test Review | Complete |
| 5 | Invariants Definition & Kill Test Design | Complete |
| 6 | Drift Analysis & Failure Classification & Risk Register | Complete |
| 7 | Final Truth Adjudication & Remediation Plan | Planned |
| 8 | Artifact Assembly & Summary | Planned |

## Next Action

Plan Phase 7: `gsd:plan-phase 7`

## Notes

- `gsd-tools.cjs` execution is currently broken locally because the installed runtime cannot load `pg`
- Phase 2 was executed manually from the approved local plan artifacts instead of through the automated GSD command path
- Phase 2 produced:
  - `.planning/brownfield-audit/CLAIMS.yaml`
  - `.planning/brownfield-audit/FEATURE_INVENTORY.yaml`
- Phase 3 produced:
  - `.planning/brownfield-audit/TRUTH.yaml`
  - `.planning/brownfield-audit/INTEGRATION_MATRIX.yaml`
- Phase 4 produced:
  - `.planning/brownfield-audit/FUNCTION_INVENTORY.md`
- Phase 5 produced:
  - `.planning/brownfield-audit/INVARIANTS.md`
  - `.planning/brownfield-audit/KILL_TESTS.md`
- Phase 6 produced:
  - `.planning/brownfield-audit/DRIFT_MAP.yaml`
  - `.planning/brownfield-audit/RISK_REGISTER.yaml`
