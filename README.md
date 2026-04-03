# BrokeLLM

**Local control plane for model-slot routing, fallbacks, and provider switching across CLI coding tools.**  
*Keep your client speaking in slots. Control what actually answers.*

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-brightgreen.svg)](https://www.python.org/)
[![LiteLLM](https://img.shields.io/badge/powered%20by-LiteLLM-orange.svg)](https://github.com/BerriAI/litellm)
[![Status](https://img.shields.io/badge/status-control--plane%20baseline-yellow.svg)]()

---

## The Problem

Most CLI coding tools assume stable access to expensive frontier models.

| Situation | The Failure Mode |
| --- | --- |
| **Single provider** | One outage, one price hike — your workflow stops |
| **Hand-editing configs** | Every backend swap requires touching LiteLLM config manually |
| **No fallback logic** | A dead route has no graceful alternative |
| **No routing visibility** | You don't know what's actually answering your slots |
| **Locked-in clients** | `claude`, `codex` assume *you* speak their model names |

> *"Most routing tools treat the client as the problem. BrokeLLM treats the routing layer as the solution."*

---

## The Solution

BrokeLLM puts a **local control plane** in front of multiple providers. Clients keep speaking in abstract slots — `sonnet`, `opus`, `haiku`, `default`, `subagent` — while you control which provider and model actually answers.

```
Claude/Codex CLI
       │
       ▼
    broke              ← control plane: routing, health, drift, fallback
       │
       ▼
 LiteLLM gateway       ← execution layer: enforces routing decisions
       │
       ▼
 selected backend      ← OpenRouter, Groq, Cerebras, GitHub Models, Gemini, HF
```

**One stable local interface. Backends become swappable.**

---

## Quickstart

```bash
git clone https://github.com/B-A-M-N/BrokeLLM.git
cd BrokeLLM
./install.sh
cp .env.template .env
broke doctor
broke list
```

> New to AI-assisted tools? See [`HUMAN_ONLY/FOR_BEGINNERS.md`](HUMAN_ONLY/FOR_BEGINNERS.md) for a beginner-facing guide.

---

## Client Support

| Client | Status | Notes |
| --- | --- | --- |
| **Claude CLI** | ✅ Verified | Works against the local LiteLLM gateway |
| **Codex CLI** | ✅ Verified | Custom provider config via Responses API wire format |
| **Gemini CLI** | ⚠️ Experimental | Raw endpoint works; CLI path not yet reliable |

---

## Core Concepts

BrokeLLM is built around three ideas:

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│  SLOT          What the client asks for                  │
│                sonnet, opus, haiku, default, subagent    │
│                                                          │
│  CONTROL PLANE Owns routing, fallback, health, drift,    │
│                and access-policy truth for those slots   │
│                                                          │
│  EXECUTION     LiteLLM enforces routing decisions        │
│  LAYER         against real upstream provider endpoints  │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

The point: **clients keep speaking in slots. You control what actually answers.**

---

## Capabilities

### 🔀 Routing Control

- Claude-style slot routing: `sonnet`, `opus`, `haiku`, `default`, `subagent`
- Interactive route switching with `broke swap`
- Team and profile presets for reusable configurations
- Fallback chain support per slot

### 🔍 Observability & Validation

- Drift warnings for floating aliases
- Health, validation, explain, route, metrics, and probe commands
- Focused regression tests for control-plane behavior
- Single canonical truth boundary — no split-brain state

### ⚡ Execution

- LiteLLM-backed gateway on `http://localhost:4000`
- Unified local entrypoint for `claude` and `codex`
- Simple one-command install

---

## Supported Providers

| Provider | Notes |
| --- | --- |
| **OpenRouter** | Recommended; includes free-tier models |
| **Groq** | Fast inference |
| **Cerebras** | High-throughput option |
| **GitHub Models** | GPT-4o-mini and others |
| **Gemini** | Direct endpoint verified; CLI path experimental |
| **Hugging Face** | Free-tier access |

> LiteLLM itself supports far more providers. BrokeLLM is an intentionally smaller, opinionated layer on top.

---

## Design Principle: One Truth Boundary

All health, drift, and routing state is resolved through a **single canonical normalization boundary** in the control plane.

`doctor`, `route`, `explain`, and `validate` do not maintain separate views of backend identity. They consume the same shared resolver — so the tool always reports one consistent truth about:

- which backend a slot maps to
- whether that backend is healthy
- whether the route is pinned or floating
- whether fallback state is relevant

> *If those surfaces disagree, the control plane stops being trustworthy. That design rule matters more than any single command.*

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full truth-boundary specification.

---

## Commands

### Gateway

```bash
broke            # start the full wrapper
broke start      # start only the gateway
broke stop
broke restart
broke status
```

### Routing

```bash
broke list
broke models
broke swap
broke swap <team>
broke fallback <slot> <fb1> [fb2...]
```

### Teams

```bash
broke team save <name> [cli|route]
broke team load <name>
broke team list
broke team delete <name>
broke team fallback <team> <slot> <fb1> [fb2...]
broke team access <team> [--slots sonnet,haiku] [--rpm N] [--tpm N]
```

> `0` means unlimited for `rpm` and `tpm`. Omitted values mean "leave unchanged."

### Profiles

```bash
broke profile new <name> <team> [--desc "text"] [--slots sonnet,haiku] [--rpm N] [--tpm N]
broke profile load <name>
broke profile list
broke profile delete <name>
```

### Observability

```bash
broke doctor
broke validate
broke explain <slot>
broke route <slot>
broke metrics
broke probe <slot>
```

### Snapshots

```bash
broke snapshot save
broke snapshot list
broke snapshot restore <id>
```

### Safety Controls

```bash
broke freeze        # toggle freeze
broke freeze on     # block swap-style state changes
broke freeze off
```

### Provider Selection

```bash
broke provider
broke provider list
broke provider swap [claude|codex|gemini]
```

---

## Example: Diagnosing a Broken Route

```bash
broke doctor
broke explain sonnet
broke route sonnet
```

Use these together to isolate different failure classes:

| Command | What It Tells You |
| --- | --- |
| `broke doctor` | Whether the gateway and upstream backends are healthy |
| `broke explain sonnet` | Configured slot, backend, health view, and fallback chain |
| `broke route sonnet` | What would actually be selected for that slot right now |

This separates: provider failure / bad mapping state / access-policy blocking / fallback activation risk.

---

## Example: Routing Across Providers

Route `sonnet` through GitHub Models, `haiku` through OpenRouter, inspect, save:

```bash
broke list
broke explain sonnet
broke route sonnet
broke team save work
```

Create a restricted profile for a production app:

```bash
broke profile new myapp work --desc "Production app" --slots sonnet --rpm 30
```

---

## Compatibility Notes

**Codex** — verified on April 3, 2026 using a custom provider configuration over the Responses API wire format:

```bash
env BROKE_DUMMY=dummy \
  codex exec \
  -c 'model_provider="broke"' \
  -c 'model_providers.broke={name="BrokeLLM",base_url="http://localhost:4000/v1",env_key="BROKE_DUMMY",wire_api="responses"}' \
  -m 'GitHub/GPT-4o-mini' --skip-git-repo-check --json \
  "Respond with exactly OK and nothing else."
```

> The previous `OPENAI_BASE_URL` env override approach was not reliable for Codex and is no longer the recommended path.

**Gemini** — BrokeLLM's Google-compatible HTTP endpoint works. The Gemini CLI itself is not reliable through BrokeLLM: even with `GOOGLE_GEMINI_BASE_URL` and `GEMINI_API_KEY_AUTH_MECHANISM` set, the CLI internally routes to `Gemini/2.0-Flash` which BrokeLLM does not expose. Until that changes upstream, Gemini CLI compatibility should not be claimed.

---

## Verification

```bash
make verify
```

Current regression coverage:

- Health agreement across `doctor`, `route`, and `explain`
- Pinned-state persistence during swap
- Floating alias drift warnings
- Zero-value limit semantics
- Installer interpreter consistency
- Env-name consistency

---

## Installation

### Requirements

- Python 3.8+
- `curl`
- `lsof`
- One or more provider API keys
- `claude` or `codex` CLI installed

### Install

```bash
./install.sh
```

The installer will:

- Verify Python
- Install `litellm[proxy]`
- Link `broke` into your `PATH`
- Create `.env` from `.env.template` if needed
- Initialize the default routing files

### Configuration

```bash
cp .env.template .env
```

Fill in whichever keys you plan to use:

```env
OPENROUTER_API_KEY=
GROQ_API_KEY=
CEREBRAS_API_KEY=
GITHUB_TOKEN=
GEMINI_API_KEY=
HF_TOKEN=
```

You do not need every key — only the providers you actively route to need valid credentials.

---

## Stability Notes

Free-tier models and routes can change availability, latency, quota behavior, or backing model behavior without notice.

For a more stable setup:

- Prefer pinned model entries over floating aliases
- Define fallback chains for important slots
- Save known-good mappings as teams
- Run `broke validate` and `broke doctor` before relying on a route

---

## When To Use BrokeLLM

| Situation | Good Fit? |
| --- | --- |
| You want cheaper or mixed-provider routing behind a stable local interface | ✅ |
| You need deterministic slot routing for CLI AI tools | ✅ |
| You care about health, drift, and explainability — not blind proxying | ✅ |
| You want to preserve the client-facing slot experience while changing backends freely | ✅ |
| You only use one provider and don't care about routing behavior | ❌ |
| You want fully managed SaaS simplicity instead of a local control plane | ❌ |
| You don't need observability, fallback chains, or slot abstraction | ❌ |

---

## Why I Built This

Most CLI coding tools assume you have stable access to expensive frontier models.

I did not.

BrokeLLM exists because I needed a way to keep using those tools without being locked into a single provider or cost structure. The goal was not to emulate a provider. The goal was to create a **local control plane** that lets the client experience stay the same while the backend becomes flexible, cheaper, and under user control.

I am a single father and primary caregiver to a young child with autism, and I am currently unemployed. This project is for anyone else in a similar situation who still wants to write code, experiment, and keep moving.

---

## Architecture

Control-plane behavior lives in [`bin/_mapping.py`](bin/_mapping.py).  
CLI entrypoint is [`bin/broke`](bin/broke).  
Truth-boundary specification is in [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Contributing

Issues and improvements are welcome, especially around:

- **Provider presets** — new backends and example configs
- **Safer install paths** — better bootstrap and dependency handling
- **Observability** — richer health and drift reporting
- **Test coverage** — import/export, snapshot, and edge-case flows
- **Documentation** — constrained-budget and offline workflows

---

## Project Status

**Current milestone:** control-plane correctness baseline.

Suggested next steps:
- Add tests around import/export and snapshot flows
- Cut a release tag after checkpointing the current state

---

## License

MIT — see [LICENSE](LICENSE).

LiteLLM is a separate upstream project with its own licensing and enterprise/commercial components. Review upstream terms independently if you distribute or extend those parts.

---

## Disclaimer

BrokeLLM is a personal open-source tool. It is not affiliated with Anthropic, OpenAI, Google, GitHub, Groq, Cerebras, Hugging Face, or BerriAI.

You are responsible for your API usage and billing, your provider terms, your local environment security, and pinning and reviewing dependency versions appropriately.

---

*Keep your client speaking in slots. Control what actually answers.* ⚡
