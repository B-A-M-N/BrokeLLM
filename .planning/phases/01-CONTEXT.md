# Phase 1: Repo Discovery & Ground Truth Bootstrap — CONTEXT.md

## Phase Goal

Discover and enumerate all executable entrypoints, CLI command surfaces, runtime control surfaces, integration paths, state files, and trust boundaries before adjudicating anything.

## Decisions

### Discovery Depth

- **Deep function tracing + top-level boundary audit** — both. Map all CLI commands, state files, trust boundaries, integration entrypoints, AND follow code paths from dispatch to deepest internals. Don't stop at CLI wrappers.
- **All code equally** — no domain prioritization during tracing. Every domain (routing, harness, security, sandbox, policy, observability, install) gets equal discovery depth.

### Runtime Probes & Kill Tests

- **Full runtime probe pass** — execute `broke status`, `broke route`, `broke doctor`, and observe actual proxy behavior. Run all 14 kill tests at full force during Phase 1 (accelerated from original Phase 5 placement).
- **Non-destructive kill tests only** — read-only probes and safe state checks. Do NOT mutate `.mapping.json`, `.snapshots`, `.deployments.json`, freeze state, or runtime config during discovery. Kill tests that require destructive state mutation (snapshot restore, freeze block testing, sandbox escape probing) should be flagged as executable-only-in-Phase-5 and deferred.
- Kill tests to flag for Phase 5: KT-01 (mapping drift mutation), KT-02 (policy race via mutation), KT-09 (freeze enforcement), KT-10 (snapshot truth), KT-11 (strict sandbox escape), KT-12 (invalid model fail-closed — may be non-destructive, check), KT-13 (invalid auth repetition — may be non-destructive), KT-14 (preflight integrity break)
- Kill tests potentially safe for Phase 1: KT-05 (fallback failure — depends on how primary is marked unhealthy), KT-06 (floating alias drift — depends on how drift is induced), KT-07 (execution mismatch — read-only if we can intercept without mutating), KT-08 (provider-direct without elevation — should be safe as a read test)

### Output Artifacts

- **Both artifacts** — Phase 1 produces:
  1. A detailed CONTEXT.md (this file) for downstream phases with full discovery findings
  2. A SYSTEM_SURFACE_MAP.md skeleton in `.planning/brownfield-audit/` that subsequent phases fill in

### Core Concerns

User is most concerned about:
1. Security isolation — credential leakage, sandbox escapes, secret injection
2. Truth boundary splits — route/explain/doctor showing different backends, config drift
3. Harness authority — block semantics, elevation gating, provider-direct worker without elevation

These domains should receive extra scrutiny during discovery but not at the expense of equal coverage.

## Codebase Observations

- Extensive runtime state files present: `.mapping.json`, `.deployments.json`, `.key_state.json`, `.model_policy.json`, `.model_state.json`, `.profiles.json`, `.teams.json`
- Harness state: `.harness_active_run.json`, `.harness_evidence_cache.json`, `.harness_prefix_cache.json`, `.harness_prompt_contracts.json`, `.harness_review_cache.json`, `.harness_runs.json`, `.harness_state.json`
- Token files: `.broke_client_token`, `.broke_internal_token`, `.env`, `.env.claude`, `.env.template`
- Audit log: `.launch_audit.log`
- State directories: `.runtime/`, `.snapshots/`, `.gemini_security/`
- Security artifacts: `.pth.allowlist`, `.provider`
- Documentation: `ARCHITECTURE.md`, `README.md`, `CHECKPOINT.md`, `HARNESS_ASSESSMENT.txt`
- Runtime logs: `broke-proxy.log`, `litellm.log`
- Key rotation state: `.rotation.json`, `.rotation.log`

## Canonical Refs

- `README.md`
- `ARCHITECTURE.md`
- `config.json`
- `bin/` — all entrypoint scripts
- `Makefile`
- `install.sh`
- `requirements.txt`
- `requirements.lock`
- `docs/` — all documentation files
- `HARNESS_ASSESSMENT.txt`
- `HUMAN_ONLY/` — human-only documentation files

## Deferred Ideas

(Empty — no scope creep detected)

## Requirements for This Phase

- DISC-01 through DISC-07 (all discovery requirements)

---

*Context created: 2026-04-04 during /gsd:discuss-phase 1*
