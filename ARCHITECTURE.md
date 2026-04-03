# BrokeLLM Control Plane

## Purpose

BrokeLLM routes Claude-style slots such as `sonnet`, `opus`, and `haiku` through a LiteLLM gateway backed by multiple providers. The critical requirement is that every control-plane surface reports the same truth about routing, health, and drift.

## Truth Boundary

The control plane has one normalization boundary in [bin/_mapping.py](/home/bamn/BrokeLLM/bin/_mapping.py):

- `_entry_identity(entry)` produces the canonical backend identity as `provider/model`.
- `_backend_catalog_entry(entry)` maps an active route back to the static backend catalog.
- `_entry_pin_state(entry)` resolves whether a route is pinned, floating, or unknown.
- `_fetch_health_index()` and `_entry_health_status()` normalize LiteLLM `/health` responses before any command compares backend health.

Every truth surface must consume these helpers instead of inventing its own comparison logic. That includes:

- `doctor`
- `route`
- `explain`
- `validate`

If a new command needs to reason about backend health or drift, it should use the shared helpers rather than comparing labels or raw fields directly.

## State Contracts

The active runtime state lives in generated files such as `.mapping.json`, `.teams.json`, `.profiles.json`, `config.json`, and `.env.claude`.

Important invariants:

- `pinned` is persisted on active mappings so drift risk is not silently lost during `swap`.
- Access limits distinguish explicit zero from omission.
- `None` means "leave unchanged" on update paths.
- `0` means "unlimited" for rpm and tpm limits.
- Positive integers mean "set the limit".

## Verification Path

The default verification path is:

```bash
make verify
```

That currently runs:

```bash
python3 -m unittest -v tests/test_mapping.py
```

These tests cover the control-plane behaviors that previously drifted:

- health agreement across `doctor`, `route`, and `explain`
- `swap` preserving `pinned`
- floating alias warnings after swap
- zero/unlimited access semantics
- installer interpreter consistency
- Gemini env-name consistency

## Release Checkpoints

This workspace is currently not a git repository, so git tags are not available here. Use a repo-local release marker until the project is moved under version control.

