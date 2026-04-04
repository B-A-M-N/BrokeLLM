# Broke Harness Code Profile

## Purpose

The Code profile specializes Broke Harness Core for software development workflows.

It adds coding-specific semantics on top of the neutral runtime substrate.

This layer is where the harness becomes opinionated about:

- repos
- files
- tests
- builds
- typechecks
- diffs
- code-review evidence

## Scope

The Code profile is still workflow-agnostic.

It does not assume:

- GSD
- a specific planning framework
- phase/milestone semantics

It only assumes the run is about code or repo mutations.

## Doctrine Family

Code is not a single doctrine. It is a family of selectable software-work doctrines.

Recommended starting catalog:

- `implement`
- `brownfield_audit`
- `debug_incident`
- `refactor_migrate`
- `spec_conformance`

The active Code doctrine answers:

> What kind of software work is being performed, and what evidence posture should govern it?

## Doctrine Schema

Each Code doctrine should define:

- purpose
- mutation posture
- required evidence
- checkpoint triggers
- review doctrine
- failure classes
- exit criteria

Without those fields, a doctrine is just branding.

## Recommended Code Doctrines

### `implement`

- build or change behavior intentionally
- optimize for delivery correctness
- require standard verification and honest completion claims

### `brownfield_audit`

- run hostile truth classification against an existing codebase
- prioritize drift detection, adversarial verification, and evidence over declaration
- classify subsystems as `VALID`, `CONDITIONAL`, or `INVALID`

Typical concerns:

- truth surface enumeration
- invariant extraction
- adversarial kill tests
- drift mapping
- failure classification
- final truth adjudication

### `debug_incident`

- isolate faults before broad mutation
- preserve forensic evidence
- minimize speculative edits before root cause is known

### `refactor_migrate`

- preserve behavior while changing structure or platform
- require compatibility gates and semantic-equivalence evidence

### `spec_conformance`

- compare implementation to declared contract
- classify missing, partial, divergent, and extra behavior

## Additional Concepts

### File classes

- source
- test
- config
- docs
- generated
- restricted

### Verification classes

- tests
- lint
- typecheck
- build
- custom

### Coding checkpoint triggers

- completion proposal
- source file changed without verification
- high-risk file touched
- verification command completed
- no-material-change retry
- tests changed significantly
- broad diff for narrow task
- snapshot or mock changes

## Runtime Additions

The Code profile adds:

- workspace-aware allowed/denied paths
- touched-file classification
- command-class detection
- diff summary artifacts
- repo-aware verification expectations
- coding-specific anti-bullshit heuristics

## Workspace Semantics

The Code profile owns:

- repo/workspace root handling
- file classification
- source/test/config/docs/build buckets
- writable path expectations
- package manager and toolchain classification

## Command Mediation

Important tools should be shimmed or wrapped:

- `git`
- `pytest`
- `npm`
- `pnpm`
- `pip`
- `python`
- `python3`
- `node`
- `go`
- `cargo`
- `make`

Goals:

- structured telemetry
- policy enforcement
- evidence artifacts
- normalized verification results

## Evidence Artifacts

The Code profile normalizes and stores:

- diff summary
- touched file map
- command summary
- test result summary
- verification class summary
- retry summary
- assertion/mock/snapshot pattern summary

## Coding Bullshit Taxonomy

Examples:

- no-op fix
- partial fix overclaimed as complete
- broad refactor camouflage
- test-only patch when code fix was expected
- assertion weakening
- skip laundering
- snapshot laundering
- mock abuse
- fixture rigging
- bypass fallback logic

## Coding-Specific Review Questions

Verifier focuses on:

- task satisfaction
- evidence support
- verification sufficiency
- overclaim detection

Adversary focuses on:

- weak tests
- mock abuse
- assertion laundering
- snapshot laundering
- bypass fixes
- partial fixes dressed up as complete

## Brownfield Audit Doctrine

The `brownfield_audit` doctrine should treat the codebase as hostile until proven otherwise.

It should force evidence for:

- routing truth
- policy truth
- health truth
- harness verdict truth
- security boundary truth
- execution layer truth
- fallback resolution truth

It should require:

- hard invariants
- adversarial kill tests
- drift mapping
- failure classification
- final truth adjudication

This doctrine is the correct base layer for the BrokeLLM brownfield audit prompt. It belongs here, not as a separate top-level harness category.

## Coding Profile Objects

- `WorkspaceDescriptor`
- `FileClassification`
- `VerificationRequirement`
- `DiffSummary`
- `TouchedFileMap`
- `TestSummary`
- `CodeIssueClass`
- `CodingCheckpointTrigger`

## Default Code Policy

Recommended default profile:

```json
{
  "verification_requirements": {
    "must_run": ["tests"],
    "forbid_skips": true,
    "allow_test_only_change": false
  }
}
```

## Output

The Code profile should produce:

- live run state
- checkpoint evidence packet
- final run report
- artifact-backed verdict trail

## Relationship To Core

Core handles:

- general execution governance
- credential planes
- role routing
- verdict engine

Code profile adds:

- repo semantics
- coding verification semantics
- code-review evidence semantics
- selectable software-work doctrines

## Coding Profile Does Not Own

The Code profile does not define:

- GSD task semantics
- plan/truth artifacts
- milestone or phase logic
- GSD-specific evidence contracts

Those belong in the overlay.
