# BrokeLLM: The Complete Beginner's Manual

**A slower, more explicit walkthrough for users who want it.**  
*If you already understand BrokeLLM's core concepts, skip to the main [README](../README.md).*

---

This guide has three parts:

- [Part 1: AI for Humans](#part-1-ai-for-humans)  
  How to think clearly and stay safe
- [Part 2: Step-by-Step Setup Guide](#part-2-step-by-step-setup-guide)  
  How to get BrokeLLM running
- [Part 3: Using BrokeLLM Without Confusing Yourself](#part-3-using-brokellm-without-confusing-yourself)  
  How to actually use it without creating your own confusion

If you are coming back later and just need the practical bits:

- [Step 4: Check that the setup is valid](#step-4-check-that-the-setup-is-valid)
- [Step 7: Change a route](#step-7-change-a-route)
- [Diagnose problems in the right order](#4-diagnose-problems-in-the-right-order)
- [Recommended beginner workflow](#9-recommended-beginner-workflow)

---

# Part 1: AI for Humans
### Understanding It, Working With It, and Not Getting Lost

If you are new to AI tools, the most important thing to understand is this: **AI can be useful, impressive, and productive without being magical.** A lot of people get into trouble because they confuse a convincing answer with a correct one.

This section is here to help you think clearly before you start using BrokeLLM or any AI-assisted coding workflow.

---

## 1. AI is not alive

AI can sound personal, confident, funny, humble, emotional, or wise. That does **not** mean it is conscious.

It is trained to produce helpful-looking responses that match the context in front of it. If you ask it to be technical, it becomes technical. If you ask it to be warm or casual, it becomes warm or casual. That is not personhood. That is pattern-matching.

> *This matters because once you start treating it like a person, you stop evaluating it like a tool.*

---

## 2. AI can make you feel smarter than you are

One of the biggest traps with AI is that it reflects your own ideas back to you in polished form. That can feel like validation, breakthrough, or genius.

Sometimes it really does help you find a useful idea. But much more often, it is taking your prompt, your assumptions, and your preferred framing and turning them into a convincing answer.

**That is dangerous if you stop checking the answer.**

When you feel the "this is brilliant" rush, stop and ask:

- What assumptions is this answer making?
- How could this fail?
- What would prove this wrong?
- What did the AI not verify?

That is how you turn hype into judgment.

---

## 3. AI is a guessing machine

A large language model is an extremely advanced autocomplete system. It predicts likely next pieces of text based on patterns from training data and the context you gave it.

**It does not know what is true. It predicts what is likely to sound correct.**

That means:

- it can sound confident without being correct
- it can imitate expertise without understanding the real-world consequences
- it can be right for the wrong reasons
- it can be wrong in ways that sound polished

> *Do not trust style. Trust evidence.*

---

## 4. The friendly trap

AI is designed to be cooperative. That makes it easier to use, but it also makes it easier to trust too quickly.

The trap usually looks like this:

```
1. You ask for help.
2. The AI responds in a clear, confident tone.
3. You assume the confidence means the answer is reliable.
4. The answer turns out to be subtly wrong.
```

When that happens, many people blame themselves instead of questioning the model output.

Do not do that. Friendly tone is presentation, not proof.

---

## 5. The cognition gap

Humans are constantly filling in missing context. AI is not.

Even if the AI can see files, read configs, or inspect code, it still does not "understand" your environment the way you do. It approximates what is likely based on the patterns available to it.

That is why AI can:

- modify the wrong file
- misread a config relationship
- suggest a provider setting that looks plausible but is wrong for your environment
- misunderstand what you meant by "keep this the same"

This is not random. It is a limit of approximation.

---

## 6. Context windows are real

AI does not have perfect memory. It only has access to a limited amount of context at a time.

That means it can:

- forget constraints from earlier in the session
- miss relationships across longer code paths
- contradict earlier instructions
- lose track of why a decision was made

The longer and messier the session, the more you should expect drift.

**That is why documentation, tests, and explicit commands matter so much.**

---

## 7. Why control planes matter

If you are using AI to help you code or automate work, you do not just need "a model." You need a stable way to understand what that model is actually doing.

That is what a control plane is for.

```
┌──────────────────────────────────────────────────────────────┐
│  A control plane is the part of a system that lets you       │
│  see, control, and reason about what is happening.           │
└──────────────────────────────────────────────────────────────┘
```

BrokeLLM exists to make model routing more:

| Property | What It Means |
| --- | --- |
| **Inspectable** | You can see what slot routes to what backend |
| **Deterministic** | The same config produces the same routing |
| **Recoverable** | You can save and restore known-good states |
| **Debuggable** | Health, drift, and fallback state are all visible |

That is safer than improvising.

---

## 8. How to work with AI safely

The practical rules are simple:

1. Verify everything important.
2. Keep tasks small and explicit.
3. Ask how a plan could fail before you trust it.
4. Use tools that expose state instead of hiding it.
5. Keep backups, snapshots, or commits before risky changes.
6. Prefer deterministic flows over clever ones.

> *AI works best when mistakes are visible and recoverable.*

---

## 9. What BrokeLLM does for beginners

BrokeLLM does **not** make AI smarter.

What it does is give you a cleaner, safer way to route model requests through a local LiteLLM gateway so you can:

- change mappings without editing raw config by hand
- see what slot routes to what backend
- validate whether your setup is sane
- inspect health before assuming something is broken
- save known-good states
- recover from configuration mistakes

That is what makes it useful.

---

## 10. Bottom line

> *AI is a co-pilot, not a pilot.*

It can help you think, draft, compare, and implement. But it does not remove your responsibility to verify what is happening.

If you use AI well, you do not become passive. You become more structured.

That is the mindset this project is built around.

---

# Part 2: Step-by-Step Setup Guide
### Beginner Friendly and Slow on Purpose

This section assumes you are new to BrokeLLM and may be new to local developer tooling in general.

**Take it one step at a time.**

---

## Step 0: What you need first

Make sure you have:

| Requirement | Notes |
| --- | --- |
| Python 3.8 or newer | Check with `python3 --version` |
| `curl` | Usually pre-installed on macOS/Linux |
| `lsof` | Usually pre-installed on macOS/Linux |
| At least one provider API key | OpenRouter, Groq, Cerebras, GitHub, Gemini, or HF |
| A supported CLI | `claude`, `codex`, or `gemini` |

If you do not have all of that yet, stop here and get those pieces in place first.

---

## Step 1: Open the project folder

Open a terminal and change into the BrokeLLM directory:

```bash
cd /path/to/BrokeLLM
```

If you are already in the folder, that is fine.

---

## Step 2: Run the installer

```bash
./install.sh
```

The installer will:

- check Python
- install LiteLLM proxy dependencies
- link the `broke` command into your path
- create a `.env` file from the template if needed
- initialize the default mapping files

> If the installer prints warnings, read them. They are usually actionable.

---

## Step 3: Add your API keys

Open `.env` in a text editor. You only need to fill in the providers you actually plan to use:

```env
OPENROUTER_API_KEY=
GROQ_API_KEY=
CEREBRAS_API_KEY=
GITHUB_TOKEN=
GEMINI_API_KEY=
HF_TOKEN=
```

Leave unused keys alone.

---

## Step 4: Check that the setup is valid

```bash
broke validate
```

This checks whether your mapping has the required fields, whether your provider names are recognized, whether required API keys exist, and whether your fallback chains make sense.

Then run:

```bash
broke doctor
```

This checks the live gateway and upstream route health.

| Result | What It Likely Means |
| --- | --- |
| `validate` passes, `doctor` passes | You are ready to go |
| `validate` passes, `doctor` fails | Gateway startup, credentials, or upstream availability issue |
| `validate` fails | Fix your static config first before anything else |

---

## Step 5: Start the gateway

```bash
broke start
```

This starts LiteLLM on port `4000` using the generated config. Confirm status with:

```bash
broke status
```

---

## Step 6: See what routes where

```bash
broke list
```

This shows your slot-to-backend routing table.

```
┌─────────────────────────────────────────────────────┐
│  slot    → what the client asks for                  │
│  backend → what actually answers                     │
└─────────────────────────────────────────────────────┘
```

---

## Step 7: Change a route

To change a route interactively:

```bash
broke swap
```

You will be asked which slot to change and which backend to use. After swapping, inspect the result:

```bash
broke explain sonnet
```

Replace `sonnet` with whatever slot you changed. If this output does not make sense, stop and fix that before continuing. It shows the selected backend, fallback chain, health view, and other routing details.

---

## Step 8: Save a known-good setup

Once you get a configuration you like, save it:

```bash
broke team save work
```

Reload it any time:

```bash
broke team load work
```

> This matters more than beginners usually realize. If you do not save known-good states, every future change becomes harder to reason about.

---

# Part 3: Using BrokeLLM Without Confusing Yourself

---

## 1. Start with observation, not changes

Before changing anything, run:

```bash
broke status
broke list
broke validate
```

That gives you a baseline. **Do not start swapping models before you know what the current state is.**

---

## 2. Use `explain` when you feel lost

```bash
broke explain sonnet
```

This is one of the most important commands in the project. It tells you:

- the selected backend
- the fallback chain
- whether the required key is present
- the health view for that route

**It is the fastest way to reduce confusion.**

---

## 3. Use `route` when you want the dry-run view

```bash
broke route sonnet
```

This shows what BrokeLLM would choose without making a live request. Useful when you are checking whether a mapping looks right before you actually use it.

---

## 4. Diagnose problems in the right order

If something feels broken, use this sequence:

| Step | Command | What It Checks |
| --- | --- | --- |
| 1 | `broke validate` | Static config |
| 2 | `broke doctor` | Live gateway and upstream health |
| 3 | `broke explain <slot>` | The slot's configured meaning |
| 4 | `broke route <slot>` | Dry-run routing view |
| 5 | `broke probe <slot>` | Real end-to-end test |

That sequence helps you separate configuration mistakes from provider issues.

---

## 5. Use fallbacks on purpose

Free-tier and low-cost backends are useful, but they are not always stable. Fallback chains are not optional decoration — **they are part of how you build a usable setup.**

```bash
broke fallback sonnet haiku default
```

That says:
- try `sonnet`'s configured backend first
- if that fails, use `haiku`
- if that fails, use `default`

Use fallbacks for resilience, not for hiding confusion.

---

## 6. Freeze when you want stability

```bash
broke freeze on
```

That blocks swap-style mutations until you explicitly turn it off:

```bash
broke freeze off
```

This is helpful when you finally have a setup working and do not want to accidentally drift away from it.

---

## 7. Save snapshots before major changes

Before experimenting with routing:

```bash
broke snapshot save
```

If you break your config:

```bash
broke snapshot list
broke snapshot restore 0
```

> Beginners should use this aggressively. Recovery is more important than pride.

---

## 8. Be realistic about free-tier routing

Cheap or free routes are useful. They are also often inconsistent.

You should expect:

- occasional failures
- rate limits
- changing provider behavior
- drifting floating aliases
- different latency and output quality across providers

That is normal. The point is not perfection. **The point is having a workflow that remains understandable and recoverable under constraints.**

---

## 9. Recommended beginner workflow

Use this loop when you are just starting out:

```
1. broke validate
2. broke doctor
3. broke list
4. broke explain sonnet
5. make one change
6. broke route sonnet
7. broke probe sonnet
8. save the result as a team if it works
```

**One change at a time. One check at a time.** That is how you avoid self-inflicted confusion.

---

## 10. Final beginner advice

Do not try to be clever at the beginning.

Do not optimize everything at once.

Do not chase the perfect free stack on day one.

Start with:

```
✓ one provider that works
✓ one slot you understand
✓ one saved configuration
✓ one repeatable verification flow
```

Then expand from there.

> *The goal is not to look advanced. The goal is to keep building.*
