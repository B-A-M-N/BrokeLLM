# ACP Hardening Checklist

This is the practical hardening list for BrokeLLM's ACP harness plane.

The goal is not to assume vendor runtimes are fully trustworthy.
The goal is to make BrokeLLM fail closed when transports drift, stall, or lie.

## Core Rules

- ACP remains harness-scoped by default.
- BrokeLLM owns session truth, not provider-native runtime state.
- Unknown transport behavior degrades or blocks; it does not silently pass through.

## Implemented

- Runtime capability metadata is persisted per session.
- Startup canary state is persisted per session.
- Watchdog metadata is persisted per session.
- Cancel semantics are explicit per runtime:
  - `native_transport`
  - `turn_interrupt`
  - `signal`
  - `logical`
- Headless providers use persistent logical sessions with ephemeral calls.
- `heartbeat` can return watchdog and capability state for a session.

## Still Required

- Runtime version capture and allow/deny pinning.
- Capability negotiation against provider version drift.
- Automatic stale-runtime quarantine after repeated failures.
- Startup auth canary for every live runtime before accepting work.
- Provider-specific retry budgets and restart backoff.
- Event replay / idempotence across process restarts.
- Artifact binding for streamed deltas and partial outputs.
- Operator-facing "transport degraded" / "quarantined" UI state in the dashboard.
- Release-gated compatibility matrix by provider, auth mode, cancel mode, and session continuity.

## Deployment Order

1. Startup canary and watchdog state
2. Runtime version pinning and compatibility gates
3. Quarantine and restart budgets
4. Replay / idempotence
5. UI surfacing and operator controls

## Production Stance

- Gemini ACP should be treated as usable but still drift-prone.
- Codex app-server should be treated as useful but experimental.
- Claude CLI adapter should be treated as adapter-backed, not protocol-native.
- Headless providers should be treated as synthetic ACP lanes, not native agents.
