---
name: troika-mode
description: The Troika working mode for multi-agent, multi-human epics — Kentaurs (one human plus their agents), at most three per epic, the epic issue as the room, status derived from draft PRs, shared gates, and a mode-routing intake. Use when starting an epic with more than one person, when deciding how to run a piece of work (think mode, solo swarm, Troika, worktree fan-out), or when coordination is drifting. Triggers - "troika mode", "how should we run this", "mode routing", "who owns which block", "set up the epic", "kentaur", "we are stepping on each other", "coordinate the agents".
---

# Troika Mode v0.2

v0.1 = `keboola/agnes-the-ai-analyst#1707`, run by hand in Aug 2026.

## Origin (kept forever)

Troika Mode v0.1 was `keboola/agnes-the-ai-analyst` issue **#1707**, run
2026-08-28 to 2026-08-31: Monika Feigler as PO briefing an autonomous Claude
loop operating under padak's identity, roughly 30 PRs merged in three days.
The five breakdowns that run taught are seeded in the Lessons ledger below.

This section is append-protected in the same way the ledger is: **never edit or
remove it in future versions.** It is how the mode remembers how it started.

A working mode for epics where more than one person, each with their own
agents, works the same body of code at the same time. It exists because the
failure modes of that setup are not code failures — they are coordination
failures, and they repeat.

## Definitions

**Kentaur.** One human plus their agents, operating as a single unit. One
identity, one accountability line. When a Kentaur commits, reviews, or claims a
block, it does not matter which half did the typing — the human half owns the
outcome. A Kentaur is the smallest unit that can be assigned work.

**Troika.** At most **three Kentaurs per epic**. Three is not a style
preference. Beyond three, the coordination surface grows faster than the work,
the room fills with status talk, and blocks start colliding. If an epic needs
more than three Kentaurs, it is more than one epic — split it.

**The room.** The epic issue. Not a chat channel, not a call, not a thread that
scrolls away.

## The epic issue is the room

The epic issue has exactly two parts.

### 1. Immutable decisions header

The decisions that constrain the epic, recorded as PRD-D records (see the
`decision-log` skill). The header is append-only. A decision that turns out to
be wrong is superseded by a new record that cites it — never edited in place,
never deleted. The header is where a Kentaur joining on day four learns what
was already settled without reading four days of comments.

### 2. Work blocks with explicit dependency edges

Each block carries:

- an ID and a one-line scope
- **Depends-on:** the block IDs it cannot start before
- acceptance criteria concrete enough for an independent judge
- the claiming Kentaur (or empty)

**The graph lives in the plan, not in prose.** If the dependency between two
blocks exists only because someone said it on a call, it does not exist. Write
the `Depends-on` edge or accept that the blocks will run in parallel and
collide.

```markdown
### Block B3 — Ingest adapter
Depends-on: B1
Claimed-by: (tracker assignment)
Acceptance:
- [ ] Adapter registered where this project registers adapters
- [ ] Round-trip test over a fixture with the malformed-row case
```

## The five rules

### 1. Block claiming is tracker assignment

A Kentaur claims a block by taking the assignment in the tracker. The lock
lives in the tracker, **never in chat**. "I'll take B3" in a message is not a
claim — two Kentaurs can both say it, both believe it, and both start. The
tracker can only hold one assignee, which is the entire point.

### 2. Per-Kentaur branch, worktree, and identity

Each Kentaur works in its own branch and its own git worktree. Commits carry
that Kentaur's identity. Never share a branch between Kentaurs and never let
one Kentaur push to another's branch — the accountability line has to survive
`git log`.

### 3. Status is DERIVED, never asserted

Status comes from pull requests, not from comments.

- Open a **draft PR at the first commit** of a block. Not when it is ready —
  at the first commit.
- Block status is a function of PR state: no PR = not started; draft PR =
  in progress; PR marked ready = awaiting review; merged = done.
- A comment saying "B3 is nearly done" is not status. It is a claim about
  status, and claims drift.

Anyone can compute the epic's true state with one query:

```bash
gh pr list --state all --json number,title,isDraft,state,url,headRefName
```

### 4. Shared gates

Every Kentaur passes the same gates. Gates are shared precisely so that no
Kentaur's local judgment can lower them.

| Gate | Applies to |
|------|-----------|
| CI required checks | every PR — and the checks must run against the working base |
| Blind-judge review | every PR (see the `blind-judge` skill) |
| Human merge seat | any change touching schema, RBAC/permissions, or a public API contract |

The merge seat is a human by default. Relaxing any gate requires a **GATE-X**
record naming the compensating control and an expiry date. A relaxation with no
expiry is a permanent change to the gate, and should be argued for as one.

### 5. The room holds stop-authority, never task state

The epic issue is where anyone says "stop, this is wrong" — scope disputes,
decision reversals, gate exceptions, escalations. It is not where anyone tracks
what percent complete a block is. Task state lives in the tracker and in the
PRs. Keep the room small enough that stop-authority is actually readable.

## Mode-routing intake

Before starting, the orchestrator asks these four questions and records the
answers as a single PRD-D line. This is the intake, and it is cheap — skipping
it is how work ends up in the wrong mode for three days.

**1. Can the acceptance criteria be written now?**
No → go to a thinking mode first (for example `gstack /office-hours`) and stay
there until the answer is yes. Nothing downstream works without verifiable
criteria: the judge has nothing to judge, and the blocks have nothing to close
against.

**2. Solo, or with others?**
Solo → solo swarm (the `swarm` skill, one Kentaur).
Others → Troika, capped at three Kentaurs.

**3. Does this touch production or users?**
Yes → full gates (CI + blind judge + human merge seat where rule 4 requires it).
Spike → tests only. A spike that starts touching production stops being a spike
and picks up the full gates; that transition needs a new PRD-D line, not a
quiet reclassification.

**4. Is the work parallelizable, or larger than one context window?**
Yes → worktree fan-out, orchestrated by Opus.
No → a single session.

### The recorded line

```
PRD-D: mode routing for <epic> — criteria: yes | shape: troika(3) |
exposure: production/full-gates | parallelism: fan-out(4 worktrees)
```

## Decision rights on mode

The agent **proposes** the mode by running the rubric above. The human half of
the Kentaur **ratifies** it as part of approving the plan. The agent does not
select its own operating mode unilaterally.

Routine ratifications may be delegated later per the autonomy registry — the
point of writing the PRD-D line is that such a delegation stays auditable. You
can look back and see which mode was chosen, on what rubric answers, and who
ratified it. Without the record, delegation is indistinguishable from drift.

## Model policy

- **Opus 5, high effort, orchestrates by default.** Orchestration is the role
  where a wrong call costs the most and the token spend is the smallest share
  of the run.
- **Fable only for >1-context-window work or fan-outs wider than 25.** Below
  that threshold the cost is not justified by the outcome.
- **Sonnet 5 for workers.** Keep sibling workers **homogeneous** — same model,
  same effort. Heterogeneous siblings produce diffs of visibly different
  quality against the same criteria, which the judge then has to disentangle.
- **Pin model and reasoning effort on every subagent spawn.** An unpinned spawn
  inherits whatever the parent happened to be running, which makes the run
  unreproducible.

Model routing decisions that depart from this policy get a **MODEL-R** record
citing the lessons ledger entry that motivated them.

## Lessons ledger

**Append-only. Delta-append, never rewritten.** Each entry records what broke
and what changed in response. The ledger is the evidence trail for
context-collapse: when a lesson is quietly edited away, the failure that
produced it becomes invisible and gets repeated. Add entries at the bottom;
never reword, reorder, or delete existing ones. Superseding an entry means
writing a new entry that cites the old one.

### v0.1 → v0.2 (from `keboola/agnes-the-ai-analyst#1707`)

- **CI-illusion day.** Required checks were green while never having run
  against the working base. Green is only green when the checks executed
  against the base the branch actually merges into. → Verify check
  configuration covers the working base before trusting a pass.
- **Comment-polling lost 2 briefs.** Polling an issue for new comments silently
  dropped two briefs between polls. → Event-driven intake, or a durable
  last-read cursor. Never a poll with in-memory state.
- **Mutable status drifted twice.** Status written into comments diverged from
  reality twice in one epic. → Derive status from PRs. Do not write status into
  prose.
- **Session crash lost work.** A crashed session lost uncommitted and unpushed
  work. → Draft PR at the first commit, always.
- **Gate erosion under time pressure.** Gates were relaxed informally near a
  deadline and never restored. → Every relaxation needs a GATE-X record with a
  compensating control and an expiry date.

## Related skills

- `swarm` — the execution mechanic for fan-out inside a Kentaur.
- `blind-judge` — the shared review gate.
- `decision-log` — where PRD-D, GATE-X, MODEL-R and the rest are written.
- `session-rules` — surfaces the decisions header into every session.
