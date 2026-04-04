# Phase 4: Function Inventory & Test Review - Research

**Generated:** 2026-04-04  
**Status:** Ready for planning  
**Method:** Manual fallback research because the local `get-shit-done` execution path still delegates into a broken runtime missing `pg`

## Research Objective

Answer: what must be understood to plan Phase 4 well?

Phase 4 is where the audit stops talking primarily in terms of surfaces and starts tracing actual function families. It must:

1. inventory the meaningful function families that make BrokeLLM work,
2. describe their inputs, state mutation, invariants, fail-open/closed behavior, and bypassability,
3. audit the test suite for nominal vs adversarial coverage,
4. identify which claims and domains still lack meaningful testing.

This phase is more implementation-granular than Phase 3, but it still should not expand into full invariant definition or kill-test design. Those belong in Phase 5.

## Strong Inputs Already Available

Phase 4 should reuse:

- `.planning/phases/01-CONTEXT.md`
- `.planning/brownfield-audit/_SYSTEM_SURFACE_MAP.md`
- `.planning/brownfield-audit/CLAIMS.yaml`
- `.planning/brownfield-audit/FEATURE_INVENTORY.yaml`
- `.planning/brownfield-audit/TRUTH.yaml`
- `.planning/brownfield-audit/INTEGRATION_MATRIX.yaml`
- `tests/test_mapping.py`

That means Phase 4 should not rediscover function existence from scratch. It should classify and connect already-surfaced implementation families.

## Function Family Baseline

The requirements already name the correct major families:

- command dispatch
- mapping resolution
- fallback selection
- health normalization
- route explanation
- doctor aggregation
- validation
- launch preflight
- client launch
- env scrubbing
- secret injection
- auth enforcement
- proxy forwarding
- LiteLLM bridging
- key/model policy resolution
- harness orchestration
- verdict handling
- ledger append
- checkpoint
- snapshot
- freeze
- persistence helpers
- sandbox setup
- audit logging
- install/bootstrap

The codebase structure supports grouping them by file ownership:

### `bin/broke`

- wrapper command dispatch
- gateway lifecycle
- sandbox profile control
- client launch mediation
- secret-file creation and env shaping
- provider selection

### `bin/_mapping.py`

- shared control-plane state loading/writing
- route/fallback explanation
- doctor/validate/preflight
- key/model policy and state
- team/profile CRUD
- snapshot/freeze-adjacent operations
- harness config/state/cache logic

### `bin/_proxy.py`

- auth enforcement
- request parsing
- model and key candidate preparation
- health/state normalization
- upstream forwarding
- rotation/state mutation

### support files

- `_harness_shim.py`: shim classification and path gating
- `_harness_common.py`: event hashing and append-only ledger writes
- `_socket_bridge.py`: strict-mode local bridge
- `_fs_common.py`: shared file locking

## Test Surface Reality

`tests/test_mapping.py` is broad but not balanced.

Current strengths:

- route/explain/doctor consistency
- swap/fallback behavior
- key/model policy and manual state paths
- harness verdict/cache behavior
- proxy auth and model rejection
- install/readme/doc regression checks
- snapshot round-trip basics
- team/profile CRUD basics

Current weaknesses:

- only one major test file
- little true integration coverage
- many runtime-forwarding cases still mocked
- no broad adversarial kill-test suite yet
- no load/perf coverage
- no real credential-leak or sandbox-escape probes

That means Phase 4 should classify test coverage conservatively by domain.

## Planning Implications

### A. Function inventory needs one stable record shape

Each function family should include:

- family name
- owned files/functions
- purpose
- inputs consumed
- state mutated
- invariants assumed
- source-of-truth or consumer-only role
- fail-open/fail-closed posture
- test coverage
- bypassability
- notable gaps

Without that schema, later invariant and remediation phases will become inconsistent.

### B. Phase 4 should evaluate mocks honestly

The test suite uses fakes and mocked HTTP connections in important places. That is not automatically bad, but the audit must ask:

- what risk is hidden by the mock?
- what claim is only indirectly tested?
- what runtime behavior is still unproven?

This matters most for:

- proxy forwarding
- upstream failures
- auth behavior
- health resolution
- harness runtime mediation

### C. Domain-level coverage judgment should sit alongside function families

Roadmap success criteria require judgments for:

- routing
- policy
- harness
- security
- sandbox
- execution alignment
- install/bootstrap
- snapshot/freeze
- client
- provider

That means the output should include a domain coverage summary, not just family-by-family notes.

## Highest-Priority Families To Trace Carefully

Based on current findings, the most important families are:

1. health normalization
   - because truth-surface mismatch is already observed
2. proxy forwarding and auth enforcement
   - because this is the execution and security choke point
3. launch preflight and client launch
   - because security and harness mediation depend on them
4. freeze and snapshot behavior
   - because current truth judgments already show likely invalid/conditional areas
5. harness orchestration, verdict handling, and ledger append
   - because harness identity is central to the system claims

## Boundaries For This Phase

Phase 4 should not:

- finalize the invariant catalog
- design all kill tests
- produce remediation ordering

It should:

1. trace function families,
2. audit tests honestly,
3. identify bypassability and coverage gaps,
4. hand clean evidence to Phase 5.

## Recommended Output Shape

This phase should produce:

- `FUNCTION_INVENTORY.md`

And inside it:

- family records
- test strategy review
- domain coverage judgments
- mock-risk notes
- uncovered-claim notes

## Conclusion

Phase 4 should be planned as a code-and-tests traceability phase.

The best execution shape is:

1. group the code into meaningful function families,
2. classify each family’s behavior and trust posture,
3. map tests to those families and domains,
4. produce conservative coverage judgments and explicit gaps.
