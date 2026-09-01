"""Guard test: decision records are append-only.

Copy this file into the host repository's test directory (for example
``tests/test_decisions_append_only.py``). It fails CI when any file that
already existed under ``decisions/`` was modified, deleted, or renamed on this
branch relative to the merge base with the base branch. Only additions pass.

The record itself is not the enforcement — this test is. See the ``decision-log``
skill: every decision that must hold needs a record, a one-line positive rule,
and a mechanical guard. For the append-only rule, this is that guard.

Requirements
------------
CI must check out enough history to resolve the merge base. With GitHub
Actions that means ``fetch-depth: 0`` on ``actions/checkout``, or an explicit
``git fetch origin <base-branch>`` before the test run.

Configuration
-------------
Base branch resolution order:
1. ``DECISIONS_BASE_REF`` environment variable (explicit override)
2. ``GITHUB_BASE_REF`` (set by GitHub Actions on pull requests)
3. ``DECISIONS_DEFAULT_BASE`` environment variable
4. ``origin/main``
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

# Directory holding the decision records, relative to the repository root.
DECISIONS_DIR = os.environ.get("DECISIONS_DIR", "decisions")

# Fallback base branch when neither an explicit override nor a CI-provided
# base ref is available.
DEFAULT_BASE_REF = os.environ.get("DECISIONS_DEFAULT_BASE", "origin/main")

# git diff --name-status letters that are allowed under the decisions directory.
# "A" is an addition. Everything else (M, D, R, C, T) mutates history.
ALLOWED_STATUSES = frozenset({"A"})

# Human-readable names for the statuses this test rejects.
STATUS_NAMES = {
    "M": "modified",
    "D": "deleted",
    "R": "renamed",
    "C": "copied",
    "T": "type-changed",
}


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _repo_root() -> Path:
    result = _run(["git", "rev-parse", "--show-toplevel"], cwd=Path(__file__).parent)
    if result.returncode != 0:
        pytest.skip("not inside a git working tree")
    return Path(result.stdout.strip())


def _resolve_base_ref(repo: Path) -> str:
    explicit = os.environ.get("DECISIONS_BASE_REF")
    if explicit:
        return explicit

    github_base = os.environ.get("GITHUB_BASE_REF")
    if github_base:
        candidates = [f"origin/{github_base}", github_base]
    else:
        candidates = [DEFAULT_BASE_REF]

    for candidate in candidates:
        if _run(["git", "rev-parse", "--verify", "--quiet", candidate], cwd=repo).returncode == 0:
            return candidate

    message = (
        "cannot resolve the base ref for the append-only check "
        f"(tried: {', '.join(candidates)}). "
        "CI needs full history — use fetch-depth: 0 or fetch the base branch."
    )
    # In CI a missing base ref must fail: skipping would silently disable the
    # guard exactly where it matters. Locally it is only a missing remote.
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        pytest.fail(message)
    pytest.skip(message)


def _merge_base(repo: Path, base_ref: str) -> str:
    result = _run(["git", "merge-base", base_ref, "HEAD"], cwd=repo)
    if result.returncode != 0:
        pytest.fail(
            f"git merge-base {base_ref} HEAD failed: {result.stderr.strip()}. "
            "CI needs full history to compute the merge base."
        )
    return result.stdout.strip()


def _changed_decision_paths(repo: Path, merge_base: str) -> list[tuple[str, str]]:
    result = _run(
        ["git", "diff", "--name-status", "--find-renames", merge_base, "HEAD"],
        cwd=repo,
    )
    if result.returncode != 0:
        pytest.fail(f"git diff failed: {result.stderr.strip()}")

    prefix = f"{DECISIONS_DIR.rstrip('/')}/"
    changes: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        status = fields[0][0]
        # Renames and copies report both the old and the new path; the old
        # path is the one that must not disappear.
        for path in fields[1:]:
            if path.startswith(prefix):
                changes.append((status, path))
    return changes


def test_decision_records_are_append_only() -> None:
    repo = _repo_root()

    if not (repo / DECISIONS_DIR).is_dir():
        pytest.skip(f"repository has no {DECISIONS_DIR}/ directory")

    base_ref = _resolve_base_ref(repo)
    merge_base = _merge_base(repo, base_ref)
    changes = _changed_decision_paths(repo, merge_base)

    violations = [
        (status, path) for status, path in changes if status not in ALLOWED_STATUSES
    ]

    if violations:
        lines = [
            f"  {STATUS_NAMES.get(status, status)}: {path}"
            for status, path in sorted(violations, key=lambda item: item[1])
        ]
        pytest.fail(
            f"{DECISIONS_DIR}/ is append-only — existing records may not be "
            "modified, deleted, or renamed.\n"
            + "\n".join(lines)
            + "\n\nTo reverse or amend a decision, add a NEW record that cites "
            "the old one with a 'Supersedes:' line."
        )
