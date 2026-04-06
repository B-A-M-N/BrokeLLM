# Broke Harness Specs

- [Core](./CORE.md): general harness runtime, independent of any workflow system
- [Code](./CODE.md): coding-specific specialization and doctrine family on top of the core
- [GSD](./GSD.md): workflow adapter/overlay family for GSD on top of core + code
- [Hardening](./HARDENING.md): hostile-environment validation matrix and proof standard
- [Lane Checklist](./LANE-CHECKLIST.md): persistent lane/session model, evidence contract split, and degraded review-lane requirements
- [ACP Lane Spec](./ACP-LANE-SPEC.md): BrokeLLM-owned ACP session, event, runtime-binding, and lane-result contract
- [PTY Supervisor Contract](./PTY-HARDENING.md): terminal supervision semantics, signal model, and lifecycle invariants
- [Gemini ACP Acceptance](./GEMINI-ACP-ACCEPTANCE.md): promotion gate for Gemini as an ACP-backed node

## Clean Boundary

Each layer answers a different question:

- Core: how is work governed at runtime?
- Code: what kind of software work is being performed, and what evidence posture governs it?
- GSD: what extra governance pressure applies when the task came from GSD?

Dependency direction:

```text
Harness Core
   ↑
Code Doctrine
   ↑
GSD Overlay
```

Core owns runtime governance.

Code owns software-work semantics and doctrine families.

GSD owns workflow-specific governance overlays and overlay families.

## Selection Model

The intended runtime composition is:

```yaml
core_profile: balanced | high_assurance
code_doctrine: implement | brownfield_audit | debug_incident | refactor_migrate | spec_conformance
gsd_overlay: null | execution | brownfield_strict | closure | recovery_drift
```

Example:

```yaml
core_profile: high_assurance
code_doctrine: brownfield_audit
gsd_overlay: brownfield_strict
```
