# Roadmap: BrokeLLM Brownfield Audit

**Created:** 2026-04-04
**Milestone:** v1 Audit
**Core Value:** Evidence over declaration — every claimed capability must be traced to code, tests, and runtime behavior

## Phase 1: Repo Discovery & Ground Truth Bootstrap

**Goal:** Discover the real system — all executable entrypoints, CLI commands, configuration boundaries, runtime state surfaces, and integration paths before adjudicating anything.

**Requirements:** DISC-01, DISC-02, DISC-03, DISC-04, DISC-05, DISC-06, DISC-07

**Success criteria:**
1. Complete listing of all executable scripts, Python packages, and CLI command entrypoints exists
2. All 12 CLI command families traced to their dispatch boundaries in code
3. All state files and persistence surfaces identified with file paths
4. Trust boundaries, authority expansion paths, and code paths that mutate routing/policy documented
5. Integration surfaces (LiteLLM, proxy, sandbox, install) identified with concrete file locations

**UI hint:** no

---

## Phase 2: Claim Extraction & Feature Inventory

**Goal:** Extract every declared claim from docs and code comments, build the complete feature inventory across all 12 feature families, and classify each claim's declared vs implemented status.

**Requirements:** CLAIM-01, CLAIM-02, CLAIM-03, FEAT-01, FEAT-02

**Success criteria:**
1. All declared claims extracted from docs with claim id, domain, statement, source, declared_scope, expected_proof_type
2. Every feature family (routing, observability, execution, key orchestration, model orchestration, harness, security, sandbox, supply chain, state, install, compatibility) inventoried with declared_behavior, implementation_locations, test_locations, runtime_entrypoints, dependencies, verification_status
3. Each claim classified as declared/implemented/verified/adversarially-verified
4. FEATURE_INVENTORY.yaml skeleton complete with all 12 feature families

**UI hint:** no

---

## Phase 3: Truth Surfaces & Integration Matrix

**Goal:** Define and adjudicate all 15+ truth surfaces with source-of-truth, readers, writers, drift risks, and evidence. Build the complete integration matrix for all client, provider, and internal integrations.

**Requirements:** TRUTH-01 through TRUTH-13, INT-01, INT-02, INT-03, INT-04

**Success criteria:**
1. Each of the 15 truth surfaces documented with source_of_truth, readers, writers, drift_risks, evidence, and notes
2. Truth surfaces end with VALID/CONDITIONAL/INVALID provisional classification
3. All client integrations (Claude, Codex, Gemini CLI, Gemini endpoint) documented
4. All provider integrations (OpenRouter, Groq, Cerebras, GitHub Models, Gemini, Hugging Face) documented
5. All internal integrations documented with classification, failure modes, observed behavior
6. INTEGRATION_MATRIX.yaml complete
7. TRUTH.yaml structure complete

**UI hint:** no

---

## Phase 4: Function Inventory & Test Review

**Goal:** Trace every meaningful function family to determine inputs, state mutations, invariants, fail-closed behavior, test coverage, and bypassability. Audit repository test strategy for nominal vs adversarial coverage.

**Requirements:** FUNC-01, FUNC-02, TEST-01, TEST-02, TEST-03

**Success criteria:**
1. All major function families traced with inputs consumed, state mutated, invariants assumed, source-of-truth vs consumer-only, fail open/closed, test coverage, bypassability
2. FUNCTION_INVENTORY.md complete
3. Repository test strategy audited — which claims have nominal tests, adversarial tests, no tests
4. Mock usage evaluated for whether it hides real risk
5. Test coverage judgment produced for each major domain (routing, policy, harness, security, sandbox, execution alignment, install/bootstrap, snapshot/freeze, client, provider)

**UI hint:** no

---

## Phase 5: Invariants Definition & Kill Test Design

**Goal:** Define all hard invariants the system must maintain, design all 14 kill tests, and map which kill tests are executable in current repo state.

**Requirements:** KILL-01, KILL-02, KILL-03, INV-01, INV-02, INV-03, INV-04, INV-05, INV-06, INV-07, INV-08, INV-09

**Success criteria:**
1. All routing invariants defined and documented
2. All truth-boundary invariants defined and documented
3. All policy invariants defined and documented
4. All harness invariants defined and documented
5. All security, sandbox, supply-chain, state, and install/bootstrap invariants defined
6. INVARIANTS.md complete
7. All 14 kill tests (KT-01 through KT-14) designed with concrete adversarial procedures
8. KILL_TESTS.md complete with kill test to invariant mapping and executability classification

**UI hint:** no

---

## Phase 6: Drift Analysis & Failure Classification & Risk Register

**Goal:** Identify all drift classes between declared and observed behavior, classify every issue into failure categories, and build the risk register.

**Requirements:** DRIFT-01 through DRIFT-10, FAIL-01, RISK-01

**Success criteria:**
1. All 10 drift classes identified with declared_surface, observed_surface, severity, exploitability, user_impact, recommended_fix
2. DRIFT_MAP.yaml complete
3. Every identified issue classified into one or more failure categories (BOUNDARY_VIOLATION, STATE_DRIFT, AUTHORITY_LEAK, OBSERVABILITY_MISMATCH, EXECUTION_DIVERGENCE, SECURITY_ISOLATION_FAILURE, SANDBOX_ENFORCEMENT_FAILURE, SUPPLY_CHAIN_GAP, INSTALL_BOOTSTRAP_GAP, INTEGRATION_OVERCLAIM, TEST_COVERAGE_GAP, PERSISTENCE_TRUTH_GAP, DOC_TRUTH_GAP)
4. RISK_REGISTER.yaml complete with all identified issues, severity, and user impact

**UI hint:** no

---

## Phase 7: Final Truth Adjudication & Remediation Plan

**Goal:** Produce final VALID/CONDITIONAL/INVALID adjudication for all 18 truth domains with rationale and evidence references. Produce ordered remediation plan for every identified issue.

**Requirements:** FINAL-01, REM-01, REM-02

**Success criteria:**
1. All 18 truth domains (routing, fallback_resolution, observability, execution_alignment, key_orchestration, model_orchestration, harness_authority, credential_isolation, sandbox_runtime_boundary, supply_chain, install_bootstrap, snapshot_restore, freeze_enforcement, client_integrations, provider_integrations, truth_boundary_consistency, overall) adjudicated as VALID/CONDITIONAL/INVALID
2. Each domain includes rationale with evidence file/line references
3. Final truth values written to TRUTH.yaml
4. Remediation plan produced ordered by: security-critical, authority-critical, truth-critical, runtime-critical, install/usability-critical, documentation-critical
5. Each remediation item includes issue, root cause, required invariant, enforcement surface, change type needed

**UI hint:** no

---

## Phase 8: Artifact Assembly & Summary

**Goal:** Assemble all 12 required deliverable files into `.planning/brownfield-audit/` and produce the final audit summary.

**Requirements:** ART-01, ART-02, ART-03, ART-04, ART-05, ART-06, ART-07, ART-08, ART-09, ART-10, ART-11, ART-12

**Success criteria:**
1. TRUTH.yaml exists with final truth adjudication
2. SYSTEM_SURFACE_MAP.md exists with all CLI command surfaces, runtime control surfaces, integration surfaces, and trust surfaces documented
3. FEATURE_INVENTORY.yaml exists with all 12 feature families
4. FUNCTION_INVENTORY.md exists with all function families traced
5. INTEGRATION_MATRIX.yaml exists with all integrations classified
6. INVARIANTS.md exists with all invariants defined
7. KILL_TESTS.md exists with all 14 kill tests designed
8. VERIFICATION.md exists confirming audit deliverable completeness
9. DRIFT_MAP.yaml exists with all drift classes documented
10. RISK_REGISTER.yaml exists with all risks registered
11. REMEDIATION_PLAN.md exists with ordered remediation items
12. SUMMARY.md exists with executive audit findings summary
13. All 12 files exist under .planning/brownfield-audit/ and are non-empty, structured, and internally consistent

**UI hint:** no
