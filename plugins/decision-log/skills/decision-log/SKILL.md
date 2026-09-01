---
name: decision-log
description: Write append-only decision records into a decisions/ directory in the host repo - PRD-D for product decisions, ARCH-D for architecture with rejected alternatives and a named guard, JUDGE-V for review verdicts, GATE-X for gate exceptions with expiry, MODEL-R for model routing, TEST-D for deliberate test gaps. Use when a decision has just been made and should survive the session. Triggers - "record this decision", "write an ADR", "decision log", "log the verdict", "gate exception", "why did we choose", "document the tradeoff", "what did we decide about".
---

# Decision Log

Append-only decision records in the host repository, under `decisions/`.

A record exists so that six weeks later someone can answer "why is it like
this?" without finding the person who decided. It is an artifact of audit and
retrieval.

## The rule that makes this work

**Records are for audit and retrieval. The enforcement travels separately.**

A decision written into `decisions/` changes nothing on its own. Nobody reads
a directory of markdown before writing code, and an agent certainly does not.
Every decision that must actually hold needs three things, not one:

1. **The record** — in `decisions/`, for the why, the alternatives, and the date.
2. **A one-line positive rule in `CLAUDE.md`** — stated as what to do, not what
   to avoid. "Money values are integer minor units" beats "never use floats for
   money": a positive rule is checkable and does not plant the thing it forbids.
3. **A mechanical guard** — a hook, a lint rule, a CI check, or a test.

**Every ARCH-D must name its guard.** A record whose Guard field says "team
discipline" is a record of an intention, not a decision. If no guard can be
named, either write the guard first or write the record honestly as an
aspiration.

## File naming

```
decisions/YYYY-MM-DD-<type>-<slug>.md
```

Examples:

```
decisions/2026-09-01-PRD-D-mode-routing-ingest-epic.md
decisions/2026-09-01-ARCH-D-single-writer-per-partition.md
decisions/2026-09-02-JUDGE-V-phase-3-adapter.md
decisions/2026-09-02-GATE-X-skip-typecheck-release-cut.md
```

`<slug>` is lowercase, hyphenated, and describes the subject — not the outcome.
Two records about the same subject on different dates sort next to each other,
which is what you want when reading history.

## Append-only

Existing records are **never modified and never deleted**. A decision that gets
reversed is superseded by a new record that cites the old one:

```markdown
Supersedes: decisions/2026-08-14-ARCH-D-shared-writer-pool.md
```

The reason is not bureaucracy. An edited record erases the evidence that the
first decision was ever made, which erases the evidence that it failed — and
the same decision gets made again. The guard test shipped with this skill turns
this rule into a CI failure rather than a convention.

## The six types

### PRD-D — product decision

What is decided, and what is explicitly still open. The open list matters more
than the decided list: it is what stops the next session from re-litigating
settled scope while quietly assuming an unsettled thing.

```markdown
# PRD-D: <subject>
Date: YYYY-MM-DD
Decided-by: <who ratified>

## Decided
- <thing that is now fixed>

## Open
- <thing deliberately not decided yet, and what would settle it>

## Context
<one paragraph — the situation that forced the decision>
```

### ARCH-D — architecture decision

```markdown
# ARCH-D: <subject>
Date: YYYY-MM-DD
Decided-by: <who>

## Decision
<one sentence, present tense>

## Rejected alternatives
- <alternative> — rejected because <reason>

## Non-goals
- <what this deliberately does not try to do>

## Guard
<the NAMED mechanism that enforces this: test path, lint rule, CI job, hook>
```

The Guard field is mandatory. Name the file.

### JUDGE-V — judge verdict

```markdown
# JUDGE-V: <PR or change under review>
Date: YYYY-MM-DD
Verdict: pass | findings

## Per-criterion evidence
| Criterion | Evidence (file:function) | Result |
|-----------|--------------------------|--------|
| <verbatim criterion> | <path>:<symbol> | pass / finding |

## Findings
- <severity> <file:line> — <what is wrong> — <what is required instead>
```

### GATE-X — gate exception

```markdown
# GATE-X: <gate being relaxed>
Date: YYYY-MM-DD
Granted-by: <who>

## Relaxation
<exactly which gate, for exactly which scope>

## Reason
<why now>

## Compensating control
<what covers the risk while the gate is down>

## Expiry
YYYY-MM-DD  — after this date the relaxation is void, not renewed by default
```

No expiry means it is not an exception, it is a change to the gate. Write it as
an ARCH-D instead and argue for it on the merits.

### MODEL-R — model routing decision

```markdown
# MODEL-R: <scope — which role or which run>
Date: YYYY-MM-DD

## Routing
<role> → <model>, effort <level>

## Rationale
<why this departs from, or confirms, the standing policy>

## Ledger citation
<the lessons-ledger entry or measurement this rests on>
```

### TEST-D — deliberate test gap

```markdown
# TEST-D: <area>
Date: YYYY-MM-DD

## Deliberately untested
- <what> — because <reason> — revisit when <condition>

## Never-weaken scope
<the assertions and test files that may not be weakened or deleted to make a
suite pass; changing them requires a new TEST-D that supersedes this one>
```

TEST-D exists so that "we do not test this" is a decision with an owner and a
date, rather than a gap that everyone assumes someone else considered. The
never-weaken scope is what a judge cites when a diff quietly loosens an
assertion.

## Writing a record

1. Pick the type. If two fit, write two records — they retrieve differently.
2. Compute the filename: `decisions/<today>-<TYPE>-<slug>.md`.
3. Check the file does not already exist. If it does, pick a sharper slug —
   never overwrite.
4. Write it. Keep the Context to one paragraph; a record nobody finishes
   reading is a record nobody reads.
5. For ARCH-D: confirm the Guard exists, or create it in the same change.
6. If the decision needs to bind future sessions, add the one-line positive
   rule to `CLAUDE.md` (and to `decisions/RULES.md` if the repo uses the
   `session-rules` hooks).

## The guard test

`templates/test_decisions_append_only.py` is a pytest template that fails CI
when any existing file under `decisions/` was modified or deleted relative to
the merge base. Only additions are allowed.

Install it into the host repo:

```bash
mkdir -p tests
cp "${CLAUDE_PLUGIN_ROOT}/skills/decision-log/templates/test_decisions_append_only.py" \
   tests/test_decisions_append_only.py
```

It needs full git history against the base branch, so CI must not use a
shallow single-commit checkout — `fetch-depth: 0` on `actions/checkout`, or an
explicit `git fetch origin <base>`.

## Related skills

- `troika-mode` — the mode that produces PRD-D, GATE-X and MODEL-R records.
- `blind-judge` — produces JUDGE-V verdicts.
- `session-rules` — reads `decisions/` back into the session at start.
