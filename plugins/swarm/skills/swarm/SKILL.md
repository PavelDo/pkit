---
name: swarm
description: Orchestrated multi-agent implementation from a phased plan, with a separated blind judge and a human merge seat. Spawns worker agents in isolated git worktrees per phase, routes review to a fresh-context judge, handles retries and escalation, and stops at an open PR. Use when implementing a phased plan such as docs/PLAN.md. Triggers - "/swarm", "implement the plan", "run phased implementation", "execute PLAN.md phases", "fan out the phases", "swarm this plan".
---

# Swarm - Orchestrated Multi-Agent Implementation

Execute a phased implementation plan using an orchestrator plus worker agent
pattern. Each phase runs in its **own git worktree**, so the main checkout
never switches branches and independent phases can run in parallel.

Two rules separate this from the naive version of the pattern:

1. **The orchestrator does not judge its own spawn.** Review is delegated to a
   fresh-context judge that never sees the spawn prompt, the worker transcript,
   or who wrote the code (see the `blind-judge` skill).
2. **The swarm does not merge.** The happy path ends at an open, reviewed PR.
   Merging belongs to the merge seat — a human, or an agent explicitly granted
   that authority outside this skill.

## Arguments

- `/swarm` - Use default plan file `docs/PLAN.md`
- `/swarm <plan-file>` - Use specified plan file

## Step 0: Project conventions come from the project

This skill is repo-agnostic. Wherever it says "the project's test command",
"the project's entry points", or "the project's conventions", resolve those
from the host repo before spawning anyone — read `CLAUDE.md` / `AGENTS.md` /
`CONTRIBUTING.md`, the package manifest's script section, and the CI workflow.
Record what you resolved and pass it into every spawn prompt so all workers use
the same commands. Never assume a language, test runner, migration tool, ORM,
identifier type, or directory layout that the repo has not shown you.

## Workflow

```
For each phase in plan:
  1. Create a worktree + branch for the phase (main checkout stays on main)
  2. Spawn a worker agent inside that worktree
  3. Worker opens a DRAFT PR at its first commit, then implements
  4. Run deterministic oracles (tests, lint, typecheck, CI) — results are inputs
  5. Spawn a FRESH-CONTEXT judge on the diff (blind-judge skill)
  6. If pass: mark the PR ready for review, report the URL, STOP for the merge seat
  7. If findings: worker fixes (max 3 attempts)
  8. If max attempts exceeded: ESCALATE to human
```

Phases marked independent in the plan MAY run in parallel (one worktree +
one worker agent each). Dependent phases run sequentially.

Because the swarm no longer merges, a dependent phase whose parent PR is still
open must branch from the parent's branch, not from `main`, and its PR must
target the parent's branch. State that stacking explicitly in the plan and in
the PR body.

## Step 1: Parse the plan

Read the plan file and extract phases. Each phase has this structure:

```markdown
<!-- PHASE:N -->
## Phase N: Name

### Branch
`phase-N-name`

### Depends on
Phase N-1 (or "none" — independent phases may run in parallel)

### Scope
...

### Files to Create/Modify
...

### Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

### Tests Required
...
<!-- /PHASE:N -->
```

If the acceptance criteria cannot be written concretely enough for an
independent judge to verify them from the repository alone, stop. The plan is
not ready to execute — go back to a thinking mode first.

## Step 2: Create a worktree for the phase

Run from the primary checkout (never `git checkout` a phase branch there):

```bash
MAIN_WT=$(git worktree list --porcelain | head -1 | sed 's/^worktree //')
git -C "$MAIN_WT" pull origin main
git -C "$MAIN_WT" worktree add "$MAIN_WT/.claude/worktrees/<branch-name>" -b <branch-name> <base-ref>
```

`<base-ref>` is `main` for independent phases, or the parent phase's branch for
a stacked phase whose parent PR has not merged yet.

If the Agent tool supports `isolation: "worktree"`, prefer that — it creates
and cleans up the worktree automatically. Otherwise pass the worktree path to
the worker agent explicitly.

## Step 3: Spawn the worker agent

For parallel-safe phases, send multiple Task calls in a single message — one
worker per phase, each in its own worktree. Pin model and reasoning effort on
every spawn, and keep sibling workers homogeneous.

```
Task(
  subagent_type: "general-purpose",
  description: "Implement Phase N",
  prompt: """
You are implementing Phase N of a plan.

## Working directory
You work EXCLUSIVELY inside the worktree: <worktree-path>
It is already on branch <branch-name>. Never touch the primary checkout,
never switch branches. All file paths and commands are relative to this
worktree.

## Project conventions (resolved by the orchestrator — use these verbatim)
- Test command: <resolved test command>
- Lint / typecheck command: <resolved commands, or "none">
- Entry-point registration: <where routes/commands/handlers get registered>
- Config/secret convention: <e.g. .env.example, config module>
- Anything else the repo's CLAUDE.md / CONTRIBUTING.md mandates: <summary>

Do not invent conventions that are not in this list or visible in the repo.
Match the patterns of the modules that already exist.

## Task
Read the plan file, find Phase N (between <!-- PHASE:N --> markers), implement
EVERYTHING in Scope.

## Open a draft PR at your FIRST commit
Before doing the bulk of the work, commit what you have and run:

  git push -u origin <branch-name>
  gh pr create --draft --base <base-ref> --title "Phase N: <name>" --body "WIP"

A crashed session with a draft PR loses nothing. A crashed session with only
local commits loses everything.

## Your work will be reviewed by an independent judge
A separate agent with NO access to this prompt or your transcript will review
the diff against the plan. It can only see what is in the repository. Anything
you "explained" but did not encode in code, tests, or the PR body does not
exist as far as the judge is concerned.

It verifies:
1. **Every file** in "Files to Create/Modify" exists and has real implementation
2. **Every acceptance criterion** is fully implemented (not stubbed), with a
   file:function citation
3. **Every test** in "Tests Required" exists and passes under the project's
   test command
4. **Integration points** — entry points registered, config documented,
   schema and data-model changes consistent with the code that uses them
5. **Code quality** — no hardcoded values, no silent defaults, consistent with
   the patterns already in this repo

DO NOT:
- Create stub implementations (empty functions, no-op bodies, TODO comments)
- Skip any file from the list
- Write trivial tests that do not verify real behavior
- Weaken or delete an existing assertion to make a suite go green
- Leave acceptance criteria partially implemented
- Forget to register entry points or document new config vars

## Rules
1. Follow the project's own configuration standards (no hardcoded values,
   fail fast on missing required config)
2. Create ALL files listed in "Files to Create/Modify" — every single one
3. Write ALL tests specified in "Tests Required" — run them with the project's
   test command and verify they pass
4. For each acceptance criterion, identify WHERE in your code it is satisfied
5. Commit with clear messages referencing the phase

## Before handing off — self-review checklist
- [ ] All files from "Files to Create/Modify" exist
- [ ] No TODO/FIXME/placeholder comments in new code
- [ ] All acceptance criteria have corresponding implementation
- [ ] The project's test command passes locally
- [ ] The project's lint/typecheck commands pass, if the repo has them
- [ ] New entry points registered, new config vars documented

## When done
Update the draft PR body. Do NOT mark it ready yourself, and do NOT merge:

gh pr edit <pr-number> --body "$(cat <<'EOF'
## Implementation Summary
<brief description>

## Acceptance Criteria
- [ ] Criterion 1 - implemented in `<file>:<function>`
- [ ] Criterion 2 - implemented in `<file>:<function>`

## Tests
- <the project's test command> - X tests pass

## Files Changed
<list of files created/modified>
EOF
)"

Report back with the PR number and the exact commands you ran to verify.
"""
)
```

## Step 4: Run the deterministic oracles

Before any judgment, run what a machine can decide. Inside the phase worktree,
using the commands resolved in Step 0 — not guessed ones:

```bash
<project test command>       > /tmp/claude/phaseN-tests.txt   2>&1; echo "tests=$?"
<project lint command>       > /tmp/claude/phaseN-lint.txt    2>&1; echo "lint=$?"
<project typecheck command>  > /tmp/claude/phaseN-types.txt   2>&1; echo "types=$?"
gh pr checks <pr-number> --watch
```

Oracle results are **inputs to the judge**, not a substitute for it. A red
oracle is an automatic `findings` verdict — do not spend judge tokens on a diff
that does not build.

Also confirm the required checks actually ran against the working base. A green
check list that never executed against this branch's base is a CI illusion, not
a pass.

## Step 5: Spawn a FRESH-CONTEXT judge

Do NOT review the diff yourself. You wrote the spawn prompt; you are the worst
available judge of whether the spawn succeeded. Delegate to a judge that starts
from an empty context window.

Use the `blind-judge` skill if it is installed. If it is not, spawn a judge
directly with the constraints below — they are the load-bearing part.

```
Task(
  subagent_type: "general-purpose",
  description: "Judge Phase N diff",
  prompt: """
You are reviewing a pull request. You do not know who wrote it, whether it was
written by a human or an agent, or what instructions the author was given.
Do not speculate about authorship — it is not evidence.

## Inputs
- Repository worktree: <worktree-path>
- PR: <pr-number>          (diff: gh pr diff <pr-number>)
- Plan phase: <plan-file>, section between <!-- PHASE:N --> markers
- Oracle results (already run, treat as ground truth):
  - tests: <pass|fail> — /tmp/claude/phaseN-tests.txt
  - lint: <pass|fail|n/a> — /tmp/claude/phaseN-lint.txt
  - typecheck: <pass|fail|n/a> — /tmp/claude/phaseN-types.txt
  - CI required checks: <pass|fail|not-run>

## Rubric — five parts, evidence required for each
1. **File inventory.** For each file in "Files to Create/Modify": does it exist,
   and is the content substantial? Flag missing files, stubs (empty bodies,
   no-op functions), and TODO/FIXME/placeholder comments.
2. **Acceptance criteria.** One table row per criterion, each with a
   `file:function` citation and the evidence that it holds. A criterion with no
   citation is a finding, not a pass.

   | Criterion | Evidence (file:function) | Verified |
   |-----------|--------------------------|----------|
   | <verbatim criterion text> | <path>:<function> | <how you confirmed it> |

3. **Tests.** Do the tests named in "Tests Required" exist? Do they assert real
   behavior rather than tautologies? Does the diff weaken or delete any
   pre-existing assertion? Cross-check against the oracle output.
4. **Integration points.** Are new entry points registered where this project
   registers them? Are new config vars documented where this project documents
   them? Are schema or data-model changes consistent with the code that reads
   and writes them?
5. **Code quality.** Hardcoded values that belong in config; silent defaults for
   required config; divergence from the patterns used by comparable modules in
   this repo.

Judge only against the plan and this repository's own conventions. Do not
import conventions from other projects you have seen.

## Output
Write your report to /tmp/claude/phaseN-judge-<dimension>.md, ending with
exactly one machine-parseable line:

VERDICT: pass
or
VERDICT: findings

Under `findings`, list each finding as: severity, file:line, what is wrong,
what the plan or convention requires instead.
"""
)
```

## Step 6: Decision

### VERDICT: pass

Mark the PR ready and stop. **Do not merge.**

```bash
gh pr ready <pr-number>
gh pr comment <pr-number> --body-file /tmp/claude/phaseN-judge-consolidated.md
gh pr view <pr-number> --json url --jq .url
```

Report the PR URL to the human and move on to the next phase that does not
depend on this one. If a later phase depends on this PR, either stack its
branch on this one or wait for the merge seat.

Keep the worktree until the PR merges — it is the cheapest place to answer
review questions.

**The swarm never runs `gh pr merge`.** Merging is a separate seat with its own
authority: a human, or an agent explicitly granted merge rights by a mechanism
outside this skill. If you find yourself reasoning toward "this one is obviously
safe to merge", that is exactly the reasoning the seat exists to prevent.

### VERDICT: findings

```
Task(
  prompt: """
Your PR for Phase N has review findings.

## Working directory
Fix EXCLUSIVELY inside the worktree: <worktree-path> (branch <branch-name>).

## Findings
<paste the judge's findings verbatim — including file:line citations>

## Required changes
1. ...

Fix, commit, and push to the same branch. Re-run the project's test command
before pushing. Attempt: <N>/3
"""
)
```

Then re-run Step 4 (oracles) and Step 5 with a **new** judge instance. Never
continue the previous judge's context — a judge that has already argued for a
verdict will defend it.

### Attempt >= 3

```
ESCALATE: Phase N requires human intervention.
PR: <url>
Attempts: 3/3
Persistent findings: <what the judge flagged in each round>
```

Keep the worktree and the open PR for inspection. Stop and notify the user.
Do not raise the attempt limit on your own judgment — three failed rounds
usually means the plan, not the worker, is what is wrong.

## Step 7: Progress tracking

Status is derived from PR state, never asserted from memory:

```bash
gh pr list --state all --json number,title,isDraft,state,url
```

```
## Swarm Progress

| Phase | Status          | Worktree                       | PR  | Attempts |
|-------|-----------------|--------------------------------|-----|----------|
| 1     | READY_FOR_MERGE | .claude/worktrees/phase-1-core | #12 | 1        |
| 2     | IN_PROGRESS     | .claude/worktrees/phase-2-api  | #13 | 2        |
| 3     | PENDING         | -                              | -   | -        |
```

Statuses: `PENDING`, `IN_PROGRESS` (draft PR open), `IN_REVIEW` (judge running),
`READY_FOR_MERGE` (judge pass, PR marked ready), `MERGED` (the merge seat acted),
`ESCALATED`.

## Post-merge cleanup

This runs only after the merge seat has merged — it is not part of the swarm's
happy path:

```bash
git -C "$MAIN_WT" pull origin main
git -C "$MAIN_WT" worktree remove "$MAIN_WT/.claude/worktrees/<branch-name>"
git -C "$MAIN_WT" worktree prune
git -C "$MAIN_WT" branch -d <branch-name> 2>/dev/null || true
git -C "$MAIN_WT" remote prune origin
```

## Error handling

- **Merge conflict between parallel phases:** escalate immediately. Two phases
  touching the same files means the plan's dependency graph is wrong.
- **`worktree add` fails (branch exists):** `git worktree prune`, delete the
  stale branch, retry once.
- **CI failure:** counts as a failed review attempt.
- **Required checks did not run against this base:** treat as a failure, not a
  pass. Fix the check configuration before continuing.
- **Judge report file missing:** fail loudly. A missing report is never a pass.
- **Agent timeout:** retry once, then escalate.
- **Network error:** retry with backoff.

## Related skills

- `blind-judge` — the review protocol invoked in Step 5, including per-dimension
  panels and scope-gated staffing.
- `troika-mode` — when more than one human is involved, the swarm runs inside a
  Troika instead of solo.
- `decision-log` — record the judge verdict (JUDGE-V) and any gate relaxation
  (GATE-X) as durable records.

## Provenance

Adapted from the `swarm` skill in
[padak/claude-code-kit](https://github.com/padak/claude-code-kit) (Petr
Simecek). Changes in this fork: the reviewer is a separate fresh-context judge
rather than the orchestrator reviewing its own spawn; deterministic oracles run
before judgment; the happy path ends at an open PR instead of an automatic
squash-merge; project conventions are resolved from the host repo rather than
assumed.
