# The tool-response contract

Every script a pkit plugin ships writes into an agent's context, not a human's
terminal. A hook's stdout, a validator's report, a guard's failure — the agent
reads all of it and decides what to do next. Shapeless output makes it guess.

This is the shape. Four fields, in this order.

| Field | What it carries |
|-------|-----------------|
| `status` | `success` \| `warning` \| `error`. One word, first. |
| `summary` | One line. What happened, not how. |
| `next_actions` | What the agent should do about it. Omit only when there is genuinely nothing to do. |
| `artifacts` | Paths and IDs the agent can open. Never re-print the content. |

The shape came from reading ECC's `agent-harness-construction` (MIT). The
reasoning below is ours, and so are the examples.

## Why `next_actions` is the one that matters

The other three are hygiene. `next_actions` is the field that changes agent
behaviour, and it is the one everybody omits.

`evals/validate.py` today prints this on failure:

```
FAIL: 2 problem(s) across 8 plugin(s)
  - plugins/foo/skills/foo/SKILL.md: frontmatter is missing `description`
  - marketplace.json: plugin 'foo' has no string `source`
```

That is a correct `status` and a correct `summary` with the failures as
evidence. It does not say what to do, so the agent infers — and a wrong
inference here means editing the marketplace when the fix was in the skill.
With the field:

```
next_actions:
  - add a `description` to plugins/foo/skills/foo/SKILL.md (20-word minimum)
  - set `source` to "./plugins/foo" in marketplace.json
```

The agent now edits the right two files without reasoning about it. Every
inference you remove is a class of mistake you remove.

## Failure paths are part of the contract

`plugins/session-rules/scripts/_common.py` already states the rule this repo
runs on:

> always exit 0 with valid JSON on stdout. A hook that can break a session is
> worse than no hook at all, so every failure path degrades to "emit nothing".

That stays. The contract adds shape to the success path; it never adds a way
for a script to take the session down. Concretely:

- A hook that cannot do its job emits an empty payload and exits 0.
- A validator that fails emits `status: error` and exits non-zero — validators
  are gates, hooks are not.
- Nothing raises into the transport.

## Rules

1. **`status` first, always.** The agent should not have to parse prose to
   learn whether something worked.
2. **`summary` is one line.** If it needs two, the second one belongs in
   `next_actions` or in an artifact.
3. **`next_actions` are imperative and specific.** "Fix the config" is not an
   action. "Set `source` to ./plugins/foo in marketplace.json" is.
4. **`artifacts` are references, never content.** A path costs ten tokens; the
   file costs two thousand, and the agent may not need it.
5. **An error without `next_actions` is a bug.** If a script can detect a
   problem it can almost always name the fix. Ship the fix with the detection.

## Anti-patterns

- **Error-only output.** A stack trace tells the agent something broke and
  nothing about what to do, so it retries the same call.
- **Success that says nothing.** `OK` with no summary means the next agent
  cannot tell a real pass from a no-op that found zero files.
- **Inlining the artifact.** Printing a 400-line diff into context to say a
  diff exists.
- **Prose status.** "It looks like the validation mostly succeeded, though
  there were a couple of issues" — unparseable, and it hedges.
