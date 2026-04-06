# Harness Lane Checklist

This checklist defines the minimum implementation bar for the review-lane control plane.

All items below are now implemented in the core harness:

- Persistent lane instances
  Durable `worker`, `verifier`, and `adversary` lane records exist in harness state with identity, binding, health, counters, and latest contribution pointers.

- Lane session continuity
  Each lane has a durable logical session id independent of whether its backend runtime is ephemeral or persistent.

- Normalized evidence classes
  Harness evidence packets store typed observation artifacts for task, diff, tests, commands, policy events, and retry history.

- Observation / inference split
  Observation artifacts are stored separately from derived evidence summaries so review lanes do not consume mixed truth levels as one blob.

- Verdict contribution records
  Each lane writes an explicit contribution object containing source, health, request hash, confidence, supportedness, and recommended verdict.

- Degraded review-lane policy
  Review-lane degradation is part of verdict algebra, not an implicit operational side note.

- Operator checklist surface
  `broke harness checklist` and `broke harness status` expose the checklist in the control plane.

The intended architectural split is:

- Persistent managed lane/session objects in BrokeLLM
- Backend-specific runtime bindings per execution
- Ephemeral model calls for most review lanes
- Persistent live runtime only where the controlled session itself requires it
