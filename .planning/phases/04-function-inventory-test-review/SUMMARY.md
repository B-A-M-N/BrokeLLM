---
phase: 4
name: Function Inventory & Test Review
completed: 2026-04-04
method: manual_phase_execution_fallback
requirements_completed:
  - FUNC-01
  - FUNC-02
  - TEST-01
  - TEST-02
  - TEST-03
artifacts:
  - .planning/brownfield-audit/FUNCTION_INVENTORY.md
status: passed
notes:
  - "Test coverage judged mostly nominal; adversarial kill tests deferred to Phase 5"
  - "Mock usage documented as risk-hiding in proxy forwarding and health normalization"
---

# Phase 4 Summary

## Result

✅ **Passed** — All Phase 4 requirements satisfied.

## Deliverables

- `FUNCTION_INVENTORY.md`: Complete function-family trace across 12 families with inputs, state mutation, invariants, truth role, fail-open/closed, test coverage, bypassability, and notable gaps

## Domain Coverage Judgments

| Domain | Coverage Rating | Notes |
|--------|----------------|-------|
| Routing | moderate | route/explain agreement evidenced; execution alignment forward-path partially proven |
| Policy | moderate | key/model policy persistence visible; concurrent isolation deferred |
| Harness | moderate | verdict and ledger mechanics traced; broad BLOCK/RETRY/ESCALATE coverage partial |
| Security | weak | authority expansion denial present; env-leak probing deferred |
| Sandbox | weak | strict-mode hardening present; escape probing deferred |
| Execution Alignment | partial | proxy forwarding traced; actual upstream target alignment not runtime-proven |
| Install/Bootstrap | moderate | preflight checks present; lockfile drift observed |
| Snapshot/Freeze | moderate | snapshot save/restore implemented; scope narrower than expectations |
| Client | partial | Codex CLI valid; Claude conditional; Gemini invalid |
| Provider | partial | provider catalog broad; live maintained proof varies |

## Test Strategy Assessment

- **Current test suite:** Single file `tests/test_mapping.py` with broad but shallow coverage
- **Strengths:** dry-run surfaces, swap/fallback, policy & state, harness verdict, proxy auth, install regression, snapshot round-trip
- **Weaknesses:** mostly nominal tests, heavy mock usage in forward-path tests, no adversarial kill tests, no credential-leak or sandbox-escape probes

## Notes

- Phase 4 intentionally avoided invariant design (belongs to Phase 5)
- Gaps identified here feed directly into Phase 5 kill-test design and Phase 6 drift classification
