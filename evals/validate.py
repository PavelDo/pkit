#!/usr/bin/env python3
"""pkit Tier-0 static validation.

Checks that hold for every plugin in this marketplace, without invoking a
model. Tier-0 is cheap and runs on every push; Tier-1 (trigger evals) is
described in evals/trigger-evals/README.md.

Checks
------
1. marketplace.json parses, and every plugin's `source` directory exists
2. every plugin has .claude-plugin/plugin.json that parses
3. plugin.json `name` matches the marketplace entry and the directory name
4. plugin.json `version` matches the marketplace entry's version
5. every SKILL.md has `name` and `description` in its frontmatter
6. a skill's `name` matches its containing directory name
7. a skill's `description` is at least MIN_DESCRIPTION_WORDS words
8. every plugin ships either a skill or a hooks manifest
9. no unquoted frontmatter scalar contains ": ", which makes YAML parsing fail
   and silently drops every frontmatter field at load time

Exit code 0 when everything passes, 1 otherwise.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"
PLUGIN_MANIFEST_RELPATH = Path(".claude-plugin") / "plugin.json"
HOOKS_MANIFEST_RELPATH = Path("hooks") / "hooks.json"
SKILLS_DIRNAME = "skills"
SKILL_FILENAME = "SKILL.md"

# A description shorter than this cannot carry both a capability statement and
# the trigger phrases the model matches against.
MIN_DESCRIPTION_WORDS = 20

FRONTMATTER_DELIMITER = "---"

failures: list[str] = []


def fail(message: str) -> None:
    failures.append(message)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"{rel(path)}: missing")
    except json.JSONDecodeError as exc:
        fail(f"{rel(path)}: invalid JSON — {exc}")
    return None


def check_plain_scalars(path: Path, body: list[str]) -> None:
    """Reject unquoted scalars containing ": ".

    A plain YAML scalar may not contain a colon followed by a space. When one
    does, the frontmatter fails to parse and the skill loads with EMPTY
    metadata — every field silently dropped, no error at runtime. Writing
    `Triggers: "/swarm"` inside a description is the way this happens.
    """
    for lineno, line in enumerate(body, start=2):
        match = re.match(r"^([A-Za-z0-9_-]+):[ \t]+(\S.*)$", line)
        if not match:
            continue
        value = match.group(2).strip()
        if value.startswith(("|", ">", '"', "'", "[", "{", "#")):
            continue
        if ": " in value:
            fail(
                f"{rel(path)}:{lineno}: unquoted frontmatter value for "
                f"`{match.group(1)}` contains ': ' — YAML will fail to parse and "
                "the skill will load with empty metadata. Quote the value, use a "
                "block scalar (|), or write 'Triggers -' instead of 'Triggers:'."
            )


def parse_frontmatter(path: Path) -> dict[str, str] | None:
    """Minimal YAML frontmatter reader.

    Handles the subset skills actually use: top-level `key: value`, block
    scalars (`key: |` / `key: >`), and list values, which are returned joined
    on spaces. Avoids a PyYAML dependency so the check runs anywhere.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"{rel(path)}: unreadable — {exc}")
        return None

    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_DELIMITER:
        fail(f"{rel(path)}: no YAML frontmatter (file must start with ---)")
        return None

    try:
        end = next(
            i
            for i, line in enumerate(lines[1:], start=1)
            if line.strip() == FRONTMATTER_DELIMITER
        )
    except StopIteration:
        fail(f"{rel(path)}: frontmatter is not closed with ---")
        return None

    check_plain_scalars(path, lines[1:end])

    fields: dict[str, str] = {}
    key: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if key is not None:
            fields[key] = " ".join(part.strip() for part in buffer if part.strip())

    for line in lines[1:end]:
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match and not line.startswith((" ", "\t", "-")):
            flush()
            key = match.group(1)
            value = match.group(2).strip()
            buffer = [] if value in ("|", ">", "|-", ">-", "") else [value]
        elif key is not None:
            buffer.append(line.lstrip("- ").strip())

    flush()
    return fields


def check_skill(skill_md: Path, plugin_name: str) -> None:
    fields = parse_frontmatter(skill_md)
    if fields is None:
        return

    name = fields.get("name", "").strip()
    description = fields.get("description", "").strip()
    expected_name = skill_md.parent.name

    if not name:
        fail(f"{rel(skill_md)}: frontmatter is missing `name`")
    elif name != expected_name:
        fail(
            f"{rel(skill_md)}: frontmatter name '{name}' does not match its "
            f"directory '{expected_name}'"
        )

    if not description:
        fail(f"{rel(skill_md)}: frontmatter is missing `description`")
        return

    word_count = len(description.split())
    if word_count < MIN_DESCRIPTION_WORDS:
        fail(
            f"{rel(skill_md)}: description is {word_count} words, "
            f"minimum is {MIN_DESCRIPTION_WORDS} (it must carry trigger phrases)"
        )

    if plugin_name and name != plugin_name:
        # Not fatal — a plugin may name its skill differently — but the kit
        # convention is one skill per plugin, sharing the name.
        fail(
            f"{rel(skill_md)}: skill name '{name}' differs from plugin name "
            f"'{plugin_name}' (kit convention: one skill per plugin, same name)"
        )


def check_plugin(entry: dict) -> None:
    name = entry.get("name")
    source = entry.get("source")
    version = entry.get("version")

    if not isinstance(name, str) or not name:
        fail("marketplace.json: a plugin entry has no `name`")
        return
    if not isinstance(source, str) or not source:
        fail(f"marketplace.json: plugin '{name}' has no string `source`")
        return

    plugin_dir = (REPO_ROOT / source).resolve()
    if not plugin_dir.is_dir():
        fail(f"marketplace.json: plugin '{name}' source '{source}' does not exist")
        return

    if plugin_dir.name != name:
        fail(
            f"marketplace.json: plugin '{name}' lives in directory "
            f"'{plugin_dir.name}' — they must match"
        )

    manifest_path = plugin_dir / PLUGIN_MANIFEST_RELPATH
    manifest = load_json(manifest_path)
    if manifest is None:
        return

    if manifest.get("name") != name:
        fail(
            f"{rel(manifest_path)}: name '{manifest.get('name')}' does not match "
            f"marketplace entry '{name}'"
        )

    if manifest.get("version") != version:
        fail(
            f"{rel(manifest_path)}: version '{manifest.get('version')}' does not "
            f"match marketplace version '{version}' (versions move in lockstep)"
        )

    if not str(manifest.get("description", "")).strip():
        fail(f"{rel(manifest_path)}: missing `description`")

    skills_dir = plugin_dir / SKILLS_DIRNAME
    skill_files = sorted(skills_dir.glob(f"*/{SKILL_FILENAME}")) if skills_dir.is_dir() else []
    has_hooks = (plugin_dir / HOOKS_MANIFEST_RELPATH).is_file()

    if not skill_files and not has_hooks:
        fail(
            f"plugin '{name}': ships neither a skill "
            f"({SKILLS_DIRNAME}/<name>/{SKILL_FILENAME}) nor {HOOKS_MANIFEST_RELPATH}"
        )

    for skill_md in skill_files:
        check_skill(skill_md, name)

    if has_hooks:
        load_json(plugin_dir / HOOKS_MANIFEST_RELPATH)


def check_orphan_skills(known_dirs: set[Path]) -> None:
    """Any SKILL.md outside a plugin listed in the marketplace is a mistake."""
    for skill_md in sorted((REPO_ROOT / "plugins").glob(f"*/{SKILLS_DIRNAME}/*/{SKILL_FILENAME}")):
        plugin_dir = skill_md.parent.parent.parent.resolve()
        if plugin_dir not in known_dirs:
            fail(
                f"{rel(skill_md)}: belongs to plugin '{plugin_dir.name}', which is "
                "not listed in marketplace.json"
            )


def main() -> int:
    marketplace = load_json(MARKETPLACE_PATH)
    if marketplace is None:
        print("FAIL: marketplace.json could not be loaded")
        for message in failures:
            print(f"  - {message}")
        return 1

    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        fail("marketplace.json: `plugins` must be a non-empty list")
        plugins = []

    for entry in plugins:
        if isinstance(entry, dict):
            check_plugin(entry)
        else:
            fail("marketplace.json: plugin entries must be objects")

    known_dirs = {
        (REPO_ROOT / entry["source"]).resolve()
        for entry in plugins
        if isinstance(entry, dict) and isinstance(entry.get("source"), str)
    }
    check_orphan_skills(known_dirs)

    plugin_count = len([e for e in plugins if isinstance(e, dict)])
    if failures:
        print(f"FAIL: {len(failures)} problem(s) across {plugin_count} plugin(s)")
        for message in failures:
            print(f"  - {message}")
        return 1

    print(f"OK: {plugin_count} plugins pass Tier-0 validation")
    for entry in plugins:
        print(f"  - {entry['name']} {entry.get('version')} ({entry['source']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
