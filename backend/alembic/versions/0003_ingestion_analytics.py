"""Phase 3 ingestion & analytics: extend transactions (description/normalized/is_anomaly +
dedup unique index), add derived per-user tables (forecasts, anomalies, subscriptions) with
RLS, and the GLOBAL anonymized population_stats (no RLS; written only by raseed_stats).

Revision ID: 0003_ingestion_analytics
Revises: 0002_auth_tenancy
Create Date: 2026-06-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_ingestion_analytics"
down_revision: str | None = "0002_auth_tenancy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# New per-user derived tables that get RLS policies (same pattern as 0002).
_DERIVED_USER_TABLES = ["forecasts", "anomalies", "subscriptions"]


def upgrade() -> None:
    # ── Extend transactions for ingestion ────────────────────────────────────────
    op.add_column("transactions", sa.Column("description", sa.String(1024), nullable=True))
    op.add_column("transactions", sa.Column("normalized_description", sa.String(1024), nullable=True))
    op.add_column(
        "transactions",
        sa.Column("is_anomaly", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Dedup natural key (R8): a row matching an existing key is skipped on insert.
    op.create_index(
        "uq_transactions_dedup",
        "transactions",
        ["user_id", "occurred_at", "amount", "normalized_description"],
        unique=True,
    )

    # ── forecasts (per-user, derived) ────────────────────────────────────────────
    op.create_table(
        "forecasts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("horizon_date", sa.Date(), nullable=False),
        sa.Column("projected_balance", sa.Numeric(18, 4), nullable=False),
        sa.Column("lower_bound", sa.Numeric(18, 4), nullable=False),
        sa.Column("upper_bound", sa.Numeric(18, 4), nullable=False),
        sa.Column("is_cold_start", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_forecasts_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_forecasts"),
    )
    op.create_index("ix_forecasts_user_id", "forecasts", ["user_id"])

    # ── anomalies (per-user, derived) ────────────────────────────────────────────
    op.create_table(
        "anomalies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("transaction_id", sa.UUID(), nullable=False),
        sa.Column("anomaly_type", sa.Enum("statistical_outlier", "duplicate_charge", name="anomaly_type"), nullable=False),
        sa.Column("score", sa.Numeric(18, 4), nullable=True),
        sa.Column("reason", sa.String(512), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_anomalies_user_id_users"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE", name="fk_anomalies_transaction_id_transactions"),
        sa.PrimaryKeyConstraint("id", name="pk_anomalies"),
    )
    op.create_index("ix_anomalies_user_id", "anomalies", ["user_id"])

    # ── subscriptions (per-user, derived) ────────────────────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("merchant", sa.String(512), nullable=False),
        sa.Column("cadence", sa.Enum("weekly", "biweekly", "monthly", "quarterly", "annual", "irregular", name="cadence_type"), nullable=False),
        sa.Column("typical_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("last_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("next_charge_date", sa.Date(), nullable=True),
        sa.Column("price_increase", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_subscriptions_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_subscriptions"),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])

    # ── population_stats (GLOBAL, anonymized, NO user_id, NO RLS) ─────────────────
    op.create_table(
        "population_stats",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("category", sa.String(128), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=False),
        sa.Column("mean_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("stddev_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("user_count", sa.SmallInteger(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_population_stats"),
    )

    # ── RLS on the derived per-user tables (same fail-closed pattern as 0002) ─────
    for table in _DERIVED_USER_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_isolation ON {table}
            USING      (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)
        """)

    # ── Grants ───────────────────────────────────────────────────────────────────
    for table in _DERIVED_USER_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO raseed_app")
        op.execute(f"GRANT SELECT ON {table} TO raseed_stats")
    # population_stats: the privileged stats job (raseed_stats) writes it; user sessions
    # (raseed_app) may only read the anonymized prior.
    op.execute("GRANT SELECT ON population_stats TO raseed_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON population_stats TO raseed_stats")


def downgrade() -> None:
    for table in _DERIVED_USER_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_isolation ON {table}")
    op.drop_table("population_stats")
    op.drop_table("subscriptions")
    op.drop_table("anomalies")
    op.drop_table("forecasts")
    op.execute("DROP TYPE IF EXISTS cadence_type")
    op.execute("DROP TYPE IF EXISTS anomaly_type")
    op.drop_index("uq_transactions_dedup", table_name="transactions")
    op.drop_column("transactions", "is_anomaly")
    op.drop_column("transactions", "normalized_description")
    op.drop_column("transactions", "description")
