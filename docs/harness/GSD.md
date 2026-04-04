# Broke Harness GSD Overlay

## Purpose

The GSD overlay adapts GSD workflow artifacts into Broke Harness Core plus the Code profile.

It is not the identity of the harness.

It is an adapter and policy overlay.

## Stack

The intended layering is:

1. Broke Harness Core
2. Broke Harness Code Profile
3. Broke Harness GSD Overlay

## What GSD Contributes

GSD contributes workflow-specific structure such as:

- phase and plan context
- explicit verification artifacts
- truth/evidence discipline
- governance around declared vs observed work
- stronger completion doctrine

## Overlay Family

GSD is not a single overlay. It is a family of governance overlays that may tighten the active Code doctrine.

Recommended starting catalog:

- `execution`
- `brownfield_strict`
- `closure`
- `recovery_drift`

The active GSD overlay answers:

> What additional governance pressure applies because this run is operating under GSD truth and artifact discipline?

## Overlay Schema

Each GSD overlay should define:

- upstream artifact bindings
- reconciliation rules
- stricter evidence requirements
- checkpoint restrictions
- escalation rules
- closure expectations

GSD overlays should usually tighten a Code doctrine, not replace it.

## What The GSD Overlay Should Do

The overlay should translate GSD artifacts into a neutral run contract.

Examples:

- phase or quick-task context becomes task input
- plan/checker/verifier expectations become verification policy
- GSD truth artifacts become structured evidence inputs
- GSD gating becomes harness policy overlays

## Upstream Translation

The overlay maps GSD outputs into a neutral run contract.

Examples:

- GSD phase/task -> task descriptor
- declared scope -> authority hints / allowed paths
- GSD verification expectations -> required verification classes
- GSD governance posture -> stricter default policy profile

## What The GSD Overlay Must Not Do

It must not redefine:

- credential planes
- runtime enforcement substrate
- verdict algebra
- event ledger model
- core harness identity

Those belong to Core and the Code profile.

## Adapter Inputs

Potential GSD-derived inputs:

- `CONTEXT.md`
- `PLAN.md`
- `RESEARCH.md`
- execution summaries
- verification artifacts
- UAT artifacts
- state/gate/degraded signals

## Overlay-Specific Expectations

Compared to generic coding runs, GSD-oriented runs may require:

- stronger declared-vs-observed reconciliation
- explicit verification artifact presence
- stricter checkpoint admissibility
- stronger drift handling
- explicit escalation on evidence gaps
- claimed completion vs evidence mismatch checks
- required artifact absence checks

## Recommended GSD Overlays

### `execution`

- bind task execution to declared plan or phase context
- flag undeclared work and scope drift
- require evidence to map back to declared scope

### `brownfield_strict`

- tighten the active `Code/brownfield_audit` doctrine
- reconcile declared truth surfaces from GSD artifacts against observed runtime and code evidence
- classify declared-vs-observed mismatches aggressively

Typical concerns:

- claimed completion vs evidence mismatch
- missing required verification artifacts
- stale truth files
- declared scope vs observed mutations
- invalid or unverifiable truth surfaces

### `closure`

- require explicit closure artifacts
- enforce summary consistency, verification freshness, and completion gates

### `recovery_drift`

- detect stale, archived, orphaned, or contradictory GSD artifacts
- help recover governance truth after workflow drift

## Example Adapter Output

```json
{
  "task_source_type": "adapter",
  "task_source_ref": ".planning/phases/12-feature/12-01-PLAN.md",
  "upstream_adapter": "gsd",
  "runtime_mode": "harness",
  "policy_profile": "high_assurance",
  "risk_tier": "high",
  "sandbox_profile": "strict",
  "verification_requirements": {
    "must_run": ["tests", "typecheck"],
    "forbid_skips": true,
    "allow_test_only_change": false
  }
}
```

## Mapping Guidance

GSD should map:

- workflow state into run metadata
- plan/checker constraints into policy overlays
- verification artifacts into evidence packets
- truth-bearing contradictions into stronger verdict precedence

## GSD Overlay Objects

- `GsdTaskMapping`
- `GsdEvidenceBinding`
- `DeclaredVsObservedReconciliation`
- `GsdCompletionExpectation`
- `GsdGovernancePolicyOverlay`

## Brownfield Strict Overlay

The BrokeLLM brownfield audit prompt maps here as the stricter GSD interpretation of the `Code/brownfield_audit` doctrine.

That means:

- Code owns the hostile brownfield audit method itself.
- GSD owns the stricter reconciliation against `.planning/` truth artifacts and governance contracts.

The intended stack is:

```yaml
core_profile: high_assurance
code_doctrine: brownfield_audit
gsd_overlay: brownfield_strict
```

## Why This Layer Exists

GSD is stricter than generic coding work.

It cares more about:

- truth surfaces
- verification discipline
- declared intent vs actual implementation
- explicit governance trails

Those are real needs, but they are not universal runtime assumptions.

So they belong in an overlay, not in the core harness definition.

## GSD Overlay Does Not Own

The overlay does not redefine:

- process wrapping
- env injection
- credential lanes
- event ledger
- review cache
- general verdict engine mechanics

Those stay in Core.
