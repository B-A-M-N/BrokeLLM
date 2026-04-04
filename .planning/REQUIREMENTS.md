# Requirements: BrokeLLM Brownfield Audit

**Defined:** 2026-04-04
**Core Value:** Evidence over declaration — every claimed capability must be traced to code, tests, and runtime behavior; unverifiable claims must be downgraded, proven claims validated, and gaps documented with structured remediation

## v1 Requirements

### Discovery & Ground Truth

- [ ] **DISC-01**: Discover and map all major executable entrypoints, CLI commands, and configuration files
- [ ] **DISC-02**: Identify all main executable and control-plane boundaries
- [ ] **DISC-03**: Map all runtime mutation and authority expansion surfaces
- [ ] **DISC-04**: Identify all persistence surfaces and trust boundaries
- [ ] **DISC-05**: Enumerate CLI command surfaces across all domains (gateway, routing, team, profile, observability, key/model policy, sandbox, harness, snapshot, freeze, provider)
- [ ] **DISC-06**: Enumerate runtime control surfaces (routing, deployments, health, key, model, freeze, snapshot, harness, launch audit, tokens, config generation, env sanitation)
- [ ] **DISC-07**: Enumerate integration surfaces (LiteLLM, providers, Claude, Codex, Gemini, local proxy, internal upstream auth, bwrap/sandbox, wheel mirror, install/bootstrap)

### Claim Extraction

- [ ] **CLAIM-01**: Extract all declared capability claims from repo docs (project purpose, client support, routing, harness, security, supply chain, truth boundaries)
- [ ] **CLAIM-02**: Classify each claim by domain and expected proof type
- [ ] **CLAIM-03**: Separate declared vs implemented vs verified vs adversarially verified capability for each claim

### Truth Surface Adjudication

- [ ] **TRUTH-01**: Adjudicate routing truth surface (source of truth, readers, writers, drift risks, evidence)
- [ ] **TRUTH-02**: Adjudicate health truth surface
- [ ] **TRUTH-03**: Adjudicate key policy and key state truth surfaces
- [ ] **TRUTH-04**: Adjudicate model policy and model state truth surfaces
- [ ] **TRUTH-05**: Adjudicate fallback resolution truth surface
- [ ] **TRUTH-06**: Adjudicate harness verdict truth surface
- [ ] **TRUTH-07**: Adjudicate credential isolation truth surface
- [ ] **TRUTH-08**: Adjudicate sandbox/runtime boundary truth surface
- [ ] **TRUTH-09**: Adjudicate execution alignment truth surface
- [ ] **TRUTH-10**: Adjudicate launch preflight integrity truth surface
- [ ] **TRUTH-11**: Adjudicate snapshot/restore truth surface
- [ ] **TRUTH-12**: Adjudicate freeze enforcement truth surface
- [ ] **TRUTH-13**: Adjudicate supply-chain truth surface

### Feature Inventory

- [ ] **FEAT-01**: Complete feature inventory for all 12 feature families (routing, observability, execution layer, live key orchestration, live model orchestration, harness mode, security model, sandbox profiles, supply chain, state controls, installation/bootstrap, compatibility/integration claims)
- [ ] **FEAT-02**: For each feature: declared behavior, implementation locations, test locations, runtime entrypoints, dependencies, verification status

### Function Inventory

- [ ] **FUNC-01**: Trace all meaningful function families (command dispatch, mapping resolution, fallback selection, health normalization, route explanation, doctor aggregation, validation, launch preflight, client launch, env scrubbing, secret injection, auth enforcement, proxy forwarding, LiteLLM bridging, key/model policy resolution, harness orchestration, verdict handling, ledger append, checkpoint, snapshot, freeze, persistence helpers, sandbox setup, audit logging, install/bootstrap)
- [ ] **FUNC-02**: For each function family: inputs, state mutated, invariants, source-of-truth vs consumer, fail open/closed, test coverage, bypassability

### Integration Matrix

- [ ] **INT-01**: Document all client integrations (Claude, Codex, Gemini CLI, Gemini endpoint)
- [ ] **INT-02**: Document all provider integrations (OpenRouter, Groq, Cerebras, GitHub Models, Gemini, Hugging Face)
- [ ] **INT-03**: Document all internal integrations (proxy to LiteLLM, harness launcher, preflight, sandbox, policy store, health state, teams/profiles, snapshots, freeze)
- [ ] **INT-04**: For each integration: classification (VALID/CONDITIONAL/INVALID), failure modes, observed behavior

### Kill Tests Design

- [ ] **KILL-01**: Define all 14 kill tests (KT-01 through KT-14) with concrete adversarial procedures
- [ ] **KILL-02**: Map kill tests to required invariants they verify
- [ ] **KILL-03**: Classify which kill tests are executable in current repo state

### Invariants Definition

- [ ] **INV-01**: Define all routing invariants (route=explain, proxy target match, fallback ordering, pinned routes, floating alias drift)
- [ ] **INV-02**: Define all truth-boundary invariants (doctor/route/explain shared source, disagreement detection)
- [ ] **INV-03**: Define all policy invariants (generation isolation, state transitions, cooldown enforcement)
- [ ] **INV-04**: Define all harness invariants (BLOCK/RETRY/ESCALATE semantics, elevation gating, credential separation)
- [ ] **INV-05**: Define all security invariants (no global env export, no secret leakage, fail-closed unknown model, rate limiting, scoped injection)
- [ ] **INV-06**: Define all sandbox invariants (strict filesystem narrowing, network posture, local bridge, blocked clients)
- [ ] **INV-07**: Define all supply-chain invariants (hash-bound, offline mode, wheel mirror)
- [ ] **INV-08**: Define all state invariants (freeze block, snapshot restore correctness, team/profile persistence)
- [ ] **INV-09**: Define all install/bootstrap invariants (runnable system, prerequisite check, default state coherence)

### Drift Analysis

- [ ] **DRIFT-01**: Identify README vs code drift
- [ ] **DRIFT-02**: Identify command surface vs implementation drift
- [ ] **DRIFT-03**: Identify test suite vs actual behavior drift
- [ ] **DRIFT-04**: Identify route/explain/doctor drift
- [ ] **DRIFT-05**: Identify policy truth vs request behavior drift
- [ ] **DRIFT-06**: Identify harness doctrine vs enforcement drift
- [ ] **DRIFT-07**: Identify sandbox claim vs actual isolation drift
- [ ] **DRIFT-08**: Identify install docs vs reality drift
- [ ] **DRIFT-09**: Identify client compatibility claim vs real path drift
- [ ] **DRIFT-10**: Identify provider support claim vs actual maintained integration drift

### Failure Classification & Risk Register

- [ ] **FAIL-01**: Classify every identified issue into one or more categories (BOUNDARY_VIOLATION, STATE_DRIFT, AUTHORITY_LEAK, OBSERVABILITY_MISMATCH, EXECUTION_DIVERGENCE, SECURITY_ISOLATION_FAILURE, SANDBOX_ENFORCEMENT_FAILURE, SUPPLY_CHAIN_GAP, INSTALL_BOOTSTRAP_GAP, INTEGRATION_OVERCLAIM, TEST_COVERAGE_GAP, PERSISTENCE_TRUTH_GAP, DOC_TRUTH_GAP)
- [ ] **RISK-01**: Build risk register with all identified issues, severity, and user impact

### Final Truth Adjudication

- [ ] **FINAL-01**: Adjudicate all 18 truth domains (routing, fallback_resolution, observability, execution_alignment, key_orchestration, model_orchestration, harness_authority, credential_isolation, sandbox_runtime_boundary, supply_chain, install_bootstrap, snapshot_restore, freeze_enforcement, client_integrations, provider_integrations, truth_boundary_consistency, overall) as VALID/CONDITIONAL/INVALID with rationale

### Remediation Plan

- [ ] **REM-01**: Produce ordered remediation plan (security-critical, authority-critical, truth-critical, runtime-critical, install/usability-critical, documentation-critical)
- [ ] **REM-02**: For each remediation item: issue, root cause, required invariant, enforcement surface, change type needed (code/test/runtime guard/docs correction/state migration/policy change)

### Test Strategy Review

- [ ] **TEST-01**: Audit repository test strategy for nominal vs adversarial coverage
- [ ] **TEST-02**: Identify core claims with no test coverage
- [ ] **TEST-03**: Evaluate whether tests match current docs and don't rely on misleading mocks

### Deliverable Artifacts

- [ ] **ART-01**: Produce TRUTH.yaml with final truth adjudication
- [ ] **ART-02**: Produce SYSTEM_SURFACE_MAP.md
- [ ] **ART-03**: Produce FEATURE_INVENTORY.yaml
- [ ] **ART-04**: Produce FUNCTION_INVENTORY.md
- [ ] **ART-05**: Produce INTEGRATION_MATRIX.yaml
- [ ] **ART-06**: Produce INVARIANTS.md
- [ ] **ART-07**: Produce KILL_TESTS.md
- [ ] **ART-08**: Produce VERIFICATION.md
- [ ] **ART-09**: Produce DRIFT_MAP.yaml
- [ ] **ART-10**: Produce RISK_REGISTER.yaml
- [ ] **ART-11**: Produce REMEDIATION_PLAN.md
- [ ] **ART-12**: Produce SUMMARY.md

## v2 Requirements

Deferred to future audit iteration:

- **RUNTIME-01**: Execute all 14 kill tests against actual runtime
- **RUNTIME-02**: Adversarial credential leak probing
- **RUNTIME-03**: Strict sandbox escape testing with bwrap
- **RUNTIME-04**: Policy race testing with concurrent requests

## Out of Scope

| Feature | Reason |
|---------|--------|
| Implementing missing features | This is an audit, not a fix phase — remediation identifies what to fix, future phases execute |
| Greenfield development | Purely diagnostic |
| Client/Provider compatibility testing that requires live credentials | No guarantee live provider keys available; classification based on code tracing |
| Performance/load testing | Out of scope for brownfield audit focused on correctness and security |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DISC-01 | Phase 1 | Pending |
| DISC-02 | Phase 1 | Pending |
| DISC-03 | Phase 1 | Pending |
| DISC-04 | Phase 1 | Pending |
| DISC-05 | Phase 1 | Pending |
| DISC-06 | Phase 1 | Pending |
| DISC-07 | Phase 1 | Pending |
| CLAIM-01 | Phase 2 | Pending |
| CLAIM-02 | Phase 2 | Pending |
| CLAIM-03 | Phase 2 | Pending |
| TRUTH-01 | Phase 3 | Pending |
| TRUTH-02 | Phase 3 | Pending |
| TRUTH-03 | Phase 3 | Pending |
| TRUTH-04 | Phase 3 | Pending |
| TRUTH-05 | Phase 3 | Pending |
| TRUTH-06 | Phase 3 | Pending |
| TRUTH-07 | Phase 3 | Pending |
| TRUTH-08 | Phase 3 | Pending |
| TRUTH-09 | Phase 3 | Pending |
| TRUTH-10 | Phase 3 | Pending |
| TRUTH-11 | Phase 3 | Pending |
| TRUTH-12 | Phase 3 | Pending |
| TRUTH-13 | Phase 3 | Pending |
| FEAT-01 | Phase 4 | Pending |
| FEAT-02 | Phase 4 | Pending |
| FUNC-01 | Phase 4 | Pending |
| FUNC-02 | Phase 4 | Pending |
| INT-01 | Phase 4 | Pending |
| INT-02 | Phase 4 | Pending |
| INT-03 | Phase 4 | Pending |
| INT-04 | Phase 4 | Pending |
| KILL-01 | Phase 5 | Pending |
| KILL-02 | Phase 5 | Pending |
| KILL-03 | Phase 5 | Pending |
| INV-01 | Phase 5 | Pending |
| INV-02 | Phase 5 | Pending |
| INV-03 | Phase 5 | Pending |
| INV-04 | Phase 5 | Pending |
| INV-05 | Phase 5 | Pending |
| INV-06 | Phase 5 | Pending |
| INV-07 | Phase 5 | Pending |
| INV-08 | Phase 5 | Pending |
| INV-09 | Phase 5 | Pending |
| DRIFT-01 | Phase 6 | Pending |
| DRIFT-02 | Phase 6 | Pending |
| DRIFT-03 | Phase 6 | Pending |
| DRIFT-04 | Phase 6 | Pending |
| DRIFT-05 | Phase 6 | Pending |
| DRIFT-06 | Phase 6 | Pending |
| DRIFT-07 | Phase 6 | Pending |
| DRIFT-08 | Phase 6 | Pending |
| DRIFT-09 | Phase 6 | Pending |
| DRIFT-10 | Phase 6 | Pending |
| FAIL-01 | Phase 6 | Pending |
| RISK-01 | Phase 6 | Pending |
| FINAL-01 | Phase 7 | Pending |
| REM-01 | Phase 7 | Pending |
| REM-02 | Phase 7 | Pending |
| TEST-01 | Phase 4 | Pending |
| TEST-02 | Phase 4 | Pending |
| TEST-03 | Phase 4 | Pending |
| ART-01 | Phase 8 | Pending |
| ART-02 | Phase 8 | Pending |
| ART-03 | Phase 8 | Pending |
| ART-04 | Phase 8 | Pending |
| ART-05 | Phase 8 | Pending |
| ART-06 | Phase 8 | Pending |
| ART-07 | Phase 8 | Pending |
| ART-08 | Phase 8 | Pending |
| ART-09 | Phase 8 | Pending |
| ART-10 | Phase 8 | Pending |
| ART-11 | Phase 8 | Pending |
| ART-12 | Phase 8 | Pending |

**Coverage:**
- v1 requirements: 85 total
- Mapped to phases: 85
- Unmapped: 0 ✓

---

*Requirements defined: 2026-04-04*
*Last updated: 2026-04-04 after initialization*
