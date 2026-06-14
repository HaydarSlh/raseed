"""Auth + tenancy foundation: all user-owned tables, RLS policies, and roles. No pgvector extension — memory embedding deferred to Phase 4 (M1, DECISIONS.md).

Revision ID: 0002_auth_tenancy
Revises: 0001_baseline
Create Date: 2026-06-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0002_auth_tenancy"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables that are user-owned and get RLS policies
_USER_TABLES = ["transactions", "goals", "corrections", "memory", "audit_log"]


def upgrade() -> None:
    # ── Roles ────────────────────────────────────────────────────────────────────
    # raseed_app: normal app role, NOT BYPASSRLS — RLS policies bind (R2)
    # raseed_stats: BYPASSRLS, reserved for Phase 3 cross-user stats job only
    op.execute("""
        DO $$ BEGIN
            CREATE ROLE raseed_app WITH LOGIN PASSWORD 'raseed_local_dev' NOINHERIT;
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE ROLE raseed_stats WITH LOGIN PASSWORD 'raseed_local_dev_stats' NOINHERIT BYPASSRLS;
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)


    # ── users ────────────────────────────────────────────────────────────────────
    # fastapi-users schema + is_operator; NO RLS (auth layer manages access — data-model.md)
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=1024), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_operator", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── transactions ─────────────────────────────────────────────────────────────
    op.create_table(
        "transactions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("provenance", sa.Enum("rule", "model", "llm", "human", name="provenance_type"), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("merchant", sa.String(512), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("category", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_transactions_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_transactions"),
    )
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])

    # ── goals ────────────────────────────────────────────────────────────────────
    op.create_table(
        "goals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("target_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_goals_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_goals"),
    )
    op.create_index("ix_goals_user_id", "goals", ["user_id"])

    # ── corrections ───────────────────────────────────────────────────────────────
    op.create_table(
        "corrections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("transaction_id", sa.UUID(), nullable=True),
        sa.Column("old_category", sa.String(128), nullable=True),
        sa.Column("new_category", sa.String(128), nullable=False),
        sa.Column("confirmed_by_human", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_corrections_user_id_users"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="SET NULL", name="fk_corrections_transaction_id_transactions"),
        sa.PrimaryKeyConstraint("id", name="pk_corrections"),
    )
    op.create_index("ix_corrections_user_id", "corrections", ["user_id"])

    # ── model_registry ───────────────────────────────────────────────────────────
    # Global — no user_id, no RLS (FR-008)
    op.create_table(
        "model_registry",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("status", sa.Enum("challenger", "champion", "archived", name="model_status_type"), nullable=False, server_default="challenger"),
        sa.Column("model_card", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_model_registry"),
    )

    # ── memory ───────────────────────────────────────────────────────────────────
    # No embedding column — deferred to Phase 4 with the embedder decision (M1)
    # No pgvector extension enabled this phase (data-model.md, DECISIONS.md)
    op.create_table(
        "memory",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_memory_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_memory"),
    )
    op.create_index("ix_memory_user_id", "memory", ["user_id"])

    # ── audit_log ────────────────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(256), nullable=False),
        sa.Column("detail", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_audit_log_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
    )
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])

    # ── Row Level Security (RLS) ─────────────────────────────────────────────────
    # Every user-owned table: ENABLE + FORCE + USING + WITH CHECK on app.user_id
    # model_registry and users tables are excluded (global / auth-managed)
    for table in _USER_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        # NULLIF converts '' to NULL so an unset context matches no rows (fail-closed,
        # no uuid-cast error when app.user_id is the empty reset value).
        op.execute(f"""
            CREATE POLICY {table}_isolation ON {table}
            USING      (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)
        """)

    # ── Grants ───────────────────────────────────────────────────────────────────
    for table in [*_USER_TABLES, "users", "model_registry"]:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO raseed_app")
        op.execute(f"GRANT SELECT ON {table} TO raseed_stats")


def downgrade() -> None:
    for table in _USER_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_isolation ON {table}")

    op.drop_table("audit_log")
    op.drop_table("memory")
    op.drop_table("model_registry")
    op.drop_table("corrections")
    op.drop_table("goals")
    op.drop_table("transactions")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS model_status_type")
    op.execute("DROP TYPE IF EXISTS provenance_type")

    op.execute("DROP ROLE IF EXISTS raseed_stats")
    op.execute("DROP ROLE IF EXISTS raseed_app")
