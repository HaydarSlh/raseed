"""T013 — Lean image guard (US1).

Asserts that torch, transformers, and scikit-learn are NOT importable in the
serving environment. This test deliberately runs without any fixture server — it
only inspects the Python environment. Refs: SC-007, Art. III.
"""

from __future__ import annotations

import importlib.util

import pytest


def _is_importable(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


@pytest.mark.parametrize(
    "module",
    ["torch", "transformers", "sklearn"],
    ids=["torch", "transformers", "scikit-learn"],
)
def test_forbidden_dep_not_importable(module: str) -> None:
    """Constitution Art. III: no torch/transformers/sklearn in the serving image."""
    assert not _is_importable(module), (
        f"'{module}' is importable in the serving environment — "
        "remove it from modelserver/pyproject.toml (Art. III violation)."
    )
