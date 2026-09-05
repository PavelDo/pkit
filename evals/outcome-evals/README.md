# Tier-2: outcome evals (planned)

Tier-0 (`evals/validate.py`) checks a skill is well-formed. Tier-1
(`evals/trigger-evals/`) checks it fires when it should and stays quiet when it
should not. Neither checks the thing the kit exists for: **does the work come
out better with the skill than without it?**

That is Tier-2. Nothing here runs yet. This file specifies what to build.

Method borrowed from ECC's `agent-eval` (MIT). The A/B framing is ours — theirs
compares agents against each other, which is not the question a kit has.

## The question is A/B, not leaderboard

ECC's tool answers "is Claude Code better than Aider on this task." Useful to
them, useless here — we are not choosing an agent. The pkit question is:

> Run the same task twice on the same commit, once with the plugin installed
> and once without. Does the plugin-installed run pass more often, cost less,
> or finish faster?

A skill that does not move any of those three numbers is a skill that costs
context and returns nothing. **That is the finding Tier-2 exists to produce**,
and it is the finding no amount of trigger testing can reach.

## What a case looks like

```yaml
# evals/outcome-evals/blind-judge.yaml
plugin: blind-judge
repo: ./fixtures/pr-with-planted-bug
commit: 3f9a1c2          # pinned — the run is meaningless if the tree moves
runs: 3                   # repeated, for consistency
prompt: |
  Review the diff on this branch and report whether it is safe to merge.
judge:
  - type: grep
    pattern: "off-by-one|boundary|index"
    files: report.md      # did the review find the planted bug at all
  - type: command
    command: python fixtures/assert_verdict.py report.md --expect reject
arms:
  - with-plugin
  - without-plugin
```

Each arm runs in **its own git worktree** off the pinned commit, so the arms
cannot contaminate each other and no run can corrupt the base repo. No Docker.

## Metrics

| Metric | What it tells you |
|--------|-------------------|
| Pass rate | Did the judge accept the output |
| pass@1 / pass@3 | First-try reliability vs. eventual reliability |
| Consistency | Pass rate across repeated runs — 3/3 and 1/3 are different skills |
| Cost | API spend per task, per arm |
| Time | Wall-clock to completion |

**Consistency is the one to watch.** A skill that passes 1 of 3 has not passed;
it has produced one good run and two you would have shipped. Trigger evals
cannot see this because firing is deterministic and outcomes are not.

## Fixtures need planted failures

An outcome eval against a clean repo measures nothing — both arms pass. Every
fixture carries a **known defect** the skill is supposed to catch, and the
judge asserts on finding it. Writing the fixture is most of the work, and a
fixture whose defect both arms find is a fixture that is too easy.

## The bar

Tier-2 is not a v1 gate. Tier-1 is. Tier-2 is what you run before claiming a
plugin is worth its context budget, and before a change to a mature plugin
lands — a refactor of `swarm` or `blind-judge` should have to show it did not
regress the numbers.

## Build order

1. One fixture repo with one planted defect, and `blind-judge` as the subject —
   it has the clearest pass/fail and the most to lose from a bad refactor.
2. The runner: worktree per arm, N runs, judge dispatch, metrics table out.
3. A second fixture for `vibecoding`, where the planted defect is a test that
   passes against broken UI — the exact failure that plugin exists to prevent.
