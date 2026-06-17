"""Phase 6 security hardening: add erasure_audit table (operator-only, no RLS).

Revision ID: 0006_security_hardening
Revises: 0005_lifecycle_ops
Create Date: 2026-06-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_security_hardening"
down_revision: str | None = "0005_lifecycle_ops"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── erasure_audit (operator-only, NO RLS, NOT purged on user erasure) ────
    op.create_table(
        "erasure_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("per_store_counts", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
    )
    # Intentionally: no RLS policy created for erasure_audit
    # Intentionally: no FK to users.id (so the audit row survives user deletion)


def downgrade() -> None:
    op.drop_table("erasure_audit")
