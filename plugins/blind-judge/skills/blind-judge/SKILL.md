---
name: blind-judge
description: Fresh-context judging protocol for code review - deterministic oracles run first and feed the judge, the judge never sees the implementer's transcript, spawn prompt, or authorship, one isolated judge instance per rubric dimension, and a consolidator that fails loudly when an expected report is missing. Use when reviewing an agent-written diff or PR, when a review needs to be trusted rather than reassuring, or when setting up a review gate. Triggers - "blind judge", "review this PR", "judge the diff", "independent review", "who reviews the agent", "review gate", "panel review", "verdict".
---

# Blind Judge

A review protocol for work an agent produced. It answers one question: is this
review evidence, or is it the author agreeing with itself?

## Why blind

The orchestrator that wrote the spawn prompt is the worst available reviewer of
the spawn's output. It knows what it asked for, so it reads the diff as a
confirmation of its own intent, and it has already spent tokens on the run it
is being asked to reject. Same-context review reliably produces the verdict the
context wants.

So: the judge starts from an empty context window and is told nothing about who
wrote the code.

## The four rules

### 1. The judge is blind to authorship and provenance

The judge does **not** receive:

- the implementer's transcript or conversation history
- the spawn prompt the implementer was given
- whether the code was written by a human or an agent, which model, or how many
  attempts it took
- any framing along the lines of "this should be fine" or "quick review"

The judge **does** receive: the diff, the specification it is judged against,
the repository, and the oracle results.

Say it explicitly in the judge's prompt, because it will speculate otherwise:

> You do not know who wrote this or what instructions they were given.
> Authorship is not evidence. Do not reason about it.

The reason is not fairness to the author — there is no author to be fair to.
It is that authorship information is a shortcut the judge will take instead of
reading the code.

### 2. Deterministic oracles run FIRST and are inputs

Anything a machine can decide, a machine decides — before the judge starts.
Tests, linters, type checkers, build, CI required checks, schema validators.
Run them with the host repo's own commands (resolve them from `CLAUDE.md`,
`AGENTS.md`, `CONTRIBUTING.md`, the package manifest, or the CI workflow — do
not guess a test runner).

```bash
<project test command>      > /tmp/claude/judge-tests.txt 2>&1; echo "tests=$?"
<project lint command>      > /tmp/claude/judge-lint.txt  2>&1; echo "lint=$?"
<project typecheck command> > /tmp/claude/judge-types.txt 2>&1; echo "types=$?"
```

Their results go into the judge's prompt as **ground truth**. Two consequences:

- A red oracle is an automatic `findings` verdict. Do not spend judge tokens on
  a diff that does not build.
- The judge never re-litigates an oracle. If the suite is green, the judge's
  job is whether the suite tests the right thing — not whether it passed.

Also confirm the required checks actually executed against the working base. A
green check that never ran against this branch's base is a CI illusion.

### 3. One isolated judge per dimension

Do not ask one judge for correctness, security, architecture, and test quality
in a single pass. A single judge spends its attention on whichever dimension
the diff makes most salient, and reports thin coverage of the rest as clean.

Spawn one judge instance per dimension, each with only its own rubric, each
writing to its own report file.

| Dimension | Asks |
|-----------|------|
| `correctness` | Does it do what the spec says, on the normal path and the edges? |
| `security` | Injection, authz/authn, secret exposure, unsafe deserialization, SSRF, injection through untrusted input |
| `architecture` | Does it fit the patterns this repo already uses? What did it couple that was separate? |
| `tests` | Do the tests assert real behavior? Does the diff weaken or delete an existing assertion? |

Each judge writes to a predictable path:

```
/tmp/claude/judge-<change-id>-<dimension>.md
```

### 4. The consolidator verifies before it merges

The consolidator collects the per-dimension reports and produces one verdict.
Before merging anything, it checks that **every expected report file exists**
and ends with a parseable verdict line.

**A missing report is never a pass.** It is a crashed judge, a timed-out spawn,
or a path typo — all three of which look exactly like silence, and silence
reads as approval unless the consolidator refuses to let it.

```python
missing = [d for d in expected_dimensions if not report_path(d).exists()]
if missing:
    raise SystemExit(f"judge reports missing for: {', '.join(missing)} — not a pass")
```

Consolidated verdict is `pass` only if every dimension returned `pass`.

## Verdict grammar

Every judge report ends with exactly one line, and nothing after it:

```
VERDICT: pass
```

or

```
VERDICT: findings
```

Two values, lowercase, machine-parseable. Not "approved with minor notes", not
"pass (see caveats)", not an emoji. A grammar with two values forces the judge
to decide; a grammar with a hedge lane means every borderline diff takes it.

Parse it strictly:

```bash
grep -E '^VERDICT: (pass|findings)$' "$report" | tail -1
```

No match is a malformed report, which is a failure — not a pass.

Under `findings`, each item is: severity, `file:line`, what is wrong, and what
the spec or convention requires instead. A finding without a citation is an
opinion.

## Panel staffing is scope-gated

Staff the panel by what the change actually touches. Running the security judge
on a docs-only diff burns tokens and trains everyone to ignore the panel.

The host repo may ship an optional `panel.yaml` mapping path globs to
dimensions:

```yaml
# panel.yaml — optional, in the host repo root
dimensions:
  correctness:
    - "**/*"
  tests:
    - "**/*"
  security:
    - "**/auth/**"
    - "**/*permission*"
    - "**/api/**"
    - "**/migrations/**"
  architecture:
    - "**/core/**"
    - "**/*.sql"
    - "**/schema/**"
```

Resolve the panel from the changed paths:

```bash
gh pr diff <pr-number> --name-only
```

**Default when `panel.yaml` is absent: `correctness` + `tests`.** Those two are
the floor, not a compromise — a change that is correct and honestly tested is
the minimum bar, and adding dimensions is an explicit decision the repo makes
by writing the file.

Record any deliberate narrowing of the panel below what `panel.yaml` calls for
as a `GATE-X` record with a compensating control and an expiry (see the
`decision-log` skill).

## Rubric design beats judge size

Measured effect on judge accuracy: **rubric quality contributed 30.4 percentage
points; judge model size contributed 24.3**. The rubric is the bigger lever,
and it is the cheaper one.

So the default is **Sonnet-tier judges with well-specified rubrics**, not
frontier-tier judges with vague ones. Spend the effort on writing criteria that
can only be answered with a citation, and spend the model budget on the
orchestrator instead.

A well-specified rubric criterion:

- names what evidence would satisfy it (`file:function`, a passing test, a
  registered route)
- can be answered `pass` or `finding` without a judgment call about tone
- is written against this repo's conventions, not against generic best practice

A badly-specified one asks "is the code good quality?" and gets back prose.

## Standard judge prompt

```
You are reviewing a change. You do not know who wrote it, whether it was
written by a human or an agent, or what instructions they were given.
Authorship is not evidence — do not reason about it.

## Dimension
You are judging ONE dimension: <dimension>. Ignore issues outside it; another
judge covers them. Do not broaden your scope to seem thorough.

## Inputs
- Repository: <path>
- Diff: gh pr diff <pr-number>   (or: git diff <base>...<head>)
- Specification: <plan section / issue / acceptance criteria — verbatim>
- Oracle results (already run — treat as ground truth, do not re-litigate):
  - tests: <pass|fail> — /tmp/claude/judge-tests.txt
  - lint: <pass|fail|n/a> — /tmp/claude/judge-lint.txt
  - typecheck: <pass|fail|n/a> — /tmp/claude/judge-types.txt
  - CI required checks: <pass|fail|not-run>

## Rubric
<the dimension's criteria — each one stating what evidence satisfies it>

## Output
Write your report to /tmp/claude/judge-<change-id>-<dimension>.md:

1. A per-criterion evidence table:

   | Criterion | Evidence (file:function) | Result |
   |-----------|--------------------------|--------|
   | <verbatim criterion> | <path>:<symbol> | pass / finding |

   A criterion with no citation is a finding, not a pass.

2. Findings, each as: severity, file:line, what is wrong, what is required
   instead.

3. The last line of the file, exactly:

VERDICT: pass
or
VERDICT: findings
```

## Consolidation report

```markdown
## Blind judge — <change-id>

| Dimension | Verdict | Report |
|-----------|---------|--------|
| correctness | pass | judge-<id>-correctness.md |
| tests | findings | judge-<id>-tests.md |

Oracles: tests pass, lint pass, typecheck n/a, CI required checks pass (ran against base).
Panel staffed from panel.yaml on changed paths: <paths>

### Blocking findings
- <severity> <file:line> — <what> — <required instead>

VERDICT: findings
```

Record the consolidated result as a `JUDGE-V` decision record when the change
is significant enough to want the evidence later.

## Related skills

- `swarm` — invokes this protocol as its review step.
- `troika-mode` — makes blind-judge review a shared gate across Kentaurs.
- `decision-log` — JUDGE-V for verdicts, GATE-X for panel narrowing.
- `second-opinion` — a different tool: an external model's opinion, not a gate.
