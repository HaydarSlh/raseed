"""Add user profile fields collected at registration.

Adds username, phone_number, country, city, bank_name to the users table. All
nullable so existing rows (demo seed) remain valid; `username` is required only at
the registration API layer (UserCreate), not the DB.

Revision ID: 0007_user_profile_fields
Revises: 0006_security_hardening
Create Date: 2026-06-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_user_profile_fields"
down_revision: str | None = "0006_security_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("phone_number", sa.String(32), nullable=True))
    op.add_column("users", sa.Column("country", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("city", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("bank_name", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "bank_name")
    op.drop_column("users", "city")
    op.drop_column("users", "country")
    op.drop_column("users", "phone_number")
    op.drop_column("users", "username")
