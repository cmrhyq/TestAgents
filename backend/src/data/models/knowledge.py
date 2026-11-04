from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    from src.data.models.space import Space


class KnowledgeDocument(Base):
    """领域知识库文档 - 原件存放于空间工作目录的 ``docs/``，本表存元数据与索引状态。"""

    __tablename__ = "knowledge_document"

    # 主键，由 next_id() 生成，不走数据库自增
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    # 所属空间，space.id；空间删除时级联删除
    space_id: Mapped[int] = mapped_column(Integer, ForeignKey("space.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    # 相对空间根的工作区路径
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime: Mapped[str] = mapped_column(Text, nullable=False, default="text/plain")
    # 原件大小，字节
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 已生成的切片数，与 knowledge_chunk 行数一致
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 索引状态：pending-待索引，indexed-已完成，failed-失败
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    # 索引方式：vector-向量索引，lexical-仅词法（向量库不可用时的降级）
    index_mode: Mapped[str] = mapped_column(Text, nullable=False, default="lexical")
    # 索引失败原因，成功时为空
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
    """文档切片 - 正文以本表为准，向量副本存于 Chroma。

    ``chroma_id`` 指向 Chroma 中的对应记录；为 NULL 表示仅有词法索引。
    """

    __tablename__ = "knowledge_chunk"

    # 主键，由 next_id() 生成，不走数据库自增
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    # 所属文档，knowledge_document.id；文档删除时级联删除
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("knowledge_document.id", ondelete="CASCADE"), nullable=False
    )
    # 所属空间，space.id；冗余自文档，用于按空间检索切片
    space_id: Mapped[int] = mapped_column(Integer, ForeignKey("space.id", ondelete="CASCADE"), nullable=False)
    # 文档内切片序号，从 0 开始递增
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Chroma 记录 id；NULL 表示未写入向量库
    chroma_id: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("idx_chunk_doc", "document_id", "seq"),
        Index("idx_chunk_space", "space_id"),
    )
