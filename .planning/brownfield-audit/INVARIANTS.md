# BrokeLLM Invariants

**Generated:** 2026-04-04  
**Phase:** 5  
**Method:** Manual phase execution fallback

## Invariant Schema

Each invariant includes:

- invariant id
- required property
- rationale
- related truth surfaces
- likely failure class if broken
- validating kill tests

## INV-01 Routing Invariants

### INV-01.1 Route/Explain Consistency

**Required property**

For any active slot:

`route(slot)` and `explain(slot)` must resolve the same primary backend identity and the same ordered fallback chain.

**Rationale**

The system cannot claim deterministic slot routing if its dry-run routing surfaces disagree.

**Related truth surfaces**

- routing_truth
- fallback_resolution_truth

**Failure class if broken**

- OBSERVABILITY_MISMATCH
- EXECUTION_DIVERGENCE

**Validating kill tests**

- KT-01
- KT-05
- KT-07

### INV-01.2 Canonical Route Identity

**Required property**

All route identity comparisons must normalize to canonical `provider/model` form rather than labels or ad hoc strings.

**Rationale**

Label-based comparisons create split-brain risk when provider/model aliases drift.

**Related truth surfaces**

- routing_truth

**Failure class if broken**

- STATE_DRIFT
- OBSERVABILITY_MISMATCH

**Validating kill tests**

- KT-01
- KT-06

### INV-01.3 Deterministic Fallback Ordering

**Required property**

Fallback chain ordering must be deterministic and preserved consistently across display, validation, and request-time selection.

**Rationale**

Fallbacks are only trustworthy if the order is stable and interpretable.

**Related truth surfaces**

- fallback_resolution_truth

**Failure class if broken**

- EXECUTION_DIVERGENCE
- STATE_DRIFT

**Validating kill tests**

- KT-05

## INV-02 Truth-Boundary Invariants

### INV-02.1 Shared Normalization Boundary

**Required property**

Commands that reason about backend identity, pin state, or health must consume the shared normalization helpers rather than inventing their own logic.

**Rationale**

The control plane loses trust as soon as multiple surfaces compute truth differently.

**Related truth surfaces**

- routing_truth
- health_truth

**Failure class if broken**

- OBSERVABILITY_MISMATCH

**Validating kill tests**

- KT-01
- KT-07

### INV-02.2 Health Agreement Across Surfaces

**Required property**

`doctor`, `route`, and `explain` must agree on gateway and selected-backend health interpretation for the same live state.

**Rationale**

Current Phase 3 evidence already shows this invariant is violated in the current system.

**Related truth surfaces**

- health_truth

**Failure class if broken**

- OBSERVABILITY_MISMATCH

**Validating kill tests**

- KT-07

## INV-03 Policy Invariants

### INV-03.1 Generation Isolation

**Required property**

In-flight requests must continue under the generation they started with. New requests must reflect the latest accepted key/model policy generation.

**Rationale**

Live policy mutation is only safe if generation boundaries are respected.

**Related truth surfaces**

- key_policy_truth
- model_policy_truth
- execution_alignment_truth

**Failure class if broken**

- EXECUTION_DIVERGENCE
- STATE_DRIFT

**Validating kill tests**

- KT-02

### INV-03.2 State Transition Sanity

**Required property**

Key and model states must only transition through valid operational states (`healthy`, `cooldown`, `blocked`, `auth_failed`, `incompatible` where applicable) and cooldown semantics must be enforced consistently.

**Rationale**

If runtime state can drift arbitrarily, policy logic becomes meaningless.

**Related truth surfaces**

- key_state_truth
- model_state_truth

**Failure class if broken**

- STATE_DRIFT

**Validating kill tests**

- KT-02
- KT-12

## INV-04 Harness Invariants

### INV-04.1 Authority Expansion Requires Elevation

**Required property**

Provider-direct worker authority must require explicit elevation and must emit a durable event when denied.

**Rationale**

Worker authority expansion is a real security boundary, not a cosmetic toggle.

**Related truth surfaces**

- harness_verdict_truth
- credential_isolation_truth

**Failure class if broken**

- AUTHORITY_LEAK
- BOUNDARY_VIOLATION

**Validating kill tests**

- KT-08

### INV-04.2 Verdict Semantics Must Be Real

**Required property**

`BLOCK`, `RETRY_*`, and `ESCALATE` outcomes must change allowed execution behavior, not merely print summaries.

**Rationale**

Harness mode is meaningless if verdicts are advisory only.

**Related truth surfaces**

- harness_verdict_truth

**Failure class if broken**

- BOUNDARY_VIOLATION
- OBSERVABILITY_MISMATCH

**Validating kill tests**

- KT-03
- KT-13

## INV-05 Security Invariants

### INV-05.1 Scoped Credential Injection

**Required property**

Provider credentials must only be injected into the exact child process or review lane that requires them. No global env export may reintroduce broad credential leakage.

**Rationale**

Credential isolation is a primary security claim and current proof is still partial.

**Related truth surfaces**

- credential_isolation_truth

**Failure class if broken**

- AUTHORITY_LEAK
- SECURITY_ISOLATION_FAILURE

**Validating kill tests**

- KT-03
- KT-04

### INV-05.2 Fail-Closed Unknown Model And Auth Rejection

**Required property**

Unknown model ids and repeated invalid auth attempts must fail closed.

**Rationale**

This is already partly enforced and must remain so.

**Related truth surfaces**

- credential_isolation_truth
- execution_alignment_truth

**Failure class if broken**

- SECURITY_ISOLATION_FAILURE
- EXECUTION_DIVERGENCE

**Validating kill tests**

- KT-12

## INV-06 Sandbox Invariants

### INV-06.1 Strict Boundary Narrowing

**Required property**

Strict sandbox mode must expose only the minimal filesystem, env, and local bridge surfaces needed for the supported client.

**Rationale**

Strict mode is only meaningful if its boundary is materially narrower than normal mode.

**Related truth surfaces**

- sandbox_runtime_boundary_truth

**Failure class if broken**

- SANDBOX_ENFORCEMENT_FAILURE
- SECURITY_ISOLATION_FAILURE

**Validating kill tests**

- KT-11

### INV-06.2 Unsupported Strict Clients Must Be Denied

**Required property**

Clients whose network/runtime model conflicts with strict mode must be denied rather than partially launched.

**Rationale**

Partial launch would create confusing half-isolated states.

**Related truth surfaces**

- sandbox_runtime_boundary_truth

**Failure class if broken**

- SANDBOX_ENFORCEMENT_FAILURE

**Validating kill tests**

- KT-11

## INV-07 Supply-Chain Invariants

### INV-07.1 Hash-Bound Install Path

**Required property**

The intended install path must remain tied to exact dependency input and transitive hashes.

**Rationale**

The supply-chain claim depends on more than having lockfiles present.

**Related truth surfaces**

- supply_chain_truth

**Failure class if broken**

- SUPPLY_CHAIN_GAP

**Validating kill tests**

- KT-14

### INV-07.2 Runtime Drift Must Be Detectable

**Required property**

If the live environment drifts from the locked dependency set, preflight must surface it clearly.

**Rationale**

Current Phase 3 evidence shows drift detection matters in practice.

**Related truth surfaces**

- launch_preflight_integrity_truth
- supply_chain_truth

**Failure class if broken**

- SUPPLY_CHAIN_GAP
- INSTALL_BOOTSTRAP_GAP

**Validating kill tests**

- KT-14

## INV-08 State Invariants

### INV-08.1 Freeze Must Match Its Implied Boundary

**Required property**

If freeze is presented as blocking state mutation, all relevant mutation surfaces must be gated or the scope must be explicitly narrowed in documentation and UX.

**Rationale**

Current Phase 3 classified freeze enforcement as invalid because the gate is too narrow.

**Related truth surfaces**

- freeze_enforcement_truth

**Failure class if broken**

- PERSISTENCE_TRUTH_GAP
- BOUNDARY_VIOLATION

**Validating kill tests**

- KT-09

### INV-08.2 Snapshot Restore Scope Must Be Truthful

**Required property**

Snapshot save/restore behavior must either preserve all declared state or clearly disclose the exact limited state it preserves.

**Rationale**

Mapping-only snapshots are acceptable only if represented truthfully.

**Related truth surfaces**

- snapshot_restore_truth

**Failure class if broken**

- PERSISTENCE_TRUTH_GAP
- DOC_TRUTH_GAP

**Validating kill tests**

- KT-10

### INV-08.3 Team/Profile Referential Integrity

**Required property**

Profiles must not silently survive with invalid team references or broken access assumptions.

**Rationale**

State-layer integrity includes reusable presets, not just routing JSON.

**Related truth surfaces**

- snapshot_restore_truth
- routing_truth

**Failure class if broken**

- STATE_DRIFT

**Validating kill tests**

- KT-12

## INV-09 Install / Bootstrap Invariants

### INV-09.1 Bootstrap Must Produce A Runnable Baseline

**Required property**

Install/bootstrap should leave the repo in a coherent runnable state with initialized core files and command path.

**Rationale**

A broken baseline invalidates all downstream control-plane guarantees.

**Related truth surfaces**

- launch_preflight_integrity_truth
- supply_chain_truth

**Failure class if broken**

- INSTALL_BOOTSTRAP_GAP

**Validating kill tests**

- KT-14

### INV-09.2 Default State Must Be Internally Coherent

**Required property**

Default initialized mapping, deployments, provider state, and env exports must not disagree with one another immediately after bootstrap.

**Rationale**

The install path is not successful if the initial state is already incoherent.

**Related truth surfaces**

- routing_truth
- execution_alignment_truth

**Failure class if broken**

- INSTALL_BOOTSTRAP_GAP
- STATE_DRIFT

**Validating kill tests**

- KT-01
- KT-14
