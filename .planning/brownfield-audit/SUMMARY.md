# BrokeLLM Brownfield Audit Summary

**Generated:** 2026-04-04  
**Phase:** 8  
**Method:** Summary from final adjudication and risk artifacts

## Overall Result

BrokeLLM is a real governed execution system with meaningful routing, policy, harness, and sandbox machinery, but the final audit result is **INVALID overall** because the current evidence base still contains direct truth-boundary failures plus several high-impact conditional security and runtime gaps.

## Strongest Valid Areas

- `routing`
  - route identity normalization is strong and route/explain agreement is well evidenced

## Invalid Domains

- `observability`
  - `doctor` disagrees with `route/explain` on live health interpretation
- `freeze_enforcement`
  - freeze semantics overclaim the actual mutation boundary
- `truth_boundary_consistency`
  - the control plane cannot claim a consistent truth boundary while major health surfaces disagree
- `overall`
  - invalid because these failures combine with unresolved high-impact conditional areas

## Highest-Impact Conditional Domains

- `execution_alignment`
  - control-plane choice vs actual forwarded target is only partially runtime-proven
- `harness_authority`
  - authority expansion denial is real, but full verdict semantics remain only partially proven
- `credential_isolation`
  - lane design exists, but adversarial leak probing is deferred
- `sandbox_runtime_boundary`
  - strict-mode hardening exists, but escape-resistance proof is deferred
- `key_orchestration` and `model_orchestration`
  - live generation isolation is not yet proven under concurrent request conditions
- `supply_chain` / `install_bootstrap`
  - hash-locked install intent is undermined by observed runtime drift

## Top Remediation Priorities

1. unify health truth across `doctor`, `route`, and `explain`
2. make freeze semantics match the actual mutation boundary or narrow the feature claim
3. prove end-to-end execution alignment
4. prove or harden credential-lane isolation and strict sandbox boundaries
5. prove generation isolation for live key/model policy mutation
6. restore runtime alignment with the hash-locked install baseline

## Bottom Line

The audit shows BrokeLLM has substantial real architecture and many meaningful controls, but it is not yet at a state where the full truth boundary, authority boundary, and runtime proof surfaces can be considered fully trustworthy. The main issue is not that the system is empty; it is that several of its most important guarantees are only partially proven, and a few are directly contradicted by current evidence.
