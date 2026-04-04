# Broke Harness Core

## Purpose

Broke Harness Core is a general-purpose governed execution layer for CLI agents.

It is independent of:

- any planning framework
- any repo methodology
- any single provider
- any single client

It consumes a **Run Contract**, not a planning system.

## Identity

Broke Harness Core owns:

- process launch
- execution policy
- credential-plane separation
- runtime evidence collection
- checkpoint admission
- completion adjudication
- replayable run ledgering

It does not assume:

- phases
- milestones
- roadmap artifacts
- GSD
- coding-specific verification by default

## Run Contract

A run contract is the neutral input object the harness operates on.

It contains:

- task descriptor
- runtime mode
- policy profile
- risk tier
- authority boundary
- credential lane policy
- checkpoint policy
- retry budget
- escalation policy

### Minimal schema

```json
{
  "task_source_type": "manual",
  "task_source_ref": null,
  "upstream_adapter": "none",
  "runtime_mode": "harness",
  "policy_profile": "balanced",
  "risk_tier": "medium",
  "sandbox_profile": "strict",
  "workspace_root": "/workspace",
  "allowed_paths": ["/workspace"],
  "verification_requirements": [],
  "roles": {}
}
```

## Core Axes

- `RuntimeMode`: `router | cli | harness`
- `InferencePath`: `broke_router | provider_direct | mixed`
- `CredentialSource`: `broke_managed | provider_managed | none`
- `ModelRole`: `worker | verifier | adversary | remediator | operator_assist`
- `PolicyProfile`: `throughput | balanced | high_assurance`
- `RiskTier`: `low | medium | high | critical`
- `SandboxProfile`: `normal | hardened | strict`

## Doctrine Resolution

Core owns doctrine resolution, not doctrine content.

The harness should resolve a runtime stack like this:

```yaml
core_profile: high_assurance
code_doctrine: brownfield_audit
gsd_overlay: brownfield_strict
```

Or:

```yaml
core_profile: balanced
code_doctrine: implement
gsd_overlay: execution
```

Or:

```yaml
core_profile: high_assurance
code_doctrine: debug_incident
gsd_overlay: null
```

Core does not define what those doctrines mean in domain terms. It defines the selection model and precedence model.

## Doctrine Precedence

Dependency direction:

```text
Harness Core
   ↑
Code Doctrine
   ↑
GSD Overlay
```

Precedence rules:

1. Core invariants always apply.
2. A selected Code doctrine defines the software-work posture.
3. A selected GSD overlay may tighten or enrich the active Code doctrine.
4. A GSD overlay must not weaken Core invariants.
5. If Code and GSD conflict, the stricter rule wins unless it violates Core portability guarantees.

Core therefore owns:

- doctrine selection
- doctrine composition
- doctrine precedence
- fail-closed handling for invalid doctrine stacks

## Credential Planes

- Agent Runtime Plane
- Harness Review Plane
- Operator Plane

Doctrine:

> Worker plane never receives provider-direct credentials by default.

## Runtime Responsibilities

The core harness mediates:

1. run registration
2. launch-time env planning
3. sandbox/profile selection
4. command/tool mediation
5. evidence capture
6. checkpoint opening
7. review orchestration
8. verdict enforcement

### Execution control surface

Core owns:

- launch mediation
- process/session wrapping
- env injection per plane
- sandbox profile
- command interception hooks
- filesystem and network policy surfaces
- artifact capture

## Role System

Core defines general roles only:

- worker
- verifier
- adversary
- remediator
- operator assist

Core does not define domain-specific review criteria for those roles.

## Evidence Framework

Core owns the generic evidence model:

- event ledger
- artifact references
- checkpoint snapshots
- review packets
- review results
- verdict reasons

## Checkpoints

Completion is never accepted as a self-reported fact.

Completion is treated as a checkpoint trigger:

- completion proposal
- high-risk change
- verification state change
- retry boundary
- manual review

## Verdict Algebra

- `ACCEPT`
- `ACCEPT_WITH_WARNINGS`
- `RETRY_NARROW`
- `RETRY_BROAD`
- `ESCALATE`
- `BLOCK`

Core doctrine:

> Deterministic evidence overrides model opinion.

## Event Model

The core harness is event-sourced.

Primary event families:

- `run.registered`
- `agent.launched`
- `env_plan.applied`
- `command.started`
- `command.completed`
- `policy.denied`
- `checkpoint.opened`
- `review.requested`
- `review.completed`
- `verdict.issued`
- `retry.dispatched`
- `model_route.changed`
- `policy.changed`
- `authority.expansion_denied`
- `run.completed`

## Review System

The core supports role-separated review:

- worker
- verifier
- adversary

And cache layers for:

- prompt contracts
- resolved prefixes
- normalized evidence
- review results
- checkpoint verdict reuse

## Authority Invariants

1. Worker using `broke_router` must use `broke_managed` credentials.
2. Provider-direct review credentials may exist only in the harness review plane.
3. Authority-expanding route/auth changes require validation and event emission.
4. Env injection is plane-specific, never ambient.

## Adapters

The core is adapter-friendly.

Task sources can include:

- manual CLI use
- file input
- API input
- CI jobs
- workflow adapters like GSD

Adapters transform upstream workflow context into a neutral run contract.

## Runtime Selection Objects

Core should be able to represent:

- `CoreProfileSelection`
- `CodeDoctrineSelection`
- `GsdOverlaySelection`
- `DoctrineResolution`
- `DoctrineConflict`

## Core Objects

- `RunContract`
- `ExecutionPolicy`
- `RoleExecutionPolicy`
- `CredentialLease`
- `EnvInjectionPlan`
- `Checkpoint`
- `EvidenceArtifact`
- `ReviewRequest`
- `ReviewResult`
- `Verdict`
- `HarnessEvent`

## Core Does Not Own

Core does not decide:

- what a good code fix is
- what tests should exist
- what GSD truth means
- what repo diff patterns are suspicious
- what plan verification artifacts should be present

Those belong in higher layers.
