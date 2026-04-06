# BrokeLLM ACP Lane Spec

This spec defines the ACP-compatible contract that BrokeLLM owns.

The point is not to wait for every vendor to be natively ACP-first.
The point is to normalize all runtimes behind one session model, one event model,
one evidence model, and one lane result schema.

## Ownership Rule

BrokeLLM owns:

- ACP session truth
- lane identity and persistence
- event normalization
- evidence binding
- degraded-mode policy
- verdict algebra

Providers own only their runtime behavior behind the adapter boundary.

## Session Model

```text
ACP Session
  -> Lane Session
  -> Runtime Binding
```

- ACP Session is the operator-visible control-plane object.
- Lane Session is the durable logical role session BrokeLLM owns.
- Runtime Binding is provider-specific and may be live or ephemeral.

## Runtime Bindings

- `native_acp`
  Gemini-style runtime with real ACP session methods.

- `cli_adapter`
  Claude/Codex-style runtime normalized through a BrokeLLM adapter.

- `headless_adapter`
  OpenRouter/Groq/Cerebras/local API runtime with synthetic session semantics.

## Required Methods

- `initialize`
- `newSession`
- `loadSession`
- `closeSession`
- `prompt`
- `cancel`
- `setSessionMode`
- `getSessionState`
- `listArtifacts`
- `submitToolResult`
- `requestApproval`
- `heartbeat`

## Required Events

- `session.started`
- `session.loaded`
- `turn.started`
- `turn.delta`
- `turn.completed`
- `tool.requested`
- `tool.completed`
- `approval.requested`
- `approval.resolved`
- `artifact.created`
- `artifact.updated`
- `lane.degraded`
- `lane.blocked`
- `lane.timeout`
- `lane.cancelled`

## Canonical Lane Result

```json
{
  "lane_role": "verifier",
  "status": "completed",
  "summary": "",
  "findings": [],
  "objections": [],
  "recommended_verdict": "RETRY_NARROW",
  "confidence": 0.72,
  "evidence_refs": [],
  "provider_metadata": {
    "provider": "gemini",
    "runtime_binding": "native_acp"
  },
  "degraded": false,
  "degraded_reason": ""
}
```

## Adapter Rules

Every non-native runtime adapter must provide:

1. Session synthesis
   Durable logical lane history independent of provider persistence.

2. Schema enforcement
   Provider output must normalize into the canonical lane result or the lane is degraded.

3. Tool / approval mediation
   Tools and approvals flow through BrokeLLM-owned control semantics, not vendor-specific side channels.

4. Transport normalization
   Timeouts, retries, cancellation, and backoff become uniform control-plane facts.

5. Evidence binding
   Lane results cite evidence refs from the BrokeLLM evidence store.

## Degraded-Mode Rule

If a runtime times out, fails schema validation, rate limits, or returns unusable output:

- the lane becomes degraded
- the degraded reason is durable state
- the verdict engine treats degraded review lanes as an explicit category
- operator surfaces must show lane degradation directly

## Initial Runtime Registry

- `gemini` -> `GeminiNativeAcpRuntime`
- `claude` -> `ClaudeAgentAcpShimRuntime`
- `codex` -> `CodexAcpShimRuntime`
- `openrouter` -> `OpenRouterHeadlessRuntime`
- `groq` -> `GroqHeadlessRuntime`
- `cerebras` -> `CerebrasHeadlessRuntime`
- `local` -> `LocalHeadlessRuntime`
