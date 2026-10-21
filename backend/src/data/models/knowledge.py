from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.space import Space


class KnowledgeDocument(Base):
    """领域知识库文档 - 原件落在 workspaces/{space_id}/docs/，本表存元数据与索引状态。"""

    __tablename__ = "knowledge_document"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    space_id: Mapped[int] = mapped_column(Integer, ForeignKey("space.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    # 相对空间根的路径，如 docs/需求说明书.md
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime: Mapped[str] = mapped_column(Text, nullable=False, default="text/plain")
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # pending=待索引 indexed=已完成 failed=失败
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    # vector=向量索引 lexical=仅词法（向量库不可用时的降级）
    index_mode: Mapped[str] = mapped_column(Text, nullable=False, default="lexical")
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    space: Mapped[Space] = relationship(back_populates="documents")
    chunks: Mapped[list[KnowledgeChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="KnowledgeChunk.seq",
    )

    __table_args__ = (
        CheckConstraint("status IN ('pending','indexed','failed')", name="ck_document_status"),
        CheckConstraint("index_mode IN ('vector','lexical')", name="ck_document_index_mode"),
        Index("idx_document_space", "space_id"),
    )


class KnowledgeChunk(Base):
    """文档切片 - DB 存正文（真源），Chroma 存向量副本（``chroma_id`` 对应）。"""

    __tablename__ = "knowledge_chunk"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("knowledge_document.id", ondelete="CASCADE"), nullable=False
    )
    space_id: Mapped[int] = mapped_column(Integer, ForeignKey("space.id", ondelete="CASCADE"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    chroma_id: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("idx_chunk_doc", "document_id", "seq"),
        Index("idx_chunk_space", "space_id"),
    )
