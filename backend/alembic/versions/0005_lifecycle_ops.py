"""Phase 5 lifecycle & ops: extend corrections/model_registry; add retrain_runs, drift_signals, user_settings.

Revision ID: 0005_lifecycle_ops
Revises: 0004_agent_rag
Create Date: 2026-06-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_lifecycle_ops"
down_revision: str | None = "0004_agent_rag"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── New enums ─────────────────────────────────────────────────────────────
    op.execute("CREATE TYPE correction_provenance_type AS ENUM ('llm', 'human')")
    op.execute("CREATE TYPE trigger_reason_type AS ENUM ('correction_count', 'time_cooldown', 'manual', 'drift')")
    op.execute("CREATE TYPE run_status_type AS ENUM ('enqueued', 'running', 'completed', 'failed', 'skipped')")
    op.execute("CREATE TYPE drift_source_type AS ENUM ('scheduled', 'on_demand', 'simulation')")
    op.execute("CREATE TYPE review_mode_type AS ENUM ('manual', 'auto_relabel')")

    # ── retrain_runs (global ops table — no user_id, no RLS) ─────────────────
    # Created BEFORE model_registry extension because model_registry.retrain_run_id FKs here.
    op.create_table(
        "retrain_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("trigger_reason", sa.Enum("correction_count", "time_cooldown", "manual", "drift", name="trigger_reason_type", create_type=False), nullable=False),
        sa.Column("idempotency_key", sa.String(256), nullable=False),
        sa.Column("status", sa.Enum("enqueued", "running", "completed", "failed", "skipped", name="run_status_type", create_type=False), nullable=False, server_default="enqueued"),
        sa.Column("skipped_reason", sa.Text(), nullable=True),
        sa.Column("challenger_id", sa.UUID(), nullable=True),
        sa.Column("champion_macro_f1", sa.Float(), nullable=True),
        sa.Column("challenger_macro_f1", sa.Float(), nullable=True),
        sa.Column("gate_verdict", sa.String(32), nullable=True),
        sa.Column("labels_used", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_retrain_runs"),
        sa.UniqueConstraint("idempotency_key", name="uq_retrain_runs_idempotency_key"),
    )
    op.create_index("ix_retrain_runs_created_at", "retrain_runs", ["created_at"])

    # ── Extend corrections: provenance + quarantine ────────────────────────────
    op.add_column(
        "corrections",
        sa.Column(
            "provenance",
            sa.Enum("llm", "human", name="correction_provenance_type", create_type=False),
            nullable=False,
            server_default="human",
        ),
    )
    op.add_column("corrections", sa.Column("quarantined", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("corrections", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))

    # ── Extend model_registry: artifact fields ─────────────────────────────────
    op.add_column("model_registry", sa.Column("artifact_uri", sa.Text(), nullable=True))
    op.add_column("model_registry", sa.Column("metrics", postgresql.JSONB(), nullable=True))
    op.add_column(
        "model_registry",
        sa.Column(
            "retrain_run_id",
            sa.UUID(),
            sa.ForeignKey("retrain_runs.id", ondelete="SET NULL", name="fk_model_registry_retrain_run_id_retrain_runs"),
            nullable=True,
        ),
    )
    op.add_column(
        "model_registry",
        sa.Column(
            "promoted_by",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_model_registry_promoted_by_users"),
            nullable=True,
        ),
    )
    op.add_column("model_registry", sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True))

    # At-most-one-champion partial unique index (Art. III invariant)
    op.execute(
        "CREATE UNIQUE INDEX uq_model_registry_single_champion "
        "ON model_registry (status) WHERE status = 'champion'"
    )

    # ── drift_signals (global ops table) ─────────────────────────────────────
    op.create_table(
        "drift_signals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("mean_confidence", sa.Float(), nullable=False),
        sa.Column("correction_rate", sa.Float(), nullable=False),
        sa.Column("psi", sa.Float(), nullable=False, server_default="0"),
        sa.Column("new_merchant_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("thresholds", postgresql.JSONB(), nullable=True),
        sa.Column("fired", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("fired_signals", postgresql.JSONB(), nullable=True),
        sa.Column("triggered_retrain", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("source", sa.Enum("scheduled", "on_demand", "simulation", name="drift_source_type", create_type=False), nullable=False, server_default="scheduled"),
        sa.PrimaryKeyConstraint("id", name="pk_drift_signals"),
    )
    op.create_index("ix_drift_signals_evaluated_at", "drift_signals", ["evaluated_at"])

    # ── user_settings (per-user, RLS-scoped) ─────────────────────────────────
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_user_settings_user_id_users"), nullable=False),
        sa.Column("review_mode", sa.Enum("manual", "auto_relabel", name="review_mode_type", create_type=False), nullable=False, server_default="manual"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", name="pk_user_settings"),
    )

    # ── Grants ────────────────────────────────────────────────────────────────
    # Global ops tables readable by stats role (privileged aggregates)
    for table in ("retrain_runs", "drift_signals"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON {table} TO raseed_app")
        op.execute(f"GRANT SELECT ON {table} TO raseed_stats")

    # User-settings: app role full access; stats role no access (user-scoped)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON user_settings TO raseed_app")

    # Enable RLS on user_settings (same pattern as other per-user tables)
    op.execute("ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY user_settings_isolation ON user_settings "
        "USING (user_id = (current_setting('app.user_id', true))::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS user_settings_isolation ON user_settings")
    op.execute("ALTER TABLE user_settings DISABLE ROW LEVEL SECURITY")
    op.drop_table("user_settings")
    op.drop_table("drift_signals")
    op.execute("DROP INDEX IF EXISTS uq_model_registry_single_champion")
    op.drop_column("model_registry", "promoted_at")
    op.drop_column("model_registry", "promoted_by")
    op.drop_column("model_registry", "retrain_run_id")
    op.drop_column("model_registry", "metrics")
    op.drop_column("model_registry", "artifact_uri")
    op.drop_column("corrections", "confirmed_at")
    op.drop_column("corrections", "quarantined")
    op.drop_column("corrections", "provenance")
    op.drop_table("retrain_runs")
    op.execute("DROP TYPE IF EXISTS review_mode_type")
    op.execute("DROP TYPE IF EXISTS drift_source_type")
    op.execute("DROP TYPE IF EXISTS run_status_type")
    op.execute("DROP TYPE IF EXISTS trigger_reason_type")
    op.execute("DROP TYPE IF EXISTS correction_provenance_type")
