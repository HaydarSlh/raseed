"""CI Gate #8 — compose smoke test (Phase 7, FR-010).

Brings up the default docker compose profile and asserts all default services
become healthy. Requires Docker — marked @pytest.mark.integration so it is
skipped when Docker is unavailable (constitution Art. V: stack-independent CI;
Gate 8 is the documented exception, see docs/EVALS.md and DECISIONS.md D17).

Run manually:
    pytest tests/test_compose_smoke.py -m integration -v
"""

from __future__ import annotations

import subprocess
import urllib.request
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parent.parent.parent
_SMOKE_SCRIPT = _REPO_ROOT / "scripts" / "smoke_compose.sh"


def _docker_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.mark.integration
def test_gate8_compose_smoke() -> None:
    """Gate #8: all default services healthy; trainer not running on default up."""
    if not _docker_available():
        pytest.skip("Docker not available — Gate 8 skipped (see docs/EVALS.md)")

    result = subprocess.run(
        ["bash", str(_SMOKE_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=_REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"Gate #8 FAILED — compose smoke script exited {result.returncode}:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    # Verify key service HTTP endpoints respond after the stack is up.
    for url, label in [
        ("http://localhost:8000/health", "backend /health"),
        ("http://localhost:5173", "frontend"),
    ]:
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                assert resp.status == 200, (
                    f"Gate #8 FAILED — {label} returned HTTP {resp.status}"
                )
        except Exception as exc:
            pytest.fail(f"Gate #8 FAILED — {label} unreachable: {exc}")
