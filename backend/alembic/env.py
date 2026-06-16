"""Alembic migration environment: resolves the DB URL from Settings and runs migrations; the `migrate` service applies these then exits (constitution Art. V)."""

from __future__ import annotations

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import get_settings

config = context.config
# Inject the async DSN as a sync URL for Alembic's migration runner.
_settings = get_settings()
config.set_main_option(
    "sqlalchemy.url",
    _settings.database_url.replace("+asyncpg", "+psycopg2"),
)

# Phase 1: domain models imported so Base.metadata is populated for autogenerate.
from app.domain import (  # noqa: E402, F401
    analytics,
    audit,
    correction,
    goal,
    memory,
    model_registry,
    transaction,
    user,
)
from app.domain.base import Base  # noqa: E402

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
