"""记忆管理路由：跨会话记忆的增删改查与镜像重建。

真源是 ``space_memory`` 表，``memory/MEMORY.md`` 为其只读镜像，
每次写操作后全量重建。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.core.errors import NotFoundError, ValidationError
from src.data.services import SpaceService
from src.memory import get_long_term_memory
from src.memory.longterm import CATEGORY_TITLES, VALID_CATEGORIES

router = APIRouter(tags=["记忆管理"])


class MemoryItem(BaseModel):
    """记忆条目响应体。"""

    id: str
    space_id: str
    title: str
    content: str
    category: str
    category_label: str
    tags: list[str] = Field(default_factory=list)
    source_conversation_id: str | None = None
    created_at: str
    updated_at: str


class MemoryListResponse(BaseModel):
    """记忆列表响应。"""

    items: list[MemoryItem]
    total: int


class MemoryCreateBody(BaseModel):
    """新建记忆请求体。"""

    title: str = Field(..., min_length=1, max_length=200, description="标题")
    content: str = Field(default="", description="内容")
    category: str = Field(default="fact", description=f"分类: {', '.join(VALID_CATEGORIES)}")
    tags: list[str] = Field(default_factory=list, description="标签")


class MemoryUpdateBody(BaseModel):
    """更新记忆请求体（所有字段可选）。"""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = None
    category: str | None = None
    tags: list[str] | None = None

    def to_fields(self) -> dict:
        """返回非空字段，供局部更新使用。"""
        return {k: v for k, v in self.model_dump().items() if v is not None}


def _to_item(entry) -> MemoryItem:
    """把记忆模型转换为响应项；``tags`` 解析失败时置为空列表。"""
    import json

    try:
        tags = json.loads(entry.tags or "[]")
    except (json.JSONDecodeError, TypeError):
        tags = []
    return MemoryItem(
        id=str(entry.id),
        space_id=str(entry.space_id),
        title=entry.title,
        content=entry.content,
        category=entry.category,
        category_label=CATEGORY_TITLES.get(entry.category, entry.category),
        tags=tags if isinstance(tags, list) else [],
        source_conversation_id=str(entry.source_conversation_id) if entry.source_conversation_id else None,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.get("/spaces/{space_id}/memories", response_model=MemoryListResponse)
def list_memories(
    space_id: int,
    category: str | None = Query(default=None, description="按分类筛选"),
    keyword: str | None = Query(default=None, description="关键字搜索"),
    db: Session = Depends(get_db),
):
    """列出空间下的记忆条目，按更新时间倒序。

    Args:
        space_id: 空间 ID
        category: 按分类过滤，取值见 ``VALID_CATEGORIES``
        keyword: 在标题、内容与标签中模糊匹配
        db: 请求级数据库会话

    Returns:
        记忆列表与总数

    Raises:
        NotFoundError: 空间不存在，返回 HTTP 404
        ValidationError: ``category`` 不在允许取值内，返回 HTTP 422
    """
    SpaceService(db).get_or_raise(space_id, "空间不存在")
    if category and category not in VALID_CATEGORIES:
        raise ValidationError(f"非法的分类: {category}")

    entries = get_long_term_memory().list(space_id, category=category, keyword=keyword)
    return MemoryListResponse(items=[_to_item(e) for e in entries], total=len(entries))


@router.post("/spaces/{space_id}/memories", response_model=MemoryItem, status_code=201)
def create_memory(space_id: int, body: MemoryCreateBody, db: Session = Depends(get_db)):
    """新建一条记忆，并重建 ``MEMORY.md`` 镜像。

    副作用：写库并覆盖镜像文件。

    Args:
        space_id: 空间 ID
        body: 标题、内容、分类与标签；分类需在允许取值内
        db: 请求级数据库会话

    Returns:
        新建记忆条目，HTTP 201

    Raises:
        NotFoundError: 空间不存在，返回 HTTP 404
        ValidationError: 分类非法或标题为空，返回 HTTP 422
    """
    SpaceService(db).get_or_raise(space_id, "空间不存在")
    try:
        entry = get_long_term_memory().add(
            space_id,
            title=body.title,
            content=body.content,
            category=body.category,
            tags=body.tags,
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return _to_item(entry)


@router.put("/memories/{memory_id}", response_model=MemoryItem)
def update_memory(memory_id: int, body: MemoryUpdateBody, db: Session = Depends(get_db)):
    """局部更新记忆，并重建 ``MEMORY.md`` 镜像。

    Args:
        memory_id: 记忆 ID
        body: 待更新字段，未传字段保持原值
        db: 请求级数据库会话

    Returns:
        更新后的记忆条目

    Raises:
        NotFoundError: 记忆不存在或已软删，返回 HTTP 404
        ValidationError: 字段名不支持或分类非法，返回 HTTP 422
    """
    _get_or_raise(db, memory_id)
    try:
        updated = get_long_term_memory().update(memory_id, **body.to_fields())
    except (ValueError, LookupError) as exc:
        raise ValidationError(str(exc)) from exc
    return _to_item(updated)


@router.delete("/memories/{memory_id}", status_code=204)
def delete_memory(
    memory_id: int,
    hard: bool = Query(default=False, description="true=物理删除，默认软删"),
    db: Session = Depends(get_db),
):
    """删除记忆，默认软删（``status=0``）并重建镜像。

    Args:
        memory_id: 记忆 ID
        hard: 为 True 时物理删除，默认仅置状态位
        db: 请求级数据库会话

    Returns:
        无响应体，HTTP 204

    Raises:
        NotFoundError: 记忆不存在或已软删，返回 HTTP 404
    """
    _get_or_raise(db, memory_id)
    get_long_term_memory().delete(memory_id, hard=hard)


@router.post("/spaces/{space_id}/memories/sync")
def sync_memory_markdown(space_id: int, db: Session = Depends(get_db)):
    """强制全量重建 ``memory/MEMORY.md`` 镜像。

    副作用：覆盖空间目录下的镜像文件。

    Args:
        space_id: 空间 ID
        db: 请求级数据库会话

    Returns:
        ``{"ok": True, "path": 镜像文件绝对路径}``

    Raises:
        NotFoundError: 空间不存在，返回 HTTP 404
    """
    SpaceService(db).get_or_raise(space_id, "空间不存在")
    path = get_long_term_memory().sync_markdown(space_id)
    return {"ok": True, "path": str(path)}


def _get_or_raise(session: Session, memory_id: int) -> None:
    """确认记忆存在且未被软删。

    Raises:
        NotFoundError: 记录不存在或 ``status == 0``
    """
    from src.data.models.space_memory import SpaceMemory

    entry = session.get(SpaceMemory, memory_id)
    if entry is None or entry.status == 0:
        raise NotFoundError("记忆不存在")
