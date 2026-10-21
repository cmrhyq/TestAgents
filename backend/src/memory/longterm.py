"""跨会话记忆（LongTermMemory）。

设计取舍：**不用向量检索**。

记忆条目是「结论型短文本」（偏好、决策、已知坑、术语），量级几十到几百条，
需要的是**精确命中**而不是语义相似。SQLite ``LIKE`` 足够，且：
- 零外部依赖 —— 向量库挂了记忆照样能用
- 结果可解释 —— 用户问「为什么 Agent 提到这条」，能答出「命中关键词 X」
- 可排序 —— 按更新时间倒序，最近的结论优先

真源是 ``space_memory`` 表；``memory/MEMORY.md`` 是给 Agent「读文件」用的只读镜像，
每次写操作后全量重建。镜像不做增量更新——全量重建不会漏、不会和 DB 漂移。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.core.logging import get_logger
from src.data.models.base import local_now
from src.data.models.space_memory import SpaceMemory
from src.workspace.manager import WorkspaceManager

logger = get_logger(__name__)

VALID_CATEGORIES = ("fact", "decision", "preference", "issue", "glossary")

CATEGORY_TITLES = {
    "decision": "决策",
    "preference": "偏好",
    "issue": "已知问题",
    "glossary": "术语",
    "fact": "事实",
}

# 召回时返回的默认条数上限：注入 prompt 的内容不是越多越好，
# 记忆过多会稀释关键信息，也会挤占工具结果的空间
DEFAULT_RECALL_LIMIT = 20

SessionScope = Callable[[], AbstractContextManager[Session]]


class LongTermMemory:
    """按空间隔离的跨会话记忆。

    Args:
        workspace: 工作目录管理器；None 时取全局单例
        session_scope: 返回 Session 上下文管理器的工厂；None 时用全局数据库单例。
            显式注入是为了单测能跑在临时库上，不必启动整个应用。
    """

    def __init__(
        self,
        workspace: WorkspaceManager | None = None,
        session_scope: SessionScope | None = None,
    ) -> None:
        if workspace is None:
            from src.workspace.manager import get_workspace_manager

            workspace = get_workspace_manager()
        self._workspace = workspace
        self._session_scope = session_scope or _default_session_scope()

    # ─── 写 ──────────────────────────────────────────────────────────────

    def add(
        self,
        space_id: int | str,
        title: str,
        content: str,
        category: str = "fact",
        tags: list[str] | None = None,
        source_conversation_id: int | None = None,
    ) -> SpaceMemory:
        """新增一条记忆，并刷新 MEMORY.md 镜像。"""
        if category not in VALID_CATEGORIES:
            raise ValueError(f"非法的 category: {category}（可选: {', '.join(VALID_CATEGORIES)}）")
        if not (title or "").strip():
            raise ValueError("记忆标题不能为空")

        entry = SpaceMemory(
            space_id=int(space_id),
            title=title.strip(),
            content=(content or "").strip(),
            category=category,
            tags=_dump_tags(tags),
            source_conversation_id=source_conversation_id,
        )
        with self._session_scope() as session:
            session.add(entry)
            session.flush()
            session.refresh(entry)

        self.sync_markdown(space_id)
        logger.info("记忆已写入", space_id=str(space_id), memory_id=str(entry.id), category=category)
        return entry

    def update(self, memory_id: int, **fields) -> SpaceMemory:
        """局部更新记忆。"""
        allowed = {"title", "content", "category", "tags", "status"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"不支持更新的字段: {', '.join(sorted(unknown))}")

        if "category" in fields and fields["category"] not in VALID_CATEGORIES:
            raise ValueError(f"非法的 category: {fields['category']}")
        if "tags" in fields:
            fields["tags"] = _dump_tags(fields["tags"])

        with self._session_scope() as session:
            entry = session.get(SpaceMemory, memory_id)
            if entry is None:
                raise LookupError(f"记忆不存在: {memory_id}")
            for key, value in fields.items():
                if value is not None:
                    setattr(entry, key, value)
            entry.updated_at = local_now()
            session.flush()
            session.refresh(entry)
            space_id = entry.space_id

        self.sync_markdown(space_id)
        return entry

    def delete(self, memory_id: int, hard: bool = False) -> None:
        """删除记忆。默认软删（``status=0``），``hard=True`` 物理删除。"""
        with self._session_scope() as session:
            entry = session.get(SpaceMemory, memory_id)
            if entry is None:
                return
            space_id = entry.space_id
            if hard:
                session.delete(entry)
            else:
                entry.status = 0
                entry.updated_at = local_now()
            session.flush()

        self.sync_markdown(space_id)

    # ─── 读 ──────────────────────────────────────────────────────────────

    def list(
        self,
        space_id: int | str,
        category: str | None = None,
        keyword: str | None = None,
        limit: int = 100,
    ) -> list[SpaceMemory]:
        """列出记忆（不含软删），按更新时间倒序。"""
        stmt = select(SpaceMemory).where(
            SpaceMemory.space_id == int(space_id),
            SpaceMemory.status == 1,
        )
        if category:
            stmt = stmt.where(SpaceMemory.category == category)
        if keyword:
            pattern = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    SpaceMemory.title.like(pattern),
                    SpaceMemory.content.like(pattern),
                    SpaceMemory.tags.like(pattern),
                )
            )
        stmt = stmt.order_by(SpaceMemory.updated_at.desc(), SpaceMemory.id.desc()).limit(limit)

        with self._session_scope() as session:
            return list(session.scalars(stmt).all())

    def recall(self, space_id: int | str, query: str, limit: int = DEFAULT_RECALL_LIMIT) -> list[SpaceMemory]:
        """按关键词召回相关记忆；空查询返回最近若干条。

        关键词从查询里**抽取**而不是整句匹配：用户说的是「帮我看看登录接口的鉴权方式」，
        记忆里存的是「鉴权方式：Bearer JWT」。整句 ``LIKE`` 永远命中不了，
        抽取后按 2-gram 拆分才能对上。
        """
        keywords = extract_keywords(query)
        if not keywords:
            return self.list(space_id, limit=limit)
        return self.list_any(space_id, keywords, limit=limit)

    def list_any(self, space_id: int | str, keywords: list[str], limit: int = 100) -> list[SpaceMemory]:
        """命中任一关键词即返回（OR 语义），按更新时间倒序。"""
        if not keywords:
            return []

        clauses = []
        for keyword in keywords:
            pattern = f"%{keyword}%"
            clauses.extend(
                (
                    SpaceMemory.title.like(pattern),
                    SpaceMemory.content.like(pattern),
                    SpaceMemory.tags.like(pattern),
                )
            )

        stmt = (
            select(SpaceMemory)
            .where(SpaceMemory.space_id == int(space_id), SpaceMemory.status == 1)
            .where(or_(*clauses))
            .order_by(SpaceMemory.updated_at.desc(), SpaceMemory.id.desc())
            .limit(limit)
        )

        with self._session_scope() as session:
            return list(session.scalars(stmt).all())


    def count(self, space_id: int | str) -> int:
        return len(self.list(space_id, limit=10_000))

    # ─── 镜像 ────────────────────────────────────────────────────────────

    def sync_markdown(self, space_id: int | str) -> Path:
        """全量重建 ``memory/MEMORY.md``。

        Returns:
            镜像文件路径
        """
        entries = self.list(space_id, limit=10_000)
        path = self._workspace.space_dir(space_id) / "memory" / "MEMORY.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._render(entries), encoding="utf-8")
        return path.resolve()

    @staticmethod
    def _render(entries: list[SpaceMemory]) -> str:
        """渲染镜像正文。"""
        header = (
            "# 空间记忆\n\n"
            "> 本文件由系统根据记忆库自动生成，**手改会被覆盖**。\n"
            "> 要增删改记忆，请在前端「记忆」面板操作，或调用记忆 API。\n"
            f"> 最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"> 条目数：{len(entries)}\n"
        )

        if not entries:
            return header + "\n_（尚无记忆条目）_\n"

        # 按类别分组，组内保持「更新时间倒序」
        grouped: dict[str, list[SpaceMemory]] = {}
        for entry in entries:
            grouped.setdefault(entry.category, []).append(entry)

        order = [c for c in VALID_CATEGORIES if c in grouped]
        sections: list[str] = []
        for category in order:
            lines = [f"## {category}（{CATEGORY_TITLES.get(category, category)}）", ""]
            for entry in grouped[category]:
                lines.append(f"### {entry.title}")
                if entry.content:
                    lines.append(entry.content)
                meta_parts = []
                tags = _load_tags(entry.tags)
                if tags:
                    meta_parts.append(" ".join(f"#{t}" for t in tags))
                meta_parts.append(entry.updated_at[:16].replace("T", " "))
                lines.append(f"_{' · '.join(meta_parts)}_")
                lines.append("")
            sections.append("\n".join(lines).rstrip())

        return header + "\n" + "\n\n".join(sections) + "\n"


# 中文没有空格，无法按分隔符切词；这里用 2-gram 近似。
# 精度不如分词器，但零依赖、可解释（命中哪个关键词能说清楚），
# 对「几十到几百条结论型短文本」的规模完全够用。
_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
_ASCII_WORD = re.compile(r"[A-Za-z0-9_]{2,}")

# 关键词数量上限：每个关键词生成 3 个 LIKE 条件，
# 抽太多会让 SQL 变长且几乎必然误命中
MAX_RECALL_KEYWORDS = 12

# 短中文片段整体作为一个关键词更精确（「鉴权」比「鉴」+「权」好用）
_SHORT_CJK = 4


def extract_keywords(text: str, limit: int = MAX_RECALL_KEYWORDS) -> list[str]:
    """从自然语言查询里抽取检索关键词。

    ASCII 片段整词保留（``auth`` / ``token_v2``），中文按长度二选一：
    4 字以内整体保留，更长的切 2-gram（保证「登录鉴权方式」能命中「鉴权」）。

    Args:
        text: 用户查询
        limit: 返回关键词上限

    Returns:
        去重后的关键词列表（保持出现顺序）
    """
    if not text or not text.strip():
        return []

    keywords: list[str] = []
    seen: set[str] = set()

    def push(value: str) -> None:
        value = value.strip()
        if len(value) < 2 or value in seen:
            return
        seen.add(value)
        keywords.append(value)

    for match in _ASCII_WORD.finditer(text):
        push(match.group())

    for match in _CJK_RUN.finditer(text):
        run = match.group()
        if len(run) <= _SHORT_CJK:
            push(run)
            continue
        for index in range(len(run) - 1):
            push(run[index : index + 2])

    return keywords[:limit]


def _default_session_scope() -> SessionScope:
    """默认从全局数据库管理器取会话。"""

    def _scope() -> AbstractContextManager[Session]:
        from src.core.database.database_manager import get_db_manager

        return get_db_manager().get_session()

    return _scope


def _dump_tags(tags: list[str] | None) -> str:
    import json

    cleaned = [str(t).strip() for t in (tags or []) if str(t).strip()]
    return json.dumps(cleaned, ensure_ascii=False)


def _load_tags(raw: str | None) -> list[str]:
    import json

    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    return [str(t) for t in value] if isinstance(value, list) else []
