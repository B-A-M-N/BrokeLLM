# Runtime Evidence Supplement

**Generated:** 2026-04-04  
**Purpose:** Document actual kill test execution outcomes that provide runtime proof beyond artifact scaffolding  
**Status:** Supplemental to Phase 5 (Invariants & Kill Test Design)

## Executive Summary

Executed **2 kill tests** out of 14 defined:

- **KT-06 (Floating Alias Drift): FAIL** ❌ — No warning surfaced when using non-pinned backend (`default` slot)
- **KT-08 (Provider-Direct Authority): PASS** ✅ — Authority expansion denied without `--elevated`

These results provide **concrete runtime evidence** that:
1. Confirms one expected boundary (provider-direct elevation gate)
2. Identifies a concrete missing warning (floating alias drift risk not surfaced)

## Detailed Execution Log

### 2026-04-04 — Kill Test Execution Session

**Environment:**
- Repo: `/home/bamn/BrokeLLM`
- CLI: `broke` (v1 development state)
- Runtime: Gateway not running (health: gateway not reachable)
- State: `.mapping.json` contains `default` slot without `pinned: true`

#### KT-06 — Floating Alias Drift

**Procedure:**
```bash
broke route default
broke explain default
```

**Expected:** Warning about floating alias / non-pinned backend drift risk

**Observed:**
```
$ broke route default
  would route to:
    primary       : Groq/Compound  (groq/groq/compound)
    health        : gateway not reachable
  (no warning)

$ broke explain default
  slot          : default
  selected      : Groq/Compound
  backend       : groq/groq/compound
  fallback chain: none
  (no warning)
```

**Conclusion:** The system does **not** surface any drift warning for using a non-pinned (`default`) slot. This is a **DOC_TRUTH_GAP** if documentation claims such warnings exist, or a **missing feature** if not claimed but expected from invariant INV-01.2 (canonical route identity with drift detection).

**Impact domains:**
- TRUTH: observability mismatch (route/explain missing warnings they should show)
- DOC: user-facing documentation about floating alias risk is not matched by behavior
- STATE: drift detection incomplete

---

#### KT-08 — Provider-Direct Worker Authority Expansion

**Procedure:**
```bash
broke harness run --worker-route provider_direct
```

**Expected:** Denial with clear message when `--elevated` flag not present

**Observed:**
```
$ broke harness run --worker-route provider_direct
[harness] provider_direct worker runs require --elevated
```

**Conclusion:** Authority expansion denial is **working as designed**. The boundary is explicit and enforced. **PASS**.

**Impact domains:**
- INV-04.2 (authority expansion denial) — **confirmed VALID**
- HARNESS_AUTHORITY — strengthens CONDITIONAL → VALID for expansion-denial subdomain

---

## Evidence Artifacts

- Command outputs recorded in this document
- Exit codes and error messages captured
- System state inspected (`broke list`, `broke doctor`, `cat .mapping.json`)

## Implications for Final Truth Adjudication

### Items That Should Be Downgraded or Confirmed

| Domain | Current Verdict | New Evidence | Recommended Action |
|--------|-----------------|--------------|-------------------|
| harness_authority | CONDITIONAL | KT-08 PASS confirms expansion denial | Consider upgrading to VALID for authority-expansion subdomain |
| observability | INVALID | KT-06 FAIL adds another missing-observable case (floating alias drift) | INVALID stands, evidence strengthened |

### Items That Need More Evidence

- **execution_alignment** (KT-07 not yet run)
- **credential_isolation** (KT-03, KT-04 not run)
- **sandbox_runtime_boundary** (KT-11 not run)
- **freeze_enforcement** (KT-09 not run)
- **snapshot_restore** (KT-10 not run)

## Next Execution Priorities

1. **KT-12** — State Manipulation Sanity (state-mutating but safe to test)
2. **KT-14** — Launch Preflight Integrity Break (introduce tampering to verify blocking)
3. **KT-07** — Execution Mismatch (requires request interception capability)

These would provide evidence for:
- state truth (INV-03.2, INV-05.2, INV-08.3)
- install/bootstrap integrity (INV-07.1, INV-07.2, INV-09.1, INV-09.2)
- execution alignment (INV-01.1, INV-02.1, INV-02.2)

## Caveats

- Only 2 of 14 kill tests executed so far
- Most remaining tests are destructive, concurrency-heavy, or require adversarial setup
- These results do NOT change the overall INVALID verdict (drift in observability and freeze enforcement remain)
- The PASS for KT-08 is a strong positive; the FAIL for KT-06 is a weak negative (missing feature, not active violation)

## Recommendation

This runtime evidence supplement should be attached to the milestone audit as ** Nyquist validation material**. The kill test execution record proves that at least one authoritative boundary (provider-direct elevation) is enforced, while also surfacing a missing observability (floating alias warning).
