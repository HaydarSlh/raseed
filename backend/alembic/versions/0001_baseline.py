"""Empty baseline revision: establishes the migration chain so `migrate` applies cleanly and exits; no schema yet (no user data in Phase 0, constitution Art. II).

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-12
"""
from collections.abc import Sequence

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op baseline. Phase 1 adds users/tenancy tables and RLS policies."""
    pass


def downgrade() -> None:
    pass
