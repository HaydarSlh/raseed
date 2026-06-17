"""Knowledge domain models: shared corpus documents and passages (no RLS — shared across all users)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import UUID, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base


class KnowledgeDocument(Base):
    """A source document in the financial-literacy corpus."""

    __tablename__ = "knowledge_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    source: Mapped[str] = mapped_column(String(512), nullable=False, default="Raseed")
    license: Mapped[str] = mapped_column(String(256), nullable=False, default="CC BY 4.0")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    passages: Mapped[list[KnowledgePassage]] = relationship("KnowledgePassage", back_populates="document", cascade="all, delete-orphan")


class KnowledgePassage(Base):
    """A chunked passage from a document, with dense and sparse search vectors."""

    __tablename__ = "knowledge_passages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    heading_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    tsv: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[KnowledgeDocument] = relationship("KnowledgeDocument", back_populates="passages")
