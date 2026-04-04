# BrokeLLM Brownfield Audit

## What This Is

A full-spectrum adversarial audit of BrokeLLM — a local control plane for model-slot routing, fallback management, provider switching, mediated harness execution, sandboxed client launching, and live key/model policy mutation across CLI coding tools. This audit determines what the system actually does vs. what it claims to do, producing a structured brownfield truth package that enterprise evaluators, hostile maintainers, or future governed harnesses can use for adjudication.

## Core Value

Evidence over declaration: every claimed capability must be traced to code, tests, and runtime behavior — unverifiable claims must be downgraded, proven claims validated, and gaps documented with structured remediation.

## Context

BrokeLLM is a brownfield Python project with documentation (ARCHITECTURE.md, README.md), harness components, skills, tests, vendor dependencies, and an install/bootstrap pipeline. The system claims extensive capabilities across routing, observation, security isolation, sandbox profiles, harness mediation, key/model orchestration, snapshot/freeze controls, provider switching, and supply-chain guarantees.

The audit must determine which claims are **VALID**, **CONDITIONAL**, or **INVALID** through code tracing, test coverage analysis, and runtime verification.

## Constraints

- **Evidence-first**: No claim is trusted based on documentation alone — must be traced in code and optionally proven at runtime
- **Brownfield audit, not greenfield** — discover before judging, enumerate before classifying
- **12 required artifact files** must be produced under `.planning/brownfield-audit/`
- **14 kill tests** are specified in the audit specification for adversarial verification
- **15+ truth surfaces** must each be individually adjudicated

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Quality model profile for planning agents | Audit requires deep analysis; opus for research/roadmap | Opus for agents |
| Research before planning each phase | Brownfield audit benefits from domain investigation into testing patterns, adversarial approaches, and verification techniques | Enabled |
| Plan checker enabled | Audit plans must be verified will achieve audit goals before execution | Enabled |
| Verifier enabled | Each audit phase must deliver its artifact outputs correctly | Enabled |
| Parallel execution | Independent audit phases (different artifact types) can proceed simultaneously | Enabled |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---

*Last updated: 2026-04-04 after initialization*
