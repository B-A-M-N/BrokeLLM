# BrokeLLM

BrokeLLM is a lightweight CLI wrapper around [LiteLLM](https://github.com/BerriAI/litellm) that lets you route Claude-style model slots such as `sonnet`, `opus`, `haiku`, `default`, and `subagent` to lower-cost or free backends.

It exists for one simple reason: sometimes you still need to build, learn, and ship even when paid model access is not realistic.

## Why This Exists

I built this because I needed a practical way to keep doing the work I am good at and enjoy doing without depending on expensive subscriptions.

I am a single father and primary caregiver to a young child with autism, and I am currently unemployed. With things being what they are, I needed a way to keep working with LLM tooling using the resources I could actually afford. This project is for anyone else in a similar situation who still wants to write code, experiment, and keep moving.

## What It Does

BrokeLLM puts a local LiteLLM gateway in front of multiple providers and lets you:

- map Claude-style slots to cheaper or free models
- swap routes interactively
- save and load routing presets as teams
- define client profiles with access limits
- configure fallback chains between slots
- inspect health, routing, and drift warnings
- launch `claude` or `codex` through the wrapper, with optional provider switching for supported paths

In practice, it gives you a local control plane for model routing without needing to hand-edit LiteLLM config every time you want to change backends.

If you are new to AI-assisted tools or want a slower, beginner-facing guide first, read [HUMAN_ONLY/FOR_BEGINNERS.md](HUMAN_ONLY/FOR_BEGINNERS.md).

## Core Terms

- Slot: what the client asks for, such as `sonnet`, `opus`, `haiku`, `default`, or `subagent`
- Model: the actual LLM that serves the request, such as `gpt-4o-mini` or `qwen/qwen3.6-plus:free`
- Provider: where that model is reached, such as OpenRouter, Groq, GitHub Models, or Gemini

The point of BrokeLLM is to let the client keep speaking in slots while you control which provider/model combination actually answers.

## Features

- Claude-style slot routing: `sonnet`, `opus`, `haiku`, `default`, `subagent`
- LiteLLM-backed gateway on `http://localhost:4000`
- Interactive and saved route switching
- Team and profile presets
- Fallback chain support
- Drift warnings for floating aliases
- Health, validation, explain, route, metrics, and probe commands
- Simple install script
- Focused regression tests for the control-plane behavior

## Supported Providers in This Repo

This repository currently includes example backends for:

- OpenRouter
- Groq
- Cerebras
- GitHub Models
- Gemini
- Hugging Face

LiteLLM itself supports far more providers; BrokeLLM is intentionally a smaller opinionated layer on top.

## Architecture

High-level flow:

```text
Claude/Codex CLI
        |
        v
     broke
        |
        v
  LiteLLM gateway
        |
        v
  selected backend provider/model
```

Control-plane behavior is handled in [`bin/_mapping.py`](bin/_mapping.py), and the CLI entrypoint is [`bin/broke`](bin/broke). For the truth boundary around health and drift reporting, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Design Principle: One Truth Boundary

All health, drift, and routing state is resolved through a single canonical normalization boundary in the control plane.

Commands like `doctor`, `route`, `explain`, and `validate` do not compute their own separate view of backend identity. They consume the same shared resolver so that the tool reports one consistent truth about:

- which backend a slot maps to
- whether that backend is healthy
- whether the route is pinned or floating
- whether fallback state is relevant

That design rule matters more than any single command. If those surfaces disagree, the control plane stops being trustworthy.

## Compatibility Status

- `claude`: verified against the local LiteLLM gateway
- `codex`: verified against the local LiteLLM gateway through a custom Codex provider config
- `gemini`: raw Gemini-format gateway calls work, but Gemini CLI is not currently reliable through BrokeLLM

Codex compatibility works when BrokeLLM is configured as a custom Codex model provider using the OpenAI Responses wire format against the local LiteLLM gateway.

On April 3, 2026, this live check succeeded:

```bash
env BROKE_DUMMY=dummy \
  codex exec \
  -c 'model_provider="broke"' \
  -c 'model_providers.broke={name="BrokeLLM",base_url="http://localhost:4000/v1",env_key="BROKE_DUMMY",wire_api="responses"}' \
  -m 'GitHub/GPT-4o-mini' --skip-git-repo-check --json \
  "Respond with exactly OK and nothing else."
```

The previous `OPENAI_BASE_URL` env override approach was not reliable for Codex and is no longer the recommended path here.

Gemini is a different case. On April 3, 2026, direct requests to BrokeLLM's Google-style endpoint succeeded:

```bash
curl -sS http://localhost:4000/v1beta/models/GitHub/GPT-4o-mini:generateContent \
  -H 'x-goog-api-key: dummy' \
  -H 'Content-Type: application/json' \
  --data '{"contents":[{"parts":[{"text":"Say OK"}]}]}'
```

That returned a valid Gemini-format response through LiteLLM.

The Gemini CLI itself was not reliable against the same gateway. Even with:

- `GOOGLE_GEMINI_BASE_URL=http://localhost:4000`
- `GEMINI_API_KEY_AUTH_MECHANISM=bearer`
- `--model 'GitHub/GPT-4o-mini'`

the CLI still internally routed requests to `Gemini/2.0-Flash` in this environment and failed because BrokeLLM does not expose that model group. In other words:

- BrokeLLM's Gemini-compatible HTTP endpoint works
- Gemini CLI's internal model routing does not currently make this a trustworthy end-to-end integration

Until that changes upstream or a stable workaround is found, this repo should not claim Gemini CLI compatibility.

## Installation

### Requirements

- Python 3.8+
- `curl`
- `lsof`
- one or more provider API keys
- the CLI you want to launch: `claude` or `codex`

### Install

```bash
./install.sh
```

The installer will:

- verify Python
- install `litellm[proxy]`
- link `broke` into your `PATH`
- create `.env` from `.env.template` if needed
- initialize the default routing files

## Configuration

Copy the template if needed:

```bash
cp .env.template .env
```

Fill in whichever keys you plan to use:

- `OPENROUTER_API_KEY`
- `GROQ_API_KEY`
- `CEREBRAS_API_KEY`
- `GITHUB_TOKEN`
- `GEMINI_API_KEY`
- `HF_TOKEN`

You do not need every key. Only the providers you actively route to need valid credentials.

## Stability Notes

Free-tier models and routes can change availability, latency, quota behavior, or backing model behavior without notice.

If you want a more stable setup:

- prefer pinned model entries over floating aliases
- define fallback chains for important slots
- save known-good mappings as teams
- use `broke validate` and `broke doctor` before relying on a route

## Quick Start

Start the wrapper:

```bash
broke
```

Start only the gateway:

```bash
broke start
```

Show the current mapping:

```bash
broke list
```

Swap a slot interactively:

```bash
broke swap
```

Validate config:

```bash
broke validate
```

Run health checks:

```bash
broke doctor
```

## Commands

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

Notes:

- `0` means unlimited for `rpm` and `tpm`
- omitted values mean "leave unchanged"

### Profiles

```bash
broke profile new <name> <team> [--desc "text"] [--slots sonnet,haiku] [--rpm N] [--tpm N]
broke profile load <name>
broke profile list
broke profile delete <name>
```

### Gateway

```bash
broke start
broke stop
broke restart
broke status
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

### Provider Selection

```bash
broke provider
broke provider list
broke provider swap [claude|codex|gemini]
```

### Safety Controls

```bash
broke freeze
broke freeze on
broke freeze off
```

When frozen, swap-style state changes are blocked.

## Examples

Route `sonnet` through GitHub Models, `haiku` through OpenRouter, and inspect the result:

```bash
broke list
broke explain sonnet
broke route sonnet
```

Save a known-good setup:

```bash
broke team save work
```

Create a restricted profile for an app:

```bash
broke profile new myapp work --desc "Production app" --slots sonnet --rpm 30
```

Example: diagnosing a broken route

```bash
broke doctor
broke explain sonnet
broke route sonnet
```

Use these together to separate different failure classes:

- `broke doctor` tells you whether the gateway and upstream backends are healthy
- `broke explain sonnet` shows the configured slot, backend, health view, and fallback chain
- `broke route sonnet` shows what would actually be selected for that slot right now

That helps distinguish:

- provider failure
- bad mapping state
- access-policy blocking
- fallback activation risk

## Verification

Default verification path:

```bash
make verify
```

Current regression coverage includes:

- health agreement across `doctor`, `route`, and `explain`
- pinned-state persistence during swap
- floating alias drift warnings
- zero-value limit semantics
- installer interpreter consistency
- env-name consistency

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

LiteLLM itself is a separate upstream project with its own licensing and enterprise/commercial components. Use and review upstream terms independently if you distribute or extend those parts.

## Disclaimer

BrokeLLM is a personal open-source tool. It is not affiliated with Anthropic, OpenAI, Google, GitHub, Groq, Cerebras, Hugging Face, or BerriAI.

You are responsible for:

- your API usage and billing
- your provider terms
- your local environment security
- pinning and reviewing dependency versions appropriately

## Contributing

Issues and improvements are welcome, especially around:

- provider presets
- safer install and bootstrap paths
- better observability
- more test coverage
- documentation for constrained-budget workflows

## Project Status

Current milestone: control-plane correctness baseline.

Suggested first follow-ups:

- add more tests around import/export and snapshot flows
- put the project under git if it is not already
- cut a release tag after checkpointing the current state
