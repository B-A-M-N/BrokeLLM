# Phase 2: Claim Extraction & Feature Inventory - Research

**Generated:** 2026-04-04  
**Status:** Ready for planning  
**Method:** Manual fallback research because `gsd-tools.cjs init plan-phase 2` failed locally due to missing `pg`

## Research Objective

Answer: what must be understood to plan Phase 2 well?

Phase 2 is not a runtime-verification phase. It is a structured extraction and inventory phase that establishes:

1. every declared claim in docs and repo-facing text,
2. every feature family in the shipped system,
3. the mapping from claims to implementation and proof surfaces,
4. the initial declared vs implemented vs verified truth state for each claim.

## Constraints Observed In This Repo

- Documentation claims are distributed across:
  - `README.md`
  - `ARCHITECTURE.md`
  - `HUMAN_ONLY/FOR_BEGINNERS.md`
  - `.planning/PROJECT.md`
  - `.planning/REQUIREMENTS.md`
  - `.planning/ROADMAP.md`
  - harness docs under `docs/harness/`
- Some claims also live in comments and command UX text inside:
  - `bin/broke`
  - `bin/_mapping.py`
  - `bin/_proxy.py`
  - `install.sh`
- Phase 1 already produced a strong surface map in:
  - `.planning/brownfield-audit/_SYSTEM_SURFACE_MAP.md`

## Planning Conflict To Carry Forward

There is a real planning inconsistency between roadmap and requirements traceability:

- `.planning/ROADMAP.md` assigns `FEAT-01` and `FEAT-02` to Phase 2
- `.planning/REQUIREMENTS.md` traceability table assigns `FEAT-01` and `FEAT-02` to Phase 4

The safest interpretation is:

- Phase 2 owns the first complete feature inventory skeleton and claim-to-feature mapping
- Phase 4 deepens that inventory with function-level tracing, test-strategy review, and stronger coverage judgment

Phase 2 planning should therefore produce the structured inventory now, while explicitly avoiding full Phase 4-style function-family adjudication.

## What Phase 2 Must Inventory

The roadmap already defines the 12 required feature families:

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

Phase 2 should treat these as fixed inventory buckets unless evidence proves one must be split.

## Planning Implications

### A. Claim extraction must be source-first

The safest approach is to extract claims by source class:

- user-facing docs
- architecture/spec docs
- beginner/operator docs
- CLI help and command UX text
- code comments / embedded assertions

This prevents missing “soft claims” that only appear in command output or doc prose.

### B. Claim normalization needs a stable schema

Every claim record should include at least:

- `claim_id`
- `domain`
- `statement`
- `source`
- `declared_scope`
- `expected_proof_type`
- `implementation_locations`
- `test_locations`
- `runtime_entrypoints`
- `declared_status`
- `implemented_status`
- `verified_status`
- `adversarial_status`

Without a stable claim schema, later phases cannot reconcile truth surfaces reliably.

### C. Feature inventory must be implementation-anchored

Feature families should not remain doc-shaped only. For each family, Phase 2 needs:

- declared behavior
- implementation locations
- test locations
- runtime entrypoints
- dependencies
- verification status

### D. This phase should not over-adjudicate

Phase 2 can classify:

- declared
- implemented
- verified
- adversarially-verified

But it should avoid claiming final `VALID / CONDITIONAL / INVALID` domain truth. That belongs later.

### E. Feature inventory here should stay skeleton-first

Because the roadmap and requirements disagree on where feature inventory fully lands, Phase 2 should produce:

- all 12 required family buckets
- declared behavior
- initial implementation/test/runtime references
- initial verification status

But it should not try to replace Phase 4's deeper function inventory or test strategy review.

## Existing Evidence To Reuse

High-value upstream inputs:

- `.planning/ROADMAP.md`
- `.planning/REQUIREMENTS.md`
- `.planning/PROJECT.md`
- `.planning/STATE.md`
- `.planning/brownfield-audit/_SYSTEM_SURFACE_MAP.md`
- `README.md`
- `docs/harness/CORE.md`
- `docs/harness/CODE.md`
- `docs/harness/GSD.md`
- `ARCHITECTURE.md`
- `HUMAN_ONLY/FOR_BEGINNERS.md`

High-value code surfaces:

- `bin/broke`
- `bin/_mapping.py`
- `bin/_proxy.py`
- `install.sh`
- `tests/test_mapping.py`

## Risks For This Phase

1. claim duplication across docs causing inflated counts
2. feature inventory collapsing distinct families into one bucket
3. implementation references being incomplete or too shallow
4. confusing “tested” with “verified adversarially”
5. overcommitting to final adjudication too early

## Recommended Phase 2 Output Shape

This phase should leave behind:

- a normalized claim inventory artifact
- a feature-family inventory artifact
- a mapping from claims to implementation/test/runtime surfaces
- a coverage/completeness check against the 12 roadmap families and Phase 2 requirements

## Conclusion

Phase 2 should be planned as a structured extraction-and-classification pass, not a freeform audit narrative.

The best execution shape is:

1. enumerate sources,
2. extract and normalize claims,
3. build the 12-family feature inventory,
4. map each claim to implementation/test/runtime evidence,
5. classify declared vs implemented vs verified vs adversarially-verified,
6. verify completeness against roadmap and requirements.
