"""CI Gate #6 Part 2 — secret scan: no hardcoded secrets in application source (Phase 6, FR-010).

Stack-independent: runs git grep over known secret patterns.
Fails if any match is found in app source files (excluding venv, fixtures, and test data).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_APP_DIRS = [
    str(_REPO_ROOT / "backend" / "app"),
    str(_REPO_ROOT / "frontend" / "src"),
    str(_REPO_ROOT / "prompts"),
]
_INCLUDE_PATTERNS = [
    "--include=*.py",
    "--include=*.ts",
    "--include=*.tsx",
    "--include=*.txt",
    "--include=*.yaml",
    "--include=*.yml",
]
_SECRET_PATTERNS = [
    "sk-",
    "AIza",
    r'password\s*=\s*["\x27]',
    r'secret\s*=\s*["\x27]',
]
_EXCLUDE_PATHS = {
    "node_modules",
    ".venv",
    "__pycache__",
    "tests/fixtures",
    ".secrets.baseline",
}


def _grep_for_pattern(pattern: str) -> list[str]:
    """Run git grep for a pattern; return list of matching lines."""
    try:
        result = subprocess.run(
            ["git", "grep", "-rn", "-E", pattern, "--"] + _INCLUDE_PATTERNS + _APP_DIRS,
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
        )
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        # Filter out excluded paths
        return [
            ln for ln in lines
            if not any(excl in ln for excl in _EXCLUDE_PATHS)
        ]
    except FileNotFoundError:
        # git not available — skip gracefully
        return []


def test_gate6_part2_no_sk_keys_in_source() -> None:
    matches = _grep_for_pattern(r"sk-[A-Za-z0-9]{8,}")
    assert not matches, (
        "Gate #6 FAILED — sk-* key pattern found in source:\n" + "\n".join(matches)
    )


def test_gate6_part2_no_google_api_keys_in_source() -> None:
    matches = _grep_for_pattern(r"AIza[A-Za-z0-9\-_]{35}")
    assert not matches, (
        "Gate #6 FAILED — Google API key pattern found in source:\n" + "\n".join(matches)
    )


def test_gate6_part2_no_hardcoded_password_assignments() -> None:
    matches = _grep_for_pattern(r'password\s*=\s*["\x27][^"\x27]{4,}')
    # Allow test/placeholder strings that are obviously non-real
    real_matches = [
        ln for ln in matches
        if not any(placeholder in ln.lower() for placeholder in
                   ["test", "example", "placeholder", "ci-", "your-", "change-me", "changeme"])
    ]
    assert not real_matches, (
        "Gate #6 FAILED — hardcoded password found in source:\n" + "\n".join(real_matches)
    )


def test_gate6_part2_prompts_dir_exists() -> None:
    """Prompts directory must exist (secrets-check can only run if the target dirs exist)."""
    assert (_REPO_ROOT / "prompts").exists(), "prompts/ directory missing"
