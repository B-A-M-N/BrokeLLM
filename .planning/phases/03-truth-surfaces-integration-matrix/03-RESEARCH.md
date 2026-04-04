# Phase 3: Truth Surfaces & Integration Matrix - Research

**Generated:** 2026-04-04  
**Status:** Ready for planning  
**Method:** Manual fallback research because the local `get-shit-done` execution path still delegates into a broken runtime missing `pg`

## Research Objective

Answer: what must be understood to plan Phase 3 well?

Phase 3 is the first phase that moves from discovery/inventory into provisional adjudication. It must:

1. take the truth surfaces already mapped in Phase 1,
2. enrich them with declared claims from Phase 2,
3. record source-of-truth, readers, writers, drift risks, and evidence,
4. assign provisional `VALID`, `CONDITIONAL`, or `INVALID` classifications,
5. build the full integration matrix for client, provider, and internal integrations.

This phase is stronger than Phase 2 because it starts assigning truth judgments, but it is still not the final remediation or final truth package phase.

## Key Inputs Now Available

Phase 3 has stronger upstream inputs than earlier planning:

- `.planning/phases/01-CONTEXT.md`
- `.planning/brownfield-audit/_SYSTEM_SURFACE_MAP.md`
- `.planning/brownfield-audit/CLAIMS.yaml`
- `.planning/brownfield-audit/FEATURE_INVENTORY.yaml`
- `.planning/ROADMAP.md`
- `.planning/REQUIREMENTS.md`
- `README.md`
- `ARCHITECTURE.md`
- `docs/harness/CORE.md`
- `docs/harness/CODE.md`
- `docs/harness/GSD.md`

That means Phase 3 should not rediscover surfaces. It should adjudicate the discovered ones.

## Truth Surface Baseline

Phase 1 already mapped a concrete preliminary truth-surface set:

1. routing truth
2. health truth
3. key policy truth
4. key state truth
5. model policy truth
6. model state truth
7. fallback resolution truth
8. harness verdict truth
9. credential isolation truth
10. sandbox/runtime boundary truth
11. execution alignment truth
12. launch preflight integrity truth
13. snapshot/restore truth
14. freeze enforcement truth
15. supply-chain truth

Roadmap language says “15+ truth surfaces.” That means this mapped set should be treated as the minimum, not the maximum. Phase 3 may need to add:

- truth-boundary consistency as a meta-surface
- client integration truth
- provider integration truth

Those may remain in the integration matrix rather than the truth-surface list if doing so keeps the artifact boundary cleaner, but the plan should keep the possibility open.

## Planning Implications

### A. Phase 3 needs evidence packets per truth surface

Each surface should not be a prose paragraph. It should have a stable structure:

- `name`
- `source_of_truth`
- `readers`
- `writers`
- `mutation_points`
- `drift_risks`
- `evidence`
- `notes`
- `provisional_classification`

Without a stable schema, later final adjudication will become hand-wavy.

### B. Phase 3 should reconcile claims against surfaces

Phase 2 extracted claims by domain. Phase 3 should reuse those claims to avoid inventing new truth categories ad hoc.

Examples:

- routing claims should feed routing truth and fallback resolution truth
- harness claims should feed harness verdict truth and credential isolation truth
- security claims should feed credential isolation, sandbox/runtime boundary, and launch preflight integrity truth
- supply-chain claims should feed supply-chain truth

### C. Integration matrix must stay separate from truth surface records

The integration matrix is related to truth surfaces but not identical to them.

Truth surfaces answer:
- what is the real source of truth for a domain?
- who reads/writes it?
- where can drift happen?

Integration matrix answers:
- what system connects to what external/internal actor?
- what is claimed to work?
- what is observed to work?
- what are the failure modes?

If those are merged carelessly, Phase 3 output will become muddled.

### D. Provisional classification must remain evidence-constrained

This phase is allowed to produce provisional `VALID / CONDITIONAL / INVALID`, but only when backed by:

- code references
- prior runtime observations
- current runtime checks where safe
- test evidence

Anything still not proven should default to `CONDITIONAL`, not optimistic `VALID`.

## Highest-Risk Surfaces To Prioritize

Phase 1 already surfaced likely drift candidates that should be prioritized in planning:

1. health truth
   - `doctor` and `explain/route` appear to consume health differently
2. freeze enforcement truth
   - docs imply stronger protection than currently enforced
3. snapshot/restore truth
   - saved scope appears narrower than user-facing implications
4. execution alignment truth
   - route/explain agreement is only partially probed; actual request path remains multi-step
5. credential isolation truth
   - child-process scoping exists, but adversarial env-leak proof is still deferred
6. sandbox/runtime boundary truth
   - strict mode is stronger now, but real runtime isolation must still be judged conservatively

## Integration Matrix Scope

Phase 3 must explicitly cover:

### Client integrations

- Claude CLI
- Codex CLI
- Gemini CLI
- Gemini endpoint

### Provider integrations

- OpenRouter
- Groq
- Cerebras
- GitHub Models
- Gemini
- Hugging Face

### Internal integrations

- Broke wrapper -> LiteLLM config generation
- Broke wrapper -> proxy
- proxy -> LiteLLM
- harness launcher -> shimmed tools
- preflight -> launch gates
- sandbox profiles -> client launch behavior
- policy stores -> runtime request behavior
- snapshots/freeze -> mutation commands
- teams/profiles -> routing and access behavior

## Boundaries For This Phase

Phase 3 should not expand into full function-family tracing. That belongs to Phase 4.

Phase 3 should not design the full invariant catalog. That belongs to Phase 5.

Phase 3 should not produce the final risk register or remediation ordering. Those belong later.

It should stay focused on:

1. truth surfaces,
2. provisional truth adjudication,
3. integration classification.

## Recommended Output Shape

This phase should produce:

- `TRUTH.yaml`
- `INTEGRATION_MATRIX.yaml`
- phase-local research/plan artifacts

And those outputs should be strong enough for:

- Phase 4 function inventory
- Phase 5 invariants and kill tests
- Phase 7 final truth adjudication

## Conclusion

Phase 3 should be planned as an evidence-anchored adjudication phase, not a rediscovery phase.

The best execution shape is:

1. finalize the truth-surface schema,
2. adjudicate each mapped surface with evidence and provisional classification,
3. build the full integration matrix across client/provider/internal boundaries,
4. record unresolved drift and proof gaps for later phases.
