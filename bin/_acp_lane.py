#!/usr/bin/env python3
"""Canonical ACP lane contract for BrokeLLM-owned control planes."""

from __future__ import annotations

import copy

ACP_LANE_METHODS = [
    "initialize",
    "newSession",
    "loadSession",
    "closeSession",
    "prompt",
    "cancel",
    "setSessionMode",
    "getSessionState",
    "listArtifacts",
    "submitToolResult",
    "requestApproval",
    "heartbeat",
]

ACP_LANE_EVENTS = [
    "session.started",
    "session.loaded",
    "turn.started",
    "turn.delta",
    "turn.completed",
    "tool.requested",
    "tool.completed",
    "approval.requested",
    "approval.resolved",
    "artifact.created",
    "artifact.updated",
    "lane.degraded",
    "lane.blocked",
    "lane.timeout",
    "lane.cancelled",
]

RUNTIME_BINDINGS = [
    "native_acp",
    "cli_adapter",
    "headless_adapter",
]


def canonical_lane_result(role, provider="", runtime_binding="headless_adapter"):
    return {
        "lane_role": role,
        "status": "completed",
        "summary": "",
        "findings": [],
        "objections": [],
        "recommended_verdict": None,
        "confidence": None,
        "evidence_refs": [],
        "provider_metadata": {
            "provider": provider,
            "runtime_binding": runtime_binding,
        },
        "degraded": False,
        "degraded_reason": "",
    }


def default_runtime_registry():
    return {
        "gemini": {
            "binding_kind": "native_acp",
            "runtime_class": "GeminiNativeAcpRuntime",
            "session_persistence": "live_runtime",
            "native": True,
        },
        "claude": {
            "binding_kind": "cli_adapter",
            "runtime_class": "ClaudeAgentAcpShimRuntime",
            "session_persistence": "live_runtime",
            "native": False,
        },
        "codex": {
            "binding_kind": "cli_adapter",
            "runtime_class": "CodexAcpShimRuntime",
            "session_persistence": "live_runtime",
            "native": False,
        },
        "openrouter": {
            "binding_kind": "headless_adapter",
            "runtime_class": "OpenRouterHeadlessRuntime",
            "session_persistence": "logical_lane",
            "native": False,
        },
        "groq": {
            "binding_kind": "headless_adapter",
            "runtime_class": "GroqHeadlessRuntime",
            "session_persistence": "logical_lane",
            "native": False,
        },
        "cerebras": {
            "binding_kind": "headless_adapter",
            "runtime_class": "CerebrasHeadlessRuntime",
            "session_persistence": "logical_lane",
            "native": False,
        },
        "local": {
            "binding_kind": "headless_adapter",
            "runtime_class": "LocalHeadlessRuntime",
            "session_persistence": "logical_lane",
            "native": False,
        },
    }


def validate_lane_result(result):
    errors = []
    if not isinstance(result, dict):
        return ["lane result must be an object"]
    required = [
        "lane_role",
        "status",
        "summary",
        "findings",
        "objections",
        "recommended_verdict",
        "confidence",
        "evidence_refs",
        "provider_metadata",
        "degraded",
    ]
    for key in required:
        if key not in result:
            errors.append(f"missing field: {key}")
    if "findings" in result and not isinstance(result["findings"], list):
        errors.append("findings must be a list")
    if "objections" in result and not isinstance(result["objections"], list):
        errors.append("objections must be a list")
    if "evidence_refs" in result and not isinstance(result["evidence_refs"], list):
        errors.append("evidence_refs must be a list")
    if "provider_metadata" in result and not isinstance(result["provider_metadata"], dict):
        errors.append("provider_metadata must be an object")
    if "degraded" in result and not isinstance(result["degraded"], bool):
        errors.append("degraded must be boolean")
    return errors


def normalize_provider_output(role, payload, provider="", runtime_binding="headless_adapter"):
    result = canonical_lane_result(role, provider=provider, runtime_binding=runtime_binding)
    if isinstance(payload, dict):
        for key in result:
            if key in payload:
                if key == "provider_metadata" and isinstance(payload.get("provider_metadata"), dict):
                    merged = copy.deepcopy(result["provider_metadata"])
                    merged.update(payload.get("provider_metadata", {}))
                    result["provider_metadata"] = merged
                else:
                    result[key] = payload[key]
    errors = validate_lane_result(result)
    if errors:
        result["status"] = "failed_schema"
        result["degraded"] = True
        result["degraded_reason"] = "; ".join(errors)
    return result
