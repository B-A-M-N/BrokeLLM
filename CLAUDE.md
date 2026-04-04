<!-- GSD:project-start source:PROJECT.md -->
## Project

**BrokeLLM Brownfield Audit**

A full-spectrum adversarial audit of BrokeLLM — a local control plane for model-slot routing, fallback management, provider switching, mediated harness execution, sandboxed client launching, and live key/model policy mutation across CLI coding tools. This audit determines what the system actually does vs. what it claims to do, producing a structured brownfield truth package that enterprise evaluators, hostile maintainers, or future governed harnesses can use for adjudication.

**Core Value:** Evidence over declaration: every claimed capability must be traced to code, tests, and runtime behavior — unverifiable claims must be downgraded, proven claims validated, and gaps documented with structured remediation.

### Constraints

- **Evidence-first**: No claim is trusted based on documentation alone — must be traced in code and optionally proven at runtime
- **Brownfield audit, not greenfield** — discover before judging, enumerate before classifying
- **12 required artifact files** must be produced under `.planning/brownfield-audit/`
- **14 kill tests** are specified in the audit specification for adversarial verification
- **15+ truth surfaces** must each be individually adjudicated
<!-- GSD:project-end -->

<!-- GSD:stack-start source:STACK.md -->
## Technology Stack

Technology stack not yet documented. Will populate after codebase mapping or first phase.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
