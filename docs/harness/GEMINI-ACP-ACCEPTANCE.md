# Gemini ACP Acceptance Matrix

## Decision

- `CONDITIONAL GO` for Gemini as an ACP-backed node.
- `NO-GO` for Gemini as a PTY-framed persistent node.

## Why

Gemini CLI exposes an ACP server over stdio using newline-delimited JSON-RPC.
That is the only serious machine-control surface for long-lived governed use.

PTY remains:

- operator-facing
- debugging-friendly
- non-authoritative for structured control truth

## BrokeLLM Invariants

For Gemini to count as a trustworthy Broke node, all of these must hold:

1. Transport truth
- ACP is the authoritative machine channel.
- PTY transcript is advisory evidence only.
- Non-JSON stdout contamination degrades the run immediately.

2. Session truth
- One Broke run maps to:
  - ACP process pid
  - Gemini ACP session id
  - Broke run id
  - active mode / permission state

3. Authority truth
- File and tool authority are mediated by Broke policy, not trusted from Gemini by default.
- ACP/MCP mediation is preferred over raw local freedom.

4. Failure truth
- Timeouts, malformed stream output, session drift, missing tool results, and repeated upstream rate-limit failures must mark the run degraded or blocked.

## Required Acceptance Tests

1. Initialize
- `initialize` returns protocol version and agent capabilities
- stdout remains JSON-only during startup

2. Session lifecycle
- `session/new`
- `session/load`
- repeated prompt turns in one session
- session mode changes
- cancel behavior

3. Stream integrity
- reject plain-text stdout contamination
- reject malformed JSON frames
- preserve request/response correlation by id

4. Policy / authority
- Broke can gate mode changes
- Broke can map ACP sessions into run ledger state
- Broke can degrade the run on ACP integrity failure

5. Upstream risk checks
- repeated prompt turns do not silently merge or vanish
- tool-call hangs are surfaced as failure, not success
- host-interaction gaps are explicitly degraded, not ignored

## Promotion Rule

Gemini should stay `experimental` in BrokeLLM until:

- ACP initialize/session/prompt sequences are stable under repeated use
- stream corruption is handled fail-closed
- session identity is durably bound into the run ledger
- degraded-mode behavior is implemented and tested
