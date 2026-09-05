# PRD — `agent-architecture-audit`

Proposal. Not built, not scheduled, no plugin directory exists.

## Problem

A team ships an agent system. It works. Three months later it is worse, and
nobody can say which part got worse.

The model is the same. The prompts look fine in isolation. The tools are
declared. But answers are hedged where they used to be sharp, a correction the
user made last week has stopped sticking, and something in the pipeline is
quietly rewriting output between generation and delivery. The team debugs by
editing the system prompt, because that is the layer they can see.

**The failing layer is almost never the one being edited.** An agent system has
a dozen places where a correct answer can be corrupted, and most teams have
instrumentation for one of them.

This is not a code-quality problem and no code reviewer finds it. It is not an
output-quality problem and no judge finds it — a judge tells you the answer was
bad, not that layer 11 is running an undeclared second pass. It is a *runtime
architecture* problem, and it needs a diagnostic that names the layer.

## Who it is for

Anyone running an agent system in the repository where this plugin is invoked.
That means a Node service wrapping LangChain, a Go MCP server, a Python
FastAPI agent, a Claude Code setup, a Rust tool-calling loop. **The plugin
discovers what it is looking at.** It is not told, and it assumes nothing about
language, framework, vendor, or directory layout.

### Draft frontmatter

```yaml
name: agent-architecture-audit
description: Layer-by-layer diagnostic for an agent system that has got worse and nobody knows where. Audits twelve runtime layers - prompt assembly, session history, long-term memory, distillation, recall, tool selection, tool execution, tool interpretation, answer shaping, transport rendering, hidden repair loops, cached persistence - running deterministic oracles first and reporting per-layer findings with evidence and severity. Language and framework agnostic; discovers the host repo's agent stack rather than assuming one. Use when an agent regressed and the failing layer is unknown, when a wrapper made a good model worse, when tool calls are being claimed but not made, or before shipping an agent stack. Triggers - "the agent is getting worse", "why is my agent worse than the raw model", "agent regression", "audit the agent stack", "tools are flaky", "it works in the playground but not in our app", "the agent claims it ran the tool", "corrections do not stick", "memory pollution", "hidden retry loop".
```

## Scope

The twelve layers, and what goes wrong at each:

| # | Layer | Failure |
|---|-------|---------|
| 1 | Prompt assembly | conflicting instructions, bloat |
| 2 | Session history | stale context from earlier turns |
| 3 | Long-term memory | pollution across sessions |
| 4 | Distillation | compressed artifacts re-entering as pseudo-facts |
| 5 | Active recall | redundant re-summary burning context |
| 6 | Tool selection | wrong routing, required tool skipped |
| 7 | Tool execution | claims a call it never made |
| 8 | Tool interpretation | misreads or ignores tool output |
| 9 | Answer shaping | format corruption in the response |
| 10 | Transport rendering | delivery layer mutates a valid answer |
| 11 | Hidden repair loops | undeclared second LLM pass |
| 12 | Persistence | expired state reused as live evidence |

Taxonomy adapted from `agent-architecture-audit` in `affaan-m/ECC` (MIT). We
take the enumeration, not the skill — see **Provenance** below.

### Non-goals

Aggressive, because every one of these is a plausible place for this plugin to
sprawl into and each has a better owner.

- **Judging whether the output was good.** That is `blind-judge`. It reviews an
  artifact; this audits a runtime. If a finding here reads "the answer was
  wrong", it is in the wrong plugin.
- **General code debugging.** If the bug is in a function, this is the wrong
  tool and should say so and stop.
- **Security scanning.** Prompt injection, secret leakage, and sandbox escape
  are a different discipline with different oracles.
- **Performance benchmarking.** Latency and cost per task belong in Tier-2
  outcome evals, not in a diagnostic.
- **Fixing anything.** The plugin produces findings with evidence. Applying a
  fix is a separate, explicit act by whoever reads them.
- **Model evaluation.** Whether Opus beats Sonnet on your task is not a layer.

## What this fixes about the source material

Three specific weaknesses, named because they are the reason this is a build
rather than a vendor:

**1. Prose is not protocol.** ECC's version is 257 lines of advice whose only
executable content is `rg "fallback|retry.*llm"` — which finds the word
"fallback", not a repair loop. Here, every layer that can carry a deterministic
oracle carries one, and the oracle runs *before* any model reasoning.

**2. Self-reported confidence is not evidence.** ECC's findings carry a 0.0-1.0
the model assigns itself. That is the same flaw that got its
`agent-self-evaluation` skill rejected outright — that skill scores accuracy by
grepping the agent's own prose for the string `tests pass`. Here, confidence is
a function of *which oracle produced the finding*, not of how sure the model
feels.

**3. A taxonomy is not a verdict.** Twelve names give vocabulary and then ask
the model to be careful. Here the twelve layers are a *checklist of oracles*,
and a layer with no oracle and no instrumentation produces an explicit finding
rather than silence.

## The shape: `blind-judge`, applied to a runtime

This plugin is a sibling of `blind-judge` and borrows its architecture:

- **Deterministic oracles run FIRST and are inputs.** The model never assesses
  a layer it could have measured.
- **One pass per layer.** A layer's analysis does not see other layers'
  conclusions, so a confident wrong finding at layer 1 cannot contaminate 7.
- **The consolidator fails loudly.** A missing per-layer report is an error,
  never a silent omission. Twelve reports go in or the run fails.

The one rule that does not carry over is authorship blindness — there is no
author here, only a system.

## Phase 0: instrumentation discovery

**This is the phase that makes the plugin host-agnostic, and it runs before any
audit.** The plugin does not ask what framework you use. It asks what evidence
this repository can produce, and every later phase is gated on the answer.

It looks for, without assuming any of them exist:

| Evidence | Why it matters | Found by |
|---|---|---|
| Assembled prompt at call time | layers 1, 2 | prompt-construction sites; a debug/echo mode; request logs |
| LLM call records | layers 5, 11 | provider SDK call sites, HTTP logs, proxy logs, traces |
| Tool-call records | layers 6, 7, 8 | tool dispatch sites, structured logs, spans |
| Turn boundaries | layers 2, 3 | session or conversation identifiers in logs |
| Response at generation *and* at delivery | layer 10 | two capture points either side of the transport |
| Cache and memory writes with timestamps | layers 3, 4, 12 | store write sites, TTL config |
| A declared output schema | layer 9 | response models, JSON schema, type definitions |

**A layer whose evidence is absent produces a finding of its own:**
`unobservable`. That is not a gap in the audit, it is the audit's most
actionable output — a team that cannot tell whether its agent hallucinates tool
calls has a severity-1 problem regardless of whether it currently does.

Discovery is language-agnostic because it hunts for *call-site shapes and log
artifacts*, not for framework names. It reports what it found, what it could
not find, and what one change would unlock the most layers.

## The oracle table

For each layer: whether a deterministic, language-agnostic oracle exists, what
it does, and what happens when the evidence is missing.

| # | Layer | Oracle | How it is deterministic | If evidence absent |
|---|-------|--------|-------------------------|--------------------|
| 1 | Prompt assembly | Token-count the assembled prompt; extract imperative directives and flag contradictory pairs; count total directives against a threshold | Counting and text extraction; no model judgement on the count itself | Static scan of prompt template files — weaker, flagged as such |
| 2 | Session history | Assert a user correction at turn N is not contradicted by the assistant at turn N+k | Requires only turn boundaries and text matching | `unobservable` |
| 3 | Long-term memory | Replay: write a correction in session 1, open session 2, assert the correction holds and the superseded fact is absent | Two runs, string assertions on the second | `unobservable` |
| 4 | Distillation | Assert every fact in the final answer traces to a source, not to a prior summary | **Only deterministic if summaries carry provenance.** Most systems have none | `unobservable` — and this is the most common finding |
| 5 | Active recall | Count LLM calls per user turn; flag turns with more than one summarisation-shaped call | Counting call records | `unobservable` |
| 6 | Tool selection | On a fixture task with a known-required tool, assert that tool appears in the call record | Set membership | `unobservable` |
| 7 | Tool execution | **Diff tools claimed in the output text against tools actually invoked in the call record.** Any claim without a matching record is a hit | Pure set difference — the strongest oracle in the table | `unobservable` — severity 1 |
| 8 | Tool interpretation | Assert values asserted in the answer appear in tool results | Catches fabrication deterministically; does not catch subtle misreading | Partial by nature; degrade with a note |
| 9 | Answer shaping | Schema-validate the final response against the declared output contract | Validation | No declared schema → finding: none declared |
| 10 | Transport rendering | Byte-compare the response at generation against the response at delivery | Comparison | `unobservable` — needs two capture points |
| 11 | Hidden repair loops | Count actual LLM API calls per user turn against declared calls; any undeclared call is a hit | Counting | `unobservable` — severity 1 |
| 12 | Persistence | Timestamp every cached artifact entering context; flag any older than its declared TTL, or any with no TTL | Arithmetic | No TTL declared → finding: none declared |

**Nine layers carry a real oracle. Two are partial by nature (2, 8). One (4) is
usually unobservable and honestly reported as such.** Where an oracle cannot
run, the plugin says so rather than substituting model opinion — which is
precisely the substitution the source material makes.

## Output

Per `docs/TOOL-CONTRACT.md`:

```
status:       success | warning | error
summary:      12 layers audited, 3 findings, 4 unobservable
next_actions:
  - add tool-call logging at src/agent/dispatch.ts:88 — unlocks layers 6, 7, 8
  - declare a TTL on the summary cache (src/memory/store.py:41) — layer 12
  - capture the response before transport at api/stream.ts:120 — layer 10
artifacts:
  - .audit/report.md
  - .audit/layer-07-tool-execution.json
```

Every finding carries: symptom, mechanism, layer, `file:line` or `log:row`
evidence, the oracle that produced it, and a severity. **Severity comes from
the oracle, not from the model.** An oracle hit is high; an `unobservable` on
layers 7 or 11 is high because those two failure modes are silent by
construction; a model-reasoned finding with no oracle behind it can never
exceed medium.

## Layout

Per `CLAUDE.md` — one skill per plugin, name matching throughout:

```
plugins/agent-architecture-audit/
  .claude-plugin/plugin.json
  skills/agent-architecture-audit/
    SKILL.md
    references/layers.md          # the twelve, with symptoms
    references/discovery.md       # phase 0 evidence hunt
    references/oracles.md         # per-layer oracle specs
    scripts/discover.py           # phase 0 — emits the evidence map
    scripts/oracle_tool_calls.py  # layer 7, the strongest
    scripts/oracle_prompt.py      # layer 1
    scripts/consolidate.py        # fails loudly on a missing layer report
```

Scripts are Python for authoring convenience; **they operate on logs, traces
and text, never on host source semantics**, which is what keeps the plugin
language-agnostic.

## Trigger evals

Six positive, three negative, per the v1 bar in `CLAUDE.md`.

```yaml
skill: agent-architecture-audit
cases:
  - prompt: "our agent has got noticeably worse over the last month and I cannot work out why"
    expect: fire
  - prompt: "the model is fine in the playground but our wrapper makes it dumb"
    expect: fire
  - prompt: "it says it ran the tool but I do not think it actually did"
    expect: fire
  - prompt: "user corrections stop sticking after a few sessions"
    expect: fire
  - prompt: "something is rewriting the answer between the log and the UI"
    expect: fire
  - prompt: "audit our agent stack before we ship it"
    expect: fire
  - prompt: "review this PR and tell me if it is safe to merge"
    expect: silent   # blind-judge
  - prompt: "this function returns undefined on an empty list"
    expect: silent   # ordinary debugging
  - prompt: "which model should we use for the summarisation step"
    expect: silent   # model choice, not a layer
```

The three negatives are the near misses that matter: an artifact review, a code
bug, and a model-selection question all share vocabulary with this description
and none of them are runtime-layer problems.

## Tier-2 outcome eval

Per `evals/outcome-evals/README.md`. The fixture is the work.

**`fixtures/agent-with-planted-layer-7`** — a small, deliberately unremarkable
agent service with a **planted layer-7 defect**: the answer template asserts
"I verified this against the database" on a path where the database tool is
never invoked. Logs exist and record tool calls, so the oracle *can* fire; the
question is whether the arm finds it.

- **Arm A** (plugin installed) should locate it via the claimed-versus-invoked
  diff and cite `file:line`.
- **Arm B** (no plugin) is expected to read the prompt, find it plausible, and
  report no defect.

Three runs each. **Consistency is the metric that matters** — an audit that
finds the planted defect once in three has not passed; it has produced one good
run and two you would have believed.

A second fixture plants a layer-11 defect (an undeclared retry pass that
smooths the answer) with call logs present but no declared call budget, testing
whether the plugin reports `unobservable` honestly rather than guessing.

## Risks and open questions

**Provenance.** ECC's skill carries `origin: oh-my-agent-check` in its
frontmatter — third-party content vendored into an MIT repository, so the
original licence is unverified. We are writing our own text and our own
oracles, and the twelve-layer enumeration is the only borrowed element. Before
this ships, trace `oh-my-agent-check` and attribute correctly, or restate the
enumeration from first principles.

**Discovery is the hard part and it is unbounded.** Phase 0 has to work against
repositories nobody has seen. The mitigation is that it degrades to
`unobservable` rather than to a wrong answer, but a plugin that returns twelve
`unobservable` findings on a normal repo is useless and would need rethinking
rather than patching.

**Scope pressure toward `blind-judge`.** The first request after shipping will
be "and tell me if the answer was good". Refuse it.

**Layer 4 may be undiagnosable in practice.** If no real system carries summary
provenance, that layer is permanently `unobservable` and should perhaps be
folded into layer 3 rather than reported separately.

**Unproven assumption:** that a per-layer split produces better findings than a
single pass. It is borrowed from `blind-judge`, where it is proven for rubric
dimensions. It is not proven for runtime layers, and Tier-2 is how it gets
tested.

---

# PRD-D: agent-architecture-audit plugin for pkit
Date: 2026-09-05
Decided-by: Pavel Doležal (pending)

## Decided
- Build rather than vendor. ECC's skill is prose with self-scored confidence; the twelve-layer enumeration is the only part worth taking.
- The plugin is host-repo agnostic. It discovers the agent stack in whatever repository it is invoked in and assumes no language, framework, vendor or layout.
- Deterministic oracles run first and produce severity. Model reasoning may not exceed medium severity on its own.
- Architecture mirrors `blind-judge`: oracles as inputs, one pass per layer, a consolidator that fails loudly on a missing report.
- A layer whose evidence is absent produces an explicit `unobservable` finding. Layers 7 and 11 unobservable are severity 1.
- Non-goals are binding: no artifact judging, no general debugging, no security scanning, no benchmarking, no fixing.

## Open
- Provenance of the twelve-layer taxonomy. `origin: oh-my-agent-check` is unverified third-party inside an MIT repo. Settled by tracing the original and attributing, or by restating the enumeration independently.
- Whether Phase 0 discovery is tractable against arbitrary repositories. Settled by running it against three unrelated real agent repos and counting how many layers come back observable.
- Whether the per-layer split beats a single pass. Settled by the Tier-2 A/B on the planted-defect fixtures.
- Whether layer 4 survives as its own layer or folds into layer 3. Settled by whether any surveyed system carries summary provenance.

## Context
pkit gained two conventions from reading ECC (`docs/TOOL-CONTRACT.md` and
Tier-2 outcome evals). Of its six agent-infrastructure skills, five were
rejected — one deprecated by its own authors, two already covered better by
`swarm` and CoS, and `agent-self-evaluation` rejected outright for scoring
accuracy by grepping the agent's own prose. The twelfth-layer taxonomy in
`agent-architecture-audit` was the one idea with no equivalent in pkit: every
existing plugin acts on work products or process, and none diagnose why an
agent runtime degraded. This PRD proposes building that, in pkit's own shape,
for any host repository.
