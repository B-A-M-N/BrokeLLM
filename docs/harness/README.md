# Broke Harness Specs

- [Core](./CORE.md): general harness runtime, independent of any workflow system
- [Code](./CODE.md): coding-specific specialization and doctrine family on top of the core
- [GSD](./GSD.md): workflow adapter/overlay family for GSD on top of core + code

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
