# pkit — kit conventions

Rules for working on this repository. They are about the kit itself, not about
what the skills say.

## Layout

```
.claude-plugin/marketplace.json     # the marketplace manifest — lists every plugin
plugins/<name>/
  .claude-plugin/plugin.json        # per-plugin manifest
  skills/<name>/SKILL.md            # the skill
  skills/<name>/references/         # optional supporting docs the skill links to
  skills/<name>/templates/          # optional files meant to be copied into a host repo
  hooks/hooks.json                  # hooks plugins only
  scripts/                          # hook scripts, referenced via ${CLAUDE_PLUGIN_ROOT}
evals/validate.py                   # Tier-0 static checks
evals/trigger-evals/                # Tier-1 plan
```

## One skill per plugin

A plugin ships exactly one skill, and the skill's `name` equals the plugin's
name equals the directory name. Installation is per plugin, so bundling two
skills means installing one to get the other.

The exception is a plugin that ships no skill at all — `session-rules` is hooks
only. That is fine; what is not fine is two skills in one plugin.

## Version lockstep

Three places carry the version:

1. `plugins/<name>/.claude-plugin/plugin.json` → `version`
2. `.claude-plugin/marketplace.json` → the plugin's entry `version`
3. the README inventory table, if the change is visible to a user

**They bump together, in the same PR.** `evals/validate.py` fails when 1 and 2
disagree. Bumping only the plugin manifest means the marketplace keeps serving
the old version and nobody notices for a week.

The marketplace's own top-level `version` bumps when the plugin roster changes
(a plugin added or removed), not on every plugin patch.

## Every skill needs at least 6 trigger-eval cases before v1

A skill stays below 1.0.0 until it has six or more trigger-eval cases in
`evals/trigger-evals/` (see the README there): cases that assert the skill
fires on the phrases its description claims, and cases that assert it does not
fire on near-miss phrases it should ignore.

Six is a floor, not a target. A skill with three positive cases and no negative
cases has been tested for enthusiasm, not for precision — the false-positive
side is where a skill becomes annoying enough to uninstall.

## Descriptions carry the triggers

A skill's frontmatter `description` is the only thing the model matches
against. It must state what the skill does **and** list the phrases that should
invoke it. Tier-0 enforces a 20-word minimum; the real bar is whether someone
who has never read the skill would recognize their own request in it.

## Append-only sections

Some sections are append-only, and the rule is enforced by convention here and
by a test in host repos (`decision-log`'s guard template):

- `troika-mode-1707`'s **Origin** section — never edited, never removed. It is how
  the mode remembers where it came from.
- `troika-mode-1707`'s **Lessons ledger** — delta-append only. Add entries at the
  bottom. Never reword, reorder, or delete existing ones. Superseding an entry
  means writing a new entry that cites the old one.

The reason is the same in both cases: an edited lesson erases the evidence that
the failure happened, and the failure then gets repeated. The ledger is
context-collapse evidence, and evidence you are allowed to rewrite is not
evidence.

## Scripts follow the tool-response contract

Every script a plugin ships writes into an agent's context, not a human's
terminal. Output carries four fields in order: `status`, `summary`,
`next_actions`, `artifacts`. `next_actions` is the one that changes agent
behaviour and the one everybody omits — an error without it is a bug, because
the agent then infers the fix and infers it wrong.

Hooks keep their existing rule on top of this: exit 0 with valid JSON, always,
and degrade to an empty payload rather than break the session. Validators are
gates and may exit non-zero; hooks are not and may not.

Full contract with worked examples: `docs/TOOL-CONTRACT.md`.

## Imported skills

`research`, `vibecoding`, `second-opinion` and `swarm` came from elsewhere (see
README provenance). When updating them:

- keep the provenance note in the README accurate
- for `swarm`, keep the **Provenance** section at the bottom of the SKILL.md —
  it lists what this fork changed, which is what a reader needs to know when
  comparing against upstream

## Before opening a PR

```bash
python3 evals/validate.py
claude plugin validate .          # if the CLI is available
```

Both must pass. CI runs the first one on every push and PR.
