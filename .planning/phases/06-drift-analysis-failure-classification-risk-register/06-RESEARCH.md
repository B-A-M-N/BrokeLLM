# Phase 6: Drift Analysis & Failure Classification & Risk Register - Research

## Research Question

What must be understood to plan Phase 6 well?

Phase 6 should convert the prior audit artifacts into a disciplined drift and risk view. It should not reopen discovery from scratch. The important constraint is that this phase must remain evidence-bound: drift and risk must be derived from already traced claims, truth surfaces, function families, integrations, invariants, kill tests, and observed runtime behavior.

## Prior Artifacts This Phase Depends On

Phase 6 stands on:

- `.planning/brownfield-audit/CLAIMS.yaml`
- `.planning/brownfield-audit/FEATURE_INVENTORY.yaml`
- `.planning/brownfield-audit/TRUTH.yaml`
- `.planning/brownfield-audit/INTEGRATION_MATRIX.yaml`
- `.planning/brownfield-audit/FUNCTION_INVENTORY.md`
- `.planning/brownfield-audit/INVARIANTS.md`
- `.planning/brownfield-audit/KILL_TESTS.md`

These already contain the evidence base for most Phase 6 outputs:

- declared vs implemented claims
- provisional truth classifications
- known invalid and conditional surfaces
- documented function-family gaps
- explicit invariant violations and kill-test coverage gaps

## What Counts As Drift In This Audit

For this repo, drift is not just stale documentation. Drift includes:

1. declared behavior vs implemented behavior
2. declared behavior vs observed runtime behavior
3. one control-plane surface vs another control-plane surface
4. test coverage posture vs actual claimed confidence
5. compatibility/support claims vs fresh runtime proof depth

That means Phase 6 must reconcile at least five evidence planes:

- docs and claim surfaces
- code paths
- runtime observations
- tests
- invariant / kill-test posture

## Drift Inputs Already Evidenced

The strongest existing evidence inputs are:

### A. Confirmed health-surface disagreement

Phase 3 established:

- `broke doctor` reported gateway live and selected upstreams healthy
- `broke route sonnet` and `broke explain sonnet` both reported `health: gateway not reachable`

This is already a confirmed drift, not a hypothetical one.

### B. Freeze semantics overclaim

Phase 3 and Phase 4 established:

- freeze enforcement is invalid as a broad truth surface
- only a subset of mutation commands are actually guarded

This is both a state-control drift and a command-surface drift.

### C. Snapshot scope overclaim

Phase 3 and Phase 4 established:

- snapshot/restore exists
- snapshot scope is mapping-only, not full control-plane state

This is a persistence-truth and documentation/expectation drift.

### D. Execution alignment remains only partially proven

Phase 3 and Phase 4 established:

- route/explain dry-run surfaces align
- actual forwarded target alignment is only partially proven

This is an execution-proof gap and potential execution-divergence risk.

### E. Policy generation isolation remains unproven

Phase 3 and Phase 5 established:

- model/key policy persistence and generation tracking exist
- concurrent generation isolation has not been runtime-proven

This is a drift risk between control-plane policy truth and request-time behavior.

### F. Credential isolation and sandbox posture are only partially proven

Phase 3, Phase 4, and Phase 5 established:

- authority expansion denial is implemented
- lane design exists
- strict sandbox has been materially hardened
- direct env-leak and escape probes remain deferred

These are evidence-backed proof gaps, not yet confirmed failures.

### G. Supply-chain lock intent vs live environment drift

Phase 3 established:

- lockfile/hash-bound install design exists
- runtime package drift and unexpected `.pth` files were observed in doctor

This is a concrete install/runtime alignment issue.

### H. Test posture remains mostly nominal/mock-backed

Phase 4 established:

- test coverage is meaningful in places
- but the suite is still mostly nominal and mock-backed
- several high-risk claims still lack adversarial/runtime proof

This must be treated as a first-class risk input, not just a testing footnote.

## Required Phase 6 Outputs

This phase must produce:

- `DRIFT_MAP.yaml`
- `RISK_REGISTER.yaml`

Those outputs must cover:

- `DRIFT-01` through `DRIFT-10`
- `FAIL-01`
- `RISK-01`

## Recommended Phase 6 Structure

Phase 6 should execute in three passes:

### Pass 1: Drift-class assembly

Build the ten required drift classes from already-evidenced issues and proof gaps.

### Pass 2: Failure classification

For each drift issue, assign one or more failure categories from the required failure taxonomy:

- `BOUNDARY_VIOLATION`
- `STATE_DRIFT`
- `AUTHORITY_LEAK`
- `OBSERVABILITY_MISMATCH`
- `EXECUTION_DIVERGENCE`
- `SECURITY_ISOLATION_FAILURE`
- `SANDBOX_ENFORCEMENT_FAILURE`
- `SUPPLY_CHAIN_GAP`
- `INSTALL_BOOTSTRAP_GAP`
- `INTEGRATION_OVERCLAIM`
- `TEST_COVERAGE_GAP`
- `PERSISTENCE_TRUTH_GAP`
- `DOC_TRUTH_GAP`

### Pass 3: Risk normalization

Translate those issues into a durable risk register with:

- issue id
- evidence refs
- severity
- exploitability
- user impact
- likely invariant(s) implicated
- likely remediation direction

## What Phase 6 Should Not Do

Phase 6 should not:

- execute the full kill-test suite
- remediate issues
- perform final truth adjudication
- rewrite prior evidence artifacts unless a concrete inconsistency is found

Those belong to later phases.

## Planning Implication

Phase 6 is an evidence-synthesis and risk-structuring phase. The plan should explicitly prove:

1. all ten drift requirements are covered
2. failure taxonomy coverage is explicit
3. the risk register is grounded only in already documented evidence
4. final adjudication and remediation remain reserved for Phases 7 and 8
