"""知识库路由。

上传 → 落盘 ``docs/`` → 切片 → （可选）向量索引。
检索能力有降级：向量库不可用时走词法匹配，文档行上的 ``index_mode`` 会如实反映。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.core.errors import NotFoundError, ValidationError
from src.data.services import SpaceService
from src.memory import get_knowledge_base

router = APIRouter(tags=["知识库"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


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
    items: list[DocumentItem]
    total: int
    vector_enabled: bool = False


class ChunkItem(BaseModel):
    id: str
    seq: int
    content: str


class SearchBody(BaseModel):
    """检索预览请求体。"""

    query: str = Field(..., min_length=1, description="检索关键词/问题")
    top_k: int = Field(default=5, ge=1, le=20)


def _to_item(doc) -> DocumentItem:
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
    """上传并索引知识库文档。"""
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
    """列出空间下的知识库文档。"""
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
    """查看文档切片（排障与效果评估用）。"""
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
    """删除文档及其切片、向量、磁盘文件。"""
    kb = get_knowledge_base()
    document = kb.get_document(document_id)
    if document is None:
        raise NotFoundError("文档不存在")
    get_knowledge_base(document.space_id).delete_document(document_id)


@router.post("/documents/{document_id}/reindex", response_model=DocumentItem)
def reindex_document(document_id: int, db: Session = Depends(get_db)):
    """以磁盘文件为准重建切片索引。"""
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
    """检索预览：在界面上直接验证「Agent 能查到什么」。"""
    SpaceService(db).get_or_raise(space_id, "空间不存在")
    kb = get_knowledge_base(space_id)
    hits = kb.search(space_id, body.query, top_k=body.top_k)
    return {
        "query": body.query,
        "vector_enabled": kb.vector_enabled,
        "hits": [hit.to_dict() for hit in hits],
    }
