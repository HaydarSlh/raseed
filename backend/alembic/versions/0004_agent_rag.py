"""Phase 4 agent + RAG: enable pgvector, create knowledge tables, extend goals and memory.

Revision ID: 0004_agent_rag
Revises: 0003_ingestion_analytics
Create Date: 2026-06-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_agent_rag"
down_revision: str | None = "0003_ingestion_analytics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Enable pgvector extension ─────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── knowledge_documents (shared corpus, no RLS) ───────────────────────────
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(256), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("source", sa.String(512), nullable=False, server_default="Raseed"),
        sa.Column("license", sa.String(256), nullable=False, server_default="CC BY 4.0"),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_documents"),
        sa.UniqueConstraint("slug", name="uq_knowledge_documents_slug"),
    )
    op.create_index("ix_knowledge_documents_slug", "knowledge_documents", ["slug"])

    # ── knowledge_passages (dense + sparse search vectors) ────────────────────
    op.create_table(
        "knowledge_passages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("heading_path", sa.String(512), nullable=False, server_default=""),
        sa.Column("ordinal", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("tsv", postgresql.TSVECTOR(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["knowledge_documents.id"],
            ondelete="CASCADE", name="fk_knowledge_passages_document_id",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_passages"),
    )
    # Add the vector column via raw SQL (pgvector type not available as SA DDL type without extension)
    op.execute("ALTER TABLE knowledge_passages ADD COLUMN embedding vector(768)")

    op.create_index("ix_knowledge_passages_document_id", "knowledge_passages", ["document_id"])
    # ivfflat cosine index for ANN retrieval
    op.execute(
        "CREATE INDEX ix_knowledge_passages_embedding ON knowledge_passages "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10)"
    )
    # GIN index for full-text search
    op.execute("CREATE INDEX ix_knowledge_passages_tsv ON knowledge_passages USING gin(tsv)")

    # ── Grants for knowledge tables ───────────────────────────────────────────
    for table in ("knowledge_documents", "knowledge_passages"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO raseed_app")
        op.execute(f"GRANT SELECT ON {table} TO raseed_stats")

    # ── Extend goals: required fields + status + updated_at ──────────────────
    op.execute("CREATE TYPE goal_status AS ENUM ('active', 'achieved', 'abandoned')")
    op.alter_column("goals", "target_amount", nullable=False)
    op.alter_column("goals", "target_date", nullable=False)
    op.add_column(
        "goals",
        sa.Column(
            "status",
            sa.Enum("active", "achieved", "abandoned", name="goal_status"),
            nullable=False,
            server_default="active",
        ),
    )
    op.add_column(
        "goals",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── Extend memory: add embedding vector ───────────────────────────────────
    op.execute("ALTER TABLE memory ADD COLUMN embedding vector(768)")


def downgrade() -> None:
    op.execute("ALTER TABLE memory DROP COLUMN IF EXISTS embedding")
    op.drop_column("goals", "updated_at")
    op.drop_column("goals", "status")
    op.execute("ALTER TABLE goals ALTER COLUMN target_date DROP NOT NULL")
    op.execute("ALTER TABLE goals ALTER COLUMN target_amount DROP NOT NULL")
    op.execute("DROP TYPE IF EXISTS goal_status")
    op.drop_table("knowledge_passages")
    op.drop_table("knowledge_documents")
    op.execute("DROP EXTENSION IF EXISTS vector")
