"""Skill 启用状态的持久化。

文件是内容真源，启用状态落库以免重启丢失。``space_id`` 为具体空间表示空间级设置
（优先级高于全局），为 NULL 表示全局默认；无对应行时按启用处理。
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
        """返回 skill 是否启用；无显式设置时视为启用。"""
        return self.enabled_map(space_id).get(name, True)

    def set_enabled(
        self,
        name: str,
        space_id: int | str | None,
        enabled: bool,
        scope: str = "space",
        directory: str = "",
    ) -> None:
        """写入启用状态，已存在则更新。

        副作用：写 ``skill`` 表并 flush，提交由调用方的事务负责。

        Args:
            name: skill 名
            space_id: 空间 ID；None 表示全局默认
            enabled: 目标状态
            scope: 作用域标记，仅新建行时写入
            directory: skill 目录展示路径，仅新建行时写入
        """
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
        """把发现结果同步进表，刷新目录、描述等元信息。

        只更新已存在的行，不新建行；新建由启停或导入等显式操作触发。
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
        """返回全局行与指定空间的行；``space_id`` 为 None 时只返回全局行。"""
        stmt = select(Skill).where(Skill.space_id.is_(None))
        if space_id is not None:
            stmt = select(Skill).where(
                (Skill.space_id == int(space_id)) | (Skill.space_id.is_(None))
            )
        return list(self._session.scalars(stmt).all())

    def _find(self, name: str, space_id: int | str | None) -> Skill | None:
        """按 skill 名与空间定位唯一行，不跨空间回退。"""
        stmt = select(Skill).where(Skill.name == name, Skill.space_id == (int(space_id) if space_id is not None else None))
        return self._session.scalars(stmt).first()
