# Tier-1: trigger evals (planned)

Tier-0 (`evals/validate.py`) checks that a skill is well-formed. It cannot
check the thing that actually matters: **does the skill fire when it should,
and stay quiet when it should not?**

That is Tier-1, and it is a v1 gate — not a v0.1 one. Nothing here runs yet.
This file specifies what to build.

Design borrowed from `keboola/ai-kit`'s evals.

## What a trigger eval is

A case pairs a user utterance with the skill that should (or should not) be
invoked in response. The eval runs the utterance against a session with the kit
installed and asserts which skills were selected.

```yaml
# evals/trigger-evals/troika-mode-1707.yaml
skill: troika-mode-1707
cases:
  - prompt: "three of us are going to work this epic, how do we not step on each other"
    expect: fire
  - prompt: "should this be a solo swarm or a troika"
    expect: fire
  - prompt: "set up the epic issue for the ingest work"
    expect: fire
  - prompt: "who owns block B3"
    expect: fire
  - prompt: "we keep colliding on the same files"
    expect: fire
  - prompt: "what is a troika in Russian history"
    expect: silent
  - prompt: "run the tests"
    expect: silent
```

## The bar before a skill reaches v1.0.0

- **At least 6 cases** per skill (see `CLAUDE.md`).
- **At least 2 of them negative** (`expect: silent`). A skill tested only on
  phrases that should fire it has been tested for enthusiasm, not precision.
- Negative cases should be *near misses* — phrasings that share vocabulary with
  the description but mean something else. "Judge the diff" fires
  `blind-judge`; "judge whether this design is worth building" should not.
- All cases pass on the model tier the kit targets.

## Why negative cases carry the weight

A skill that fires too eagerly is worse than one that fires too rarely. The
rare one gets invoked manually; the eager one injects a few thousand tokens of
irrelevant instructions into unrelated work, and the user uninstalls the
plugin rather than debugging why the agent keeps talking about Kentaurs.

Cross-skill collisions are the specific risk in this kit: `swarm`,
`blind-judge` and `troika-mode-1707` share vocabulary (review, orchestrate, phase,
gate). Each one's negative set should include at least one phrase that belongs
to a sibling.

## Known collision pairs to cover

| Utterance shape | Should fire | Should stay silent |
|-----------------|-------------|--------------------|
| "review this PR" | `blind-judge` | `second-opinion` |
| "ask another model what it thinks" | `second-opinion` | `blind-judge` |
| "run the phases in parallel" | `swarm` | `troika-mode-1707` |
| "how should we split this between the three of us" | `troika-mode-1707` | `swarm` |
| "write down why we picked Postgres" | `decision-log` | `troika-mode-1707` |
| "the tests pass but the page is blank" | `vibecoding` | `blind-judge` |

## Harness

To be built. The likely shape: `claude plugin eval` if the CLI supports the
case format above by the time this is picked up, otherwise a thin runner that
starts a headless session per case with the kit installed and inspects which
skills loaded.

Whatever the harness, the case files stay declarative YAML in this directory —
one file per skill, named after the skill.

## Status

| Skill | Cases | Status |
|-------|-------|--------|
| research | 0 | not started |
| vibecoding | 0 | not started |
| swarm | 0 | not started |
| second-opinion | 0 | not started |
| troika-mode-1707 | 0 | not started |
| decision-log | 0 | not started |
| blind-judge | 0 | not started |
| session-rules | n/a | hooks plugin, no skill to trigger |
