# PTY Supervisor Contract

## Purpose

This document defines the production semantics for BrokeLLM's PTY supervisor layer.

`_pty_harness.py` is not just terminal glue.
It is a runtime supervisor responsible for terminal ownership, signal routing, lifecycle truth, and operator control.

If this layer lies about session state, foreground ownership, or process-tree control, the harness becomes untrustworthy even if the rest of the policy stack looks correct.

## Core Model

The PTY supervisor is the authoritative controller for one interactive harnessed run.

A run under PTY supervision has these control objects:

- `supervisor_pid`: the BrokeLLM PTY supervisor process
- `child_pid`: the launched CLI process
- `pgid`: the process group that receives interrupt/terminate semantics
- `session state`: durable lifecycle fact written into run-local state files
- `control channel`: operator/governor requests written to `state/control.json`
- `transcript`: PTY byte stream captured to `artifacts/pty-output.log`

## Invariants

These are required semantics, not implementation suggestions.

1. A run has at most one active PTY supervisor.
2. A live operator action must target the expected supervisor/child identity pair.
3. `Interrupt` targets the controlled execution group, not an arbitrary stale PID.
4. `Kill` must attempt full process-group termination before falling back to narrower control.
5. A dead session must not accept live operator control actions.
6. Transcript bytes are evidence, not authority, for lifecycle truth.
7. Durable session state outranks optimistic ledger state.
8. Reconciliation must converge to one terminal truth after abnormal termination.

## Signal Semantics

Operator actions are process-control semantics.

### Interrupt

Definition:
- sends `SIGINT` to the controlled target
- intended meaning: stop current foreground work without declaring the run dead

Required behavior:
- target the controlled process group when available
- record the action durably
- remain coherent if the child exits concurrently
- preserve terminal-control correctness when supervisor-side terminal signals are in play

### Kill

Definition:
- sends `SIGTERM` to the controlled target
- after grace timeout, escalates to `SIGKILL`

Required behavior:
- target the process group first
- escalate deterministically after grace period
- record whether kill completed, escalated, or missed because the process was already gone

### Resume

Definition:
- clears current intervention state and reopens normal work only if the run is still live

Required behavior:
- reject resume against dead or mismatched sessions
- not silently invent liveness
- preserve reconciliation truth if resume arrives after exit

## Terminal State

The supervisor is responsible for terminal-adjacent state, not just child lifecycle.

Minimum required behavior:

- copy initial window size into the supervised PTY when possible
- propagate terminal resize events into the PTY session
- restore supervisor-side tty mode on exit
- avoid supervisor suspension from `SIGTTOU` / `SIGTTIN` during terminal-control operations
- degrade to `stdin detached` rather than tearing down a live child just because operator input disappeared

## Evidence Classes

The PTY transcript is not full truth.

The supervisor layer must keep these evidence classes distinct:

1. `PTY transcript`
- bytes seen crossing the terminal boundary
- useful for operator context
- not authoritative for exec/process truth

2. `Operator action facts`
- control action ID
- requested action
- targeted supervisor/child identity
- acceptance or rejection result

3. `Session lifecycle facts`
- child PID
- supervisor PID
- session status
- exit code when known
- time of completion/interruption if available

4. `Process-control facts`
- signal target type used (`process_group`, `process`, `missing`)
- escalation to `SIGKILL` when needed

5. `Governor facts`
- verification-only mode
- intervention status
- next required action

A verdict or dashboard summary must not collapse these into one undifferentiated event stream.

## Transport Split

PTY is presentation, not protocol.

The authoritative transport model is:

1. `PTY transcript`
- human-visible interaction only
- advisory evidence

2. `Run channel`
- structured machine-message transport
- monotonic `msg_seq`
- integrity chaining via `prev_hash` / `hash`
- used for control-plane facts and machine-readable session semantics

3. `Event ledger`
- append-only audit ledger
- broader governance/evidence trail
- may mirror channel facts, but does not replace framing semantics

The supervisor layer must not infer authoritative machine messages from PTY bytes.

## Reliability Rules

The PTY supervisor must behave safely under ugly lifecycle conditions.

Required posture:

- partial or corrupt control payloads are ignored safely
- duplicate control actions are idempotent
- stale control actions for the wrong session identity are rejected
- dead sessions do not present as live
- stale ledger records reconcile to terminal truth
- process-group termination is preferred over child-only termination

## Known Non-Goals

This document does not claim:

- token-by-token control of model reasoning
- complete exec lineage from PTY transcript alone
- universal portability across all Unix-like environments

The supervisor governs runtime control, not hidden model cognition.

## Required Kill Tests

### Correctness

1. signal prefers process group over direct child
2. kill escalates from `SIGTERM` to `SIGKILL`
3. dead sessions reject interrupt/resume/kill
4. stale control payloads do not hit restarted sessions

### Reliability

1. invalid `control.json` is ignored
2. invalid intervention payload is ignored safely
3. duplicate action markers are idempotent
4. stale running ledger reconciles to non-live truth
5. failed launch reconciles deterministically
6. stdin loss degrades to detached supervision instead of forced child teardown

### Control Authority

1. real process-group termination test against a forked child tree
2. verification-only mode constrains further mutating work
3. operator interrupt changes supervised outcome, not just log output
4. resize propagation updates live PTY session metadata

### Evidence Integrity

1. PTY output can be tailed without defining lifecycle truth
2. operator actions include target identity
3. session state survives transcript ambiguity

## Operational Interpretation

The correct way to describe `_pty_harness.py` is:

> A small terminal supervisor with explicit control semantics, durable state, and process-group authority requirements.

The incorrect way to describe it is:

> A wrapper that starts a CLI and logs terminal output.

## Exit Criteria

The PTY layer may be described as production-hardened only when:

1. process-group semantics are the default control path
2. operator actions are identity-bound and idempotent
3. dead-session truth wins over stale ledger state
4. kill/interrupt behavior is proven against real subprocess trees
5. transcript, lifecycle, and control evidence remain distinct in the control plane
