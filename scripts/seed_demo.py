"""Seed demo users with 6 months of realistic UK transaction history.

Creates two demo users (demo@raseed.app, demo2@raseed.app) and ~180 transactions
each. Idempotent — re-running does not create duplicates.

Usage:
    DATABASE_URL=postgresql+asyncpg://... python scripts/seed_demo.py

Or with the compose stack running (uses default from .env):
    docker compose exec backend python /app/scripts/seed_demo.py

Note: constructs its own AsyncEngine from DATABASE_URL env var — does NOT import
from the backend package so the script can run standalone.
"""

from __future__ import annotations

import asyncio
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

from passlib.hash import argon2
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://raseed:raseed_local_dev@localhost:5432/raseed",
)

_DEMO_USERS = [
    {
        "email": "demo@raseed.app",
        "password": "Demo1234!",
        "is_operator": False,
    },
    {
        "email": "demo2@raseed.app",
        "password": "Demo5678!",
        "is_operator": False,
    },
]

# UK-realistic merchants mapped to Phase-2 taxonomy categories
_MERCHANTS: list[tuple[str, str, str, tuple[float, float]]] = [
    # (merchant_name, type_code, category, (min_amount, max_amount))
    ("TESCO STORES", "DEB", "groceries", (5.0, 120.0)),
    ("SAINSBURY'S", "DEB", "groceries", (8.0, 100.0)),
    ("LIDL GB", "DEB", "groceries", (4.0, 60.0)),
    ("AMAZON", "DEB", "amazon", (6.0, 250.0)),
    ("TFL TRAVEL", "DEB", "travel", (2.5, 15.0)),
    ("DELIVEROO", "DEB", "dine_out", (10.0, 45.0)),
    ("NANDOS", "DEB", "dine_out", (12.0, 40.0)),
    ("NETFLIX", "DD", "entertainment", (10.99, 10.99)),
    ("SPOTIFY", "DD", "entertainment", (9.99, 9.99)),
    ("BRITISH GAS", "DD", "bills", (45.0, 120.0)),
    ("BT GROUP", "DD", "bills", (35.0, 70.0)),
    ("VODAFONE", "DD", "bills", (20.0, 50.0)),
    ("EMPLOYER SALARY", "FPI", "income", (1800.0, 3500.0)),
    ("HMRC REFUND", "BGC", "income", (50.0, 800.0)),
    ("NATIONWIDE BS", "DD", "mortgage", (600.0, 1400.0)),
    ("PURE GYM", "DD", "fitness", (19.99, 25.99)),
    ("PRIMARK", "DEB", "clothes", (15.0, 80.0)),
    ("WATERSTONES", "DEB", "other_shopping", (8.0, 35.0)),
    ("PREMIER INN", "DEB", "hotels", (55.0, 180.0)),
    ("CASH WITHDRAWAL", "CPT", "cash", (20.0, 200.0)),
    ("AVIVA INSURANCE", "DD", "insurance", (30.0, 90.0)),
    ("ISLINGTON COUNCIL", "BP", "bills", (80.0, 200.0)),
]

_CATEGORIES = list({m[2] for m in _MERCHANTS})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash_password(plain: str) -> str:
    return argon2.hash(plain)


def _random_transactions(
    user_id: uuid.UUID,
    months: int = 6,
    target_count: int = 180,
) -> list[dict]:
    now = datetime.now(tz=timezone.utc)
    rows: list[dict] = []
    for _ in range(target_count):
        merchant, type_code, category, (lo, hi) = random.choice(_MERCHANTS)
        days_back = random.randint(0, months * 30)
        occurred_at = now - timedelta(days=days_back, hours=random.randint(0, 23))
        amount = round(random.uniform(lo, hi), 2)
        description = f"{merchant} {''.join(random.choices('0123456789', k=4))}"
        rows.append({
            "id": str(uuid.uuid4()),
            "user_id": str(user_id),
            "provenance": "human",
            "confidence": 1.0,
            "needs_review": False,
            "amount": amount,
            "currency": "GBP",
            "merchant": merchant,
            "occurred_at": occurred_at.isoformat(),
            "category": category,
            "description": description,
            "normalized_description": description.lower().strip(),
            "is_anomaly": False,
        })
    return rows


# ---------------------------------------------------------------------------
# Seed logic
# ---------------------------------------------------------------------------


async def seed(engine_url: str) -> None:
    engine = create_async_engine(engine_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore[call-overload]

    async with async_session() as session:
        for demo in _DEMO_USERS:
            user_id = uuid.uuid4()
            hashed = _hash_password(demo["password"])

            # Upsert user — ON CONFLICT DO NOTHING keeps idempotency
            result = await session.execute(
                text(
                    "INSERT INTO users (id, email, hashed_password, is_active, "
                    "is_superuser, is_verified, is_operator) "
                    "VALUES (:id, :email, :hashed_password, true, false, true, :is_operator) "
                    "ON CONFLICT (email) DO NOTHING "
                    "RETURNING id"
                ),
                {
                    "id": str(user_id),
                    "email": demo["email"],
                    "hashed_password": hashed,
                    "is_operator": demo["is_operator"],
                },
            )
            row = result.fetchone()
            if row is None:
                # User already exists — fetch the existing id
                existing = await session.execute(
                    text("SELECT id FROM users WHERE email = :email"),
                    {"email": demo["email"]},
                )
                user_id = uuid.UUID(str(existing.scalar_one()))
                print(f"  {demo['email']}: already exists (id={user_id}), skipping inserts")
            else:
                user_id = uuid.UUID(str(row[0]))
                transactions = _random_transactions(user_id)
                for tx in transactions:
                    await session.execute(
                        text(
                            "INSERT INTO transactions "
                            "(id, user_id, provenance, confidence, needs_review, amount, "
                            "currency, merchant, occurred_at, category, description, "
                            "normalized_description, is_anomaly) "
                            "VALUES (:id, :user_id, :provenance, :confidence, :needs_review, "
                            ":amount, :currency, :merchant, :occurred_at, :category, "
                            ":description, :normalized_description, :is_anomaly) "
                            "ON CONFLICT ON CONSTRAINT uq_transactions_dedup DO NOTHING"
                        ),
                        tx,
                    )
                print(f"  {demo['email']}: seeded id={user_id} with {len(transactions)} transactions")

        await session.commit()

    await engine.dispose()


async def main() -> None:
    print("Seeding demo users...")
    await seed(_DATABASE_URL)
    print("Seeded 2 demo users with 6 months of transactions.")


if __name__ == "__main__":
    asyncio.run(main())
