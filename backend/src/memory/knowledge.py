"""按空间隔离的领域知识库：文档摄取、切片、检索与管理。

检索能力必须可降级：向量库与 embedding 均可用时走向量检索，否则回退到切片表
``LIKE`` 词法检索；实际方式记录在文档行的 ``index_mode`` 上。
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from data.constant.memory import TEXT_SUFFIXES, MAX_DOCUMENT_BYTES, CHUNK_SIZE, CHUNK_OVERLAP
from src.core.logging import get_logger
from src.data.models.base import local_now
from src.data.models.knowledge import KnowledgeChunk, KnowledgeDocument
from src.utils.id import next_id
from src.workspace.manager import WorkspaceManager

logger = get_logger(__name__)

SessionScope = Callable[[], AbstractContextManager[Session]]


class VectorStore(Protocol):
    """向量库抽象：仅依赖 add / query / delete 三个动作，便于替换与 mock。"""

    def add(self, ids: list[str], documents: list[str], metadatas: list[dict[str, Any]]) -> None: ...

    def query(self, query_text: str, top_k: int) -> list[dict[str, Any]]: ...

    def delete(self, ids: list[str]) -> None: ...


Embedder = Callable[[list[str]], list[list[float]]]


@dataclass(slots=True)
class SearchHit:
    """一条检索结果。"""

    content: str
    document_name: str
    chunk_id: int
    seq: int
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """转换为工具与接口返回用的字典，``score`` 保留 4 位小数。"""
        return {
            "document": self.document_name,
            "seq": self.seq,
            "content": self.content,
            "score": round(self.score, 4),
        }


class KnowledgeBase:
    """按空间隔离的领域知识库。

    ``vector_store`` 与 ``embedder`` 任一为 None 即视为词法模式，
    此时上传与检索只写读切片表。

    Args:
        workspace: 工作目录管理器；None 时取全局单例
        session_scope: Session 上下文工厂；None 时用全局数据库单例
        vector_store: 向量库实现；None 表示走词法降级
        embedder: 文本向量化函数；None 表示走词法降级
    """

    def __init__(
        self,
        workspace: WorkspaceManager | None = None,
        session_scope: SessionScope | None = None,
        vector_store: VectorStore | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        if workspace is None:
            from src.workspace.manager import get_workspace_manager

            workspace = get_workspace_manager()
        self._workspace = workspace
        self._session_scope = session_scope or _default_session_scope()
        self._vector_store = vector_store
        self._embedder = embedder

    @property
    def vector_enabled(self) -> bool:
        """是否同时具备向量库与 embedder。"""
        return self._vector_store is not None and self._embedder is not None

    @property
    def vector_store(self) -> VectorStore | None:
        """当前向量库实现（None 表示词法降级）。"""
        return self._vector_store

    # ─── 摄取 ────────────────────────────────────────────────────────────

    def ingest(self, space_id: int | str, filename: str, data: bytes, mime: str = "") -> KnowledgeDocument:
        """上传并索引一份文档。

        副作用：文件写入空间 ``docs/`` 目录，文档行与切片落库；
        启用向量能力时会调用 embedder 并写入向量库。

        Args:
            space_id: 空间 ID
            filename: 原始文件名，仅保留文件名部分，路径会被丢弃以防目录穿越
            data: 文件字节
            mime: MIME 类型，缺省按扩展名推断

        Returns:
            已入库的文档行（``status='indexed'``）

        Raises:
            ValueError: 后缀不支持、内容为空、解码后为空或文件超过 20MB
        """
        safe_name = Path(filename).name
        suffix = Path(safe_name).suffix.lower()
        if suffix not in TEXT_SUFFIXES:
            raise ValueError(f"不支持的文档格式: {suffix or '(无扩展名)'}，支持 {', '.join(sorted(TEXT_SUFFIXES))}")
        if not data or not data.strip():
            raise ValueError("文档内容为空")
        if len(data) > MAX_DOCUMENT_BYTES:
            raise ValueError(f"文档过大，上限 {MAX_DOCUMENT_BYTES // 1024 // 1024}MB")

        text = _decode(data)
        if not text.strip():
            raise ValueError("文档解码后为空（可能是二进制文件或被错误编码）")

        target = self._workspace.resolve(space_id, f"docs/{safe_name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

        doc_id = next_id()
        relative = self._workspace.relative(space_id, target)
        with self._session_scope() as session:
            document = KnowledgeDocument(
                id=doc_id,
                space_id=int(space_id),
                filename=safe_name,
                file_path=relative,
                mime=mime or _guess_mime(suffix),
                size=len(data),
                status="pending",
                index_mode="vector" if self.vector_enabled else "lexical",
            )
            session.add(document)
            session.flush()

        self._index(space_id, doc_id, text)
        logger.info(
            "知识库文档已索引",
            space_id=str(space_id),
            document_id=str(doc_id),
            filename=safe_name,
            vector=self.vector_enabled,
        )
        return self.get_document(doc_id)  # type: ignore[return-value]

    def reindex(self, document_id: int) -> KnowledgeDocument | None:
        """以磁盘源文件为准重建切片索引，覆盖原有切片与向量。

        Args:
            document_id: 文档 ID

        Returns:
            重建后的文档行；文档不存在时返回 None；源文件缺失时返回状态为
            ``failed`` 的文档行
        """
        document = self.get_document(document_id)
        if document is None:
            return None

        path = self._workspace.resolve(document.space_id, document.file_path)
        if not path.is_file():
            self._mark_failed(document_id, f"源文件已不存在: {document.file_path}")
            return self.get_document(document_id)

        text = _decode(path.read_bytes())
        self._clear_chunks(document_id)
        self._index(document.space_id, document_id, text)
        return self.get_document(document_id)

    # ─── 检索 ────────────────────────────────────────────────────────────

    def search(self, space_id: int | str, query: str, top_k: int = 5) -> list[SearchHit]:
        """检索相关切片，优先向量检索，失败或未启用时降级为词法检索。

        Args:
            space_id: 空间 ID
            query: 检索词；空白查询直接返回空列表
            top_k: 返回条数上限

        Returns:
            按相关度降序的命中列表，无命中时为空列表
        """
        keyword = (query or "").strip()
        if not keyword:
            return []

        if self.vector_enabled:
            try:
                return self._vector_search(space_id, keyword, top_k)
            except Exception as exc:  # 向量库异常不应导致检索整体失败
                logger.warning("向量检索失败，降级为词法检索", error=str(exc), space_id=str(space_id))

        return self._lexical_search(space_id, keyword, top_k)

    def _vector_search(self, space_id: int | str, query: str, top_k: int) -> list[SearchHit]:
        """向量检索，返回结果前用 ``chroma_id`` 回查切片与文档名。"""
        raw_hits = self._vector_store.query(query, top_k)  # type: ignore[union-attr]
        if not raw_hits:
            return []

        chroma_ids = [hit["id"] for hit in raw_hits]
        with self._session_scope() as session:
            rows = session.scalars(
                select(KnowledgeChunk).where(KnowledgeChunk.chroma_id.in_(chroma_ids))
            ).all()
            chunk_map = {row.chroma_id: row for row in rows}
            doc_ids = {row.document_id for row in rows}
            docs = {
                doc.id: doc.filename
                for doc in session.scalars(
                    select(KnowledgeDocument).where(KnowledgeDocument.id.in_(doc_ids))
                ).all()
            }

        hits: list[SearchHit] = []
        for raw in raw_hits:
            chunk = chunk_map.get(raw["id"])
            if chunk is None:
                continue
            hits.append(
                SearchHit(
                    content=chunk.content,
                    document_name=docs.get(chunk.document_id, ""),
                    chunk_id=chunk.id,
                    seq=chunk.seq,
                    score=float(raw.get("score") or 0.0),
                )
            )
        return hits

    def _lexical_search(self, space_id: int | str, query: str, top_k: int) -> list[SearchHit]:
        """词法降级检索：整句命中优先，其次按分词命中率排序。"""
        with self._session_scope() as session:
            candidates = session.scalars(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.space_id == int(space_id),
                    KnowledgeChunk.content.like(f"%{query}%"),
                )
            ).all()
            if not candidates:
                candidates = self._loose_candidates(session, space_id, query)

            doc_ids = {c.document_id for c in candidates}
            docs = {
                doc.id: doc.filename
                for doc in session.scalars(
                    select(KnowledgeDocument).where(KnowledgeDocument.id.in_(doc_ids))
                ).all()
            }

        tokens = _tokenize(query)
        scored: list[SearchHit] = []
        for chunk in candidates:
            score = _lexical_score(chunk.content, query, tokens)
            if score <= 0:
                continue
            scored.append(
                SearchHit(
                    content=chunk.content,
                    document_name=docs.get(chunk.document_id, ""),
                    chunk_id=chunk.id,
                    seq=chunk.seq,
                    score=score,
                )
            )

        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:top_k]

    @staticmethod
    def _loose_candidates(session: Session, space_id: int | str, query: str) -> list[KnowledgeChunk]:
        """整句未命中时退一步：任一分词命中即可作为候选。"""
        tokens = _tokenize(query)
        if not tokens:
            return []
        from sqlalchemy import or_

        conditions = [KnowledgeChunk.content.like(f"%{t}%") for t in tokens if len(t) >= 2]
        if not conditions:
            return []
        return list(
            session.scalars(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.space_id == int(space_id),
                    or_(*conditions),
                )
            ).all()
        )

    # ─── 管理 ────────────────────────────────────────────────────────────

    def list_documents(self, space_id: int | str) -> list[KnowledgeDocument]:
        """列出空间下的文档，按创建时间倒序。"""
        with self._session_scope() as session:
            return list(
                session.scalars(
                    select(KnowledgeDocument)
                    .where(KnowledgeDocument.space_id == int(space_id))
                    .order_by(KnowledgeDocument.created_at.desc())
                ).all()
            )

    def get_document(self, document_id: int) -> KnowledgeDocument | None:
        """按 ID 取文档行，不存在时返回 None。"""
        with self._session_scope() as session:
            return session.get(KnowledgeDocument, document_id)

    def list_chunks(self, document_id: int) -> list[KnowledgeChunk]:
        """列出文档的切片，按 ``seq`` 升序。"""
        with self._session_scope() as session:
            return list(
                session.scalars(
                    select(KnowledgeChunk)
                    .where(KnowledgeChunk.document_id == document_id)
                    .order_by(KnowledgeChunk.seq)
                ).all()
            )

    def delete_document(self, document_id: int) -> None:
        """删除文档及其切片、向量与磁盘源文件。

        副作用：删除向量库条目、数据库行与磁盘文件。向量或文件删除失败只记录
        日志，数据库记录仍会被清理。
        """
        document = self.get_document(document_id)
        if document is None:
            return

        chunk_ids = [c.chroma_id for c in self.list_chunks(document_id) if c.chroma_id]
        if chunk_ids and self._vector_store is not None:
            try:
                self._vector_store.delete(chunk_ids)
            except Exception as exc:
                logger.warning("向量删除失败（切片仍从库中移除）", error=str(exc))

        with self._session_scope() as session:
            session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id))
            session.execute(delete(KnowledgeDocument).where(KnowledgeDocument.id == document_id))
            session.flush()

        try:
            self._workspace.resolve(document.space_id, document.file_path).unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("源文件删除失败", error=str(exc), path=document.file_path)

        logger.info("知识库文档已删除", document_id=str(document_id))

    # ─── 内部 ────────────────────────────────────────────────────────────

    def _index(self, space_id: int | str, document_id: int, text: str) -> None:
        """切片、写入切片表并尝试向量化；向量化失败时该文档降级为词法索引。"""
        pieces = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
        if not pieces:
            self._mark_failed(document_id, "切片结果为空")
            return

        chroma_ids: list[str] = []
        index_mode = "lexical"

        if self.vector_enabled:
            try:
                chroma_ids = self._upsert_vectors(space_id, document_id, pieces)
                index_mode = "vector"
            except Exception as exc:
                logger.warning(
                    "向量化失败，该文档降级为词法索引",
                    document_id=str(document_id),
                    error=str(exc),
                )
                chroma_ids = []
                index_mode = "lexical"

        with self._session_scope() as session:
            for seq, piece in enumerate(pieces):
                session.add(
                    KnowledgeChunk(
                        document_id=document_id,
                        space_id=int(space_id),
                        seq=seq,
                        content=piece,
                        chroma_id=chroma_ids[seq] if seq < len(chroma_ids) else None,
                    )
                )
            document = session.get(KnowledgeDocument, document_id)
            if document is not None:
                document.status = "indexed"
                document.index_mode = index_mode
                document.chunk_count = len(pieces)
                document.error = ""
                document.updated_at = local_now()
            session.flush()

    def _upsert_vectors(self, space_id: int | str, document_id: int, pieces: list[str]) -> list[str]:
        """写入向量库，返回每个切片对应的向量 ID。

        Raises:
            ValueError: embedding 返回的向量数与切片数不一致
        """
        ids = [f"{document_id}-{seq}" for seq in range(len(pieces))]
        vectors = self._embedder(pieces)  # type: ignore[misc]
        if len(vectors) != len(pieces):
            raise ValueError(f"embedding 数量与切片数不一致: {len(vectors)} != {len(pieces)}")
        self._vector_store.add(  # type: ignore[union-attr]
            ids=ids,
            documents=pieces,
            metadatas=[
                {"space_id": int(space_id), "document_id": document_id, "seq": seq}
                for seq in range(len(pieces))
            ],
        )
        return ids

    def _clear_chunks(self, document_id: int) -> None:
        """删除文档的全部切片及其向量，用于重建索引前清理。"""
        chunk_ids = [c.chroma_id for c in self.list_chunks(document_id) if c.chroma_id]
        if chunk_ids and self._vector_store is not None:
            try:
                self._vector_store.delete(chunk_ids)
            except Exception as exc:
                logger.warning("重新索引时向量删除失败", error=str(exc))
        with self._session_scope() as session:
            session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id))
            session.flush()

    def _mark_failed(self, document_id: int, error: str) -> None:
        """把文档标记为 ``failed`` 并记录错误摘要（最多 500 字符）。"""
        with self._session_scope() as session:
            document = session.get(KnowledgeDocument, document_id)
            if document is not None:
                document.status = "failed"
                document.error = error[:500]
                document.updated_at = local_now()
            session.flush()


# ---------------------------------------------------------------------------
# 切片
# ---------------------------------------------------------------------------


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """把长文本切成带重叠的片段。

    断点优先取段落边界，其次句子边界，最后硬切，避免片段从句子中间开始。

    Args:
        text: 原文
        size: 单片最大字符数
        overlap: 相邻片段重叠字符数

    Returns:
        片段列表，已去除纯空白片段

    Raises:
        ValueError: ``size`` 非正，或 ``overlap`` 不满足 ``0 <= overlap < size``
    """
    if size <= 0:
        raise ValueError("size 必须为正数")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap 必须满足 0 <= overlap < size")

    stripped = (text or "").strip()
    if not stripped:
        return []

    chunks: list[str] = []
    start = 0
    total = len(stripped)

    while start < total:
        end = min(start + size, total)
        if end < total:
            end = _find_break(stripped, start, end, size)
        piece = stripped[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= total:
            break
        # 下一片从 end 往前退 overlap 个字符，保证衔接处有冗余
        start = max(end - overlap, start + 1)

    return chunks


def _find_break(text: str, start: int, end: int, size: int) -> int:
    """在 ``[start, end]`` 内向前查找断点，找不到时返回原 ``end``。"""
    window_start = max(start + int(size * 0.5), start)

    for separator in ("\n\n", "\n", "。", "！", "？", ". ", "; ", "；"):
        position = text.rfind(separator, window_start, end)
        if position != -1:
            return position + len(separator)
    return end


# ---------------------------------------------------------------------------
# 词法打分
# ---------------------------------------------------------------------------

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}")


def _tokenize(text: str) -> list[str]:
    """粗粒度分词：英文按词、中文按连续片段，不引入分词依赖。"""
    tokens: list[str] = []
    for match in _TOKEN_PATTERN.finditer(text or ""):
        token = match.group(0)
        if len(token) >= 2:
            tokens.append(token.lower())
    return tokens


def _lexical_score(content: str, query: str, tokens: list[str]) -> float:
    """词法打分：整句命中权重高，分词命中按覆盖率累加。"""
    lowered = content.lower()
    score = 3.0 if query.lower() in lowered else 0.0
    if not tokens:
        return score

    hits = sum(1 for token in tokens if token in lowered)
    coverage = hits / len(tokens)
    return score + coverage + math.log1p(hits) * 0.1


# ---------------------------------------------------------------------------
# 杂项
# ---------------------------------------------------------------------------


def _decode(data: bytes) -> str:
    """按 utf-8、utf-8-sig、gbk、latin-1 依次尝试解码，全部失败时替换非法字节。"""
    for encoding in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _guess_mime(suffix: str) -> str:
    """按扩展名推断 MIME 类型，未知时返回 ``text/plain``。"""
    return {
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".json": "application/json",
        ".yaml": "application/yaml",
        ".yml": "application/yaml",
        ".csv": "text/csv",
    }.get(suffix, "text/plain")


def _default_session_scope() -> SessionScope:
    """返回默认 Session 上下文工厂，每次调用新开一个会话。"""
    def _scope() -> AbstractContextManager[Session]:
        from src.core.database.database_manager import get_db_manager

        return get_db_manager().get_session()

    return _scope


def format_hits(hits: list[SearchHit]) -> str:
    """把检索结果渲染为 JSON 字符串，供工具返回。"""
    return json.dumps([hit.to_dict() for hit in hits], ensure_ascii=False)
