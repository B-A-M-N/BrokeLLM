# Phase 3: Truth Surfaces & Integration Matrix - Plan

**Phase:** 3  
**Name:** Truth Surfaces & Integration Matrix  
**Goal:** Define and adjudicate all 15+ truth surfaces with source-of-truth, readers, writers, drift risks, and evidence. Build the complete integration matrix for all client, provider, and internal integrations.

## Phase Requirements

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

## Success Criteria

1. Each of the 15 truth surfaces is documented with `source_of_truth`, `readers`, `writers`, `drift_risks`, `evidence`, and `notes`
2. Truth surfaces end with provisional `VALID`, `CONDITIONAL`, or `INVALID` classification
3. All client integrations are documented
4. All provider integrations are documented
5. All internal integrations are documented with classification, failure modes, and observed behavior
6. `INTEGRATION_MATRIX.yaml` is complete
7. `TRUTH.yaml` structure is complete

## Execution Strategy

Phase 3 should execute as an evidence-anchored adjudication phase.

It should reuse:

- the surface map from Phase 1
- the normalized claims from Phase 2
- the feature inventory from Phase 2

It should avoid:

- redoing discovery work from Phase 1
- full function-family tracing from Phase 4
- full invariant design from Phase 5

## Planning Assumption

Phase 1 already mapped 15 concrete truth surfaces in `.planning/brownfield-audit/_SYSTEM_SURFACE_MAP.md`. This plan treats that set as the baseline truth-surface inventory for Phase 3:

1. routing
2. health
3. key policy
4. key state
5. model policy
6. model state
7. fallback resolution
8. harness verdict
9. credential isolation
10. sandbox/runtime boundary
11. execution alignment
12. launch preflight integrity
13. snapshot/restore
14. freeze enforcement
15. supply chain

If additional meta-surfaces are needed during execution, they may be added explicitly instead of being implied.

## Plan

### Plan 3.1 — Normalize Truth Surface Schema

**Objective:** Establish the canonical schema for truth-surface adjudication so every later domain record is comparable.

**Inputs:**

- `.planning/ROADMAP.md`
- `.planning/REQUIREMENTS.md`
- `.planning/phases/01-CONTEXT.md`
- `.planning/brownfield-audit/_SYSTEM_SURFACE_MAP.md`

**Tasks:**

1. define the truth-surface record schema
2. enumerate the baseline truth-surface list from Phase 1
3. map each Phase 3 `TRUTH-*` requirement to one or more concrete truth surfaces
4. define the evidence fields required for provisional classification

**Outputs:**

- initial `TRUTH.yaml` skeleton with one record per truth surface

**Verification:**

- all `TRUTH-01` through `TRUTH-13` requirements map to concrete surfaces
- no truth surface record is missing source-of-truth or evidence fields

### Plan 3.2 — Adjudicate Truth Surfaces With Evidence

**Objective:** Populate the truth-surface records with readers, writers, drift risks, evidence, and provisional classification.

**Inputs:**

- `TRUTH.yaml` skeleton from Plan 3.1
- `.planning/brownfield-audit/CLAIMS.yaml`
- `.planning/brownfield-audit/FEATURE_INVENTORY.yaml`
- `.planning/brownfield-audit/_SYSTEM_SURFACE_MAP.md`
- key code surfaces:
  - `bin/_mapping.py`
  - `bin/_proxy.py`
  - `bin/broke`
  - `bin/_harness_shim.py`
  - `bin/_socket_bridge.py`
  - `install.sh`

**Tasks:**

1. record source-of-truth, readers, and writers for each surface
2. attach claim references from Phase 2 where relevant
3. add evidence pointers:
   - code references
   - test references
   - prior runtime observations
4. classify each surface provisionally as:
   - `VALID`
   - `CONDITIONAL`
   - `INVALID`
5. mark unresolved proof gaps explicitly

**Outputs:**

- populated `TRUTH.yaml`

**Verification:**

- every truth surface has evidence and classification
- any surface lacking decisive proof is downgraded to `CONDITIONAL`, not inflated to `VALID`

### Plan 3.3 — Build Client, Provider, And Internal Integration Matrix

**Objective:** Produce the full integration matrix with classifications, observed behavior, and failure modes.

**Required coverage:**

**Clients**

- Claude CLI
- Codex CLI
- Gemini CLI
- Gemini endpoint

**Providers**

- OpenRouter
- Groq
- Cerebras
- GitHub Models
- Gemini
- Hugging Face

**Internal**

- wrapper -> config generation
- wrapper -> proxy
- proxy -> LiteLLM
- harness launcher -> shimmed tools
- preflight -> launch gating
- sandbox profiles -> client launch
- policy state -> runtime request behavior
- teams/profiles -> route/access state
- snapshots/freeze -> mutation commands

**Tasks:**

1. create one integration record per integration surface
2. classify each as `VALID`, `CONDITIONAL`, or `INVALID`
3. record failure modes and observed behavior
4. link integrations back to truth surfaces where applicable

**Outputs:**

- `INTEGRATION_MATRIX.yaml`

**Verification:**

- all Phase 3 integration requirements are covered
- each integration has classification, observed behavior, and failure modes

### Plan 3.4 — Reconcile Drift Candidates And Deferred Proof Gaps

**Objective:** Capture the known suspected drifts and proof gaps so later phases inherit them cleanly.

**Tasks:**

1. promote Phase 1 suspected drift candidates into truth-surface notes where relevant
2. identify which surfaces remain only partially runtime-proven
3. record which provisional classifications depend on deferred kill tests or deeper function tracing
4. append explicit downstream guidance for Phases 4 and 5

**Priority cases:**

- health-path divergence
- freeze enforcement gap
- snapshot scope gap
- execution alignment partial proof
- credential isolation proof gap
- sandbox boundary proof gap

**Outputs:**

- reconciliation notes embedded in `TRUTH.yaml` and `INTEGRATION_MATRIX.yaml`

**Verification:**

- no known drift candidate from Phase 1 disappears silently
- deferred proof gaps are attached to the correct truth surfaces

## Risks And Controls

### Risk 1: truth surfaces collapse into vague summaries

**Control:** require a stable record schema and evidence pointers for every surface

### Risk 2: integration matrix duplicates truth-surface content without adding value

**Control:** keep truth-surface records about source-of-truth and drift, and integration records about connectivity, observed behavior, and failure modes

### Risk 3: provisional classifications become overconfident

**Control:** default to `CONDITIONAL` when runtime or adversarial proof is incomplete

### Risk 4: later phases lose track of deferred proof obligations

**Control:** explicitly record unresolved proof gaps and downstream handoff notes

## Deliverables

- `.planning/brownfield-audit/TRUTH.yaml`
- `.planning/brownfield-audit/INTEGRATION_MATRIX.yaml`
- phase-local research and plan artifacts for Phase 3

## Exit Criteria

Phase 3 is complete when:

1. all mapped truth surfaces have structured records with provisional classification
2. all required client, provider, and internal integrations are represented
3. `TRUTH.yaml` and `INTEGRATION_MATRIX.yaml` are both non-empty and reusable by later phases
4. major suspected drift candidates from Phase 1 are explicitly carried forward into the adjudication artifacts

## Verification Loop

Before closing the phase plan:

1. verify every `TRUTH-*` requirement maps to a surface record
2. verify every `INT-*` requirement maps to integration records
3. verify provisional classifications are evidence-backed and conservative
4. fail the plan if either `TRUTH.yaml` or `INTEGRATION_MATRIX.yaml` would be left as a prose-only outline

## Notes

- `gsd-tools.cjs` remains unavailable in this environment because the local delegated runtime cannot load `pg`
- this Phase 3 plan was produced manually from approved planning artifacts so work can continue without blocking on the external GSD runtime
