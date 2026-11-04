"""知识库路由：文档上传、切片查看、检索预览、删除与重建索引。

上传的文件先落盘 ``docs/`` 再切片；向量能力不可用时降级为词法检索，
文档行的 ``index_mode`` 记录实际生效的索引方式。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from data.constant.constants import MAX_UPLOAD_BYTES
from src.api.deps import get_db
from src.core.errors import NotFoundError, ValidationError
from src.data.services import SpaceService
from src.memory import get_knowledge_base

router = APIRouter(tags=["知识库"])


class DocumentItem(BaseModel):
    """文档列表项。"""

    id: str
    space_id: str
    filename: str
    file_path: str
    mime: str
    size: int
    chunk_count: int
    status: str
    index_mode: str
    error: str = ""
    created_at: str
    updated_at: str


class DocumentListResponse(BaseModel):
    """文档列表响应；``vector_enabled`` 表示当前是否启用向量检索。"""

    items: list[DocumentItem]
    total: int
    vector_enabled: bool = False


class ChunkItem(BaseModel):
    """文档切片。"""

    id: str
    seq: int
    content: str


class SearchBody(BaseModel):
    """检索预览请求体。"""

    query: str = Field(..., min_length=1, description="检索关键词/问题")
    top_k: int = Field(default=5, ge=1, le=20)


def _to_item(doc) -> DocumentItem:
    """把文档模型转换为列表项。"""
    return DocumentItem(
        id=str(doc.id),
        space_id=str(doc.space_id),
        filename=doc.filename,
        file_path=doc.file_path,
        mime=doc.mime,
        size=doc.size,
        chunk_count=doc.chunk_count,
        status=doc.status,
        index_mode=doc.index_mode,
        error=doc.error,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.post("/spaces/{space_id}/documents", response_model=DocumentItem, status_code=201)
async def upload_document(
    space_id: int,
    file: UploadFile = File(..., description="需求/接口文档（md/txt/json/yaml/csv 等文本格式）"),
    db: Session = Depends(get_db),
):
    """上传并索引知识库文档。

    副作用：文件写入空间 ``docs/`` 目录并落库切片，可能调用嵌入模型。
    文件上限 20MB，且仅接受文本类后缀。

    Args:
        space_id: 目标空间 ID
        file: 上传文件，支持 md/txt/json/yaml/csv 等文本格式
        db: 请求级数据库会话

    Returns:
        新建文档记录，HTTP 201

    Raises:
        NotFoundError: 空间不存在，返回 HTTP 404
        ValidationError: 文件过大、后缀不支持或内容为空，返回 HTTP 422
    """
    SpaceService(db).get_or_raise(space_id, "空间不存在")

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValidationError(f"文档过大，上限 {MAX_UPLOAD_BYTES // 1024 // 1024}MB")

    try:
        document = get_knowledge_base(space_id).ingest(
            space_id,
            filename=file.filename or "unnamed.md",
            data=data,
            mime=file.content_type or "",
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    return _to_item(document)


@router.get("/spaces/{space_id}/documents", response_model=DocumentListResponse)
def list_documents(space_id: int, db: Session = Depends(get_db)):
    """列出空间下的知识库文档，按创建时间倒序。

    Args:
        space_id: 空间 ID
        db: 请求级数据库会话

    Returns:
        文档列表、总数与当前是否启用向量检索

    Raises:
        NotFoundError: 空间不存在，返回 HTTP 404
    """
    SpaceService(db).get_or_raise(space_id, "空间不存在")
    kb = get_knowledge_base(space_id)
    documents = kb.list_documents(space_id)
    return DocumentListResponse(
        items=[_to_item(d) for d in documents],
        total=len(documents),
        vector_enabled=kb.vector_enabled,
    )


@router.get("/documents/{document_id}/chunks", response_model=list[ChunkItem])
def list_chunks(document_id: int, db: Session = Depends(get_db)):
    """列出文档的全部切片，按序号升序。

    Args:
        document_id: 文档 ID
        db: 请求级数据库会话

    Returns:
        切片列表

    Raises:
        NotFoundError: 文档不存在，返回 HTTP 404
    """
    kb = get_knowledge_base()
    document = kb.get_document(document_id)
    if document is None:
        raise NotFoundError("文档不存在")
    return [
        ChunkItem(id=str(c.id), seq=c.seq, content=c.content)
        for c in get_knowledge_base(document.space_id).list_chunks(document_id)
    ]


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """删除文档，同时移除其切片、向量与磁盘源文件。

    向量删除失败只记录日志，不影响库中记录与文件的清理。

    Args:
        document_id: 文档 ID
        db: 请求级数据库会话

    Returns:
        无响应体，HTTP 204

    Raises:
        NotFoundError: 文档不存在，返回 HTTP 404
    """
    kb = get_knowledge_base()
    document = kb.get_document(document_id)
    if document is None:
        raise NotFoundError("文档不存在")
    get_knowledge_base(document.space_id).delete_document(document_id)


@router.post("/documents/{document_id}/reindex", response_model=DocumentItem)
def reindex_document(document_id: int, db: Session = Depends(get_db)):
    """以磁盘源文件为准重建切片索引。

    副作用：覆盖库中切片并重写向量。

    Args:
        document_id: 文档 ID
        db: 请求级数据库会话

    Returns:
        重建后的文档记录

    Raises:
        NotFoundError: 文档不存在，返回 HTTP 404
    """
    kb = get_knowledge_base()
    document = kb.get_document(document_id)
    if document is None:
        raise NotFoundError("文档不存在")

    updated = get_knowledge_base(document.space_id).reindex(document_id)
    if updated is None:
        raise NotFoundError("文档不存在")
    return _to_item(updated)


@router.post("/spaces/{space_id}/documents/search")
def search_documents(
    space_id: int,
    body: SearchBody,
    db: Session = Depends(get_db),
):
    """检索预览：按当前索引方式返回命中的切片。

    Args:
        space_id: 空间 ID
        body: 检索词与返回条数上限，``top_k`` 取值 1-20
        db: 请求级数据库会话

    Returns:
        含 ``query``、``vector_enabled`` 与命中切片列表的字典

    Raises:
        NotFoundError: 空间不存在，返回 HTTP 404
    """
    SpaceService(db).get_or_raise(space_id, "空间不存在")
    kb = get_knowledge_base(space_id)
    hits = kb.search(space_id, body.query, top_k=body.top_k)
    return {
        "query": body.query,
        "vector_enabled": kb.vector_enabled,
        "hits": [hit.to_dict() for hit in hits],
    }
