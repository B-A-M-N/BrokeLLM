# Phase 2: Claim Extraction & Feature Inventory - Plan

**Phase:** 2  
**Name:** Claim Extraction & Feature Inventory  
**Goal:** Extract every declared claim from docs and code comments, build the complete feature inventory across all 12 feature families, and classify each claim's declared vs implemented status.

## Phase Requirements

- CLAIM-01
- CLAIM-02
- CLAIM-03
- FEAT-01
- FEAT-02

## Success Criteria

1. All declared claims extracted from docs with `claim_id`, `domain`, `statement`, `source`, `declared_scope`, `expected_proof_type`
2. Every feature family inventoried with `declared_behavior`, `implementation_locations`, `test_locations`, `runtime_entrypoints`, `dependencies`, `verification_status`
3. Each claim classified as `declared`, `implemented`, `verified`, `adversarially-verified`
4. `FEATURE_INVENTORY.yaml` skeleton complete with all 12 feature families

## Execution Strategy

Phase 2 should execute as a bounded evidence-extraction phase, not a narrative audit. The work should produce structured inventory artifacts that later phases can consume directly.

## Planning Assumption

`ROADMAP.md` and `REQUIREMENTS.md` currently disagree on the placement of `FEAT-01` and `FEAT-02`:

- roadmap places them in Phase 2
- requirements traceability places them in Phase 4

This plan resolves that conflict conservatively:

- Phase 2 will produce the complete 12-family feature inventory skeleton and initial claim/evidence mapping
- Phase 4 will deepen those inventories with function-family tracing, stronger test review, and broader coverage judgment

## Plan

### Plan 2.1 — Extract And Normalize Declared Claims

**Objective:** Build the canonical claim inventory from all relevant docs and claim-bearing text surfaces.

**Inputs:**

- `.planning/PROJECT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/brownfield-audit/_SYSTEM_SURFACE_MAP.md`
- `README.md`
- `ARCHITECTURE.md`
- `HUMAN_ONLY/FOR_BEGINNERS.md`
- `docs/harness/CORE.md`
- `docs/harness/CODE.md`
- `docs/harness/GSD.md`

**Tasks:**

1. enumerate all claim-bearing source files
2. extract each declared capability statement into a normalized schema
3. assign stable claim ids grouped by domain
4. record source path and declared scope for every claim
5. assign expected proof type for each claim:
   - code trace
   - test evidence
   - runtime verification
   - adversarial verification

**Outputs:**

- `CLAIMS.yaml` or equivalent normalized claim artifact under `.planning/brownfield-audit/`

**Verification:**

- every major doc source is represented
- no claim record is missing source path or expected proof type
- duplicate claims are collapsed or cross-linked, not silently duplicated

### Plan 2.2 — Build The 12-Family Feature Inventory

**Objective:** Produce the feature inventory skeleton required by the roadmap and tie each feature family to code/test/runtime surfaces.

**Feature families:**

1. routing
2. observability
3. execution layer
4. live key orchestration
5. live model orchestration
6. harness mode
7. security model
8. sandbox profiles
9. supply chain
10. state controls
11. installation/bootstrap
12. compatibility/integration claims

**Tasks:**

1. create one inventory section per feature family
2. populate declared behavior from extracted claims
3. populate implementation locations from code
4. populate test locations from `tests/test_mapping.py`
5. populate runtime entrypoints from CLI/proxy/bootstrap paths
6. record dependencies between families where relevant

**Outputs:**

- `FEATURE_INVENTORY.yaml`

**Verification:**

- all 12 families present
- each family has implementation locations and runtime entrypoints
- empty sections are explicitly marked, not silently omitted
- outputs remain inventory-level and do not sprawl into full function-family tracing reserved for Phase 4

### Plan 2.3 — Map Claims To Implementation And Proof Surfaces

**Objective:** Connect every normalized claim to code, tests, and runtime entrypoints so later phases can adjudicate them without redoing extraction.

**Inputs:**

- claim inventory from Plan 2.1
- feature inventory from Plan 2.2
- code surfaces:
  - `bin/broke`
  - `bin/_mapping.py`
  - `bin/_proxy.py`
  - `install.sh`
  - `tests/test_mapping.py`

**Tasks:**

1. add implementation locations per claim
2. add test locations per claim where available
3. add runtime entrypoints per claim where applicable
4. classify each claim as:
   - `declared`
   - `implemented`
   - `verified`
   - `adversarially-verified`
5. mark unsupported or unproven claims explicitly

**Outputs:**

- enriched claim inventory
- cross-links into `FEATURE_INVENTORY.yaml`

**Verification:**

- no claim remains with only prose and no evidence pointer unless explicitly marked unproven
- classification vocabulary is used consistently

### Plan 2.4 — Completeness And Consistency Review

**Objective:** Verify the Phase 2 outputs fully satisfy the roadmap and requirement set.

**Tasks:**

1. check `CLAIM-01` through `CLAIM-03` against produced artifacts
2. check `FEAT-01` and `FEAT-02` against the 12-family inventory
3. compare the inventory to Phase 1 surface map to catch missing families or missing runtime surfaces
4. record any gaps for later truth-surface or drift analysis phases

**Outputs:**

- completeness notes appended to the phase verification summary

**Verification:**

- all five Phase 2 requirements explicitly covered
- all four success criteria explicitly evidenced

## Risks And Controls

### Risk 1: claim duplication inflates inventory

**Control:** de-duplicate by statement meaning and source cross-reference

### Risk 2: feature families get collapsed or misbucketed

**Control:** use the 12 roadmap families as fixed top-level buckets

### Risk 3: “verified” and “adversarially-verified” get conflated

**Control:** reserve adversarial status only for evidence backed by kill tests or hostile verification work

### Risk 4: later phases cannot reuse outputs cleanly

**Control:** keep schemas structured and machine-readable from the start

## Deliverables

- `.planning/brownfield-audit/CLAIMS.yaml` or equivalent normalized claim inventory
- `.planning/brownfield-audit/FEATURE_INVENTORY.yaml`
- phase-local planning/research artifacts for reuse by downstream phases

## Exit Criteria

Phase 2 is complete when:

1. claim extraction is source-complete across the identified docs
2. all 12 feature families are present in `FEATURE_INVENTORY.yaml`
3. each claim has declared-vs-implemented-vs-verified classification
4. the artifact set is internally consistent with Phase 1 surface mapping
5. the phase output is strong enough for later truth-surface and function-inventory phases without pre-consuming their scope

## Verification Loop

Before closing the phase plan:

1. verify every Phase 2 roadmap success criterion has a corresponding task and output
2. verify every Phase 2 requirement is covered by at least one plan item
3. verify the deliverables are structured enough for Phase 3 and Phase 4 reuse
4. fail the phase plan if any of the 12 feature families is missing or undefined

## Notes

- `gsd-tools.cjs init plan-phase 2` failed in this environment because the local GSD install could not load `pg`
- this plan was produced manually from roadmap, requirements, state, and Phase 1 brownfield artifacts so Phase 2 planning could proceed without blocking
- the `FEAT-01` / `FEAT-02` phase-placement conflict remains in source planning docs and should be reconciled later rather than silently ignored
