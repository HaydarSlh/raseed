"""Promote (or demote) a user to operator by email.

Operators can access the /ops dashboard (retrain, promote, drift, history).
Registration cannot set is_operator, so this flag is only changed by the demo
seed or this helper — never by self-service.

Usage:
    DATABASE_URL=postgresql+asyncpg://... python scripts/make_operator.py admin@example.com

    # revoke instead of grant
    python scripts/make_operator.py admin@example.com --revoke

With the compose stack running:
    docker compose exec backend python /app/scripts/make_operator.py admin@example.com

Note: constructs its own AsyncEngine from DATABASE_URL — does NOT import from the
backend package, so it runs standalone (mirrors scripts/seed_demo.py).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://raseed:raseed_local_dev@localhost:5432/raseed",
)


async def _set_operator(email: str, *, value: bool) -> int:
    """Set is_operator on the user with this email. Returns rows affected (0 or 1)."""
    engine = create_async_engine(_DATABASE_URL)
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    "UPDATE users SET is_operator = :value "
                    "WHERE email = :email RETURNING id"
                ),
                {"value": value, "email": email},
            )
            return len(result.fetchall())
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Grant or revoke operator access by email.")
    parser.add_argument("email", help="The user's login email.")
    parser.add_argument(
        "--revoke",
        action="store_true",
        help="Revoke operator access instead of granting it.",
    )
    args = parser.parse_args()

    grant = not args.revoke
    affected = asyncio.run(_set_operator(args.email, value=grant))

    verb = "granted" if grant else "revoked"
    if affected == 0:
        print(f"No user found with email {args.email!r}. Nothing changed.", file=sys.stderr)
        return 1
    print(f"Operator access {verb} for {args.email}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
