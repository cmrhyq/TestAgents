"""Skill 启用状态的持久化。

内容真源是文件，但「用户关掉了某个 skill」这个意志必须落库——否则重启就丢。
表里一行代表「某空间对某 skill 的显式设置」：

    space_id 为具体空间   → 该空间的设置（优先级高）
    space_id 为 NULL      → 全局默认设置

没有对应行时按「启用」处理（默认开启），这样新装进来的 skill 立刻可用。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.data.models.skill import Skill
from src.skill.repository import DiscoveredSkill


class SkillRegistry:
    """基于 ``skill`` 表的启用状态读写。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def enabled_map(self, space_id: int | str | None) -> dict[str, bool]:
        """返回该上下文下每个 skill 名对应的启用状态（只含显式设置过的）。"""
        rows = self._rows_for(space_id)
        return {row.name: bool(row.enabled) for row in rows}

    def is_enabled(self, name: str, space_id: int | str | None) -> bool:
        return self.enabled_map(space_id).get(name, True)

    def set_enabled(
        self,
        name: str,
        space_id: int | str | None,
        enabled: bool,
        scope: str = "space",
        directory: str = "",
    ) -> None:
        """写入启用状态（存在则更新）。"""
        existing = self._find(name, space_id)
        if existing is not None:
            existing.enabled = 1 if enabled else 0
            self._session.flush()
            return

        self._session.add(
            Skill(
                name=name,
                scope=scope,
                space_id=int(space_id) if space_id is not None else None,
                directory=directory,
                enabled=1 if enabled else 0,
            )
        )
        self._session.flush()

    def sync(self, skills: list[DiscoveredSkill], space_id: int | str | None) -> None:
        """把发现结果同步进表，顺带刷新目录/描述等元信息。

        只更新已存在的行，**不新建**——新建应当由显式操作（启停/导入）触发，
        否则扫描一次就多出一堆行，等于把文件状态复制成一份易腐的副本。
        """
        if space_id is None:
            return
        for skill in skills:
            row = self._find(skill.name, space_id)
            if row is None:
                continue
            row.directory = skill.display_path
            row.description = skill.manifest.description
            row.when_to_use = skill.manifest.when_to_use
            row.version = skill.manifest.version
            row.scope = skill.scope
        self._session.flush()

    # ─── 内部 ────────────────────────────────────────────────────────────

    def _rows_for(self, space_id: int | str | None) -> list[Skill]:
        stmt = select(Skill).where(Skill.space_id.is_(None))
        if space_id is not None:
            stmt = select(Skill).where(
                (Skill.space_id == int(space_id)) | (Skill.space_id.is_(None))
            )
        return list(self._session.scalars(stmt).all())

    def _find(self, name: str, space_id: int | str | None) -> Skill | None:
        stmt = select(Skill).where(Skill.name == name, Skill.space_id == (int(space_id) if space_id is not None else None))
        return self._session.scalars(stmt).first()
