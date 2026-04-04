# STATE.md

**Project:** BrokeLLM Brownfield Audit
**Current Phase:** Phase 2 (Claim Extraction & Feature Inventory)
**Status:** Phase 2 executed manually; ready to plan Phase 3

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-04)

**Core value:** Evidence over declaration — every claimed capability must be traced to code, tests, and runtime behavior; unverifiable claims must be downgraded, proven claims validated, and gaps documented with structured remediation.
**Current focus:** Phase 3: Truth Surfaces & Integration Matrix

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
| 3 | Truth Surfaces & Integration Matrix | Planned |
| 4 | Function Inventory & Test Review | Planned |
| 5 | Invariants Definition & Kill Test Design | Planned |
| 6 | Drift Analysis & Failure Classification & Risk Register | Planned |
| 7 | Final Truth Adjudication & Remediation Plan | Planned |
| 8 | Artifact Assembly & Summary | Planned |

## Next Action

Plan Phase 3: `gsd:plan-phase 3`

## Notes

- `gsd-tools.cjs` execution is currently broken locally because the installed runtime cannot load `pg`
- Phase 2 was executed manually from the approved local plan artifacts instead of through the automated GSD command path
- Phase 2 produced:
  - `.planning/brownfield-audit/CLAIMS.yaml`
  - `.planning/brownfield-audit/FEATURE_INVENTORY.yaml`
